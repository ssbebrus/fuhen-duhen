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
        f"INSERT INTO products (id, title, slug, description, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_mod}', 'P Mod', 'p-mod', 'Desc', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{product_id_blk}', 'P Blk', 'p-blk', 'Desc', 'BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{product_id_hblk}', 'P Hblk', 'p-hblk', 'Desc', 'HARD_BLOCKED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{product_id_other}', 'P Oth', 'p-oth', 'Desc', 'CREATED', '{category_id}', '{seller_id_2}', '[]', '[]', now(), now())"
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
    
    response = await client.post("/api/v1/products", json=payload, headers=headers)
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
    
    response = await client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 201
    
    product_id = response.json()["id"]
    
    # Check DB
    res = await test_db.execute(text(f"SELECT seller_id FROM products WHERE id = '{product_id}'"))
    db_seller_id = res.scalar()
    assert str(db_seller_id) == str(setup_data["seller_id"])

@pytest.mark.asyncio
async def test_missing_category_returns_422(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "images": [{"url": "http://img", "ordering": 0}]
        # missing category_id
    }
    
    response = await client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "VALIDATION_ERROR"
    assert "category_id" in data["message"]

@pytest.mark.asyncio
async def test_missing_description_returns_422(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "category_id": str(setup_data["category_id"]),
        "images": [{"url": "http://img", "ordering": 0}]
        # missing description
    }
    
    response = await client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_missing_images_returns_422(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(setup_data["category_id"])
        # missing images
    }
    
    response = await client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_invalid_category_id_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "title": "iPhone 15",
        "description": "Phone",
        "category_id": str(uuid.uuid4()), # Non-existent
        "images": [{"url": "http://img", "ordering": 0}]
    }
    
    response = await client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"

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
    assert response.json()["code"] == "FORBIDDEN"

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
    assert response.json()["code"] == "NOT_OWNER"

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

@pytest.mark.asyncio
@patch("src.modules.products.router.send_b2c_product_event")
@patch("src.modules.products.router.send_moderation_event")
async def test_delete_sets_deleted_true(mock_send_mod, mock_send_b2c, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"]
    
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 204
    
    res = await test_db.execute(text(f"SELECT deleted FROM products WHERE id = '{product_id}'"))
    is_deleted = res.scalar()
    assert is_deleted is True

@pytest.mark.asyncio
@patch("src.modules.products.router.send_b2c_product_event")
@patch("src.modules.products.router.send_moderation_event")
async def test_delete_emits_event_to_moderation(mock_send_mod, mock_send_b2c, client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_blk"]
    
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 204
    
    mock_send_mod.assert_called_once_with(product_id, setup_data["seller_id"], "DELETED")

@pytest.mark.asyncio
@patch("src.modules.products.router.send_b2c_product_event")
@patch("src.modules.products.router.send_moderation_event")
async def test_delete_emits_product_deleted_to_b2c(mock_send_mod, mock_send_b2c, client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    product_id = setup_data["product_id_mod"]
    sku_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, stock_quantity, product_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id}', 'SKU 1', 1000, 0, '{product_id}', '[]', '[]', now(), now())"
    ))
    await test_db.flush()

    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 204
    
    mock_send_b2c.assert_called_once_with(product_id, [str(sku_id)], "PRODUCT_DELETED")

@pytest.mark.asyncio
async def test_delete_already_deleted_returns_400(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"]
    
    await test_db.execute(text(f"UPDATE products SET deleted = true WHERE id = '{product_id}'"))
    await test_db.flush()
    
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"

@pytest.mark.asyncio
async def test_delete_others_product_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_other"] 
    
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_OWNER"

@pytest.mark.asyncio
async def test_deleted_product_not_in_seller_list(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"]
    
    await test_db.execute(text(f"UPDATE products SET deleted = true WHERE id = '{product_id}'"))
    await test_db.flush()
    
    response = await client.get("/api/v1/products", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    items = data["items"]
    
    product_ids = [item["id"] for item in items]
    assert str(product_id) not in product_ids
    
    response2 = await client.get("/api/v1/products?include_deleted=true", headers=headers)
    data2 = response2.json()
    product_ids2 = [item["id"] for item in data2["items"]]
    assert str(product_id) in product_ids2

@pytest.mark.asyncio
async def test_get_moderated_product_returns_full_payload(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_mod"]
    
    # Add SKU
    sku_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, stock_quantity, product_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id}', 'SKU 1', 1000, 0, '{product_id}', '[]', '[]', now(), now())"
    ))
    await test_db.flush()
    
    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "MODERATED"
    assert data["blocking_reason"] is None
    assert data["field_reports"] == []
    assert len(data["skus"]) == 1
    assert "cost_price" in data["skus"][0]
    assert data["blocked"] is False

@pytest.mark.asyncio
async def test_get_blocked_product_returns_blocking_reason_and_field_reports(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_blk"]
    
    reason_id = uuid.uuid4()
    await test_db.execute(text(
        f"UPDATE products SET blocking_reason_id = '{reason_id}', blocking_reason_title = 'Bad Title', "
        f"moderator_comment = 'Comment', "
        f"field_reports = '[{{\"field_name\": \"title\", \"sku_id\": null, \"comment\": \"Bad\"}}]' "
        f"WHERE id = '{product_id}'"
    ))
    await test_db.flush()

    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "BLOCKED"
    assert data["blocked"] is True
    assert data["blocking_reason"] is not None
    assert data["blocking_reason"]["id"] == str(reason_id)
    assert data["blocking_reason"]["title"] == "Bad Title"
    assert data["blocking_reason"]["comment"] == "Comment"
    assert "blocking_reason_id" not in data
    assert "moderator_comment" not in data
    assert len(data["field_reports"]) == 1
    assert data["field_reports"][0]["field_name"] == "title"

@pytest.mark.asyncio
async def test_get_others_product_returns_404(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_other"] 
    
    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_get_nonexistent_returns_404(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = uuid.uuid4()
    
    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_get_product_with_service_key(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    product_id = setup_data["product_id_other"]
    
    # Add an SKU to make sure we can check SKU public schema
    sku_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, cost_price, discount, stock_quantity, active_quantity, reserved_quantity, product_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id}', 'SKU 2', 2000, 1500, 100, 10, 10, 2, '{product_id}', '[]', '[]', now(), now())"
    ))
    await test_db.flush()
    
    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Ensure it's the public schema (no seller-only fields in product)
    assert "deleted" not in data
    assert "blocked" not in data
    assert "blocking_reason" not in data
    assert "field_reports" not in data
    
    # Ensure it's the public schema for SKU (no cost_price, no reserved_quantity)
    assert len(data["skus"]) == 1
    sku = data["skus"][0]
    assert "cost_price" not in sku
    assert "reserved_quantity" not in sku
    
    # Ensure general fields are still present
    assert sku["name"] == "SKU 2"
    assert sku["price"] == 2000
    assert sku["discount"] == 100
    assert sku["active_quantity"] == 10


@pytest.mark.asyncio
async def test_list_returns_only_own_products(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    # Добавим SKU для товара, чтобы проверить skus_count и total_active_quantity
    product_id = setup_data["product_id_mod"]
    sku_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, cost_price, discount, stock_quantity, active_quantity, reserved_quantity, product_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id}', 'SKU 1', 1000, 800, 0, 10, 5, 0, '{product_id}', '[]', '[]', now(), now())"
    ))
    await test_db.flush()

    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    response = await client.get("/api/v1/products", headers=headers)
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    
    # Должны быть только товары первого продавца
    product_ids = [item["id"] for item in items]
    assert str(setup_data["product_id_mod"]) in product_ids
    assert str(setup_data["product_id_blk"]) in product_ids
    assert str(setup_data["product_id_hblk"]) in product_ids
    assert str(setup_data["product_id_other"]) not in product_ids

    # Проверим skus_count и total_active_quantity для product_id_mod
    mod_item = next(item for item in items if item["id"] == str(product_id))
    assert mod_item["skus_count"] == 1
    assert mod_item["total_active_quantity"] == 5


