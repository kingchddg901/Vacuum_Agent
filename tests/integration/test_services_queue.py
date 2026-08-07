"""Phase 4 integration tests — queue service handlers.

Coverage targets
----------------
[SQ-1]  build_queue service populates manager queue data.
[SQ-1b] RP-031/Q9: build_queue now supports_response.
[SQ-2]  get_queue_state service returns empty default for unknown vacuum.
[SQ-3]  get_queue_state service returns populated data after build_queue.
[SQ-4]  get_payload_state service returns a response dict.
[SQ-5]  build_room_payload service completes without error.
[SQ-5b] RP-031/Q9: build_room_payload now supports_response.
[SQ-6]  clear_queue service empties the queue.
[SQ-6b] RP-031/Q9: clear_queue now supports_response.
[SQ-7]  RP-032/RF-28 (A2-JOB-5): break_type -> required-sibling-parameter
        cross-field validation, at the schema layer.
[SQ-8]  RP-032/RF-28 (A2-JOB-5): add_queue_break has no zone branch, so its
        schema deliberately rejects break_type=zone (add_queue_zone's job).
[SQ-9]  RP-032/RF-28 (A2-JOB-6): set_queue_breaks accepts the read shape
        get_queue_steps emits ({after_index, step: {type, ...}}), not just
        the flat write shape -- the documented round trip doesn't need
        hand-flattening first.
"""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.services.queue import (
    _ADD_QUEUE_BREAK_SCHEMA,
    _QUEUE_BREAK_ENTRY_SCHEMA,
    _flatten_break_entry,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"


# ---------------------------------------------------------------------------
# [SQ-1] build_queue
# ---------------------------------------------------------------------------

async def test_build_queue_service_populates_queue(hass, manager_with_services):
    """[SQ-1] Calling build_queue service populates manager.data['queue']."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN,
        "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    assert _VAC in manager_with_services.data.get("queue", {})
    assert _MAP in manager_with_services.data["queue"][_VAC]


async def test_build_queue_service_returns_response(hass, manager_with_services):
    """[SQ-1b] RP-031/Q9: build_queue now supports_response -- was
    fire-and-forget (-> None) even though it always builds a real payload."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    result = await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["room_count"] == 3


async def test_build_queue_service_sets_room_ids(hass, manager_with_services):
    """[SQ-1] build_queue service wires queue_room_ids into runtime."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    await hass.services.async_call(
        DOMAIN,
        "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    runtime = manager_with_services.ensure_runtime(_VAC)
    assert len(runtime.queue_room_ids) == 2


# ---------------------------------------------------------------------------
# [SQ-2] — [SQ-3] get_queue_state
# ---------------------------------------------------------------------------

async def test_get_queue_state_service_unknown_vacuum_default(hass, manager_with_services):
    """[SQ-2] get_queue_state returns empty default for an unseen vacuum."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_queue_state",
        {"vacuum_entity_id": _VAC, "map_id": "99"},
        blocking=True,
        return_response=True,
    )
    assert result["room_count"] == 0
    assert result["queue_room_ids"] == []


async def test_get_queue_state_service_after_build_has_rooms(hass, manager_with_services):
    """[SQ-3] get_queue_state returns populated state after build_queue service."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    result = await hass.services.async_call(
        DOMAIN, "get_queue_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert result["room_count"] == 3
    assert len(result["queue_room_ids"]) == 3


async def test_get_queue_state_service_echoes_ids(hass, manager_with_services):
    """[SQ-2] Response includes the vacuum_entity_id and map_id passed in."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN, "get_queue_state",
        {"vacuum_entity_id": _VAC, "map_id": "5"},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert result["map_id"] == "5"


# ---------------------------------------------------------------------------
# [SQ-4] get_payload_state
# ---------------------------------------------------------------------------

async def test_get_payload_state_service_returns_dict(hass, manager_with_services):
    """[SQ-4] get_payload_state returns a response dict for any vacuum/map."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN, "get_payload_state",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result


# ---------------------------------------------------------------------------
# [SQ-5] build_room_payload
# ---------------------------------------------------------------------------

async def test_build_room_payload_service_no_error(hass, manager_with_services):
    """[SQ-5] build_room_payload completes without raising."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "build_room_payload",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )


