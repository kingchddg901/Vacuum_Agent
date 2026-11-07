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

WHY THE NUMBERING JUMPS FROM SW-9b TO SW-14, since it looks like a mistake: the
`SW-` prefix is shared by THREE unrelated files -- this one (SW-1..SW-9b),
tests/integration/test_setup_workflow.py (SW-10..SW-13) and
tests/unit/test_stuck_watch.py (SW-10..SW-11), the last two of which already collide
with each other. SW-14 is the lowest number free repo-wide, so the new ids start
there rather than adding a third claim on SW-10.

The MALFORMED-DECLARATION guards. Every one of these protects against a mistake in
an adapter's own ``dispatch.settings_write`` block, not against device data -- and
they matter because this call carries index-aligned arrays into an object selector
that rejects the WHOLE call if any one column is the wrong type or length. A guard
that let a bad column through would not degrade one field; it would lose the entire
per-room write for the run.

[SW-14] a settings_write block with no ``domain``/``service`` -> no call at all.
[SW-15] a resolved room whose room_id is not numeric -> ERROR log and no call; the
        arrays cannot be aligned to a segment list that does not exist.
[SW-16] a field with no ``wire`` is skipped, and the rest still emit.
[SW-17] a field with a ``wire`` but neither ``canonical`` nor ``constant`` is
        skipped -- it names a column with nothing to put in it.
[SW-18] a clamped field whose value will not coerce takes the filler, so a typo in
        one room cannot poison the column.
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


def _register(hass, *, fields=_FIELDS, settings_write=True, sw_override=None):
    """Register the Dreame-shaped adapter.

    ``sw_override`` REPLACES the whole settings_write block, for the malformed-
    declaration tests ([SW-14]) that need a block missing ``domain``/``service``.
    Default None keeps the well-formed block every other test here relies on.
    """
    dispatch = {
        "template": "dreame_room_clean", "service_domain": "dreame_vacuum",
        "service_name": "vacuum_clean_segment", "command": None,
        "rooms_field": "segments", "clean_passes_field": None,
    }
    if settings_write:
        dispatch["settings_write"] = sw_override if sw_override is not None else {
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


# ---------------------------------------------------------------------------
# [SW-10..SW-14] -- the malformed-declaration guards, from the 2026-11-07 coverage
# pass. Measured missed before this batch: 1142, 1146-1152, 1160, 1171, 1202-1203.
#
# All five are reached by an adapter DECLARATION mistake rather than by device data,
# which is why they are worth tests rather than pragmas: a declaration is authored by
# hand (ours today, a contributor's tomorrow), and the failure it causes is not local.
# The comment in the code says it plainly -- an unmapped value must never become "a
# stray string on an int-typed wire (the object selector would reject the whole
# call)". So each guard's job is to drop ONE column or refuse the call outright,
# never to emit a malformed one.
# ---------------------------------------------------------------------------


async def test_settings_write_without_domain_or_service_makes_no_call(hass, manager, caplog):
    """[SW-14] a settings_write block that names no service is a no-op.

    Reachable by declaring the block and forgetting a key -- the shape a half-written
    adapter port has. The guard must refuse BEFORE building any arrays, because the
    alternative is an async_call with domain=None.

    `calls == []` ALONE CANNOT TEST THIS, and that is the whole point of the second
    assertion. Delete the guard and `async_call(None, None, ...)` raises, which the
    function's own best-effort-loud `except Exception` at the end swallows into an
    ERROR log -- so no call is recorded either way and the first assertion passes
    with the guard gone. Only the absence of that log separates "refused cleanly
    before building anything" from "attempted it and swallowed the failure".
    """
    _register(hass, sw_override={
        # domain and service deliberately absent.
        "segment_id_field": "segment_id", "fields": _FIELDS,
    })
    calls = _capture(hass)

    with caplog.at_level("ERROR"):
        await manager._run_settings_write(
            vacuum_entity_id=_VAC,
            resolved_rooms=[{"room_id": 1, "fan_speed": "quiet", "clean_passes": 1}],
        )

    assert calls == []
    assert "settings_write" not in caplog.text, (
        "the block must be refused before the call, not attempted and swallowed"
    )


async def test_non_numeric_room_id_is_refused_loudly(hass, manager, caplog):
    """[SW-15] a room whose id will not coerce aborts the write, and says so.

    The segment column IS the alignment for every other column, so one unusable
    room_id makes the entire call meaningless -- there is no per-room degradation
    available. It aborts, and LOUDLY: the run proceeds on the device's stored
    settings, which is a real behaviour change the user would otherwise have no
    record of.
    """
    _register(hass)
    calls = _capture(hass)

    with caplog.at_level("ERROR"):
        await manager._run_settings_write(
            vacuum_entity_id=_VAC,
            resolved_rooms=[
                {"room_id": 1, "fan_speed": "quiet", "clean_passes": 1},
                {"room_id": "kitchen", "fan_speed": "turbo", "clean_passes": 2},
            ],
        )

    assert calls == [], "one unusable room_id must abort the whole write"
    assert "numeric room_id" in caplog.text, "the abort must be loud, not silent"


async def test_a_field_with_no_wire_is_skipped(hass, manager):
    """[SW-16] no ``wire`` means no column name, so there is nothing to emit.

    The field is dropped and its SIBLINGS still emit -- asserted, because a guard
    that bailed out of the loop instead of continuing would silently drop every
    field declared after the bad one.
    """
    _register(hass, fields=[
        {"canonical": "fan_speed", "wire": "suction_level",
         "value_map": dv.FAN_SPEED_WIRE_MAP, "filler": 0},
        {"canonical": "clean_passes", "filler": 1},          # no wire
        {"canonical": "clean_passes", "wire": "repeats", "filler": 1},
    ])
    calls = _capture(hass)

    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"room_id": 1, "fan_speed": "quiet", "clean_passes": 2}],
    )

    assert calls == [{
        "entity_id": _VAC, "segment_id": [1],
        "suction_level": [0],
        "repeats": [2],          # the field AFTER the bad one still emitted
    }]


