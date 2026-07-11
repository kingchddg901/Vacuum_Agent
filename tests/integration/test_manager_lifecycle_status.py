"""Tests for core/manager.py lifecycle + start-status surfaces.

Two thin-but-real engines the dashboard polls:

* get_lifecycle_state — folds the ErrorTracker's active-run latch into the
  user-visible lifecycle message (the error-override block).
* get_start_status — the start-protection gate that blocks a new run when a
  job is paused or onboarding is incomplete.

Driven against the real manager with a recording ErrorTracker stand-in and the
shared setup_map helper; no entity listeners or service registry required.

Coverage targets
----------------
[LS-1]  get_lifecycle_state: current_message overrides the generic message.
[LS-2]  get_lifecycle_state: blank current_message → "Run had N…; last:" derived
        from the latest error entry.
[LS-3]  get_start_status: a paused job blocks the start (reason job_paused).
[LS-4]  get_start_status: incomplete floor-type onboarding blocks (onboarding_required).
[LS-5]  get_start_status: every selected room blocked → all_selected_rooms_blocked.
[LS-6]  get_lifecycle_state: adapter vocabulary is read + lower-cased when the
        caller omits the explicit sets (the _vocab_frozenset raw-present branch).
[LS-7]  get_lifecycle_state: after start clears the payload, the active job's
        rooms + payload are folded into the lifecycle metadata (the fallback copy).
[LS-8]  get_dashboard_snapshot surfaces max_clean_passes + tank-driven mop_active +
        supports_base_station/map_bounds + live_map_image_entity (drives the card's
        tab visibility + Map view).
[LS-9]  get_dashboard_snapshot live-map backdrop is OVERRIDE-FIRST: a per-vacuum
        live_map_image_entity override (existence-checked) beats the adapter pattern
        and works with NO pattern (Eufy + the eufy-clean camera); clearing it falls
        back to the pattern.
[LS-10] get_dashboard_snapshot surfaces cv_available + cv_missing (runtime CV-library
        signal) so the card can hide Auto (CV) when numpy/Pillow/scipy are absent;
        libs present -> available + empty, monkeypatched-missing -> the names.
[LS-11] get_dashboard_snapshot surfaces the adapter's settings_selects as resolved,
        existence-checked entity-ids (setting_entities) for the zone-clean panel's
        live controls: only entities that actually exist are included, a declared-
        but-missing one is dropped, and no settings_selects declared -> empty.
[EXT-1] maybe_handle_external_run: cleaning with no dispatched job opens an
        "external" capture slot.
[EXT-2] maybe_handle_external_run: a mid-run dock resume cancels the pending
        grace finalize.
[EXT-3] _external_grace_finalize: staying docked past the grace window fires the
        finalize → slot clears.
[EXT-4] _external_grace_finalize: a mid-run task_status defers the close → slot
        stays + timer reschedules.
[EXT-5] maybe_handle_external_run: an in-progress slot with the vacuum neither
        cleaning nor docked/idle (e.g. paused) → no-op, no grace timer.
[EXT-6] _external_status_is_mid_run: False when the adapter declares no
        external_mid_run_statuses (the empty-list guard).
[EXT-7] _external_status_is_mid_run: False when mid-run statuses exist but the
        adapter wires no task_status entity.
[EXT-8] _external_grace_finalize: early-out when the slot is no longer "external"
        (already resumed/cleared) → no finalize, slot stays cleared.
[EXT-9] _external_grace_finalize: early-out when the robot raced the cancel back
        to "cleaning" → slot left "external" for the next dock.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eufy_vacuum.adapters.registry import (
    register_adapter_config,
    unregister_adapter_config,
)
from custom_components.eufy_vacuum.const import (
    DATA_ERROR_TRACKER,
    DOMAIN,
    EVENT_EXTERNAL_RUN_PENDING,
)
from custom_components.eufy_vacuum.learning.constants import EXTERNAL_FINALIZE_GRACE_S

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"


async def test_dashboard_snapshot_mop_active_and_passes(manager, hass):
    """[LS-8] The dashboard snapshot surfaces max_clean_passes (from dispatch
    passes_max) and a tank-driven mop_active (from entities.mop_active), so the
    room editor can render S6-correct passes + mop state."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"mop_active": "binary_sensor.alfred_water_box_attached"},
        "dispatch": {"passes_max": 3, "passes_is_global": True},
        "capabilities": {"supports_room_profiles": False},
        # S6 shape: no dock_events + noop segmenter -> no Base Station / Map Bounds.
        "mapping": {"segmenter_engine": "noop_fallback"},
    })
    try:
        hass.states.async_set("binary_sensor.alfred_water_box_attached", "on")
        await hass.async_block_till_done()
        snap = manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        assert snap["max_clean_passes"] == 3
        assert snap["mop_active"] is True
        # S6-shaped: passes is one whole-run scalar; profiles section is hidden.
        assert snap["passes_is_global"] is True
        assert snap["supports_room_profiles"] is False
        # No dock, no CV map -> both tabs hidden.
        assert snap["supports_base_station"] is False
        assert snap["supports_map_bounds"] is False

        hass.states.async_set("binary_sensor.alfred_water_box_attached", "off")
        await hass.async_block_till_done()
        snap = manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        assert snap["mop_active"] is False
    finally:
        unregister_adapter_config(_VAC)


