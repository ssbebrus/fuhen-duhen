from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from src.config import settings
from src.api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "Invalid request"
    if errors:
        err = errors[0]
        field = ".".join([str(loc) for loc in err["loc"] if loc != "body"])
        message = f"{field} {err['msg']}".strip()
        # Customizing some messages based on b2b.yaml requirements
        if "category_id" in field and "missing" in err['msg'].lower():
            message = "category_id is required"
        elif "title" in field and "missing" in err['msg'].lower():
            message = "title is required"
        elif "images" in field and "missing" in err['msg'].lower():
            message = "At least one image is required"
            
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_REQUEST", "message": message},
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    """Лёгкий эндпоинт для проверки жизнеспособности сервиса (в докере или kubernetes)"""
    return {"status": "ok"}
