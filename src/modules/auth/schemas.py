from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from uuid import UUID

class SellerCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    phone: Optional[str] = None

class SellerResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

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
    access_token: str
    token_type: str
    
class RefreshRequest(BaseModel):
    refresh_token: str
