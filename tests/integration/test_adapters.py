"""Tests for the adapters/ infra — registry, config_loader, config_schema.

Covers the adapter contract surface (high-priority: adapter-degraded paths,
storage contracts): the AdapterCoordinator, the legacy bare-function fallback
shims (no-coordinator path), adapter validation, and the stored-config loader.

Coverage targets
----------------
[RG-1]  AdapterCoordinator register/get/get_all/unregister/clear/get_adapter_value.
[RG-2]  AdapterCoordinator construct sets active pointer; shutdown clears it.
[RG-3]  register with invalid mapping logs but still stores; non-dict raises.
[RG-4]  _validate_adapter: valid, mapping-not-dict, missing/unknown engine, noop ok.
[RG-5]  bare-function fallback shims operate on _REGISTRY when no coordinator.
[CL-1]  load_stored_adapter_configs: non-dict store → 0; malformed skipped; counts.
[CL-2]  load_stored_adapter_configs: register exception is swallowed.
[CL-3]  save / delete / get_stored_adapter_config round-trip.
[CS-1]  ADAPTER_CONFIG_SCHEMA is importable and has the required top-level keys.
"""

from __future__ import annotations

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.eufy_vacuum.adapters.registry as reg
from custom_components.eufy_vacuum.adapters import config_loader as cl
from custom_components.eufy_vacuum.adapters.config_schema import ADAPTER_CONFIG_SCHEMA
from custom_components.eufy_vacuum.adapters.registry import (
    AdapterCoordinator,
    _validate_adapter,
    get_active_coordinator,
)
from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


@pytest.fixture(autouse=True)
def _preserve_registry():
    """Snapshot + reset the module-level registry globals around each test."""
    prev = reg._active_coordinator
    snap = dict(reg._REGISTRY)
    reg._set_active_coordinator(None)
    reg._REGISTRY.clear()
    yield
    reg._set_active_coordinator(prev)
    reg._REGISTRY.clear()
    reg._REGISTRY.update(snap)


def _coord(hass):
    return AdapterCoordinator(hass, MockConfigEntry(domain=DOMAIN))


# ---------------------------------------------------------------------------
# AdapterCoordinator
# ---------------------------------------------------------------------------

def test_coordinator_crud(hass):
    """[RG-1]"""
    c = _coord(hass)
    c.register_adapter_config(_VAC, {"adapter_id": "a", "source": "code"})
    assert c.get_adapter_config(_VAC)["adapter_id"] == "a"
    assert _VAC in c.get_all_adapter_configs()
    assert c.get_adapter_value(_VAC, "adapter_id") == "a"
    assert c.get_adapter_value(_VAC, "nope", fallback="d") == "d"
    assert c.get_adapter_value(_VAC, "adapter_id", "deeper", fallback="d") == "d"
    c.unregister_adapter_config(_VAC)
    assert c.get_adapter_config(_VAC) is None
    c.register_adapter_config(_VAC, {"adapter_id": "a"})
    c.clear_registry()
    assert c.get_all_adapter_configs() == {}
    c.shutdown()


def test_coordinator_active_pointer(hass):
    """[RG-2]"""
    assert get_active_coordinator() is None
    c = _coord(hass)
    assert get_active_coordinator() is c
    c.shutdown()
    assert get_active_coordinator() is None
    c.shutdown()  # idempotent


def test_coordinator_invalid_and_nondict(hass):
    """[RG-3] unknown segmenter engine logs but still stores; non-dict raises."""
    c = _coord(hass)
    c.register_adapter_config(_VAC, {
        "adapter_id": "a", "mapping": {"segmenter_engine": "does_not_exist"}})
    # invalid mapping is a warning, not fatal — config is still stored
    assert c.get_adapter_config(_VAC) is not None
    with pytest.raises(TypeError):
        c.register_adapter_config(_VAC, "not-a-dict")
    c.shutdown()


# ---------------------------------------------------------------------------
# _validate_adapter
# ---------------------------------------------------------------------------

