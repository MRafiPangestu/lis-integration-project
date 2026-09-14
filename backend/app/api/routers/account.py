"""Self-service account endpoints (M9.1a, OD-S4).

Mounted under ``api_router`` (protected by the deny-by-default dependency) —
authentication only, no role restriction: every authenticated user may
change their own password.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import hash_password, validate_password_policy, verify_password
from app.models.audit_event import AuditEvent
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest

router = APIRouter(prefix="/account", tags=["account"])


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """OD-S4: current password required; unauthenticated callers cannot reach
    this endpoint at all (deny-by-default mount).

    M9.1b: audited as ``PASSWORD_CHANGED`` — actor and target are the same
    authenticated user. ``state_before``/``state_after`` are always NULL:
    the password value itself (plaintext or hashed) must never appear in the
    audit trail, and there is no other field of this event worth snapshotting.
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    validate_password_policy(payload.new_password)

    current_user.password_hash = hash_password(payload.new_password)
    db.add(
        AuditEvent(
            id_user=current_user.id_user,
            actor_username=current_user.username,
            actor_role=current_user.role,
            action="PASSWORD_CHANGED",
            entity_type="USER",
            entity_id=current_user.id_user,
            outcome="SUCCESS",
            state_before=None,
            state_after=None,
        )
    )
    db.commit()
