from fastapi import APIRouter, UploadFile, File
from src.core.s3 import s3_service

router = APIRouter(prefix="/images", tags=["images"])

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Загрузить изображение в S3 и получить URL."""
    url = await s3_service.upload_image(file)
    return {"url": url}
