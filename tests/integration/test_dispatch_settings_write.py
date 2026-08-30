"""Tests for the bulk per-room settings write (Dreame's vacuum_set_custom_cleaning).

Dreame's per-room settings are PERSISTENT DEVICE STATE and the saved store WINS over
the ``vacuum_clean_segment`` payload (settled on hardware 2026-08-10), so the real
per-room control surface is ONE bulk ``vacuum_set_custom_cleaning`` call carrying
index-aligned INT arrays, run while parked just before a BARE segment dispatch. Driven
entirely by ``dispatch.settings_write`` — no brand logic in core. The THIRD pre-dispatch
shape, distinct from ``global_pre_calls`` (one global scalar/run) and
``per_room_live_settings`` (one per-room ENTITY write per room, mid-run).

Coverage
--------
[SW-1] required fields -> aligned INT arrays in one call; value_maps applied; a constant
       field (water_volume) rides a fixed value; the fine water axis (wetness_level, a
       NUMBER-domain field) carries the numeric water_level; segment_id in queued order.
[SW-2] no settings_write declared -> no service call (every other brand).
[SW-3] an empty room field (vacuum-only water) takes the filler, keeping arrays aligned.
[SW-4] a gate_room_suffix field emits ONLY when its per-room entity is registered.
[SW-5] an unmapped value takes the filler, never a stray string on the int wire.
[SW-6] clean_passes is clamped to [1,3].
[SW-7] a failed write is best-effort-LOUD: logs, does NOT raise, the run proceeds.
[SW-8] ordering: settings_write runs before the global pre-calls and the dispatch.
[SW-9] wetness_level: numeric water_level "16"/"26" -> ints; clamp [1,32]; gated on the
       NUMBER entity (gate_domain), omitted when that entity is absent.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.dreame import vocabulary as dv
from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

_VAC = "vacuum.robin"

# Mirrors the real adapter's dispatch.settings_write.fields.
_FIELDS = [
    {"canonical": "fan_speed", "wire": "suction_level",
     "value_map": dv.FAN_SPEED_WIRE_MAP, "required": True, "filler": 0},
    # water_volume is a schema-required CONSTANT filler (device uses wetness instead).
    {"wire": "water_volume", "constant": 2, "required": True},
    # the FINE 1..32 wetness scale — numeric water_level, gated on the NUMBER entity.
    {"canonical": "water_level", "wire": "wetness_level",
     "clamp": [1, 32], "filler": 16,
     "gate_room_suffix": "wetness_level", "gate_domain": "number"},
    {"canonical": "clean_passes", "wire": "repeats",
     "required": True, "filler": 1, "clamp": [1, 3]},
    {"canonical": "clean_mode", "wire": "cleaning_mode",
     "value_map": dv.CLEAN_MODE_WIRE_MAP, "gate_room_suffix": "cleaning_mode", "filler": 0},
    {"canonical": "clean_intensity", "wire": "cleaning_route",
     "value_map": dv.CLEAN_INTENSITY_WIRE_MAP,
     "gate_room_suffix": "cleaning_route", "filler": 1},
]


def _register(hass, *, fields=_FIELDS, settings_write=True):
    dispatch = {
        "template": "dreame_room_clean", "service_domain": "dreame_vacuum",
        "service_name": "vacuum_clean_segment", "command": None,
        "rooms_field": "segments", "clean_passes_field": None,
    }
    if settings_write:
        dispatch["settings_write"] = {
            "domain": "dreame_vacuum", "service": "vacuum_set_custom_cleaning",
            "segment_id_field": "segment_id", "fields": fields,
        }
    register_adapter_config(_VAC, {
        "adapter_id": "dreame", "source": "code", "entities": {}, "dispatch": dispatch,
    })


def _capture(hass, *, gate_rooms=(1, 2, 3),
             gate_suffixes=("cleaning_mode", "cleaning_route"), wetness=True):
    """Register the bulk service (records call data) + the per-room gate entities.

    A gated field emits only when its per-room entity is REGISTERED (probed on the first
    queued room). select-domain gates use ``select.<obj>_room_N_<suffix>``; the wetness
    axis is a NUMBER entity. Entities are set ``unavailable`` on purpose — registered-
    but-UI-unavailable still means the device is capable (the bulk call bypasses the
    UI gate). Narrow the args to model a device missing a capability.
    """
    hass.states.async_set(_VAC, "docked")
    obj = _VAC.split(".", 1)[-1]
    for rid in gate_rooms:
        for suffix in gate_suffixes:
            hass.states.async_set(f"select.{obj}_room_{rid}_{suffix}", "unavailable")
        if wetness:
            hass.states.async_set(f"number.{obj}_room_{rid}_wetness_level", "16")

    calls: list[dict] = []

    async def _set_custom(call):
        calls.append(dict(call.data))

    hass.services.async_register(
        "dreame_vacuum", "vacuum_set_custom_cleaning", _set_custom
    )
    return calls


async def test_bulk_write_builds_aligned_arrays(hass, manager):
    """[SW-1] one call, aligned INT arrays; constant water_volume; numeric wetness."""
    _register(hass)
    calls = _capture(hass)
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"room_id": 1, "fan_speed": "quiet", "water_level": "",
             "clean_passes": 1, "clean_mode": "vacuum", "clean_intensity": "standard"},
            {"room_id": 3, "fan_speed": "turbo", "water_level": "26",
             "clean_passes": 2, "clean_mode": "vacuum_mop", "clean_intensity": "deep"},
        ],
    )
    assert calls == [{
        "entity_id": _VAC,
        "segment_id": [1, 3],
        "suction_level": [0, 3],       # quiet->0, turbo->3
        "water_volume": [2, 2],        # constant filler (device uses wetness)
        "wetness_level": [16, 26],     # room1 "" -> filler 16; room3 "26" -> 26
        "repeats": [1, 2],
        "cleaning_mode": [0, 2],       # vacuum->0, vacuum_mop->2
        "cleaning_route": [1, 3],      # standard->1, deep->3
    }]


async def test_no_settings_write_no_call(hass, manager):
    """[SW-2] absent config -> no service call (every brand but Dreame)."""
    _register(hass, settings_write=False)
    calls = _capture(hass)
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"room_id": 1, "fan_speed": "standard", "clean_passes": 1}],
    )
    assert calls == []


async def test_empty_field_takes_filler(hass, manager):
    """[SW-3] a vacuum-only room's empty water/fan/intensity take the filler, aligned."""
    _register(hass)
    calls = _capture(hass)
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"room_id": 2, "fan_speed": "", "water_level": None,
             "clean_passes": 1, "clean_mode": "vacuum", "clean_intensity": ""},
        ],
    )
    assert calls[0]["suction_level"] == [0]     # empty fan -> filler 0
    assert calls[0]["water_volume"] == [2]      # constant
    assert calls[0]["wetness_level"] == [16]    # None water -> filler 16
    assert calls[0]["cleaning_route"] == [1]    # empty intensity -> filler 1


