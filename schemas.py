from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

class UserRegister(BaseModel):
    name:         str
    email:        EmailStr
    phone_number: str
    password:     str
    location:     Optional[str] = None
    city:         Optional[str] = None
    category:     Optional[str] = None
    bio:          Optional[str] = None

class UserLogin(BaseModel):
    identifier: str
    password:   str

class UserUpdate(BaseModel):
    name:            Optional[str]  = None
    phone_number:    Optional[str]  = None
    location:        Optional[str]  = None
    city:            Optional[str]  = None
    category:        Optional[str]  = None
    bio:             Optional[str]  = None
    profile_picture: Optional[str]  = None
    availability:    Optional[bool] = None

class UserResponse(BaseModel):
    user_id:         uuid.UUID
    name:            str
    email:           str
    phone_number:    str
    location:        Optional[str]
    city:            Optional[str]
    category:        Optional[str]
    bio:             Optional[str]
    profile_picture: Optional[str]
    availability:    bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type:   str
    user:         UserResponse