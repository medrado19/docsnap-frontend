import json
import logging
import os
import uuid

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import FeedbackReport, IncomeEntry, Invoice, User
from app.schemas.schemas import FeedbackCreate, IncomeCreate, IncomeResponse, InvoiceCreate, InvoiceResponse, UserFindOrCreate, UserResponse

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