async def test_gated_field_omitted_when_entity_absent(hass, manager):
    """[SW-4] cleaning_route is omitted when its per-room entity isn't registered."""
    _register(hass)
    calls = _capture(hass, gate_suffixes=("cleaning_mode",))  # no _cleaning_route entity
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{
            "room_id": 1, "fan_speed": "standard", "water_level": "16",
            "clean_passes": 1, "clean_mode": "mop", "clean_intensity": "deep",
        }],
    )
    assert "cleaning_route" not in calls[0]     # gated off (entity absent)
    assert calls[0]["cleaning_mode"] == [1]     # gate present -> emitted; mop -> 1


async def test_unmapped_value_takes_filler(hass, manager):
    """[SW-5] a value not in the value_map takes the filler, never a stray string."""
    _register(hass)
    calls = _capture(hass)
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{
            "room_id": 1, "fan_speed": "Boost",      # not in FAN_SPEED_WIRE_MAP
            "water_level": "16", "clean_passes": 1,
            "clean_mode": "vacuum", "clean_intensity": "standard",
        }],
    )
    assert calls[0]["suction_level"] == [0]     # "Boost" unmapped -> filler 0
    assert all(isinstance(v, int) for v in calls[0]["suction_level"])


async def test_clean_passes_clamped(hass, manager):
    """[SW-6] clean_passes is clamped to [1,3]."""
    _register(hass)
    calls = _capture(hass)
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"room_id": 1, "fan_speed": "standard", "water_level": "16",
             "clean_passes": 9, "clean_mode": "vacuum", "clean_intensity": "standard"},
            {"room_id": 3, "fan_speed": "standard", "water_level": "16",
             "clean_passes": 0, "clean_mode": "vacuum", "clean_intensity": "standard"},
        ],
    )
    assert calls[0]["repeats"] == [3, 1]        # 9 -> 3, 0 -> 1


