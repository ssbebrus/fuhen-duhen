import asyncio
from src.db.database import AsyncSessionLocal
from src.modules.auth.models import Seller, WarehouseOperator
from src.modules.auth.service import AuthService
from src.modules.categories.models import Category
from src.modules.products.models import Product, ProductStatus
from src.modules.skus.models import SKU

async def main():
    async with AsyncSessionLocal() as session:
        # Create categories
        cat1 = Category(name="Electronics")
        cat2 = Category(name="Home Appliances")
        session.add_all([cat1, cat2])
        await session.commit()

        # Create Seller (base)
        seller = Seller(
            email="base",
            hashed_password=AuthService.get_password_hash("base"),
            first_name="Base",
            last_name="User",
            company_name="Base Company",
            phone="123456789"
        )
        session.add(seller)
        await session.commit()

        # Create Operator (operator)
        operator = WarehouseOperator(
            email="operator",
            hashed_password=AuthService.get_password_hash("operator"),
            first_name="Warehouse",
            last_name="Operator"
        )
        session.add(operator)
        await session.commit()

        # Create Products
        prod1 = Product(
            title="Smartphone X",
            category_id=cat1.id,
            seller_id=seller.id,
            status=ProductStatus.MODERATED
        )
        prod2 = Product(
            title="Vacuum Cleaner Y",
            category_id=cat2.id,
            seller_id=seller.id,
            status=ProductStatus.MODERATED
        )
        session.add_all([prod1, prod2])
        await session.commit()

        # Create SKUs
        sku1 = SKU(
            name="Smartphone X - 128GB - Black",
            price=50000,
            product_id=prod1.id,
            article="SM-X-128-BLK",
            stock_quantity=100,
            active_quantity=100
        )
        sku2 = SKU(
            name="Smartphone X - 256GB - White",
            price=60000,
            product_id=prod1.id,
            article="SM-X-256-WHT",
            stock_quantity=50,
            active_quantity=50
        )
        sku3 = SKU(
            name="Vacuum Cleaner Y - Pro",
            price=15000,
            product_id=prod2.id,
            article="VC-Y-PRO",
            stock_quantity=30,
            active_quantity=30
        )
        session.add_all([sku1, sku2, sku3])
        await session.commit()

        print("Database successfully seeded with base, operator, categories, products and SKUs!")

if __name__ == "__main__":
    asyncio.run(main())
