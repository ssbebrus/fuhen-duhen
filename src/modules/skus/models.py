import uuid
import enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.products.models import Product

class SKU(Base, TimestampMixin):
    __tablename__ = "skus"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    price: Mapped[int] = mapped_column(Integer)
    cost_price: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    discount: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    active_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    article: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    images: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # Список {"url": "...", "ordering": 0}
    characteristics: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # Список {"name": "...", "value": "..."}
    
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))

    product: Mapped["Product"] = relationship("Product", back_populates="skus")

    def __repr__(self) -> str:
        return f"<SKU(id={self.id}, name={self.name}, price={self.price})>"
