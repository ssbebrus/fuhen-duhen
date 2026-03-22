from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    parent_id: Optional[UUID] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[int] = None

class CategoryResponse(CategoryBase):
    id: UUID
    level: int
    path: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