@pytest.mark.asyncio
async def test_idor_query_param_seller_id_ignored(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    # Пытаемся передать seller_id другого продавца
    other_seller_id = setup_data["product_id_other"]
    response = await client.get(f"/api/v1/products?seller_id={other_seller_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    
    # Должны получить только СВОИ товары, но не чужие
    product_ids = [item["id"] for item in items]
    assert str(setup_data["product_id_mod"]) in product_ids
    assert str(setup_data["product_id_other"]) not in product_ids


@pytest.mark.asyncio
async def test_deleted_products_visible_with_deleted_flag(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    product_id = setup_data["product_id_mod"]
    await test_db.execute(text(f"UPDATE products SET deleted = true WHERE id = '{product_id}'"))
    await test_db.flush()

    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    # По умолчанию удаленные не видны
    response = await client.get("/api/v1/products", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert str(product_id) not in [item["id"] for item in items]

    # С флагом include_deleted=true видны
    response = await client.get("/api/v1/products?include_deleted=true", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    deleted_item = next(item for item in items if item["id"] == str(product_id))
    assert deleted_item["deleted"] is True


@pytest.mark.asyncio
async def test_status_filter_works_correctly(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    response = await client.get("/api/v1/products?status=BLOCKED", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    
    # Должен вернуться только товар со статусом BLOCKED
    for item in items:
        assert item["status"] == "BLOCKED"
    
    product_ids = [item["id"] for item in items]
    assert str(setup_data["product_id_blk"]) in product_ids
    assert str(setup_data["product_id_mod"]) not in product_ids


@pytest.mark.asyncio
async def test_search_by_title_case_insensitive(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    # Создадим пару товаров с похожими названиями
    seller_id = setup_data["seller_id"]
    category_id = setup_data["category_id"]
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, slug, description, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{p1}', 'MacBook Pro 16', 'macbook-16', 'Desc', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{p2}', 'macbook air M2', 'macbook-air', 'Desc', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))
    await test_db.flush()

    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    # Ищем по mAcBoOk
    response = await client.get("/api/v1/products?search=mAcBoOk", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    
    product_ids = [item["id"] for item in items]
    assert str(p1) in product_ids
    assert str(p2) in product_ids
    assert len(items) == 2

@pytest.mark.asyncio
async def test_delete_nonexistent_product_returns_404(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = uuid.uuid4()
    
    response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"

@pytest.mark.asyncio
async def test_get_hard_blocked_product_returns_blocking_reason_and_field_reports(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    product_id = setup_data["product_id_hblk"]
    
    reason_id = uuid.uuid4()
    await test_db.execute(text(
        f"UPDATE products SET blocking_reason_id = '{reason_id}', blocking_reason_title = 'Bad Title', "
        f"moderator_comment = 'Comment', "
        f"field_reports = '[{{\"field_name\": \"title\", \"sku_id\": null, \"comment\": \"Bad\"}}]' "
        f"WHERE id = '{product_id}'"
    ))
    await test_db.flush()

    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HARD_BLOCKED"
    assert data["blocked"] is True
    assert data["blocking_reason"] is not None
    assert data["blocking_reason"]["id"] == str(reason_id)
    assert data["blocking_reason"]["title"] == "Bad Title"
    assert data["blocking_reason"]["comment"] == "Comment"
    assert len(data["field_reports"]) == 1
    assert data["field_reports"][0]["field_name"] == "title"
