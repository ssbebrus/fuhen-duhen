from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID

from .models import SKU, SKUStatus
from .schemas import SKUCreate, SKUUpdate

class SKUService:
    @staticmethod
    async def get_all(db: AsyncSession, include_deleted: bool = False) -> List[SKU]:
        """Получить список всех SKU"""
        query = select(SKU)
        if not include_deleted:
            query = query.where(SKU.status != SKUStatus.DELETED)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, sku_id: UUID) -> Optional[SKU]:
        """Получить SKU по ID"""
        result = await db.execute(select(SKU).where(SKU.id == sku_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, sku_in: SKUCreate) -> SKU:
        """Создать новый SKU"""
        new_sku = SKU(**sku_in.model_dump())
        db.add(new_sku)
        await db.commit()
        await db.refresh(new_sku)
        return new_sku

    @staticmethod
    async def update(db: AsyncSession, sku_id: UUID, sku_in: SKUUpdate) -> Optional[SKU]:
        """Обновить SKU"""
        update_data = sku_in.model_dump(exclude_unset=True)
        if not update_data:
            return await SKUService.get_by_id(db, sku_id)
            
        query = update(SKU).where(SKU.id == sku_id).values(**update_data).returning(SKU)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, sku_id: UUID) -> bool:
        """Мягкое удаление SKU (смена статуса)"""
        sku = await SKUService.get_by_id(db, sku_id)
        if not sku:
            return False
            
        sku.status = SKUStatus.DELETED
        await db.commit()
        return True
