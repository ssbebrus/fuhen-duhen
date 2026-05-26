import uuid
import enum
from typing import TYPE_CHECKING, Optional
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
    blocking_reason_title: Mapped[str] = mapped_column(String(255), nullable=True)
    images: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # Список {"url": "...", "ordering": 0}
    characteristics: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # Список {"name": "...", "value": "..."}
    field_reports: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default='[]')  # Список {"field_name": "...", "sku_id": "...", "comment": "..."}
    
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"))
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sellers.id"), index=True, nullable=False)

    category: Mapped["Category"] = relationship("Category", back_populates="products")
    skus: Mapped[list["SKU"]] = relationship("SKU", back_populates="product")
    seller: Mapped["Seller"] = relationship("Seller")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title={self.title}, status={self.status})>"

    @property
    def blocked(self) -> bool:
        return self.status in (ProductStatus.BLOCKED, ProductStatus.HARD_BLOCKED)

    @property
    def skus_count(self) -> int:
        return len(self.skus) if "skus" in self.__dict__ else 0

    @property
    def total_active_quantity(self) -> int:
        if "skus" in self.__dict__:
            return sum(sku.active_quantity for sku in self.skus)
        return 0

    @property
    def min_price(self) -> Optional[int]:
        if "skus" in self.__dict__ and self.skus:
            return min(sku.price for sku in self.skus)
        return None

    @property
    def cover_image(self) -> Optional[str]:
        if self.images:
            sorted_imgs = sorted(self.images, key=lambda x: x.get("ordering", 0))
            if sorted_imgs:
                return sorted_imgs[0].get("url")
        return None


class ProcessedEvent(Base, TimestampMixin):
    __tablename__ = "processed_events"

    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

