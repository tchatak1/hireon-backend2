from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base

class User(Base):
    __tablename__ = "users"

    user_id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(100), nullable=False)
    email           = Column(String(150), unique=True, nullable=False)
    phone_number    = Column(String(20), unique=True, nullable=False)
    password        = Column(Text, nullable=False)
    location        = Column(String(100), nullable=True)
    city            = Column(String(100), nullable=True)
    category        = Column(String(50), nullable=True)
    bio             = Column(Text, nullable=True)
    profile_picture = Column(Text, nullable=True)
    availability    = Column(Boolean, default=True)