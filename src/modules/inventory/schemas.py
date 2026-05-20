from pydantic import BaseModel, ConfigDict, Field
from typing import List
from uuid import UUID
from datetime import datetime

class InventoryItem(BaseModel):
    sku_id: UUID
    quantity: int = Field(..., gt=0, description="Количество товара (должно быть > 0)")

class ReserveRequest(BaseModel):
    idempotency_key: UUID
    order_id: UUID
    items: List[InventoryItem] = Field(..., min_length=1)

class ReservedItemInfo(BaseModel):
    sku_id: UUID
    reserved_quantity: int
    remaining_stock: int

class ReserveResponse(BaseModel):
    order_id: UUID
    status: str = "RESERVED"
    reserved_at: datetime
    
    # Поля совместимости с каноном B2C
    reserved: bool = True
    items: List[ReservedItemInfo]

    model_config = ConfigDict(from_attributes=True)

class InventoryOrderRequest(BaseModel):
    order_id: UUID
    items: List[InventoryItem] = Field(..., min_length=1)

class InventoryOrderResponse(BaseModel):
    order_id: UUID
    status: str  # UNRESERVED или FULFILLED
    processed_at: datetime
    
    # Поля совместимости с каноном B2C
    ok: bool = True

    model_config = ConfigDict(from_attributes=True)
