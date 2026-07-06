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
[ZC-7] zone_coords=device_mm (Roborock): converts the drawn rects to device mm via the
       live map + sends app_zoned_clean params=[[x0,y0,x1,y1,repeat],...] (NOT re-wrapped
       despite the adapter's params_as_list).
[ZC-8] device_mm with no live map available -> ValueError, no dispatch (refuse).
[ZC-9] device_mm where the projection can't be validated -> ValueError, no dispatch.
[ZC-10] more zones than the brand's capabilities.zone_max -> ValueError, no dispatch.
[ZC-11] a zone larger than zone_max_area_m2 (device mm²) -> ValueError, no dispatch.
[ZC-12] a zone smaller than zone_min_area_m2 -> ValueError, no dispatch.
[ZC-13] Eufy per-side: a side over zone_max_side_m -> ValueError, no dispatch.
[ZC-14] Eufy per-side: a side under zone_min_side_m -> ValueError, no dispatch.
[ZC-15] Eufy zone within the per-side bounds -> dispatches the 0-1 rect verbatim.
[ZC-16] Eufy side caps declared but no live map -> check skipped (dispatches, no false refuse).
"""

from __future__ import annotations

import types

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


# --- Roborock device-mm branch (app_zoned_clean) -----------------------------
# A fake parser MapData whose to_img is a known Y-flipped affine (mm -> px), so the
# drawn 0-1 rect inverts to a predictable mm box. Mirrors test_zone_dispatch's fixture.
_RB_DISPATCH = {
    "service_domain": "vacuum",
    "service_name": "send_command",
    "command": "app_segment_clean",
    "zone_command": "app_zoned_clean",
    "zone_coords": "device_mm",
    "params_as_list": True,  # the segment path sets this; zone must NOT double-wrap
}
_RB_CAPS = {"zone_max": 5, "zone_min_area_m2": 0.0929, "zone_max_area_m2": 3.05}


def _register_rb(hass):
    register_adapter_config(_VAC, {
        "adapter_id": "roborock", "source": "code",
        "dispatch": dict(_RB_DISPATCH),
        "capabilities": dict(_RB_CAPS),
    })


class _FP:
    def __init__(self, x, y):
        self.x, self.y = x, y


class _FakeDims:
    rotation = 0

    def to_img(self, pt):  # mm 0..5000 -> px 0..1000, Y-flipped (a realistic 5 m map)
        return _FP(pt.x * 1000 / 5000.0, (5000 - pt.y) * 1000 / 5000.0)


class _FakeImage:
    dimensions = _FakeDims()
    data = types.SimpleNamespace(size=(1000, 1000))


class _FakeRoom:
    def __init__(self, n, x0, y0, x1, y1):
        self.number, self.name = n, None
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _FakeMapData:
    image = _FakeImage()
    rooms = {
        1: _FakeRoom(1, 0, 0, 2500, 2500),
        2: _FakeRoom(2, 2500, 2500, 5000, 5000),
    }


def _stub_map_source(manager, monkeypatch, obj):
    monkeypatch.setattr(
        manager, "map_source",
        types.SimpleNamespace(get_live_mapdata_obj=lambda **kw: obj),
        raising=False,
    )


async def test_zone_clean_device_mm(hass, manager, monkeypatch):
    """[ZC-7] device_mm converts via the live map and sends app_zoned_clean with
    params=[[x0,y0,x1,y1,repeat],...] in mm — a single list, NOT re-wrapped."""
    _register_rb(hass)
    calls = _capture_send(hass)
    _stub_map_source(manager, monkeypatch, _FakeMapData())
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], clean_times=2
    )
    assert calls[0]["command"] == "app_zoned_clean"
    params = calls[0]["params"]
    assert isinstance(params, list) and len(params) == 1  # one zone, not double-wrapped
    assert params[0] == [1500, 2500, 2500, 3500, 2]       # mm (1 m² zone), min/max-ordered
    assert out["zone_count"] == 1


async def test_zone_clean_device_mm_repeat_honors_adapter_max(hass, manager, monkeypatch):
    """[ZC-10] The per-zone repeat cap is adapter-driven, not a hardcoded 3. A brand
    declaring dispatch.zone_passes_max honors clean_times up to that max — regression
    for the old `min(clean_times, 3)` that collapsed any >3-repeat brand."""
    register_adapter_config(_VAC, {
        "adapter_id": "roborock", "source": "code",
        "dispatch": {**_RB_DISPATCH, "zone_passes_max": 5},
        "capabilities": dict(_RB_CAPS),
    })
    calls = _capture_send(hass)
    _stub_map_source(manager, monkeypatch, _FakeMapData())
    await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], clean_times=5
    )
    assert calls[0]["params"][0][-1] == 5  # repeat honored, NOT clamped to 3


async def test_zone_clean_device_mm_repeat_defaults_to_3(hass, manager, monkeypatch):
    """[ZC-11] With no adapter zone-repeat cap declared, repeat defaults to 3
    (backward-compatible; covers Eufy 1-2 and Roborock 1-3)."""
    _register_rb(hass)  # neither zone_passes_max nor passes_max
    calls = _capture_send(hass)
    _stub_map_source(manager, monkeypatch, _FakeMapData())
    await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], clean_times=9
    )
    assert calls[0]["params"][0][-1] == 3  # clamped to the default max


async def test_zone_clean_device_mm_no_map_refuses(hass, manager, monkeypatch):
    """[ZC-8] device_mm with no live map -> refuse (ValueError), nothing dispatched."""
    _register_rb(hass)
    calls = _capture_send(hass)
    _stub_map_source(manager, monkeypatch, None)
    with pytest.raises(ValueError, match="no live map"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.25, 0.25, 0.75, 0.75]]
        )
    assert calls == []


async def test_zone_clean_device_mm_unvalidatable_refuses(hass, manager, monkeypatch):
    """[ZC-9] device_mm where the map yields no usable projection -> refuse."""
    _register_rb(hass)
    calls = _capture_send(hass)

    class _NoRooms:
        image = _FakeImage()
        rooms = None

    _stub_map_source(manager, monkeypatch, _NoRooms())
    with pytest.raises(ValueError, match="refusing to dispatch|projection failed"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.25, 0.25, 0.75, 0.75]]
        )
    assert calls == []


async def test_zone_count_cap(hass, manager, monkeypatch):
    """[ZC-10] more zones than the brand's zone_max -> ValueError before any dispatch."""
    _register_rb(hass)  # zone_max = 5
    calls = _capture_send(hass)
    six = [[0.1 * i, 0.1, 0.1 * i + 0.05, 0.15] for i in range(6)]
    with pytest.raises(ValueError, match="too many zones"):
        await manager.dispatch_zone_clean(vacuum_entity_id=_VAC, zones=six)
    assert calls == []


async def test_zone_too_large_refuses(hass, manager, monkeypatch):
    """[ZC-11] a zone over zone_max_area_m2 -> ValueError, nothing dispatched."""
    _register_rb(hass)
    calls = _capture_send(hass)
    _stub_map_source(manager, monkeypatch, _FakeMapData())
    # [0.1..0.9] of a 5 m map = 4 m x 4 m = 16 m2 > 3.05.
    with pytest.raises(ValueError, match="too large"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.9, 0.9]]
        )
    assert calls == []


