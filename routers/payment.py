from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import httpx
import uuid
import os
from dotenv import load_dotenv

from database import get_db
from models import User, Subscription
from routers.users import get_current_user

load_dotenv()

CAMPAY_USERNAME = os.getenv("CAMPAY_USERNAME")
CAMPAY_PASSWORD = os.getenv("CAMPAY_PASSWORD")
CAMPAY_ENV      = os.getenv("CAMPAY_ENV", "DEV")
CAMPAY_BASE     = "https://demo.campay.net/api" if CAMPAY_ENV == "DEV" else "https://campay.net/api"

router = APIRouter(prefix="/payment", tags=["Payment"])

# ── Plans ─────────────────────────────────────────────────────────
PLANS = {
    "quarterly":   {"label": "3 Months", "duration_days": 90,  "amount": 500},
    "semi_annual": {"label": "6 Months", "duration_days": 180, "amount": 900},
    "annual":      {"label": "1 Year",   "duration_days": 365, "amount": 1500},
}

# ── Helper: strip timezone for safe subtraction ───────────────────
def naive(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to naive UTC datetime."""
    if dt is None:
        return datetime.utcnow()
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

# ── Schemas ───────────────────────────────────────────────────────
class InitiatePaymentRequest(BaseModel):
    plan:         str
    phone_number: str

class PaymentResponse(BaseModel):
    reference: str
    status:    str
    message:   Optional[str] = None

# ── Get CamPay token ──────────────────────────────────────────────
async def get_campay_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CAMPAY_BASE}/token/",
            json={"username": CAMPAY_USERNAME, "password": CAMPAY_PASSWORD},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="CamPay auth failed")
        return resp.json().get("token")


# ── POST /payment/initiate ────────────────────────────────────────
@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    body:         InitiatePaymentRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    plan = PLANS.get(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose: {list(PLANS.keys())}")

    # Check for existing active subscription
    existing = db.query(Subscription).filter(
        Subscription.user_id    == current_user.user_id,
        Subscription.status     == "active",
        Subscription.expires_at > datetime.utcnow(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"You already have an active subscription until {naive(existing.expires_at).strftime('%Y-%m-%d')}"
        )

    # Format phone number
    phone = body.phone_number.strip().replace(" ", "").replace("+", "")
    if not phone.startswith("237"):
        phone = "237" + phone

    token = await get_campay_token()

    # Send to CamPay — use 25 XAF in sandbox, real amount in production
    amount = str(plan["amount"]) if CAMPAY_ENV == "PROD" else "25"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CAMPAY_BASE}/collect/",
            json={
                "amount":             amount,
                "currency":           "XAF",
                "from":               phone,
                "description":        f"Hireon {plan['label']} subscription",
                "external_reference": str(uuid.uuid4()),
            },
            headers={
                "Authorization": f"Token {token}",
                "Content-Type":  "application/json",
            },
            timeout=30,
        )

    data = resp.json()

    if resp.status_code not in (200, 201) or data.get("status") == "FAILED":
        raise HTTPException(
            status_code=400,
            detail=data.get("message") or "Payment initiation failed"
        )

    reference = data.get("reference")
    if not reference:
        raise HTTPException(status_code=502, detail="No reference returned by CamPay")

    sub = Subscription(
        user_id       = current_user.user_id,
        plan          = body.plan,
        amount        = plan["amount"],
        duration_days = plan["duration_days"],
        phone_number  = phone,
        reference     = reference,
        status        = "pending",
        expires_at    = datetime.utcnow() + timedelta(days=plan["duration_days"]),
    )
    db.add(sub)
    db.commit()

    return {
        "reference": reference,
        "status":    data.get("status", "PENDING"),
        "message":   "Payment request sent to your phone. Please approve it.",
    }


# ── GET /payment/status/{reference} ──────────────────────────────
@router.get("/status/{reference}", response_model=PaymentResponse)
async def check_payment_status(
    reference:    str,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    sub = db.query(Subscription).filter(
        Subscription.reference == reference,
        Subscription.user_id   == current_user.user_id,
    ).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if sub.status == "active":
        return {"reference": reference, "status": "SUCCESSFUL", "message": "Subscription active"}

    token = await get_campay_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CAMPAY_BASE}/transaction/{reference}/",
            headers={"Authorization": f"Token {token}"},
            timeout=15,
        )

    data          = resp.json()
    campay_status = data.get("status", "PENDING")

    if campay_status == "SUCCESSFUL":
        sub.status     = "active"
        sub.expires_at = datetime.utcnow() + timedelta(days=sub.duration_days)
        db.commit()
    elif campay_status == "FAILED":
        sub.status = "failed"
        db.commit()

    return {
        "reference": reference,
        "status":    campay_status,
        "message":   data.get("message"),
    }


# ── GET /payment/subscription ─────────────────────────────────────
@router.get("/subscription")
def get_subscription(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    sub = db.query(Subscription).filter(
        Subscription.user_id == current_user.user_id,
        Subscription.status  == "active",
        Subscription.expires_at > datetime.utcnow(),
    ).order_by(Subscription.expires_at.desc()).first()

    if not sub:
        return {"is_active": False, "plan": None, "expires_at": None}

    plan_info   = PLANS.get(sub.plan, {})
    expires_naive = naive(sub.expires_at)

    return {
        "is_active":  True,
        "plan":       sub.plan,
        "label":      plan_info.get("label"),
        "amount":     sub.amount,
        "expires_at": expires_naive.strftime("%Y-%m-%d"),
        "days_left":  (expires_naive - datetime.utcnow()).days,
    }


# ── GET /payment/plans ────────────────────────────────────────────
@router.get("/plans")
def get_plans():
    return [
        {"key": k, "label": v["label"], "amount": v["amount"], "duration_days": v["duration_days"]}
        for k, v in PLANS.items()
    ]


# ── Subscription gate dependency ──────────────────────────────────
def require_subscription(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
) -> User:
    """Blocks the endpoint if the user has no active subscription."""
    active = db.query(Subscription).filter(
        Subscription.user_id    == current_user.user_id,
        Subscription.status     == "active",
        Subscription.expires_at > datetime.utcnow(),
    ).first()

    if not active:
        raise HTTPException(
            status_code=403,
            detail="You need an active subscription to perform this action. "
                   "Go to Profile → Subscription to subscribe."
        )
    return current_user