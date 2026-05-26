from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID

from src.db.database import get_db
from .schemas import (
    ProductCreate, ProductUpdate, ProductResponse, PaginatedProductResponse,
    ProductImageCreateRequest, ProductImageUpdateRequest, ProductImageResponse,
    ProductPublicResponse, BlockingReason, ProductDetailResponse, ProductStatus,
    ModerationEventRequest
)
from .service import ProductService
from src.modules.auth.dependencies import get_current_seller, get_auth_context, AuthContext
from src.modules.auth.models import Seller
from src.modules.common.events import send_moderation_event, send_b2c_product_event
from typing import Union

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/", response_model=PaginatedProductResponse, summary="Получить список своих товаров с пагинацией")
async def get_products(
    limit: int = 20, 
    offset: int = 0, 
    status: Optional[ProductStatus] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Получить список своих товаров с пагинацией"""
    return await ProductService.get_all(
        db,
        limit=limit,
        offset=offset,
        seller_id=seller.id,
        include_deleted=include_deleted,
        status=status,
        search=search
    )

@router.get("/{product_id}", response_model=Union[ProductDetailResponse, ProductPublicResponse], summary="Получить товар по ID")
async def get_product(
    product_id: UUID, 
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db)
):
    """Получить товар по ID (два режима: Seller и Service)"""
    product = await ProductService.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        
    if auth_context.mode == "seller":
        if str(product.seller_id) != str(auth_context.seller_id):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        
        # Build blocking_reason if present
        blocking_reason = None
        if product.blocking_reason_id and product.blocking_reason_title:
            blocking_reason = BlockingReason(
                id=product.blocking_reason_id,
                title=product.blocking_reason_title,
                comment=product.moderator_comment or ""
            )
            
        # Pydantic will build the response
        resp = ProductDetailResponse.model_validate(product)
        if blocking_reason:
            resp.blocking_reason = blocking_reason
        return resp
    else:
        # Service mode
        return ProductPublicResponse.model_validate(product)

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Создать товар")
async def create_product(
    product_in: ProductCreate, 
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Создать новый товар"""
    return await ProductService.create(db, product_in, seller_id=seller.id)

@router.patch("/{product_id}", response_model=ProductResponse, summary="Обновить товар")
async def update_product(
    product_id: UUID, 
    product_in: ProductUpdate, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Обновить товар"""
    try:
        product, status_changed = await ProductService.update(db, product_id, product_in, seller.id)
    except ValueError as e:
        if str(e) == "Product not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        elif str(e) == "Product does not belong to the authenticated seller":
            raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        elif str(e) == "Cannot edit hard-blocked product":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        raise
        
        
    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
        
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Мягкое удаление товара")
async def delete_product(
    product_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Мягкое удаление товара"""
    try:
        product, sku_ids = await ProductService.delete(db, product_id, seller.id)
    except ValueError as e:
        if str(e) == "Product not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        elif str(e) == "Product does not belong to the authenticated seller":
            raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        elif str(e) == "Product already deleted":
            raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "Product already deleted"})
        elif str(e) == "Cannot edit hard-blocked product":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        raise
        
    background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "DELETED")
    background_tasks.add_task(send_b2c_product_event, product.id, sku_ids, "PRODUCT_DELETED")
    return None

