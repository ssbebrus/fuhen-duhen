import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.db.database import get_db
from src.config import settings
from .service import AuthService
from .models import Seller

security = HTTPBearer()

async def get_current_seller(auth: HTTPAuthorizationCredentials = Depends(security), db: AsyncSession = Depends(get_db)) -> Seller:
    token = auth.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
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
