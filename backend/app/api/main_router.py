from fastapi import APIRouter
from app.api.routers import test_runs

api_router = APIRouter()
api_router.include_router(test_runs.router, tags=["Test Runs"])