@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED, summary="Добавить изображение к товару")
async def add_product_image(
    product_id: UUID,
    image_in: ProductImageCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Добавить изображение к товару"""
    try:
        new_image, status_changed, product = await ProductService.add_image(db, product_id, image_in, seller.id)
    except ValueError as e:
        if str(e) == "Product not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        elif str(e) == "Product does not belong to the authenticated seller":
            raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        elif str(e) == "Cannot edit hard-blocked product":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        raise

    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
    return new_image

@router.patch("/images/{image_id}", response_model=ProductImageResponse, summary="Обновить изображение товара")
async def update_product_image(
    image_id: UUID,
    image_in: ProductImageUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Обновить изображение товара"""
    try:
        updated_image, status_changed, product = await ProductService.update_image(db, image_id, image_in, seller.id)
    except ValueError as e:
        if str(e) == "Image not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
        elif str(e) == "Product does not belong to the authenticated seller":
            raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        elif str(e) == "Cannot edit hard-blocked product":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        raise

    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
    return updated_image

@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить изображение товара")
async def delete_product_image(
    image_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Удалить изображение товара"""
    try:
        status_changed, product = await ProductService.delete_image(db, image_id, seller.id)
    except ValueError as e:
        if str(e) == "Image not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
        elif str(e) == "Product does not belong to the authenticated seller":
            raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"})
        elif str(e) == "Cannot edit hard-blocked product":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"})
        raise

    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id, "EDITED")
    return None

from fastapi import Header
from typing import Optional
from .schemas import (
    ProductPublicShortResponse, ProductPublicPaginatedResponse, ProductBatchRequest
)
from src.modules.skus.schemas import SKUPublicResponse
from src.config import settings
from src.modules.products.models import Product, ProductStatus

async def verify_service_key(x_service_key: Optional[str] = Header(None, alias="X-Service-Key")) -> str:
    if not x_service_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key header is missing"}
        )
    if x_service_key != settings.SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid X-Service-Key"}
        )
    return x_service_key

public_router = APIRouter(prefix="/public", tags=["Public Catalog"])

@public_router.get("/products", response_model=ProductPublicPaginatedResponse, summary="Витрина — список товаров")
async def list_public_products(
    category_id: Optional[UUID] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
    ids: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """Витрина — только MODERATED, не deleted, active_quantity > 0"""
    data = await ProductService.get_public_catalog(
        db, limit=limit, offset=offset, category_id=category_id, search=search, sort=sort, ids=ids
    )
    return ProductPublicPaginatedResponse.model_validate(data)

@public_router.post("/products/batch", response_model=List[ProductPublicResponse], summary="Batch-получение карточек по списку product_id")
async def batch_public_products(
    request: ProductBatchRequest,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """Batch-получение карточек по списку product_id (только MODERATED, не deleted, active_quantity > 0)"""
    products = await ProductService.batch_get_public_products(db, request.product_ids)
    return [ProductPublicResponse.model_validate(p) for p in products]

@public_router.get("/products/{product_id}", response_model=ProductPublicResponse, summary="Карточка товара для витрины")
async def get_public_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """Карточка товара для витрины (только MODERATED, не deleted, active_quantity > 0)"""
    product = await ProductService.get_public_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    return ProductPublicResponse.model_validate(product)

@public_router.get("/products/{product_id}/similar", response_model=List[ProductPublicShortResponse], summary="Похожие товары")
async def get_public_similar_products(
    product_id: UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """Похожие товары (случайная выборка из той же категории)"""
    product = await ProductService.get_by_id(db, product_id)
    if not product or product.deleted or product.status != ProductStatus.MODERATED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    similar = await ProductService.get_public_similar_products(db, product_id, limit)
    return similar

@public_router.get("/skus/{sku_id}", response_model=SKUPublicResponse, summary="SKU для витрины")
async def get_public_sku(
    sku_id: UUID,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_service_key)
):
    """SKU для витрины (без cost_price, reserved_quantity, только MODERATED и активные)"""
    from src.modules.skus.service import SKUService

    sku = await SKUService.get_public_sku_by_id(db, sku_id)
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "SKU not found"}
        )
    return SKUPublicResponse.model_validate(sku)


async def verify_moderation_service_key(x_service_key: Optional[str] = Header(None, alias="X-Service-Key")) -> str:
    if not x_service_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key header is missing"}
        )
    if x_service_key != settings.B2B_TO_MOD_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid X-Service-Key"}
        )
    return x_service_key


moderation_router = APIRouter(prefix="/moderation", tags=["Moderation Events"])


@moderation_router.post("/events", status_code=status.HTTP_204_NO_CONTENT, summary="Приём событий от Moderation Service")
async def receive_moderation_event(
    event: ModerationEventRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _service_key: str = Depends(verify_moderation_service_key)
):
    """Приём событий от Moderation Service: MODERATED, BLOCKED (с hard_block flag)"""
    try:
        await ProductService.process_moderation_event(db, event, background_tasks)
    except ValueError as e:
        if str(e) == "Product not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        raise
    return None