async def test_build_room_payload_service_returns_response(hass, manager_with_services):
    """[SQ-5b] RP-031/Q9: build_room_payload now supports_response -- was
    fire-and-forget (-> None) even though it always builds a real payload dict."""
    setup_map(manager_with_services, _VAC, _MAP, count=2)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    result = await hass.services.async_call(
        DOMAIN, "build_room_payload",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict) and result


# ---------------------------------------------------------------------------
# [SQ-6] clear_queue
# ---------------------------------------------------------------------------

async def test_clear_queue_service_empties_queue(hass, manager_with_services):
    """[SQ-6] clear_queue service resets queue_room_ids to empty."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "clear_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True,
    )
    state = manager_with_services.get_queue_state(
        vacuum_entity_id=_VAC, map_id=_MAP
    )
    assert state["queue_room_ids"] == []
    assert state["room_count"] == 0


async def test_clear_queue_service_returns_response(hass, manager_with_services):
    """[SQ-6b] RP-031/Q9: clear_queue now supports_response -- was
    fire-and-forget (-> None) even though it always builds a real payload."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    result = await hass.services.async_call(
        DOMAIN, "clear_queue",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    assert result["room_count"] == 0
    assert result["queue_room_ids"] == []


# ---------------------------------------------------------------------------
# [SQ-7]/[SQ-8] add_queue_break schema: break_type -> required parameter.
# ---------------------------------------------------------------------------

def test_add_queue_break_schema_rejects_wait_without_minutes():
    """[SQ-7] Before this, {break_type: wait} with no wait_minutes validated
    cleanly and only failed later, silently, inside the manager."""
    with pytest.raises(vol.Invalid):
        _ADD_QUEUE_BREAK_SCHEMA(
            {"vacuum_entity_id": _VAC, "break_type": "wait", "after_index": 1}
        )


def test_add_queue_break_schema_rejects_charge_wait_without_target():
    """[SQ-7] Same dependency for the charge_wait/target_battery_percent pair."""
    with pytest.raises(vol.Invalid):
        _ADD_QUEUE_BREAK_SCHEMA(
            {"vacuum_entity_id": _VAC, "break_type": "charge_wait", "after_index": 1}
        )


def test_add_queue_break_schema_accepts_wait_with_minutes():
    """[SQ-7] The matching parameter still validates cleanly."""
    out = _ADD_QUEUE_BREAK_SCHEMA(
        {
            "vacuum_entity_id": _VAC,
            "break_type": "wait",
            "after_index": 1,
            "wait_minutes": 20,
        }
    )
    assert out["wait_minutes"] == 20


def test_add_queue_break_schema_accepts_charge_wait_with_target():
    """[SQ-7] Same for charge_wait + target_battery_percent."""
    out = _ADD_QUEUE_BREAK_SCHEMA(
        {
            "vacuum_entity_id": _VAC,
            "break_type": "charge_wait",
            "after_index": 1,
            "target_battery_percent": 90,
        }
    )
    assert out["target_battery_percent"] == 90


def test_add_queue_break_schema_rejects_zone_type():
    """[SQ-8] add_queue_break has no zone branch -- zones go through the
    dedicated add_queue_zone service, not through this schema."""
    with pytest.raises(vol.Invalid):
        _ADD_QUEUE_BREAK_SCHEMA(
            {"vacuum_entity_id": _VAC, "break_type": "zone", "after_index": 1}
        )


# ---------------------------------------------------------------------------
# [SQ-7] _QUEUE_BREAK_ENTRY_SCHEMA (set_queue_breaks): same dependency, plus
# zone -> zone_ids.
# ---------------------------------------------------------------------------

def test_queue_break_entry_schema_rejects_zone_without_zone_ids():
    """[SQ-7] zone entries need a non-empty zone_ids, same cross-field rule."""
    with pytest.raises(vol.Invalid):
        _QUEUE_BREAK_ENTRY_SCHEMA({"after_index": 1, "break_type": "zone"})


