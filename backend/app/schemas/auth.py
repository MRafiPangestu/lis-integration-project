import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.security import Role


class UserPublic(BaseModel):
    """A user account as returned by the API. Never carries ``password_hash``."""

    id_user: int
    username: str
    nama_lengkap: str
    role: Role
    is_active: bool
    created_at: datetime.datetime
    last_login_at: Optional[datetime.datetime] = None
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    nama_lengkap: str = Field(min_length=1, max_length=100)
    password: str
    role: Role


class UpdateUserStatusRequest(BaseModel):
    is_active: bool
