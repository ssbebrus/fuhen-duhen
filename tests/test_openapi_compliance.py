import pytest
import uuid
import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from src.config import settings
from src.modules.auth.models import Seller, RefreshToken
from src.modules.categories.models import Category
from src.modules.products.models import Product
from src.modules.skus.models import SKU

@pytest.fixture
async def setup_compliance_data(test_db: AsyncSession):
    # Create seller
    seller_id = uuid.uuid4()
    email = f"compliance_{seller_id}@test.com"
    hashed_password = "$bcrypt$dummy_hash" # Dummy or actual password hash
    
    # We will insert via ORM or simple SQL, let's use SQL so we control columns
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, phone, inn, deleted, created_at, updated_at) "
        f"VALUES ('{seller_id}', '{email}', 'hash', 'Test', 'User', 'TestCompany', '12345', '123456789012', false, now(), now())"
    ))
    
    # Create categories
    cat_root_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{cat_root_id}', 'RootCat', 0, '{cat_root_id}', true, now(), now())"
    ))
    
    cat_child_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO categories (id, name, level, path, is_active, created_at, updated_at) "
        f"VALUES ('{cat_child_id}', 'ChildCat', 1, '{cat_root_id}.{cat_child_id}', true, now(), now())"
    ))
    
    # Create product in child category
    product_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO products (id, title, slug, description, status, deleted, category_id, seller_id, images, characteristics, field_reports, created_at, updated_at) "
        f"VALUES ('{product_id}', 'Prod1', 'prod1', 'Desc', 'MODERATED', false, '{cat_child_id}', '{seller_id}', '[]', '[]', '[]', now(), now())"
    ))
    
    # Create SKU
    sku_id = uuid.uuid4()
    await test_db.execute(text(
        f"INSERT INTO skus (id, name, price, cost_price, discount, stock_quantity, active_quantity, reserved_quantity, article, product_id, images, characteristics, created_at, updated_at) "
        f"VALUES ('{sku_id}', 'Sku1', 100, 80, 0, 10, 10, 0, 'ART1', '{product_id}', '[]', '[]', now(), now())"
    ))

    
    # Create other seller
    other_seller_id = uuid.uuid4()
    other_email = f"other_{other_seller_id}@test.com"
    await test_db.execute(text(
        f"INSERT INTO sellers (id, email, hashed_password, first_name, last_name, company_name, phone, inn, deleted, created_at, updated_at) "
        f"VALUES ('{other_seller_id}', '{other_email}', 'hash', 'Other', 'User', 'OtherCompany', '12345', '123456789012', false, now(), now())"
    ))
    
    await test_db.commit()
    
    token = jwt.encode({"sub": str(seller_id), "role": "seller"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    other_token = jwt.encode({"sub": str(other_seller_id), "role": "seller"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    admin_token = jwt.encode({"sub": str(uuid.uuid4()), "role": "admin"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    return {
        "seller_id": seller_id,
        "email": email,
        "cat_root_id": cat_root_id,
        "cat_child_id": cat_child_id,
        "product_id": product_id,
        "sku_id": sku_id,
        "token": token,
        "other_token": other_token,
        "admin_token": admin_token
    }


@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient, test_db: AsyncSession):
    # 1. Register
    reg_payload = {
        "email": "new_seller@test.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "Seller",
        "company_name": "NewCompany",
        "inn": "770123456789"
    }
    resp = await client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == "new_seller@test.com"
    assert data["inn"] == "770123456789"
    assert "id" in data

    # 2. Login
    login_payload = {
        "email": "new_seller@test.com",
        "password": "strongpassword123"
    }
    resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert resp.status_code == 200, resp.text
    login_data = resp.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data
    assert login_data["token_type"].lower() == "bearer"
    assert login_data["user_id"] == data["id"]
    assert login_data["expires_in"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

@pytest.mark.asyncio
async def test_refresh_token_rotation_and_logout(client: AsyncClient, setup_compliance_data: dict, test_db: AsyncSession):
    # Simulate a login by generating a refresh token manually
    seller_id = setup_compliance_data["seller_id"]
    # We will create a refresh token in DB
    from datetime import datetime, timedelta, timezone
    import secrets
    r_token = secrets.token_hex(64)
    db_token = RefreshToken(
        token=r_token,
        user_id=seller_id,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
    )
    test_db.add(db_token)
    await test_db.commit()

    # Call /auth/refresh
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": r_token})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    new_r_token = data["refresh_token"]

    # Verify old token is revoked
    await test_db.refresh(db_token)
    assert db_token.revoked is True

    # Try refreshing again with the old token -> should be 401
    resp_old = await client.post("/api/v1/auth/refresh", json={"refresh_token": r_token})
    assert resp_old.status_code == 401

    # Call logout with new token
    resp_logout = await client.post("/api/v1/auth/logout", json={"refresh_token": new_r_token})
    assert resp_logout.status_code == 204

    # Verify new token is revoked
    res_new = await test_db.execute(select(RefreshToken).where(RefreshToken.token == new_r_token))
    new_db_token = res_new.scalar_one()
    assert new_db_token.revoked is True

@pytest.mark.asyncio
async def test_seller_profile_endpoints(client: AsyncClient, setup_compliance_data: dict, test_db: AsyncSession):
    headers = {"Authorization": f"Bearer {setup_compliance_data['token']}"}
    
    # 1. GET /sellers/me
    resp = await client.get("/api/v1/sellers/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "TestCompany"
    assert data["inn"] == "123456789012"

    # 2. PATCH /sellers/me
    patch_payload = {
        "company_name": "Updated Company Name",
        "phone": "99999"
    }
    resp = await client.patch("/api/v1/sellers/me", json=patch_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "Updated Company Name"
    assert data["phone"] == "99999"

    # 3. DELETE /sellers/me
    resp = await client.delete("/api/v1/sellers/me", headers=headers)
    assert resp.status_code == 204

    # 4. Verify account is soft-deleted
    seller = await test_db.get(Seller, setup_compliance_data["seller_id"])
    assert seller.deleted is True

    # 5. GET /sellers/me should now return 401
    resp = await client.get("/api/v1/sellers/me", headers=headers)
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_categories_hierarchy_and_permissions(client: AsyncClient, setup_compliance_data: dict, test_db: AsyncSession):
    # Public endpoints (no token)
    # 1. GET /categories/tree
    resp = await client.get("/api/v1/categories/tree")
    assert resp.status_code == 200
    tree = resp.json()
    # RootCat should be in the tree
    root_node = next((n for n in tree if n["id"] == str(setup_compliance_data["cat_root_id"])), None)
    assert root_node is not None
    assert root_node["name"] == "RootCat"
    assert len(root_node["children"]) == 1
    assert root_node["children"][0]["id"] == str(setup_compliance_data["cat_child_id"])

    # 2. GET /categories/{category_id}
    resp = await client.get(f"/api/v1/categories/{setup_compliance_data['cat_root_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "RootCat"
    assert "children" in data
    assert len(data["children"]) == 1
    assert data["children"][0]["id"] == str(setup_compliance_data["cat_child_id"])

    # 3. GET /categories/{category_id}/breadcrumbs
    resp = await client.get(f"/api/v1/categories/{setup_compliance_data['cat_child_id']}/breadcrumbs")
    assert resp.status_code == 200
    bc = resp.json()
    assert len(bc) == 2
    assert bc[0]["id"] == str(setup_compliance_data["cat_root_id"])
    assert bc[1]["id"] == str(setup_compliance_data["cat_child_id"])

    # Admin actions (requires admin role)
    admin_headers = {"Authorization": f"Bearer {setup_compliance_data['admin_token']}"}
    seller_headers = {"Authorization": f"Bearer {setup_compliance_data['token']}"}

    # 4. POST /categories - seller token should be 403 Forbidden
    resp = await client.post("/api/v1/categories", json={"name": "NewCat"}, headers=seller_headers)
    assert resp.status_code == 403

    # 5. POST /categories - admin token should succeed
    resp = await client.post("/api/v1/categories", json={"name": "NewCat"}, headers=admin_headers)
    assert resp.status_code == 201
    new_cat_data = resp.json()
    assert new_cat_data["name"] == "NewCat"
    new_cat_id = new_cat_data["id"]

    # 6. PATCH /categories/{category_id} - cycle check
    # Try to set root category parent to child category -> cycle!
    resp = await client.patch(
        f"/api/v1/categories/{setup_compliance_data['cat_root_id']}",
        json={"parent_id": str(setup_compliance_data["cat_child_id"])},
        headers=admin_headers
    )
    assert resp.status_code == 400
    assert "cycle" in resp.json()["message"].lower()

    # 7. DELETE /categories/{category_id} - conflict if has products
    resp = await client.delete(f"/api/v1/categories/{setup_compliance_data['cat_child_id']}", headers=admin_headers)
    assert resp.status_code == 409
    assert "products" in resp.json()["message"].lower()



@pytest.mark.asyncio
async def test_sku_endpoints_compliance(client: AsyncClient, setup_compliance_data: dict):
    headers = {"Authorization": f"Bearer {setup_compliance_data['token']}"}
    
    # 1. GET /products/{product_id}/skus
    resp = await client.get(f"/api/v1/products/{setup_compliance_data['product_id']}/skus", headers=headers)
    assert resp.status_code == 200
    skus = resp.json()
    assert len(skus) == 1
    assert skus[0]["id"] == str(setup_compliance_data["sku_id"])

    # 2. GET /skus/{sku_id}
    resp = await client.get(f"/api/v1/skus/{setup_compliance_data['sku_id']}", headers=headers)
    assert resp.status_code == 200
    sku = resp.json()
    assert sku["name"] == "Sku1"

    # 3. GET /skus/{sku_id} with another seller's token -> should be 403
    other_token = setup_compliance_data["other_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    resp = await client.get(f"/api/v1/skus/{setup_compliance_data['sku_id']}", headers=other_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_image_upload_compliance(client: AsyncClient, setup_compliance_data: dict):
    headers = {"Authorization": f"Bearer {setup_compliance_data['token']}"}
    
    # Mocking UploadFile multipart request
    files = {"file": ("test_image.png", b"fake image bytes", "image/png")}
    resp = await client.post("/api/v1/images", files=files, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data
    assert "url" in data
    # url is a string (s3 mocked or dummy url)
    assert isinstance(data["url"], str)


@pytest.mark.asyncio
async def test_new_compliance_filters(client: AsyncClient, setup_compliance_data: dict, test_db: AsyncSession):
    # 1. Test GET /categories with only_root=true
    resp = await client.get("/api/v1/categories?only_root=true")
    assert resp.status_code == 200
    categories = resp.json()
    # Check that our created root category is in the response
    root_ids = [c["id"] for c in categories]
    assert str(setup_compliance_data["cat_root_id"]) in root_ids
    # Check that all returned categories are root (level == 0)
    for cat in categories:
        assert cat["level"] == 0

    # 2. Test GET /categories with parent_id
    resp = await client.get(f"/api/v1/categories?parent_id={setup_compliance_data['cat_root_id']}")
    assert resp.status_code == 200
    categories = resp.json()
    # Check that our created child category is in the response
    child_ids = [c["id"] for c in categories]
    assert str(setup_compliance_data["cat_child_id"]) in child_ids
    # Check that all returned categories have the correct parent_id
    for cat in categories:
        assert cat["parent_id"] == str(setup_compliance_data["cat_root_id"])

    # Public headers
    public_headers = {"X-Service-Key": settings.B2B_TO_B2C_KEY}

    # 3. Test GET /public/products with seller_id
    resp = await client.get(f"/api/v1/public/products?seller_id={setup_compliance_data['seller_id']}", headers=public_headers)
    assert resp.status_code == 200, resp.text
    catalog = resp.json()
    assert catalog["total_count"] == 1
    assert catalog["items"][0]["id"] == str(setup_compliance_data["product_id"])

    # Test GET /public/products with non-existent seller_id -> 0 count
    resp = await client.get(f"/api/v1/public/products?seller_id={uuid.uuid4()}", headers=public_headers)
    assert resp.status_code == 200
    catalog = resp.json()
    assert catalog["total_count"] == 0

    # 4. Test GET /public/products with min_price / max_price
    # Sku1 price is 100 kopecks (setup_compliance_data)
    resp = await client.get("/api/v1/public/products?min_price=50&max_price=150", headers=public_headers)
    assert resp.status_code == 200
    catalog = resp.json()
    product_ids = [p["id"] for p in catalog["items"]]
    assert str(setup_compliance_data["product_id"]) in product_ids

    # Sku1 is 100 kopecks, so min_price=150 filter should exclude it
    resp = await client.get("/api/v1/public/products?min_price=150", headers=public_headers)
    assert resp.status_code == 200
    catalog = resp.json()
    product_ids = [p["id"] for p in catalog["items"]]
    assert str(setup_compliance_data["product_id"]) not in product_ids

    # 5. Test GET /public/products/{product_id}/similar schema structure
    resp = await client.get(f"/api/v1/public/products/{setup_compliance_data['product_id']}/similar", headers=public_headers)
    assert resp.status_code == 200
    similar = resp.json()
    assert isinstance(similar, list)
    for item in similar:
        assert "min_price" in item
        assert "cover_image" in item
