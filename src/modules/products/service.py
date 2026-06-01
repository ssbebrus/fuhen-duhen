from src.modules.products.models import ProductStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import uuid
from fastapi import HTTPException, status, BackgroundTasks

from .models import Product, ProcessedEvent
from .schemas import ProductCreate, ProductUpdate, ModerationEventRequest
from src.modules.categories.service import CategoryService
from .exceptions import (
    ProductNotFoundError,
    NotOwnerError,
    ProductHardBlockedError,
    ProductAlreadyDeletedError,
    ImageNotFoundError,
    InvalidUUIDError
)

import re

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

def safe_slugify(text: str) -> str:
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    text = text.lower()
    res = []
    for char in text:
        res.append(mapping.get(char, char))
    text = "".join(res)
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

class ProductService:
    @staticmethod
    async def get_all(
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0,
        seller_id: Optional[UUID] = None,
        include_deleted: bool = False,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> dict:
        """Получить список всех продуктов с пагинацией"""
        # Считаем общее количество
        count_query = select(func.count()).select_from(Product)
        
        conditions = []
        if seller_id:
            conditions.append(Product.seller_id == seller_id)
        if not include_deleted:
            conditions.append(Product.deleted == False)
        if status:
            conditions.append(Product.status == status)
        if search:
            conditions.append(Product.title.ilike(f"%{search}%"))
            
        if conditions:
            count_query = count_query.where(*conditions)
            
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Получаем данные с лимитом и оффсетом
        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.skus))
        )
        
        if conditions:
            query = query.where(*conditions)
            
        query = query.order_by(Product.created_at.desc())
        query = query.limit(limit).offset(offset)
            
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
            # US-B2B-01 ошибка исправлена
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
            raise ProductNotFoundError("Product not found")
            
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
            
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError("Cannot edit hard-blocked product")
            
        update_data = product_in.model_dump(exclude_unset=True)
            
        status_changed = False
        # Если поле товара было обновлено, устанавливаем статус ON_MODERATION
        if update_data and product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            update_data["status"] = ProductStatus.ON_MODERATION
            status_changed = True
            
        if update_data:
            query = update(Product).where(Product.id == product_id).values(**update_data)
            await db.execute(query)
            await db.commit()
            
        return await ProductService.get_by_id(db, product_id), status_changed

    @staticmethod
    async def delete(db: AsyncSession, product_id: UUID, seller_id: UUID) -> tuple[Product, list[str]]:
        """Мягкое удаление продукта"""
        product = await ProductService.get_by_id(db, product_id)
        if not product:
            raise ProductNotFoundError("Product not found")
            
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
            
        if product.deleted:
            raise ProductAlreadyDeletedError("Product already deleted")
            
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError("Cannot edit hard-blocked product")
            
        sku_ids = [str(sku.id) for sku in product.skus]
        
        query = update(Product).where(Product.id == product_id).values(deleted=True)
        await db.execute(query)
        await db.commit()
        await db.refresh(product)
        
        return product, sku_ids

    @staticmethod
    async def add_image(db: AsyncSession, product_id: UUID, image_in, seller_id: UUID) -> tuple[dict, bool, Product]:
        product = await ProductService.get_by_id(db, product_id)
        if not product:
            raise ProductNotFoundError("Product not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError("Cannot edit hard-blocked product")
            
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
            raise ImageNotFoundError("Image not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError("Cannot edit hard-blocked product")
            
        images = list(product.images)
        image_to_update = next((img for img in images if img["id"] == str(image_id)), None)
        if not image_to_update:
            raise ImageNotFoundError("Image not found in product")
            
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
            raise ImageNotFoundError("Image not found")
        if product.seller_id != seller_id:
            raise NotOwnerError("Product does not belong to the authenticated seller")
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError("Cannot edit hard-blocked product")
            
        images = [img for img in product.images if img["id"] != str(image_id)]
        
        product_update_data = {"images": images}
        status_changed = False
        if product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]:
            product_update_data["status"] = ProductStatus.ON_MODERATION
            status_changed = True
            
        await db.execute(update(Product).where(Product.id == product.id).values(**product_update_data))
        await db.commit()
        return status_changed, product

    @staticmethod
    def _matches_filters(product: Product, filters_dict: dict) -> bool:
        if not filters_dict:
            return True
            
        char_map = {}
        if product.characteristics:
            for char in product.characteristics:
                name = char.get("name")
                val = char.get("value")
                if name and val:
                    slug = safe_slugify(name)
                    if slug not in char_map:
                        char_map[slug] = set()
                    char_map[slug].add(val)
                    
        for slug, expected_val in filters_dict.items():
            if slug == "price":
                continue # ignore price filter here, usually price is min,max or similar
            if slug not in char_map:
                return False
            # Check if expected_val matches any value for this characteristic
            # B2C expects exact match for string filters e.g. filters[brand]=Apple
            if expected_val not in char_map[slug]:
                return False
        return True

    @staticmethod
    async def get_public_catalog(
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0,
        category_id: Optional[UUID] = None,
        search: Optional[str] = None,
        sort: Optional[str] = None,
        ids: Optional[str] = None,
        filters: Optional[dict] = None
    ) -> dict:
        """Получить список публичных продуктов для B2C с фильтрами видимости"""
        from src.modules.skus.models import SKU
        from sqlalchemy import exists, or_, select, func

        # Товар отображается в каталоге только если:
        # status = MODERATED, deleted = false, хотя бы один SKU имеет active_quantity > 0
        active_sku_exists = exists().where(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        )

        conditions = [
            Product.status == ProductStatus.MODERATED,
            Product.deleted == False,
            active_sku_exists
        ]

        if category_id:
            conditions.append(Product.category_id == category_id)

        if search:
            escaped_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(
                or_(
                    Product.title.ilike(f"%{escaped_search}%", escape="\\"),
                    Product.description.ilike(f"%{escaped_search}%", escape="\\")
                )
            )

        if ids:
            try:
                uuid_list = [UUID(id_str.strip()) for id_str in ids.split(",") if id_str.strip()]
                if uuid_list:
                    conditions.append(Product.id.in_(uuid_list))
            except ValueError:
                raise InvalidUUIDError("INVALID_UUID")

        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.skus))
            .where(*conditions)
        )

        if filters:
            result = await db.execute(query)
            all_products = result.scalars().all()
            
            filtered_products = []
            for p in all_products:
                if ProductService._matches_filters(p, filters):
                    filtered_products.append(p)
                    
            total = len(filtered_products)
            
            if sort == "price_asc":
                filtered_products.sort(key=lambda p: p.min_price or float('inf'))
            elif sort == "price_desc":
                filtered_products.sort(key=lambda p: p.min_price or 0, reverse=True)
            elif sort == "new":
                filtered_products.sort(key=lambda p: p.created_at, reverse=True)
            else:
                filtered_products.sort(key=lambda p: p.created_at, reverse=True)
                
            products = filtered_products[offset:offset+limit]
        else:
            # Meta Total Count
            count_query = select(func.count()).select_from(Product).where(*conditions)
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0

            # Min SKU Price subquery for price sorting
            min_price_sub = (
                select(func.min(SKU.price))
                .where(SKU.product_id == Product.id, SKU.active_quantity > 0)
                .scalar_subquery()
            )

            if sort == "price_asc":
                query = query.order_by(min_price_sub.asc())
            elif sort == "price_desc":
                query = query.order_by(min_price_sub.desc())
            elif sort == "new":
                query = query.order_by(Product.created_at.desc())
            else:
                query = query.order_by(Product.created_at.desc())

            query = query.limit(limit).offset(offset)
            result = await db.execute(query)
            products = list(result.scalars().all())

        items = []
        for product in products:
            active_prices = [sku.price for sku in product.skus if sku.active_quantity > 0]
            m_price = min(active_prices) if active_prices else 0
            
            cover = None
            if product.images:
                sorted_imgs = sorted(product.images, key=lambda x: x.get("ordering", 0))
                if sorted_imgs:
                    cover = sorted_imgs[0].get("url")

            items.append({
                "id": product.id,
                "title": product.title,
                "slug": product.slug or "",
                "status": product.status,
                "category_id": product.category_id,
                "min_price": m_price,
                "cover_image": cover,
                "created_at": product.created_at
            })

        return {
            "items": items,
            "total_count": total,
            "limit": limit,
            "offset": offset
        }

    @staticmethod
    async def get_public_product_by_id(db: AsyncSession, product_id: UUID) -> Optional[Product]:
        """Получить продукт по ID для витрины B2C (MODERATED, deleted=false, active SKU > 0)"""
        from src.modules.skus.models import SKU
        from sqlalchemy import exists

        active_sku_exists = exists().where(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        )

        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.skus))
            .where(
                Product.id == product_id,
                Product.status == ProductStatus.MODERATED,
                Product.deleted == False,
                active_sku_exists
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def batch_get_public_products(db: AsyncSession, product_ids: List[UUID]) -> List[Product]:
        """Получить список продуктов по списку ID для витрины B2C (MODERATED, deleted=false, active SKU > 0)"""
        from src.modules.skus.models import SKU
        from sqlalchemy import exists

        active_sku_exists = exists().where(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        )

        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.skus))
            .where(
                Product.id.in_(product_ids),
                Product.status == ProductStatus.MODERATED,
                Product.deleted == False,
                active_sku_exists
            )
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_public_similar_products(db: AsyncSession, product_id: UUID, limit: int = 10) -> List[Product]:
        """Получить похожие товары для B2C из той же категории"""
        from src.modules.skus.models import SKU
        from sqlalchemy import exists, func

        product = await ProductService.get_by_id(db, product_id)
        if not product or product.deleted or product.status != ProductStatus.MODERATED:
            return []

        active_sku_exists = exists().where(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        )

        query = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.skus))
            .where(
                Product.category_id == product.category_id,
                Product.id != product_id,
                Product.status == ProductStatus.MODERATED,
                Product.deleted == False,
                active_sku_exists
            )
            .order_by(func.random())
            .limit(limit)
        )
        result = await db.execute(query)
        similar_products = list(result.scalars().all())

        # Get parent_id from category.path
        parent_id = None
        if product.category and product.category.path:
            parts = product.category.path.split(".")
            if len(parts) > 1:
                try:
                    parent_id = uuid.UUID(parts[-2])
                except ValueError:
                    pass

        if len(similar_products) < limit and parent_id:
            remaining = limit - len(similar_products)
            excluded_ids = [p.id for p in similar_products] + [product_id]
            parent_query = (
                select(Product)
                .options(selectinload(Product.category), selectinload(Product.skus))
                .where(
                    Product.category_id == parent_id,
                    Product.id.notin_(excluded_ids),
                    Product.status == ProductStatus.MODERATED,
                    Product.deleted == False,
                    active_sku_exists
                )
                .order_by(func.random())
                .limit(remaining)
            )
            parent_result = await db.execute(parent_query)
            similar_products.extend(list(parent_result.scalars().all()))

        return similar_products

    @staticmethod
    async def process_moderation_event(
        db: AsyncSession,
        event: ModerationEventRequest,
        background_tasks: BackgroundTasks
    ) -> None:
        # Check idempotency
        existing_event = await db.get(ProcessedEvent, event.idempotency_key)
        if existing_event:
            return  # Already processed

        # Get product
        product = await ProductService.get_by_id(db, event.product_id)
        if not product:
            raise ProductNotFoundError("Product not found")

        final_status = event.event_type

        if final_status == "MODERATED":
            product.status = ProductStatus.MODERATED
            product.blocking_reason_id = None
            product.blocking_reason_title = None
            product.moderator_comment = None
            product.field_reports = []

        elif final_status == "BLOCKED":
            if event.hard_block:
                product.status = ProductStatus.HARD_BLOCKED
            else:
                product.status = ProductStatus.BLOCKED
            
            product.blocking_reason_id = event.blocking_reason_id
            product.blocking_reason_title = "Blocked by moderation"
            product.moderator_comment = event.moderator_comment

            # Save field reports
            if event.field_reports:
                product.field_reports = [
                    {
                        "field_name": fr.field_name,
                        "sku_id": str(fr.sku_id) if fr.sku_id else None,
                        "comment": fr.comment
                    }
                    for fr in event.field_reports
                ]
            else:
                product.field_reports = []

            # Send cascade to B2C only if it was visible
            if any(sku.active_quantity > 0 for sku in product.skus):
                sku_ids = [str(sku.id) for sku in product.skus]
                from src.modules.common.events import send_b2c_product_event
                background_tasks.add_task(
                    send_b2c_product_event,
                    product.id,
                    sku_ids,
                    "PRODUCT_BLOCKED"
                )

        # Record processed event
        processed_event = ProcessedEvent(
            idempotency_key=event.idempotency_key,
            product_id=event.product_id,
            status=product.status
        )
        db.add(processed_event)
        await db.commit()

    @staticmethod
    async def get_category_filters(db: AsyncSession, category_id: UUID) -> dict:
        from src.modules.skus.models import SKU
        from sqlalchemy import exists

        active_sku_exists = exists().where(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        )
        
        query = (
            select(Product)
            .options(selectinload(Product.skus))
            .where(
                Product.category_id == category_id,
                Product.status == ProductStatus.MODERATED,
                Product.deleted == False,
                active_sku_exists
            )
        )
        result = await db.execute(query)
        products = list(result.scalars().all())

        if not products:
            return {"items": []}

        all_prices = []
        char_map = {}
        for p in products:
            for sku in p.skus:
                if sku.active_quantity > 0:
                    all_prices.append(sku.price)
            if p.characteristics:
                for char in p.characteristics:
                    name = char.get("name")
                    val = char.get("value")
                    if name and val:
                        if name not in char_map:
                            char_map[name] = set()
                        char_map[name].add(val)

        filters = []
        if all_prices:
            filters.append({
                "slug": "price",
                "name": "Цена",
                "type": "range",
                "min": min(all_prices),
                "max": max(all_prices)
            })

        for name, values_set in char_map.items():
            filters.append({
                "slug": safe_slugify(name),
                "name": name,
                "type": "list",
                "value": list(values_set)
            })
            
        return {"items": filters}

    @staticmethod
    async def get_category_facets(db: AsyncSession, category_id: UUID, filters_dict: dict) -> dict:
        from src.modules.skus.models import SKU
        from sqlalchemy import exists

        active_sku_exists = exists().where(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        )
        
        query = (
            select(Product)
            .where(
                Product.category_id == category_id,
                Product.status == ProductStatus.MODERATED,
                Product.deleted == False,
                active_sku_exists
            )
        )
        result = await db.execute(query)
        all_products = list(result.scalars().all())

        filtered_products = []
        for p in all_products:
            if ProductService._matches_filters(p, filters_dict):
                filtered_products.append(p)

        facets_map = {}
        for p in filtered_products:
            if p.characteristics:
                for char in p.characteristics:
                    name = char.get("name")
                    val = char.get("value")
                    if name and val:
                        slug = safe_slugify(name)
                        if slug not in facets_map:
                            facets_map[slug] = {}
                        if val not in facets_map[slug]:
                            facets_map[slug][val] = 0
                        facets_map[slug][val] += 1

        facets_list = []
        for slug, values_counts in facets_map.items():
            values_list = []
            for val, count in values_counts.items():
                values_list.append({"value": val, "count": count})
            facets_list.append({
                "name": slug,
                "values": values_list
            })

        return {
            "category_id": category_id,
            "facets": facets_list
        }
