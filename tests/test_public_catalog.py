import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.config import settings

@pytest.fixture
async def catalog_setup(test_db: AsyncSession):
    # 1. Create seller
    seller_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, created_at, updated_at) "
        f"VALUES ('{seller_id}', 'seller_catalog@test.com', 'hash', 'Test', 'Seller', 'CatalogInc', now(), now())"
    ))
    
    # 2. Create category
    category_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{category_id}', 'CatalogCat', 0, '{category_id}', true, now(), now())"
    ))

    # 3. Create products
    p_mod_active = uuid.uuid4()      # MODERATED, deleted=false, active SKU > 0 -> Visible!
    p_mod_inactive = uuid.uuid4()    # MODERATED, deleted=false, active SKU = 0 -> Hidden!
    p_hard_blocked = uuid.uuid4()    # HARD_BLOCKED, deleted=false, active SKU > 0 -> Hidden!
    p_blocked = uuid.uuid4()         # BLOCKED, deleted=false, active SKU > 0 -> Hidden!
    p_created = uuid.uuid4()         # CREATED, deleted=false, active SKU > 0 -> Hidden!
    p_deleted = uuid.uuid4()         # MODERATED, deleted=true, active SKU > 0 -> Hidden!
    p_mod_active_2 = uuid.uuid4()    # MODERATED, deleted=false, active SKU > 0 -> Visible!

    img_id = uuid.uuid4()

    await test_db.execute(text(
        f"INSERT INTO products (id, title, slug, description, status, deleted, category_id, seller_id, images, characteristics, created_at, updated_at) VALUES "
        f"('{p_mod_active}', 'P Mod Active', 'p-mod-active', 'Desc Active', 'MODERATED', false, '{category_id}', '{seller_id}', '[{{\"id\": \"{img_id}\", \"url\": \"http://img1\", \"ordering\": 0}}]', '[{{\"id\": \"{uuid.uuid4()}\", \"name\": \"Бренд\", \"value\": \"Apple\"}}]', now(), now()), "
        f"('{p_mod_inactive}', 'P Mod Inactive', 'p-mod-inactive', 'Desc Inactive', 'MODERATED', false, '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{p_hard_blocked}', 'P Hard Blocked', 'p-hard-blocked', 'Desc HBlk', 'HARD_BLOCKED', false, '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{p_blocked}', 'P Blocked', 'p-blocked', 'Desc Blk', 'BLOCKED', false, '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{p_created}', 'P Created', 'p-created', 'Desc Created', 'CREATED', false, '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{p_deleted}', 'P Deleted', 'p-deleted', 'Desc Deleted', 'MODERATED', true, '{category_id}', '{seller_id}', '[]', '[]', now(), now()), "
        f"('{p_mod_active_2}', 'P Mod Active 2', 'p-mod-active-2', 'Desc Active 2', 'MODERATED', false, '{category_id}', '{seller_id}', '[]', '[{{\"id\": \"{uuid.uuid4()}\", \"name\": \"Бренд\", \"value\": \"Samsung\"}}]', now(), now())"
    ))

    # 4. Create SKUs
    sku_mod_active = uuid.uuid4()
    sku_mod_inactive = uuid.uuid4()
    sku_hard_blocked = uuid.uuid4()
    sku_blocked = uuid.uuid4()
    sku_created = uuid.uuid4()
    sku_deleted = uuid.uuid4()
    sku_mod_active_2 = uuid.uuid4()

    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, cost_price, discount, stock_quantity, active_quantity, reserved_quantity, product_id, images, characteristics, created_at, updated_at) VALUES "
        f"('{sku_mod_active}', 'SKU Active', 1000, 800, 100, 10, 5, 2, '{p_mod_active}', '[]', '[]', now(), now()), "
        f"('{sku_mod_inactive}', 'SKU Inactive', 2000, 1500, 0, 10, 0, 0, '{p_mod_inactive}', '[]', '[]', now(), now()), "
        f"('{sku_hard_blocked}', 'SKU Hard Blocked', 3000, 2000, 0, 10, 5, 0, '{p_hard_blocked}', '[]', '[]', now(), now()), "
        f"('{sku_blocked}', 'SKU Blocked', 4000, 3000, 0, 10, 5, 0, '{p_blocked}', '[]', '[]', now(), now()), "
        f"('{sku_created}', 'SKU Created', 5000, 4000, 0, 10, 5, 0, '{p_created}', '[]', '[]', now(), now()), "
        f"('{sku_deleted}', 'SKU Deleted', 6000, 5000, 0, 10, 5, 0, '{p_deleted}', '[]', '[]', now(), now()), "
        f"('{sku_mod_active_2}', 'SKU Active 2', 1500, 1200, 0, 10, 8, 2, '{p_mod_active_2}', '[]', '[]', now(), now())"
    ))

    await test_db.flush()

    return {
        "seller_id": seller_id,
        "category_id": category_id,
        "p_mod_active": p_mod_active,
        "p_mod_inactive": p_mod_inactive,
        "p_hard_blocked": p_hard_blocked,
        "p_blocked": p_blocked,
        "p_created": p_created,
        "p_deleted": p_deleted,
        "p_mod_active_2": p_mod_active_2,
        "sku_mod_active": sku_mod_active,
        "sku_mod_active_2": sku_mod_active_2
    }

