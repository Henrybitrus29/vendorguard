import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    UPLOAD_DIR=f"{_tmp}/uploads",
    QUEUE_MODE="inline",
    ENV="test",
    SECRET_KEY="test-secret-key-test-secret-key-1234",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import tasks  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.limits import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

limiter.enabled = False


class FakeAgent:
    """Stands in for the LangGraph agent so API tests need no LLM and no network."""

    def stream(self, state, stream_mode="updates"):
        yield {"classify_document": {"document_type": "COMMERCIAL_VENDOR_DOC"}}
        yield {"evaluate_compliance": {"confidence_score": 0.95}}
        yield {
            "finalize_decision": {
                "decision": "APPROVED",
                "status": "Approved",
                "compliance_passed": True,
                "confidence_score": 0.95,
                "reasoning": "All checks passed.",
                "flags": [],
                "checks": {"tax_id_verified_in_text": True},
            }
        }


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(tasks, "agent_app", FakeAgent())


def make_client() -> TestClient:
    return TestClient(app, headers={"X-Requested-With": "fetch"})


@pytest.fixture
def client():
    return make_client()


@pytest.fixture
def make_vendor():
    def _make(email: str) -> TestClient:
        c = make_client()
        r = c.post("/auth/register", json={"email": email, "password": "a-long-password-1"})
        assert r.status_code == 201, r.text
        return c

    return _make


@pytest.fixture
def admin_client():
    db = SessionLocal()
    db.add(User(email="boss@example.com", password_hash=hash_password("admin-password-1"), role="admin"))
    db.commit()
    db.close()
    c = make_client()
    assert c.post("/auth/login", json={"email": "boss@example.com", "password": "admin-password-1"}).status_code == 200
    return c
