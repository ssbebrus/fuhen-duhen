import pytest
import uuid
import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.config import settings

@pytest.fixture
async def setup_auth_data(test_db: AsyncSession):
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
    await test_db.flush()

    token = jwt.encode({"sub": str(seller_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {
        "seller_id": seller_id,
        "category_id": category_id,
        "token": token
    }

@pytest.mark.asyncio
async def test_create_product_missing_token_returns_401(client: AsyncClient, setup_auth_data: dict):
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(setup_auth_data["category_id"]),
        "images": [{"url": "http://img", "ordering": 0}]
    }
    # No Authorization header
    response = await client.post("/api/v1/products/", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"
    assert data["message"] == "Not authenticated"

@pytest.mark.asyncio
async def test_create_product_invalid_token_returns_401(client: AsyncClient, setup_auth_data: dict):
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(setup_auth_data["category_id"]),
        "images": [{"url": "http://img", "ordering": 0}]
    }
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = await client.post("/api/v1/products/", json=payload, headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"
    assert data["message"] == "Could not validate credentials"
