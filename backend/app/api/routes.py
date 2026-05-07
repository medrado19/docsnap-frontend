import json
import logging
import os
import uuid
from textwrap import dedent

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import BugReport, FeedbackReport, IncomeEntry, Invoice, User
from app.schemas.schemas import BugReportCreate, FeedbackCreate, IncomeCreate, IncomeResponse, InvoiceCreate, InvoiceResponse, UserFindOrCreate, UserResponse

router = APIRouter()
logger = logging.getLogger("revnio.upload")


def _to_number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fake_ai_extract(filename: str):
    return {"vendor": filename.rsplit(".", 1)[0].replace("_", " "), "status": "Unpaid", "line_items": []}


def _send_feedback_email(email: str, issue_type: str, message: str):
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("RESEND_FROM_EMAIL", "noreply@revnio.co")
    if not api_key:
        logger.warning("RESEND_API_KEY not configured; skipping email send")
        return
    payload = {
        "from": sender,
        "to": ["contact@revnio.co"],
        "subject": f"Revnio feedback: {issue_type}",
        "html": f"<p><strong>User email:</strong> {email}</p><p><strong>Issue type:</strong> {issue_type}</p><p><strong>Message:</strong><br>{message}</p>",
    }
    requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=10)


def _create_github_issue_if_enabled(report: BugReportCreate):
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")
    if not token or not repo:
        return None
    issue_payload = {
        "title": f"[Bug] {report.page}: {report.error_message[:80]}",
        "body": dedent(
            f"""
            Automated bug report from Revnio frontend.

            - Email: {report.email}
            - Workspace ID: {report.workspace_id or "N/A"}
            - Page: {report.page}
            - Error: {report.error_message}
            - Browser: {report.browser}
            - Timestamp: {report.timestamp}
            - Last action: {report.last_action or "N/A"}

            AI may suggest fixes, but implementation must be submitted as a PR with human review before merge.
            """
        ).strip(),
        "labels": ["bug", "needs-review", "ai-suggested-fix-allowed-no-automerge"],
    }
    response = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json=issue_payload,
        timeout=10,
    )
    if not response.ok:
        logger.warning("Failed to create GitHub issue for bug report", extra={"repo": repo, "status": response.status_code})
        return None
    return response.json().get("html_url")


def _send_bug_report_email(report: BugReportCreate, github_issue_url: str | None):
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("RESEND_FROM_EMAIL", "noreply@revnio.co")
    if not api_key:
        logger.warning("RESEND_API_KEY not configured; skipping bug report email send")
        return
    payload = {
        "from": sender,
        "to": ["contact@revnio.co"],
        "subject": f"Revnio bug report from {report.email}",
        "html": (
            f"<p><strong>Email:</strong> {report.email}</p>"
            f"<p><strong>Workspace ID:</strong> {report.workspace_id or 'N/A'}</p>"
            f"<p><strong>Page:</strong> {report.page}</p>"
            f"<p><strong>Error:</strong> {report.error_message}</p>"
            f"<p><strong>Browser:</strong> {report.browser}</p>"
            f"<p><strong>Timestamp:</strong> {report.timestamp}</p>"
            f"<p><strong>Last action:</strong> {report.last_action or 'N/A'}</p>"
            f"<p><strong>GitHub issue:</strong> {github_issue_url or 'Not created'}</p>"
            "<p><strong>Policy:</strong> AI fixes must be submitted through PR and human review. No auto-merge.</p>"
        ),
    }
    requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=10)


@router.post("/users/find-or-create", response_model=UserResponse)
def find_or_create_user(payload: UserFindOrCreate, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.business_name = payload.business_name or user.business_name
        user.language = payload.language or user.language
    else:
        user = User(email=email, business_name=payload.business_name, language=payload.language)
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}/invoices", response_model=list[InvoiceResponse])
def get_user_invoices(user_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(Invoice).filter(Invoice.user_id == user_id).order_by(Invoice.created_at.desc()).all()


@router.post("/users/{user_id}/invoices", response_model=InvoiceResponse)
def create_user_invoice(user_id: uuid.UUID, payload: InvoiceCreate, db: Session = Depends(get_db)):
    invoice = Invoice(user_id=user_id, **payload.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/users/{user_id}/invoices/{invoice_id}")
def delete_user_invoice(user_id: uuid.UUID, invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.user_id == user_id, Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted", "id": invoice_id}


@router.get("/users/{user_id}/income", response_model=list[IncomeResponse])
def get_user_income(user_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(IncomeEntry).filter(IncomeEntry.user_id == user_id).order_by(IncomeEntry.created_at.desc()).all()


@router.post("/users/{user_id}/income", response_model=IncomeResponse)
def create_user_income(user_id: uuid.UUID, payload: IncomeCreate, db: Session = Depends(get_db)):
    income = IncomeEntry(user_id=user_id, **payload.model_dump())
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


@router.delete("/users/{user_id}/income/{income_id}")
def delete_user_income(user_id: uuid.UUID, income_id: uuid.UUID, db: Session = Depends(get_db)):
    income = db.query(IncomeEntry).filter(IncomeEntry.user_id == user_id, IncomeEntry.id == income_id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Income record not found")
    db.delete(income)
    db.commit()
    return {"message": "Income deleted", "id": income_id}


@router.post("/feedback")
def save_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    report = FeedbackReport(**payload.model_dump())
    db.add(report)
    db.commit()
    _send_feedback_email(payload.email, payload.issue_type, payload.message)
    return {"message": "Feedback saved"}


@router.post("/bug-report")
def save_bug_report(payload: BugReportCreate, db: Session = Depends(get_db)):
    github_issue_url = _create_github_issue_if_enabled(payload)
    report = BugReport(**payload.model_dump(), github_issue_url=github_issue_url, requires_pr_review=True)
    db.add(report)
    db.commit()
    _send_bug_report_email(payload, github_issue_url)
    return {
        "message": "Bug report saved",
        "github_issue_url": github_issue_url,
        "policy": "AI fixes must be pull requests and require human review before merge.",
    }


@router.post("/upload-invoice", response_model=InvoiceResponse)
async def upload_invoice_file(file: UploadFile = File(...), user_id: uuid.UUID = Form(...), db: Session = Depends(get_db)):
    content = await file.read()
    logger.info("Invoice upload received", extra={"filename": file.filename, "size": len(content), "user_id": str(user_id)})
    ai_raw = _fake_ai_extract(file.filename or "invoice")
    payload = InvoiceCreate(vendor=ai_raw.get("vendor", "Unknown vendor"), date=None, total_amount=0, tax_amount=0, category="Other", status=ai_raw.get("status", "Unpaid"), notes=json.dumps({"raw": ai_raw}), line_items=ai_raw.get("line_items") or [])
    invoice = Invoice(user_id=user_id, **payload.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
