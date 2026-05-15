from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db
from models import User, HireRequest, Review, Notification
from schemas import ReviewCreate, ReviewResponse, UserProfileResponse
from routers.users import get_current_user
import uuid

router = APIRouter(prefix="/reviews", tags=["Reviews"])

# ── Mark job as completed ─────────────────────────────────────────
@router.put("/complete/{request_id}")
def mark_completed(
    request_id:   uuid.UUID,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    request = db.query(HireRequest).filter(
        HireRequest.request_id == request_id,
        HireRequest.client_id  == current_user.user_id,
        HireRequest.status     == "accepted"
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found or not accepted yet")

    request.status = "completed"
    db.commit()
    db.refresh(request)

    # Notify provider
    provider = db.query(User).filter(User.user_id == request.provider_id).first()
    notification = Notification(
        user_id         = request.provider_id,
        hire_request_id = request.request_id,
        type            = "job_completed",
        message         = f"{current_user.name} marked the job as completed. Thank you!",
        is_read         = False,
    )
    db.add(notification)
    db.commit()

    return {"message": "Job marked as completed", "request_id": str(request_id)}

# ── Submit a review ───────────────────────────────────────────────
@router.post("/", response_model=ReviewResponse, status_code=201)
def submit_review(
    data:         ReviewCreate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    # Check request exists and is completed
    request = db.query(HireRequest).filter(
        HireRequest.request_id == data.request_id,
        HireRequest.client_id  == current_user.user_id,
        HireRequest.status     == "completed"
    ).first()
    if not request:
        raise HTTPException(status_code=400, detail="Job must be completed before rating")

    # Check not already reviewed
    existing = db.query(Review).filter(
        Review.reviewer_id == current_user.user_id,
        Review.request_id  == data.request_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already reviewed this job")

    # Validate rating
    if not 1 <= data.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    review = Review(
        reviewer_id = current_user.user_id,
        reviewed_id = request.provider_id,
        request_id  = data.request_id,
        rating      = data.rating,
        comment     = data.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    # Notify provider
    stars = "⭐" * data.rating
    notification = Notification(
        user_id         = request.provider_id,
        hire_request_id = request.request_id,
        type            = "new_review",
        message         = f"{current_user.name} rated you {stars} — {data.comment or 'No comment'}",
        is_read         = False,
    )
    db.add(notification)
    db.commit()

    reviewer = db.query(User).filter(User.user_id == current_user.user_id).first()
    return {
        "review_id":   review.review_id,
        "reviewer_id": review.reviewer_id,
        "reviewed_id": review.reviewed_id,
        "request_id":  review.request_id,
        "rating":      review.rating,
        "comment":     review.comment,
        "reviewer":    reviewer,
    }

# ── Get user public profile with rating ──────────────────────────
@router.get("/profile/{user_id}", response_model=UserProfileResponse)
def get_user_profile(
    user_id: uuid.UUID,
    db:      Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all reviews for this user
    reviews = db.query(Review).filter(Review.reviewed_id == user_id).all()

    # Calculate average rating
    avg = db.query(func.avg(Review.rating)).filter(
        Review.reviewed_id == user_id
    ).scalar()
    average_rating = round(float(avg), 1) if avg else None

    # Attach reviewer info to each review
    reviews_with_reviewer = []
    for r in reviews:
        reviewer = db.query(User).filter(User.user_id == r.reviewer_id).first()
        reviews_with_reviewer.append({
            "review_id":   r.review_id,
            "reviewer_id": r.reviewer_id,
            "reviewed_id": r.reviewed_id,
            "request_id":  r.request_id,
            "rating":      r.rating,
            "comment":     r.comment,
            "reviewer":    reviewer,
        })

    return {
        "user_id":        user.user_id,
        "name":           user.name,
        "location":       user.location,
        "city":           user.city,
        "category":       user.category,
        "bio":            user.bio,
        "profile_picture":user.profile_picture,
        "availability":   user.availability,
        "average_rating": average_rating,
        "total_reviews":  len(reviews),
        "reviews":        reviews_with_reviewer,
    }