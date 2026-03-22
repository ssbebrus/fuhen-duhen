from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.db.database import get_db
from .schemas import ProductCreate, ProductUpdate, ProductResponse
from .service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/", response_model=List[ProductResponse])
async def get_products(include_deleted: bool = False, db: AsyncSession = Depends(get_db)):
    """Получить все продукты"""
    return await ProductService.get_all(db, include_deleted=include_deleted)

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    """Получить продукт по ID"""
    product = await ProductService.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return product

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(product_in: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый продукт"""
    return await ProductService.create(db, product_in)

@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: UUID, product_in: ProductUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить продукт"""
    product = await ProductService.update(db, product_id, product_in)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    """Мягкое удаление продукта"""
    success = await ProductService.delete(db, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return None
