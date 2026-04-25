from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

# ── Register ────────────────────────────────────────────────────
class UserRegister(BaseModel):
    name:         str
    email:        EmailStr
    phone_number: str
    password:     str
    location:     Optional[str] = None
    city:         Optional[str] = None
    category:     Optional[str] = None
    bio:          Optional[str] = None

# ── Login ────────────────────────────────────────────────────────
class UserLogin(BaseModel):
    identifier: str   # email OR phone number
    password:   str

# ── Response (what we send back — never includes password) ───────
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

# ── Token ────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type:   str
    user:         UserResponse