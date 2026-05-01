import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    name: str
    email: str


class UserResponse(UserBase):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceCreate(BaseModel):
    user_id: uuid.UUID | None = None
    vendor: str
    amount: float
    due_date: str | None = None
    notes: str | None = None


class InvoiceResponse(InvoiceCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncomeCreate(BaseModel):
    user_id: uuid.UUID | None = None
    source: str
    amount: float
    received_date: str | None = None
    notes: str | None = None


class IncomeResponse(IncomeCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
