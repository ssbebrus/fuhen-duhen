from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.db.database import get_db
from .schemas import ProductCreate, ProductUpdate, ProductResponse, PaginatedProductResponse
from .service import ProductService

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
async def create_product(product_in: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый товар"""
    return await ProductService.create(db, product_in)

@router.put("/{product_id}", response_model=ProductResponse, summary="Изменить товар")
async def update_product(product_id: UUID, product_in: ProductUpdate, db: AsyncSession = Depends(get_db)):
    """Изменить товар"""
    product = await ProductService.update(db, product_id, product_in)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product
