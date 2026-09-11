"""Admin user-management endpoints (M9.1a, OD-1 = Option B).

Mounted under ``api_router`` (deny-by-default), with an additional
``require_role(Role.ADMIN)`` on every route — the one capability Option B
reserves to ADMIN alone (design §5.3). Creating a user here is the normal
operational path; the interactive ``scripts/create_admin.py`` bootstrap
exists only because the very first admin cannot be created through an
endpoint nobody can yet call.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import Role, hash_password, require_role, validate_password_policy
from app.models.user import User
from app.schemas.auth import CreateUserRequest, UpdateUserStatusRequest, UserPublic

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


def would_leave_no_active_admin(db: Session, target: User) -> bool:
    """True if deactivating *target* would leave the system with no active
    ADMIN — i.e. nobody able to reach these endpoints again (M9.1a review
    finding M-3).

    Extracted from the handler so the guard itself is directly testable. Note
    that the self-disable rule in ``update_user_status`` already makes this
    condition unreachable through the API today: the caller is necessarily an
    active ADMIN and cannot be the target, so at least one active ADMIN always
    remains. It is kept as defence in depth — it stays correct if the
    self-disable rule is ever relaxed, or if a non-interactive admin path is
    added later.
    """
    if target.role != Role.ADMIN.value or not target.is_active:
        # Deactivating a non-admin, or an already-inactive account, cannot
        # reduce the active-ADMIN count. Compared against the stored value so
        # an unparseable role (written by direct SQL) is simply not an ADMIN
        # here rather than raising.
        return False

    remaining = db.scalar(
        select(func.count(User.id_user)).where(
            User.role == Role.ADMIN.value,
            User.is_active.is_(True),
            User.id_user != target.id_user,
        )
    )
    return not remaining


@router.get("", response_model=List[UserPublic])
def list_users(db: Session = Depends(get_db)) -> List[User]:
    return list(db.scalars(select(User).order_by(User.id_user)).all())


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db)) -> User:
    validate_password_policy(payload.password)

    user = User(
        username=payload.username,
        nama_lengkap=payload.nama_lengkap,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username already exists.",
        )
    db.refresh(user)
    return user


@router.patch("/{id_user}/status", response_model=UserPublic)
def update_user_status(
    id_user: int,
    payload: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    # The router-level require_role(Role.ADMIN) already enforces the role;
    # this only needs the value. get_current_user is cached per request, so
    # this adds no second database lookup.
    current_user: User = Depends(get_current_user),
) -> User:
    """Enable or disable an account. This is the revocation mechanism
    (design §6.3): disabling takes effect on the user's next request, not
    after their current token expires.

    Deactivation is guarded so that an administrator cannot lock every
    administrator out of user management (M9.1a review finding M-3).
    Reactivation is unguarded — it can only ever increase access.
    """
    user = db.get(User, id_user)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not payload.is_active:
        if user.id_user == current_user.id_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "You cannot disable your own account. Ask another "
                    "administrator to do it."
                ),
            )
        if would_leave_no_active_admin(db, user):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot disable the last active ADMIN — no one would be "
                    "able to manage users afterwards."
                ),
            )

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user
