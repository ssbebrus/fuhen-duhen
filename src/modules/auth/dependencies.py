import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel
from typing import Optional

from src.db.database import get_db
from src.config import settings
from .service import AuthService
from .models import Seller, WarehouseOperator

security = HTTPBearer(auto_error=False)

# US-B2B-01 ошибка исправлена
async def get_current_seller(auth: Optional[HTTPAuthorizationCredentials] = Depends(security), db: AsyncSession = Depends(get_db)) -> Seller:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Could not validate credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if auth is None or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        seller_id: str = payload.get("sub")
        if seller_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    try:
        seller_uuid = UUID(seller_id)
    except ValueError:
        raise credentials_exception

    from sqlalchemy import select
    res = await db.execute(select(Seller).where(Seller.id == seller_uuid))
    seller = res.scalar_one_or_none()
    
    if seller is None:
        raise credentials_exception
    return seller

async def get_current_operator(auth: Optional[HTTPAuthorizationCredentials] = Depends(security), db: AsyncSession = Depends(get_db)) -> WarehouseOperator:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Could not validate credentials"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    forbidden_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Only warehouse operators are authorized to perform this action"},
    )
    if auth is None or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        operator_id: str = payload.get("sub")
        role: str = payload.get("role")
        if operator_id is None:
            raise credentials_exception
        if role != "operator":
            raise forbidden_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    try:
        operator_uuid = UUID(operator_id)
    except ValueError:
        raise credentials_exception

    from sqlalchemy import select
    res = await db.execute(select(WarehouseOperator).where(WarehouseOperator.id == operator_uuid))
    operator = res.scalar_one_or_none()
    
    if operator is None:
        raise credentials_exception
    return operator

class AuthContext(BaseModel):
    mode: str  # "seller" or "service"
    seller_id: Optional[UUID] = None

async def get_auth_context(request: Request, db: AsyncSession = Depends(get_db)) -> AuthContext:
    service_key = request.headers.get("X-Service-Key")
    if service_key:
        if service_key != settings.B2B_TO_B2C_KEY:
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid X-Service-Key"})
        return AuthContext(mode="service")

    # If no X-Service-Key, try JWT auth
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    seller = await get_current_seller(credentials, db)
    return AuthContext(mode="seller", seller_id=seller.id)
