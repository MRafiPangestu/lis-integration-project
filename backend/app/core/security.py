"""Password hashing, JWT issuance/validation, and role model (M9.1a).

Pure and database-free except where noted. Owner-approved parameters
(``docs/M9.1a_SECURITY_FOUNDATION_DESIGN.md``, Governance Update):

* Password storage: Argon2id via ``argon2-cffi`` (OD-4 §8.1).
* Tokens: JWT, HS256, 8-hour lifetime, no refresh token (OD-S1).
* Role is never trusted from the token — ``get_current_user``
  (``app/api/deps.py``) resolves it from the live ``User`` row on every
  request (OD-S1 / design §6.3). This module only issues/validates the token
  and exposes the role enum + role-check dependency factory.
"""
from __future__ import annotations

import datetime
from enum import Enum
from typing import Callable

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
from fastapi import Depends, HTTPException, status

from app.core.config import settings

# --- Roles (OD-1 = B) --------------------------------------------------------


class Role(str, Enum):
    """ADMIN inherits every ANALYST capability plus user management (OD-1=B).

    There is no endpoint, in any role, that modifies a clinical value — that
    is an architectural guarantee, not an RBAC rule (design doc §5.3).
    """

    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


# Minimum password length (design §8.3 — length over composition rules).
MIN_PASSWORD_LENGTH = 12


def validate_password_policy(password: str) -> None:
    """Raise ``HTTPException(422)`` if *password* does not meet the minimum
    policy. Deliberately length-only — no composition/rotation rules
    (design §8.3: "modern guidance favours length over composition")."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.",
        )


# --- Password hashing (Argon2id) --------------------------------------------

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash *password* with Argon2id. Never log the input or the result."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-effort verification. Any hashing failure (wrong password,
    corrupt/foreign hash format) returns ``False`` rather than raising —
    callers must not distinguish these cases in their response."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


# --- JWT issuance / validation ------------------------------------------------

# Claims are deliberately minimal: subject, issued-at, expiry — nothing else.
# In particular, no ``role`` claim: authorization always re-reads the live
# ``User`` row (see app/api/deps.py:get_current_user).


def create_access_token(user_id: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TokenError(Exception):
    """Raised for any invalid, malformed, expired or wrong-signature token.

    Deliberately a single exception type: the caller (``get_current_user``)
    must respond with one generic 401 regardless of the specific cause, per
    the no-enumeration-oracle rule (design §6.2)."""


def decode_access_token(token: str) -> dict:
    """Validate signature and expiry, and return the claims.

    The algorithm is pinned from server-side configuration
    (``algorithms=[settings.JWT_ALGORITHM]``) — the token header's own ``alg``
    is never trusted to select the verification algorithm, which is what
    defeats ``alg=none`` / algorithm-confusion forgery."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


# --- Role-based authorization -------------------------------------------------


def require_role(*allowed: Role) -> Callable:
    """FastAPI dependency factory: 403 unless the current user's live role is
    one of *allowed*. Applied per endpoint (design §7.3) — under Option B this
    only narrows user-management endpoints to ADMIN, since every authenticated
    user already passes the six clinical mutations."""
    # Imported lazily to avoid a circular import (deps -> models -> ... );
    # get_current_user itself lives in app.api.deps.
    from app.api.deps import get_current_user
    from app.models.user import User

    def _dependency(current_user: "User" = Depends(get_current_user)) -> "User":
        try:
            role = Role(current_user.role)
        except ValueError:
            # An invalid role value in the DB (e.g. written by direct SQL)
            # fails closed rather than being trusted (design §8.2 trade-off).
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )
        return current_user

    return _dependency