def test_queue_break_entry_schema_rejects_zone_with_empty_zone_ids():
    """[SQ-7] An explicit empty list is rejected the same as a missing key."""
    with pytest.raises(vol.Invalid):
        _QUEUE_BREAK_ENTRY_SCHEMA(
            {"after_index": 1, "break_type": "zone", "zone_ids": []}
        )


def test_queue_break_entry_schema_accepts_zone_with_zone_ids():
    """[SQ-7] The matching parameter still validates cleanly."""
    out = _QUEUE_BREAK_ENTRY_SCHEMA(
        {"after_index": 1, "break_type": "zone", "zone_ids": ["z1"]}
    )
    assert out["zone_ids"] == ["z1"]


# ---------------------------------------------------------------------------
# [SQ-9] set_queue_breaks accepts get_queue_steps's read shape directly.
# ---------------------------------------------------------------------------

def test_queue_break_entry_schema_accepts_flat_write_shape():
    """[SQ-9] The pre-existing flat write shape still works unchanged."""
    out = _QUEUE_BREAK_ENTRY_SCHEMA(
        {"after_index": 2, "break_type": "wait", "wait_minutes": 15}
    )
    assert out == {"after_index": 2, "break_type": "wait", "wait_minutes": 15}


def test_queue_break_entry_schema_accepts_get_queue_steps_read_shape():
    """[SQ-9] The exact shape get_queue_steps's `breaks` entries have --
    {after_index, step: {type, ...}} -- round-trips straight into
    set_queue_breaks without the caller flattening `step` first."""
    out = _QUEUE_BREAK_ENTRY_SCHEMA(
        {
            "after_index": 1,
            "step": {"type": "charge_wait", "target_battery_percent": 90},
        }
    )
    assert out == {
        "after_index": 1,
        "break_type": "charge_wait",
        "target_battery_percent": 90,
    }


def test_queue_break_entry_schema_read_shape_zone():
    """[SQ-9] The read shape round-trips a zone step too."""
    out = _QUEUE_BREAK_ENTRY_SCHEMA(
        {"after_index": 3, "step": {"type": "zone", "zone_ids": ["z1", "z2"]}}
    )
    assert out == {
        "after_index": 3,
        "break_type": "zone",
        "zone_ids": ["z1", "z2"],
    }


def test_queue_break_entry_schema_read_shape_still_enforces_dependency():
    """[SQ-9] Flattening doesn't bypass the break_type -> parameter check -- a
    malformed step (e.g. a wait step missing wait_minutes) is still rejected."""
    with pytest.raises(vol.Invalid):
        _QUEUE_BREAK_ENTRY_SCHEMA({"after_index": 1, "step": {"type": "wait"}})


# ---------------------------------------------------------------------------
# [SQ-10..13] R2-COV-1 — the break/step/zone HANDLER BODIES.
#
# SQ-7/8/9 above cover these services' SCHEMAS, which validate before the handler
# is ever entered — so every `_handle_*` body below, and every register() closure
# that reaches one, had zero coverage. Driving them through
# hass.services.async_call exercises the closure and the body together, which is
# also how the card reaches them.
# ---------------------------------------------------------------------------


