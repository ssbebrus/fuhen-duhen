import pytest
import uuid
import jwt
from unittest.mock import patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.main import app
from src.config import settings
from src.modules.products.models import Product, ProductStatus, ProcessedEvent


@pytest.fixture
async def setup_moderation_data(test_db: AsyncSession):
    # 1. Create seller
    seller_id = uuid.uuid4()
    email = f"seller_{seller_id}@test.com"
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id}', '{email}', 'hash', 'Test', 'Seller', 'Corp', now(), now())"
    ))
    
    # 2. Create category
    category_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{category_id}', 'ModerationCat', 0, '{category_id}', true, now(), now())"
    ))

    # 3. Create products with different initial statuses
    product_id_on_mod = uuid.uuid4()
    product_id_blocked = uuid.uuid4()
    product_id_hard_blocked = uuid.uuid4()

    await test_db.execute(text(
        f"INSERT INTO products (id, title, slug, description, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_on_mod}', 'Product Moderating', 'p-mod', 'Desc', 'ON_MODERATION', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))

    reason_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, slug, description, status, category_id, seller_id, images, characteristics, blocking_reason_id, blocking_reason_title, moderator_comment, field_reports, created_at, updated_at) "
        f"VALUES ('{product_id_blocked}', 'Product Blocked', 'p-blocked', 'Desc', 'BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', '{reason_id}', 'Bad Description', 'Check text', '[{{\"field_name\": \"description\", \"sku_id\": null, \"comment\": \"Too short\"}}]', now(), now())"
    ))

    await test_db.execute(text(
        f"INSERT INTO products (id, title, slug, description, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_hard_blocked}', 'Product Hard Blocked', 'p-hblocked', 'Desc', 'HARD_BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))

    # 4. Create SKU for the products to check cascade sku_ids
    sku_id_1 = uuid.uuid4()
    sku_id_2 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, stock_quantity, product_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_1}', 'SKU 1', 1000, 10, '{product_id_on_mod}', '[]', '[]', now(), now()), "
        f"('{sku_id_2}', 'SKU 2', 2000, 20, '{product_id_blocked}', '[]', '[]', now(), now())"
    ))

    await test_db.flush()

    token = jwt.encode({"sub": str(seller_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    yield {
        "seller_id": seller_id,
        "category_id": category_id,
        "product_id_on_mod": product_id_on_mod,
        "product_id_blocked": product_id_blocked,
        "product_id_hard_blocked": product_id_hard_blocked,
        "sku_id_1": sku_id_1,
        "sku_id_2": sku_id_2,
        "token": token,
        "service_headers": {"X-Service-Key": settings.B2B_TO_MOD_KEY}
    }


@pytest.mark.asyncio
async def test_moderated_event_clears_blocking_data(client: AsyncClient, setup_moderation_data: dict, test_db: AsyncSession):
    idempotency_key = uuid.uuid4()
    product_id = setup_moderation_data["product_id_blocked"]

    payload = {
        "idempotency_key": str(idempotency_key),
        "product_id": str(product_id),
        "event_type": "MODERATED",
        "occurred_at": "2026-03-15T14:30:00.000Z"
    }

    response = await client.post(
        "/api/v1/moderation/events",
        json=payload,
        headers=setup_moderation_data["service_headers"]
    )
    assert response.status_code == 204

    # Verify database status using ORM properties
    res = await test_db.execute(select(Product).where(Product.id == product_id))
    product = res.scalar_one()
    
    assert product.status == ProductStatus.MODERATED
    assert product.blocking_reason_id is None
    assert product.blocking_reason_title is None
    assert product.moderator_comment is None
    assert product.field_reports == []

    # Verify idempotency recorded using ORM properties
    res_event = await test_db.execute(select(ProcessedEvent).where(ProcessedEvent.idempotency_key == idempotency_key))
    processed_event = res_event.scalar_one_or_none()
    assert processed_event is not None
    assert processed_event.product_id == product_id
    assert processed_event.status == "MODERATED"


@pytest.mark.asyncio
@patch("src.modules.common.events.send_b2c_product_event")
async def test_blocked_soft_saves_field_reports(mock_send, client: AsyncClient, setup_moderation_data: dict, test_db: AsyncSession):
    idempotency_key = uuid.uuid4()
    product_id = setup_moderation_data["product_id_on_mod"]
    reason_id = uuid.uuid4()

    payload = {
        "idempotency_key": str(idempotency_key),
        "product_id": str(product_id),
        "event_type": "BLOCKED",
        "hard_block": False,
        "blocking_reason_id": str(reason_id),
        "moderator_comment": "Несоответствие описания и фотографий",
        "field_reports": [
            {
                "field_name": "description",
                "sku_id": None,
                "comment": "Текст описания скопирован с другого товара"
            }
        ],
        "occurred_at": "2026-03-15T14:30:00.000Z"
    }

    response = await client.post(
        "/api/v1/moderation/events",
        json=payload,
        headers=setup_moderation_data["service_headers"]
    )
    assert response.status_code == 204

    # Verify database status using ORM properties
    res = await test_db.execute(select(Product).where(Product.id == product_id))
    product = res.scalar_one()

    assert product.status == ProductStatus.BLOCKED
    assert product.blocking_reason_id == reason_id
    assert product.blocking_reason_title == "Blocked by moderation"
    assert product.moderator_comment == "Несоответствие описания и фотографий"
    assert len(product.field_reports) == 1
    assert product.field_reports[0]["field_name"] == "description"
    assert product.field_reports[0]["comment"] == "Текст описания скопирован с другого товара"

    # Verify cascade event to B2C is sent with SKU ID 1
    mock_send.assert_called_once_with(
        product_id,
        [str(setup_moderation_data["sku_id_1"])],
        "PRODUCT_BLOCKED"
    )


@pytest.mark.asyncio
@patch("src.modules.common.events.send_b2c_product_event")
async def test_blocked_hard_sets_terminal_status(mock_send, client: AsyncClient, setup_moderation_data: dict, test_db: AsyncSession):
    idempotency_key = uuid.uuid4()
    product_id = setup_moderation_data["product_id_on_mod"]
    reason_id = uuid.uuid4()

    payload = {
        "idempotency_key": str(idempotency_key),
        "product_id": str(product_id),
        "event_type": "BLOCKED",
        "hard_block": True,
        "blocking_reason_id": str(reason_id),
        "moderator_comment": "Terminal comment",
        "occurred_at": "2026-03-15T14:30:00.000Z"
    }

    response = await client.post(
        "/api/v1/moderation/events",
        json=payload,
        headers=setup_moderation_data["service_headers"]
    )
    assert response.status_code == 204

    # Verify database status is HARD_BLOCKED using ORM properties
    res = await test_db.execute(select(Product).where(Product.id == product_id))
    product = res.scalar_one()

    assert product.status == ProductStatus.HARD_BLOCKED
    assert product.blocking_reason_id == reason_id
    assert product.blocking_reason_title == "Blocked by moderation"
    assert product.moderator_comment == "Terminal comment"

    # Verify cascade event to B2C is sent
    mock_send.assert_called_once_with(
        product_id,
        [str(setup_moderation_data["sku_id_1"])],
        "PRODUCT_BLOCKED"
    )


@pytest.mark.asyncio
async def test_hard_blocked_product_rejects_seller_edits(client: AsyncClient, setup_moderation_data: dict):
    product_id = setup_moderation_data["product_id_hard_blocked"]
    headers = {"Authorization": f"Bearer {setup_moderation_data['token']}"}

    # 1. Reject PATCH (edit)
    payload = {
        "title": "Seller trying to edit hard blocked",
        "description": "Will fail",
        "category_id": str(setup_moderation_data["category_id"])
    }
    response_patch = await client.patch(f"/api/v1/products/{product_id}", json=payload, headers=headers)
    assert response_patch.status_code == 403
    assert response_patch.json()["code"] == "FORBIDDEN"

    # 2. Reject DELETE
    response_delete = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response_delete.status_code == 403
    assert response_delete.json()["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_duplicate_event_same_idempotency_key_no_side_effects(client: AsyncClient, setup_moderation_data: dict, test_db: AsyncSession):
    idempotency_key = uuid.uuid4()
    product_id = setup_moderation_data["product_id_on_mod"]

    payload = {
        "idempotency_key": str(idempotency_key),
        "product_id": str(product_id),
        "event_type": "MODERATED",
        "occurred_at": "2026-03-15T14:30:00.000Z"
    }

    # Call 1
    response1 = await client.post(
        "/api/v1/moderation/events",
        json=payload,
        headers=setup_moderation_data["service_headers"]
    )
    assert response1.status_code == 204

    # Call 2
    response2 = await client.post(
        "/api/v1/moderation/events",
        json=payload,
        headers=setup_moderation_data["service_headers"]
    )
    assert response2.status_code == 204

    # Verify database has only 1 processed event with that key
    res = await test_db.execute(select(ProcessedEvent).where(ProcessedEvent.idempotency_key == idempotency_key))
    processed_event = res.scalar_one_or_none()
    assert processed_event is not None


@pytest.mark.asyncio
async def test_missing_service_key_returns_401(client: AsyncClient, setup_moderation_data: dict):
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": str(setup_moderation_data["product_id_on_mod"]),
        "event_type": "MODERATED",
        "occurred_at": "2026-03-15T14:30:00.000Z"
    }

    # 1. Missing service key header
    response = await client.post("/api/v1/moderation/events", json=payload)
    assert response.status_code == 401

    # 2. Invalid service key header
    response_invalid = await client.post(
        "/api/v1/moderation/events",
        json=payload,
        headers={"X-Service-Key": "completely_invalid_key"}
    )
    assert response_invalid.status_code == 401
