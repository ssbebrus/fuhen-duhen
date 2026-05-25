import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from unittest.mock import patch

from src.config import settings

@pytest.fixture
async def setup_inventory_data(test_db: AsyncSession):
    # 1. Create seller
    seller_id = uuid.uuid4()
    email = f"seller_{seller_id}@test.com"
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id}', '{email}', 'hash', 'Test', 'Seller', 'TestCompany', now(), now())"
    ))
    
    # 2. Create category
    category_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{category_id}', 'Electronics', 0, '{category_id}', true, now(), now())"
    ))

    # 3. Create a MODERATED active product
    product_id_active = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, deleted, created_at, updated_at) "
        f"VALUES ('{product_id_active}', 'Active Product', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', false, now(), now())"
    ))

    # 4. Create a BLOCKED product
    product_id_blocked = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, deleted, created_at, updated_at) "
        f"VALUES ('{product_id_blocked}', 'Blocked Product', 'HARD_BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', false, now(), now())"
    ))

    # 5. Create a deleted product
    product_id_deleted = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, deleted, created_at, updated_at) "
        f"VALUES ('{product_id_deleted}', 'Deleted Product', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', true, now(), now())"
    ))

    # 6. Create SKUs for the active product
    sku_id_1 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, reserved_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_1}', '{product_id_active}', 'SKU 1', 1000, 10, 10, 0, 'ART-1', '[]', '[]', now(), now())"
    ))

    sku_id_2 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, reserved_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_2}', '{product_id_active}', 'SKU 2', 2000, 20, 20, 0, 'ART-2', '[]', '[]', now(), now())"
    ))

    # 7. Create SKU for the blocked product
    sku_id_blocked = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, reserved_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_blocked}', '{product_id_blocked}', 'SKU Blocked', 1500, 15, 15, 0, 'ART-BLOCKED', '[]', '[]', now(), now())"
    ))

    # 8. Create SKU for the deleted product
    sku_id_deleted = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, reserved_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_deleted}', '{product_id_deleted}', 'SKU Deleted', 1200, 12, 12, 0, 'ART-DELETED', '[]', '[]', now(), now())"
    ))

    await test_db.flush()

    return {
        "product_id_active": product_id_active,
        "sku_id_1": sku_id_1,
        "sku_id_2": sku_id_2,
        "sku_id_blocked": sku_id_blocked,
        "sku_id_deleted": sku_id_deleted,
    }


@pytest.mark.asyncio
async def test_reserve_all_skus_succeeds(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 5},
            {"sku_id": str(setup_inventory_data["sku_id_2"]), "quantity": 12}
        ]
    }

    response = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["order_id"] == str(order_id)
    assert data["status"] == "RESERVED"
    assert "reserved_at" in data
    assert data["reserved"] is True
    assert len(data["items"]) == 2

    # Check quantities in DB
    res_1 = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    sku_1_stock = res_1.fetchone()
    assert sku_1_stock[0] == 5
    assert sku_1_stock[1] == 5

    res_2 = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_2']}'"))
    sku_2_stock = res_2.fetchone()
    assert sku_2_stock[0] == 8
    assert sku_2_stock[1] == 12


@pytest.mark.asyncio
async def test_partial_insufficient_stock_returns_409_all_rollback(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    # Requesting valid amount for SKU 1, but too much for SKU 2
    payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 5},
            {"sku_id": str(setup_inventory_data["sku_id_2"]), "quantity": 25}
        ]
    }

    response = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response.status_code == 409, response.text
    data = response.json()

    assert data["code"] == "INSUFFICIENT_STOCK"
    assert "details" in data
    assert data["details"]["reserved"] is False
    assert data["reserved"] is False

    failed_items = data["details"]["failed_items"]
    assert len(failed_items) == 1
    assert failed_items[0]["sku_id"] == str(setup_inventory_data["sku_id_2"])
    assert failed_items[0]["requested"] == 25
    assert failed_items[0]["available"] == 20
    assert failed_items[0]["reason"] == "INSUFFICIENT_STOCK"

    # Verify that SKU 1 was NOT reserved (atomic rollback)
    res_1 = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    sku_1_stock = res_1.fetchone()
    assert sku_1_stock[0] == 10
    assert sku_1_stock[1] == 0

    # Verify that SKU 2 was NOT reserved either
    res_2 = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_2']}'"))
    sku_2_stock = res_2.fetchone()
    assert sku_2_stock[0] == 20
    assert sku_2_stock[1] == 0


