from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    spotify_id: str
    name: Optional[str] = None
    is_premium: bool

class UserCreate(UserBase):
    access_token: str
    refresh_token: str
    token_expiry: datetime

class UserTokenUpdate(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None  # A veces Spotify no devuelve un nuevo refresh_token
    token_expiry: datetime

class UserResponse(UserBase):
    id: int
    registration_date: datetime

class AuthCodeRequest(BaseModel):
    code: str

#Para convertir a json 
    class Config:
        from_attributes = True