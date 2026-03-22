import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID

from .models import Category
from .schemas import CategoryCreate, CategoryUpdate

class CategoryService:
    @staticmethod
    async def get_all(db: AsyncSession) -> List[Category]:
        """Получить список всех категорий"""
        result = await db.execute(select(Category).order_by(Category.level, Category.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, category_id: UUID) -> Optional[Category]:
        """Получить категорию по ID"""
        result = await db.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, category_in: CategoryCreate) -> Category:
        """Создать новую категорию с расчетом path и level"""
        new_id = uuid.uuid4()
        level = 0
        path = str(new_id)
        
        if category_in.parent_id:
            parent = await CategoryService.get_by_id(db, category_in.parent_id)
            if parent:
                level = parent.level + 1
                path = f"{parent.path}.{new_id}"
        
        # Удаляем parent_id из данных для модели, так как прямого поля parent_id в модели нет (используется path)
        data = category_in.model_dump(exclude={"parent_id"})
        new_category = Category(id=new_id, level=level, path=path, **data)
        
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        return new_category

    @staticmethod
    async def update(db: AsyncSession, category_id: UUID, category_in: CategoryUpdate) -> Optional[Category]:
        """Обновить категорию"""
        update_data = category_in.model_dump(exclude_unset=True)
        if not update_data:
            return await CategoryService.get_by_id(db, category_id)
            
        query = update(Category).where(Category.id == category_id).values(**update_data).returning(Category)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, category_id: UUID) -> bool:
        """Удалить категорию (физическое удаление, так как для категорий soft delete не подтвержден)"""
        category = await CategoryService.get_by_id(db, category_id)
        if not category:
            return False
        await db.delete(category)
        await db.commit()
        return True
