import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="vendor")  # vendor | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="Processing", index=True)
    stage: Mapped[str] = mapped_column(String(16), default="uploaded")  # last completed pipeline step
    original_filename: Mapped[str] = mapped_column(String(200), default="")
    stored_path: Mapped[str] = mapped_column(String(400), default="")
    content_type: Mapped[str] = mapped_column(String(64), default="text/plain")
    ai_decision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # APPROVED | HUMAN_REVIEW | REJECTED
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    checks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extracted_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    audit_runs: Mapped[list["AuditRun"]] = relationship(
        cascade="all, delete-orphan", order_by="AuditRun.executed_at.desc()"
    )
    overrides: Mapped[list["OverrideLog"]] = relationship(
        cascade="all, delete-orphan", order_by="OverrideLog.created_at.desc()"
    )
    alerts: Mapped[list["AlertLog"]] = relationship(
        cascade="all, delete-orphan", order_by="AlertLog.created_at.desc()"
    )


class AuditRun(Base):
    __tablename__ = "audit_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    confidence_score: Mapped[float] = mapped_column(Float)
    reasoning_summary: Mapped[str] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OverrideLog(Base):
    __tablename__ = "override_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    admin_email: Mapped[str] = mapped_column(String(255))
    previous_status: Mapped[str] = mapped_column(String(16))
    new_status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertLog(Base):
    """One row per security alert decision (sent, failed, or suppressed by the per-vendor throttle)."""

    __tablename__ = "alert_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), index=True)
    severity: Mapped[str] = mapped_column(String(16))  # high | medium | test
    status: Mapped[str] = mapped_column(String(16))  # sent | failed | suppressed
    detail: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
