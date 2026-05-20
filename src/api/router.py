from fastapi import APIRouter
from src.modules.products.router import router as products_router, public_router as public_router
from src.modules.categories.router import router as categories_router
from src.modules.skus.router import router as skus_router
from src.modules.images.router import router as images_router
from src.modules.auth.router import router as auth_router
from src.modules.invoices.router import router as invoices_router
from src.modules.inventory.router import router as inventory_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(products_router)
api_router.include_router(public_router)
api_router.include_router(skus_router)
api_router.include_router(images_router)
api_router.include_router(invoices_router)
api_router.include_router(inventory_router)
