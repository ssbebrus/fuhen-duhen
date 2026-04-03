from pydantic import BaseModel
from typing import TypeVar, Generic, List

T = TypeVar("T")

class Image(BaseModel):
    url: str
    ordering: int

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int
