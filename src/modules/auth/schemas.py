from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class SellerCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = None
    company_name: str
    phone: Optional[str] = None
    inn: str = Field(..., min_length=10, max_length=12)

class SellerResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    phone: Optional[str] = None
    inn: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SellerUpdate(BaseModel):
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    phone: Optional[str] = None

class OperatorCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class OperatorResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    user_id: UUID
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    
class RefreshRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

