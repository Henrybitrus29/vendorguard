"""Security alerts: what triggers them, what they contain, and what they must never do."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import alerts, tasks
from app.db import SessionLocal
from app.models import AlertLog, Submission, User
from app.security import hash_password

INJECTION_FLAGS = ["injection_pattern:force_approval", "model_flagged_injection"]


class Receiver:
    """A real local HTTP server that records what the webhook would receive."""

    def __init__(self, status=200):
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.requests.append((dict(self.headers), body))
                self.send_response(status)
                self.end_headers()

            def log_message(self, *_):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook/SECRET-TOKEN"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def receiver(monkeypatch):
    r = Receiver()
    monkeypatch.setattr(alerts.settings, "alert_webhook_url", r.url)
    monkeypatch.setattr(alerts.settings, "alert_allow_private", True)
    monkeypatch.setattr(alerts.settings, "alert_webhook_secret", "s3cret")
    monkeypatch.setattr(alerts.settings, "alert_format", "generic")
    monkeypatch.setattr(alerts.time, "sleep", lambda _: None)
    yield r
    r.close()


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def make_submission(db, title="Acme MSA", flags=None, vendor_email="v@example.com"):
    vendor = db.query(User).filter_by(email=vendor_email).first()
    if not vendor:
        vendor = User(email=vendor_email, password_hash=hash_password("a-long-password-1"), role="vendor")
        db.add(vendor)
        db.flush()
    sub = Submission(vendor_id=vendor.id, title=title, status="Human_Review", stage="decided",
                     ai_decision="HUMAN_REVIEW", ai_confidence=0.5, flags=flags or [])
    db.add(sub)
    db.commit()
    return sub


# ── what triggers an alert ──

def test_severity_levels():
    assert alerts.severity_for(["injection_pattern:force_approval"]) == "high"
    assert alerts.severity_for(["model_flagged_injection"]) == "high"
    assert alerts.severity_for(["tax_id_not_found_in_text"]) == "medium"
    assert alerts.severity_for(["empty_text", "evaluation_error"]) is None
    assert alerts.severity_for([]) is None


def test_nothing_is_sent_when_alerts_are_not_configured(db, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_webhook_url", "")
    assert alerts.maybe_alert(db, make_submission(db, flags=INJECTION_FLAGS), INJECTION_FLAGS) is None


def test_non_security_flags_do_not_alert(db, receiver):
    assert alerts.maybe_alert(db, make_submission(db, flags=["empty_text"]), ["empty_text"]) is None
    assert receiver.requests == []


# ── what is sent ──

def test_alert_is_delivered_signed_and_contains_no_document_text(db, receiver):
    sub = make_submission(db, flags=INJECTION_FLAGS)
    assert alerts.maybe_alert(db, sub, INJECTION_FLAGS) == "sent"

    headers, body = receiver.requests[0]
    event = json.loads(body)
    assert event["severity"] == "high" and event["submission_id"] == sub.id
    assert set(event["flags"]) == set(INJECTION_FLAGS)
    assert "document_text" not in event and "reasoning" not in event

    expected = alerts.sign("s3cret", headers["X-VendorGuard-Timestamp"], body)
    assert headers["X-VendorGuard-Signature"] == expected
    assert db.query(AlertLog).filter_by(submission_id=sub.id, status="sent").count() == 1


def test_slack_message_cannot_be_used_for_mention_or_link_injection(db, receiver, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_format", "slack")
    nasty = "<!channel> <https://evil.example|click> *urgent* `x` [link](http://evil)"
    sub = make_submission(db, title=nasty, flags=INJECTION_FLAGS)
    alerts.maybe_alert(db, sub, INJECTION_FLAGS)
    text = json.loads(receiver.requests[0][1])["text"]
    assert "<!channel>" not in text and "<https://evil" not in text and "](http" not in text


def test_teams_payload_is_an_adaptive_card(db, receiver, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_format", "teams")
    alerts.maybe_alert(db, make_submission(db, flags=INJECTION_FLAGS), INJECTION_FLAGS)
    payload = json.loads(receiver.requests[0][1])
    assert payload["attachments"][0]["contentType"] == "application/vnd.microsoft.card.adaptive"


def test_unsigned_when_no_secret(db, receiver, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_webhook_secret", "")
    alerts.maybe_alert(db, make_submission(db, flags=INJECTION_FLAGS), INJECTION_FLAGS)
    assert "X-VendorGuard-Signature" not in receiver.requests[0][0]


# ── abuse resistance ──

def test_per_vendor_hourly_cap_stops_alert_flooding(db, receiver, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_max_per_vendor_hour", 2)
    results = [alerts.maybe_alert(db, make_submission(db, title=f"doc {i}", flags=INJECTION_FLAGS), INJECTION_FLAGS)
               for i in range(4)]
    assert results == ["sent", "sent", "suppressed", "suppressed"]
    assert len(receiver.requests) == 2


def test_a_different_vendor_is_not_throttled_by_another(db, receiver, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_max_per_vendor_hour", 1)
    a = alerts.maybe_alert(db, make_submission(db, vendor_email="a@example.com", flags=INJECTION_FLAGS), INJECTION_FLAGS)
    b = alerts.maybe_alert(db, make_submission(db, vendor_email="b@example.com", flags=INJECTION_FLAGS), INJECTION_FLAGS)
    assert (a, b) == ("sent", "sent")


def test_failed_delivery_is_recorded_without_leaking_the_secret_url(db, monkeypatch):
    bad = Receiver(status=500)
    monkeypatch.setattr(alerts.settings, "alert_webhook_url", bad.url)
    monkeypatch.setattr(alerts.settings, "alert_allow_private", True)
    monkeypatch.setattr(alerts.time, "sleep", lambda _: None)
    try:
        sub = make_submission(db, flags=INJECTION_FLAGS)
        assert alerts.maybe_alert(db, sub, INJECTION_FLAGS) == "failed"
        row = db.query(AlertLog).filter_by(submission_id=sub.id).one()
        assert row.detail == "HTTP 500" and "SECRET-TOKEN" not in row.detail
        assert len(bad.requests) == 2  # one retry
    finally:
        bad.close()


@pytest.mark.parametrize("url", [
    "http://example.com/hook",                      # plain http
    "https://127.0.0.1/hook",                       # loopback
    "https://169.254.169.254/latest/meta-data",     # cloud metadata endpoint
    "https://10.0.0.5/hook",                        # private network
    "https://[::1]/hook",                           # IPv6 loopback
    "file:///etc/passwd",                           # wrong scheme
])
def test_ssrf_targets_are_blocked(url, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_allow_private", False)
    with pytest.raises(ValueError):
        alerts.validate_url(url)


# ── wired into the pipeline ──

class FlaggedAgent:
    def stream(self, state, stream_mode="updates"):
        yield {"classify_document": {}}
        yield {"finalize_decision": {
            "decision": "HUMAN_REVIEW", "status": "Human_Review", "compliance_passed": False,
            "confidence_score": 0.5, "reasoning": "Suspicious text.", "flags": INJECTION_FLAGS, "checks": {},
        }}


def test_pipeline_sends_an_alert_and_the_admin_can_see_it(make_vendor, admin_client, receiver, monkeypatch):
    monkeypatch.setattr(tasks, "agent_app", FlaggedAgent())
    v = make_vendor("pipe@example.com")
    import io
    r = v.post("/submissions", data={"title": "Sneaky doc"},
               files={"file": ("a.txt", io.BytesIO(b"Tax ID 12-3456789 vendor"), "text/plain")})
    assert r.status_code == 201
    assert len(receiver.requests) == 1
    detail = admin_client.get(f"/submissions/{r.json()['id']}").json()
    assert [a["status"] for a in detail["alerts"]] == ["sent"]
    assert detail["status"] == "Human_Review"


def test_an_alerting_crash_never_breaks_processing(make_vendor, admin_client, monkeypatch):
    monkeypatch.setattr(tasks, "agent_app", FlaggedAgent())
    monkeypatch.setattr(tasks, "maybe_alert", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("slack is down")))
    v = make_vendor("crash@example.com")
    import io
    r = v.post("/submissions", data={"title": "Doc"}, files={"file": ("a.txt", io.BytesIO(b"hello vendor doc"), "text/plain")})
    assert admin_client.get(f"/submissions/{r.json()['id']}").json()["status"] == "Human_Review"


# ── admin test button ──

def test_test_alert_endpoint(admin_client, make_vendor, receiver):
    assert admin_client.post("/admin/alerts/test").status_code == 200
    assert json.loads(receiver.requests[0][1])["severity"] == "test"
    assert make_vendor("nope@example.com").post("/admin/alerts/test").status_code == 403


def test_test_alert_when_not_configured(admin_client, monkeypatch):
    monkeypatch.setattr(alerts.settings, "alert_webhook_url", "")
    assert admin_client.post("/admin/alerts/test").status_code == 409
    assert admin_client.get("/admin/metrics").json()["alerts_configured"] is False
