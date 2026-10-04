import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .limits import limiter
from .models import OverrideLog, Submission, User
from .samples import sample_text
from .security import current_user, require_admin
from .serializers import serialize_for_admin, serialize_for_vendor
from .tasks import dispatch

router = APIRouter(prefix="/submissions", tags=["submissions"])
settings = get_settings()
MAX_BYTES = settings.max_upload_mb * 1024 * 1024


CONTENT_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "txt": "text/plain"}


def sniff(data: bytes) -> str | None:
    """Decide the file type from its CONTENT, never from the filename or the client's header."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data and b"\x00" not in data[:4096]:
        try:
            data.decode("utf-8")
            return "txt"
        except UnicodeDecodeError:
            return None
    return None


def _owned_or_admin(db: Session, user: User, submission_id: str) -> Submission:
    sub = db.get(Submission, submission_id)
    # 404 (not 403) for other people's records, so IDs cannot be probed.
    if sub is None or (user.role != "admin" and sub.vendor_id != user.id):
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@router.post("", status_code=201)
@limiter.limit("20/hour")
def create_submission(
    request: Request,
    background: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.role != "vendor":
        raise HTTPException(status_code=403, detail="Only vendor accounts can upload documents")
    title = re.sub(r"\s+", " ", title).strip()
    if not 3 <= len(title) <= 120:
        raise HTTPException(status_code=422, detail="Title must be 3 to 120 characters")

    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB")
    kind = sniff(data)
    if kind is None:
        raise HTTPException(status_code=415, detail="Only PDF, PNG, JPEG and plain-text files are accepted")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / f"{uuid.uuid4().hex}.{kind}"  # random name; the user's filename never touches the disk
    stored.write_bytes(data)

    sub = Submission(
        vendor_id=user.id,
        title=title,
        original_filename=Path(file.filename or "upload").name[:200],
        stored_path=str(stored),
        content_type=CONTENT_TYPES[kind],
    )
    db.add(sub)
    db.commit()
    dispatch(background, sub.id)
    return serialize_for_vendor(sub)


@router.get("")
def list_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Submission).order_by(Submission.created_at.desc()).limit(200)
    if user.role != "admin":
        q = q.where(Submission.vendor_id == user.id)
    subs = db.scalars(q).all()
    if user.role == "admin":
        return [serialize_for_admin(s) for s in subs]
    return [serialize_for_vendor(s) for s in subs]


@router.get("/{submission_id}")
def get_submission(submission_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = _owned_or_admin(db, user, submission_id)
    if user.role == "admin":
        return serialize_for_admin(sub, with_overrides=True)
    return serialize_for_vendor(sub)


@router.get("/{submission_id}/file")
def get_file(submission_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = _owned_or_admin(db, user, submission_id)
    if not sub.stored_path:  # seeded demo rows have no file: generate the fake text instead
        d = sub.extracted_data or {}
        return PlainTextResponse(
            sample_text(d.get("vendor_name") or "Demo Vendor", d.get("tax_id_value") or "00-0000000"),
            headers={"X-Content-Type-Options": "nosniff"},
        )
    path = Path(sub.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File is no longer available")
    media = "text/plain; charset=utf-8" if sub.content_type == "text/plain" else sub.content_type
    return FileResponse(path, media_type=media, content_disposition_type="inline", filename=sub.original_filename)


class OverrideBody(BaseModel):
    new_status: Literal["Approved", "Human_Review", "Rejected"]
    reason: str = Field(min_length=10, max_length=500)


@router.patch("/{submission_id}/override")
def override(
    submission_id: str,
    body: OverrideBody,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.status == "Processing":
        raise HTTPException(status_code=409, detail="Wait until processing finishes")
    if sub.status == body.new_status:
        raise HTTPException(status_code=409, detail="The submission already has that status")
    db.add(
        OverrideLog(
            submission_id=sub.id,
            admin_email=admin.email,
            previous_status=sub.status,
            new_status=body.new_status,
            reason=body.reason.strip(),
        )
    )
    sub.status = body.new_status
    db.commit()
    db.refresh(sub)
    return serialize_for_admin(sub, with_overrides=True)