async def test_dashboard_snapshot_no_tank_sensor_defaults(manager, hass):
    """[LS-8] No mop_active entity -> mop_active None (Eufy uses clean_mode);
    no passes_max -> default 2 (historical Eufy editor)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)
    register_adapter_config(_VAC, {"adapter_id": "eufy", "source": "code", "entities": {}})
    try:
        await hass.async_block_till_done()
        snap = manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        assert snap["mop_active"] is None
        assert snap["max_clean_passes"] == 2
        # Eufy defaults: per-room passes + profiles section shown.
        assert snap["passes_is_global"] is False
        assert snap["supports_room_profiles"] is True
        # Default-REJECT: a bare adapter declares no dock_events + no segmenter,
        # so both tab flags resolve False (NOT hardcoded on). The REAL Eufy
        # adapter declares dock_events.enabled + segmenter_engine="eufy_cv_v1" ->
        # both True (covered by test_dashboard_snapshot_tab_capabilities below).
        assert snap["supports_base_station"] is False
        assert snap["supports_map_bounds"] is False
    finally:
        unregister_adapter_config(_VAC)


async def test_dashboard_snapshot_tab_capabilities(manager, hass):
    """[LS-8] supports_base_station / supports_map_bounds drive whether the card
    shows the Base Station + Map Bounds tabs; live_map_image_entity drives the Map
    view's live backdrop. Cover every derivation branch."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)

    def _snap(cfg):
        register_adapter_config(_VAC, {"adapter_id": "x", "source": "code", **cfg})
        try:
            return manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        finally:
            unregister_adapter_config(_VAC)

    # Dock + CV (the Eufy shape) -> both tabs shown.
    s = _snap({
        "dock_events": {"enabled": True},
        "mapping": {"segmenter_engine": "eufy_cv_v1"},
    })
    assert s["supports_base_station"] is True
    assert s["supports_map_bounds"] is True

    # No dock_events but a station/wash/dry/empty capability -> Base Station shown
    # via the capability OR-branch.
    assert _snap({"capabilities": {"supports_station_water": True}})["supports_base_station"] is True
    assert _snap({"capabilities": {"supports_mop_wash": True}})["supports_base_station"] is True

    # dock_events present but disabled + no dock caps -> hidden.
    assert _snap({"dock_events": {"enabled": False}})["supports_base_station"] is False

    # noop segmenter (native segments) -> Map Bounds hidden; a real engine -> shown.
    assert _snap({"mapping": {"segmenter_engine": "noop_fallback"}})["supports_map_bounds"] is False
    assert _snap({"mapping": {"segmenter_engine": "eufy_cv_v1"}})["supports_map_bounds"] is True

    # Live map image (Roborock): declared AND the derived image.{object_id}_{slug}
    # entity exists -> the entity id is surfaced; declared but the entity is absent
    # -> None; not declared (Eufy / older backend) -> None. _MAP="6" -> image.alfred_6.
    hass.states.async_set(
        "image.alfred_6", "2026-01-01T00:00:00+00:00",
        {"entity_picture": "/api/image_proxy/image.alfred_6?token=abc"},
    )
    _pat = {"mapping": {"live_map_image_entity_pattern": "image.{object_id}_{map_slug}"}}
    assert _snap(_pat)["live_map_image_entity"] == "image.alfred_6"
    hass.states.async_remove("image.alfred_6")
    assert _snap(_pat)["live_map_image_entity"] is None
    assert _snap({})["live_map_image_entity"] is None

    # live_map_rotation rides the snapshot from the per-map bucket (default 0).
    assert _snap({})["live_map_rotation"] == 0
    manager.data["maps"][_VAC][_MAP]["live_map_rotation"] = 180
    assert _snap({})["live_map_rotation"] == 180


