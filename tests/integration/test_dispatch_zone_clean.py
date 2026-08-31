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
[ZC-16] Eufy side caps declared but no live map -> ValueError, no dispatch (RP-022/ZONE-4 -- was a skip).
[ZC-17] supports_zone_clean: false -> ValueError, no dispatch (RP-022/ZONE-2 -- dispatch itself now checks it).
[ZC-18] Eufy (non-device_mm) branch: a zone_max_area_m2 bound is now enforced there too (RP-022 item 2).
[ZC-19] Eufy: supports_zone_repeat: false overrides an otherwise-valid declared cap (RP-022/Q12).
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
    """[ZC-1] command=zone_clean, bare {zones, clean_times} payload + status dict.
    RP-022/Q12: no capabilities registered at all means no zone_passes_max/
    passes_max declared either, so clean_times normalizes to 1 (the non-device_mm
    branch has no safe repeat default to fall back to — was previously verbatim)."""
    _register(hass, _EUFY_DISPATCH)
    calls = _capture_send(hass)
    zones = [[0.05, 0.70, 0.35, 0.95], [0.4, 0.4, 0.6, 0.6]]
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=zones, clean_times=2
    )
    assert calls[0]["command"] == "zone_clean"
    assert calls[0]["params"] == {"zones": zones, "clean_times": 1}
    assert out["status"] == "dispatched"
    assert out["zone_count"] == 2
    assert out["clean_times"] == 1


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
    """[ZC-3] an adapter with NEITHER dispatch.zone_command NOR a dedicated `zone` block
    rejects zone cleaning (message widened when the dedicated-service shape was added)."""
    _register(hass, {
        "service_domain": "vacuum", "service_name": "send_command",
        "command": "room_clean",
    })
    _capture_send(hass)
    with pytest.raises(ValueError, match="no zone service"):
        await manager.dispatch_zone_clean(vacuum_entity_id=_VAC, zones=[[0, 0, 1, 1]])


async def test_supports_zone_clean_false_refuses(hass, manager):
    """[ZC-17] RP-022/ZONE-2: dispatch_zone_clean previously never consulted
    supports_zone_clean at all -- only the card did, so a direct service call or
    automation reached the device even when the brand declares it unsupported."""
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": dict(_EUFY_DISPATCH),
        "capabilities": {"supports_zone_clean": False},
    })
    calls = _capture_send(hass)
    with pytest.raises(ValueError, match="supports_zone_clean"):
        await manager.dispatch_zone_clean(vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.5, 0.5]])
    assert calls == []


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


async def test_eufy_zone_area_bound_enforced(hass, manager, monkeypatch):
    """[ZC-18] RP-022 item 2: a zone_max_area_m2 bound is now enforced on the
    Eufy (non-device_mm) branch too -- previously area bounds only existed
    inside the device_mm branch, so a bound declared here was silently never
    checked regardless of how large the zone was. Map 360x300 @res 5 = 18x15 m;
    a 0.5x0.5 rect = 9x7.5 m = 67.5 m^2, far over the 3.0 m^2 cap."""
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": dict(_EUFY_DISPATCH),
        "capabilities": {"zone_max_area_m2": 3.0},
    })
    calls = _capture_send(hass)
    _stub_map_dims(manager, monkeypatch, 360, 300, 5)
    with pytest.raises(ValueError, match="too large"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.6, 0.6]]
        )
    assert calls == []


async def test_eufy_zone_repeat_explicit_unsupported(hass, manager, monkeypatch):
    """[ZC-19] Q12 explicit override: an adapter that DOES declare a repeat cap
    but also sets supports_zone_repeat: false still normalizes to 1 -- the
    explicit flag wins over a declared cap, distinct from ZC-1's "no cap
    declared at all" path."""
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "dispatch": {**_EUFY_DISPATCH, "zone_passes_max": 2},
        "capabilities": {"supports_zone_repeat": False},
    })
    calls = _capture_send(hass)
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.5, 0.5]], clean_times=2
    )
    assert calls[0]["params"]["clean_times"] == 1
    assert out["clean_times"] == 1


