from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
import uuid
from uuid import UUID

from .models import SKU
from .schemas import SKUCreate, SKUUpdate
from src.modules.products.models import Product, ProductStatus
from sqlalchemy import func

class SKUService:
    @staticmethod
    async def get_by_id(db: AsyncSession, sku_id: UUID) -> Optional[SKU]:
        """Получить SKU по ID"""
        result = await db.execute(select(SKU).where(SKU.id == sku_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, sku_in: SKUCreate) -> tuple[SKU, bool, Optional[Product]]:
        """Создать новый SKU и обновить статус товара если нужно"""
        # Fetch the product
        product = await db.scalar(select(Product).where(Product.id == sku_in.product_id))
        if not product:
            raise ValueError("Product not found")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ValueError("Product is hard-blocked")

        # Check if it's the first SKU
        sku_count = await db.scalar(select(func.count(SKU.id)).where(SKU.product_id == sku_in.product_id))
        is_first_sku = (sku_count == 0)

        data = sku_in.model_dump()
        
        # Add IDs to images and characteristics if they don't have them
        for img in data.get("images", []):
            if "id" not in img:
                img["id"] = str(uuid.uuid4())
        
        for char in data.get("characteristics", []):
            if "id" not in char:
                char["id"] = str(uuid.uuid4())
                
        new_sku = SKU(**data)
        db.add(new_sku)

        status_changed = False
        if is_first_sku and product.status == ProductStatus.CREATED:
            await db.execute(update(Product).where(Product.id == product.id).values(status=ProductStatus.ON_MODERATION))
            status_changed = True

        await db.commit()
        await db.refresh(new_sku)
        return new_sku, status_changed, product

    @staticmethod
    async def update(db: AsyncSession, sku_id: UUID, sku_in: SKUUpdate, seller_id: UUID) -> tuple[Optional[SKU], bool]:
        """Обновить SKU"""
        sku = await SKUService.get_by_id(db, sku_id)
        if not sku:
            raise ValueError("SKU not found")
            
        product = await db.scalar(select(Product).where(Product.id == sku.product_id))
        if not product:
            raise ValueError("Product not found")
            
        if product.seller_id != seller_id:
            raise ValueError("Product does not belong to the authenticated seller")
            
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ValueError("Cannot edit SKU of a hard-blocked product")
            
        update_data = sku_in.model_dump(exclude_unset=True)
        
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            await db.execute(update(Product).where(Product.id == product.id).values(status=ProductStatus.ON_MODERATION))
            status_changed = True
            
        if update_data:
            query = update(SKU).where(SKU.id == sku_id).values(**update_data).returning(SKU)
            result = await db.execute(query)
            await db.commit()
            return result.scalar_one_or_none(), status_changed
            
        await db.commit()
        return sku, status_changed
