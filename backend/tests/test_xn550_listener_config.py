"""XN-550 listener configuration and startup wiring (contract §4.2, §19).

DB-free. Verifies that listener mode is bound exactly to the OD-XN-1 approval
scope, stays disabled by default (G0), must name exactly the dedicated XN-550
parser and policy (Phase 2), that protocol families are enforced at startup,
and that the HL7 client path is unchanged.
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

import run_integration
from app.core.config import (
    LISTENER_APPROVED_SCOPES,
    InstrumentConfig,
    ensure_unique_listener_bindings,
    settings,
)
from app.integration.client import InstrumentClient
from app.integration.instruments import RuntimeInstrument, load_runtime_instruments
from app.core.config import LISTENER_CLASSIFICATION_POLICIES, LISTENER_PARSER_KEYS
from app.integration.listener import ListenerTransport
from app.integration.parsers.registry import (
    KNOWN_PARSER_KEYS,
    PROTOCOL_ASTM_E1394_CR,
    ParserNotRegisteredError,
    protocol_family,
)
from app.integration.parsers.xn550_astm import XN550_POLICIES, parse_xn550_astm

LISTENER = {
    "key": "sysmex_xn550",
    "instrument_name": "Sysmex XN-550",
    "host": "10.0.0.10",
    "port": 5001,
    "mode": "listener",
    "parser_key": "xn550_astm_e1394",
    "classification_policy": "xn550_observed_envelope",
    "allowed_peers": ["10.0.0.11"],
    "ack_policy": "ack_per_read_on_receive",
    "ingestion_stage": "raw_only",
}
CLIENT = {
    "key": "mindray_bc5150",
    "instrument_name": "Mindray BC-5150",
    "host": "127.0.0.1",
    "port": 5100,
    "mode": "client",
    "parser_key": "bc5150_hl7",
    "identity_prefix": "BC5150-",
    "enabled": True,
}


def rejects(data: dict, needle: str) -> None:
    with pytest.raises(ValidationError) as exc:
        InstrumentConfig.model_validate(data)
    assert needle in str(exc.value), str(exc.value)


# --------------------------------------------------------------------------- #
# Valid listener configuration
# --------------------------------------------------------------------------- #


def test_listener_config_parses_without_identity_prefix():
    cfg = InstrumentConfig.model_validate(LISTENER)
    assert cfg.mode == "listener"
    assert cfg.parser_key == "xn550_astm_e1394" and cfg.identity_prefix is None
    assert cfg.classification_policy == "xn550_observed_envelope"
    assert cfg.allowed_peers == ["10.0.0.11"]
    assert (cfg.ack_policy, cfg.ingestion_stage) == ("ack_per_read_on_receive", "raw_only")


def test_listener_is_disabled_by_default_g0():
    assert InstrumentConfig.model_validate(LISTENER).enabled is False


def test_identity_prefix_is_optional_in_listener_mode():
    cfg = InstrumentConfig.model_validate({**LISTENER, "identity_prefix": "XN550-"})
    assert cfg.identity_prefix == "XN550-"


def test_od_xn_1_scope_is_exactly_the_tested_xn550_on_port_5001():
    assert LISTENER_APPROVED_SCOPES == frozenset({("Sysmex XN-550", 5001)})


# --------------------------------------------------------------------------- #
# OD-XN-1 scope and listener-only rules
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "override",
    [
        {"instrument_name": "Mindray BC-5150"},
        {"instrument_name": "Mindray BS-200E"},
        {"instrument_name": "sysmex xn-550"},  # exact match only
        {"port": 5002},
        {"port": 5100},
    ],
)
def test_listener_mode_outside_the_approved_scope_is_rejected(override):
    rejects({**LISTENER, **override}, "not approved")


@pytest.mark.parametrize("peers", [None, [], ["xn550.local"], ["10.0.0.300"]])
def test_listener_requires_a_valid_ip_allowlist(peers):
    data = {**LISTENER, "allowed_peers": peers}
    if peers is None:
        data.pop("allowed_peers")
    rejects(data, "allowed_peers")


def test_listener_host_must_be_a_literal_ip():
    rejects({**LISTENER, "host": "lis-server"}, "literal IP bind address")


@pytest.mark.parametrize("policy", [None, "ack_per_message_after_raw_commit", "nak_on_error"])
def test_listener_ack_policy_must_be_the_verified_baseline(policy):
    data = {**LISTENER, "ack_policy": policy}
    rejects(data, "ack_policy")


@pytest.mark.parametrize("stage", [None, "observations", "clinical"])
def test_listener_ingestion_stage_must_be_raw_only(stage):
    rejects({**LISTENER, "ingestion_stage": stage}, "ingestion_stage")


@pytest.mark.parametrize("key", [None, "bc5150_hl7", "astm_generic", "xn550_astm", "XN550_ASTM_E1394"])
def test_listener_must_name_exactly_the_dedicated_xn550_parser(key):
    data = {**LISTENER, "parser_key": key}
    if key is None:
        data.pop("parser_key")
    rejects(data, "parser_key")


@pytest.mark.parametrize("policy", [None, "strict", "unverified_passthrough", "bc5150_name_passthrough"])
def test_listener_must_name_exactly_the_xn550_policy(policy):
    data = {**LISTENER, "classification_policy": policy}
    if policy is None:
        data.pop("classification_policy")
    rejects(data, "classification_policy")


def test_listener_config_sets_match_the_registry_and_policy_table():
    assert LISTENER_PARSER_KEYS <= KNOWN_PARSER_KEYS
    assert all(protocol_family(key) == PROTOCOL_ASTM_E1394_CR for key in LISTENER_PARSER_KEYS)
    assert LISTENER_CLASSIFICATION_POLICIES == frozenset(XN550_POLICIES)


def test_client_mode_cannot_use_the_astm_parser_key():
    rejects({**CLIENT, "parser_key": "xn550_astm_e1394"}, "cannot be used in client mode")


# --------------------------------------------------------------------------- #
# Client (HL7) mode unchanged
# --------------------------------------------------------------------------- #


def test_client_mode_still_requires_parser_key_and_identity_prefix():
    for field in ("parser_key", "identity_prefix"):
        rejects({k: v for k, v in CLIENT.items() if k != field}, field)
        rejects({**CLIENT, field: None}, field)


@pytest.mark.parametrize(
    "extra", [{"allowed_peers": ["10.0.0.2"]}, {"ack_policy": "ack_per_read_on_receive"}, {"ingestion_stage": "raw_only"}]
)
def test_client_mode_rejects_listener_only_fields(extra):
    rejects({**CLIENT, **extra}, "listener-mode fields")


def test_unknown_mode_is_still_rejected():
    rejects({**CLIENT, "mode": "server"}, "client")


def test_parser_registry_holds_bc5150_and_only_the_dedicated_xn550_parser():
    assert KNOWN_PARSER_KEYS == frozenset({"bc5150_hl7", "xn550_astm_e1394"})


# --------------------------------------------------------------------------- #
# Startup wiring
# --------------------------------------------------------------------------- #


def test_duplicate_listener_bindings_fail_startup():
    a = InstrumentConfig.model_validate(LISTENER)
    b = InstrumentConfig.model_validate({**LISTENER, "key": "sysmex_xn550_second"})
    with pytest.raises(ValueError, match="both bind"):
        ensure_unique_listener_bindings([a, b])
    ensure_unique_listener_bindings([a, InstrumentConfig.model_validate(CLIENT)])


def test_disabled_listener_is_never_loaded(tmp_path, monkeypatch):
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps({"instruments": [LISTENER]}), encoding="utf-8")
    monkeypatch.setattr(settings, "INSTRUMENTS_CONFIG_FILE", path)

    class NoDatabase:
        def scalars(self, *args, **kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("a disabled instrument must not be resolved against the database")

    assert load_runtime_instruments(NoDatabase()) == []


def test_worker_factory_binds_listener_to_the_xn550_parser_and_classification_hooks():
    runtime = RuntimeInstrument(
        config=InstrumentConfig.model_validate({**LISTENER, "enabled": True}), id_instrument=3
    )
    assert run_integration.resolve_runtime_parser(runtime) is parse_xn550_astm
    client, thread = run_integration.worker_factory(runtime)
    assert isinstance(client, ListenerTransport)
    assert not thread.is_alive()
    # the injected hooks are the XN-550 T2 stage, not the Phase-1 no-ops
    assert client._on_raw_committed.__qualname__ == "Xn550ClassificationStage.process"
    assert client._on_serve_start.func.__qualname__ == "Xn550ClassificationStage.process_pending"
    assert client._on_serve_start.args == (3,)


def _unvalidated_runtime(**overrides) -> RuntimeInstrument:
    """Bypass config validation to prove the startup family check is independent of it."""
    data = {**CLIENT, "classification_policy": None, "allowed_peers": None,
            "ack_policy": None, "ingestion_stage": None, **overrides}
    return RuntimeInstrument(config=InstrumentConfig.model_construct(**data), id_instrument=9)


def test_startup_refuses_an_astm_parser_on_the_hl7_client_path():
    with pytest.raises(ParserNotRegisteredError, match="requires a HL7_MLLP parser"):
        run_integration.resolve_runtime_parser(_unvalidated_runtime(parser_key="xn550_astm_e1394"))


def test_startup_refuses_the_hl7_parser_on_a_listener():
    runtime = _unvalidated_runtime(mode="listener", parser_key="bc5150_hl7")
    with pytest.raises(ParserNotRegisteredError, match="requires a ASTM_E1394_CR parser"):
        run_integration.resolve_runtime_parser(runtime)


def test_unknown_parser_key_still_fails_without_fallback():
    with pytest.raises(ParserNotRegisteredError):
        run_integration.resolve_runtime_parser(_unvalidated_runtime(parser_key="astm_generic"))
    with pytest.raises(ParserNotRegisteredError):
        protocol_family("astm_generic")


def test_worker_factory_client_mode_is_unchanged():
    runtime = RuntimeInstrument(config=InstrumentConfig.model_validate(CLIENT), id_instrument=2)
    client, thread = run_integration.worker_factory(runtime)
    assert isinstance(client, InstrumentClient)
    assert (client.host, client.port, client.instrument_id) == ("127.0.0.1", 5100, 2)
    assert not thread.is_alive()


def test_main_resolves_and_family_checks_every_parser(monkeypatch):
    resolved: list[str] = []
    listener_rt = RuntimeInstrument(
        config=InstrumentConfig.model_validate({**LISTENER, "enabled": True}), id_instrument=3
    )
    client_rt = RuntimeInstrument(config=InstrumentConfig.model_validate(CLIENT), id_instrument=2)

    class SpySupervisor:
        def __init__(self, runtimes, factory, *, shutdown_event):
            self.runtimes = runtimes

        def run(self):
            return None

    real_resolve = run_integration.resolve_parser

    def spy(key):
        resolved.append(key)
        return real_resolve(key)

    monkeypatch.setattr(run_integration, "load_runtime_instruments", lambda session: [listener_rt, client_rt])
    monkeypatch.setattr(run_integration, "resolve_parser", spy)
    monkeypatch.setattr(run_integration, "Supervisor", SpySupervisor)
    monkeypatch.setattr(run_integration.signal, "signal", lambda *a, **k: None)
    run_integration.main()
    assert resolved == ["xn550_astm_e1394", "bc5150_hl7"]
