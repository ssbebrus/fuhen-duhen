from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.db.database import get_db
from .schemas import ProductCreate, ProductUpdate, ProductResponse, PaginatedProductResponse
from .service import ProductService
from src.modules.auth.dependencies import get_current_seller
from src.modules.auth.models import Seller
from src.modules.common.events import send_moderation_event

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/", response_model=PaginatedProductResponse, summary="Получить список всех товаров с пагинацией")
async def get_products(
    limit: int = 10, 
    offset: int = 0, 
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех товаров с пагинацией"""
    return await ProductService.get_all(db, limit=limit, offset=offset)

@router.get("/{product_id}", response_model=ProductResponse, summary="Получить товар по ID")
async def get_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    """Получить товар по ID"""
    product = await ProductService.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Создать товар")
async def create_product(
    product_in: ProductCreate, 
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Создать новый товар"""
    return await ProductService.create(db, product_in, seller_id=seller.id)

@router.put("/{product_id}", response_model=ProductResponse, summary="Изменить товар")
async def update_product(
    product_id: UUID, 
    product_in: ProductUpdate, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Изменить товар"""
    try:
        product, status_changed = await ProductService.update(db, product_id, product_in, seller.id)
    except ValueError as e:
        if str(e) == "Product not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        elif str(e) == "Product does not belong to the authenticated seller":
            raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        elif str(e) == "Cannot edit hard-blocked product":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        raise
        
    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
        
    return product
