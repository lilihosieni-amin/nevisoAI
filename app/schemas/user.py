# for gemini/app/schemas/user.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    phone_number: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    university: Optional[str] = None
    field_of_study: Optional[str] = None


class UserCreate(BaseModel):
    phone_number: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    university: Optional[str] = None
    field_of_study: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    phone_number: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    university: Optional[str] = None
    field_of_study: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OTPRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20)


class OTPVerify(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20)
    otp_code: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: Optional[str] = None  # <-- **تغییر اصلی اینجاست**
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse