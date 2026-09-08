import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Only client mode is supported in M8. Listener/server mode is deferred until
# field verification proves it is required.
SUPPORTED_INSTRUMENT_MODES = {"client"}


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
