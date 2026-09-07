from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from typing import List

from app.core.database import get_db
from app.schemas.test_run import TestRunResponse
from app.services.test_run_service import TestRunService
from app.models.test_run import TestRun
from app.models.order import Order
from app.models.visit import Visit
from app.integration.simrs_client import SimrsClient
from app.integration.simrs_payload import build_simrs_payload

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

@router.post("/test-runs/{run_id}/delivery/start", response_model=TestRunResponse)
def start_test_run_delivery(run_id: int, db: Session = Depends(get_db)):
    """Start the delivery process for a final TestRun."""
    return TestRunService.start_delivery(db, run_id)

@router.post("/test-runs/{run_id}/delivery/success", response_model=TestRunResponse)
def mark_test_run_delivery_success(run_id: int, db: Session = Depends(get_db)):
    """Mark a TestRun as successfully delivered."""
    return TestRunService.mark_delivery_delivered(db, run_id)

@router.post("/test-runs/{run_id}/delivery/fail", response_model=TestRunResponse)
def mark_test_run_delivery_fail(run_id: int, db: Session = Depends(get_db)):
    """Mark a TestRun delivery as failed."""
    return TestRunService.mark_delivery_failed(db, run_id)

@router.post("/test-runs/{run_id}/sync-simrs")
def sync_simrs(run_id: int, db: Session = Depends(get_db)):
    """Synchronize a final Test Run to SIMRS safely."""
    # Phase 1: Database Claim (Atomic)
    try:
        stmt = select(TestRun).options(
            joinedload(TestRun.order).joinedload(Order.visit).joinedload(Visit.patient),
            joinedload(TestRun.results)
        ).where(TestRun.id_run == run_id).with_for_update(nowait=True, of=TestRun)

        test_run = db.scalars(stmt).unique().first()

        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")

        if not test_run.is_final:
            raise HTTPException(status_code=409, detail="Only final TestRuns can be synchronized.")

        # Build payload while relationships are safely and eagerly loaded
        payload = build_simrs_payload(test_run)

        # Transition state and release lock (commits!)
        test_run = TestRunService.start_delivery(db, run_id)

    except OperationalError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent delivery in progress.")

    # Phase 2: External HTTP Call (No DB transaction held open)
    simrs_response = SimrsClient.send(payload)

    # Phase 3: Finalization
    if simrs_response.success:
        test_run = TestRunService.mark_delivery_delivered(db, run_id)
    else:
        test_run = TestRunService.mark_delivery_failed(db, run_id)

    return {
        "run_id": test_run.id_run,
        "delivery_status": test_run.delivery_status,
        "delivered_at": test_run.delivered_at,
        "simrs_success": simrs_response.success,
        "simrs_status_code": simrs_response.status_code,
        "simrs_error": simrs_response.error
    }
