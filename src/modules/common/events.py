import httpx
import uuid
from datetime import datetime, timezone
from uuid import UUID
from src.config import settings

async def send_moderation_event(product_id: UUID, seller_id: UUID, event_type: str = "CREATED"):
    event_data = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": str(product_id),
        "seller_id": str(seller_id),
        "event": event_type,
        "date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    url = f"{settings.MODERATION_URL}/api/v1/events/product"
    headers = {"X-Service-Key": settings.B2B_TO_MOD_KEY}
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=event_data, headers=headers, timeout=5.0)
        except Exception:
            pass
