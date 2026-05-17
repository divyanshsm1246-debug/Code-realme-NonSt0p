import random
import string
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

def generate_social_id():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"CRN-{suffix}"

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    social_id: str = Field(default_factory=generate_social_id)
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    avatar_url: Optional[str] = None

class UserInDBBase(UserBase):
    id: Optional[int] = None
    is_active: bool = True
    is_superuser: bool = False

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str
