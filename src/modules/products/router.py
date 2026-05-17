from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.db.database import get_db
from .schemas import (
    ProductCreate, ProductUpdate, ProductResponse, PaginatedProductResponse,
    ProductImageCreateRequest, ProductImageUpdateRequest, ProductImageResponse,
    ProductPublicResponse, BlockingReason
)
from .service import ProductService
from src.modules.auth.dependencies import get_current_seller, get_auth_context, AuthContext
from src.modules.auth.models import Seller
from src.modules.common.events import send_moderation_event, send_b2c_product_event
from typing import Union

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("/", response_model=PaginatedProductResponse, summary="Получить список своих товаров с пагинацией")
async def get_products(
    limit: int = 10, 
    offset: int = 0, 
    include_deleted: bool = False,
    db: AsyncSession = Depends(get_db),
    seller: Seller = Depends(get_current_seller)
):
    """Получить список своих товаров с пагинацией"""
    return await ProductService.get_all(db, limit=limit, offset=offset, seller_id=seller.id, include_deleted=include_deleted)

@router.get("/{product_id}", response_model=Union[ProductResponse, ProductPublicResponse], summary="Получить товар по ID")
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
        resp = ProductResponse.model_validate(product)
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
