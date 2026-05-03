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
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def test_db():
    async with AsyncSessionLocal() as session:
        yield session

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
    
    await test_db.commit()
    
    # Generate token
    token = jwt.encode({"sub": str(seller_id)}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    yield {"seller_id": seller_id, "category_id": category_id, "token": token}
    
    # Teardown - ignore errors
    try:
        await test_db.execute(text("DELETE FROM products"))
        await test_db.execute(text(f"DELETE FROM categories WHERE id = '{category_id}'"))
        await test_db.execute(text(f"DELETE FROM sellers WHERE id = '{seller_id}'"))
        await test_db.commit()
    except Exception:
        await test_db.rollback()

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
    assert response.json().get("code") == "INVALID_REQUEST" or response.json().get("detail", {}).get("code") == "INVALID_REQUEST"

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
