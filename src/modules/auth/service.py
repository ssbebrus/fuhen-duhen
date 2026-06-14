import uuid
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from typing import Optional

from src.config import settings
from .models import Seller, WarehouseOperator, RefreshToken
from .schemas import SellerCreate, OperatorCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if expires_delta:
            expire = now_utc + expires_delta
        else:
            expire = now_utc + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    async def get_seller_by_email(db: AsyncSession, email: str) -> Optional[Seller]:
        result = await db.execute(select(Seller).where(Seller.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_seller(db: AsyncSession, seller_in: SellerCreate) -> Seller:
        existing = await AuthService.get_seller_by_email(db, seller_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
        hashed_password = AuthService.get_password_hash(seller_in.password)
        db_seller = Seller(
            email=seller_in.email,
            hashed_password=hashed_password,
            first_name=seller_in.first_name,
            last_name=seller_in.last_name,
            middle_name=seller_in.middle_name,
            company_name=seller_in.company_name,
            phone=seller_in.phone,
            inn=seller_in.inn
        )
        db.add(db_seller)
        await db.commit()
        await db.refresh(db_seller)
        return db_seller

    @staticmethod
    async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
        import secrets
        token = secrets.token_hex(64)
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
        db_token = RefreshToken(
            token=token,
            user_id=user_id,
            expires_at=expires_at
        )
        db.add(db_token)
        await db.commit()
        return token

    @staticmethod
    async def verify_refresh_token(db: AsyncSession, token: str) -> Optional[RefreshToken]:
        result = await db.execute(select(RefreshToken).where(RefreshToken.token == token, RefreshToken.revoked == False))
        db_token = result.scalar_one_or_none()
        if db_token and db_token.expires_at > datetime.now(timezone.utc).replace(tzinfo=None):
            return db_token
        return None

    @staticmethod
    async def revoke_refresh_token(db: AsyncSession, token: str) -> bool:
        result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
        db_token = result.scalar_one_or_none()
        if db_token:
            db_token.revoked = True
            await db.commit()
            return True
        return False


    @staticmethod
    async def get_operator_by_email(db: AsyncSession, email: str) -> Optional[WarehouseOperator]:
        result = await db.execute(select(WarehouseOperator).where(WarehouseOperator.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_operator(db: AsyncSession, operator_in: OperatorCreate) -> WarehouseOperator:
        existing = await AuthService.get_operator_by_email(db, operator_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
        hashed_password = AuthService.get_password_hash(operator_in.password)
        db_operator = WarehouseOperator(
            email=operator_in.email,
            hashed_password=hashed_password,
            first_name=operator_in.first_name,
            last_name=operator_in.last_name
        )
        db.add(db_operator)
        await db.commit()
        await db.refresh(db_operator)
        return db_operator
