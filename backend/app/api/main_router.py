from fastapi import APIRouter
from app.api.routers import test_runs, results, patients, instruments

api_router = APIRouter()
api_router.include_router(test_runs.router, tags=["Test Runs"])
api_router.include_router(results.router)
api_router.include_router(patients.router)
api_router.include_router(instruments.router)

