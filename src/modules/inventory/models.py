import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.db.base import Base, TimestampMixin

class ReserveOperation(Base, TimestampMixin):
    __tablename__ = "reserve_operations"

    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(50), default="RESERVED")  # RESERVED, UNRESERVED, FULFILLED
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
