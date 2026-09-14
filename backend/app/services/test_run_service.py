import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models import AuditEvent, TestRun, Order, User

# M9.1b action vocabulary for this service — see
# docs/M9.1b_AUDIT_ATTRIBUTION_DESIGN.md §5. Kept as plain module constants
# (VARCHAR, no DB CHECK) rather than a new enum type, matching the schema's
# existing app-level-string-enum convention (role, delivery_status).
_ACTION_TEST_RUN_FINALIZED = "TEST_RUN_FINALIZED"
_ACTION_TEST_RUN_UNFINALIZED = "TEST_RUN_UNFINALIZED"
_ACTION_DELIVERY_STARTED = "DELIVERY_STARTED"
_ACTION_DELIVERY_DELIVERED = "DELIVERY_DELIVERED"
_ACTION_DELIVERY_FAILED = "DELIVERY_FAILED"

_ENTITY_TYPE_TEST_RUN = "TEST_RUN"

# OD-B3: M9.1b records successful, committed state transitions only — every
# row this service writes is "SUCCESS" by construction.
_OUTCOME_SUCCESS = "SUCCESS"


def _stage_test_run_audit_event(
    session: Session,
    *,
    actor: User,
    action: str,
    test_run: TestRun,
    state_before: str,
    state_after: str,
) -> None:
    """Stage one audit_events row for *test_run* in *session*, to be
    persisted by the caller's own upcoming ``session.commit()`` — never a
    separate commit (design §8.1: same transaction as the business mutation).

    ``state_before``/``state_after`` are the project's actual domain state
    representation for the field being changed (the literal ``str(bool)`` for
    ``is_final``, or the existing ``delivery_status`` string verbatim) — not
    an invented label vocabulary.
    """
    session.add(
        AuditEvent(
            id_user=actor.id_user,
            actor_username=actor.username,
            actor_role=actor.role,
            action=action,
            entity_type=_ENTITY_TYPE_TEST_RUN,
            entity_id=test_run.id_run,
            outcome=_OUTCOME_SUCCESS,
            state_before=state_before,
            state_after=state_after,
        )
    )


class TestRunService:
    @staticmethod
    def get_runs_by_order(session: Session, order_id: int) -> list[TestRun]:
        order = session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        stmt = select(TestRun).where(TestRun.id_order == order_id).order_by(TestRun.run_sequence.asc())
        return list(session.scalars(stmt).all())

    @staticmethod
    def finalize_run(session: Session, run_id: int, actor: User) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")

        if test_run.is_final:
            return test_run  # no-op — already final; no mutation, no audit row

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
            state_before = str(test_run.is_final)
            test_run.is_final = True
            state_after = str(test_run.is_final)
            _stage_test_run_audit_event(
                session,
                actor=actor,
                action=_ACTION_TEST_RUN_FINALIZED,
                test_run=test_run,
                state_before=state_before,
                state_after=state_after,
            )
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
    def unfinalize_run(session: Session, run_id: int, actor: User) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")

        if not test_run.is_final:
            return test_run  # no-op — already not final; no mutation, no audit row

        # Unfinalization blocking policy for M4.2
        if test_run.delivery_status in ['sending', 'delivered']:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot unfinalize a TestRun that is in '{test_run.delivery_status}' state."
            )

        state_before = str(test_run.is_final)
        test_run.is_final = False
        state_after = str(test_run.is_final)
        _stage_test_run_audit_event(
            session,
            actor=actor,
            action=_ACTION_TEST_RUN_UNFINALIZED,
            test_run=test_run,
            state_before=state_before,
            state_after=state_after,
        )
        session.commit()
        session.refresh(test_run)
        return test_run

    @staticmethod
    def start_delivery(session: Session, run_id: int, actor: User) -> TestRun:
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

        state_before = test_run.delivery_status
        test_run.delivery_status = 'sending'
        state_after = test_run.delivery_status
        _stage_test_run_audit_event(
            session,
            actor=actor,
            action=_ACTION_DELIVERY_STARTED,
            test_run=test_run,
            state_before=state_before,
            state_after=state_after,
        )
        session.commit()
        session.refresh(test_run)
        return test_run

    @staticmethod
    def mark_delivery_delivered(session: Session, run_id: int, actor: User) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")

        if test_run.delivery_status != 'sending':
            raise HTTPException(
                status_code=409,
                detail=f"Cannot mark as delivered from '{test_run.delivery_status}' state. Must be 'sending'."
            )

        state_before = test_run.delivery_status
        test_run.delivery_status = 'delivered'
        test_run.delivered_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) # using naïve UTC as is common in SQLA if not timezone aware, or just datetime.now()
        # Wait, how does this project handle datetime? I will use datetime.datetime.now() to be safe and let SQLA handle it.
        # Let's use datetime.datetime.utcnow() to match postgres TIMESTAMP without timezone, or just func.current_timestamp()
        # Better yet:
        test_run.delivered_at = datetime.datetime.now()
        state_after = test_run.delivery_status
        _stage_test_run_audit_event(
            session,
            actor=actor,
            action=_ACTION_DELIVERY_DELIVERED,
            test_run=test_run,
            state_before=state_before,
            state_after=state_after,
        )
        session.commit()
        session.refresh(test_run)
        return test_run

    @staticmethod
    def mark_delivery_failed(session: Session, run_id: int, actor: User) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")

        if test_run.delivery_status != 'sending':
            raise HTTPException(
                status_code=409,
                detail=f"Cannot mark as failed from '{test_run.delivery_status}' state. Must be 'sending'."
            )

        state_before = test_run.delivery_status
        test_run.delivery_status = 'failed'
        state_after = test_run.delivery_status
        _stage_test_run_audit_event(
            session,
            actor=actor,
            action=_ACTION_DELIVERY_FAILED,
            test_run=test_run,
            state_before=state_before,
            state_after=state_after,
        )
        session.commit()
        session.refresh(test_run)
        return test_run
