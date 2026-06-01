import asyncio
from sqlalchemy import text
from src.db.database import AsyncSessionLocal
from src.modules.auth.service import AuthService
from src.modules.auth.schemas import SellerCreate, OperatorCreate
from src.modules.categories.service import CategoryService
from src.modules.categories.schemas import CategoryCreate
from src.modules.products.service import ProductService
from src.modules.products.schemas import ProductCreate
from src.modules.products.models import ProductStatus
from src.modules.skus.service import SKUService
from src.modules.skus.schemas import SKUCreate

async def main():
    async with AsyncSessionLocal() as session:
        # Clean up database tables before seeding to prevent conflicts and clear old dirty data
        await session.execute(text(
            "TRUNCATE TABLE categories, products, skus, sellers, "
            "warehouse_operators, invoices, invoice_items, "
            "reserve_operations, processed_events CASCADE;"
        ))
        await session.commit()

        # 1. Create Seller (base) via AuthService
        seller_in = SellerCreate(
            email="base@example.com",
            password="base",
            first_name="Base",
            last_name="User",
            company_name="Base Company",
            phone="123456789"
        )
        seller = await AuthService.create_seller(session, seller_in)

        # 2. Create Operator (operator) via AuthService
        operator_in = OperatorCreate(
            email="operator@example.com",
            password="operator",
            first_name="Warehouse",
            last_name="Operator"
        )
        operator = await AuthService.create_operator(session, operator_in)

        # 3. Create Root Categories
        cat_elec = await CategoryService.create(session, CategoryCreate(name="Electronics"))
        cat_home = await CategoryService.create(session, CategoryCreate(name="Home & Kitchen"))

        # 4. Create Level 1 Subcategories under Electronics
        cat_comp = await CategoryService.create(session, CategoryCreate(
            name="Computers & Laptops",
            parent_id=cat_elec.id
        ))
        cat_smart = await CategoryService.create(session, CategoryCreate(
            name="Smartphones & Gadgets",
            parent_id=cat_elec.id
        ))

        # 5. Create Level 2 Subcategory under Smartphones & Gadgets
        cat_watch = await CategoryService.create(session, CategoryCreate(
            name="Smartwatches & Trackers",
            parent_id=cat_smart.id
        ))

        # 6. Create Products at different levels
        # Root Electronics
        prod_gen_elec_in = ProductCreate(
            title="Generic Electronic Component Kit",
            description="A comprehensive kit of electronics components for hobbyists and students.",
            category_id=cat_elec.id,
            images=[{"url": "https://example.com/images/elec-kit.jpg", "ordering": 0}],
            characteristics=[
                {"name": "Type", "value": "DIY Kit"},
                {"name": "Difficulty", "value": "Beginner"}
            ]
        )
        prod_gen_elec = await ProductService.create(session, prod_gen_elec_in, seller_id=seller.id)
        prod_gen_elec.status = ProductStatus.MODERATED

        # Level 1 Computers & Laptops
        prod_laptop_in = ProductCreate(
            title="Developer Laptop Pro",
            description="High-performance laptop designed for software development and creative professionals.",
            category_id=cat_comp.id,
            images=[{"url": "https://example.com/images/laptop-pro.jpg", "ordering": 0}],
            characteristics=[
                {"name": "Brand", "value": "TechBrand"},
                {"name": "CPU", "value": "Intel i7"},
                {"name": "RAM", "value": "16GB"}
            ]
        )
        prod_laptop = await ProductService.create(session, prod_laptop_in, seller_id=seller.id)
        prod_laptop.status = ProductStatus.MODERATED

        # Level 1 Smartphones & Gadgets
        prod_phone_in = ProductCreate(
            title="Smartphone X",
            description="Flagship smartphone featuring state of the art triple camera and immersive display.",
            category_id=cat_smart.id,
            images=[{"url": "https://example.com/images/smartphone-x.jpg", "ordering": 0}],
            characteristics=[
                {"name": "Brand", "value": "Apple"},
                {"name": "OS", "value": "iOS"},
                {"name": "Color", "value": "Black"}
            ]
        )
        prod_phone = await ProductService.create(session, prod_phone_in, seller_id=seller.id)
        prod_phone.status = ProductStatus.MODERATED

        # Level 2 Smartwatches & Trackers
        prod_watch_in = ProductCreate(
            title="Active Fitness Smartwatch",
            description="Waterproof smartwatch with built-in GPS and heart rate monitoring.",
            category_id=cat_watch.id,
            images=[{"url": "https://example.com/images/smartwatch.jpg", "ordering": 0}],
            characteristics=[
                {"name": "Brand", "value": "FitnessCo"},
                {"name": "Waterproof", "value": "Yes"},
                {"name": "Heart Rate", "value": "Yes"}
            ]
        )
        prod_watch = await ProductService.create(session, prod_watch_in, seller_id=seller.id)
        prod_watch.status = ProductStatus.MODERATED

        # Root Home & Kitchen
        prod_vacuum_in = ProductCreate(
            title="Vacuum Cleaner Y",
            description="Powerful cordless vacuum cleaner with multi-surface brush roll.",
            category_id=cat_home.id,
            images=[{"url": "https://example.com/images/vacuum-y.jpg", "ordering": 0}],
            characteristics=[
                {"name": "Brand", "value": "CleanCo"},
                {"name": "Type", "value": "Cordless"},
                {"name": "Power", "value": "250W"}
            ]
        )
        prod_vacuum = await ProductService.create(session, prod_vacuum_in, seller_id=seller.id)
        prod_vacuum.status = ProductStatus.MODERATED

        await session.commit()

        # 7. Create SKUs for each Product
        # Generic Electronic Kit SKUs
        sku_kit1_in = SKUCreate(
            product_id=prod_gen_elec.id,
            name="Basic Component Kit",
            price=1500,
            cost_price=1000,
            stock_quantity=50,
            article="EL-KIT-BAS"
        )
        sku_kit1, _, _ = await SKUService.create(session, sku_kit1_in, seller_id=seller.id)
        sku_kit1.active_quantity = 50

        sku_kit2_in = SKUCreate(
            product_id=prod_gen_elec.id,
            name="Advanced Component Kit",
            price=3500,
            cost_price=2500,
            stock_quantity=25,
            article="EL-KIT-ADV"
        )
        sku_kit2, _, _ = await SKUService.create(session, sku_kit2_in, seller_id=seller.id)
        sku_kit2.active_quantity = 25

        # Laptop SKUs
        sku_lap1_in = SKUCreate(
            product_id=prod_laptop.id,
            name="Developer Laptop Pro - 16GB RAM",
            price=120000,
            cost_price=90000,
            stock_quantity=10,
            article="LP-PRO-16"
        )
        sku_lap1, _, _ = await SKUService.create(session, sku_lap1_in, seller_id=seller.id)
        sku_lap1.active_quantity = 10

        sku_lap2_in = SKUCreate(
            product_id=prod_laptop.id,
            name="Developer Laptop Pro - 32GB RAM",
            price=150000,
            cost_price=110000,
            stock_quantity=5,
            article="LP-PRO-32"
        )
        sku_lap2, _, _ = await SKUService.create(session, sku_lap2_in, seller_id=seller.id)
        sku_lap2.active_quantity = 5

        # Smartphone SKUs
        sku_phone1_in = SKUCreate(
            product_id=prod_phone.id,
            name="Smartphone X - 128GB - Black",
            price=50000,
            cost_price=40000,
            stock_quantity=100,
            article="SM-X-128-BLK"
        )
        sku_phone1, _, _ = await SKUService.create(session, sku_phone1_in, seller_id=seller.id)
        sku_phone1.active_quantity = 100

        sku_phone2_in = SKUCreate(
            product_id=prod_phone.id,
            name="Smartphone X - 256GB - White",
            price=60000,
            cost_price=48000,
            stock_quantity=50,
            article="SM-X-256-WHT"
        )
        sku_phone2, _, _ = await SKUService.create(session, sku_phone2_in, seller_id=seller.id)
        sku_phone2.active_quantity = 50

        # Smartwatch SKUs
        sku_watch1_in = SKUCreate(
            product_id=prod_watch.id,
            name="Active Fitness Smartwatch - Black",
            price=12000,
            cost_price=8000,
            stock_quantity=40,
            article="SW-FIT-BLK"
        )
        sku_watch1, _, _ = await SKUService.create(session, sku_watch1_in, seller_id=seller.id)
        sku_watch1.active_quantity = 40

        sku_watch2_in = SKUCreate(
            product_id=prod_watch.id,
            name="Active Fitness Smartwatch - Red",
            price=12500,
            cost_price=8200,
            stock_quantity=20,
            article="SW-FIT-RED"
        )
        sku_watch2, _, _ = await SKUService.create(session, sku_watch2_in, seller_id=seller.id)
        sku_watch2.active_quantity = 20

        # Vacuum Cleaner SKUs
        sku_vac1_in = SKUCreate(
            product_id=prod_vacuum.id,
            name="Vacuum Cleaner Y - Pro",
            price=15000,
            cost_price=12000,
            stock_quantity=30,
            article="VC-Y-PRO"
        )
        sku_vac1, _, _ = await SKUService.create(session, sku_vac1_in, seller_id=seller.id)
        sku_vac1.active_quantity = 30

        await session.commit()

        print("Database successfully seeded with base, operator, rich nested categories, products (with characteristics) and SKUs!")

if __name__ == "__main__":
    asyncio.run(main())
