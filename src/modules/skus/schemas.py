from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import SKUStatus
from src.modules.common.schemas import ImageSchema

class SKUBase(BaseModel):
    name: str
    price: int
    active_quantity: int = 0
    status: SKUStatus = SKUStatus.ACTIVE
    images: List[ImageSchema] = []
    characteristics: List[dict] = []
    product_id: UUID

class SKUCreate(SKUBase):
    pass

class SKUUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    active_quantity: Optional[int] = None
    status: Optional[SKUStatus] = None
    images: Optional[List[ImageSchema]] = None
    characteristics: Optional[List[dict]] = None
    product_id: Optional[UUID] = None

class SKUResponse(SKUBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
