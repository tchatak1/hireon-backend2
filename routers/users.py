from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserRegister, UserLogin, UserResponse, Token, UserUpdate
from auth import hash_password, verify_password, create_token, decode_token
import os
from dotenv import load_dotenv
import httpx
from typing import List
from sqlalchemy import func
from models import Review, User


load_dotenv()

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
STORAGE_BUCKET  = "profile-pictures"

VALID_CATEGORIES = [
    'Electrician', 'Plumber', 'Mechanic', 'Carpenter',
    'Tiler', 'Painter', 'Computer repair technician', 'Photographer'
]

# ── Helper: get current logged-in user from token ────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db:    Session = Depends(get_db)
):
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ── REGISTER ─────────────────────────────────────────────────────
@router.post("/register", response_model=Token, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.phone_number == data.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")
    if data.category and data.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category")

    new_user = User(
        name         = data.name,
        email        = data.email,
        phone_number = data.phone_number,
        password     = hash_password(data.password),
        location     = data.location,
        city         = data.city,
        category     = data.category,
        bio          = data.bio,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_token(str(new_user.user_id))
    return {"access_token": token, "token_type": "bearer", "user": new_user}

# ── LOGIN ─────────────────────────────────────────────────────────
@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.email == data.identifier) |
        (User.phone_number == data.identifier)
    ).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(str(user.user_id))
    return {"access_token": token, "token_type": "bearer", "user": user}

# ── GET MY PROFILE ────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# ── UPDATE MY PROFILE ─────────────────────────────────────────────
@router.put("/me", response_model=UserResponse)
def update_me(
    data:         UserUpdate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db)
):
    # Check if new phone number is taken by another user
    if data.phone_number:
        existing = db.query(User).filter(
            User.phone_number == data.phone_number,
            User.user_id != current_user.user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Phone number already in use")

    # Check category is valid
    if data.category and data.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    # Update only fields that were sent
    if data.name            is not None: current_user.name            = data.name
    if data.phone_number    is not None: current_user.phone_number    = data.phone_number
    if data.location        is not None: current_user.location        = data.location
    if data.city            is not None: current_user.city            = data.city
    if data.category        is not None: current_user.category        = data.category
    if data.bio             is not None: current_user.bio             = data.bio
    if data.profile_picture is not None: current_user.profile_picture = data.profile_picture
    if data.availability    is not None: current_user.availability    = data.availability

    db.commit()
    db.refresh(current_user)
    return current_user

# ── UPLOAD PROFILE PICTURE ────────────────────────────────────────
@router.post("/me/upload-picture", response_model=UserResponse)
async def upload_picture(
    file:         UploadFile = File(...),
    current_user: User       = Depends(get_current_user),
    db:           Session    = Depends(get_db)
):
    # Read file bytes
    contents = await file.read()

    # Build file path in Supabase storage
    file_ext  = file.filename.split(".")[-1]
    file_path = f"{current_user.user_id}.{file_ext}"

    # Upload to Supabase Storage via REST API
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{file_path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  file.content_type,
        "x-upsert":      "true",  # overwrite if exists
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(upload_url, content=contents, headers=headers)
        if response.status_code not in [200, 201]:
            raise HTTPException(status_code=500, detail="Image upload failed")

    # Build public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{file_path}"

    # Save URL to user record
    current_user.profile_picture = public_url
    db.commit()
    db.refresh(current_user)

    return current_user

# ── GET ALL USERS (for home screen) ──────────────────────────────
@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    category:     str  = None,
    city:         str  = None,
    availability: bool = None,
    db:           Session = Depends(get_db)
):
    query = db.query(User)
    if category:              query = query.filter(User.category == category)
    if city:                  query = query.filter(User.city == city)
    if availability is not None: query = query.filter(User.availability == availability)
    users = query.all()

    # Attach average rating to each user
    result = []
    for user in users:
        avg = db.query(func.avg(Review.rating)).filter(
            Review.reviewed_id == user.user_id
        ).scalar()
        user_dict = {
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
        result.append(user_dict)
    return result