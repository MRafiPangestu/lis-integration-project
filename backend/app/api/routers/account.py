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
    this endpoint at all (deny-by-default mount)."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    validate_password_policy(payload.new_password)

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
