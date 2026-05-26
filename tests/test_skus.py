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

    # Create SKU for product_id_reserves
    sku_id_reserves = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_reserves}', '{product_id_reserves}', 'SKU Res', 1000, 10, 'ART-RES', '[]', '[]', now(), now())"
    ))
    
    # Create SKU for product 2 (other seller)
    sku_id_other = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_other}', '{product_id_other}', 'SKU Oth', 1000, 10, 'ART-OTH', '[]', '[]', now(), now())"
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
        "cost_price": 800,
        "images": [{"url": "http://img.jpg", "ordering": 0}]
    }
    
    response = await client.post("/api/v1/skus", json=payload, headers=headers)
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
        "cost_price": 500,
        "images": [{"url": "http://img.jpg"}]
    }
    
    response = await client.post("/api/v1/skus", json=payload, headers=headers)
    assert response.status_code == 201
    
    mock_send.assert_called_once_with(setup_data["product_id_created"], setup_data["seller_id"])

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_second_sku_no_state_change(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload1 = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "SKU 1",
        "price": 1000,
        "cost_price": 500
    }
    
    # Add first SKU
    response1 = await client.post("/api/v1/skus", json=payload1, headers=headers)
    assert response1.status_code == 201
    mock_send.assert_called_once()
    mock_send.reset_mock()
    
    # Verify product is ON_MODERATION
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{setup_data['product_id_created']}'"))
    db_status = res.scalar()
    assert db_status == "ON_MODERATION"
    
    # Add second SKU while product is ON_MODERATION
    payload2 = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "SKU 2",
        "price": 1200,
        "cost_price": 600
    }
    response2 = await client.post("/api/v1/skus", json=payload2, headers=headers)
    assert response2.status_code == 201
    
    # Verify no state change
    res2 = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{setup_data['product_id_created']}'"))
    db_status2 = res2.scalar()
    assert db_status2 == "ON_MODERATION"
    
    # Verify no event emitted
    mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_add_sku_to_hard_blocked_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "product_id": str(setup_data["product_id_blocked"]),
        "name": "Blocked SKU",
        "price": 1000,
        "cost_price": 500
    }
    
    response = await client.post("/api/v1/skus", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"

@pytest.mark.asyncio
async def test_missing_required_fields_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # Missing name
    payload_no_name = {
        "product_id": str(setup_data["product_id_created"]),
        "price": 1000,
        "cost_price": 500
    }
    response = await client.post("/api/v1/skus", json=payload_no_name, headers=headers)
    assert response.status_code == 400
    
    # Missing price
    payload_no_price = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "No price",
        "cost_price": 500
    }

    response = await client.post("/api/v1/skus", json=payload_no_price, headers=headers)
    assert response.status_code == 400

    # Missing product_id
    payload_no_product = {
        "name": "No product",
        "price": 1000,
        "cost_price": 500
    }
    response = await client.post("/api/v1/skus", json=payload_no_product, headers=headers)
    assert response.status_code == 400

    # Missing cost_price
    payload_no_cost = {
        "product_id": str(setup_data["product_id_created"]),
        "name": "No cost price",
        "price": 1000
    }
    response = await client.post("/api/v1/skus", json=payload_no_cost, headers=headers)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_sku_other_seller_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "product_id": str(setup_data["product_id_other"]),
        "name": "Other SKU",
        "price": 1000,
        "cost_price": 500
    }
    
    response = await client.post("/api/v1/skus", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_OWNER"

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_reserves_preserved_after_sku_edit(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "name": "SKU Res Updated",
        "price": 1200,
        "article": "new-article"
    }
    sku_id = setup_data["sku_id_reserves"]
    
    response = await client.patch(f"/api/v1/skus/{sku_id}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "SKU Res Updated"
    
    # Check DB directly to ensure stock_quantity is unchanged
    res = await test_db.execute(text(f"SELECT stock_quantity FROM skus WHERE id = '{sku_id}'"))
    db_stock = res.scalar()
    assert db_stock == 10

@pytest.mark.asyncio
async def test_edit_others_sku_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "name": "SKU Oth Updated",
        "price": 1200
    }
    sku_id = setup_data["sku_id_other"]
    
    response = await client.patch(f"/api/v1/skus/{sku_id}", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_OWNER"

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_edit_sku_returns_product_to_on_moderation(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "name": "SKU Res Edited",
        "price": 1500
    }
    sku_id = setup_data["sku_id_reserves"]
    product_id = setup_data["product_id_reserves"]
    
    # In setup_data, product_id_reserves status is MODERATED
    response = await client.patch(f"/api/v1/skus/{sku_id}", json=payload, headers=headers)
    assert response.status_code == 200
    
    # Verify product state changed to ON_MODERATION
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{product_id}'"))
    db_status = res.scalar()
    assert db_status == "ON_MODERATION"
    mock_send.assert_called_once_with(product_id, setup_data["seller_id"], "EDITED")

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_add_sku_image(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_reserves"]
    payload = {"url": "http://new-sku-img.jpg", "ordering": 5}
    
    response = await client.post(f"/api/v1/skus/{sku_id}/images", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["url"] == "http://new-sku-img.jpg"
    
    res = await test_db.execute(text(f"SELECT images FROM skus WHERE id = '{sku_id}'"))
    images = res.scalar()
    assert any(img["url"] == "http://new-sku-img.jpg" for img in images)

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_update_sku_image(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_reserves"]
    
    img_id = str(uuid.uuid4())
    await test_db.execute(text(f"UPDATE skus SET images = '[{{\"id\": \"{img_id}\", \"url\": \"http://old.jpg\", \"ordering\": 0}}]' WHERE id = '{sku_id}'"))
    await test_db.flush()
    
    payload = {"url": "http://updated-sku.jpg"}
    response = await client.patch(f"/api/v1/skus/images/{img_id}", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["url"] == "http://updated-sku.jpg"

@pytest.mark.asyncio
@patch("src.modules.skus.router.send_moderation_event")
async def test_delete_sku_image(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_reserves"]
    
    img_id = str(uuid.uuid4())
    await test_db.execute(text(f"UPDATE skus SET images = '[{{\"id\": \"{img_id}\", \"url\": \"http://old.jpg\", \"ordering\": 0}}]' WHERE id = '{sku_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/skus/images/{img_id}", headers=headers)
    assert response.status_code == 204
    
    res = await test_db.execute(text(f"SELECT images FROM skus WHERE id = '{sku_id}'"))
    images = res.scalar()
    assert len(images) == 0

@pytest.mark.asyncio
async def test_delete_sku_succeeds(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_reserves"]
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 204
    
    # Verify physically deleted from DB
    res = await test_db.execute(text(f"SELECT * FROM skus WHERE id = '{sku_id}'"))
    sku = res.scalar()
    assert sku is None

@pytest.mark.asyncio
async def test_delete_sku_with_active_reserves_returns_409(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_reserves"]
    
    # Set reserved_quantity > 0
    await test_db.execute(text(f"UPDATE skus SET reserved_quantity = 3 WHERE id = '{sku_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
    assert response.json()["message"] == "Cannot delete SKU with active reserves"

@pytest.mark.asyncio
@patch("src.modules.skus.service.send_moderation_event")
async def test_last_sku_on_moderation_transitions_product_to_created(mock_send_mod, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # We will use product_id_created, which is CREATED by default.
    # Let's insert a single SKU for it, and set the product's status to ON_MODERATION
    product_id = setup_data["product_id_created"]
    sku_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id}', '{product_id}', 'Temp SKU', 1000, 10, 'ART-TEMP', '[]', '[]', now(), now())"
    ))
    await test_db.execute(text(f"UPDATE products SET status = 'ON_MODERATION' WHERE id = '{product_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 204
    
    # Verify product status changed to CREATED
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{product_id}'"))
    db_status = res.scalar()
    assert db_status == "CREATED"
    
    # Verify DELETED moderation event was triggered
    mock_send_mod.assert_called_once_with(product_id, setup_data["seller_id"], "DELETED")

@pytest.mark.asyncio
async def test_delete_sku_hard_blocked_product_returns_403(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # sku_id_reserves belongs to product_id_reserves. Let's make it HARD_BLOCKED.
    product_id = setup_data["product_id_reserves"]
    sku_id = setup_data["sku_id_reserves"]
    await test_db.execute(text(f"UPDATE products SET status = 'HARD_BLOCKED' WHERE id = '{product_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Cannot delete SKU of hard-blocked product"

@pytest.mark.asyncio
@patch("src.modules.skus.service.send_b2c_sku_out_of_stock_event")
async def test_sku_out_of_stock_event_on_moderated_product(mock_send_b2c, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_reserves"]
    product_id = setup_data["product_id_reserves"]
    
    # Ensure active_quantity > 0 and product is MODERATED (it is MODERATED in setup_data)
    await test_db.execute(text(f"UPDATE skus SET active_quantity = 5 WHERE id = '{sku_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 204
    
    # Verify B2C SKU_OUT_OF_STOCK event was triggered
    mock_send_b2c.assert_called_once_with(product_id, sku_id)

@pytest.mark.asyncio
async def test_delete_sku_other_seller_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = setup_data["sku_id_other"] # Belongs to seller_id_2
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_OWNER"
    assert response.json()["message"] == "SKU does not belong to the authenticated seller"

@pytest.mark.asyncio
async def test_delete_sku_not_found_returns_404(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    sku_id = uuid.uuid4()
    
    response = await client.delete(f"/api/v1/skus/{sku_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "SKU not found"