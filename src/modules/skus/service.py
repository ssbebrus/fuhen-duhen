from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID

from .models import SKU
from .schemas import SKUCreate, SKUUpdate

class SKUService:
    @staticmethod
    async def get_by_id(db: AsyncSession, sku_id: UUID) -> Optional[SKU]:
        """Получить SKU по ID"""
        result = await db.execute(select(SKU).where(SKU.id == sku_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, sku_in: SKUCreate) -> SKU:
        """Создать новый SKU"""
        data = sku_in.model_dump()
        if data.get("images"):
            data["images"] = sorted(data["images"], key=lambda x: x["ordering"])
            
        new_sku = SKU(**data)
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
            
        if "images" in update_data and update_data["images"]:
            update_data["images"] = sorted(update_data["images"], key=lambda x: x["ordering"])
            
        query = update(SKU).where(SKU.id == sku_id).values(**update_data).returning(SKU)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()
