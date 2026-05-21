from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import math
import uuid

from database import get_db
from models import User, Review
from schemas import UserResponse
from routers.users import get_current_user

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


# ── Haversine distance formula (km between two lat/lon points) ────
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Score a provider (0.0 → 1.0) ──────────────────────────────────
def score_provider(
    provider,
    avg_rating: Optional[float],
    review_count: int,
    client_lat: Optional[float],
    client_lon: Optional[float],
) -> float:
    score = 0.0

    # ── 1. Rating score (weight: 50%) ──────────────────────────────
    # Normalize 1–5 stars → 0–1, reward more reviews with a confidence factor
    if avg_rating:
        confidence = min(review_count / 5, 1.0)   # full confidence after 5 reviews
        rating_score = ((avg_rating - 1) / 4) * confidence
    else:
        rating_score = 0.3  # no reviews yet → neutral score (not penalised)
    score += 0.50 * rating_score

    # ── 2. Availability score (weight: 30%) ────────────────────────
    availability_score = 1.0 if provider.availability else 0.0
    score += 0.30 * availability_score

    # ── 3. Distance score (weight: 20%) ────────────────────────────
    # Only applies when both client and provider have coordinates
    if (
        client_lat is not None and client_lon is not None
        and provider.latitude is not None and provider.longitude is not None
    ):
        dist_km = haversine(client_lat, client_lon, provider.latitude, provider.longitude)
        # Score drops from 1 (same spot) to 0 (100+ km away)
        distance_score = max(0.0, 1.0 - dist_km / 100.0)
        score += 0.20 * distance_score
    else:
        # No location data — split the 20% evenly so other scores still count fairly
        score += 0.10

    return round(score, 4)


# ── GET /recommendations ───────────────────────────────────────────
@router.get("", response_model=List[UserResponse])
def get_recommendations(
    category:  Optional[str]   = Query(None,  description="Filter by category"),
    lat:       Optional[float]  = Query(None,  description="Client latitude"),
    lon:       Optional[float]  = Query(None,  description="Client longitude"),
    limit:     int              = Query(10,    description="Max results to return"),
    current_user: User          = Depends(get_current_user),
    db:           Session       = Depends(get_db),
):
    # ── Determine which category to recommend ──────────────────────
    # Priority: explicit query param → client's own category → all categories
    target_category = category or current_user.category

    # ── Fetch candidate providers ──────────────────────────────────
    query = db.query(User).filter(User.user_id != current_user.user_id)
    if target_category:
        query = query.filter(User.category == target_category)
    else:
        # Only show users that have a category (actual providers)
        query = query.filter(User.category.isnot(None))

    providers = query.all()

    if not providers:
        return []

    # ── Use client's coordinates (param > stored profile) ─────────
    client_lat = lat or current_user.latitude if hasattr(current_user, 'latitude') else lat
    client_lon = lon or current_user.longitude if hasattr(current_user, 'latitude') else lon

    # ── Score every provider ───────────────────────────────────────
    scored = []
    for provider in providers:
        avg = db.query(func.avg(Review.rating)).filter(
            Review.reviewed_id == provider.user_id
        ).scalar()
        count = db.query(func.count(Review.review_id)).filter(
            Review.reviewed_id == provider.user_id
        ).scalar() or 0

        avg_rating = float(avg) if avg else None
        final_score = score_provider(provider, avg_rating, count, client_lat, client_lon)

        scored.append({
            "user":         provider,
            "avg_rating":   avg_rating,
            "score":        final_score,
        })

    # ── Sort descending by score, take top N ──────────────────────
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:limit]

    # ── Build response with average_rating attached ────────────────
    result = []
    for item in top:
        u = item["user"]
        result.append({
            "user_id":         u.user_id,
            "name":            u.name,
            "email":           u.email,
            "phone_number":    u.phone_number,
            "location":        u.location,
            "city":            u.city,
            "category":        u.category,
            "bio":             u.bio,
            "profile_picture": u.profile_picture,
            "availability":    u.availability,
            "average_rating":  round(item["avg_rating"], 1) if item["avg_rating"] else None,
        })

    return result