def test_validate_adapter():
    """[RG-4]"""
    assert _validate_adapter({"adapter_id": "a"}) == []
    assert _validate_adapter("nope") == ["adapter config must be a dict"]
    assert "'mapping' must be a dict if present" in _validate_adapter(
        {"mapping": "x"})
    # mapping present but no engine declared
    assert any("segmenter_engine is required" in i
               for i in _validate_adapter({"mapping": {}}))
    # unknown engine name
    assert any("is unknown" in i for i in _validate_adapter(
        {"mapping": {"segmenter_engine": "bogus_engine"}}))
    # a real engine passes validation
    assert _validate_adapter(
        {"mapping": {"segmenter_engine": "noop_fallback"}}) == []


def test_validate_adapter_job_segmenter_block():
    """[RG-4] job_segmenter block is the 2nd-brand JobSegmenter seam contract.

    A declared block that is not-a-dict / omits the engine / names an unknown
    engine must surface a checked issue (so registration rejects a brand that
    would otherwise silently fall back to the Eufy counter engine), mirroring
    the mapping.segmenter_engine contract. The declared 'noop_job_fallback'
    sentinel must pass clean.
    """
    # block present but not a dict
    assert "'job_segmenter' must be a dict if present" in _validate_adapter(
        {"job_segmenter": "x"})
    # block present but no engine declared
    assert any("job_segmenter.engine is required" in i
               for i in _validate_adapter({"job_segmenter": {}}))
    # unknown engine name
    assert any("is unknown" in i for i in _validate_adapter(
        {"job_segmenter": {"engine": "bogus_job_engine"}}))
    # the documented disable sentinel passes validation
    assert _validate_adapter(
        {"job_segmenter": {"engine": "noop_job_fallback"}}) == []


# ---------------------------------------------------------------------------
# bare-function fallback shims (no active coordinator)
# ---------------------------------------------------------------------------

def test_fallback_shims():
    """[RG-5] with no coordinator active, shims operate on _REGISTRY."""
    assert get_active_coordinator() is None  # _preserve set it None
    reg.register_adapter_config(_VAC, {"adapter_id": "a", "source": "code"})
    assert reg.get_adapter_config(_VAC)["adapter_id"] == "a"
    assert _VAC in reg.get_all_adapter_configs()
    assert reg.get_adapter_value(_VAC, "adapter_id") == "a"
    assert reg.get_adapter_value(_VAC, "missing", fallback="d") == "d"
    reg.unregister_adapter_config(_VAC)
    assert reg.get_adapter_config(_VAC) is None
    reg.register_adapter_config(_VAC, {"adapter_id": "a"})
    reg.clear_registry()
    assert reg.get_all_adapter_configs() == {}


def test_fallback_register_nondict_raises():
    """[RG-5] fallback path also rejects non-dict configs."""
    with pytest.raises(TypeError):
        reg.register_adapter_config(_VAC, "not-a-dict")


# ---------------------------------------------------------------------------
# config_loader
# ---------------------------------------------------------------------------

def test_load_stored_configs(hass):
    """[CL-1]"""
    assert cl.load_stored_adapter_configs(hass, {"adapters": "not-a-dict"}) == 0
    data = {"adapters": {
        _VAC: {"adapter_id": "a", "source": "config"},
        "vacuum.bad": "malformed",   # non-dict → skipped
    }}
    assert cl.load_stored_adapter_configs(hass, data) == 1
    assert reg.get_adapter_config(_VAC)["adapter_id"] == "a"


def test_load_stored_configs_register_raises(hass, monkeypatch):
    """[CL-2] a register failure is logged and skipped, not propagated."""
    def _boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(cl, "register_adapter_config", _boom)
    data = {"adapters": {_VAC: {"adapter_id": "a"}}}
    assert cl.load_stored_adapter_configs(hass, data) == 0


def test_save_delete_get_stored():
    """[CL-3]"""
    data: dict = {}
    cl.save_adapter_config(data, _VAC, {"adapter_id": "a"})
    assert cl.get_stored_adapter_config(data, _VAC)["adapter_id"] == "a"
    assert cl.delete_adapter_config(data, _VAC) is True
    assert cl.get_stored_adapter_config(data, _VAC) is None
    assert cl.delete_adapter_config(data, _VAC) is False


# ---------------------------------------------------------------------------
# config_schema
# ---------------------------------------------------------------------------

def test_schema_shape():
    """[CS-1]"""
    for key in ("adapter_id", "source", "entities", "dispatch"):
        assert key in ADAPTER_CONFIG_SCHEMA
    assert ADAPTER_CONFIG_SCHEMA["adapter_id"]["required"] is True
