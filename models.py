from sqlalchemy import Column, String, Boolean, Text, Float, ForeignKey, Integer, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
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

class HireRequest(Base):
    __tablename__ = "hire_requests"
    request_id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id      = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    provider_id    = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    status         = Column(String(20), default="pending")
    description    = Column(Text, nullable=False)
    scheduled_date = Column(String(20), nullable=False)
    scheduled_time = Column(String(10), nullable=False)
    latitude       = Column(Float, nullable=True)
    longitude      = Column(Float, nullable=True)
    address        = Column(String(255), nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    hire_request_id = Column(UUID(as_uuid=True), ForeignKey("hire_requests.request_id"), nullable=True)
    type            = Column(String(50), nullable=False)
    message         = Column(Text, nullable=False)
    is_read         = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint('reviewer_id', 'request_id'),)
    review_id   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    reviewed_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    request_id  = Column(UUID(as_uuid=True), ForeignKey("hire_requests.request_id"), nullable=False)
    rating      = Column(Integer, nullable=False)
    comment     = Column(Text, nullable=True)

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint('user1_id', 'user2_id'),)
    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user1_id        = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    user2_id        = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    message_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False)
    sender_id       = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    content         = Column(Text, nullable=False)
    is_read         = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())