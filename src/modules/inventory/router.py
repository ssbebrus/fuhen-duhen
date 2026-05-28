from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_db
from src.modules.products.router import verify_service_key
from .schemas import ReserveRequest, ReserveResponse, InventoryOrderRequest, InventoryOrderResponse
from .service import InventoryService
from .exceptions import NotEnoughReservedQuantityError

router = APIRouter(prefix="/inventory", tags=["Inventory"])

@router.post(
    "/reserve", 
    response_model=ReserveResponse, 
    status_code=status.HTTP_200_OK, 
    summary="Резервирование остатков SKU"
)
async def reserve_inventory(
    request: ReserveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """
    Резервирование SKU под заказ. Использует транзакцию с SELECT FOR UPDATE
    для предотвращения double-sell и deadlocks.
    """
    return await InventoryService.reserve(db, request, background_tasks)

@router.post(
    "/unreserve", 
    response_model=InventoryOrderResponse, 
    status_code=status.HTTP_200_OK, 
    summary="Снятие резервов SKU"
)
async def unreserve_inventory(
    request: InventoryOrderRequest,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """
    Снятие резерва при отмене заказа. Идемпотентно по order_id.
    """
    try:
        return await InventoryService.unreserve(db, request)
    except NotEnoughReservedQuantityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": "Not enough reserved quantity to unreserve"}
        )

@router.post(
    "/fulfill", 
    response_model=InventoryOrderResponse, 
    status_code=status.HTTP_200_OK, 
    summary="Списание резервов SKU"
)
async def fulfill_inventory(
    request: InventoryOrderRequest,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """
    Списание резерва при доставке заказа. Идемпотентно по order_id.
    """
    try:
        return await InventoryService.fulfill(db, request)
    except NotEnoughReservedQuantityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": "Not enough reserved or physical quantity to fulfill"}
        )
