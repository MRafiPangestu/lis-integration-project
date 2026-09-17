"""XN-550 Phase 1 — listener configuration and startup wiring (contract §4.2, §19).

DB-free. Verifies that listener mode is bound exactly to the OD-XN-1 approval
scope, stays disabled by default (G0), carries no parser / classification
policy, and that the HL7 client path and the parser registry are unchanged.
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
from app.integration.listener import ListenerTransport
from app.integration.parsers.registry import KNOWN_PARSER_KEYS

LISTENER = {
    "key": "sysmex_xn550",
    "instrument_name": "Sysmex XN-550",
    "host": "10.0.0.10",
    "port": 5001,
    "mode": "listener",
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


def test_listener_config_parses_without_parser_key_or_identity_prefix():
    cfg = InstrumentConfig.model_validate(LISTENER)
    assert cfg.mode == "listener"
    assert cfg.parser_key is None and cfg.identity_prefix is None
    assert cfg.classification_policy is None
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


@pytest.mark.parametrize("key", ["xn550_astm_e1394", "bc5150_hl7", "astm_generic"])
def test_listener_must_not_name_a_parser(key):
    rejects({**LISTENER, "parser_key": key}, "must omit parser_key")


def test_listener_must_not_name_a_classification_policy():
    rejects({**LISTENER, "classification_policy": "xn550_observed_envelope"}, "classification_policy")


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


def test_parser_registry_is_unchanged_no_astm_key_registered():
    assert KNOWN_PARSER_KEYS == frozenset({"bc5150_hl7"})


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


def test_worker_factory_dispatches_listener_mode_without_resolving_a_parser(monkeypatch):
    def forbidden(key):  # pragma: no cover - must not be reached
        raise AssertionError("listener mode must not resolve a parser")

    monkeypatch.setattr(run_integration, "resolve_parser", forbidden)
    runtime = RuntimeInstrument(
        config=InstrumentConfig.model_validate({**LISTENER, "enabled": True}), id_instrument=3
    )
    client, thread = run_integration.worker_factory(runtime)
    assert isinstance(client, ListenerTransport)
    assert not thread.is_alive()


def test_worker_factory_client_mode_is_unchanged():
    runtime = RuntimeInstrument(config=InstrumentConfig.model_validate(CLIENT), id_instrument=2)
    client, thread = run_integration.worker_factory(runtime)
    assert isinstance(client, InstrumentClient)
    assert (client.host, client.port, client.instrument_id) == ("127.0.0.1", 5100, 2)
    assert not thread.is_alive()


def test_main_skips_parser_resolution_for_listener_but_not_for_client(monkeypatch):
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

    monkeypatch.setattr(run_integration, "load_runtime_instruments", lambda session: [listener_rt, client_rt])
    monkeypatch.setattr(run_integration, "resolve_parser", lambda key: resolved.append(key))
    monkeypatch.setattr(run_integration, "Supervisor", SpySupervisor)
    monkeypatch.setattr(run_integration.signal, "signal", lambda *a, **k: None)
    run_integration.main()
    assert resolved == ["bc5150_hl7"]
