from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import users, bio

app = FastAPI(title="HireOn API", version="1.0.0")

# Allow React Native to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(bio.router) 

@app.get("/")
def root():
    return {"message": "HireOn API is running"}