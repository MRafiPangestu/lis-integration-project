import json

import pytest
from pydantic import ValidationError

from app.core.config import (
    InstrumentConfig,
    load_instrument_configs,
    settings,
)

VALID = {
    "key": "mindray_bc5150",
    "instrument_name": "Mindray BC-5150",
    "host": "127.0.0.1",
    "port": 5100,
    "mode": "client",
    "parser_key": "bc5150_hl7",
    "identity_prefix": "BC5150-",
    "enabled": True,
}


def test_valid_instrument_config_parses():
    cfg = InstrumentConfig.model_validate(VALID)
    assert cfg.key == "mindray_bc5150"
    assert cfg.instrument_name == "Mindray BC-5150"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 5100
    assert cfg.mode == "client"
    assert cfg.parser_key == "bc5150_hl7"
    assert cfg.identity_prefix == "BC5150-"
    assert cfg.enabled is True


def test_mode_defaults_to_client():
    data = {k: v for k, v in VALID.items() if k != "mode"}
    assert InstrumentConfig.model_validate(data).mode == "client"


def test_server_mode_is_rejected():
    data = {**VALID, "mode": "server"}
    with pytest.raises(ValidationError) as exc:
        InstrumentConfig.model_validate(data)
    assert "client" in str(exc.value)


def test_missing_parser_key_is_rejected():
    data = {k: v for k, v in VALID.items() if k != "parser_key"}
    with pytest.raises(ValidationError) as exc:
        InstrumentConfig.model_validate(data)
    assert "parser_key" in str(exc.value)


def test_missing_required_fields_are_rejected():
    with pytest.raises(ValidationError) as exc:
        InstrumentConfig.model_validate({"key": "x"})
    message = str(exc.value)
    for field in ("instrument_name", "host", "port", "parser_key", "identity_prefix"):
        assert field in message


def test_load_instrument_configs_missing_file_returns_empty(tmp_path):
    assert load_instrument_configs(tmp_path / "nope.json") == []


def test_load_instrument_configs_reads_object_form(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps({"instruments": [VALID]}), encoding="utf-8")
    configs = load_instrument_configs(path)
    assert len(configs) == 1
    assert configs[0].instrument_name == "Mindray BC-5150"


def test_load_instrument_configs_reads_list_form(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps([VALID]), encoding="utf-8")
    assert load_instrument_configs(path)[0].key == "mindray_bc5150"


def test_settings_instruments_loads_from_configured_path(tmp_path, monkeypatch):
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps({"instruments": [VALID]}), encoding="utf-8")
    monkeypatch.setattr(settings, "INSTRUMENTS_CONFIG_FILE", path)

    configs = settings.instruments
    assert len(configs) == 1
    assert configs[0].parser_key == "bc5150_hl7"


def test_config_can_represent_local_bc5150_simulator(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps({"instruments": [VALID]}), encoding="utf-8")
    cfg = load_instrument_configs(path)[0]
    assert (cfg.host, cfg.port) == ("127.0.0.1", 5100)


def test_committed_example_file_is_valid():
    from app.core.config import BACKEND_DIR

    configs = load_instrument_configs(BACKEND_DIR / "instruments.example.json")
    assert len(configs) == 1
    assert configs[0].instrument_name == "Mindray BC-5150"
    assert configs[0].mode == "client"
