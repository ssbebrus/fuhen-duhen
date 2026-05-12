from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class SKUBase(BaseModel):
    product_id: UUID
    name: str
    price: int
    stock_quantity: int = 0
    article: Optional[str] = None

class SKUCreate(SKUBase):
    pass

class SKUUpdate(BaseModel):
    name: str
    price: int
    stock_quantity: int
    article: Optional[str] = None

class SKUShortResponse(BaseModel):
    id: UUID
    name: str
    price: int
    stock_quantity: int
    article: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SKUResponse(SKUBase):
    id: UUID
    images: List[dict] = []  # To be refined if needed
    characteristics: List[dict] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
