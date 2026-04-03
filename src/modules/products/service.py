from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID

from .models import Product
from .schemas import ProductCreate, ProductUpdate

class ProductService:
    @staticmethod
    async def get_all(db: AsyncSession, limit: int = 10, offset: int = 0) -> dict:
        """Получить список всех продуктов с пагинацией"""
        # Считаем общее количество
        count_query = select(func.count()).select_from(Product)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Получаем данные с лимитом и оффсетом
        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.skus))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    @staticmethod
    async def get_by_id(db: AsyncSession, product_id: UUID) -> Optional[Product]:
        """Получить продукт по ID"""
        result = await db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.category), selectinload(Product.skus))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, product_in: ProductCreate) -> Product:
        """Создать новый продукт"""
        data = product_in.model_dump()
        if data.get("images"):
            data["images"] = sorted(data["images"], key=lambda x: x["ordering"])
            
        new_product = Product(**data)
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product, attribute_names=["category"])
        return new_product

    @staticmethod
    async def update(db: AsyncSession, product_id: UUID, product_in: ProductUpdate) -> Optional[Product]:
        """Обновить продукт"""
        update_data = product_in.model_dump(exclude_unset=True)
        if not update_data:
            return await ProductService.get_by_id(db, product_id)
            
        if "images" in update_data and update_data["images"]:
            update_data["images"] = sorted(update_data["images"], key=lambda x: x["ordering"])
            
        query = update(Product).where(Product.id == product_id).values(**update_data)
        await db.execute(query)
        await db.commit()
        return await ProductService.get_by_id(db, product_id)