@pytest.mark.asyncio
async def test_idempotent_reserve_returns_200_without_double_deduction(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 3}
        ]
    }

    # First call
    response_1 = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response_1.status_code == 200

    # Second call with the same idempotency key
    response_2 = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response_2.status_code == 200
    assert response_1.json() == response_2.json()

    # Verify database: active_quantity should be 7 (10 - 3), not 4 (10 - 3 - 3)
    res = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    sku_stock = res.fetchone()
    assert sku_stock[0] == 7
    assert sku_stock[1] == 3


@pytest.mark.asyncio
@patch("src.modules.inventory.service.send_b2c_sku_out_of_stock_event")
async def test_sku_out_of_stock_event_emitted(mock_send, client: AsyncClient, setup_inventory_data: dict):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 10}
        ]
    }

    response = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response.status_code == 200

    # The background task is added. FastAPI runs background tasks after response is returned in test client.
    # So the mock should be called.
    mock_send.assert_called_once_with(
        setup_inventory_data["product_id_active"], 
        setup_inventory_data["sku_id_1"]
    )


@pytest.mark.asyncio
async def test_unreserve_restores_quantities(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    reserve_payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # 1. Reserve
    response_reserve = await client.post("/api/v1/inventory/reserve", json=reserve_payload, headers=headers)
    assert response_reserve.status_code == 200

    # Check that reservation took place
    res_before = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock_before = res_before.fetchone()
    assert stock_before[0] == 6
    assert stock_before[1] == 4

    # 2. Unreserve
    unreserve_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    response_unreserve = await client.post("/api/v1/inventory/unreserve", json=unreserve_payload, headers=headers)
    assert response_unreserve.status_code == 200
    data_unreserve = response_unreserve.json()

    assert data_unreserve["order_id"] == str(order_id)
    assert data_unreserve["status"] == "UNRESERVED"
    assert "processed_at" in data_unreserve
    assert data_unreserve["ok"] is True

    # 3. Check that quantities are fully restored
    res_after = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock_after = res_after.fetchone()
    assert stock_after[0] == 10
    assert stock_after[1] == 0


@pytest.mark.asyncio
async def test_unreserve_idempotency(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    order_id = uuid.uuid4()

    unreserve_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # First unreserve (without reservation existing, which acts as a placeholder)
    response_1 = await client.post("/api/v1/inventory/unreserve", json=unreserve_payload, headers=headers)
    assert response_1.status_code == 200

    # Second unreserve
    response_2 = await client.post("/api/v1/inventory/unreserve", json=unreserve_payload, headers=headers)
    assert response_2.status_code == 200
    assert response_1.json() == response_2.json()

    # Check quantities: they shouldn't change at all since no reservation existed
    res = await test_db.execute(text(f"SELECT active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock = res.fetchone()
    assert stock[0] == 10
    assert stock[1] == 0


@pytest.mark.asyncio
async def test_blocked_product_fails_reservation(client: AsyncClient, setup_inventory_data: dict):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    # Request reservation for a blocked product SKU
    payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_blocked"]), "quantity": 1}
        ]
    }

    response = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "INSUFFICIENT_STOCK"
    failed_items = data["details"]["failed_items"]
    assert failed_items[0]["sku_id"] == str(setup_inventory_data["sku_id_blocked"])
    assert failed_items[0]["reason"] == "OUT_OF_STOCK"


@pytest.mark.asyncio
async def test_deleted_product_fails_reservation(client: AsyncClient, setup_inventory_data: dict):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    # Request reservation for a deleted product SKU
    payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_deleted"]), "quantity": 1}
        ]
    }

    response = await client.post("/api/v1/inventory/reserve", json=payload, headers=headers)
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "INSUFFICIENT_STOCK"
    failed_items = data["details"]["failed_items"]
    assert failed_items[0]["sku_id"] == str(setup_inventory_data["sku_id_deleted"])
    assert failed_items[0]["reason"] == "OUT_OF_STOCK"


