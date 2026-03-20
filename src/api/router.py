from fastapi import APIRouter
from src.modules.products.router import router as products_router

api_router = APIRouter()
api_router.include_router(products_router)
