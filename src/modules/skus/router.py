import httpx
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.db.database import get_db
from src.config import settings
from src.modules.products.models import ProductStatus
from .schemas import SKUCreate, SKUUpdate, SKUResponse
from .service import SKUService

router = APIRouter(prefix="/skus", tags=["SKUs"])

async def send_moderation_event(product_id: UUID, seller_id: UUID):
    event_data = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": str(product_id),
        "seller_id": str(seller_id),
        "event": "CREATED",
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    url = f"{settings.MODERATION_URL}/api/v1/events/product"
    headers = {"X-Service-Key": settings.B2B_TO_MOD_KEY}
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=event_data, headers=headers, timeout=5.0)
        except Exception:
            pass

@router.post("/create", response_model=SKUResponse, status_code=status.HTTP_201_CREATED, summary="Создать SKU")
async def create_sku(sku_in: SKUCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Создать новый SKU"""
    if sku_in.price <= 0:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "price must be a positive integer (kopecks)"})
    
    # Validation from openapi: name is required by schema, Pydantic handles it.
    # Images and characteristics are optional with default []
        
    try:
        new_sku, status_changed, product = await SKUService.create(db, sku_in)
    except ValueError as e:
        if str(e) == "Product not found":
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
        elif str(e) == "Product is hard-blocked":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot add SKU to hard-blocked product"})
        raise
        
    if status_changed:
        background_tasks.add_task(send_moderation_event, product.id, product.seller_id)
        
    return new_sku

@router.put("/{sku_id}", response_model=SKUResponse, summary="Изменить SKU")
async def update_sku(sku_id: UUID, sku_in: SKUUpdate, db: AsyncSession = Depends(get_db)):
    """Изменить SKU"""
    sku = await SKUService.update(db, sku_id, sku_in)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU не найден")
    return sku
