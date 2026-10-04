from datetime import datetime, timezone
from typing import Any, Optional

from .models import Submission


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def serialize_for_vendor(sub: Submission) -> dict[str, Any]:
    """Vendors only learn the outcome. Flags, checks and reasoning stay hidden so an attacker
    cannot use them as feedback to tune a prompt-injection payload."""
    return {
        "id": sub.id,
        "title": sub.title,
        "status": sub.status,
        "stage": sub.stage,
        "filename": sub.original_filename,
        "created_at": iso(sub.created_at),
    }


def serialize_for_admin(sub: Submission, with_overrides: bool = False) -> dict[str, Any]:
    data = {
        **serialize_for_vendor(sub),
        "vendor_id": sub.vendor_id,
        "content_type": sub.content_type,
        "file_url": f"/api/submissions/{sub.id}/file",
        "ai_decision": sub.ai_decision,
        "ai_confidence": sub.ai_confidence,
        "flags": sub.flags or [],
        "checks": sub.checks or {},
        "extracted_data": sub.extracted_data or {},
        "audit_history": [
            {
                "task_id": r.id,
                "confidence_score": r.confidence_score,
                "reasoning_summary": r.reasoning_summary,
                "executed_at": iso(r.executed_at),
            }
            for r in sub.audit_runs
        ],
    }
    if with_overrides:
        data["overrides"] = [
            {
                "id": o.id,
                "admin_email": o.admin_email,
                "previous_status": o.previous_status,
                "new_status": o.new_status,
                "reason": o.reason,
                "created_at": iso(o.created_at),
            }
            for o in sub.overrides
        ]
        data["alerts"] = [
            {"id": a.id, "severity": a.severity, "status": a.status, "created_at": iso(a.created_at)}
            for a in sub.alerts
        ]
    return data
