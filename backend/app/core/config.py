import ipaddress
import json
from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# "client": the LIS dials the instrument (M8; HL7 over MLLP).
# "listener": the instrument dials the LIS. Field verification proved this is
# required for the tested Sysmex XN-550 configuration and the project owner
# approved it (docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md,
# OD-XN-1). Listener mode is authorised ONLY for LISTENER_APPROVED_SCOPES below.
SUPPORTED_INSTRUMENT_MODES = {"client", "listener"}

# OD-XN-1 approval scope, encoded exactly: (instrument_name, port) pairs for
# which listener mode is approved. The approval covers the tested XN-550 ASTM
# configuration on TCP port 5001 only — not other ports (UNKNOWN; no port scan
# authorised) and not any other instrument. Extending this set is an
# architecture decision backed by that instrument's own transport evidence,
# never a configuration change.
LISTENER_APPROVED_SCOPES = frozenset({("Sysmex XN-550", 5001)})

# Listener ACK policies implemented in this phase (contract §4.5). Only the
# field-verified baseline exists; `ack_per_message_after_raw_commit` is NOT
# FIELD-VERIFIED and stays unavailable until OD-XN-4.
LISTENER_ACK_POLICIES = frozenset({"ack_per_read_on_receive"})

# Listener ingestion stages (contract §19.3). G1 `raw_only`: raw capture, envelope
# classification and byte-identity linking. G2 `observations`: additionally the
# unlinked observation sets (OD-XN-3 approved). There is no default: a listener
# entry must name its stage explicitly. Production XN-550 stays `raw_only` until
# the 14-day G1 soak exit criteria pass (contract §19.7); nothing switches the
# stage automatically.
LISTENER_INGESTION_STAGES = frozenset({"raw_only", "observations"})

# Parser keys and classification policies a listener-mode instrument may name
# (contract §4.2, §19.1). Only the dedicated XN-550 parser exists; there is no
# generic ASTM parser. Startup additionally checks the key's registered protocol
# family (run_integration).
LISTENER_PARSER_KEYS = frozenset({"xn550_astm_e1394"})
LISTENER_CLASSIFICATION_POLICIES = frozenset({"xn550_observed_envelope"})

