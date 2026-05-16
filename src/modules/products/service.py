from src.modules.products.models import ProductStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import uuid
from fastapi import HTTPException, status

from .models import Product
from .schemas import ProductCreate, ProductUpdate
from src.modules.categories.service import CategoryService

import re

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

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
            "total_count": total,
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
    async def create(db: AsyncSession, product_in: ProductCreate, seller_id: UUID) -> Product:
        """Создать новый продукт"""
        category = await CategoryService.get_by_id(db, product_in.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "Category not found"}
            )

        data = product_in.model_dump()
        if not data.get("slug"):
            data["slug"] = slugify(data["title"])
            
        if data.get("images"):
            for img in data["images"]:
                img["id"] = str(uuid.uuid4())
            data["images"] = sorted(data["images"], key=lambda x: x["ordering"])
            
        if data.get("characteristics"):
            for char in data["characteristics"]:
                char["id"] = str(uuid.uuid4())
            
        data["seller_id"] = seller_id
            
        new_product = Product(**data)
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product, attribute_names=["category", "skus"])
        return new_product

    @staticmethod
    async def update(db: AsyncSession, product_id: UUID, product_in: ProductUpdate, seller_id: UUID) -> tuple[Optional[Product], bool]:
        """Обновить продукт"""
        product = await ProductService.get_by_id(db, product_id)
        if not product:
            raise ValueError("Product not found")
            
        if product.seller_id != seller_id:
            raise ValueError("Product does not belong to the authenticated seller")
            
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ValueError("Cannot edit hard-blocked product")
            
        update_data = product_in.model_dump(exclude_unset=True)
            
        status_changed = False
        # If any field is updated, we might need to reset moderation status
        if update_data and product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            update_data["status"] = ProductStatus.ON_MODERATION
            status_changed = True
            
        if update_data:
            query = update(Product).where(Product.id == product_id).values(**update_data)
            await db.execute(query)
            await db.commit()
            
        return await ProductService.get_by_id(db, product_id), status_changed

    @staticmethod
    async def add_image(db: AsyncSession, product_id: UUID, image_in, seller_id: UUID) -> tuple[dict, bool, Product]:
        product = await ProductService.get_by_id(db, product_id)
        if not product:
            raise ValueError("Product not found")
        if product.seller_id != seller_id:
            raise ValueError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ValueError("Cannot edit hard-blocked product")
            
        new_image = image_in.model_dump()
        new_image["id"] = str(uuid.uuid4())
        
        images = list(product.images)
        images.append(new_image)
        images = sorted(images, key=lambda x: x["ordering"])
        
        update_data = {"images": images}
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            update_data["status"] = ProductStatus.ON_MODERATION
            status_changed = True
            
        await db.execute(update(Product).where(Product.id == product_id).values(**update_data))
        await db.commit()
        return new_image, status_changed, product

    @staticmethod
    async def update_image(db: AsyncSession, image_id: UUID, image_in, seller_id: UUID) -> tuple[dict, bool, Product]:
        query = select(Product).where(Product.images.contains([{"id": str(image_id)}]))
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            raise ValueError("Image not found")
        if product.seller_id != seller_id:
            raise ValueError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ValueError("Cannot edit hard-blocked product")
            
        images = list(product.images)
        image_to_update = next((img for img in images if img["id"] == str(image_id)), None)
        if not image_to_update:
            raise ValueError("Image not found in product")
            
        update_data = image_in.model_dump(exclude_unset=True)
        image_to_update.update(update_data)
        
        images = sorted(images, key=lambda x: x["ordering"])
        
        product_update_data = {"images": images}
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            product_update_data["status"] = ProductStatus.ON_MODERATION
            status_changed = True
            
        await db.execute(update(Product).where(Product.id == product.id).values(**product_update_data))
        await db.commit()
        return image_to_update, status_changed, product

    @staticmethod
    async def delete_image(db: AsyncSession, image_id: UUID, seller_id: UUID) -> tuple[bool, Product]:
        query = select(Product).where(Product.images.contains([{"id": str(image_id)}]))
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            raise ValueError("Image not found")
        if product.seller_id != seller_id:
            raise ValueError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ValueError("Cannot edit hard-blocked product")
            
        images = [img for img in product.images if img["id"] != str(image_id)]
        
        product_update_data = {"images": images}
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            product_update_data["status"] = ProductStatus.ON_MODERATION
            status_changed = True
            
        await db.execute(update(Product).where(Product.id == product.id).values(**product_update_data))
        await db.commit()
        return status_changed, product
