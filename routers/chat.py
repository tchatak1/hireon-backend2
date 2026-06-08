from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List
import uuid

from database import get_db
from models import User, Conversation, Message
from schemas import MessageCreate, MessageResponse, ConversationResponse, UserResponse
from routers.users import get_current_user
from routers.payment import require_subscription

router = APIRouter(prefix="/chat", tags=["Chat"])


def fmt_time(dt) -> str:
    return dt.isoformat() if dt else None


# ── Start or get existing conversation ───────────────────────────
@router.post("/conversations/{other_user_id}", response_model=ConversationResponse)
def get_or_create_conversation(
    other_user_id: uuid.UUID,
    current_user:  User    = Depends(get_current_user),
    db:            Session = Depends(get_db),
):
    if str(other_user_id) == str(current_user.user_id):
        raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself")

    other_user = db.query(User).filter(User.user_id == other_user_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")

    uid1 = min(str(current_user.user_id), str(other_user_id))
    uid2 = max(str(current_user.user_id), str(other_user_id))

    conv = db.query(Conversation).filter(
        Conversation.user1_id == uid1,
        Conversation.user2_id == uid2,
    ).first()

    if not conv:
        conv = Conversation(user1_id=uid1, user2_id=uid2)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    last_msg = db.query(Message).filter(
        Message.conversation_id == conv.conversation_id
    ).order_by(Message.created_at.desc()).first()

    unread = db.query(func.count(Message.message_id)).filter(
        Message.conversation_id == conv.conversation_id,
        Message.sender_id != current_user.user_id,
        Message.is_read == False,
    ).scalar() or 0

    return {
        "conversation_id": conv.conversation_id,
        "other_user":      _user_response(other_user, db),
        "last_message":    last_msg.content if last_msg else None,
        "last_message_at": fmt_time(conv.last_message_at),
        "unread_count":    unread,
    }


# ── List all conversations for current user ───────────────────────
@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    uid = str(current_user.user_id)
    convs = db.query(Conversation).filter(
        or_(Conversation.user1_id == uid, Conversation.user2_id == uid)
    ).order_by(Conversation.last_message_at.desc()).all()

    result = []
    for conv in convs:
        other_id = conv.user2_id if str(conv.user1_id) == uid else conv.user1_id
        other    = db.query(User).filter(User.user_id == other_id).first()
        if not other:
            continue

        last_msg = db.query(Message).filter(
            Message.conversation_id == conv.conversation_id
        ).order_by(Message.created_at.desc()).first()

        unread = db.query(func.count(Message.message_id)).filter(
            Message.conversation_id == conv.conversation_id,
            Message.sender_id != current_user.user_id,
            Message.is_read == False,
        ).scalar() or 0

        result.append({
            "conversation_id": conv.conversation_id,
            "other_user":      _user_response(other, db),
            "last_message":    last_msg.content if last_msg else None,
            "last_message_at": fmt_time(conv.last_message_at),
            "unread_count":    unread,
        })

    return result


# ── Get messages in a conversation ───────────────────────────────
@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: uuid.UUID,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    uid  = str(current_user.user_id)
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        or_(Conversation.user1_id == uid, Conversation.user2_id == uid),
    ).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.sender_id != current_user.user_id,
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    return [
        {
            "message_id":      m.message_id,
            "conversation_id": m.conversation_id,
            "sender_id":       m.sender_id,
            "content":         m.content,
            "is_read":         m.is_read,
            "created_at":      fmt_time(m.created_at),
        }
        for m in messages
    ]


# ── Send a message ────────────────────────────────────────────────
@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def send_message(
    conversation_id: uuid.UUID,
    body:            MessageCreate,
    current_user:    User    = Depends(require_subscription),
    db:              Session = Depends(get_db),
):
    uid  = str(current_user.user_id)
    conv = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        or_(Conversation.user1_id == uid, Conversation.user2_id == uid),
    ).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    msg = Message(
        conversation_id = conversation_id,
        sender_id       = current_user.user_id,
        content         = body.content.strip(),
    )
    db.add(msg)
    conv.last_message_at = msg.created_at or func.now()
    db.commit()
    db.refresh(msg)

    return {
        "message_id":      msg.message_id,
        "conversation_id": msg.conversation_id,
        "sender_id":       msg.sender_id,
        "content":         msg.content,
        "is_read":         msg.is_read,
        "created_at":      fmt_time(msg.created_at),
    }


# ── Helper ────────────────────────────────────────────────────────
def _user_response(user: User, db: Session) -> dict:
    from sqlalchemy import func as sqlfunc
    from models import Review
    avg = db.query(sqlfunc.avg(Review.rating)).filter(
        Review.reviewed_id == user.user_id
    ).scalar()
    return {
        "user_id":         user.user_id,
        "name":            user.name,
        "email":           user.email,
        "phone_number":    user.phone_number,
        "location":        user.location,
        "city":            user.city,
        "category":        user.category,
        "bio":             user.bio,
        "profile_picture": user.profile_picture,
        "availability":    user.availability,
        "average_rating":  round(float(avg), 1) if avg else None,
    }