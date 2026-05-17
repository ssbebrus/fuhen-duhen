import httpx
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from uuid import UUID
from src.config import settings

logger = logging.getLogger(__name__)

async def send_moderation_event(product_id: UUID, seller_id: UUID, event_type: str = "CREATED"):
    idemp_key = str(uuid.uuid5(uuid.NAMESPACE_OID, f"{product_id}_{event_type}"))
    event_data = {
        "idempotency_key": idemp_key,
        "product_id": str(product_id),
        "seller_id": str(seller_id),
        "event": event_type,
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    url = f"{settings.MODERATION_URL}/api/v1/events/product"
    headers = {"X-Service-Key": settings.B2B_TO_MOD_KEY}
    
    max_retries = 5
    base_delay = 1.0
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(url, json=event_data, headers=headers, timeout=5.0)
                response.raise_for_status()
                logger.info(f"Successfully sent moderation event {event_type} for product {product_id}")
                return
            except (httpx.HTTPError, httpx.NetworkError) as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for product {product_id}: {e}. "
                    f"Retrying in {delay}s..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to send moderation event after {max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending moderation event: {e}")
                break

async def send_b2c_product_event(product_id: UUID, sku_ids: list[str], event_type: str = "PRODUCT_DELETED"):
    idemp_key = str(uuid.uuid5(uuid.NAMESPACE_OID, f"{product_id}_{event_type}_b2c"))
    event_data = {
        "idempotency_key": idemp_key,
        "event": event_type,
        "product_id": str(product_id),
        "sku_ids": sku_ids,
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    url = f"{settings.B2C_URL}/api/v1/events/product"
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    max_retries = 5
    base_delay = 1.0
    
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(url, json=event_data, headers=headers, timeout=5.0)
                response.raise_for_status()
                logger.info(f"Successfully sent B2C event {event_type} for product {product_id}")
                return
            except (httpx.HTTPError, httpx.NetworkError) as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for product {product_id} to B2C: {e}. "
                    f"Retrying in {delay}s..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to send B2C event after {max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending B2C event: {e}")
                break

