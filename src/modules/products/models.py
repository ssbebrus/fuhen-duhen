import uuid
import enum
from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.categories.models import Category
    from src.modules.skus.models import SKU

class ProductStatus(str, enum.Enum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    DELETED = "DELETED"

class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.CREATED)
    images: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # List of {"url": "...", "ordering": 0}
    characteristics: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # List of {"name": "...", "value": "..."}
    
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"))

    category: Mapped["Category"] = relationship("Category", back_populates="products")
    skus: Mapped[list["SKU"]] = relationship("SKU", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title={self.title}, status={self.status})>"
