"""Startup-time instrument identity resolution for the integration service.

Configuration carries a human-readable ``instrument_name``. The runtime numeric
``id_instrument`` is resolved once here by matching it against
``instruments.nama_mesin``, so no numeric database ID ever lives in
configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import InstrumentConfig, settings
from app.core.database import SessionLocal
from app.models import Instrument


class InstrumentConfigError(RuntimeError):
    """Raised when instrument configuration cannot be bound to the database."""


def write_instrument_status(id_instrument: int, status: str) -> None:
    """Persist one instrument's connection status in its own short-lived Session.

    Shared by ``InstrumentClient`` and the supervisor so a status write never
    piggybacks on a Session held elsewhere (startup, supervisor state).
    """
    try:
        with SessionLocal() as session:
            session.execute(
                update(Instrument)
                .where(Instrument.id_instrument == id_instrument)
                .values(connection_status=status, last_status_at=datetime.utcnow())
            )
            session.commit()
    except SQLAlchemyError as exc:
        print(f"[!] Failed to update instrument {id_instrument} status to {status}: {exc}")


@dataclass(frozen=True)
class RuntimeInstrument:
    """A configured instrument bound to its resolved database identity."""

    config: InstrumentConfig
    id_instrument: int


def resolve_instrument_id(session: Session, instrument_name: str) -> int:
    """Resolve a configuration ``instrument_name`` to a runtime ``id_instrument``.

    Fails loudly on zero matches or on an ambiguous (duplicate) match rather
    than guessing.
    """
    ids = session.scalars(
        select(Instrument.id_instrument).where(Instrument.nama_mesin == instrument_name)
    ).all()

    if not ids:
        raise InstrumentConfigError(
            f"No instrument row found with nama_mesin == {instrument_name!r}. "
            "Seed master data or correct instrument_name in the instrument configuration."
        )
    if len(ids) > 1:
        raise InstrumentConfigError(
            f"Instrument identity is ambiguous: {len(ids)} rows have "
            f"nama_mesin == {instrument_name!r} (id_instrument={sorted(ids)})."
        )
    return ids[0]


def load_runtime_instruments(session: Session) -> list[RuntimeInstrument]:
    """Resolve every enabled configured instrument to its database identity.

    Called once at integration-service startup, not per message.
    """
    runtime: list[RuntimeInstrument] = []
    for config in settings.instruments:
        if not config.enabled:
            continue
        id_instrument = resolve_instrument_id(session, config.instrument_name)
        runtime.append(RuntimeInstrument(config=config, id_instrument=id_instrument))
    return runtime