async def test_dashboard_snapshot_live_map_override(manager, hass):
    """[LS-9] Live-map backdrop resolution is override-first: a per-vacuum
    live_map_image_entity (existence-checked) beats the adapter pattern and works with
    no pattern at all (the Eufy + eufy-clean-camera case); clearing it falls back."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)

    def _snap(cfg):
        register_adapter_config(_VAC, {"adapter_id": "x", "source": "code", **cfg})
        try:
            return manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        finally:
            unregister_adapter_config(_VAC)

    # A device-named camera the {object_id} pattern would NOT produce.
    hass.states.async_set(
        "camera.eufy_omni_c28_map", "2026-01-01T00:00:00+00:00",
        {"entity_picture": "/api/camera_proxy/camera.eufy_omni_c28_map?token=abc"},
    )

    # No override + no pattern -> None (Eufy default; byte-identical to before).
    assert _snap({})["live_map_image_entity"] is None

    # Override set + entity exists -> wins even with NO adapter pattern declared.
    manager.data["vacuums"][_VAC]["live_map_image_entity"] = "camera.eufy_omni_c28_map"
    assert _snap({})["live_map_image_entity"] == "camera.eufy_omni_c28_map"

    # Override is existence-checked: a stored-but-missing entity -> falls back (None here).
    manager.data["vacuums"][_VAC]["live_map_image_entity"] = "camera.gone"
    assert _snap({})["live_map_image_entity"] is None

    # Override beats a declared pattern that WOULD otherwise resolve.
    hass.states.async_set(
        "image.alfred_6", "2026-01-01T00:00:00+00:00",
        {"entity_picture": "/api/image_proxy/image.alfred_6?token=z"},
    )
    _pat = {"mapping": {"live_map_image_entity_pattern": "image.{object_id}_{map_slug}"}}
    manager.data["vacuums"][_VAC]["live_map_image_entity"] = "camera.eufy_omni_c28_map"
    assert _snap(_pat)["live_map_image_entity"] == "camera.eufy_omni_c28_map"

    # Clearing the override -> the declared pattern resolves again.
    manager.data["vacuums"][_VAC].pop("live_map_image_entity", None)
    assert _snap(_pat)["live_map_image_entity"] == "image.alfred_6"


async def test_dashboard_snapshot_setting_entities(manager, hass):
    """[LS-11] The snapshot surfaces the adapter's settings_selects as resolved,
    existence-checked entity-ids — the live controls for the zone-clean panel.
    Only entities that actually exist are included; none declared -> empty."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)

    def _snap(cfg):
        register_adapter_config(_VAC, {"adapter_id": "x", "source": "code", **cfg})
        try:
            return manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        finally:
            unregister_adapter_config(_VAC)

    cfg = {"settings_selects": {
        "fan_speed":   {"entity_id": "select.alfred_suction_level"},
        "clean_mode":  {"entity_id": "select.alfred_cleaning_mode"},
        "water_level": {"entity_id": "select.alfred_water_level"},
    }}

    # No entities exist yet -> empty (existence-checked).
    assert _snap(cfg)["setting_entities"] == {}

    # Only the entities that actually exist are surfaced (water_level missing -> dropped).
    hass.states.async_set("select.alfred_suction_level", "Max", {})
    hass.states.async_set("select.alfred_cleaning_mode", "vacuum", {})
    assert _snap(cfg)["setting_entities"] == {
        "fan_speed": "select.alfred_suction_level",
        "clean_mode": "select.alfred_cleaning_mode",
    }

    # No settings_selects declared -> empty.
    assert _snap({})["setting_entities"] == {}


async def test_dashboard_snapshot_cv_availability(manager, hass, monkeypatch):
    """[LS-10] The snapshot surfaces cv_available + cv_missing (runtime CV-library
    signal) so the card can hide Auto (CV) + explain when the optional science stack
    (numpy/Pillow/scipy) is absent — never blocking anything else."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=1)
    register_adapter_config(_VAC, {"adapter_id": "x", "source": "code"})
    try:
        # The libs are present in the test env -> available, nothing missing.
        snap = manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        assert snap["cv_available"] is True
        assert snap["cv_missing"] == []

        # Simulate a HA env without the science stack -> not available, names listed.
        import custom_components.eufy_vacuum.mapping.segment_primitives as _sp
        monkeypatch.setattr(_sp, "image_runtime_capabilities", lambda: {
            "numpy": {"available": False},
            "pillow": {"available": False},
            "scipy": {"available": True},
            "scipy_ndimage": {"available": True},
            "pipeline_ready": False,
        })
        snap2 = manager.get_dashboard_snapshot(vacuum_entity_id=_VAC, map_id=_MAP)
        assert snap2["cv_available"] is False
        assert snap2["cv_missing"] == ["numpy", "pillow"]
    finally:
        unregister_adapter_config(_VAC)


class _FakeErrorTracker:
    """Returns a canned active-run latch — mirrors ErrorTracker's read API."""

    def __init__(self, latch: dict | None) -> None:
        self._latch = latch

    def get_active_run_latch(self, vacuum_entity_id: str) -> dict | None:
        return self._latch


