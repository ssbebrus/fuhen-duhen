from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from sqlalchemy import select

from src.db.database import get_db
from src.config import settings
from .schemas import (
    SellerCreate, SellerResponse, TokenResponse,
    LoginRequest, RefreshRequest, SellerUpdate
)
from .service import AuthService
from .models import Seller, WarehouseOperator
from .dependencies import get_current_seller

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=SellerResponse, status_code=status.HTTP_201_CREATED, summary="Регистрация продавца")
async def register(seller_in: SellerCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация продавца"""
    return await AuthService.create_seller(db, seller_in)

@router.post("/login", response_model=TokenResponse, summary="Логин продавца")
async def login(login_in: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login для продавцов и операторов"""
    # 1. Try to find in Warehouse Operators
    operator = await AuthService.get_operator_by_email(db, login_in.email)
    if operator and AuthService.verify_password(login_in.password, operator.hashed_password):
        access_token_expires = timedelta(minutes=int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
        access_token = AuthService.create_access_token(
            data={"sub": str(operator.id), "role": "operator"}, expires_delta=access_token_expires
        )
        refresh_token = await AuthService.create_refresh_token(db, operator.id)
        return {
            "user_id": operator.id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
            "token_type": "Bearer"
        }

    # 2. Try to find in Sellers
    seller = await AuthService.get_seller_by_email(db, login_in.email)
    if seller and not seller.deleted and AuthService.verify_password(login_in.password, seller.hashed_password):
        access_token_expires = timedelta(minutes=int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
        access_token = AuthService.create_access_token(
            data={"sub": str(seller.id), "role": "seller"}, expires_delta=access_token_expires
        )
        refresh_token = await AuthService.create_refresh_token(db, seller.id)
        return {
            "user_id": seller.id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
            "token_type": "Bearer"
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Incorrect email or password"},
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/refresh", response_model=TokenResponse, summary="Обновление пары токенов")
async def refresh(refresh_in: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Обновление пары токенов (ротация refresh)"""
    db_token = await AuthService.verify_refresh_token(db, refresh_in.refresh_token)
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or expired refresh token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Determine role
    user_id = db_token.user_id
    role = "seller"
    
    # Check if seller exists
    res = await db.execute(select(Seller).where(Seller.id == user_id))
    seller = res.scalar_one_or_none()
    if seller:
        if seller.deleted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Account deleted"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        role = "seller"
    else:
        # Check operator
        res_op = await db.execute(select(WarehouseOperator).where(WarehouseOperator.id == user_id))
        operator = res_op.scalar_one_or_none()
        if operator:
            role = "operator"
        else:
            # We also check if it's admin role (e.g. from token role check, wait, if admin exists we can just support role)
            # If neither seller nor operator is in DB, raise 401
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "User not found"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Revoke old refresh token
    await AuthService.revoke_refresh_token(db, refresh_in.refresh_token)

    # Create new pair
    access_token_expires = timedelta(minutes=int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = AuthService.create_access_token(
        data={"sub": str(user_id), "role": role}, expires_delta=access_token_expires
    )
    new_refresh_token = await AuthService.create_refresh_token(db, user_id)

    return {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": int(settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES) * 60,
        "token_type": "Bearer"
    }

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Выход")
async def logout(logout_in: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Выход (отзыв refresh-токена)"""
    await AuthService.revoke_refresh_token(db, logout_in.refresh_token)
    return None


seller_router = APIRouter(prefix="/sellers", tags=["Seller"])

@seller_router.get("/me", response_model=SellerResponse, summary="Профиль текущего продавца")
async def get_my_profile(seller: Seller = Depends(get_current_seller)):
    """Профиль текущего продавца"""
    return seller

@seller_router.patch("/me", response_model=SellerResponse, summary="Обновить профиль")
async def update_my_profile(seller_in: SellerUpdate, db: AsyncSession = Depends(get_db), seller: Seller = Depends(get_current_seller)):
    """Обновить профиль продавца"""
    update_data = seller_in.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(seller, key, val)
    await db.commit()
    await db.refresh(seller)
    return seller

@seller_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить аккаунт продавца")
async def delete_my_profile(db: AsyncSession = Depends(get_db), seller: Seller = Depends(get_current_seller)):
    """Удалить аккаунт продавца (soft-delete)"""
    seller.deleted = True
    await db.commit()
    return None