async def test_eufy_zone_side_check_skipped_without_map(hass, manager, monkeypatch):
    """[ZC-16] RP-022/ZONE-4: with side caps declared but NO live map, the check now
    REFUSES — parity with the device_mm branch's own refusal for the identical
    "can't validate the geometry" situation. Previously degraded to a silent skip
    (dispatched unchecked); a zone that WOULD be too long if dims were known must
    not ship blind."""
    _register_eufy_caps(hass)
    calls = _capture_send(hass)

    async def _no_md(**_kw):
        return None
    monkeypatch.setattr(manager, "async_get_map_data_dict", _no_md, raising=False)
    with pytest.raises(ValueError, match="no live map"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.1, 0.1, 0.8, 0.3]]
        )
    assert calls == []


# --- Dreame DEDICATED-service branch (vacuum_clean_zone) ----------------------
# Unlike Roborock/Eufy (a send_command verb), Dreame's zone is its own service, so the
# adapter declares a top-level `zone` block (like `goto`). The MapData is the Dreame SHAPE
# (`.dimensions` grid + `.segments`, no `.image`/`.rooms`), projected through the real
# _dreame_projector — NO mock projector — and the offset comes from map_state_source.

class _DrDims:
    grid_size = 50.0
    top = 0.0
    left = 0.0
    width = 100
    height = 100


class _DrSeg:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _DreameMapData:
    # 5 m grid; corners kept off the edge so none project out-of-grid (the -1 in the
    # projector nudges the far edge just negative).
    dimensions = _DrDims()
    segments = {
        1: _DrSeg(100, 100, 2400, 2400),
        2: _DrSeg(2600, 2600, 4900, 4900),
    }


_DR_ZONE = {
    "service_domain": "dreame_vacuum",
    "service_name": "vacuum_clean_zone",
    "zone_coords": "device_mm",
    "zone_field": "zone",
    "repeats_field": "repeats",
    "zone_passes_max": 2,
    # A zone is a GLOBAL clean: settings are pre-set on the device's global entities
    # (ungated by flipping the customized-cleaning switch off), verified by readback, then
    # the bare zone runs; the prior state is restored at zone completion.
    "global_precall": {
        "gate_switch_suffix": "customized_cleaning",
        "restore_gate": True,
        "settings": [
            {"key": "suction", "label": "Suction", "entity_suffix": "suction_level",
             "options": [{"value": "strong", "label": "Intense"}], "default": "standard"},
            {"key": "water", "label": "Water", "entity_suffix": "wetness_level",
             "domain": "number", "service": "set_value", "value_field": "value",
             "options": [{"value": "wet", "label": "Wet"}],
             "value_map": {"slightly_dry": 8, "moist": 16, "wet": 27}, "default": "moist"},
        ],
    },
}


def _wire_precall(hass):
    """Register fake select/number/switch services that UPDATE their entity state (so the
    readback sees the set take), plus the zone service — and capture every call in order."""
    calls: list[tuple[str, dict]] = []

    async def _sel(call):
        calls.append(("select", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], call.data["option"])

    async def _num(call):
        calls.append(("number", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], str(call.data["value"]))

    async def _swon(call):
        calls.append(("switch_on", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], "on")

    async def _swoff(call):
        calls.append(("switch_off", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], "off")

    async def _zone(call):
        calls.append(("zone", dict(call.data)))

    hass.services.async_register("select", "select_option", _sel)
    hass.services.async_register("number", "set_value", _num)
    hass.services.async_register("switch", "turn_on", _swon)
    hass.services.async_register("switch", "turn_off", _swoff)
    hass.services.async_register("dreame_vacuum", "vacuum_clean_zone", _zone)
    return calls


def _register_dreame(hass, *, offset=(0, 0)):
    register_adapter_config(_VAC, {
        "adapter_id": "dreame", "source": "code",
        # room-clean is a DIFFERENT service; the dedicated zone block must win over it.
        "dispatch": {"service_domain": "dreame_vacuum",
                     "service_name": "vacuum_clean_segment", "command": None},
        "zone": dict(_DR_ZONE),
        "map_state_source": {"backend": "camera_attrs", "map_frame_offset_mm": list(offset)},
        "capabilities": {"supports_zone_clean": True},
    })


def _capture_dreame_zone(hass):
    calls: list[dict] = []

    async def _svc(call):
        calls.append(dict(call.data))

    hass.services.async_register("dreame_vacuum", "vacuum_clean_zone", _svc)
    return calls


