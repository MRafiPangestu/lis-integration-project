from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.test_run import TestRunResponse
from app.services.test_run_service import TestRunService

router = APIRouter()

@router.get("/orders/{order_id}/test-runs", response_model=List[TestRunResponse])
def get_order_test_runs(order_id: int, db: Session = Depends(get_db)):
    """Retrieve all historical TestRuns for a specific Order along with their Results."""
    return TestRunService.get_runs_by_order(db, order_id)

@router.post("/test-runs/{run_id}/finalize", response_model=TestRunResponse)
def finalize_test_run(run_id: int, db: Session = Depends(get_db)):
    """Set a TestRun as final for clinical validation."""
    return TestRunService.finalize_run(db, run_id)

@router.post("/test-runs/{run_id}/unfinalize", response_model=TestRunResponse)
def unfinalize_test_run(run_id: int, db: Session = Depends(get_db)):
    """Unset the final state of a TestRun to allow another run to be finalized."""
    return TestRunService.unfinalize_run(db, run_id)

