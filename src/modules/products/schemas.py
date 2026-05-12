from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import ProductStatus
from src.modules.common.schemas import PaginatedResponse
from src.modules.skus.schemas import SKUShortResponse

class CategoryRef(BaseModel):
    id: UUID
    name: str
    level: int
    path: str

    model_config = ConfigDict(from_attributes=True)

class ProductCharacteristicBase(BaseModel):
    name: str = Field(..., title="Name")
    value: str = Field(..., title="Value")

class ProductCharacteristicCreate(ProductCharacteristicBase):
    pass

class ProductCharacteristicResponse(ProductCharacteristicBase):
    id: UUID = Field(..., title="Id")

    model_config = ConfigDict(from_attributes=True)

class ProductImageCreate(BaseModel):
    url: str = Field(..., title="Url")
    ordering: int = Field(default=0, title="Ordering")

class ProductImageCreateRequest(ProductImageCreate):
    pass

class ProductImageUpdateRequest(BaseModel):
    url: Optional[str] = Field(None, title="Url")
    ordering: Optional[int] = Field(None, title="Ordering")

class ProductImageResponse(ProductImageCreate):
    id: UUID = Field(..., title="Id")

    model_config = ConfigDict(from_attributes=True)

class ProductBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, title="Title")
    description: str = Field(..., min_length=1, max_length=5000, title="Description")
    category_id: UUID = Field(..., title="Category Id")
    images: List[ProductImageCreate] = Field(..., min_length=1, title="Images")
    characteristics: List[ProductCharacteristicCreate] = Field(default=[], title="Characteristics")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, title="Title")
    description: Optional[str] = Field(None, title="Description")
    category_id: Optional[UUID] = Field(None, title="Category Id")
    status: Optional[ProductStatus] = Field(None, title="Status")

class ProductResponse(BaseModel):
    id: UUID = Field(..., title="Id")
    seller_id: UUID = Field(..., title="Seller Id")
    title: str = Field(..., title="Title")
    description: str = Field(..., title="Description")
    status: ProductStatus
    deleted: bool = Field(..., title="Deleted")
    blocked: bool = Field(..., title="Blocked")
    images: List[ProductImageResponse] = Field(..., title="Images")
    characteristics: List[ProductCharacteristicResponse] = Field(..., title="Characteristics")
    skus: List[SKUShortResponse] = Field(..., title="Skus")
    category: CategoryRef = Field(..., title="Category")
    created_at: datetime = Field(..., title="Created At")
    updated_at: datetime = Field(..., title="Updated At")

    model_config = ConfigDict(from_attributes=True)

class PaginatedProductResponse(PaginatedResponse[ProductResponse]):
    pass
