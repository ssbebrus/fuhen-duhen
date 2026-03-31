import uuid
import enum
from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.products.models import Product

class SKUStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class SKU(Base, TimestampMixin):
    __tablename__ = "skus"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    price: Mapped[int] = mapped_column(Integer)
    active_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[SKUStatus] = mapped_column(Enum(SKUStatus), default=SKUStatus.ACTIVE)
    images: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # List of {"url": "...", "ordering": 0}
    characteristics: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # List of {"name": "...", "value": "..."}
    
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))

    product: Mapped["Product"] = relationship("Product", back_populates="skus")

    def __repr__(self) -> str:
        return f"<SKU(id={self.id}, name={self.name}, status={self.status})>"