@pytest.mark.asyncio
async def test_catalog_returns_moderated_in_stock_products(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    response = await client.get("/api/v1/public/products", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    items = data["items"]
    titles = [item["title"] for item in items]
    assert "P Mod Active" in titles
    assert "P Mod Active 2" in titles
    
    # Verify that the schema fields are correct
    for item in items:
        if item["title"] in ["P Mod Active", "P Mod Active 2"]:
            assert "min_price" in item
            assert "cover_image" in item
            assert "created_at" in item
            assert "status" in item
            assert item["status"] == "MODERATED"
            assert "deleted" not in item
            assert "cost_price" not in item

@pytest.mark.asyncio
async def test_catalog_excludes_hard_blocked(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    response = await client.get("/api/v1/public/products", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    items = data["items"]
    titles = [item["title"] for item in items]
    assert "P Hard Blocked" not in titles
    assert "P Blocked" not in titles
    assert "P Created" not in titles
    assert "P Deleted" not in titles
    assert "P Mod Inactive" not in titles

@pytest.mark.asyncio
async def test_catalog_missing_service_key_returns_401(client: AsyncClient, catalog_setup: dict):
    # No header
    response = await client.get("/api/v1/public/products")
    assert response.status_code == 401
    
    # Invalid key
    response = await client.get("/api/v1/public/products", headers={"X-Service-Key": "invalid_key"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_catalog_response_has_no_cost_price(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    # 1. Check list view
    response = await client.get("/api/v1/public/products", headers=headers)
    assert response.status_code == 200
    res_text = response.text
    assert "cost_price" not in res_text
    assert "reserved_quantity" not in res_text
    
    # 2. Check detail view of product
    response = await client.get(f"/api/v1/public/products/{catalog_setup['p_mod_active']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    res_text = response.text
    assert "cost_price" not in res_text
    assert "reserved_quantity" not in res_text
    assert "stock_quantity" in data["skus"][0]
    assert data["skus"][0]["stock_quantity"] == 10
    
    # 3. Check SKU detail view
    response = await client.get(f"/api/v1/public/skus/{catalog_setup['sku_mod_active']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    res_text = response.text
    assert "cost_price" not in res_text
    assert "reserved_quantity" not in res_text
    assert "stock_quantity" in data
    assert data["stock_quantity"] == 10

@pytest.mark.asyncio
async def test_batch_ids_returns_visible_subset(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    # Test through the GET list view batch filter ?ids=
    ids_param = f"{catalog_setup['p_mod_active']},{catalog_setup['p_mod_inactive']},{catalog_setup['p_hard_blocked']},{uuid.uuid4()}"
    response = await client.get(f"/api/v1/public/products?ids={ids_param}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    items = data["items"]
    # Only P Mod Active should be returned (P Mod Inactive is out of stock, P Hard Blocked is blocked, and uuid is non-existent)
    titles = [item["title"] for item in items]
    assert "P Mod Active" in titles
    assert "P Mod Active 2" not in titles
    assert "P Mod Inactive" not in titles
    assert "P Hard Blocked" not in titles

@pytest.mark.asyncio
async def test_catalog_similar_products(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    # Check similar products endpoint for p_mod_active
    response = await client.get(f"/api/v1/public/products/{catalog_setup['p_mod_active']}/similar", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    # Since p_mod_active and p_mod_active_2 are in the same category CatalogCat and both MODERATED/active,
    # similar products for p_mod_active should include P Mod Active 2
    titles = [item["title"] for item in data]
    assert "P Mod Active 2" in titles
    assert "P Mod Active" not in titles  # Should not include itself

@pytest.mark.asyncio
async def test_catalog_category_filters(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    response = await client.get(f"/api/v1/public/categories/{catalog_setup['category_id']}/filters", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    items = data["items"]
    assert len(items) == 2 # Price and Brand
    
    price_filter = next((i for i in items if i["slug"] == "price"), None)
    assert price_filter is not None
    assert price_filter["type"] == "range"
    assert price_filter["min"] == 1000 # p_mod_active min price
    assert price_filter["max"] == 1500 # p_mod_active_2 min price
    
    brand_filter = next((i for i in items if i["name"] == "Бренд"), None)
    assert brand_filter is not None
    assert brand_filter["slug"] == "brend"
    assert brand_filter["type"] == "list"
    assert "Apple" in brand_filter["value"]
    assert "Samsung" in brand_filter["value"]

@pytest.mark.asyncio
async def test_catalog_facets(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    # Facets without filters
    response = await client.get(f"/api/v1/public/facets?category_id={catalog_setup['category_id']}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    facets = data["facets"]
    assert len(facets) == 1
    
    brand_facet = facets[0]
    assert brand_facet["name"] == "brend"
    values = {v["value"]: v["count"] for v in brand_facet["values"]}
    assert values["Apple"] == 1
    assert values["Samsung"] == 1
    
    # Facets with filter filters[brend]=Apple
    response = await client.get(f"/api/v1/public/facets?category_id={catalog_setup['category_id']}&filters[brend]=Apple", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    brand_facet = data["facets"][0]
    values = {v["value"]: v["count"] for v in brand_facet["values"]}
    assert values.get("Apple") == 1
    assert "Samsung" not in values # because it's filtered out

@pytest.mark.asyncio
async def test_catalog_products_with_filter(client: AsyncClient, catalog_setup: dict):
    headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}
    
    response = await client.get(f"/api/v1/public/products?category_id={catalog_setup['category_id']}&filters[brend]=Apple", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    
    items = data["items"]
    assert len(items) == 1
    assert items[0]["title"] == "P Mod Active"
