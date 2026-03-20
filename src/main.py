from fastapi import FastAPI
from src.config import settings
from src.api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    """Лёгкий эндпоинт для проверки жизнеспособности сервиса (в докере или kubernetes)"""
    return {"status": "ok"}
