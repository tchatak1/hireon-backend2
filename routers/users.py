from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserRegister, UserLogin, UserResponse, Token
from auth import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

VALID_CATEGORIES = [
    'Electrician', 'Plumber', 'Mechanic', 'Carpenter',
    'Tiler', 'Painter', 'Computer repair technician', 'Photographer'
]

# ── Helper: get current logged-in user from token ────────────────
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
    # Check email already exists
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check phone already exists
    if db.query(User).filter(User.phone_number == data.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    # Validate category
    if data.category and data.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Choose from: {VALID_CATEGORIES}")

    # Create user
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
    # Find user by email or phone
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