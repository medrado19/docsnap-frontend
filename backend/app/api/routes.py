import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Income, Invoice, User
from app.schemas.schemas import IncomeCreate, IncomeResponse, InvoiceResponse, UserBase, UserResponse

router = APIRouter()
logger = logging.getLogger("revnio.upload")


def _to_number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_extracted_invoice(raw: dict):
    vendor = (raw.get("vendor") or raw.get("supplier") or raw.get("merchant") or raw.get("company") or "").strip()
    total = raw.get("total")
    if total is None:
        total = raw.get("amount")
    if total is None:
        total = raw.get("subtotal")
    tax = raw.get("tax")
    invoice_date = raw.get("invoiceDate") or raw.get("date")
    due_date = raw.get("dueDate")
    status = raw.get("status") or "draft"

    missing_total = total is None
    if missing_total:
        total_value = 0.0
        status = "needs_review"
    else:
        total_value = _to_number(total, 0.0)

    if not vendor:
        vendor = "Unknown vendor"

    parsed = {
        "vendor": vendor,
        "amount": total_value,
        "due_date": due_date or invoice_date,
        "notes": json.dumps({
            "invoice_date": invoice_date,
            "subtotal": raw.get("subtotal"),
            "tax": tax,
            "raw_status": raw.get("status"),
            "normalized_status": status,
            "raw": raw,
        }),
    }
    return parsed


def _fake_ai_extract(filename: str):
    # Placeholder extraction until external OCR/AI service is wired.
    return {"vendor": filename.rsplit(".", 1)[0].replace("_", " "), "status": "draft"}



@router.post("/users/lookup", response_model=UserResponse)
def lookup_or_create_user(payload: UserBase, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user:
        if payload.name and user.name != payload.name:
            user.name = payload.name
            db.commit()
            db.refresh(user)
        return user
    user = User(name=payload.name, email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/upload-invoice", response_model=InvoiceResponse)
async def upload_invoice_file(
    file: UploadFile = File(...),
    user_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    logger.info("Invoice upload received", extra={"filename": file.filename, "content_type": file.content_type, "size": len(content), "user_id": str(user_id) if user_id else None})

    ai_raw = _fake_ai_extract(file.filename or "invoice")
    logger.info("AI raw extraction response: %s", ai_raw)

    parsed = _normalize_extracted_invoice(ai_raw)
    parsed["user_id"] = user_id
    parsed["status"] = json.loads(parsed["notes"]).get("normalized_status", "draft")
    logger.info("Parsed invoice object: %s", parsed)

    invoice = Invoice(**parsed)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    logger.info("Database insert result: id=%s user_id=%s", invoice.id, invoice.user_id)
    return invoice

@router.get("/invoices", response_model=list[InvoiceResponse])
def get_invoices(user_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(Invoice)
    if user_id:
        query = query.filter(Invoice.user_id == user_id)
    return query.order_by(Invoice.created_at.desc()).all()


@router.delete("/invoice/{id}")
def delete_invoice(id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted", "id": id}


@router.post("/income", response_model=IncomeResponse)
def create_income(payload: IncomeCreate, db: Session = Depends(get_db)):
    income = Income(**payload.model_dump())
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


@router.get("/income", response_model=list[IncomeResponse])
def get_income(user_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(Income)
    if user_id:
        query = query.filter(Income.user_id == user_id)
    return query.order_by(Income.created_at.desc()).all()


@router.delete("/income/{id}")
def delete_income(id: uuid.UUID, db: Session = Depends(get_db)):
    income = db.query(Income).filter(Income.id == id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Income record not found")

    db.delete(income)
    db.commit()
    return {"message": "Income deleted", "id": id}
