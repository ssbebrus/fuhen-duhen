import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from src.core.s3 import s3_service
from src.modules.auth.dependencies import get_current_seller
from src.modules.auth.models import Seller

router = APIRouter(prefix="/images", tags=["Images"])

@router.post("/upload", summary="Загрузить изображение")
async def upload_image_legacy(file: UploadFile = File(...)):
    """Загрузить изображение в S3 и получить URL (legacy)."""
    url = await s3_service.upload_image(file)
    return {"url": url}

@router.post("", response_model_exclude_none=True, status_code=201, summary="Загрузить файл изображения")
async def upload_image(
    file: UploadFile = File(...),
    seller: Seller = Depends(get_current_seller)
):
    """Загрузить файл изображения (multipart). Возвращает url + id."""
    url = await s3_service.upload_image(file)
    return {
        "id": uuid.uuid4(),
        "url": url
    }

