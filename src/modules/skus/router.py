import httpx
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.db.database import get_db
from src.config import settings
from src.modules.products.models import ProductStatus
from .schemas import (
    SKUCreate, SKUUpdate, SKUResponse,
    SKUImageCreateRequest, SKUImageUpdateRequest, SKUImageResponse
)
from .service import SKUService
from .exceptions import (
    SkuNotFoundError, ProductNotFoundError, NotOwnerError, 
    SkuHardBlockedError, SkuHasReservesError, ImageNotFoundError
)
from src.modules.auth.dependencies import get_current_seller
from src.modules.auth.models import Seller
from src.modules.common.events import send_moderation_event

router = APIRouter(prefix="/skus", tags=["SKUs"])

@router.post("", response_model=SKUResponse, status_code=status.HTTP_201_CREATED, summary="Создать SKU")
async def create_sku(
    sku_in: SKUCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Создать новый SKU"""
    if sku_in.price <= 0:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "price must be a positive integer (kopecks)"})
    try:
        new_sku, status_changed, product = await SKUService.create(db, sku_in, seller.id)
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    except SkuHardBlockedError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot add SKU to hard-blocked product"})
    except NotOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        
    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id)
        
    return new_sku

@router.patch("/{sku_id}", response_model=SKUResponse, summary="Обновить SKU")
async def update_sku(
    sku_id: UUID, 
    sku_in: SKUUpdate, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Обновить SKU"""
    try:
        sku, status_changed = await SKUService.update(db, sku_id, sku_in, seller.id)
    except (SkuNotFoundError, ProductNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "SKU not found"})
    except NotOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
    except SkuHardBlockedError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        
    if status_changed:
        background_tasks.add_task(send_moderation_event, sku.product_id, seller.id, "EDITED")
        
    return sku

@router.post("/{sku_id}/images", response_model=SKUImageResponse, status_code=status.HTTP_201_CREATED, summary="Добавить изображение к SKU")
async def add_sku_image(
    sku_id: UUID,
    image_in: SKUImageCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Добавить изображение к SKU"""
    try:
        new_image, status_changed, product = await SKUService.add_image(db, sku_id, image_in, seller.id)
    except (SkuNotFoundError, ProductNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "SKU or Product not found"})
    except NotOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
    except SkuHardBlockedError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})

    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
    return new_image

@router.patch("/images/{image_id}", response_model=SKUImageResponse, summary="Обновить изображение SKU")
async def update_sku_image(
    image_id: UUID,
    image_in: SKUImageUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Обновить изображение SKU"""
    try:
        updated_image, status_changed, product = await SKUService.update_image(db, image_id, image_in, seller.id)
    except ImageNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    except NotOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
    except SkuHardBlockedError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})

    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
    return updated_image

@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить изображение SKU")
async def delete_sku_image(
    image_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Удалить изображение SKU"""
    try:
        status_changed, product = await SKUService.delete_image(db, image_id, seller.id)
    except ImageNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
    except ProductNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    except NotOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
    except SkuHardBlockedError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})

    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
    return None

@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить SKU")
async def delete_sku(
    sku_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Удалить SKU"""
    try:
        await SKUService.delete(db, sku_id, seller.id, background_tasks)
    except (SkuNotFoundError, ProductNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "SKU not found"})
    except NotOwnerError:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "SKU does not belong to the authenticated seller"})
    except SkuHardBlockedError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot delete SKU of hard-blocked product"})
    except SkuHasReservesError:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Cannot delete SKU with active reserves"})
    return None

@router.get("/{sku_id}", response_model=SKUResponse, summary="Получить SKU")
async def get_sku(
    sku_id: UUID,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Получить SKU (seller view)"""
    from sqlalchemy import select
    from src.modules.products.models import Product
    sku = await SKUService.get_by_id(db, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "SKU not found"})
        
    product = await db.scalar(select(Product).where(Product.id == sku.product_id))
    if not product or product.seller_id != seller.id:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "SKU does not belong to the authenticated seller"})
        
    return sku

