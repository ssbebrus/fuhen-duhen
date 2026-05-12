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
    
    # Мы НЕ делаем commit() здесь, так как conftest.py откатит транзакцию в конце теста.
    # Но если мы хотим, чтобы данные были видны в других сессиях (хотя у нас одна), можно сделать flush.
    await test_db.flush()
    
    # Generate token
    token = jwt.encode({"sub": str(seller_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    yield {"seller_id": seller_id, "category_id": category_id, "token": token}
    
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
