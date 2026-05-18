from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from src.modules.invoices.models import InvoiceStatus

class InvoiceItemCreate(BaseModel):
    sku_id: UUID
    quantity: int = Field(..., gt=0)

class InvoiceCreate(BaseModel):
    items: List[InvoiceItemCreate] = Field(..., min_length=1)

class InvoiceItemResponse(BaseModel):
    id: UUID
    sku_id: UUID
    quantity: int
    accepted_quantity: Optional[int]
    sku_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceResponse(BaseModel):
    id: UUID
    seller_id: UUID
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None
    accepted_by: Optional[UUID] = None
    items: List[InvoiceItemResponse]

    model_config = ConfigDict(from_attributes=True)

class InvoicePaginatedResponse(BaseModel):
    items: List[InvoiceResponse]
    total_count: int
    limit: int
    offset: int

class InvoiceAcceptItem(BaseModel):
    invoice_item_id: UUID
    accepted_quantity: int = Field(..., ge=0)

class InvoiceAcceptRequest(BaseModel):
    accepted_items: Optional[List[InvoiceAcceptItem]] = None
