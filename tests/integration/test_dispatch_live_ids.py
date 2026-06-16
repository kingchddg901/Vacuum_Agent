"""Tests for dispatch-time slug->live segment id resolution (Wave 2b).

For brands whose segment ids renumber on re-segment (Roborock), the framework
re-resolves each target room's name slug to its CURRENT id from a fresh get_maps
right before sending, so a stored id never cleans the wrong room. Stored data is
never touched — only the wire payload is rewritten.

Coverage targets
----------------
[LID-1] flag off -> payload returned unchanged.
[LID-2] flag on -> wire segment ids remapped slug->live; batch scalar untouched.
[LID-3] a target slug absent from the live map is skipped.
[LID-4] an unavailable live source falls back to the stored ids.
[LID-5] params_as_list wraps the wire payload in a list (Roborock app_segment_clean); bare dict by default (Eufy).
[LID-6] live source has rooms but NONE matches a target slug → fall back to the stored payload.
"""

from __future__ import annotations

import pytest

from homeassistant.core import SupportsResponse

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config


_VAC = "vacuum.ivy"
_MAP = "Main floor"

_DISPATCH = {
    "template": "roborock_segment_clean",
    "service_domain": "vacuum",
    "service_name": "send_command",
    "command": "app_segment_clean",
    "rooms_field": "segments",
    "clean_passes_field": "repeat",
    "resolve_live_ids_by_slug": True,
}

_DISCOVERY = {
    "source": "service_response",
    "maps_service": {"domain": "roborock", "service": "get_maps"},
    "maps_rooms_key": "rooms",
    "map_name_key": "name",
    "room_id_key": "segment_id",
    "room_name_key": "name",
}


def _register(hass, *, resolve: bool = True):
    dispatch = dict(_DISPATCH)
    dispatch["resolve_live_ids_by_slug"] = resolve
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_map": "select.ivy_selected_map"},
        "discovery": dict(_DISCOVERY),
        "dispatch": dispatch,
    })
    hass.states.async_set("select.ivy_selected_map", _MAP)


def _register_get_maps(hass, rooms: dict[str, str]):
    async def _get_maps(call):
        return {"maps": [{"flag": 0, "name": _MAP, "rooms": rooms}]}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )


async def test_flag_off_unchanged(hass, manager):
    """[LID-1]"""
    _register(hass, resolve=False)
    _register_get_maps(hass, {"27": "KITCHEN"})
    payload = {"segments": [16], "repeat": 1}
    out = await manager._resolve_live_dispatch_payload(
        vacuum_entity_id=_VAC, map_id=_MAP, payload=payload,
        resolved_rooms=[{"room_id": 16, "slug": "kitchen"}],
    )
    assert out == {"segments": [16], "repeat": 1}


async def test_remaps_to_live_ids(hass, manager):
    """[LID-2] stored ids 16/17 -> live 27/18 via slug; repeat untouched."""
    _register(hass)
    _register_get_maps(hass, {"27": "KITCHEN", "18": "Dining Room"})
    out = await manager._resolve_live_dispatch_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        payload={"segments": [16, 17], "repeat": 2},
        resolved_rooms=[
            {"room_id": 16, "slug": "kitchen"},
            {"room_id": 17, "slug": "dining_room"},
        ],
    )
    assert out["segments"] == [27, 18]
    assert out["repeat"] == 2


async def test_skips_slug_absent_from_live_map(hass, manager):
    """[LID-3] a target whose slug is gone from the current map is dropped."""
    _register(hass)
    _register_get_maps(hass, {"27": "KITCHEN"})  # office not on the map
    out = await manager._resolve_live_dispatch_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        payload={"segments": [16, 19], "repeat": 1},
        resolved_rooms=[
            {"room_id": 16, "slug": "kitchen"},
            {"room_id": 19, "slug": "office"},
        ],
    )
    assert out["segments"] == [27]


async def test_unavailable_source_falls_back_to_stored(hass, manager):
    """[LID-4] no get_maps service registered -> stored ids dispatched."""
    _register(hass)
    # No get_maps service registered: async_refresh swallows the error, the cache
    # stays empty, and the resolver falls back to the stored payload.
    out = await manager._resolve_live_dispatch_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        payload={"segments": [16, 17], "repeat": 1},
        resolved_rooms=[
            {"room_id": 16, "slug": "kitchen"},
            {"room_id": 17, "slug": "dining_room"},
        ],
    )
    assert out["segments"] == [16, 17]


# --- params_as_list wire-shape contract -------------------------------------


async def test_params_list_wrapped(hass, manager):
    """[LID-5] params_as_list -> the payload is LIST-wrapped on the wire
    (Roborock app_segment_clean wants params=[{segments,repeat}])."""
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "dispatch": {
            "service_domain": "vacuum", "service_name": "send_command",
            "command": "app_segment_clean", "params_as_list": True,
        },
    })
    calls: list[dict] = []

    async def _send(call):
        calls.append(dict(call.data))

    hass.services.async_register("vacuum", "send_command", _send)
    await manager._dispatch_clean_payload(
        vacuum_entity_id=_VAC, payload={"segments": [16, 19], "repeat": 2}
    )
    assert calls[0]["command"] == "app_segment_clean"
    assert calls[0]["params"] == [{"segments": [16, 19], "repeat": 2}]


async def test_params_bare_dict_by_default(hass, manager):
    """[LID-5] without params_as_list the payload is the bare dict (Eufy)."""
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": {
            "service_domain": "vacuum", "service_name": "send_command",
            "command": "room_clean",
        },
    })
    calls: list[dict] = []

    async def _send(call):
        calls.append(dict(call.data))

    hass.services.async_register("vacuum", "send_command", _send)
    await manager._dispatch_clean_payload(
        vacuum_entity_id=_VAC, payload={"map_id": "1", "rooms": [{"id": 1}]}
    )
    assert calls[0]["params"] == {"map_id": "1", "rooms": [{"id": 1}]}


async def test_all_targets_absent_falls_back_to_stored(hass, manager):
    """[LID-6] the live source HAS rooms but NONE matches a target slug → no segment
    resolves, so the original stored payload is dispatched unchanged (vs LID-3 where one
    target still resolved and only the missing one was dropped). Guards against a
    zero-room dispatch when every target slug has drifted off the current map."""
    _register(hass)
    _register_get_maps(hass, {"27": "KITCHEN"})   # only kitchen is live; targets are elsewhere
    out = await manager._resolve_live_dispatch_payload(
        vacuum_entity_id=_VAC, map_id=_MAP,
        payload={"segments": [19, 20], "repeat": 1},
        resolved_rooms=[
            {"room_id": 19, "slug": "office"},
            {"room_id": 20, "slug": "lounge"},
        ],
    )
    assert out == {"segments": [19, 20], "repeat": 1}   # stored ids dispatched unchanged
