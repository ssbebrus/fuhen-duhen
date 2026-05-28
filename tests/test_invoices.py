import pytest
import uuid
import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.config import settings

@pytest.fixture
async def setup_data(test_db: AsyncSession):
    # Create seller 1
    seller_id = uuid.uuid4()
    email = f"test_{seller_id}@test.com"
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id}', '{email}', 'hash', 'T', 'T', 'C', now(), now())"
    ))

    # Create warehouse operator
    operator_id = uuid.uuid4()
    operator_email = f"operator_{operator_id}@warehouse.com"
    await test_db.execute(text(
        f"INSERT INTO warehouse_operators (id, email, hashed_password, first_name, last_name, created_at, updated_at) "
        f"VALUES ('{operator_id}', '{operator_email}', 'hash', 'O', 'P', now(), now())"
    ))
    
    # Create category
    category_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{category_id}', 'TestCat', 0, '{category_id}', true, now(), now())"
    ))

    # Create product 1 (MODERATED status)
    product_id_moderated = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_moderated}', 'P Moderated', 'MODERATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))

    # Create SKU 1 for moderated product
    sku_id_moderated = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_moderated}', '{product_id_moderated}', '256GB Black', 1000, 10, 10, 'ART-MOD', '[]', '[]', now(), now())"
    ))

    # Create SKU 2 for moderated product (for multi-item testing)
    sku_id_moderated_2 = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_moderated_2}', '{product_id_moderated}', '128GB Silver', 900, 5, 5, 'ART-MOD-2', '[]', '[]', now(), now())"
    ))

    # Create product 2 (CREATED status - non-moderated)
    product_id_created = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_created}', 'P Created', 'CREATED', '{category_id}', '{seller_id}', '[]', '[]', now(), now())"
    ))

    # Create SKU for created product
    sku_id_created = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_created}', '{product_id_created}', '256GB White', 1000, 10, 10, 'ART-CRT', '[]', '[]', now(), now())"
    ))

    # Create seller 2
    seller_id_other = uuid.uuid4()
    email_other = f"test_{seller_id_other}@test.com"
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id_other}', '{email_other}', 'hash', 'T', 'T', 'C', now(), now())"
    ))

    # Create product for seller 2 (MODERATED status)
    product_id_other_moderated = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, status, category_id, seller_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{product_id_other_moderated}', 'P Other Moderated', 'MODERATED', '{category_id}', '{seller_id_other}', '[]', '[]', now(), now())"
    ))

    # Create SKU for seller 2's moderated product
    sku_id_other_moderated = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, product_id, name, price, stock_quantity, active_quantity, article, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id_other_moderated}', '{product_id_other_moderated}', 'Other SKU', 1000, 10, 10, 'ART-OTH-MOD', '[]', '[]', now(), now())"
    ))

    await test_db.flush()
    
    seller_token = jwt.encode({"sub": str(seller_id), "role": "seller"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    operator_token = jwt.encode({"sub": str(operator_id), "role": "operator"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    yield {
        "seller_id": seller_id,
        "operator_id": operator_id,
        "token": seller_token,
        "operator_token": operator_token,
        "sku_id_moderated": sku_id_moderated,
        "sku_id_moderated_2": sku_id_moderated_2,
        "sku_id_created": sku_id_created,
        "sku_id_other_moderated": sku_id_other_moderated
    }

@pytest.mark.asyncio
async def test_create_invoice_with_moderated_sku_returns_201(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "items": [
            {
                "sku_id": str(setup_data["sku_id_moderated"]),
                "quantity": 10
            }
        ]
    }
    
    response = await client.post("/api/v1/invoices", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    
    data = response.json()
    assert "id" in data
    assert data["status"] == "CREATED"
    assert "created_at" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["sku_id"] == str(setup_data["sku_id_moderated"])
    assert data["items"][0]["sku_name"] == "256GB Black"
    assert data["items"][0]["quantity"] == 10
    assert data["items"][0]["accepted_quantity"] == 0

@pytest.mark.asyncio
async def test_empty_items_returns_422(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # 1. Empty list
    payload_empty = {
        "items": []
    }
    response = await client.post("/api/v1/invoices", json=payload_empty, headers=headers)
    assert response.status_code == 422
    
    # 2. Missing items key completely
    response = await client.post("/api/v1/invoices", json={}, headers=headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_non_moderated_sku_returns_400(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "items": [
            {
                "sku_id": str(setup_data["sku_id_created"]),
                "quantity": 10
            }
        ]
    }
    
    response = await client.post("/api/v1/invoices", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"
    assert "MODERATED" in response.json()["message"]

@pytest.mark.asyncio
async def test_others_sku_returns_403(client: AsyncClient, setup_data: dict):
    headers = {"Authorization": f"Bearer {setup_data['token']}"}
    payload = {
        "items": [
            {
                "sku_id": str(setup_data["sku_id_other_moderated"]),
                "quantity": 10
            }
        ]
    }
    
    response = await client.post("/api/v1/invoices", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_OWNER"

@pytest.mark.asyncio
async def test_accept_invoice_full_success_returns_200(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    invoice_id = create_res.json()["id"]

    # Call accept with empty body (meaning full acceptance) using operator token
    accept_res = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json={}, headers=operator_headers)
    assert accept_res.status_code == 200, accept_res.text
    
    data = accept_res.json()
    assert data["status"] == "ACCEPTED"
    assert data["accepted_by"] == str(setup_data["operator_id"])
    assert data["items"][0]["accepted_quantity"] == 10
    
    # Verify stock increased: 10 (base) + 10 (accepted) = 20
    res = await test_db.execute(text(f"SELECT active_quantity, stock_quantity FROM skus WHERE id = '{setup_data['sku_id_moderated']}'"))
    active_qty, stock_qty = res.fetchone()
    assert active_qty == 20
    assert stock_qty == 20

@pytest.mark.asyncio
async def test_accept_invoice_partial_success_returns_200(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10},
            {"sku_id": str(setup_data["sku_id_moderated_2"]), "quantity": 5}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    created_data = create_res.json()
    invoice_id = created_data["id"]
    
    item_1_id = created_data["items"][0]["id"]
    item_2_id = created_data["items"][1]["id"]

    # Partial acceptance request
    payload_accept = {
        "accepted_items": [
            {"invoice_item_id": item_1_id, "accepted_quantity": 7},
            {"invoice_item_id": item_2_id, "accepted_quantity": 0}
        ]
    }
    
    accept_res = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json=payload_accept, headers=operator_headers)
    assert accept_res.status_code == 200, accept_res.text
    
    data = accept_res.json()
    assert data["status"] == "PARTIALLY_ACCEPTED"
    assert data["accepted_by"] == str(setup_data["operator_id"])
    
    # Find items in response
    item_map = {item["id"]: item["accepted_quantity"] for item in data["items"]}
    assert item_map[item_1_id] == 7
    assert item_map[item_2_id] == 0
    
    # Verify stocks updated correctly
    res_1 = await test_db.execute(text(f"SELECT active_quantity FROM skus WHERE id = '{setup_data['sku_id_moderated']}'"))
    assert res_1.scalar() == 17 # 10 + 7
    
    res_2 = await test_db.execute(text(f"SELECT active_quantity FROM skus WHERE id = '{setup_data['sku_id_moderated_2']}'"))
    assert res_2.scalar() == 5 # 5 + 0

@pytest.mark.asyncio
async def test_accept_invoice_rejection_returns_200(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    created_data = create_res.json()
    invoice_id = created_data["id"]
    item_id = created_data["items"][0]["id"]

    # Reject fully (accepted_quantity = 0)
    payload_accept = {
        "accepted_items": [
            {"invoice_item_id": item_id, "accepted_quantity": 0}
        ]
    }
    
    accept_res = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json=payload_accept, headers=operator_headers)
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "CANCELLED"
    assert accept_res.json()["accepted_by"] == str(setup_data["operator_id"])
    
    # Verify stock unchanged
    res = await test_db.execute(text(f"SELECT active_quantity FROM skus WHERE id = '{setup_data['sku_id_moderated']}'"))
    assert res.scalar() == 10 # 10 + 0

@pytest.mark.asyncio
async def test_accept_invoice_invalid_quantities_returns_400(client: AsyncClient, setup_data: dict):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    created_data = create_res.json()
    invoice_id = created_data["id"]
    item_id = created_data["items"][0]["id"]

    # Try to accept 11 out of 10
    payload_invalid = {
        "accepted_items": [
            {"invoice_item_id": item_id, "accepted_quantity": 11}
        ]
    }
    
    accept_res = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json=payload_invalid, headers=operator_headers)
    assert accept_res.status_code == 400

@pytest.mark.asyncio
async def test_accept_invoice_already_processed_returns_409(client: AsyncClient, setup_data: dict):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    invoice_id = create_res.json()["id"]

    # Accept first time -> 200
    res_1 = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json={}, headers=operator_headers)
    assert res_1.status_code == 200
    
    # Accept second time -> 409
    res_2 = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json={}, headers=operator_headers)
    assert res_2.status_code == 409
    assert res_2.json()["code"] == "CONFLICT"

@pytest.mark.asyncio
async def test_accept_invoice_non_existent_returns_404(client: AsyncClient, setup_data: dict):
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    random_id = str(uuid.uuid4())
    res = await client.post(f"/api/v1/invoices/{random_id}/accept", json={}, headers=operator_headers)
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_accept_invoice_by_seller_returns_403(client: AsyncClient, setup_data: dict):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    invoice_id = create_res.json()["id"]

    accept_res = await client.post(f"/api/v1/invoices/{invoice_id}/accept", json={}, headers=seller_headers)
    assert accept_res.status_code == 403, f"Status: {accept_res.status_code}, Body: {accept_res.text}"
    assert accept_res.json()["code"] == "FORBIDDEN"
    assert accept_res.json()["message"] == "Only warehouse operators are authorized to perform this action"

@pytest.mark.asyncio
async def test_get_invoices_returns_200(client: AsyncClient, setup_data: dict, test_db: AsyncSession):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # Create an invoice
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    
    # Get invoices
    res = await client.get("/api/v1/invoices", headers=seller_headers)
    assert res.status_code == 200
    
    data = res.json()
    assert "items" in data
    assert "total_count" in data
    assert len(data["items"]) >= 1

@pytest.mark.asyncio
async def test_get_invoice_by_id_returns_200(client: AsyncClient, setup_data: dict):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # Create an invoice
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    invoice_id = create_res.json()["id"]
    
    # Get invoice by id
    res = await client.get(f"/api/v1/invoices/{invoice_id}", headers=seller_headers)
    assert res.status_code == 200
    
    data = res.json()
    assert data["id"] == invoice_id
    assert data["seller_id"] == str(setup_data["seller_id"])

@pytest.mark.asyncio
async def test_delete_invoice_returns_204(client: AsyncClient, setup_data: dict):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    
    # Create an invoice
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    invoice_id = create_res.json()["id"]
    
    # Delete invoice
    res = await client.delete(f"/api/v1/invoices/{invoice_id}", headers=seller_headers)
    assert res.status_code == 204
    
    # Verify it's deleted
    res_get = await client.get(f"/api/v1/invoices/{invoice_id}", headers=seller_headers)
    assert res_get.status_code == 404

@pytest.mark.asyncio
async def test_delete_invoice_already_processed_returns_409(client: AsyncClient, setup_data: dict):
    seller_headers = {"Authorization": f"Bearer {setup_data['token']}"}
    operator_headers = {"Authorization": f"Bearer {setup_data['operator_token']}"}
    
    # Create an invoice
    payload_create = {
        "items": [
            {"sku_id": str(setup_data["sku_id_moderated"]), "quantity": 10}
        ]
    }
    
    create_res = await client.post("/api/v1/invoices", json=payload_create, headers=seller_headers)
    invoice_id = create_res.json()["id"]
    
    # Accept invoice
    await client.post(f"/api/v1/invoices/{invoice_id}/accept", json={}, headers=operator_headers)
    
    # Try to delete
    res = await client.delete(f"/api/v1/invoices/{invoice_id}", headers=seller_headers)
    assert res.status_code == 409
    assert res.json()["code"] == "CONFLICT"