async def test_dreame_zone_dedicated_service_shape(hass, manager, monkeypatch):
    """[ZC-DR-1] Dreame routes to its OWN service dreame_vacuum.vacuum_clean_zone with
    `zone`=[[x0,y0,x1,y1]] (4-tuple int mm, NOT the 5-tuple) + a separate `repeats` int —
    NOT vacuum_clean_segment via a command override. BITE: the old command-override path
    would call vacuum_clean_segment and never register a vacuum_clean_zone call."""
    _register_dreame(hass)
    calls = _capture_dreame_zone(hass)
    _stub_map_source(manager, monkeypatch, _DreameMapData())
    out = await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], clean_times=2
    )
    assert len(calls) == 1
    d = calls[0]
    assert d["entity_id"] == _VAC
    assert d["repeats"] == 2                       # honored up to zone_passes_max
    zone = d["zone"]
    assert isinstance(zone, list) and len(zone) == 1 and len(zone[0]) == 4  # 4-tuple, not 5
    x0, y0, x1, y1 = zone[0]
    # nx 0.3/0.5 -> mm 1500/2500 ; ny 0.3/0.5 -> mm 3499/2499 (Y-flip), min/max ordered.
    assert x0 == pytest.approx(1500, abs=2) and x1 == pytest.approx(2500, abs=2)
    assert y0 == pytest.approx(2499, abs=2) and y1 == pytest.approx(3499, abs=2)
    assert out["zone_count"] == 1


async def test_dreame_zone_carries_the_frame_offset(hass, monkeypatch, manager):
    """[ZC-DR-2] the map_frame_offset_mm the render applies MUST reach the correspondences,
    or the box cleans ~offset away. With offset [500,0] the SAME drawn box inverts to a
    mm rect shifted -500 in x. BITE: the old bare correspondences_from_mapdata(map_obj)
    call ignored the offset and would report x0≈1500, not 1000."""
    _register_dreame(hass, offset=(500, 0))
    calls = _capture_dreame_zone(hass)
    _stub_map_source(manager, monkeypatch, _DreameMapData())
    await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], clean_times=1
    )
    x0, _y0, x1, _y1 = calls[0]["zone"][0]
    assert x0 == pytest.approx(1000, abs=2)        # 1500 - 500 offset
    assert x1 == pytest.approx(2000, abs=2)        # 2500 - 500 offset


async def test_dreame_zone_no_map_refuses(hass, manager, monkeypatch):
    """[ZC-DR-3] dedicated path with no live map -> refuse (ValueError), nothing sent."""
    _register_dreame(hass)
    calls = _capture_dreame_zone(hass)
    _stub_map_source(manager, monkeypatch, None)
    with pytest.raises(ValueError, match="no live map"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]]
        )
    assert calls == []


async def test_dreame_goto_dispatch_shares_the_offset_helper(hass, manager, monkeypatch):
    """[GOTO-DR-1] dispatch_goto routes to dreame_vacuum.vacuum_goto with x/y = the
    offset-corrected device-mm of the tapped point, through the SAME _live_correspondences
    helper zone uses (locks the refactor that extracted it). offset [500,0]: nx 0.4 -> x
    0.4*5000-500=1500 ; ny 0.4 -> y 4999-0.4*5000=2999. BITE: a bare (offset-less) build
    would send x≈2000."""
    register_adapter_config(_VAC, {
        "adapter_id": "dreame", "source": "code",
        "dispatch": {"service_domain": "dreame_vacuum",
                     "service_name": "vacuum_clean_segment", "command": None},
        "goto": {"service_domain": "dreame_vacuum", "service_name": "vacuum_goto",
                 "x_field": "x", "y_field": "y"},
        "map_state_source": {"backend": "camera_attrs", "map_frame_offset_mm": [500, 0]},
        "capabilities": {"supports_path_control": True},
    })
    calls: list[dict] = []

    async def _svc(call):
        calls.append(dict(call.data))

    hass.services.async_register("dreame_vacuum", "vacuum_goto", _svc)
    _stub_map_source(manager, monkeypatch, _DreameMapData())
    await manager.dispatch_goto(vacuum_entity_id=_VAC, point=[0.4, 0.4])
    assert len(calls) == 1
    assert calls[0]["entity_id"] == _VAC
    assert calls[0]["x"] == pytest.approx(1500, abs=3)
    assert calls[0]["y"] == pytest.approx(2999, abs=3)


