from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import ProductStatus
from src.modules.common.schemas import ImageSchema

class ProductBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: ProductStatus = ProductStatus.ACTIVE
    images: List[ImageSchema] = []
    characteristics: List[dict] = []
    category_id: UUID

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProductStatus] = None
    images: Optional[List[ImageSchema]] = None
    characteristics: Optional[List[dict]] = None
    category_id: Optional[UUID] = None

class ProductResponse(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
