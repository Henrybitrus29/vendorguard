"""Security alerts to Slack, Microsoft Teams, or any signed webhook.

Design rules:
* The webhook URL comes from the environment only (never from a user or a document), and is validated against
  private/loopback addresses and plain http to limit SSRF.
* The payload never contains document text. Vendor-controlled strings (the title) are sanitised so they cannot
  inject Slack mentions like <!channel> or Markdown links.
* A per-vendor hourly cap stops an attacker from flooding the SOC channel.
* Failures never break processing, and the secret URL is never logged or stored (only "HTTP 404"-style codes).
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import socket
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AlertLog, Submission, utcnow

log = logging.getLogger(__name__)
settings = get_settings()


# ───────── what deserves an alert ─────────

def severity_for(flags: list[str]) -> Optional[str]:
    if any(f.startswith("injection_pattern:") or f == "model_flagged_injection" for f in flags):
        return "high"
    if "tax_id_not_found_in_text" in flags:
        return "medium"
    return None


# ───────── payload building ─────────

def clean_text(value: str, limit: int = 80) -> str:
    """Make a vendor-controlled string safe to show in a chat message."""
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value or "")
    value = re.sub(r"[`*_~\[\]()<>]", "", value)
    return value.strip()[:limit]


def _slack_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_event(submission_id: str, vendor_id: str, title: str, severity: str, flags: list[str],
                status: str, confidence: Optional[float]) -> dict:
    base = settings.app_base_url.rstrip("/")
    return {
        "event": "security.suspicious_submission",
        "severity": severity,
        "submission_id": submission_id,
        "vendor_id": vendor_id,
        "title": clean_text(title, 120),
        "flags": sorted(flags),
        "status": status,
        "ai_confidence": confidence,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "url": f"{base}/admin" if base else None,
    }


def format_body(fmt: str, event: dict) -> dict:
    title = clean_text(event["title"])
    summary = f"VendorGuard security alert ({event['severity']})"
    lines = [
        f"Submission: {title} ({event['submission_id'][:8]})",
        f"Signals: {', '.join(event['flags']) or 'none'}",
        f"Current status: {event['status']}",
    ]
    if event.get("url"):
        lines.append(f"Review: {event['url']}")

    if fmt == "slack":
        text = f":rotating_light: *{summary}*\n" + "\n".join(_slack_escape(l) for l in lines)
        return {"text": text}
    if fmt == "teams":
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {"type": "TextBlock", "text": summary, "weight": "Bolder", "size": "Medium"},
                            *[{"type": "TextBlock", "text": l, "wrap": True} for l in lines],
                        ],
                    },
                }
            ],
        }
    return event  # generic: the structured event itself


def sign(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


# ───────── sending ─────────

def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise ValueError("invalid webhook URL")
    if settings.alert_allow_private:
        return
    if parsed.scheme != "https":
        raise ValueError("webhook must use https")
    for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("webhook resolves to a blocked address")


def _post(url: str, body: bytes, headers: dict[str, str]) -> None:
    validate_url(url)
    # No redirects: a redirect could bounce the request to an internal address.
    response = httpx.post(url, content=body, headers=headers, timeout=5.0, follow_redirects=False)
    response.raise_for_status()


def _deliver(event: dict) -> tuple[str, str]:
    """Returns (status, detail). Never raises, never includes the URL."""
    body_dict = format_body(settings.alert_format, event)
    body = json.dumps(body_dict, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json"}
    if settings.alert_webhook_secret:
        ts = str(int(time.time()))
        headers["X-VendorGuard-Timestamp"] = ts
        headers["X-VendorGuard-Signature"] = sign(settings.alert_webhook_secret, ts, body)

    detail = ""
    for attempt in range(2):
        try:
            _post(settings.alert_webhook_url, body, headers)
            return "sent", ""
        except httpx.HTTPStatusError as exc:
            detail = f"HTTP {exc.response.status_code}"
        except Exception as exc:  # exception text can contain the secret URL, so keep only the class name
            detail = type(exc).__name__
        if attempt == 0:
            time.sleep(1)
    log.warning("security alert delivery failed: %s", detail)
    return "failed", detail


def maybe_alert(db: Session, sub: Submission, flags: list[str]) -> Optional[str]:
    """Called after a submission is decided. Returns the alert status, or None if no alert applies."""
    if not settings.alert_webhook_url:
        return None
    severity = severity_for(flags)
    if severity is None:
        return None

    since = utcnow() - timedelta(hours=1)
    recent = db.scalar(
        select(func.count()).select_from(AlertLog).where(
            AlertLog.vendor_id == sub.vendor_id, AlertLog.status == "sent", AlertLog.created_at >= since
        )
    ) or 0
    if recent >= settings.alert_max_per_vendor_hour:
        status, detail = "suppressed", "per-vendor hourly cap reached"
    else:
        event = build_event(sub.id, sub.vendor_id, sub.title, severity, flags, sub.status, sub.ai_confidence)
        status, detail = _deliver(event)

    db.add(AlertLog(submission_id=sub.id, vendor_id=sub.vendor_id, severity=severity, status=status, detail=detail))
    db.commit()
    return status


def send_test_alert(admin_email: str) -> None:
    """Used by the admin 'Send test alert' button. Raises HTTPException with a safe message."""
    if not settings.alert_webhook_url:
        raise HTTPException(status_code=409, detail="Alerts are not configured on this server")
    event = build_event("00000000-test", "test", f"Test alert from {admin_email}", "test", ["test_alert"], "n/a", None)
    status, detail = _deliver(event)
    if status != "sent":
        raise HTTPException(status_code=502, detail=f"The webhook rejected the test message ({detail})")
