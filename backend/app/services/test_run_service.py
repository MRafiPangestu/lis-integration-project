import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models import TestRun, Order

class TestRunService:
    @staticmethod
    def get_runs_by_order(session: Session, order_id: int) -> list[TestRun]:
        order = session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        stmt = select(TestRun).where(TestRun.id_order == order_id).order_by(TestRun.run_sequence.asc())
        return list(session.scalars(stmt).all())

    @staticmethod
    def finalize_run(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if test_run.is_final:
            return test_run
            
        # Application-level check (for cleaner errors)
        existing_final = session.scalar(
            select(TestRun).where(
                TestRun.id_order == test_run.id_order, 
                TestRun.is_final == True
            )
        )
        if existing_final:
            raise HTTPException(
                status_code=409, 
                detail=f"Order already has a final TestRun (id_run: {existing_final.id_run}). Please unfinalize it explicitly first."
            )
            
        try:
            test_run.is_final = True
            session.commit()
            session.refresh(test_run)
            return test_run
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Database constraint violation: Another run is already final for this order."
            )

    @staticmethod
    def unfinalize_run(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if not test_run.is_final:
            return test_run
            
        # Unfinalization blocking policy for M4.2
        if test_run.delivery_status in ['sending', 'delivered']:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot unfinalize a TestRun that is in '{test_run.delivery_status}' state."
            )
            
        test_run.is_final = False
        session.commit()
        session.refresh(test_run)
        return test_run

    @staticmethod
    def start_delivery(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if not test_run.is_final:
            raise HTTPException(
                status_code=409,
                detail="Only final TestRuns can be delivered."
            )
            
        if test_run.delivery_status == 'sending':
            raise HTTPException(
                status_code=409,
                detail="Delivery is already in progress."
            )
            
        if test_run.delivery_status == 'delivered':
            raise HTTPException(
                status_code=409,
                detail="TestRun has already been delivered."
            )
            
        if test_run.delivery_status not in ['pending', 'failed']:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot start delivery from '{test_run.delivery_status}' state."
            )
            
        test_run.delivery_status = 'sending'
        session.commit()
        session.refresh(test_run)
        return test_run

    @staticmethod
    def mark_delivery_delivered(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if test_run.delivery_status != 'sending':
            raise HTTPException(
                status_code=409,
                detail=f"Cannot mark as delivered from '{test_run.delivery_status}' state. Must be 'sending'."
            )
            
        test_run.delivery_status = 'delivered'
        test_run.delivered_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) # using naïve UTC as is common in SQLA if not timezone aware, or just datetime.now()
        # Wait, how does this project handle datetime? I will use datetime.datetime.now() to be safe and let SQLA handle it.
        # Let's use datetime.datetime.utcnow() to match postgres TIMESTAMP without timezone, or just func.current_timestamp()
        # Better yet:
        test_run.delivered_at = datetime.datetime.now() 
        session.commit()
        session.refresh(test_run)
        return test_run

    @staticmethod
    def mark_delivery_failed(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if test_run.delivery_status != 'sending':
            raise HTTPException(
                status_code=409,
                detail=f"Cannot mark as failed from '{test_run.delivery_status}' state. Must be 'sending'."
            )
            
        test_run.delivery_status = 'failed'
        session.commit()
        session.refresh(test_run)
        return test_run
