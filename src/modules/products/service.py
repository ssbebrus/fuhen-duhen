from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from .models import Product
from .schemas import ProductCreate

class ProductService:
    @staticmethod
    async def get_all(db: AsyncSession) -> List[Product]:
        """Получить список всех продуктов"""
        result = await db.execute(select(Product))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, product_in: ProductCreate) -> Product:
        """Создать новый продукт"""
        new_product = Product(**product_in.model_dump())
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)
        return new_product
