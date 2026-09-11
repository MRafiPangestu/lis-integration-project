"""Public authentication endpoint (M9.1a).

This router is mounted directly on the app with NO ``get_current_user``
dependency — it is the one deliberate exception to deny-by-default (design
§7.1). Every other router in this package is mounted under ``api_router``,
which does carry that dependency.
"""
import datetime
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

# OD-S5: a fixed ~1 second delay on a failed login attempt, no account
# lockout. Deliberately not a security-through-obscurity measure — it simply
# makes online brute-forcing slow without introducing a denial-of-service
# primitive against a named analyst (a lockout would).
_FAILED_LOGIN_DELAY_SECONDS = 1.0


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    started_at = time.monotonic()

    user = db.scalar(select(User).where(User.username == payload.username))
    password_ok = user is not None and verify_password(payload.password, user.password_hash)

    # Single generic failure path for "unknown username", "wrong password"
    # and "inactive user" — no enumeration oracle (design §6.2, §17).
    if not password_ok or not user.is_active:
        elapsed = time.monotonic() - started_at
        remaining = _FAILED_LOGIN_DELAY_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    user.last_login_at = datetime.datetime.now()
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id_user)
    return LoginResponse(
        access_token=token,
        user=UserPublic.model_validate(user),
    )
