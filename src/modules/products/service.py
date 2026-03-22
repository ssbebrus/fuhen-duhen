from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID

from .models import Product, ProductStatus
from .schemas import ProductCreate, ProductUpdate

class ProductService:
    @staticmethod
    async def get_all(db: AsyncSession, include_deleted: bool = False) -> List[Product]:
        """Получить список всех продуктов"""
        query = select(Product)
        if not include_deleted:
            query = query.where(Product.status != ProductStatus.DELETED)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, product_id: UUID) -> Optional[Product]:
        """Получить продукт по ID"""
        result = await db.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, product_in: ProductCreate) -> Product:
        """Создать новый продукт"""
        new_product = Product(**product_in.model_dump())
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)
        return new_product

    @staticmethod
    async def update(db: AsyncSession, product_id: UUID, product_in: ProductUpdate) -> Optional[Product]:
        """Обновить продукт"""
        update_data = product_in.model_dump(exclude_unset=True)
        if not update_data:
            return await ProductService.get_by_id(db, product_id)
            
        query = update(Product).where(Product.id == product_id).values(**update_data).returning(Product)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, product_id: UUID) -> bool:
        """Мягкое удаление продукта (смена статуса)"""
        product = await ProductService.get_by_id(db, product_id)
        if not product:
            return False
            
        product.status = ProductStatus.DELETED
        await db.commit()
        return True
