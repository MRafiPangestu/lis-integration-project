import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Only client mode is supported in M8. Listener/server mode is deferred until
# field verification proves it is required.
SUPPORTED_INSTRUMENT_MODES = {"client"}

# --- JWT secret strength (M9.1a review finding M-1) --------------------------
# Minimum accepted JWT_SECRET_KEY length. 32 characters is the smallest value
# that makes offline recovery of an HS256 secret impractical; the generator
# suggested in .env.example produces 64.
MIN_JWT_SECRET_KEY_LENGTH = 32

# The literal placeholder shipped in backend/.env.example. It is public by
# definition, so it must never be accepted as a real secret. This is a
# placeholder to reject, not a credential.
JWT_SECRET_KEY_PLACEHOLDER = "<generate-a-long-random-secret-and-put-it-here>"

# Well-known values that are weak regardless of length. Compared casefolded,
# and also rejected when repeated to pad out the length check.
_WEAK_JWT_SECRETS = frozenset({"changeme", "secret", "password"})


class InstrumentConfig(BaseModel):
    """Per-instrument deployment configuration.

    This is application configuration, not master data. The ``instruments``
    database table stays responsible for instrument identity, master-data
    attributes and runtime connection status. Numeric database IDs must never
    appear here — identity is resolved at startup via ``instrument_name``.
    """

    key: str
    instrument_name: str
    host: str
    port: int
    mode: str = "client"
    parser_key: str
    identity_prefix: str
    enabled: bool = False
    # M8.2: name of the message-classification policy for this instrument.
    # Omitted -> the strict default (UNCLASSIFIED). Resolved in
    # app.integration.classification; unknown names fall back to strict.
    classification_policy: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def _mode_supported(cls, value: str) -> str:
        if value not in SUPPORTED_INSTRUMENT_MODES:
            raise ValueError(
                f"Unsupported instrument mode {value!r}. "
                f"Only {sorted(SUPPORTED_INSTRUMENT_MODES)} is supported in M8; "
                "listener/server mode is deferred."
            )
        return value


def load_instrument_configs(path: Path) -> list[InstrumentConfig]:
    """Load the per-instrument configuration list from a JSON file.

    Accepts either a top-level list or ``{"instruments": [...]}``. A missing
    file yields an empty list so the API can start without the integration
    configuration present.
    """
    file_path = Path(path)
    if not file_path.is_file():
        return []

    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("instruments", [])
    if not isinstance(raw, list):
        raise ValueError(
            f"Instrument configuration at {file_path} must be a list "
            'or an object with an "instruments" list.'
        )
    return [InstrumentConfig.model_validate(item) for item in raw]


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "lis_marina_permata_dev"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # API
    API_TITLE: str = "LIS API Marina Permata"
    API_VERSION: str = "1.0.0"

    # Deployment environment. Controls only dev-convenience behaviour that must
    # not exist in production (M9.1a OD-S2): FastAPI docs/redoc/openapi are
    # disabled when this is "production". Never used to relax authentication.
    ENVIRONMENT: str = "development"

    # --- Security / authentication (M9.1a) -----------------------------------
    # No default. pydantic-settings makes this a required field, so the
    # application refuses to start (raises at import time) if it is unset or
    # empty in both the environment and .env — see the design doc §6.4 / the
    # M9.1a Governance Update OD-S1. Never logged.
    JWT_SECRET_KEY: str
    # Pinned per OD-S1. Never read the algorithm from the token header.
    JWT_ALGORITHM: str = "HS256"
    # 8-hour shift, no refresh token, per OD-S1.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _jwt_secret_key_must_be_strong(cls, value: str) -> str:
        """Fail fast on a secret that cannot actually protect HS256 tokens.

        The secret is the only thing preventing arbitrary token forgery: an
        attacker who recovers it can mint a token for any ``sub``, including
        the bootstrap ADMIN. A short, public or dictionary value is
        recoverable offline from a single captured token, so "set" is not a
        sufficient bar — "unguessable" is (M9.1a review finding M-1).

        Deliberately checked in this order so the error names the real
        problem: a copied placeholder is reported as a placeholder, not as
        "too short".
        """
        candidate = value.strip()

        if not candidate:
            raise ValueError(
                "JWT_SECRET_KEY must not be empty or whitespace-only. "
                "No default is provided — set a real secret in the environment "
                "or backend/.env before starting the application."
            )

        if candidate == JWT_SECRET_KEY_PLACEHOLDER or (
            candidate.startswith("<") and candidate.endswith(">")
        ):
            raise ValueError(
                "JWT_SECRET_KEY is still the backend/.env.example placeholder. "
                "That value is public and must never be used. Generate a real "
                'secret, e.g. python -c "import secrets; '
                'print(secrets.token_urlsafe(48))".'
            )

        normalised = candidate.casefold()
        if normalised in _WEAK_JWT_SECRETS or any(
            # A weak word padded out to clear the length check is still weak.
            weak * (len(normalised) // len(weak)) == normalised
            for weak in _WEAK_JWT_SECRETS
            if len(normalised) % len(weak) == 0
        ):
            raise ValueError(
                "JWT_SECRET_KEY is a well-known weak value. Generate a real "
                'secret, e.g. python -c "import secrets; '
                'print(secrets.token_urlsafe(48))".'
            )

        if len(candidate) < MIN_JWT_SECRET_KEY_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_KEY_LENGTH} "
                f"characters long (got {len(candidate)}). A short secret is "
                "recoverable offline from a captured token, which would allow "
                "forging a token for any user."
            )

        return value

    # Explicit CORS allowlist (OD-S2 / §9). Fail closed: an unset variable
    # means no cross-origin access, never "*". Comma-separated, e.g.
    # "http://localhost:5173,https://lis.example.org". Kept as a plain string
    # field (not List[str]) because pydantic-settings would otherwise require
    # JSON-array syntax in .env; ``cors_allow_origins`` below does the split.
    CORS_ALLOW_ORIGINS: str = ""

    @property
    def cors_allow_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]

    # SIMRS Integration
    SIMRS_BASE_URL: Optional[str] = None
    SIMRS_ENDPOINT: str = "/api/v1/lis/results"
    SIMRS_TIMEOUT: int = 15
    SIMRS_API_KEY: Optional[str] = None

    # Instrument integration
    INSTRUMENTS_CONFIG_FILE: Path = BACKEND_DIR / "instruments.json"

    @property
    def instruments(self) -> list[InstrumentConfig]:
        return load_instrument_configs(self.INSTRUMENTS_CONFIG_FILE)

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent.parent / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