async def test_failed_write_does_not_raise(hass, manager):
    """[SW-7] a failed bulk write is best-effort-LOUD: logs, does NOT raise."""
    _register(hass)
    _capture(hass)     # registers gates + docked; its recorder is replaced next
    async def _boom(call):
        raise RuntimeError("HTTP 500")
    hass.services.async_register("dreame_vacuum", "vacuum_set_custom_cleaning", _boom)

    # Must NOT raise — the run proceeds on the device's stored settings.
    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{
            "room_id": 1, "fan_speed": "standard", "water_level": "16",
            "clean_passes": 1, "clean_mode": "vacuum", "clean_intensity": "standard",
        }],
    )


_WET_ROOMS = [
    {"room_id": 1, "fan_speed": "standard", "water_level": "40",   # over max -> 32
     "clean_passes": 1, "clean_mode": "vacuum_mop", "clean_intensity": "standard"},
    {"room_id": 3, "fan_speed": "standard", "water_level": "16",
     "clean_passes": 1, "clean_mode": "vacuum_mop", "clean_intensity": "standard"},
]


async def test_wetness_numeric_and_clamped(hass, manager):
    """[SW-9a] numeric water_level -> ints on the wetness_level wire, clamped to [1,32]."""
    _register(hass)
    calls = _capture(hass)
    await manager._run_settings_write(vacuum_entity_id=_VAC, resolved_rooms=_WET_ROOMS)
    assert calls[0]["wetness_level"] == [32, 16]           # "40" clamps to 32, "16" -> 16
    assert all(isinstance(v, int) for v in calls[0]["wetness_level"])


async def test_wetness_gated_on_number_entity(hass, manager):
    """[SW-9b] wetness_level is dropped when its NUMBER entity is absent (gate_domain).

    A fresh hass with NO number.<obj>_room_N_wetness_level registered. The gate probes
    the NUMBER domain; a select-domain probe would miss the number entity and drop the
    field on every device, so this pins the domain."""
    _register(hass)
    calls = _capture(hass, wetness=False)
    await manager._run_settings_write(vacuum_entity_id=_VAC, resolved_rooms=_WET_ROOMS)
    assert "wetness_level" not in calls[0]
    assert calls[0]["water_volume"] == [2, 2]              # constant still present


def test_settings_write_runs_before_pre_calls_and_dispatch():
    """[SW-8] settings_write must precede the global pre-calls and the dispatch, or the
    saved store is written after (or not before) the run it configures.

    Read off the real start path rather than a stub sequence — a mock-driven ordering
    test passes just as happily when the production order is wrong (mirrors GPC-11)."""
    import inspect

    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    src = inspect.getsource(EufyVacuumManager.start_selected_rooms)
    settings_at = src.index("await self._run_settings_write(")
    pre_calls_at = src.index("await self._run_global_pre_calls(")
    dispatch_at = src.index("await self._dispatch_clean_payload(")

    assert settings_at < pre_calls_at, (
        "settings_write must run before the global pre-calls"
    )
    assert pre_calls_at < dispatch_at, (
        "pre-calls (and the settings write before them) must precede dispatch"
    )
