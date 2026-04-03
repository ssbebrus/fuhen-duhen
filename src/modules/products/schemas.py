from pydantic import BaseModel, ConfigDict
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

class ProductBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: ProductStatus = ProductStatus.CREATED
    images: List[Image] = []
    characteristics: List[dict] = []

class ProductCreate(ProductBase):
    category_id: UUID

class ProductUpdate(ProductCreate):
    pass

class ProductResponse(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    category: CategoryRef
    skus: List[SKUResponse]

    model_config = ConfigDict(from_attributes=True)

class PaginatedProductResponse(PaginatedResponse[ProductResponse]):
    pass
