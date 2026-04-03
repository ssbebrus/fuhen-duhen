from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.db.database import get_db
from .schemas import SKUCreate, SKUUpdate, SKUResponse
from .service import SKUService

router = APIRouter(prefix="/skus", tags=["SKU"])

# @router.get("/{sku_id}", response_model=SKUResponse)
# async def get_sku(sku_id: UUID, db: AsyncSession = Depends(get_db)):
#     """Получить SKU по ID"""
#     sku = await SKUService.get_by_id(db, sku_id)
#     if not sku:
#         raise HTTPException(status_code=404, detail="SKU не найден")
#     return sku

@router.post("/", response_model=SKUResponse, status_code=status.HTTP_201_CREATED, summary="Создать SKU")
async def create_sku(sku_in: SKUCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый SKU"""
    return await SKUService.create(db, sku_in)

@router.put("/{sku_id}", response_model=SKUResponse, summary="Изменить SKU")
async def update_sku(sku_id: UUID, sku_in: SKUUpdate, db: AsyncSession = Depends(get_db)):
    """Изменить SKU"""
    sku = await SKUService.update(db, sku_id, sku_in)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU не найден")
    return sku
