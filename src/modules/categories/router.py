from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists
from typing import List, Optional
from uuid import UUID

from src.db.database import get_db
from src.modules.auth.dependencies import get_current_admin
from src.modules.products.models import Product
from .models import Category
from .schemas import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    CategoryWithChildrenResponse, CategoryTreeResponse
)
from .service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("", response_model=List[CategoryResponse], summary="Список категорий")
async def get_categories(
    parent_id: Optional[UUID] = None,
    only_root: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Список категорий (read-open)"""
    return await CategoryService.get_all(db, parent_id=parent_id, only_root=only_root)

@router.get("/tree", response_model=List[CategoryTreeResponse], summary="Полное дерево категорий")
async def get_categories_tree(db: AsyncSession = Depends(get_db)):
    """Полное дерево категорий (используется витриной)"""
    return await CategoryService.get_tree(db)

@router.get("/{category_id}", response_model=CategoryWithChildrenResponse, summary="Категория с прямыми подкатегориями")
async def get_category(category_id: UUID, db: AsyncSession = Depends(get_db)):
    """Категория с прямыми подкатегориями"""
    category_data = await CategoryService.get_by_id_with_children(db, category_id)
    if not category_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Category not found"}
        )
    return category_data

@router.get("/{category_id}/breadcrumbs", response_model=List[CategoryResponse], summary="Цепочка категорий от корня до текущей")
async def get_category_breadcrumbs(category_id: UUID, db: AsyncSession = Depends(get_db)):
    """Цепочка категорий от корня до текущей"""
    breadcrumbs = await CategoryService.get_breadcrumbs(db, category_id)
    if not breadcrumbs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Category not found"}
        )
    return breadcrumbs

@router.post("", response_model=CategoryWithChildrenResponse, status_code=status.HTTP_201_CREATED, summary="Создать категорию")
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(get_current_admin)
):
    """Создать категорию (только админ)"""
    new_cat = await CategoryService.create(db, category_in)
    return await CategoryService.get_by_id_with_children(db, new_cat.id)

@router.patch("/{category_id}", response_model=CategoryWithChildrenResponse, summary="Обновить категорию")
async def update_category(
    category_id: UUID,
    category_in: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(get_current_admin)
):
    """Обновить категорию (только админ)"""
    category = await CategoryService.update(db, category_id, category_in)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Category not found"}
        )
    return await CategoryService.get_by_id_with_children(db, category.id)

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить категорию")
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(get_current_admin)
):
    """Удалить категорию (только админ, если в ней нет товаров)"""
    category = await CategoryService.get_by_id(db, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Category not found"}
        )
        
    # Check if there are active subcategories
    subcat_exists = await db.scalar(
        select(exists().where(Category.path.like(f"{category.path}.%")))
    )
    if subcat_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": "Cannot delete category with subcategories"}
        )
        
    # Check if there are active (non-deleted) products in this category
    prod_exists = await db.scalar(
        select(exists().where(Product.category_id == category_id, Product.deleted == False))
    )
    if prod_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": "Cannot delete category with products"}
        )
        
    await db.delete(category)
    await db.commit()
    return None

