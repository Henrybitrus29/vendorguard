"""Background processing: runs the compliance agent and records each pipeline stage as it finishes."""
import logging
from pathlib import Path

from fastapi import BackgroundTasks

from .agents.compliance_agent import agent_app
from .alerts import maybe_alert
from .config import get_settings
from .db import SessionLocal
from .models import AuditRun, Submission
from .ocr import extract_document

log = logging.getLogger(__name__)
settings = get_settings()

STAGE_BY_NODE = {"classify_document": "classified", "evaluate_compliance": "audited"}


def _alert_safely(db, sub: Submission) -> None:
    """Alerting is best-effort. It must never undo or break a finished decision."""
    try:
        maybe_alert(db, sub, sub.flags or [])
    except Exception:
        log.exception("alerting failed for submission %s", sub.id)
        db.rollback()


def process_submission(submission_id: str) -> None:
    db = SessionLocal()
    try:
        sub = db.get(Submission, submission_id)
        if sub is None:
            return
        try:
            extraction = extract_document(Path(sub.stored_path), sub.content_type)
            state: dict = {
                "submission_id": sub.id,
                "document_text": extraction.text,
                "extraction_method": extraction.method,
                "flags": [],
            }

            for step in agent_app.stream(state, stream_mode="updates"):
                for node, update in step.items():
                    state.update(update or {})
                    stage = STAGE_BY_NODE.get(node)
                    if stage:
                        sub.stage = stage
                        db.commit()

            meta = state.get("extracted_metadata") or {}
            sub.status = state["status"]
            sub.stage = "decided"
            sub.ai_decision = state["decision"]
            sub.ai_confidence = float(state.get("confidence_score", 0.0))
            sub.flags = state.get("flags", [])
            sub.checks = state.get("checks", {})
            sub.extracted_data = {
                **meta,
                "risk": state.get("risk_assessment") or {},
                "document_type": state.get("document_type"),
                "reasoning": state.get("reasoning", ""),
                "extraction": {"method": extraction.method, "ocr_pages": extraction.ocr_pages},
            }
            db.add(
                AuditRun(
                    submission_id=sub.id,
                    confidence_score=sub.ai_confidence,
                    reasoning_summary=state.get("reasoning", "")[:2000],
                )
            )
            db.commit()
            _alert_safely(db, sub)
        except Exception:
            # Fail closed: anything unexpected goes to a human, never to Approved.
            log.exception("processing failed for submission %s", submission_id)
            db.rollback()
            sub = db.get(Submission, submission_id)
            sub.status = "Human_Review"
            sub.stage = "decided"
            sub.ai_decision = "HUMAN_REVIEW"
            sub.ai_confidence = 0.0
            sub.flags = ["processing_error"]
            sub.extracted_data = {"reasoning": "Automated processing failed. A person needs to review this file."}
            db.commit()
    finally:
        db.close()


def dispatch(background: BackgroundTasks, submission_id: str) -> None:
    if settings.queue_mode == "rq":
        from redis import Redis
        from rq import Queue

        Queue("default", connection=Redis.from_url(settings.redis_url)).enqueue(
            process_submission, submission_id, job_timeout=300
        )
    else:
        background.add_task(process_submission, submission_id)
