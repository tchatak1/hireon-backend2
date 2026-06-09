from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import httpx
import os
import base64
from dotenv import load_dotenv

from database import get_db
from models import User, PortfolioPost, PortfolioImage
from routers.users import get_current_user

load_dotenv()

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
STORAGE_BUCKET  = "portfolio"

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


# ── Upload image to Supabase Storage ─────────────────────────────
async def upload_to_supabase(file: UploadFile, user_id: str, index: int) -> str:
    content   = await file.read()
    ext       = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename  = f"{user_id}/{uuid.uuid4()}.{ext}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
        f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{filename}",
        content=content,
        headers={
            "Authorization":  f"Bearer {SUPABASE_KEY}",
            "Content-Type":   file.content_type or "image/jpeg",
            "x-upsert":       "true",
        },
    )
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"Image upload failed: {resp.text}")

    return f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{filename}"


# ── POST /portfolio — create a post with up to 3 images ──────────
@router.post("")
async def create_post(
    description: Optional[str]       = Form(None),
    images:      List[UploadFile]    = File(...),
    current_user: User               = Depends(get_current_user),
    db:           Session            = Depends(get_db),
):
    if len(images) == 0:
        raise HTTPException(status_code=400, detail="At least one image is required")
    if len(images) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 images per post")

    # Validate file types
    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"}
    for img in images:
        if img.content_type not in allowed:
            raise HTTPException(status_code=400, detail=f"Only images allowed (jpg, png, webp). Got: {img.content_type}")

    # Create post
    post = PortfolioPost(
        user_id     = current_user.user_id,
        description = description,
    )
    db.add(post)
    db.flush()  # get post_id before uploading images

    # Upload each image and save
    for i, img_file in enumerate(images):
        url = await upload_to_supabase(img_file, str(current_user.user_id), i)
        db.add(PortfolioImage(
            post_id     = post.post_id,
            image_url   = url,
            order_index = i,
        ))

    db.commit()
    db.refresh(post)

    return {
        "post_id":     post.post_id,
        "description": post.description,
        "created_at":  post.created_at.isoformat() if post.created_at else None,
        "images":      [{"image_url": img.image_url, "order_index": img.order_index}
                        for img in sorted(post.images, key=lambda x: x.order_index)],
    }


# ── GET /portfolio/{user_id} — get all posts for a user ──────────
@router.get("/{user_id}")
def get_user_portfolio(
    user_id:      str,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    posts = db.query(PortfolioPost).filter(
        PortfolioPost.user_id == user_id
    ).order_by(PortfolioPost.created_at.desc()).all()

    return [
        {
            "post_id":     p.post_id,
            "description": p.description,
            "created_at":  p.created_at.isoformat() if p.created_at else None,
            "images":      [{"image_url": img.image_url, "order_index": img.order_index}
                            for img in sorted(p.images, key=lambda x: x.order_index)],
        }
        for p in posts
    ]


# ── DELETE /portfolio/{post_id} — delete a post ──────────────────
@router.delete("/{post_id}")
def delete_post(
    post_id:      uuid.UUID,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    post = db.query(PortfolioPost).filter(
        PortfolioPost.post_id == post_id,
        PortfolioPost.user_id == current_user.user_id,
    ).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found or not yours")

    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}