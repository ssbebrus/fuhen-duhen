import pytest
import uuid
import jwt
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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
    
    # Create seller 2
    seller_id_2 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id_2}', 'test2@test.com', 'hash', 'T', 'T', 'C', now(), now())"
    ))

    # Create products for editing tests
    product_id_mod = uuid.uuid4()
    product_id_blk = uuid.uuid4()
    product_id_hblk = uuid.uuid4()
    product_id_other = uuid.uuid4()
    
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_mod}', 'P Mod', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{product_id_blk}', 'P Blk', 'BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{product_id_hblk}', 'P Hblk', 'HARD_BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{product_id_other}', 'P Oth', 'CREATED', '{category_id}', '{seller_id_2}', '[]', '[]', now(), now())"
    ))
    
    # Мы НЕ делаем commit() здесь, так как conftest.py откатит транзакцию в конце теста.
    # Но если мы хотим, чтобы данные были видны в других сессиях (хотя у нас одна), можно сделать flush.
    await test_db.flush()
    
    # Generate token
    token = jwt.encode({"sub": str(seller_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    yield {
        "seller_id": seller_id, 
        "category_id": category_id, 
        "token": token,
        "product_id_mod": product_id_mod,
        "product_id_blk": product_id_blk,
        "product_id_hblk": product_id_hblk,
        "product_id_other": product_id_other
    }
    
    # Ручная очистка больше не нужна, так как вся транзакция откатывается.

@pytest.mark.asyncio
async def test_create_product_returns_201_with_created_status(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(setup_data["category_id"]),
        "images": [{"url": "http://img", "ordering": 0}],
        "characteristics": [{"name": "Brand", "value": "Apple"}]
    }
    
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "CREATED"
    assert data["title"] == "iPhone 15"
    assert "id" in data
    assert data["skus"] == []
    
    # Check that images and characteristics have IDs (as per spec)
    assert len(data["images"]) == 1
    assert "id" in data["images"][0]
    assert len(data["characteristics"]) == 1
    assert "id" in data["characteristics"][0]

@pytest.mark.asyncio
async def test_seller_id_taken_from_jwt(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 16",
        "description": "Phone",
        "category_id": str(setup_data["category_id"]),
        "images": [{"url": "http://img", "ordering": 0}]
    }
    
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 201
    
    product_id = response.json()["id"]
    
    # Check DB
    res = await test_db.execute(text(f"SELECT seller_id FROM products WHERE id = '{product_id}'"))
    db_seller_id = res.scalar()
    assert str(db_seller_id) == str(setup_data["seller_id"])

@pytest.mark.asyncio
async def test_missing_category_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "images": [{"url": "http://img", "ordering": 0}]
        # missing category_id
    }
    
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_missing_description_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "category_id": str(setup_data["category_id"]),
        "images": [{"url": "http://img", "ordering": 0}]
        # missing description
    }
    
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_missing_images_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(setup_data["category_id"])
        # missing images
    }
    
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_invalid_category_id_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(uuid.uuid4()), # Non-existent
        "images": [{"url": "http://img", "ordering": 0}]
    }
    
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_REQUEST"

from unittest.mock import patch

@pytest.mark.asyncio
@patch("src.modules.products.router.send_moderation_event")
async def test_edit_moderated_product_returns_to_on_moderation(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "Updated Mod",
        "description": "Phone",
        "category_id": str(setup_data["category_id"])
    }
    product_id = setup_data["product_id_mod"]
    response = await client.patch(f"/api/v1/products/{product_id}", json=payload, headers=headers)
    assert response.status_code == 200
    
    # Check DB status
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{product_id}'"))
    db_status = res.scalar()
    assert db_status == "ON_MODERATION"
    mock_send.assert_called_once_with(product_id, setup_data["seller_id"], "EDITED")

@pytest.mark.asyncio
@patch("src.modules.products.router.send_moderation_event")
async def test_edit_blocked_product_returns_to_on_moderation(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "Updated Blk",
        "description": "Phone",
        "category_id": str(setup_data["category_id"])
    }
    product_id = setup_data["product_id_blk"]
    response = await client.patch(f"/api/v1/products/{product_id}", json=payload, headers=headers)
    assert response.status_code == 200
    
    res = await test_db.execute(text(f"SELECT status FROM products WHERE id = '{product_id}'"))
    db_status = res.scalar()
    assert db_status == "ON_MODERATION"
    mock_send.assert_called_once_with(product_id, setup_data["seller_id"], "EDITED")

@pytest.mark.asyncio
async def test_edit_hard_blocked_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "Updated Hblk",
        "description": "Phone",
        "category_id": str(setup_data["category_id"])
    }
    product_id = setup_data["product_id_hblk"]
    response = await client.patch(f"/api/v1/products/{product_id}", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FORBIDDEN"

@pytest.mark.asyncio
async def test_edit_others_product_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "Updated Other",
        "description": "Phone",
        "category_id": str(setup_data["category_id"])
    }
    product_id = setup_data["product_id_other"]
    response = await client.patch(f"/api/v1/products/{product_id}", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "NOT_OWNER"

@pytest.mark.asyncio
@patch("src.modules.products.router.send_moderation_event")
async def test_add_product_image(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"] # Status is MODERATED in setup
    payload = {"url": "http://new-img.jpg", "ordering": 10}
    
    response = await client.post(f"/api/v1/products/{product_id}/images", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "http://new-img.jpg"
    assert "id" in data
    
    # Check status changed
    res = await test_db.execute(text(f"SELECT status, images FROM products WHERE id = '{product_id}'"))
    row = res.fetchone()
    assert row[0] == "ON_MODERATION"
    assert any(img["url"] == "http://new-img.jpg" for img in row[1])
    mock_send.assert_called_once()

@pytest.mark.asyncio
@patch("src.modules.products.router.send_moderation_event")
async def test_update_product_image(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"]
    
    # Add an image first
    img_id = str(uuid.uuid4())
    await test_db.execute(text(f"UPDATE products SET images = '[{{\"id\": \"{img_id}\", \"url\": \"http://old.jpg\", \"ordering\": 0}}]' WHERE id = '{product_id}'"))
    await test_db.flush()
    
    payload = {"url": "http://updated.jpg"}
    response = await client.patch(f"/api/v1/products/images/{img_id}", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["url"] == "http://updated.jpg"
    
    res = await test_db.execute(text(f"SELECT images FROM products WHERE id = '{product_id}'"))
    images = res.scalar()
    assert images[0]["url"] == "http://updated.jpg"

@pytest.mark.asyncio
@patch("src.modules.products.router.send_moderation_event")
async def test_delete_product_image(mock_send, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"]
    
    img_id = str(uuid.uuid4())
    await test_db.execute(text(f"UPDATE products SET images = '[{{\"id\": \"{img_id}\", \"url\": \"http://old.jpg\", \"ordering\": 0}}]' WHERE id = '{product_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/products/images/{img_id}", headers=headers)
    assert response.status_code == 204
    
    res = await test_db.execute(text(f"SELECT images FROM products WHERE id = '{product_id}'"))
    images = res.scalar()
    assert len(images) == 0
