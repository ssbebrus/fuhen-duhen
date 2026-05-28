from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from src.db.database import get_db
from src.modules.auth.dependencies import get_current_seller, get_current_operator
from src.modules.auth.models import Seller, WarehouseOperator
from .models import InvoiceStatus
from .schemas import InvoiceCreate, InvoiceResponse, InvoiceAcceptRequest, InvoicePaginatedResponse
from .service import InvoiceService
from .exceptions import (
    InvoiceItemMissingError,
    SkuNotFoundError,
    NotOwnerError,
    InvalidProductStatusError,
    InvalidQuantityError,
    InvoiceNotFoundError,
    InvoiceAlreadyProcessedError,
    InvoiceItemNotFoundError
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])

@router.get("", response_model=InvoicePaginatedResponse, summary="Список накладных продавца")
async def list_invoices(
    limit: int = 20,
    offset: int = 0,
    status: Optional[InvoiceStatus] = None,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Получить список накладных текущего продавца"""
    return await InvoiceService.get_all(db, limit, offset, seller_id=seller.id, status_filter=status)

@router.get("/{invoice_id}", response_model=InvoiceResponse, summary="Получить накладную")
async def get_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Получить накладную (только если seller_id == JWT.sub)"""
    try:
        return await InvoiceService.get_by_id(db, invoice_id, seller.id)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)})
    except NotOwnerError as e:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": str(e)})

@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить накладную")
async def delete_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Удалить накладную (только в статусе CREATED)"""
    try:
        await InvoiceService.delete(db, invoice_id, seller.id)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)})
    except NotOwnerError as e:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": str(e)})
    except InvoiceAlreadyProcessedError as e:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": str(e)})

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Создать накладную (в статусе CREATED)")
async def create_invoice(
    invoice_in: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Создать новую накладную"""
    try:
        return await InvoiceService.create(db, invoice_in, seller.id)
    except InvoiceItemMissingError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": str(e)})
    except SkuNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)})
    except NotOwnerError as e:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": str(e)})
    except InvalidProductStatusError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": str(e)})
    except InvalidQuantityError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": str(e)})

@router.post("/{invoice_id}/accept", response_model=InvoiceResponse, summary="Принять накладную")
async def accept_invoice(
    invoice_id: UUID,
    accept_in: Optional[InvoiceAcceptRequest] = None,
    db: AsyncSession = Depends(get_db),
    operator: WarehouseOperator = Depends(get_current_operator)
):
    """Принять накладную оператором (в тестовых целях вызываем через API)"""
    try:
        return await InvoiceService.accept(db, invoice_id, accept_in, operator_id=operator.id)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(e)})
    except InvoiceAlreadyProcessedError as e:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": str(e)})
    except InvoiceItemNotFoundError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": str(e)})
    except InvalidQuantityError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": str(e)})
