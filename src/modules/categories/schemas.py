from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    parent_id: Optional[UUID] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class CategoryResponse(CategoryBase):
    id: UUID
    level: int
    path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def parent_id(self) -> Optional[UUID]:
        if self.level == 0:
            return None
        parts = self.path.split('.')
        if len(parts) > 1:
            try:
                return UUID(parts[-2])
            except ValueError:
                return None
        return None

    model_config = ConfigDict(from_attributes=True)

class CategoryWithChildrenResponse(CategoryResponse):
    children: List[CategoryResponse]

class CategoryTreeResponse(BaseModel):
    id: UUID
    name: str
    children: List["CategoryTreeResponse"]

    model_config = ConfigDict(from_attributes=True)

