"""Tests for services/_common.py — the shared map_id auto-resolver.

resolved_call_data substitutes the vacuum's active map when the caller omits
map_id, reading the adapter's declared active_map entity.

Coverage targets
----------------
[SC-1]  map_id already present → returned unchanged.
[SC-2]  no vacuum_entity_id → returned unchanged.
[SC-3]  map_id omitted → resolved from the active_map entity state.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.services._common import resolved_call_data


_VAC = "vacuum.alfred"


class _Call:
    def __init__(self, data):
        self.data = data


def test_resolved_passthrough_map_id(hass):
    """[SC-1]"""
    out = resolved_call_data(hass, _Call({"vacuum_entity_id": _VAC, "map_id": "6"}))
    assert out["map_id"] == "6"


def test_resolved_no_vacuum(hass):
    """[SC-2]"""
    out = resolved_call_data(hass, _Call({"foo": "bar"}))
    assert out == {"foo": "bar"}


def test_resolved_active_map(hass):
    """[SC-3]"""
    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_map"}})
    hass.states.async_set("sensor.alfred_map", "9")
    out = resolved_call_data(hass, _Call({"vacuum_entity_id": _VAC}))
    assert out["map_id"] == "9"