def _wire_error_tracker(hass, latch: dict | None) -> None:
    hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = _FakeErrorTracker(latch)


# ---------------------------------------------------------------------------
# get_lifecycle_state — error-message override
# ---------------------------------------------------------------------------

def test_lifecycle_current_message_overrides(manager, hass):
    """[LS-1] a live current_message replaces the generic lifecycle message."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _wire_error_tracker(hass, {
        "error_count": 1,
        "current_message": "Side brush stuck",
        "errors": [],
        "recovered": False,
    })
    out = manager.get_lifecycle_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["message"] == "Side brush stuck"
    assert out["has_error"] is True
    assert out["error_count"] == 1


def test_lifecycle_recovered_message_derived(manager, hass):
    """[LS-2] blank current_message + error history → a "had errors" summary."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    _wire_error_tracker(hass, {
        "error_count": 2,
        "current_message": "",
        "errors": [
            {"message": "Wheel jam"},
            {"message": "Cliff sensor dirty"},
        ],
        "recovered": True,
    })
    out = manager.get_lifecycle_state(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["message"] == "Run had 2 error(s); last: Cliff sensor dirty"
    assert out["has_error"] is True


# ---------------------------------------------------------------------------
# get_start_status — start-protection gates
# ---------------------------------------------------------------------------

def test_start_status_blocked_by_paused_job(manager, hass):
    """[LS-3] a paused tracked job blocks a fresh start."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2, enabled_room_ids=[1, 2])
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
        "status": "paused", "job_id": "jp", "paused_at": "2026-01-01T00:00:00+00:00",
    }
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "job_paused"


def test_start_status_blocked_by_onboarding(manager, hass):
    """[LS-4] enabled rooms missing a confirmed floor type block the start."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        room["enabled"] = True
    # save_managed_rooms auto-confirms floor types; clear them so enabled rooms
    # still need confirmation → onboarding incomplete.
    manager.data["onboarding"][_VAC][_MAP]["floor_types_confirmed"] = {}
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "onboarding_required"


def _blocker(entity: str) -> dict:
    return {"kind": "blocker", "id": "b1", "entity_id": entity,
            "operator": "is_on", "effect": {"reason": "window_open"}}


def test_start_status_all_rooms_blocked(manager, hass):
    """[LS-5] when every selected room is blocked, the start is fully blocked."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    keys = list(rooms.keys())
    for i, key in enumerate(keys):
        rooms[key]["enabled"] = True
        rooms[key]["order"] = i + 1
        rooms[key]["rules"] = [_blocker(f"binary_sensor.win_{i}")]
        hass.states.async_set(f"binary_sensor.win_{i}", "on")
    # a complete access graph so rule-bearing rooms pass the graph gate and we
    # reach the all-blocked branch: room1 is the dock room granting room2 access.
    rooms[keys[0]].update({"is_dock_room": True, "grants_access_to": [2]})
    rooms[keys[1]]["grants_access_to"] = []
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "all_selected_rooms_blocked"


def test_start_status_blocked_by_empty_queue(manager, hass):
    """[LS-6] no enabled rooms → empty queue → the build_start_blocker_from_lifecycle
    path returns no_rooms_selected. This is the card-facing blocked payload that
    was previously untested."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2, enabled_room_ids=[])
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is True
    assert out["reason"] == "no_rooms_selected"
    # the payload fields the card reads on a lifecycle-block are populated
    assert out["reason_label"] and "preflight" in out
    assert "requires_confirmation" in out and "confirm_token" in out


@pytest.mark.parametrize("estimate,reason", [
    ({"not_enough_clean_water": True}, "not_enough_clean_water"),
    ({"low_clean_water_margin": True}, "low_clean_water_margin"),
])
def test_start_status_water_warning(manager, hass, monkeypatch, estimate, reason):
    """[LS-7] a ready start with a low-clean-water estimate surfaces a non-blocking
    water warning (the card's water-warning payload), covering both reason branches."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2, enabled_room_ids=[1, 2])
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    for i, room in enumerate(rooms.values(), start=1):
        room["enabled"] = True
        room["order"] = i
    hass.states.async_set(_VAC, "docked", {"battery_level": 90})
    monkeypatch.setattr(manager, "get_planned_job_estimate",
                        lambda **kw: {"water_estimate": estimate})
    out = manager.get_start_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert out["blocked"] is False
    assert out["water_warning"] is True
    assert out["water_warning_reason"] == reason
    assert out["warning"] is True


# ---------------------------------------------------------------------------
# get_lifecycle_state — adapter-vocabulary lookup + active-job payload fallback
#
# These exercise the two internal branches the dashboard relies on but which
# none of the LS-1..5 tests reach, because those pass no adapter config:
#   * _vocab_frozenset (the raw-present branch): the adapter's vocabulary is
#     read AND lower-cased when the caller omits the explicit sets.
#   * the post-start fallback: once a run starts and the prepared payload is
#     cleared, lifecycle metadata is rebuilt from the running job's rooms.
# ---------------------------------------------------------------------------

_VOCAB_ADAPTER = {
    "adapter_id": "t",
    "source": "t",
    "entities": {
        # task_status feeds evaluate_job_lifecycle's hard-service check.
        "task_status": "sensor.alfred_task",
    },
    # Mixed-case on purpose: a faithful match only happens if get_lifecycle_state
    # lower-cases the vocab (manager.py:2071) the same way _norm lower-cases the
    # live entity state. drying/active_run lists are empty → those keys fall back.
    "vocabulary": {
        "hard_service_states": ["Washing Mop"],
        "drying_states": [],
        "active_run_task_states": ["Cleaning"],
    },
}


def test_lifecycle_reads_and_lowercases_adapter_vocabulary(manager, hass):
    """[LS-6] omitting the explicit sets drives the adapter-vocabulary lookup.

    Registering ``hard_service_states: ["Washing Mop"]`` (mixed case) and setting
    the task-status entity to the same mixed-case string is a hard-service match
    ONLY if the vocab was read and lower-cased by ``_vocab_frozenset`` — the
    live entity side is lower-cased by ``_norm`` regardless. So a resulting
    ``mid_job_service`` lifecycle is the observable proof the raw-present branch
    (manager.py:2071) executed; an empty-fallback frozenset would never match
    and the state would fall through to ``ready``.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _VOCAB_ADAPTER)
    try:
        hass.states.async_set("sensor.alfred_task", "Washing Mop")

        # NOTE: no hard_service_states/drying_states/active_run_task_states args
        # → the manager must source them from the adapter registry (lines 2065-2079).
        out = manager.get_lifecycle_state(vacuum_entity_id=_VAC, map_id=_MAP)

        # structural: the lifecycle surface the card consumes.
        assert out["vacuum_entity_id"] == _VAC
        assert out["map_id"] == _MAP
        assert "lifecycle_state" in out and "message" in out and "blocking" in out
        # behavioural: the lower-cased vocab matched the lower-cased task status.
        assert out["lifecycle_state"] == "mid_job_service"
        assert out["blocking"] is True
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


