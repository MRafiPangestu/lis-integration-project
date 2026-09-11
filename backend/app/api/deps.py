"""Authentication dependency (M9.1a).

``get_current_user`` is the single point every protected route resolves
identity through. It is deliberately the only place that decides "who is
calling": role checks (``app.core.security.require_role``) are layered on
top of it, never duplicated.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import TokenError, decode_access_token
from app.models.user import User

# auto_error=False so a missing header reaches our own generic 401 (with the
# WWW-Authenticate header) instead of FastAPI's own error shape.
_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    # One generic message for every failure mode (missing / malformed /
    # expired / wrong-signature token, unknown or inactive user) — no
    # enumeration oracle (design §6.2, §17).
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the calling user from a validated Bearer token.

    Returns the ORM ``User`` row itself (not just an id) so a future M9.1b
    can read ``current_user.id_user`` at the router without a second lookup —
    see design §13. Role is intentionally not read from the token: the live
    ``is_active`` flag is checked here on every request, which is the
    revocation mechanism (§6.3) — disabling a user takes effect on its next
    request, not after the token's 8-hour expiry.
    """
    if credentials is None:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        raise _unauthorized()

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized()

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    return user
