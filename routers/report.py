from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid

from database import get_db
from models import User, Report
from routers.users import get_current_user

# ── Schema ────────────────────────────────────────────────────────
class ReportCreate(BaseModel):
    reported_id: uuid.UUID
    reason:      str
    details:     Optional[str] = None

router = APIRouter(prefix="/reports", tags=["Reports"])

# ── POST /reports ─────────────────────────────────────────────────
@router.post("", status_code=201)
def submit_report(
    data:         ReportCreate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    if str(data.reported_id) == str(current_user.user_id):
        raise HTTPException(status_code=400, detail="You cannot report yourself")

    reported = db.query(User).filter(User.user_id == data.reported_id).first()
    if not reported:
        raise HTTPException(status_code=404, detail="User not found")

    if not data.reason.strip():
        raise HTTPException(status_code=400, detail="Reason is required")

    report = Report(
        reporter_id = current_user.user_id,
        reported_id = data.reported_id,
        reason      = data.reason.strip(),
        details     = data.details.strip() if data.details else None,
    )
    db.add(report)
    db.commit()

    return {"message": "Report submitted. Thank you for helping keep the community safe."}