# Fields that only have meaning for a listener-mode instrument.
_LISTENER_ONLY_FIELDS = ("allowed_peers", "ack_policy", "ingestion_stage")

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
    # client mode: the instrument's address. listener mode: the LIS bind address.
    host: str
    port: int
    mode: str = "client"
    # Required (and non-null) in both modes. Listener mode accepts only
    # LISTENER_PARSER_KEYS (contract §19.5); client mode must not name them.
    parser_key: Optional[str]
    # Required (and non-null) in client mode, where it builds `no_registrasi`.
    # Optional in listener mode, and never used by any listener code path
    # (contract §4.2, §12.3).
    identity_prefix: Optional[str]
    enabled: bool = False
    # M8.2: name of the message-classification policy for this instrument.
    # Omitted -> the strict default (UNCLASSIFIED). Resolved in
    # app.integration.classification; unknown names fall back to strict.
    # Listener mode requires one of LISTENER_CLASSIFICATION_POLICIES (exact; no
    # strict fallback for listener instruments).
    classification_policy: Optional[str] = None
    # Listener mode only (contract §4.2). Exact peer IP allowlist.
    allowed_peers: Optional[List[str]] = None
    # Listener mode only (contract §4.5).
    ack_policy: Optional[str] = None
    # Listener mode only (contract §19.3).
    ingestion_stage: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def _mode_supported(cls, value: str) -> str:
        if value not in SUPPORTED_INSTRUMENT_MODES:
            raise ValueError(
                f"Unsupported instrument mode {value!r}. "
                f"Supported modes: {sorted(SUPPORTED_INSTRUMENT_MODES)} "
                "('client' = the LIS dials the instrument; 'listener' = the "
                "instrument dials the LIS, approved scopes only)."
            )
        return value

    @model_validator(mode="before")
    @classmethod
    def _listener_fields_may_be_omitted(cls, data):
        """In listener mode `identity_prefix` may be omitted, and an omitted
        `parser_key` is reported by the listener rules below rather than as a
        bare "Field required".

        Both stay required keys in client mode, so a client config that omits
        them keeps failing with pydantic's own "Field required" errors.
        """
        if isinstance(data, dict) and data.get("mode") == "listener":
            data = dict(data)
            data.setdefault("parser_key", None)
            data.setdefault("identity_prefix", None)
        return data

    @model_validator(mode="after")
    def _mode_specific_requirements(self) -> "InstrumentConfig":
        if self.mode == "client":
            return self._validate_client()
        return self._validate_listener()

    def _validate_client(self) -> "InstrumentConfig":
        missing = [f for f in ("parser_key", "identity_prefix") if getattr(self, f) is None]
        if missing:
            raise ValueError(f"client mode requires non-null {missing}")
        present = [f for f in _LISTENER_ONLY_FIELDS if getattr(self, f) is not None]
        if present:
            raise ValueError(f"{present} are listener-mode fields and must be omitted in client mode")
        if self.parser_key in LISTENER_PARSER_KEYS:
            raise ValueError(
                f"parser_key {self.parser_key!r} is a listener-mode (ASTM) parser and "
                "cannot be used in client mode"
            )
        return self

    def _validate_listener(self) -> "InstrumentConfig":
        if (self.instrument_name, self.port) not in LISTENER_APPROVED_SCOPES:
            raise ValueError(
                f"listener mode is not approved for instrument_name="
                f"{self.instrument_name!r} on port {self.port}. Approved scopes "
                f"(OD-XN-1): {sorted(LISTENER_APPROVED_SCOPES)}. Other instruments "
                "and ports require their own transport evidence and approval."
            )
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            raise ValueError(
                f"listener mode requires host to be a literal IP bind address, got {self.host!r}"
            ) from None
        if not self.allowed_peers:
            raise ValueError("listener mode requires a non-empty allowed_peers list")
        normalised = []
        for peer in self.allowed_peers:
            try:
                normalised.append(str(ipaddress.ip_address(peer)))
            except ValueError:
                raise ValueError(f"allowed_peers entry {peer!r} is not a literal IP address") from None
        self.allowed_peers = normalised
        if self.ack_policy not in LISTENER_ACK_POLICIES:
            raise ValueError(
                f"listener ack_policy {self.ack_policy!r} is not available. Implemented: "
                f"{sorted(LISTENER_ACK_POLICIES)} (the field-verified baseline). "
                "'ack_per_message_after_raw_commit' is NOT FIELD-VERIFIED (OD-XN-4)."
            )
        if self.ingestion_stage not in LISTENER_INGESTION_STAGES:
            raise ValueError(
                f"listener ingestion_stage {self.ingestion_stage!r} is not available. "
                f"Required: one of {sorted(LISTENER_INGESTION_STAGES)} "
                "('raw_only' = G1 raw capture; 'observations' = G2 unlinked observations). "
                "Production XN-550 stays 'raw_only' until the G1 soak exit criteria pass."
            )
        if self.parser_key not in LISTENER_PARSER_KEYS:
            raise ValueError(
                f"listener parser_key {self.parser_key!r} is not available. Required: "
                f"one of {sorted(LISTENER_PARSER_KEYS)} (no generic ASTM parser, no fallback)."
            )
        if self.classification_policy not in LISTENER_CLASSIFICATION_POLICIES:
            raise ValueError(
                f"listener classification_policy {self.classification_policy!r} is not "
                f"available. Required: one of {sorted(LISTENER_CLASSIFICATION_POLICIES)}."
            )
        return self


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


def ensure_unique_listener_bindings(configs: Iterable[InstrumentConfig]) -> None:
    """Fail loudly if two listener configs would bind the same (host, port).

    Contract §4.2. Called at integration-service startup over the enabled
    instruments only.
    """
    seen: dict[tuple[str, int], str] = {}
    for config in configs:
        if config.mode != "listener":
            continue
        binding = (str(ipaddress.ip_address(config.host)), config.port)
        if binding in seen:
            raise ValueError(
                f"listener configs {seen[binding]!r} and {config.key!r} both bind "
                f"{binding[0]}:{binding[1]}"
            )
        seen[binding] = config.key


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
