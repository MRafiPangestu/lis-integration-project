"""M9.1a — JWT secret strength validation (review finding M-1).

``JWT_SECRET_KEY`` is the only thing preventing arbitrary HS256 token
forgery, so "is set" was never a sufficient bar. These tests pin the four
rejection rules and the accept case.

No database and no application startup: ``Settings`` is instantiated
directly. Init keyword arguments outrank ``backend/.env`` in
pydantic-settings' precedence order, so each case exercises exactly the
value under test while the remaining settings still load normally.
"""
import pytest
from pydantic import ValidationError

from app.core.config import (
    JWT_SECRET_KEY_PLACEHOLDER,
    MIN_JWT_SECRET_KEY_LENGTH,
    Settings,
)

# Not a real secret — a random-looking value of acceptable length, used only
# to prove the validator accepts a well-formed one.
_ACCEPTABLE_SECRET = "yq3F_zK8pR2vN7wL5tX1cB9mH4jG6sD0aE-ZuQiOpAsDfGhJkL"


def _build(secret: str) -> Settings:
    return Settings(JWT_SECRET_KEY=secret)


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_secret_rejected(blank):
    with pytest.raises(ValidationError) as exc_info:
        _build(blank)
    assert "empty or whitespace-only" in str(exc_info.value)


@pytest.mark.parametrize(
    "short",
    [
        "x",
        "short-secret",
        "a" * (MIN_JWT_SECRET_KEY_LENGTH - 1),
    ],
)
def test_short_secret_rejected(short):
    with pytest.raises(ValidationError) as exc_info:
        _build(short)
    assert str(MIN_JWT_SECRET_KEY_LENGTH) in str(exc_info.value)


def test_env_example_placeholder_rejected():
    """The placeholder is public by definition — an operator who copies
    .env.example without substituting it must not get a running server."""
    with pytest.raises(ValidationError) as exc_info:
        _build(JWT_SECRET_KEY_PLACEHOLDER)
    assert "placeholder" in str(exc_info.value)


def test_any_angle_bracket_placeholder_rejected():
    """Catches hand-edited placeholders too, not just the literal one."""
    with pytest.raises(ValidationError):
        _build("<put-your-very-long-secret-key-value-here>")


@pytest.mark.parametrize("weak", ["changeme", "secret", "password", "CHANGEME", "Secret"])
def test_common_weak_secret_rejected(weak):
    with pytest.raises(ValidationError):
        _build(weak)


def test_weak_secret_padded_to_the_length_limit_is_still_rejected():
    """A weak word repeated to clear the length check is still weak."""
    padded = "changeme" * 4  # 32 chars — long enough to pass on length alone
    assert len(padded) >= MIN_JWT_SECRET_KEY_LENGTH
    with pytest.raises(ValidationError) as exc_info:
        _build(padded)
    assert "weak" in str(exc_info.value)


def test_sufficiently_long_random_secret_accepted():
    settings = _build(_ACCEPTABLE_SECRET)
    assert settings.JWT_SECRET_KEY == _ACCEPTABLE_SECRET


def test_accepted_secret_is_not_trimmed():
    """The validator normalises only for its checks — the configured value
    itself is returned verbatim, so a token signed before a restart still
    verifies after one."""
    padded = f"  {_ACCEPTABLE_SECRET}  "
    assert _build(padded).JWT_SECRET_KEY == padded
