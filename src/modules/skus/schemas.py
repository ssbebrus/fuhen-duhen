from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class SKUCharacteristicBase(BaseModel):
    name: str
    value: str

class SKUCharacteristicCreate(SKUCharacteristicBase):
    pass

class SKUCharacteristicResponse(SKUCharacteristicBase):
    id: UUID

class SKUImageBase(BaseModel):
    url: str
    ordering: int = 0

class SKUImageCreate(SKUImageBase):
    pass

class SKUImageCreateRequest(SKUImageCreate):
    pass

class SKUImageUpdateRequest(BaseModel):
    url: Optional[str] = None
    ordering: Optional[int] = None

class SKUImageResponse(SKUImageBase):
    id: UUID

class SKUBase(BaseModel):
    product_id: UUID
    name: str
    price: int
    stock_quantity: int = 0
    article: Optional[str] = None

class SKUCreate(SKUBase):
    cost_price: int = Field(gt=0, description="Цена в копейках")
    discount: int = Field(default=0, ge=0, description="Скидка в копейках")
    images: List[SKUImageCreate] = []
    characteristics: List[SKUCharacteristicCreate] = []

class SKUUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    article: Optional[str] = None

class SKUResponse(SKUBase):
    id: UUID
    cost_price: int = 0
    discount: int = 0
    active_quantity: int = 0
    reserved_quantity: int = 0
    images: List[SKUImageResponse] = []
    characteristics: List[SKUCharacteristicResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SKUPublicResponse(BaseModel):
    id: UUID
    product_id: UUID
    name: str
    price: int
    discount: int = 0
    stock_quantity: int = 0
    active_quantity: int = 0
    article: Optional[str] = None
    images: List[SKUImageResponse] = []
    characteristics: List[SKUCharacteristicResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SKUShortResponse(BaseModel):
    id: UUID
    name: str
    price: int
    stock_quantity: int
    article: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
