from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from .models import ProductStatus
from src.modules.common.schemas import PaginatedResponse
from src.modules.skus.schemas import SKUResponse, SKUPublicResponse

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
    slug: Optional[str] = Field(None, title="Slug")
    images: List[ProductImageCreate] = Field(..., min_length=1, title="Images")
    characteristics: List[ProductCharacteristicCreate] = Field(default=[], title="Characteristics")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, title="Title")
    description: Optional[str] = Field(None, title="Description")
    category_id: Optional[UUID] = Field(None, title="Category Id")
    characteristics: Optional[List[ProductCharacteristicCreate]] = Field(None, title="Characteristics")

class FieldReport(BaseModel):
    field_name: str
    sku_id: Optional[UUID] = None
    comment: str

class BlockingReason(BaseModel):
    id: UUID
    title: str
    comment: str

class ProductResponse(BaseModel):
    id: UUID = Field(..., title="Id")
    seller_id: UUID = Field(..., title="Seller Id")
    category_id: UUID = Field(..., title="Category Id")
    title: str = Field(..., title="Title")
    slug: str = Field(..., title="Slug")
    description: str = Field(..., title="Description")
    status: ProductStatus
    deleted: bool = Field(..., title="Deleted")
    blocked: bool = Field(default=False, title="Blocked")
    blocking_reason: Optional[BlockingReason] = Field(None, title="Blocking Reason")
    field_reports: List[FieldReport] = Field(default=[], title="Field Reports")
    images: List[ProductImageResponse] = Field(..., title="Images")
    characteristics: List[ProductCharacteristicResponse] = Field(..., title="Characteristics")
    skus: List[SKUResponse] = Field(..., title="Skus")
    category: CategoryRef = Field(..., title="Category")
    created_at: datetime = Field(..., title="Created At")
    updated_at: datetime = Field(..., title="Updated At")

    model_config = ConfigDict(from_attributes=True)

class ProductPublicResponse(BaseModel):
    id: UUID = Field(..., title="Id")
    seller_id: UUID = Field(..., title="Seller Id")
    category_id: UUID = Field(..., title="Category Id")
    category: CategoryRef = Field(..., title="Category")
    title: str = Field(..., title="Title")
    slug: str = Field(..., title="Slug")
    description: str = Field(..., title="Description")
    status: ProductStatus
    images: List[ProductImageResponse] = Field(..., title="Images")
    characteristics: List[ProductCharacteristicResponse] = Field(..., title="Characteristics")
    skus: List[SKUPublicResponse] = Field(..., title="Skus")
    created_at: datetime = Field(..., title="Created At")
    updated_at: datetime = Field(..., title="Updated At")

    model_config = ConfigDict(from_attributes=True)

class ProductPublicShortResponse(BaseModel):
    id: UUID = Field(..., title="Id")
    title: str = Field(..., title="Title")
    slug: str = Field(..., title="Slug")
    status: ProductStatus
    category_id: UUID = Field(..., title="Category Id")
    min_price: int = Field(..., title="Minimum Price")
    cover_image: Optional[str] = Field(None, title="Cover Image")
    created_at: datetime = Field(..., title="Created At")

    model_config = ConfigDict(from_attributes=True)

class ProductPublicPaginatedResponse(BaseModel):
    items: List[ProductPublicShortResponse] = Field(..., title="Items")
    total_count: int = Field(..., title="Total Count")
    limit: int = Field(..., title="Limit")
    offset: int = Field(..., title="Offset")

    model_config = ConfigDict(from_attributes=True)

class PaginatedProductResponse(PaginatedResponse[ProductResponse]):
    pass

class ProductBatchRequest(BaseModel):
    product_ids: List[UUID]
