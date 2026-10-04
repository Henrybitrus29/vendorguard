"""Fake demo data for the portfolio site. Run:  python -m app.seed [--reset]

Creates a demo admin, a demo vendor and ~10 fabricated submissions. No real client data is used.
"""
import sys
from datetime import timedelta

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import AlertLog, AuditRun, OverrideLog, Submission, User, utcnow
from .security import hash_password

DEMO_ADMIN = ("admin@demo.vendorguard.dev", "DemoAdmin#2026")
DEMO_VENDOR = ("vendor@demo.vendorguard.dev", "DemoVendor#2026")

OK_CHECKS = {"tax_id_verified_in_text": True, "liability_or_sla_terms": True, "corporate_vendor": True, "model_assessment_passed": True}

# (title, vendor, tax id, status, ai_decision, confidence, flags, checks, reasoning, days_ago, override)
ROWS = [
    ("Acme Cloud MSA 2026", "Acme Cloud Ltd", "12-3456789", "Approved", "APPROVED", 0.96, [], OK_CHECKS,
     "Valid corporate vendor with a verifiable Tax ID, indemnity clause and 99.9% SLA.", 1, None),
    ("Northwind Logistics SOW", "Northwind Logistics LLC", "98-7654321", "Approved", "APPROVED", 0.93, [], OK_CHECKS,
     "Statement of work with clear liability terms and a verified registration number.", 1, None),
    ("Brightline Insurance Certificate", "Brightline Assurance Inc", "45-1122334", "Approved", "APPROVED", 0.95, [], OK_CHECKS,
     "Scanned insurance certificate read with OCR. Registered company, all required items present.", 2, None),
    ("Globex Data Processing Agreement", "Globex Corp", "77-5566778", "Human_Review", "HUMAN_REVIEW", 0.72, [],
     {**OK_CHECKS, "liability_or_sla_terms": False, "model_assessment_passed": False},
     "Tax ID verified but no explicit liability or SLA terms were found.", 2, None),
    ("Initech Services Contract", "Initech Services", "31-9988776", "Human_Review", "HUMAN_REVIEW", 0.5,
     ["injection_pattern:force_approval", "model_flagged_injection"], OK_CHECKS,
     "The text contains instructions aimed at an AI reviewer. Treated as suspicious and sent to a person.", 3, None),
    ("Umbrella Pharma Compliance Form", "Umbrella Pharma", "60-1239874", "Human_Review", "HUMAN_REVIEW", 0.5,
     ["tax_id_not_found_in_text"], {**OK_CHECKS, "tax_id_verified_in_text": False},
     "The reported Tax ID does not appear anywhere in the document, so it could not be verified.", 3, None),
    ("Stark Hardware Invoice", "Stark Hardware Co", "22-3344556", "Rejected", "APPROVED", 0.88, [], OK_CHECKS,
     "Looked compliant to the AI.", 4,
     ("Approved", "Rejected", "Vendor appears on our internal supplier blocklist; AI had no way to know this.")),
    ("Wayne Security SLA", "Wayne Security Group", "18-4455667", "Approved", "HUMAN_REVIEW", 0.64, [],
     {**OK_CHECKS, "model_assessment_passed": False},
     "Confidence below the approval threshold; routed to a person.", 4,
     ("Human_Review", "Approved", "Checked the registration number with the state registry and it is valid.")),
    ("Quarterly Research Paper", "n/a", "", "Rejected", "REJECTED", 0.0, [], {},
     "Classified as ACADEMIC_PAPER. Only commercial vendor documents are eligible.", 5, None),
    ("Jane Doe Resume", "n/a", "", "Rejected", "REJECTED", 0.0, [], {},
     "Classified as PERSONAL_RESUME. Only commercial vendor documents are eligible.", 6, None),
]


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User.id).limit(1)):
            return
        admin = User(email=DEMO_ADMIN[0], password_hash=hash_password(DEMO_ADMIN[1]), role="admin")
        vendor = User(email=DEMO_VENDOR[0], password_hash=hash_password(DEMO_VENDOR[1]), role="vendor")
        db.add_all([admin, vendor])
        db.flush()

        now = utcnow()
        for title, vname, tax, status, ai, conf, flags, checks, why, days, override in ROWS:
            when = now - timedelta(days=days, hours=len(title) % 7)
            sub = Submission(
                vendor_id=vendor.id, title=title, status=status, stage="decided",
                original_filename=title.lower().replace(" ", "-") + ".pdf", stored_path="",
                content_type="application/pdf", ai_decision=ai, ai_confidence=conf,
                flags=flags, checks=checks, created_at=when,
                extracted_data={"vendor_name": vname, "tax_id_value": tax or None, "reasoning": why,
                                "document_type": "COMMERCIAL_VENDOR_DOC" if tax else "OTHER",
                                "extraction": {"method": "ocr", "ocr_pages": 2} if "Scanned" in why else {"method": "digital", "ocr_pages": 0}},
            )
            db.add(sub)
            db.flush()
            db.add(AuditRun(submission_id=sub.id, confidence_score=conf, reasoning_summary=why,
                            executed_at=when + timedelta(seconds=20)))
            for flag_name, severity in (("injection_pattern", "high"), ("tax_id_not_found_in_text", "medium")):
                if any(f.startswith(flag_name) for f in flags):
                    db.add(AlertLog(submission_id=sub.id, vendor_id=vendor.id, severity=severity, status="sent",
                                    created_at=when + timedelta(seconds=25)))
            if override:
                prev, new, reason = override
                db.add(OverrideLog(submission_id=sub.id, admin_email=admin.email, previous_status=prev,
                                   new_status=new, reason=reason, created_at=when + timedelta(hours=3)))
        db.commit()
        print("Seeded demo data.")
    finally:
        db.close()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_if_empty()