async def test_dreame_zone_global_precall_flips_sets_reads_executes(hass, manager, monkeypatch):
    """[ZC-DR-4] a zone WITH settings runs the GLOBAL precall: flip customized_cleaning OFF
    (ungates the globals), set the global suction SELECT + wetness NUMBER, read them back,
    THEN execute the bare zone. suction 'strong' -> option 'strong'; water 'wet' ->
    number.<obj>_wetness_level 27 (value_map). BITE: the old params path put suction_level
    in the zone call and never touched the gate/selects."""
    _register_dreame(hass)
    _stub_map_source(manager, monkeypatch, _DreameMapData())
    hass.states.async_set("switch.alfred_customized_cleaning", "on")
    hass.states.async_set("vacuum.alfred", "docked")
    calls = _wire_precall(hass)
    await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]],
        settings={"suction": "strong", "water": "wet"},
    )
    kinds = [c[0] for c in calls]
    assert kinds.index("switch_off") < kinds.index("zone")       # gate flipped BEFORE execute
    sel = next(d for k, d in calls if k == "select")
    assert sel["entity_id"] == "select.alfred_suction_level" and sel["option"] == "strong"
    num = next(d for k, d in calls if k == "number")
    assert num["entity_id"] == "number.alfred_wetness_level" and num["value"] == 27
    assert "zone" in kinds                                        # executed after readback OK


async def test_dreame_zone_global_precall_readback_mismatch_refuses(hass, manager, monkeypatch):
    """[ZC-DR-5] a global setting that does NOT read back as set -> REFUSE (never clean with
    unconfirmed settings) and restore the gate. Nothing executed."""
    _register_dreame(hass)
    _stub_map_source(manager, monkeypatch, _DreameMapData())
    hass.states.async_set("switch.alfred_customized_cleaning", "on")
    calls: list[tuple[str, dict]] = []

    async def _sel_wrong(call):     # sets a value OTHER than requested -> readback fails
        calls.append(("select", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], "quiet")

    async def _swon(call):
        calls.append(("switch_on", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], "on")

    async def _swoff(call):
        calls.append(("switch_off", dict(call.data)))
        hass.states.async_set(call.data["entity_id"], "off")

    async def _zone(call):
        calls.append(("zone", dict(call.data)))

    hass.services.async_register("select", "select_option", _sel_wrong)
    hass.services.async_register("switch", "turn_on", _swon)
    hass.services.async_register("switch", "turn_off", _swoff)
    hass.services.async_register("dreame_vacuum", "vacuum_clean_zone", _zone)
    with pytest.raises(ValueError, match="did not take"):
        await manager.dispatch_zone_clean(
            vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], settings={"suction": "strong"},
        )
    kinds = [c[0] for c in calls]
    assert "zone" not in kinds        # refused — never executed
    assert "switch_on" in kinds       # gate restored on refuse


async def test_dreame_zone_global_precall_restores_at_completion(hass, manager, monkeypatch):
    """[ZC-DR-6] the prior state is restored RIGHT AT ZONE COMPLETION, not before: the gate
    stays OFF while the robot runs, and flips back ON only after it starts (cleaning) and
    returns (docked) — so per-room room cleans work again afterward."""
    _register_dreame(hass)
    _stub_map_source(manager, monkeypatch, _DreameMapData())
    hass.states.async_set("switch.alfred_customized_cleaning", "on")
    hass.states.async_set("vacuum.alfred", "docked")
    calls = _wire_precall(hass)
    await manager.dispatch_zone_clean(
        vacuum_entity_id=_VAC, zones=[[0.3, 0.3, 0.5, 0.5]], settings={"suction": "strong"},
    )
    kinds = [c[0] for c in calls]
    assert "switch_off" in kinds and "switch_on" not in kinds    # gate off, NOT yet restored
    calls.clear()
    # Simulate the run: the pre-clean docked state must NOT trigger restore; only docked
    # AFTER an active state does.
    hass.states.async_set("vacuum.alfred", "cleaning")
    await hass.async_block_till_done()
    assert "switch_on" not in [c[0] for c in calls]              # still running
    hass.states.async_set("vacuum.alfred", "docked")
    await hass.async_block_till_done()
    assert "switch_on" in [c[0] for c in calls]                  # restored at completion
