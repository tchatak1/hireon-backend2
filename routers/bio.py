from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.users import get_current_user
from google import genai
import PyPDF2
import io
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter(prefix="/bio", tags=["Bio Generation"])

@router.post("/generate")
async def generate_bio(
    file:         UploadFile       = File(...),
    current_user: User             = Depends(get_current_user),
    db:           Session          = Depends(get_db)
):
    # ── Validate file type ────────────────────────────────────────
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # ── Read and extract text from PDF ────────────────────────────
    contents = await file.read()
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(contents))
        cv_text = ""
        for page in pdf_reader.pages:
            cv_text += page.extract_text() or ""
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the PDF file")

    if not cv_text.strip():
        raise HTTPException(status_code=400, detail="PDF appears to be empty or unreadable")

    # ── Call Gemini to generate bio ───────────────────────────────
    try:
        prompt = f"""
You are a professional profile writer for a service hiring platform called HireOn.

Based on the CV below, write a short, natural, and professional bio for this person.

Rules:
- Maximum 3 sentences
- Written in first person (I am...)
- Focus on their skill, experience, and location if mentioned
- Sound human and approachable, not robotic
- Do not include personal contact details
- If the CV mentions a specific trade skill (electrician, plumber, painter, mechanic etc), highlight it

CV:
{cv_text}

Return ONLY the bio text, nothing else.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        bio = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    return { "bio": bio }