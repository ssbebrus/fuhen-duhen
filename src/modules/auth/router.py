from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from src.db.database import get_db
from src.config import settings
from .schemas import SellerCreate, SellerResponse, TokenResponse
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
async def register(seller_in: SellerCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация продавца"""
    return await AuthService.create_seller(db, seller_in)

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Login"""
    seller = await AuthService.get_seller_by_email(db, form_data.username)
    if not seller or not AuthService.verify_password(form_data.password, seller.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # According to settings
    access_token_expires = timedelta(minutes=int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = AuthService.create_access_token(
        data={"sub": str(seller.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