@pytest.mark.asyncio
async def test_fulfill_decreases_reserved_and_stock_quantities(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    reserve_payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # 1. Reserve first
    response_reserve = await client.post("/api/v1/inventory/reserve", json=reserve_payload, headers=headers)
    assert response_reserve.status_code == 200

    # Check quantities right after reservation: stock=10, active=6, reserved=4
    res_before = await test_db.execute(text(f"SELECT stock_quantity, active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock_before = res_before.fetchone()
    assert stock_before[0] == 10
    assert stock_before[1] == 6
    assert stock_before[2] == 4

    # 2. Fulfill the order
    fulfill_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    response_fulfill = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_fulfill.status_code == 200
    data_fulfill = response_fulfill.json()

    assert data_fulfill["order_id"] == str(order_id)
    assert data_fulfill["status"] == "FULFILLED"
    assert data_fulfill["ok"] is True

    # 3. Check quantities after fulfillment: stock should be 6 (10 - 4), active should remain 6, reserved should be 0 (4 - 4)
    res_after = await test_db.execute(text(f"SELECT stock_quantity, active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock_after = res_after.fetchone()
    assert stock_after[0] == 6
    assert stock_after[1] == 6
    assert stock_after[2] == 0


@pytest.mark.asyncio
async def test_fulfill_idempotency(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    reserve_payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # 1. Reserve
    await client.post("/api/v1/inventory/reserve", json=reserve_payload, headers=headers)

    fulfill_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # First fulfill
    response_1 = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_1.status_code == 200

    # Second fulfill
    response_2 = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_2.status_code == 200
    assert response_1.json() == response_2.json()

    # Check quantities: stock should be 6, reserved should be 0. If it double-fulfilled, stock would be 2.
    res = await test_db.execute(text(f"SELECT stock_quantity, active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock = res.fetchone()
    assert stock[0] == 6
    assert stock[1] == 6
    assert stock[2] == 0


@pytest.mark.asyncio
async def test_fulfill_decreases_reserved_quantity(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    reserve_payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # 1. Reserve
    response_reserve = await client.post("/api/v1/inventory/reserve", json=reserve_payload, headers=headers)
    assert response_reserve.status_code == 200

    # 2. Fulfill
    fulfill_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    response_fulfill = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_fulfill.status_code == 200
    assert response_fulfill.json()["ok"] is True

    # 3. Check that reserved_quantity is decreased (should be 0) and stock_quantity is decreased (should be 6)
    res_after = await test_db.execute(text(f"SELECT stock_quantity, active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock_after = res_after.fetchone()
    assert stock_after[2] == 0  # reserved_quantity decreased to 0
    assert stock_after[0] == 6  # stock_quantity decreased to 6


@pytest.mark.asyncio
async def test_active_quantity_unchanged(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    reserve_payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 3}
        ]
    }

    # 1. Reserve
    await client.post("/api/v1/inventory/reserve", json=reserve_payload, headers=headers)

    # 2. Fulfill
    fulfill_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 3}
        ]
    }

    response_fulfill = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_fulfill.status_code == 200

    # 3. Check active_quantity is unchanged (should be 7, since 10 - 3 reserved, and fulfill doesn't change active_quantity)
    res_after = await test_db.execute(text(f"SELECT stock_quantity, active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock_after = res_after.fetchone()
    assert stock_after[1] == 7  # active_quantity remains 7


@pytest.mark.asyncio
async def test_idempotent_fulfill_no_double_deduction(client: AsyncClient, setup_inventory_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.SERVICE_KEY}
    idempotency_key = uuid.uuid4()
    order_id = uuid.uuid4()

    reserve_payload = {
        "idempotency_key": str(idempotency_key),
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # 1. Reserve
    await client.post("/api/v1/inventory/reserve", json=reserve_payload, headers=headers)

    fulfill_payload = {
        "order_id": str(order_id),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 4}
        ]
    }

    # First fulfill call
    response_1 = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_1.status_code == 200

    # Second fulfill call (should be idempotent, no changes)
    response_2 = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload, headers=headers)
    assert response_2.status_code == 200
    assert response_1.json() == response_2.json()

    # Check quantities: stock should be 6, reserved should be 0. (If double-deducted, stock would be 2)
    res = await test_db.execute(text(f"SELECT stock_quantity, active_quantity, reserved_quantity FROM skus WHERE id = '{setup_inventory_data['sku_id_1']}'"))
    stock = res.fetchone()
    assert stock[0] == 6
    assert stock[2] == 0


@pytest.mark.asyncio
async def test_missing_service_key_returns_401(client: AsyncClient, setup_inventory_data: dict):
    fulfill_payload = {
        "order_id": str(uuid.uuid4()),
        "items": [
            {"sku_id": str(setup_inventory_data["sku_id_1"]), "quantity": 1}
        ]
    }

    response = await client.post("/api/v1/inventory/fulfill", json=fulfill_payload)  # No X-Service-Key header
    assert response.status_code == 401