async def _steps(hass, manager=None):
    return await hass.services.async_call(
        DOMAIN, "get_queue_steps",
        {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )


async def test_queue_break_lifecycle_through_the_services(hass, manager_with_services):
    """[SQ-10] add -> read -> remove -> clear, entirely through the service layer."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue", {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )

    added = await hass.services.async_call(
        DOMAIN, "add_queue_break",
        {"vacuum_entity_id": _VAC, "map_id": _MAP,
         "break_type": "charge_wait", "target_battery_percent": 80, "after_index": 1},
        blocking=True, return_response=True,
    )
    assert isinstance(added, dict)

    steps = await _steps(hass)
    kinds = [s.get("type") for s in steps.get("steps", [])]
    assert "charge_wait" in kinds, f"the break never reached the stepped view: {kinds}"

    await hass.services.async_call(
        DOMAIN, "remove_queue_break",
        {"vacuum_entity_id": _VAC, "map_id": _MAP, "index": 0},
        blocking=True, return_response=True,
    )
    assert "charge_wait" not in [s.get("type") for s in (await _steps(hass)).get("steps", [])]

    # clear on an already-break-free queue must be a clean no-op, not an error —
    # the card calls it unconditionally from "remove all".
    cleared = await hass.services.async_call(
        DOMAIN, "clear_queue_breaks", {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    assert isinstance(cleared, dict)


async def test_set_queue_breaks_replaces_wholesale(hass, manager_with_services):
    """[SQ-11] set_queue_breaks is the reorder/retarget path — it REPLACES, so the
    previous break must not survive it."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue", {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )
    await hass.services.async_call(
        DOMAIN, "add_queue_break",
        {"vacuum_entity_id": _VAC, "map_id": _MAP,
         "break_type": "charge_wait", "target_battery_percent": 80, "after_index": 1},
        blocking=True, return_response=True,
    )

    await hass.services.async_call(
        DOMAIN, "set_queue_breaks",
        {"vacuum_entity_id": _VAC, "map_id": _MAP,
         "breaks": [{"after_index": 2, "break_type": "wait", "wait_minutes": 15}]},
        blocking=True, return_response=True,
    )

    kinds = [s.get("type") for s in (await _steps(hass)).get("steps", [])]
    assert "wait" in kinds, f"the replacement break is missing: {kinds}"
    assert "charge_wait" not in kinds, "set_queue_breaks appended instead of replacing"


async def test_queue_mutators_persist_but_the_reader_does_not(hass, manager_with_services):
    """[SQ-12] The asymmetry that makes the queue survive a restart.

    Every mutating handler awaits async_save(); get_queue_steps deliberately does not,
    because it writes nothing. A mutator that forgot the save would look correct for the
    whole session and lose the user's breaks on the next restart — invisible to any test
    that only checks the response payload, which is why this asserts on the SAVE.
    """
    from unittest.mock import AsyncMock

    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue", {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )

    manager_with_services.async_save = AsyncMock()
    await _steps(hass)
    assert manager_with_services.async_save.await_count == 0, (
        "the read-only stepped view triggered a persist"
    )

    await hass.services.async_call(
        DOMAIN, "add_queue_break",
        {"vacuum_entity_id": _VAC, "map_id": _MAP,
         "break_type": "charge_wait", "target_battery_percent": 80, "after_index": 1},
        blocking=True, return_response=True,
    )
    assert manager_with_services.async_save.await_count == 1, (
        "add_queue_break did not persist — the break is lost on restart"
    )


async def test_add_queue_zone_inserts_a_zone_step(hass, manager_with_services):
    """[SQ-13] add_queue_zone is a separate service from add_queue_break precisely
    because the break schema rejects break_type=zone (SQ-8). Its handler had no
    coverage, so nothing proved the zone branch reaches the queue at all."""
    setup_map(manager_with_services, _VAC, _MAP, count=3)
    await hass.services.async_call(
        DOMAIN, "build_queue", {"vacuum_entity_id": _VAC, "map_id": _MAP},
        blocking=True, return_response=True,
    )

    result = await hass.services.async_call(
        DOMAIN, "add_queue_zone",
        {"vacuum_entity_id": _VAC, "map_id": _MAP,
         "zone_ids": ["under_table"], "after_index": 1},
        blocking=True, return_response=True,
    )
    assert isinstance(result, dict)


def test_flatten_break_entry_passes_non_dicts_straight_through():
    """[SQ-14] R2-COV-1, the last uncovered line. The coercer must hand a non-dict
    entry to the entry schema UNCHANGED, so voluptuous reports "expected a dictionary"
    against the offending element. Reaching for .get() on it here would raise
    AttributeError out of schema validation instead — a 500-shaped failure for what is
    ordinary bad input."""
    for value in ("not-a-dict", 7, None, ["after_index"]):
        assert _flatten_break_entry(value) is value
