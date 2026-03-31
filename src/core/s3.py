import uuid
import json
import aiobotocore.session
from fastapi import UploadFile
from src.config import settings

class S3Service:
    def __init__(self):
        self.session = aiobotocore.session.get_session()
        self.bucket_name = settings.MINIO_BUCKET
        self.endpoint_url = f"http://{settings.MINIO_URL}"
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY

    async def _get_client(self):
        return self.session.create_client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )

    async def ensure_bucket_exists(self):
        """Проверяет наличие бакета и создает его, если он не существует."""
        async with await self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket_name)
            except Exception:
                await client.create_bucket(Bucket=self.bucket_name)
            
            # Всегда гарантируем наличие политики публичного доступа на чтение
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicRead",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                    }
                ]
            }
            await client.put_bucket_policy(Bucket=self.bucket_name, Policy=json.dumps(policy))

    async def upload_image(self, file: UploadFile) -> str:
        """Загружает файл в S3 и возвращает путь."""
        await self.ensure_bucket_exists()
        
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"{unique_filename}"
        
        async with await self._get_client() as client:
            file_content = await file.read()
            await client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=file.content_type
            )
            
        return f"/{self.bucket_name}/{file_path}"

s3_service = S3Service()
