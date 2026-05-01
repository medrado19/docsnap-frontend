import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Income, Invoice
from app.schemas.schemas import IncomeCreate, IncomeResponse, InvoiceCreate, InvoiceResponse

router = APIRouter()


@router.post("/upload-invoice", response_model=InvoiceResponse)
def upload_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    invoice = Invoice(**payload.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/invoices", response_model=list[InvoiceResponse])
def get_invoices(db: Session = Depends(get_db)):
    return db.query(Invoice).order_by(Invoice.created_at.desc()).all()


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
def get_income(db: Session = Depends(get_db)):
    return db.query(Income).order_by(Income.created_at.desc()).all()


@router.delete("/income/{id}")
def delete_income(id: uuid.UUID, db: Session = Depends(get_db)):
    income = db.query(Income).filter(Income.id == id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Income record not found")

    db.delete(income)
    db.commit()
    return {"message": "Income deleted", "id": id}