async def test_zone_too_small_refuses(hass, manager, monkeypatch):
    """[ZC-12] a zone under zone_min_area_m2 -> ValueError, nothing dispatched."""
    _register_rb(hass)
    calls = _capture_send(hass)
    _stub_map_source(manager, monkeypatch, _FakeMapData())
    # [0.4..0.43] of a 5 m map = 0.15 m x 0.15 m = 0.0225 m2 < 0.0929.
    with pytest.raises(ValueError, match="too small"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.4, 0.4, 0.43, 0.43]]
        )
    assert calls == []


# --- Eufy per-SIDE bounds (verbatim branch) ----------------------------------
# Eufy ships the 0-1 rects verbatim; the per-SIDE cap (0.5-10 m) is checked against the
# live map dims via the fork's own de-normalization (side_m = Δnorm * dim * res / 100).
_EUFY_SIDE_CAPS = {"zone_max": 10, "zone_min_side_m": 0.5, "zone_max_side_m": 10.0}


def _register_eufy_caps(hass):
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": dict(_EUFY_DISPATCH),
        "capabilities": dict(_EUFY_SIDE_CAPS),
    })


def _stub_map_dims(manager, monkeypatch, width, height, res):
    async def _md(**_kw):
        return {"width": width, "height": height, "resolution": res}
    monkeypatch.setattr(manager, "async_get_map_data_dict", _md, raising=False)


async def test_eufy_zone_side_too_long_refuses(hass, manager, monkeypatch):
    """[ZC-13] Eufy: a side over zone_max_side_m -> ValueError, nothing dispatched.
    Map 360x300 @res 5 = 18x15 m; a 0.7-wide rect = 12.6 m > 10 m."""
    _register_eufy_caps(hass)
    calls = _capture_send(hass)
    _stub_map_dims(manager, monkeypatch, 360, 300, 5)
    with pytest.raises(ValueError, match="too long"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.8, 0.3]]
        )
    assert calls == []


async def test_eufy_zone_side_too_short_refuses(hass, manager, monkeypatch):
    """[ZC-14] Eufy: a side under zone_min_side_m -> ValueError, nothing dispatched.
    Map 360x300 @res 5; a 0.02-wide rect = 0.36 m < 0.5 m (still above the degenerate floor)."""
    _register_eufy_caps(hass)
    calls = _capture_send(hass)
    _stub_map_dims(manager, monkeypatch, 360, 300, 5)
    with pytest.raises(ValueError, match="too short"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.10, 0.10, 0.12, 0.40]]
        )
    assert calls == []


async def test_eufy_zone_side_within_bounds_dispatches(hass, manager, monkeypatch):
    """[ZC-15] Eufy: a zone with both sides in [0.5, 10] m dispatches the 0-1 rect verbatim."""
    _register_eufy_caps(hass)
    calls = _capture_send(hass)
    _stub_map_dims(manager, monkeypatch, 360, 300, 5)
    # 0.3 wide = 5.4 m, 0.3 tall = 4.5 m -> both inside the bounds.
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.6, 0.6]]
    )
    assert calls[0]["command"] == "zone_clean"
    assert calls[0]["params"] == {"zones": [[0.3, 0.3, 0.6, 0.6]], "clean_times": 1}
    assert out["zone_count"] == 1


async def test_eufy_zone_side_check_skipped_without_map(hass, manager, monkeypatch):
    """[ZC-16] with side caps declared but NO live map, the check degrades to skip (the card
    validates at draw time) — the zone still dispatches rather than falsely refusing."""
    _register_eufy_caps(hass)
    calls = _capture_send(hass)

    async def _no_md(**_kw):
        return None
    monkeypatch.setattr(manager, "async_get_map_data_dict", _no_md, raising=False)
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.8, 0.3]]  # would be too long IF dims known
    )
    assert calls[0]["command"] == "zone_clean"
    assert out["zone_count"] == 1
