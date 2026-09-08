"""M8.3 parser registry tests.

The registry must resolve a configuration ``parser_key`` to a concrete parser by
exact lookup only, fail loudly on anything unknown, and never fall back to
BC-5150.
"""
import inspect

import pytest

from app.integration.parsers.hl7 import parse_hl7_bc5150
from app.integration.parsers.registry import (
    KNOWN_PARSER_KEYS,
    ParserNotRegisteredError,
    _PARSERS,
    resolve_parser,
)


# R1 -----------------------------------------------------------------

def test_resolve_bc5150_returns_the_existing_parser_function():
    assert resolve_parser("bc5150_hl7") is parse_hl7_bc5150


# R2 -----------------------------------------------------------------

def test_unknown_parser_key_raises_parser_not_registered():
    with pytest.raises(ParserNotRegisteredError):
        resolve_parser("astm_generic")


# R3 -----------------------------------------------------------------

def test_error_message_names_the_offending_key_and_known_keys():
    with pytest.raises(ParserNotRegisteredError) as exc:
        resolve_parser("sysmex_astm")
    message = str(exc.value)
    assert "sysmex_astm" in message
    assert "bc5150_hl7" in message


# R4 -----------------------------------------------------------------

@pytest.mark.parametrize("bad_key", ["", "BC5150_HL7", "Bc5150_Hl7", " bc5150_hl7", "bc5150_hl7 ", "bc5150-hl7"])
def test_no_fuzzy_or_case_insensitive_matching(bad_key):
    with pytest.raises(ParserNotRegisteredError):
        resolve_parser(bad_key)


# R5 -----------------------------------------------------------------

def test_known_parser_keys_is_exactly_bc5150():
    assert KNOWN_PARSER_KEYS == frozenset({"bc5150_hl7"})
    assert set(_PARSERS) == {"bc5150_hl7"}


# R6 -----------------------------------------------------------------

def test_multiple_unknown_keys_never_resolve_to_bc5150():
    for key in ("astm", "hl7", "bc5150", "mindray", "default", "hl7_v2", "generic"):
        with pytest.raises(ParserNotRegisteredError):
            resolve_parser(key)


# R7 -----------------------------------------------------------------

def test_registry_dict_is_not_mutated_by_resolution():
    snapshot = dict(_PARSERS)
    resolve_parser("bc5150_hl7")
    for key in ("nope", "", "ASTM"):
        with pytest.raises(ParserNotRegisteredError):
            resolve_parser(key)
    assert _PARSERS == snapshot
    assert set(_PARSERS) == {"bc5150_hl7"}


# R8 -----------------------------------------------------------------

def test_registry_module_is_db_free_and_uses_no_dynamic_import():
    import app.integration.parsers.registry as registry_module

    src = inspect.getsource(registry_module)
    for forbidden in ("importlib", "__import__", "pkgutil", "sqlalchemy",
                      "Session", "sessionmaker", "app.core.database",
                      "app.integration.instruments", "app.integration.repository"):
        assert forbidden not in src, forbidden

    # only imports are from the parser layer
    imported = {
        name for name, val in vars(registry_module).items()
        if inspect.ismodule(val)
    }
    assert imported <= {"annotations"}  # from __future__ import annotations only


# --- R9 / R10: configuration -> runtime binding -----------------------

def _runtime(*, key="inst", parser_key="bc5150_hl7", id_instrument=1):
    from app.core.config import InstrumentConfig
    from app.integration.instruments import RuntimeInstrument

    cfg = InstrumentConfig(
        key=key,
        instrument_name="Machine",
        host="127.0.0.1",
        port=5100,
        parser_key=parser_key,
        identity_prefix="X-",
        enabled=True,
    )
    return RuntimeInstrument(config=cfg, id_instrument=id_instrument)


class _SpySupervisor:
    """Records construction and fails if run() is reached."""

    def __init__(self, *args, **kwargs):
        _SpySupervisor.built.append((args, kwargs))

    def run(self):  # pragma: no cover
        raise AssertionError("Supervisor.run() must not be reached")


# R9 -----------------------------------------------------------------

def test_r9_invalid_parser_key_fails_startup_before_supervisor(monkeypatch):
    import run_integration

    _SpySupervisor.built = []
    monkeypatch.setattr(
        run_integration, "load_runtime_instruments",
        lambda session: [_runtime(key="bad", parser_key="nonexistent_parser")],
    )
    monkeypatch.setattr(run_integration, "Supervisor", _SpySupervisor)

    with pytest.raises(ParserNotRegisteredError) as exc:
        run_integration.main()

    assert "nonexistent_parser" in str(exc.value)
    assert _SpySupervisor.built == []  # no worker startup / status writes


# R10 ----------------------------------------------------------------

def test_r10_unknown_parser_key_cannot_fall_back_to_bc5150_at_startup(monkeypatch):
    import run_integration

    _SpySupervisor.built = []
    runtimes = [
        _runtime(key="good", parser_key="bc5150_hl7"),
        _runtime(key="bad", parser_key="totally_unknown"),
    ]
    monkeypatch.setattr(run_integration, "load_runtime_instruments", lambda session: runtimes)
    monkeypatch.setattr(run_integration, "Supervisor", _SpySupervisor)

    with pytest.raises(ParserNotRegisteredError):
        run_integration.main()

    assert _SpySupervisor.built == []
    # the unknown key never yields a parser at all, let alone BC-5150
    with pytest.raises(ParserNotRegisteredError):
        resolve_parser("totally_unknown")
