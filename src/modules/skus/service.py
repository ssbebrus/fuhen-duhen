from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
import uuid
from uuid import UUID
from fastapi import BackgroundTasks

from .models import SKU
from .schemas import SKUCreate, SKUUpdate
from src.modules.products.models import Product, ProductStatus
from src.modules.common.events import send_moderation_event, send_b2c_sku_out_of_stock_event
from .exceptions import (
    SkuNotFoundError, ProductNotFoundError, NotOwnerError, 
    SkuHardBlockedError, SkuHasReservesError, ImageNotFoundError
)

class SKUService:
    @staticmethod
    async def get_by_id(db: AsyncSession, sku_id: UUID) -> Optional[SKU]:
        """Получить SKU по ID"""
        result = await db.execute(select(SKU).where(SKU.id == sku_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, sku_in: SKUCreate, seller_id: UUID) -> tuple[SKU, bool, Optional[Product]]:
        """Создать новый SKU и обновить статус товара если нужно"""
        # Получаем товар
        product = await db.scalar(select(Product).where(Product.id == sku_in.product_id))
        if not product:
            raise ProductNotFoundError("Product not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SkuHardBlockedError("Product is hard-blocked")

        # Проверяем, является ли это первым SKU
        sku_count = await db.scalar(select(func.count(SKU.id)).where(SKU.product_id == sku_in.product_id))
        is_first_sku = (sku_count == 0)

        data = sku_in.model_dump()
        
        # Добавляем ID изображениям и характеристикам
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
            raise SkuNotFoundError("SKU not found")
            
        product = await db.scalar(select(Product).where(Product.id == sku.product_id))
        if not product:
            raise ProductNotFoundError("Product not found")
            
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
            
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SkuHardBlockedError("Cannot edit SKU of a hard-blocked product")
            
        update_data = sku_in.model_dump(exclude_unset=True)
        
        status_changed = False
        if update_data and product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            await db.execute(update(Product).where(Product.id == product.id).values(status=ProductStatus.ON_MODERATION))
            status_changed = True
            
        if update_data:
            query = update(SKU).where(SKU.id == sku_id).values(**update_data).returning(SKU)
            result = await db.execute(query)
            await db.commit()
            return result.scalar_one_or_none(), status_changed
            
        await db.commit()
        return sku, status_changed

    @staticmethod
    async def add_image(db: AsyncSession, sku_id: UUID, image_in, seller_id: UUID) -> tuple[dict, bool, Product]:
        sku = await SKUService.get_by_id(db, sku_id)
        if not sku:
            raise SkuNotFoundError("SKU not found")
        
        product = await db.scalar(select(Product).where(Product.id == sku.product_id))
        if not product:
            raise ProductNotFoundError("Product not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SkuHardBlockedError("Cannot edit SKU of a hard-blocked product")
            
        new_image = image_in.model_dump()
        new_image["id"] = str(uuid.uuid4())
        
        images = list(sku.images)
        images.append(new_image)
        images = sorted(images, key=lambda x: x["ordering"])
        
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            await db.execute(update(Product).where(Product.id == product.id).values(status=ProductStatus.ON_MODERATION))
            status_changed = True
            
        await db.execute(update(SKU).where(SKU.id == sku_id).values(images=images))
        await db.commit()
        return new_image, status_changed, product

    @staticmethod
    async def update_image(db: AsyncSession, image_id: UUID, image_in, seller_id: UUID) -> tuple[dict, bool, Product]:
        query = select(SKU).where(SKU.images.contains([{"id": str(image_id)}]))
        result = await db.execute(query)
        sku = result.scalar_one_or_none()
        
        if not sku:
            raise ImageNotFoundError("Image not found")
            
        product = await db.scalar(select(Product).where(Product.id == sku.product_id))
        if not product:
            raise ProductNotFoundError("Product not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SkuHardBlockedError("Cannot edit SKU of a hard-blocked product")
            
        images = list(sku.images)
        image_to_update = next((img for img in images if img["id"] == str(image_id)), None)
        if not image_to_update:
            raise ValueError("Image not found in SKU")
            
        update_data = image_in.model_dump(exclude_unset=True)
        image_to_update.update(update_data)
        
        images = sorted(images, key=lambda x: x["ordering"])
        
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            await db.execute(update(Product).where(Product.id == product.id).values(status=ProductStatus.ON_MODERATION))
            status_changed = True
            
        await db.execute(update(SKU).where(SKU.id == sku.id).values(images=images))
        await db.commit()
        return image_to_update, status_changed, product

    @staticmethod
    async def delete_image(db: AsyncSession, image_id: UUID, seller_id: UUID) -> tuple[bool, Product]:
        query = select(SKU).where(SKU.images.contains([{"id": str(image_id)}]))
        result = await db.execute(query)
        sku = result.scalar_one_or_none()
        
        if not sku:
            raise ImageNotFoundError("Image not found")
            
        product = await db.scalar(select(Product).where(Product.id == sku.product_id))
        if not product:
            raise ProductNotFoundError("Product not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SkuHardBlockedError("Cannot edit SKU of a hard-blocked product")
            
        images = [img for img in sku.images if img["id"] != str(image_id)]
        
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            await db.execute(update(Product).where(Product.id == product.id).values(status=ProductStatus.ON_MODERATION))
            status_changed = True
            
        await db.execute(update(SKU).where(SKU.id == sku.id).values(images=images))
        await db.commit()
        return status_changed, product

    @staticmethod
    async def get_public_sku_by_id(db: AsyncSession, sku_id: UUID) -> Optional[SKU]:
        """Получить SKU для витрины B2C (только если товар MODERATED, не удален, и active_quantity > 0)"""
        query = (
            select(SKU)
            .join(Product, SKU.product_id == Product.id)
            .where(
                SKU.id == sku_id,
                Product.status == ProductStatus.MODERATED,
                Product.deleted == False,
                SKU.active_quantity > 0
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, sku_id: UUID, seller_id: UUID, background_tasks: BackgroundTasks) -> None:
        """Удалить SKU"""
        result = await db.execute(
            select(SKU)
            .where(SKU.id == sku_id)
            .options(selectinload(SKU.product))
            .with_for_update()
        )
        sku = result.scalar_one_or_none()
        
        if not sku:
            raise SkuNotFoundError("SKU not found")
            
        product = sku.product
        if not product:
            raise ProductNotFoundError("Product not found")
            
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
            
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SkuHardBlockedError("Cannot delete SKU of hard-blocked product")
            
        if sku.reserved_quantity > 0:
            raise SkuHasReservesError("Cannot delete SKU with active reserves")
            
        sku_active_quantity = sku.active_quantity
        
        # Count remaining SKUs for the product
        remaining_skus_count = await db.scalar(
            select(func.count(SKU.id))
            .where(SKU.product_id == product.id)
            .where(SKU.id != sku.id)
        )
        has_no_skus_left = (remaining_skus_count == 0)
        
        # Physical deletion of SKU
        await db.delete(sku)
        
        # Side-effects
        if has_no_skus_left:
            if product.status == ProductStatus.ON_MODERATION:
                product.status = ProductStatus.CREATED
                background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "DELETED")
                
        if sku_active_quantity > 0 and product.status == ProductStatus.MODERATED:
            background_tasks.add_task(send_b2c_sku_out_of_stock_event, product.id, sku.id)
            
        await db.commit()
