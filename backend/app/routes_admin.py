import csv
import io

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .alerts import send_test_alert
from .config import get_settings
from .db import get_db
from .limits import limiter
from .models import OverrideLog, Submission, User
from .security import require_admin
from .serializers import iso

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
AI_TO_STATUS = {"APPROVED": "Approved", "HUMAN_REVIEW": "Human_Review", "REJECTED": "Rejected"}


@router.get("/metrics")
def metrics(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    subs = db.scalars(select(Submission)).all()
    done = [s for s in subs if s.status != "Processing"]

    by_status: dict[str, int] = {}
    for s in subs:
        by_status[s.status] = by_status.get(s.status, 0) + 1

    # "AI decided" means the AI approved or rejected without asking for help.
    ai_decided = [s for s in done if s.ai_decision in ("APPROVED", "REJECTED")]
    ai_agreed = [s for s in ai_decided if AI_TO_STATUS[s.ai_decision] == s.status]
    confidences = [s.ai_confidence for s in done if s.ai_confidence is not None]

    def pct(n: int, d: int) -> float | None:
        return round(100 * n / d, 1) if d else None

    return {
        "total": len(subs),
        "processing": by_status.get("Processing", 0),
        "pending_review": by_status.get("Human_Review", 0),
        "by_status": by_status,
        "auto_approved_pct": pct(sum(1 for s in done if s.ai_decision == "APPROVED"), len(done)),
        "automation_rate_pct": pct(len(ai_decided), len(done)),
        "security_flagged": sum(1 for s in done if s.flags),
        "avg_confidence_pct": round(100 * sum(confidences) / len(confidences), 1) if confidences else None,
        "ai_agreement_pct": pct(len(ai_agreed), len(ai_decided)),
        "overrides_total": db.scalar(select(func.count()).select_from(OverrideLog)) or 0,
        "alerts_configured": bool(settings.alert_webhook_url),
    }


@router.post("/alerts/test")
@limiter.limit("5/minute")
def test_alert(request: Request, admin: User = Depends(require_admin)):
    send_test_alert(admin.email)
    return {"ok": True}


def _csv_safe(value: object) -> str:
    """Stop spreadsheet formula injection: a cell starting with = + - @ would run as a formula in Excel."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/audit-log.csv")
def audit_log_csv(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(OverrideLog, Submission.title)
        .join(Submission, Submission.id == OverrideLog.submission_id)
        .order_by(OverrideLog.created_at.desc())
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp_utc", "submission_id", "submission_title", "admin", "previous_status", "new_status", "reason"])
    for log, title in rows:
        writer.writerow(
            [_csv_safe(v) for v in (iso(log.created_at), log.submission_id, title, log.admin_email,
                                    log.previous_status, log.new_status, log.reason)]
        )
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="override-audit-log.csv"'},
    )
