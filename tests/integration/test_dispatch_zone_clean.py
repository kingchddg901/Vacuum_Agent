"""Tests for ad-hoc free-form zone cleaning dispatch.

manager.dispatch_zone_clean sends a vacuum.send_command ``zone_clean`` with a bare
``{zones, clean_times}`` payload, riding the generic _dispatch_clean_payload
send-site via a command override. It carries no room ids and never touches the
job/queue/learning store (fire-and-forget).

Coverage targets
----------------
[ZC-1] dispatch_zone_clean sends command=zone_clean with the bare {zones,clean_times} payload + status dict.
[ZC-2] _dispatch_clean_payload command_override replaces the adapter's default command.
[ZC-3] no dispatch.zone_command declared -> ValueError (brand has no zone clean).
[ZC-4] empty zones -> ValueError before any dispatch.
[ZC-5] map_id is accepted (the service auto-resolves it) but is NOT put on the wire.
[ZC-6] a degenerate (near-zero-area) rect is rejected before any dispatch.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config


_VAC = "vacuum.alfred"

_EUFY_DISPATCH = {
    "service_domain": "vacuum",
    "service_name": "send_command",
    "command": "room_clean",
    "zone_command": "zone_clean",
}


def _register(hass, dispatch):
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": dict(dispatch),
    })


def _capture_send(hass):
    calls: list[dict] = []

    async def _send(call):
        calls.append(dict(call.data))

    hass.services.async_register("vacuum", "send_command", _send)
    return calls


async def test_zone_clean_dispatch(hass, manager):
    """[ZC-1] command=zone_clean, bare {zones, clean_times} payload + status dict."""
    _register(hass, _EUFY_DISPATCH)
    calls = _capture_send(hass)
    zones = [[0.05, 0.70, 0.35, 0.95], [0.4, 0.4, 0.6, 0.6]]
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=zones, clean_times=2
    )
    assert calls[0]["command"] == "zone_clean"
    assert calls[0]["params"] == {"zones": zones, "clean_times": 2}
    assert out["status"] == "dispatched"
    assert out["zone_count"] == 2
    assert out["clean_times"] == 2


async def test_command_override(hass, manager):
    """[ZC-2] command_override replaces the adapter's default command verb."""
    _register(hass, _EUFY_DISPATCH)
    calls = _capture_send(hass)
    await manager._dispatch_clean_payload(
        vacuum_entity_id=_VAC,
        payload={"zones": [[0, 0, 1, 1]], "clean_times": 1},
        command_override="zone_clean",
    )
    assert calls[0]["command"] == "zone_clean"


async def test_no_zone_command_raises(hass, manager):
    """[ZC-3] an adapter without dispatch.zone_command rejects zone cleaning."""
    _register(hass, {
        "service_domain": "vacuum", "service_name": "send_command",
        "command": "room_clean",
    })
    _capture_send(hass)
    with pytest.raises(ValueError, match="zone_command"):
        await manager.dispatch_zone_clean(vacuum_entity_id=_VAC, zones=[[0, 0, 1, 1]])


async def test_empty_zones_raises(hass, manager):
    """[ZC-4] no zones -> ValueError before any dispatch."""
    _register(hass, _EUFY_DISPATCH)
    calls = _capture_send(hass)
    with pytest.raises(ValueError, match="at least one zone"):
        await manager.dispatch_zone_clean(vacuum_entity_id=_VAC, zones=[])
    assert calls == []


async def test_map_id_accepted_but_not_sent(hass, manager):
    """[ZC-5] map_id is accepted (auto-resolved by the service) but never sent."""
    _register(hass, _EUFY_DISPATCH)
    calls = _capture_send(hass)
    await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0, 0, 1, 1]], clean_times=1, map_id="3"
    )
    assert "map_id" not in calls[0]["params"]


async def test_degenerate_zone_raises(hass, manager):
    """[ZC-6] a near-zero-area rect is rejected before any dispatch."""
    _register(hass, _EUFY_DISPATCH)
    calls = _capture_send(hass)
    with pytest.raises(ValueError, match="degenerate"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.2, 0.5, 0.2, 0.9]]  # zero width
        )
    assert calls == []
