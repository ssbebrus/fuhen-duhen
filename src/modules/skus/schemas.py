from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from src.modules.common.schemas import Image

class SKUBase(BaseModel):
    name: str
    price: int
    active_quantity: int = 0
    images: List[Image] = []
    characteristics: List[dict] = []
    product_id: UUID

class SKUCreate(SKUBase):
    pass

class SKUUpdate(BaseModel):
    name: str
    price: int
    active_quantity: int
    images: List[Image] = []
    characteristics: List[dict] = []
    product_id: UUID

class SKUResponse(SKUBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
