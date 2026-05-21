from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import users, bio, hire, reviews, recommendations

app = FastAPI(title="HireOn API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def bypass_ngrok_warning(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

app.include_router(users.router)
app.include_router(bio.router)
app.include_router(hire.router)
app.include_router(reviews.router)
app.include_router(recommendations.router)

@app.get("/")
def root():
    return {"message": "HireOn API is running"}