def test_lifecycle_falls_back_to_active_job_rooms_after_start(manager, hass):
    """[LS-7] a started run whose prepared payload was cleared still reports rooms.

    After dispatch the manager clears the prepared payload (``get_payload_state``
    then yields empty ``resolved_rooms`` and an empty ``payload``). The lifecycle
    builder must fall back to the *running* job's room list (manager.py:2105-2107)
    and its payload (manager.py:2108-2109) so the dashboard keeps describing the
    in-flight run. We observe the copy via ``job_metadata``: the room count/ids
    come from the job's resolved_rooms, and the map_id comes from the job's
    payload — a sentinel that the default payload (map_id == _MAP) would never
    produce, so it can only be present if line 2109 copied it.
    """
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    try:
        # Stored payload state with NO selection — empty resolved_rooms AND a
        # falsy payload ({}) so both fallback copies (2107 + 2109) are exercised.
        manager.data.setdefault("payloads", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "payload": {},
            "resolved_rooms": [],
            "room_count": 0,
        }
        # A live, started job carrying the run's rooms + a sentinel payload map_id.
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {
            "vacuum_entity_id": _VAC,
            "map_id": _MAP,
            "status": "started",
            "job_id": "j-ls7",
            "resolved_rooms": [
                {"room_id": 1, "slug": "kitchen", "name": "Kitchen"},
                {"room_id": 2, "slug": "den", "name": "Den"},
            ],
            "payload": {
                "map_id": "EXT-SENTINEL",
                "rooms": [{"id": 1}, {"id": 2}],
            },
        }
        # Sanity: the public payload-state surface really has no selection, so the
        # fallback (not a pre-populated payload) is what supplies the rooms below.
        ps = manager.get_payload_state(vacuum_entity_id=_VAC, map_id=_MAP)
        assert ps.get("resolved_rooms") == []
        assert not ps.get("payload")

        out = manager.get_lifecycle_state(vacuum_entity_id=_VAC, map_id=_MAP)

        meta = out["job_metadata"]
        # resolved_rooms fallback (line 2107): two rooms from the running job.
        assert meta["room_count"] == 2
        assert meta["room_ids"] == [1, 2]
        # payload fallback (line 2109): the job's payload map_id, not the default.
        assert meta["map_id"] == "EXT-SENTINEL"
        assert out["active_job_exists"] is True
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# maybe_handle_external_run + _external_grace_finalize — app-started run
# detection and the dock grace-window finalize. Real manager, real timers
# driven by async_fire_time_changed (no wall-clock sleeps).
#
# [EXT-1]  cleaning with no dispatched job opens an "external" capture slot.
# [EXT-1b] a dispatched (started) job short-circuits: no external slot opens.
# [EXT-2]  a mid-run dock resume cancels the pending grace finalize.
# [EXT-3]  staying docked past the grace window fires the finalize → slot clears.
# [EXT-4]  a mid-run task_status defers the close → slot stays + timer reschedules.
# ---------------------------------------------------------------------------