async def test_a_field_with_no_canonical_or_constant_is_skipped(hass, manager):
    """[SW-17] a wire with nothing to put in it is skipped, not filled.

    Distinct from [SW-16]: here the column is NAMED but has no source -- no
    ``canonical`` to read per room and no ``constant`` to repeat. Emitting it with
    fillers would be worse than omitting it, because a filler is a real value the
    device would store for every room.
    """
    _register(hass, fields=[
        {"wire": "cleaning_mode", "filler": 0},              # named, no source
        {"canonical": "clean_passes", "wire": "repeats", "filler": 1},
    ])
    calls = _capture(hass)

    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[{"room_id": 1, "clean_passes": 2}],
    )

    assert calls == [{"entity_id": _VAC, "segment_id": [1], "repeats": [2]}]
    assert "cleaning_mode" not in calls[0], (
        "a column with no source must be absent, not filled with the filler"
    )


async def test_an_uncoercible_clamped_value_takes_the_filler(hass, manager):
    """[SW-18] a value that will not int() falls back to the filler, per room.

    [SW-6] covers the clamp's arithmetic on values that DO coerce. This covers the
    arm underneath it. The degradation is deliberately per-room rather than
    per-call: one room with a typo'd setting must not cost the other rooms their
    write, so the column stays aligned and only that entry becomes the filler.
    """
    _register(hass, fields=[
        {"canonical": "clean_passes", "wire": "repeats",
         "filler": 1, "clamp": [1, 3]},
    ])
    calls = _capture(hass)

    await manager._run_settings_write(
        vacuum_entity_id=_VAC,
        resolved_rooms=[
            {"room_id": 1, "clean_passes": 2},        # coerces, in range
            {"room_id": 2, "clean_passes": "lots"},   # will not coerce -> filler
            {"room_id": 3, "clean_passes": 9},        # coerces, clamped down
        ],
    )

    assert calls == [{
        "entity_id": _VAC, "segment_id": [1, 2, 3],
        "repeats": [2, 1, 3],
    }], "the bad room takes the filler; the others keep their own values"
