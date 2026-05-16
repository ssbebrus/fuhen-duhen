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
    from src.modules.auth.models import Seller

class ProductStatus(str, enum.Enum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"

class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.CREATED)
    deleted: Mapped[bool] = mapped_column(default=False, server_default="false")
    blocking_reason_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    moderator_comment: Mapped[str] = mapped_column(Text, nullable=True)
    images: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # Список {"url": "...", "ordering": 0}
    characteristics: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # Список {"name": "...", "value": "..."}
    
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"))
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sellers.id"), index=True, nullable=False)

    category: Mapped["Category"] = relationship("Category", back_populates="products")
    skus: Mapped[list["SKU"]] = relationship("SKU", back_populates="product")
    seller: Mapped["Seller"] = relationship("Seller")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title={self.title}, status={self.status})>"
