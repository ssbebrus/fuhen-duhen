from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import ProductStatus
from src.modules.common.schemas import Image, PaginatedResponse
from src.modules.skus.schemas import SKUResponse

class CategoryRef(BaseModel):
    id: UUID
    name: str
    level: int
    path: str

    model_config = ConfigDict(from_attributes=True)

class CharacteristicValue(BaseModel):
    name: str
    value: str

class ProductBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    category_id: UUID
    images: List[Image] = Field(..., min_length=1)
    characteristics: List[CharacteristicValue] = []

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1, max_length=5000)
    category_id: Optional[UUID] = None
    images: Optional[List[Image]] = None
    characteristics: Optional[List[CharacteristicValue]] = None

class ProductResponse(ProductBase):
    id: UUID
    status: ProductStatus
    seller_id: UUID
    deleted: bool
    blocked: bool
    created_at: datetime
    updated_at: datetime
    category: CategoryRef
    skus: List[SKUResponse] = []

    model_config = ConfigDict(from_attributes=True)

class PaginatedProductResponse(PaginatedResponse[ProductResponse]):
    pass
