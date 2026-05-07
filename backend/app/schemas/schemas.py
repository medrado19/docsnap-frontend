import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserFindOrCreate(BaseModel):
    email: str
    business_name: str
    language: str = "en"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    business_name: str
    language: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    vendor: str
    date: str | None = None
    total_amount: float
    tax_amount: float = 0
    category: str | None = None
    status: str | None = "Unpaid"
    notes: str | None = None
    line_items: list[dict] = []


class InvoiceResponse(InvoiceCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncomeCreate(BaseModel):
    source: str
    amount: float
    date: str | None = None
    notes: str | None = None


class IncomeResponse(IncomeCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreate(BaseModel):
    user_id: uuid.UUID | None = None
    email: str
    message: str
    issue_type: str
