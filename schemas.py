from pydantic import BaseModel, EmailStr
from typing import Optional, List
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
    average_rating:  Optional[float] = None  
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type:   str
    user:         UserResponse

class HireRequestCreate(BaseModel):
    provider_id:    uuid.UUID
    description:    str
    scheduled_date: str
    scheduled_time: str
    latitude:       Optional[float] = None
    longitude:      Optional[float] = None
    address:        Optional[str]   = None

class HireRequestResponse(BaseModel):
    request_id:     uuid.UUID
    client_id:      uuid.UUID
    provider_id:    uuid.UUID
    status:         str
    description:    str
    scheduled_date: str
    scheduled_time: str
    latitude:       Optional[float]
    longitude:      Optional[float]
    address:        Optional[str]
    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    notification_id: uuid.UUID
    user_id:         uuid.UUID
    hire_request_id: Optional[uuid.UUID]
    type:            str
    message:         str
    is_read:         bool
    created_at:      Optional[str] = None
    client:          Optional[UserResponse] = None
    request:         Optional[HireRequestResponse] = None
    class Config:
        from_attributes = True

class ReviewCreate(BaseModel):
    request_id: uuid.UUID
    rating:     int
    comment:    Optional[str] = None

class ReviewResponse(BaseModel):
    review_id:   uuid.UUID
    reviewer_id: uuid.UUID
    reviewed_id: uuid.UUID
    request_id:  uuid.UUID
    rating:      int
    comment:     Optional[str]
    reviewer:    Optional[UserResponse] = None
    class Config:
        from_attributes = True

class UserProfileResponse(BaseModel):
    user_id:         uuid.UUID
    name:            str
    location:        Optional[str]
    city:            Optional[str]
    category:        Optional[str]
    bio:             Optional[str]
    profile_picture: Optional[str]
    availability:    bool
    average_rating:  Optional[float]
    total_reviews:   int
    reviews:         List[ReviewResponse] = []
    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    message_id:      uuid.UUID
    conversation_id: uuid.UUID
    sender_id:       uuid.UUID
    content:         str
    is_read:         bool
    created_at:      Optional[str] = None
    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    conversation_id: uuid.UUID
    other_user:      UserResponse
    last_message:    Optional[str]     = None
    last_message_at: Optional[str]     = None
    unread_count:    int               = 0
    class Config:
        from_attributes = True