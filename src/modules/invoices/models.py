import uuid
import enum
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from src.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.modules.auth.models import Seller, WarehouseOperator
    from src.modules.skus.models import SKU

class InvoiceStatus(str, enum.Enum):
    CREATED = "CREATED"
    PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED"
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"

class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.CREATED)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    accepted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_operators.id"), nullable=True)
    
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sellers.id"), index=True, nullable=False)

    seller: Mapped["Seller"] = relationship("Seller")
    operator: Mapped[Optional["WarehouseOperator"]] = relationship("WarehouseOperator")
    items: Mapped[list["InvoiceItem"]] = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, status={self.status})>"

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), index=True, nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), index=True, nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    sku: Mapped["SKU"] = relationship("SKU")

    def __repr__(self) -> str:
        return f"<InvoiceItem(id={self.id}, sku_id={self.sku_id}, quantity={self.quantity})>"
