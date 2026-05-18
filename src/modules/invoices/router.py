from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from src.db.database import get_db
from src.modules.auth.dependencies import get_current_seller, get_current_operator
from src.modules.auth.models import Seller, WarehouseOperator
from .schemas import InvoiceCreate, InvoiceResponse, InvoiceAcceptRequest
from .service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Создать накладную (в статусе CREATED)")
async def create_invoice(
    invoice_in: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Создать новую накладную"""
    return await InvoiceService.create(db, invoice_in, seller.id)

@router.post("/{invoice_id}/accept", response_model=InvoiceResponse, summary="Принять накладную")
async def accept_invoice(
    invoice_id: UUID,
    accept_in: Optional[InvoiceAcceptRequest] = None,
    db: AsyncSession = Depends(get_db),
    operator: WarehouseOperator = Depends(get_current_operator)
):
    """Принять накладную оператором (в тестовых целях вызываем через API)"""
    return await InvoiceService.accept(db, invoice_id, accept_in, operator_id=operator.id)