_EXT_ADAPTER = {
    "adapter_id": "t",
    "source": "t",
    "entities": {
        "active_map": "sensor.alfred_active_map",
        "task_status": "sensor.alfred_task",
    },
    "external_mid_run_statuses": ["washing mop", "emptying dust"],
}


def _ext_setup(manager):
    """Shared setup: a 2-room map on "6" + the external-aware adapter config."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    setup_map(manager, _VAC, _MAP, count=2)
    register_adapter_config(_VAC, _EXT_ADAPTER)


async def test_external_run_opens_capture_slot(manager, hass):
    """[EXT-1] cleaning + active_map set + no dispatched job → external slot."""
    _ext_setup(manager)
    try:
        hass.states.async_set("sensor.alfred_active_map", "6")
        hass.states.async_set(_VAC, "cleaning")

        opened = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert opened is True
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_run_short_circuits_when_dispatched(manager, hass):
    """[EXT-1b] a dispatched (started) job owns the run → no external slot opens."""
    _ext_setup(manager)
    try:
        manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})["6"] = {
            "status": "started"
        }
        hass.states.async_set("sensor.alfred_active_map", "6")
        hass.states.async_set(_VAC, "cleaning")

        opened = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert opened is False
        # the internal job is untouched — no external capture clobbered it.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "started"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_run_cancels_grace_on_resume(manager, hass):
    """[EXT-2] a mid-run dock schedules a grace finalize; resuming cancels it."""
    _ext_setup(manager)
    try:
        # open the external slot directly, then dock to schedule the timer.
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")

        scheduled = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert scheduled is False
        timers = manager._external_grace_timers()
        assert (_VAC, "6") in timers  # a finalize is pending

        # robot resumes mid-run → the pending finalize must be cancelled.
        hass.states.async_set(_VAC, "cleaning")
        resumed = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert resumed is False
        assert (_VAC, "6") not in manager._external_grace_timers()  # cancelled
        # the capture slot survives — the run is still one record.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_grace_finalize_clears_slot(manager, hass):
    """[EXT-3] docked past the grace window with a non-mid-run task → finalize.

    The timer fires _external_grace_finalize, which clears the capture slot
    (back to the default idle state). Asserting the cleared slot is the clean
    observable for "the run was finalized"."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")
        hass.states.async_set("sensor.alfred_task", "Charging")  # NOT mid-run

        deferred = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert deferred is False
        assert (_VAC, "6") in manager._external_grace_timers()

        # advance virtual time past the grace window so the timer fires.
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] != "external"  # finalized → slot cleared
        assert slot["status"] == "idle"
        assert (_VAC, "6") not in manager._external_grace_timers()
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_grace_finalize_defers_when_mid_run(manager, hass):
    """[EXT-4] task_status reports a mid-run station cycle → finalize is deferred.

    _external_status_is_mid_run keeps the run open and reschedules the grace
    timer instead of closing it, so the slot stays "external"."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")
        # "Washing Mop" matches external_mid_run_statuses (case-insensitive).
        hass.states.async_set("sensor.alfred_task", "Washing Mop")

        deferred = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)
        assert deferred is False
        assert (_VAC, "6") in manager._external_grace_timers()

        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=EXTERNAL_FINALIZE_GRACE_S + 1)
        )
        await hass.async_block_till_done()

        # still mid-run → NOT finalized; slot held open + a fresh timer rescheduled.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
        assert (_VAC, "6") in manager._external_grace_timers()
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# External-grace state-machine residual branches — the in-progress slot that
# neither resumed nor docked, the two _external_status_is_mid_run guard rails,
# and the two _external_grace_finalize early-outs (slot already cleared / the
# robot raced the cancel back to cleaning). All real manager, no wall clock.
#
# [EXT-5] in-progress external slot + vacuum state NOT cleaning/docked/idle
#         (e.g. "paused") → no-op: returns False, schedules NO grace timer.
# [EXT-6] _external_status_is_mid_run False when the adapter declares no
#         external_mid_run_statuses (the empty-list guard).
# [EXT-7] _external_status_is_mid_run False when mid-run statuses exist but the
#         adapter wires no task_status entity (nothing to read).
# [EXT-8] _external_grace_finalize early-out when the slot is no longer
#         "external" (already resumed/cleared): no finalize, slot stays cleared.
# [EXT-9] _external_grace_finalize early-out when the robot raced the cancel back
#         to "cleaning": the slot is left "external" for the next dock.
# ---------------------------------------------------------------------------

# An adapter that declares mid-run statuses but NO task_status entity wiring,
# for the _external_status_is_mid_run "no entity" guard ([EXT-7]).
_EXT_ADAPTER_NO_TASK = {
    "adapter_id": "t",
    "source": "t",
    "entities": {"active_map": "sensor.alfred_active_map"},
    "external_mid_run_statuses": ["washing mop"],
}

# An adapter with NO mid-run statuses declared, for the empty-list guard ([EXT-6]).
_EXT_ADAPTER_NO_MIDRUN = {
    "adapter_id": "t",
    "source": "t",
    "entities": {
        "active_map": "sensor.alfred_active_map",
        "task_status": "sensor.alfred_task",
    },
}


async def test_external_run_noop_when_state_neither_cleaning_nor_home(manager, hass):
    """[EXT-5] external slot open but the vacuum is in a state that is neither
    "cleaning" (resume) nor "docked"/"idle" (dock) — e.g. "paused" — so the state
    machine does nothing: returns False and schedules no grace finalize."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "paused")  # not cleaning, not docked/idle

        handled = await manager.maybe_handle_external_run(vacuum_entity_id=_VAC)

        assert handled is False
        # neither cancelled nor scheduled a finalize: the slot just stays open.
        assert (_VAC, "6") not in manager._external_grace_timers()
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


