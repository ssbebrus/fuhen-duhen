from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.db.database import get_db
from .schemas import CategoryCreate, CategoryUpdate, CategoryResponse
from .service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("/", response_model=List[CategoryResponse], summary="Получить все категории")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Получить все категории"""
    return await CategoryService.get_all(db)

# @router.get("/{category_id}", response_model=CategoryResponse)
# async def get_category(category_id: UUID, db: AsyncSession = Depends(get_db)):
#     """Получить категорию по ID"""
#     category = await CategoryService.get_by_id(db, category_id)
#     if not category:
#         raise HTTPException(status_code=404, detail="Категория не найдена")
#     return category

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED, summary="Создать категорию")
async def create_category(category_in: CategoryCreate, db: AsyncSession = Depends(get_db)):
    """Создать новую категорию"""
    return await CategoryService.create(db, category_in)

@router.put("/{category_id}", response_model=CategoryResponse, summary="Изменить категорию")
async def update_category(category_id: UUID, category_in: CategoryUpdate, db: AsyncSession = Depends(get_db)):
    """Изменить категорию"""
    category = await CategoryService.update(db, category_id, category_in)
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return category

# @router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_category(category_id: UUID, db: AsyncSession = Depends(get_db)):
#     """Удалить категорию"""
#     success = await CategoryService.delete(db, category_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Категория не найдена")
#     return None
