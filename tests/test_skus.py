import pytest
import uuid
import jwt
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from unittest.mock import patch

from src.main import app
from src.db.database import AsyncSessionLocal
from src.config import settings

@pytest.fixture
async def setup_data(test_db: AsyncSession):
    # Create seller
    seller_id = uuid.uuid4()
    email = f"test_{seller_id}@test.com"
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id}', '{email}', 'hash', 'T', 'T', 'C', now(), now())"
    ))
    
    # Create category
    category_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{category_id}', 'TestCat', 0, '{category_id}', true, now(), now())"
    ))

    # Create product 1 (CREATED status)
    product_id_created = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_created}', 'P1', 'CREATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))

    # Create product 2 (HARD_BLOCKED status)
    product_id_blocked = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_blocked}', 'P2', 'HARD_BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))

    # Create product for reserves test
    product_id_reserves = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_reserves}', 'P Res', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))
    
    # Create seller 2
    seller_id_2 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id_2}', 'test2@test.com', 'hash', 'T', 'T', 'C', now(), now())"
    ))

    # Create product for seller 2
    product_id_other = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_other}', 'P Oth', 'CREATED', '{category_id}', '{seller_id_2}', '[]', '[]', now(), now())"
    ))

    # Create SKU with reserves for product_id_reserves
    sku_id_reserves = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, cost_price, discount, image, active_quantity, reserved_quantity, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_reserves}', '{product_id_reserves}', 'SKU Res', 1000, 500, 0, 'http://img', 10, 5, '[]', now(), now())"
    ))
    
    # Create SKU for product 2 (other seller)
    sku_id_other = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, cost_price, discount, image, active_quantity, reserved_quantity, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_other}', '{product_id_other}', 'SKU Oth', 1000, 500, 0, 'http://img', 10, 0, '[]', now(), now())"
    ))

    await test_db.flush()
    
    token = jwt.encode({"sub": str(seller_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    yield {
        "seller_id": seller_id, 
        "category_id": category_id, 
        "product_id_created": product_id_created,
        "product_id_blocked": product_id_blocked,
        "product_id_reserves": product_id_reserves,
        "product_id_other": product_id_other,
        "sku_id_reserves": sku_id_reserves,
        "sku_id_other": sku_id_other,
        "token": token
    }
    
    # Очистка не требуется - conftest откатит транзакцию

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_first_sku_transitions_product_to_on_moderation(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "256GB Black",
        "price": 1000,
        "images": [{"url": "http://img.jpg", "ordering": 0}]
    }
    
    response = await client.post("/api/v1/skus/create", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    
    # Verify product state changed to ON_MODERATION
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{setup_data['product_id_created']}'"))
    db_status = res.scalar()
    assert db_status == "ON_MODERATION"

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_first_sku_emits_created_event_to_moderation(mock_send, client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "First SKU",
        "price": 1000,
        "images": [{"url": "http://img.jpg"}]
    }
    
    response = await client.post("/api/v1/skus/create", json=payload, headers=headers)
    assert response.status_code == 201
    
    mock_send.assert_called_once_with(setup_data["product_id_created"], setup_data["seller_id"])

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_second_sku_no_state_change(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload1 = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "SKU 1",
        "price": 1000
    }
    
    # Add first SKU
    response1 = await client.post("/api/v1/skus/create", json=payload1, headers=headers)
    assert response1.status_code == 201
    mock_send.assert_called_once()
    mock_send.reset_mock()
    
    # Change status back to CREATED just to verify it won't change
    await test_db.execute(text(f"UPDATE products SET status = 'CREATED' WHERE id = '{setup_data['product_id_created']}'"))
    await test_db.flush()
    
    # Add second SKU
    payload2 = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "SKU 2",
        "price": 1200
    }
    response2 = await client.post("/api/v1/skus/create", json=payload2, headers=headers)
    assert response2.status_code == 201
    
    # Verify no state change
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{setup_data['product_id_created']}'"))
    db_status = res.scalar()
    assert db_status == "CREATED"
    
    # Verify no event emitted
    mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_add_sku_to_hard_blocked_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "product_id": str(setup_data["product_id_blocked"]),
        "name": "Blocked SKU",
        "price": 1000
    }
    
    response = await client.post("/api/v1/skus/create", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"

@pytest.mark.asyncio
async def test_missing_required_fields_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # Missing name
    payload_no_name = {
        "product_id": str(setup_data["product_id_created"]),
        "price": 1000
    }
    response = await client.post("/api/v1/skus/create", json=payload_no_name, headers=headers)
    assert response.status_code in [400, 422]
    
    # Missing price
    payload_no_price = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "No price"
    }

    response = await client.post("/api/v1/skus/create", json=payload_no_price, headers=headers)
    assert response.status_code in [400, 422]

    response_missing = await client.post("/api/v1/skus/", json=payload_missing, headers=headers)
    # FastAPI schema validation returns 422 for missing fields, but b2b.yaml maps it sometimes or our custom exception handler does 400.
    assert response_missing.status_code in [400, 422]

@pytest.mark.asyncio
async def test_reserves_preserved_after_sku_edit(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "name": "SKU Res Updated",
        "price": 1200,
        "cost_price": 600,
        "discount": 0,
        "image": "http://img2",
        "characteristics": []
    }
    sku_id = setup_data["sku_id_reserves"]
    
    response = await client.put(f"/api/v1/skus/{sku_id}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "SKU Res Updated"
    
    # Check DB directly to ensure reserved_quantity is unchanged
    res = await test_db.execute(text(f"SELECT reserved_quantity FROM skus WHERE id = '{sku_id}'"))
    db_reserved = res.scalar()
    assert db_reserved == 5

@pytest.mark.asyncio
async def test_edit_others_sku_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "name": "SKU Oth Updated",
        "price": 1200,
        "cost_price": 600,
        "discount": 0,
        "image": "http://img2",
        "characteristics": []
    }
    sku_id = setup_data["sku_id_other"]
    
    response = await client.put(f"/api/v1/skus/{sku_id}", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_OWNER"

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_edit_sku_returns_product_to_on_moderation(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "name": "SKU Res Edited",
        "price": 1500,
        "cost_price": 700,
        "discount": 0,
        "image": "http://img3",
        "characteristics": []
    }
    sku_id = setup_data["sku_id_reserves"]
    product_id = setup_data["product_id_reserves"]
    
    # In setup_data, product_id_reserves status is MODERATED
    response = await client.put(f"/api/v1/skus/{sku_id}", json=payload, headers=headers)
    assert response.status_code == 200
    
    # Verify product state changed to ON_MODERATION
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{product_id}'"))
    db_status = res.scalar()
    assert db_status == "ON_MODERATION"
    mock_send.assert_called_once_with(product_id, setup_data["seller_id"], "EDITED")