def test_external_status_mid_run_false_without_declared_statuses(manager, hass):
    """[EXT-6] an adapter that declares no external_mid_run_statuses can never be
    mid-run — even if the task_status entity currently reads a wash cycle."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _EXT_ADAPTER_NO_MIDRUN)
    try:
        hass.states.async_set("sensor.alfred_task", "Washing Mop")
        assert manager._external_status_is_mid_run(_VAC) is False
    finally:
        unregister_adapter_config(_VAC)


def test_external_status_mid_run_false_without_task_entity(manager, hass):
    """[EXT-7] mid-run statuses are declared but the adapter wires no task_status
    entity → there is nothing to read, so it is never treated as mid-run."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _EXT_ADAPTER_NO_TASK)
    try:
        assert manager._external_status_is_mid_run(_VAC) is False
    finally:
        unregister_adapter_config(_VAC)


async def test_external_grace_finalize_skips_when_slot_not_external(manager, hass):
    """[EXT-8] the grace timer fired, but the slot is no longer "external" (the run
    already resumed or was cleared). _external_grace_finalize early-outs: it does
    not finalize, does not reschedule, and leaves the cleared slot untouched."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        manager.clear_active_job(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "docked")

        await manager._external_grace_finalize(_VAC, "6")

        # slot stays cleared (idle); nothing rescheduled.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "idle"
        assert (_VAC, "6") not in manager._external_grace_timers()
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


async def test_external_grace_finalize_skips_when_raced_back_to_cleaning(manager, hass):
    """[EXT-9] the grace timer fired but the robot raced the cancel and is "cleaning"
    again. _external_grace_finalize early-outs on the not-docked/idle guard: the
    external slot is LEFT open for the next dock rather than being finalized."""
    _ext_setup(manager)
    try:
        manager.start_external_capture(vacuum_entity_id=_VAC, map_id="6")
        hass.states.async_set(_VAC, "cleaning")  # resumed — not docked/idle

        await manager._external_grace_finalize(_VAC, "6")

        # not finalized: the run is still one open external record.
        slot = manager.get_active_job(vacuum_entity_id=_VAC, map_id="6")
        assert slot["status"] == "external"
        assert (_VAC, "6") not in manager._external_grace_timers()
    finally:
        for _cancel in list(manager._external_grace_timers().values()):
            _cancel()
        unregister_adapter_config(_VAC)


# ---------------------------------------------------------------------------
# _resolve_active_map_id — the adapter active_map -> map id lookup the external-
# run capture path keys on. Synchronous, no timers scheduled; reads only the
# registry + hass.states, so it's fully deterministic. Reuses the EXT recipe:
# register_adapter_config in setup, unregister in a finally.
#
# [EXT-5a] no active_map entity configured -> None (2496); a configured entity
#          whose state is missing / unknown / unavailable / none / blank -> None
#          (2500); a real map-id state -> str(value).
# ---------------------------------------------------------------------------

# Adapter config WITH an active_map entity wired (case b/c below). Kept minimal
# so it validates clean (no mapping/dispatch/job_segmenter blocks).
_RESOLVE_ADAPTER_WITH_MAP = {
    "adapter_id": "t",
    "source": "t",
    "entities": {"active_map": "sensor.alfred_active_map"},
}

# Adapter config with an entities block but NO active_map key (case d / line 2496).
_RESOLVE_ADAPTER_NO_MAP = {
    "adapter_id": "t",
    "source": "t",
    "entities": {"task_status": "sensor.alfred_task"},
}


@pytest.mark.parametrize(
    "missing_state",
    ["unknown", "unavailable", "none", ""],
)
def test_resolve_active_map_id_missing_state_returns_none(
    manager, hass, missing_state
):
    """[EXT-5a] a configured active_map entity in a non-value state -> None (2500).

    Covers every sentinel the guard rejects (unknown/unavailable/none/blank)
    plus, via the no-set case below, the entity-absent-from-the-state-machine
    branch (state_obj is None -> getattr default None)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _RESOLVE_ADAPTER_WITH_MAP)
    try:
        hass.states.async_set("sensor.alfred_active_map", missing_state)
        assert manager.resolve_active_map_id(_VAC) is None
    finally:
        unregister_adapter_config(_VAC)


