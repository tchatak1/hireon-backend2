from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User, HireRequest, Notification
from schemas import HireRequestCreate, HireRequestResponse, NotificationResponse
from routers.users import get_current_user
import uuid

router = APIRouter(prefix="/hire", tags=["Hire Requests"])

# ── Send a hire request ───────────────────────────────────────────
@router.post("/request", response_model=HireRequestResponse, status_code=201)
def send_hire_request(
    data:         HireRequestCreate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    # Can't hire yourself
    if str(data.provider_id) == str(current_user.user_id):
        raise HTTPException(status_code=400, detail="You cannot hire yourself")

    # Check provider exists
    provider = db.query(User).filter(User.user_id == data.provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Create hire request
    hire_request = HireRequest(
        client_id      = current_user.user_id,
        provider_id    = data.provider_id,
        description    = data.description,
        scheduled_date = data.scheduled_date,
        scheduled_time = data.scheduled_time,
        latitude       = data.latitude,
        longitude      = data.longitude,
        address        = data.address,
        status         = "pending",
    )
    db.add(hire_request)
    db.commit()
    db.refresh(hire_request)

    # Build location string for notification message
    location_str = f"in {current_user.city}" if current_user.city else ""

    # Create notification for provider
    notification = Notification(
        user_id         = data.provider_id,
        hire_request_id = hire_request.request_id,
        type            = "hire_request",
        message         = f"{current_user.name} {location_str} wants to hire you for {data.scheduled_date} at {data.scheduled_time}",
        is_read         = False,
    )
    db.add(notification)
    db.commit()

    return hire_request

# ── Accept a hire request ─────────────────────────────────────────
@router.put("/request/{request_id}/accept", response_model=HireRequestResponse)
def accept_hire_request(
    request_id:   uuid.UUID,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    request = db.query(HireRequest).filter(
        HireRequest.request_id == request_id,
        HireRequest.provider_id == current_user.user_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already responded to")

    request.status = "accepted"
    db.commit()
    db.refresh(request)

    # Notify client
    notification = Notification(
        user_id         = request.client_id,
        hire_request_id = request.request_id,
        type            = "request_accepted",
        message         = f"{current_user.name} accepted your hiring request",
        is_read         = False,
    )
    db.add(notification)
    db.commit()

    return request

# ── Refuse a hire request ─────────────────────────────────────────
@router.put("/request/{request_id}/refuse", response_model=HireRequestResponse)
def refuse_hire_request(
    request_id:   uuid.UUID,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    request = db.query(HireRequest).filter(
        HireRequest.request_id == request_id,
        HireRequest.provider_id == current_user.user_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already responded to")

    request.status = "refused"
    db.commit()
    db.refresh(request)

    # Notify client
    notification = Notification(
        user_id         = request.client_id,
        hire_request_id = request.request_id,
        type            = "request_refused",
        message         = f"{current_user.name} refused your hiring request",
        is_read         = False,
    )
    db.add(notification)
    db.commit()

    return request

# ── Get my notifications ──────────────────────────────────────────
@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.user_id
    ).order_by(Notification.notification_id.desc()).all()

    result = []
    for notif in notifications:
        notif_dict = {
            "notification_id": notif.notification_id,
            "user_id":         notif.user_id,
            "hire_request_id": notif.hire_request_id,
            "type":            notif.type,
            "message":         notif.message,
            "is_read":         notif.is_read,
            "created_at":      notif.created_at.isoformat() if notif.created_at else None,
            "client":          None,
            "request":         None,
        }
        if notif.hire_request_id:
            req = db.query(HireRequest).filter(
                HireRequest.request_id == notif.hire_request_id
            ).first()
            if req:
                notif_dict["request"] = req
                # For accepted/refused: show the provider's avatar (they responded)
                # For everything else: show the client's avatar (they initiated)
                if notif.type in ("request_accepted", "request_refused"):
                    other_user = db.query(User).filter(User.user_id == req.provider_id).first()
                else:
                    other_user = db.query(User).filter(User.user_id == req.client_id).first()
                if other_user:
                    notif_dict["client"] = other_user
        result.append(notif_dict)

    return result

# ── Mark notification as read ─────────────────────────────────────
@router.put("/notifications/{notification_id}/read")
def mark_as_read(
    notification_id: uuid.UUID,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db)
):
    notif = db.query(Notification).filter(
        Notification.notification_id == notification_id,
        Notification.user_id == current_user.user_id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Marked as read"}