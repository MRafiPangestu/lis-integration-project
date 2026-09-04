from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.main_router import api_router
from app.core.config import settings

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production (M9)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "LIS API is running."}