def test_resolve_active_map_id_unset_entity_returns_none(manager, hass):
    """[EXT-5a] entity configured but never set in the state machine -> None (2500).

    state_obj is None, so getattr(state_obj, "state", None) is None and the
    sentinel guard returns None — the run-not-started case the capture path sees
    before the device reports its active map."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _RESOLVE_ADAPTER_WITH_MAP)
    try:
        # deliberately do NOT async_set sensor.alfred_active_map
        assert hass.states.get("sensor.alfred_active_map") is None
        assert manager.resolve_active_map_id(_VAC) is None
    finally:
        unregister_adapter_config(_VAC)


def test_resolve_active_map_id_returns_value(manager, hass):
    """[EXT-5a] a configured active_map entity with a real map id -> str(value)."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _RESOLVE_ADAPTER_WITH_MAP)
    try:
        hass.states.async_set("sensor.alfred_active_map", _MAP)
        resolved = manager.resolve_active_map_id(_VAC)
        assert resolved == _MAP
        assert isinstance(resolved, str)
    finally:
        unregister_adapter_config(_VAC)


def test_resolve_active_map_id_no_entity_configured_returns_none(manager, hass):
    """[EXT-5a] adapter config has no active_map entity -> None (2496).

    The `if not entity_id` guard short-circuits before any state lookup, so even
    with a populated state machine the resolver yields None when the brand maps
    no active-map signal."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    register_adapter_config(_VAC, _RESOLVE_ADAPTER_NO_MAP)
    try:
        # a populated state would resolve if active_map were wired — prove the
        # guard ignores it because no active_map entity is configured.
        hass.states.async_set("sensor.alfred_active_map", _MAP)
        assert manager.resolve_active_map_id(_VAC) is None
    finally:
        unregister_adapter_config(_VAC)


def test_resolve_active_map_id_no_adapter_config_returns_none(manager, hass):
    """[EXT-5a] no adapter registered at all -> None (2496 via empty cfg).

    get_adapter_config returns None, the `or {}` yields an empty cfg, and the
    missing active_map entity hits the same 2496 guard. No register/unregister
    needed; the registry is left clean."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    assert manager.resolve_active_map_id(_VAC) is None
