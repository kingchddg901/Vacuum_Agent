"""Proof RP-035 (RF-34) — sensor/entity platform batch.

Extended during execution (2026-08-03) to cover every finding_id in the packet
that landed as a REAL code fix, beyond the two recipes the packet's own
reproducer_script wrote out (SN-1, INF-2). Per-case notes on why each is
proved the way it is:

  1. SN-1 — A NEW VACUUM HAS NO SENSORS UNTIL A RESTART. sensor/__init__.py's
     per-vacuum loop used to iterate `manager.data["maps"]`, not the managed
     vacuums roster. Fixed to iterate `manager.data["vacuums"]`, plus two
     creation hooks (vacuum-added, room-update) so a vacuum added / a map
     imported AFTER initial platform setup gets its sensors without a reload.

  2. SN-4 — ROOM RENAME NEVER UPDATES THE SENSOR'S NAME. Only the MECHANISM
     half is driven here (does the sync have a signal to detect a rename at
     all — EufyVacuumRoomEntity.room_name). The swap itself needs the real HA
     entity registry, which this pure-function-style harness does not carry;
     that half is tests/integration/test_init_setup.py::
     test_room_rename_swaps_entity_keeping_unique_id. Same partial-coverage
     convention the rest of this corpus uses — declare the boundary rather
     than fake the mechanism.

  3. SN-8 — dead `active_job_entities` dict removed (source-shape check).

  4. SN-10b — theme sensor renders "None" (the literal string) instead of
     "none" when a library entry's stored name is None, not absent.

  5. EP-6 — four has_entity_name entities set the inert `_attr_suggested_object_id`
     (source-shape check across the four sites).

  6. EP-3 / EP-4 — EufyVacuumMaintenanceIntervalNumber's native_max_value now
     derives from the component's own declared max_interval (EP-3), and
     _attr_should_poll is honestly False (EP-4).

  7. EP-7 — a single room-field update mixing a MANAGED field with an
     UNMANAGED one no longer drops the unmanaged one.

  8. FLOW-2 / FLOW-3 — options-flow vacuum-switch source-shape checks (the
     behavioural side is tests/integration/test_config_flow.py's [OF-5]/[OF-6],
     which need the real HA config-entry flow machinery this harness doesn't
     carry).

  9. PRE-3 — behavioural side is tests/integration/test_run_plan_start_plan.py's
     [RPS-17]-[RPS-21] (needs RunPlanManager + a real manager fixture); this
     file's PRE-3 case is a source-shape check for the same reason as FLOW-2/3.

  10. PRE-4 — doc-comment-only fix (BlockedRoomEntry / RoomRuleStatus comments
      naming the real "access_dependency" literal instead of the
      never-written "access_graph"). Source-shape check; no behaviour changed.

  11. METRICS-3 — `_duration_state_to_seconds` (a pure function) now warns
      once per distinct unrecognized unit. Driven for real.

  12. METRICS-4 — station-water wiring source-shape check (the behavioural
      side is tests/integration/test_listeners_job_metrics_negative.py's
      [JMN-10]/[JMN-11], which need a real hass + manager fixture).

  13. METRICS-5 — watch_map's type annotation source-shape check (a pure
      annotation fix; every writer already stored a 4-tuple).

  14. VAC-5 — get_managed_vacuums driven against a REAL EufyVacuumManager
      (mirrors _proof_manager_reload.py / _proof_closing_batch.py's own
      convention for exercising core/manager.py directly).

  15. INF-1 — fallback-panel source-shape check (the behavioural side is
      tests/integration/test_init_setup.py's [INIT-2b], which needs the full
      config-entry setup + panel_custom patch this harness doesn't carry).

  16. INF-2 — THE LOCAL TIMEZONE IS FROZEN AT IMPORT (packet's own recipe,
      unchanged in shape). Now resolved per-call via dt_util.DEFAULT_TIME_ZONE.

DQ-PH-5 is explicitly SKIPPED (no case here) — the packet found queue_engine.py's
QueueEntry/PayloadItem/ActiveJobSnapshot disclaimer already accurate and
sufficient; no code change.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_platform_batch.py
"""

from __future__ import annotations

import datetime as _dt
import importlib
import inspect
import logging
import os
import re
import sys
import time
import zoneinfo

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

# Pin a DST-observing zone BEFORE timestamp_utils is imported. reload() covers
# the case where something already imported it. dt_util.set_default_time_zone
# mirrors what a real HA core does at startup from hass.config.time_zone — the
# fix reads dt_util.DEFAULT_TIME_ZONE fresh on every call, so this proof has to
# set that up the same way production's caller (HA core) would, or there is
# nothing DST-aware for the fix to consult.
ZONE = "America/New_York"
os.environ["TZ"] = ZONE
if hasattr(time, "tzset"):
    time.tzset()

from homeassistant.util import dt as dt_util   # noqa: E402

dt_util.set_default_time_zone(zoneinfo.ZoneInfo(ZONE))

from custom_components.eufy_vacuum import timestamp_utils   # noqa: E402

timestamp_utils = importlib.reload(timestamp_utils)

# the package's __init__.py IS the module — importing `__init__` by name picks up the
# method-wrapper on the package object instead.
from custom_components.eufy_vacuum import sensor as sensor_init   # noqa: E402


# ---------------------------------------------------------------------------
# SN-1
# ---------------------------------------------------------------------------

def case_new_vacuum_gets_no_sensors(proof: H.Proof) -> None:
    """Source-shape check against the REAL per-vacuum loop line, not a
    hardcoded/disconnected data-shape literal (the original version of this
    case computed `without_sensors` from a fixture independent of the regex
    verdict, so it could never actually flip to AFTER — fixed here so the two
    signals agree)."""
    vacuums = {"vacuum.alfred": {}, "vacuum.ivy": {}}
    maps = {"vacuum.alfred": {"12": {}}}

    src = inspect.getsource(sensor_init.async_setup_entry)
    iterates_maps_keys = bool(
        re.search(r'for\s+vacuum_entity_id\s+in\s+maps\s*(\.keys\(\))?\s*:', src)
    )
    iterates_vacuums = bool(
        re.search(r'for\s+vacuum_entity_id\s+in\s+vacuums\s*:', src)
    )
    has_creation_hooks = (
        "register_vacuum_added_callback" in src and "register_room_update_callback" in src
    )

    iterated = set(vacuums) if (iterates_vacuums and not iterates_maps_keys) else set(maps)
    without_sensors = sorted(set(vacuums) - iterated)

    proof.case(
        "two managed vacuums, one of which has not had its map imported yet",
        before=iterates_maps_keys and without_sensors == ["vacuum.ivy"],
        before_msg="no per-vacuum sensors until restart — the loop iterates the MAPS "
                   "dict, which records what has been imported, not the roster of what "
                   "the user manages; setup runs once, so importing the map later "
                   "changes nothing until HA restarts",
        after=iterates_vacuums and not iterates_maps_keys
        and not without_sensors and has_creation_hooks,
        after_msg="the loop iterates managed vacuums, and creation hooks (vacuum-added, "
                  "room-update) fill in a vacuum added / a map imported after setup "
                  "without a restart",
        detail=f"vacuums={sorted(vacuums)} · iterated by the loop as written="
               f"{sorted(iterated)} · gets NO sensors={without_sensors} · "
               f"iterates_maps_keys={iterates_maps_keys} · "
               f"iterates_vacuums={iterates_vacuums} · "
               f"has_creation_hooks={has_creation_hooks}",
    )


# ---------------------------------------------------------------------------
# SN-4 (mechanism half — see module docstring)
# ---------------------------------------------------------------------------

def case_room_rename_detectable_via_room_name(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.sensor.room_history import (
        EufyVacuumRoomCleaningHistorySensor,
    )

    stale = EufyVacuumRoomCleaningHistorySensor(
        coordinator_key="room_history_sensor", vacuum_entity_id=H.VAC, map_id=H.MAP,
        room_id=1, room_data={"name": "Kitchen"},
    )
    fresh = EufyVacuumRoomCleaningHistorySensor(
        coordinator_key="room_history_sensor", vacuum_entity_id=H.VAC, map_id=H.MAP,
        room_id=1, room_data={"name": "Great Room"},
    )
    has_room_name = hasattr(stale, "room_name")
    renamed_detectable = has_room_name and (stale.room_name != fresh.room_name)

    proof.case(
        "same room_id, renamed Kitchen -> Great Room, two freshly built entity objects",
        before=not has_room_name,
        before_msg="EufyVacuumRoomEntity exposes no room_name accessor at all -- "
                   "_sync_dynamic_entities's existing/new branch had no signal to "
                   "detect a rename and always reused the stale object, writing "
                   "its OLD cached name's state forever",
        after=renamed_detectable,
        after_msg="room_name is a real property reflecting each object's own "
                  "room_data, so the sync can compare stale.room_name != "
                  "fresh.room_name and swap instead of reusing the stale object "
                  "(the swap mechanics themselves need the HA entity registry -- "
                  "see test_init_setup.py::"
                  "test_room_rename_swaps_entity_keeping_unique_id)",
        detail=f"has_room_name={has_room_name} · stale.room_name="
               f"{getattr(stale, 'room_name', '<n/a>')!r} · fresh.room_name="
               f"{getattr(fresh, 'room_name', '<n/a>')!r}",
    )


# ---------------------------------------------------------------------------
# SN-8
# ---------------------------------------------------------------------------

def case_active_job_entities_dict_removed(proof: H.Proof) -> None:
    src = inspect.getsource(sensor_init)
    present = "active_job_entities" in src

    proof.case(
        "sensor/__init__.py source",
        before=present,
        before_msg="active_job_entities dict (keyed by (vacuum_entity_id, map_id)) "
                   "is written and never read anywhere -- EufyVacuumActiveJobSensor "
                   "self-subscribes to events directly (sensor/lifecycle.py)",
        after=not present,
        after_msg="the dead dict is gone",
        detail=f"'active_job_entities' present in source: {present}",
    )


# ---------------------------------------------------------------------------
# SN-10b
# ---------------------------------------------------------------------------

def case_theme_stored_none_name_renders_none(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.sensor.theme import EufyVacuumThemeStateSensor

    class _Mgr:
        data = {
            "theme": {
                "vacuums": {H.VAC: {"active_theme_id": "t1"}},
                "library": {"t1": {"name": None}},
            }
        }

    sensor = EufyVacuumThemeStateSensor(manager=_Mgr(), vacuum_entity_id=H.VAC)
    value = sensor.native_value

    proof.case(
        "a library entry whose name is stored as None (not absent)",
        before=value == "None",
        before_msg=".get('name', 'none')'s default only fires on an ABSENT key -- "
                   "a stored {'name': None} entry renders the literal string 'None'",
        after=value == "none",
        after_msg=".get('name') or 'none' falls back on any falsy value, "
                  "including a stored None",
        detail=f"native_value={value!r}",
    )


# ---------------------------------------------------------------------------
# EP-6
# ---------------------------------------------------------------------------

def case_suggested_object_id_removed(proof: H.Proof) -> None:
    import custom_components.eufy_vacuum.battery.sensors as _battery_sensors
    import custom_components.eufy_vacuum.binary_sensor as _binary_sensor
    import custom_components.eufy_vacuum.sensor.error as _sensor_error
    import custom_components.eufy_vacuum.sensor.lifecycle as _sensor_lifecycle

    modules = {
        "battery/sensors.py": _battery_sensors,
        "binary_sensor.py": _binary_sensor,
        "sensor/error.py": _sensor_error,
        "sensor/lifecycle.py": _sensor_lifecycle,
    }
    hits = {
        name: "_attr_suggested_object_id" in inspect.getsource(mod)
        for name, mod in modules.items()
    }

    proof.case(
        "four has_entity_name entity classes across battery/sensors.py, "
        "binary_sensor.py, sensor/error.py, sensor/lifecycle.py",
        before=all(hits.values()),
        before_msg="all four sites set _attr_suggested_object_id alongside "
                   "has_entity_name=True + translation_key -- an attribute the "
                   "convention every OTHER such entity in this codebase follows "
                   "without it",
        after=not any(hits.values()),
        after_msg="all four assignments (and battery/sensors.py's now-incorrect "
                  "explanatory comment) are gone",
        detail=f"{hits}",
    )


# ---------------------------------------------------------------------------
# EP-3 / EP-4
# ---------------------------------------------------------------------------

def case_maintenance_interval_max_from_component(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.number import (
        MAINTENANCE_INTERVAL_MAX,
        EufyVacuumMaintenanceIntervalNumber,
    )

    sig = inspect.signature(EufyVacuumMaintenanceIntervalNumber.__init__)
    accepts_max_interval = "max_interval" in sig.parameters

    kwargs = dict(
        manager=H.ManagerStub(), vacuum_entity_id=H.VAC, component="sensor",
        label="Sensor", icon="mdi:eye-outline", default_interval=60.0,
    )
    if accepts_max_interval:
        kwargs["max_interval"] = 720.0
    entity = EufyVacuumMaintenanceIntervalNumber(**kwargs)

    proof.case(
        "a component declaring max_interval_hours=720 (above the flat 500.0 constant)",
        before=(not accepts_max_interval)
        and entity._attr_native_max_value == MAINTENANCE_INTERVAL_MAX,
        before_msg="native_max_value is pinned to the flat 500.0 constant "
                   "regardless of what the component declares, so a value the "
                   "card reads as high as 720 can never be written back via "
                   "number.set_value (HA rejects anything above the entity's "
                   "own advertised max)",
        after=accepts_max_interval and entity._attr_native_max_value == 720.0,
        after_msg="native_max_value derives from the component's own declared "
                  "max_interval_hours",
        detail=f"accepts_max_interval={accepts_max_interval} · "
               f"native_max_value={entity._attr_native_max_value!r} · "
               f"MAINTENANCE_INTERVAL_MAX={MAINTENANCE_INTERVAL_MAX!r}",
    )


def case_maintenance_interval_polls_honestly(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.number import EufyVacuumMaintenanceIntervalNumber

    # HA's Entity.__init_subclass__ wraps a class-level _attr_* assignment in
    # a property for its caching machinery -- read it off an INSTANCE (which
    # resolves through that property to the real value), not the bare class.
    entity = EufyVacuumMaintenanceIntervalNumber(
        manager=H.ManagerStub(), vacuum_entity_id=H.VAC, component="sensor",
        label="Sensor", icon="mdi:eye-outline", default_interval=60.0,
    )
    should_poll = entity._attr_should_poll
    src = inspect.getsource(EufyVacuumMaintenanceIntervalNumber.async_set_native_value)
    writes_state = "async_write_ha_state" in src

    proof.case(
        "EufyVacuumMaintenanceIntervalNumber's polling contract",
        before=(should_poll is not False) and not writes_state,
        before_msg="_attr_should_poll is left unset (inherits True) and "
                   "async_set_native_value never calls async_write_ha_state() -- "
                   "only non-stale today because HA's default 30s poll happens "
                   "to paper over the missing write",
        after=(should_poll is False) and writes_state,
        after_msg="_attr_should_poll=False honestly, and async_set_native_value "
                  "writes state itself",
        detail=f"_attr_should_poll={should_poll!r} · "
               f"async_set_native_value calls async_write_ha_state={writes_state}",
    )


# ---------------------------------------------------------------------------
# EP-7
# ---------------------------------------------------------------------------

async def case_mixed_room_update_reaches_merge_branch(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.const import DOMAIN
    from custom_components.eufy_vacuum.number import EufyVacuumRoomOrderNumber

    mgr = H.ManagerStub()
    H.seed_map(mgr, H.managed_rooms(1))
    mgr.async_save = H.async_noop()
    hass = H.make_hass("/tmp/_proof_hass_ep7")
    hass.data.setdefault(DOMAIN, {})["runtime"] = mgr

    entity = EufyVacuumRoomOrderNumber(
        coordinator_key="entry1", vacuum_entity_id=H.VAC, map_id=H.MAP,
        room_id=1, room_data=mgr.data["maps"][H.VAC][H.MAP]["rooms"]["1"],
    )
    entity.hass = hass
    entity.async_write_ha_state = lambda: None

    await entity._async_update_room({"enabled": False, "color": "#ff0000"})

    room = mgr.data["maps"][H.VAC][H.MAP]["rooms"]["1"]
    color_applied = room.get("color") == "#ff0000"

    proof.case(
        "a single _async_update_room call mixing a managed field (enabled) "
        "with an unmanaged one (color)",
        before=not color_applied,
        before_msg="the managed branch (update_room_fields) applies 'enabled' "
                   "then unconditionally returns -- 'color' never reaches the "
                   "generic merge branch and is silently dropped",
        after=color_applied,
        after_msg="the managed subset applies via update_room_fields AND the "
                  "remaining keys still reach the generic merge",
        detail=f"room={room}",
    )


# ---------------------------------------------------------------------------
# FLOW-2 / FLOW-3 (source-shape — see module docstring for the behavioural half)
# ---------------------------------------------------------------------------

def case_options_flow_keeps_old_vacuum_but_warns(proof: H.Proof) -> None:
    import custom_components.eufy_vacuum.config_flow as _config_flow

    src = inspect.getsource(_config_flow.EufyVacuumOptionsFlow.async_step_init)
    # A CALL (with the opening paren), not the explanatory comment naming why
    # there ISN'T one -- the comment mentions "remove_vacuum_record" in prose.
    calls_remove = "remove_vacuum_record(" in src
    logs_warning = "_LOGGER.warning" in src and "previous_vacuum" in src

    proof.case(
        "options-flow vacuum-switch submit path",
        before=not logs_warning,
        before_msg="a vacuum switch writes the new options dict and never "
                   "reconciles (or even logs) the vacuum being replaced -- "
                   "remove_vacuum_record's one caller is the device-delete path, "
                   "never this flow",
        after=(not calls_remove) and logs_warning,
        after_msg="the old vacuum's data is deliberately KEPT (still no "
                  "remove_vacuum_record call -- that decision was pre-resolved) "
                  "and a warning names it (see test_config_flow.py [OF-6])",
        detail=f"calls_remove_vacuum_record={calls_remove} · logs_warning={logs_warning}",
    )


def case_options_flow_revalidates_vacuum_at_submit(proof: H.Proof) -> None:
    import custom_components.eufy_vacuum.config_flow as _config_flow

    src = inspect.getsource(_config_flow.EufyVacuumOptionsFlow.async_step_init)
    revalidates = "self.hass.states.get(vacuum_entity_id)" in src

    proof.case(
        "options-flow vacuum-switch submit path",
        before=not revalidates,
        before_msg="submit never re-reads HA's live state, so a stale open "
                   "dialog can resurrect a just-device-deleted vacuum by "
                   "resubmitting the (now-invalid) rendered default",
        after=revalidates,
        after_msg="submit re-validates the submitted vacuum id against HA's "
                  "live state, refusing (vacuum_not_found) if it no longer "
                  "exists (see test_config_flow.py [OF-5])",
        detail=f"revalidates={revalidates}",
    )


# ---------------------------------------------------------------------------
# PRE-3 (source-shape — see test_run_plan_start_plan.py [RPS-17]-[RPS-21] for
# the behavioural half; RunPlanManager needs a real manager fixture this
# harness doesn't carry)
# ---------------------------------------------------------------------------

def case_preflight_available_touched_on_every_blocked_path(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.planning import run_plan

    src = inspect.getsource(run_plan.RunPlanManager._build_effective_start_plan)
    graph_block = src[src.index('if _graph_block_reason:'):src.index('selected_room_id_set')]
    access_block = src[src.index('if has_blocker_rules'):src.index('for room in all_rooms:')]
    final_block = src[src.index('message = "Ready to start cleaning."'):]

    touches = {
        "graph_block_branch": '"available": False' in graph_block,
        "access_graph_required_branch": '"available": False' in access_block,
        "final_branch": '"available":' in final_block,
    }

    proof.case(
        "the three places _build_effective_start_plan finalizes `preflight`",
        before=not any(touches.values()),
        before_msg="preflight['available'] is set True once at the top of the "
                   "function and never touched again anywhere -- it stays True "
                   "even when blocked=True or every selected room ends up "
                   "blocked (included_room_count==0)",
        after=all(touches.values()),
        after_msg="all three finalization points set available appropriately -- "
                  "False on a structural graph block, and False in the success "
                  "path specifically when nothing ended up includable (see "
                  "test_run_plan_start_plan.py [RPS-17]-[RPS-21])",
        detail=f"{touches}",
    )


# ---------------------------------------------------------------------------
# PRE-4 (doc-comment-only; no behaviour changed)
# ---------------------------------------------------------------------------

def case_block_source_comment_matches_real_literal(proof: H.Proof) -> None:
    """Checks the FIELD-LEVEL inline comments specifically (not the class
    docstring prose, which is allowed to keep a historical "used to say X"
    note about the old wrong value without that counting as still-wrong)."""
    from custom_components.eufy_vacuum.jobs import job_monitor
    from custom_components.eufy_vacuum.models import models

    job_monitor_src = inspect.getsource(job_monitor.BlockedRoomEntry)
    source_field_line = next(
        line for line in job_monitor_src.splitlines()
        if line.strip().startswith("source:")
    )
    models_src = inspect.getsource(models)
    last_block_source_line = next(
        line for line in models_src.splitlines() if "last_block_source" in line
    )

    wrong_still_present = (
        '"access_graph"' in source_field_line or '"access_graph"' in last_block_source_line
    )
    right_present = (
        "access_dependency" in source_field_line
        and "access_dependency" in last_block_source_line
    )

    proof.case(
        "BlockedRoomEntry's docstring/comment + RoomRuleStatus.last_block_source's comment",
        before=wrong_still_present,
        before_msg='both comments document the pair "direct_rule"|"access_graph" -- '
                   '"access_graph" as a literal value is never actually written '
                   "anywhere; the real value planning/run_plan.py writes is "
                   '"access_dependency"',
        after=right_present and not wrong_still_present,
        after_msg="both comments now name the real value the code actually "
                  "emits (documentation-truth fix only -- the literal itself "
                  "was never renamed)",
        detail=f"wrong_literal_still_present={wrong_still_present} · "
               f"right_literal_present={right_present}",
    )


# ---------------------------------------------------------------------------
# METRICS-3
# ---------------------------------------------------------------------------

class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def case_duration_unit_unrecognized_warns_once(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.listeners import job_metrics as jm

    has_warned_set = hasattr(jm, "_WARNED_UNKNOWN_DURATION_UNITS")
    if has_warned_set:
        jm._WARNED_UNKNOWN_DURATION_UNITS.clear()

    cap = _CaptureHandler()
    jm._LOGGER.addHandler(cap)
    jm._LOGGER.setLevel(logging.WARNING)
    try:
        jm._duration_state_to_seconds("300", "fortnight")
        jm._duration_state_to_seconds("301", "fortnight")
        second_value = jm._duration_state_to_seconds("301", "fortnight")
    finally:
        jm._LOGGER.removeHandler(cap)

    warnings = [r for r in cap.records if "fortnight" in r.getMessage()]

    proof.case(
        "two-plus calls with the same unrecognized unit 'fortnight'",
        before=not has_warned_set,
        before_msg="an unrecognized unit silently falls through to bare-seconds "
                   "with no signal at all -- no d/w/us handling, no log",
        after=has_warned_set and len(warnings) == 1 and second_value == 301,
        after_msg="still falls through to seconds (unchanged, non-numeric-looking "
                  "units aren't rejected) AND logs once for the distinct "
                  "unrecognized unit, not once per call",
        detail=f"has_warned_set={has_warned_set} · warnings_logged={len(warnings)} · "
               f"value={second_value!r}",
    )


# ---------------------------------------------------------------------------
# METRICS-4 (source-shape — see test_listeners_job_metrics_negative.py
# [JMN-10]/[JMN-11] for the behavioural half; register() needs a real hass +
# manager fixture this harness doesn't carry)
# ---------------------------------------------------------------------------

def case_station_water_requires_capability_check(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.listeners import job_metrics as jm

    src = inspect.getsource(jm.register)
    checks_capability = "supports_station_water" in src
    bare_except_pass = bool(re.search(r'except Exception:\s*\n\s*pass\b', src))

    proof.case(
        "job_metrics.register's station-water wiring block",
        before=(not checks_capability),
        before_msg="wires a guessed 'water_level'/'station_water' entity key "
                   "with no supports_station_water check at all, and swallows "
                   "any lookup exception in a bare except-pass with no log",
        after=checks_capability and not bare_except_pass,
        after_msg="checks supports_station_water explicitly before wiring, and "
                  "logs (not silently swallows) a lookup failure",
        detail=f"checks_capability={checks_capability} · "
               f"bare_except_pass_present={bare_except_pass}",
    )


# ---------------------------------------------------------------------------
# METRICS-5
# ---------------------------------------------------------------------------

def case_watch_map_tuple_arity_annotation(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.listeners import job_metrics as jm

    src = inspect.getsource(jm.register)
    three_tuple = bool(
        re.search(r'watch_map:\s*dict\[str,\s*tuple\[str,\s*str,\s*str\]\]', src)
    )
    four_tuple = bool(
        re.search(
            r'watch_map:\s*dict\[str,\s*tuple\[str,\s*str,\s*str,\s*str\s*\|\s*None\]\]',
            src,
        )
    )

    proof.case(
        "watch_map's declared type vs. the 4-tuples every writer actually stores",
        before=three_tuple,
        before_msg="annotated as a 3-tuple while every writer (cleaning_time, "
                   "cleaning_area, battery, station-water) stores a 4-tuple and "
                   "the unpack expects four fields",
        after=four_tuple and not three_tuple,
        after_msg="annotation corrected to the real 4-tuple shape (int-branch "
                  "battery watcher, RP-013e, is live code and was left alone)",
        detail=f"three_tuple_pattern_found={three_tuple} · "
               f"four_tuple_pattern_found={four_tuple}",
    )


# ---------------------------------------------------------------------------
# VAC-5
# ---------------------------------------------------------------------------

async def case_managed_vacuums_capabilities_populated(proof: H.Proof) -> None:
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    mgr = EufyVacuumManager(H.make_hass("/tmp/_proof_hass_vac5"))
    await mgr.async_initialize()
    # Seed the vacuum record directly (not via ensure_vacuum_record, which
    # needs a real entity registry lookup this bare hass double doesn't carry
    # -- matches _proof_closing_batch.py's own cb_4 convention). No
    # refresh_vacuum_capabilities / get_vacuum_capabilities call at all --
    # a genuinely cold read.
    mgr.data["vacuums"][H.VAC] = {
        "vacuum_entity_id": H.VAC, "detected_model": None, "is_managed": True,
    }
    # get_vacuum_capabilities (the function under test, VIA get_managed_vacuums)
    # itself calls ensure_vacuum_record -> _get_registry_model_code, an
    # unrelated collaborator that needs a real, loaded entity registry this
    # bare hass double doesn't carry. Neutralize just that one collaborator
    # -- production logic (get_vacuum_capabilities/get_managed_vacuums
    # themselves) is untouched.
    mgr._get_registry_model_code = lambda *, vacuum_entity_id: None
    cold = H.VAC not in mgr.data.get("capabilities", {})

    result = mgr.get_managed_vacuums()
    entry = result["vacuums"][0]

    proof.case(
        "a managed vacuum with no capability snapshot recorded yet",
        before=cold and entry.get("supports_rooms") is None,
        before_msg="reads data['capabilities'].get(vacuum_id, {}) raw -- an "
                   "empty/missing snapshot reports None for every supports_* "
                   "field even though the vacuum genuinely exists",
        after=cold and entry.get("supports_rooms") is not None,
        after_msg="routed through get_vacuum_capabilities(refresh=False), which "
                  "detects on a cold read and guarantees a real snapshot",
        detail=f"cold_read={cold} · entry={entry}",
    )


# ---------------------------------------------------------------------------
# INF-1 (source-shape — see test_init_setup.py [INIT-2b] for the behavioural
# half; the fallback-panel path needs the full config-entry setup + a
# panel_custom patch this harness doesn't carry)
# ---------------------------------------------------------------------------

def case_fallback_panel_uses_shared_constants(proof: H.Proof) -> None:
    import custom_components.eufy_vacuum as _init_module

    src = inspect.getsource(_init_module.async_setup_entry)
    fallback_block = src[src.index("if not registered_panels:"):]

    hand_retyped = (
        'webcomponent_name="eufy-vacuum-command-center"' in fallback_block
        or 'sidebar_title="Vacuum Agent"' in fallback_block
        or 'sidebar_icon="mdi:robot-vacuum"' in fallback_block
    )
    uses_constants = (
        "webcomponent_name=WEBCOMPONENT_NAME" in fallback_block
        and "sidebar_title=DEFAULT_PANEL_TITLE" in fallback_block
        and "sidebar_icon=PANEL_ICON" in fallback_block
    )

    proof.case(
        "the fallback-panel registration block (no vacuum configured yet)",
        before=hand_retyped,
        before_msg="panels.py's own docstring claims DEFAULT_PANEL_TITLE / "
                   "PANEL_ICON / WEBCOMPONENT_NAME are the single source of "
                   "truth for three call sites -- but this fourth site "
                   "hand-retypes all three literals instead of importing them",
        after=uses_constants and not hand_retyped,
        after_msg="imports and uses the real constants at this site too "
                  "(see test_init_setup.py [INIT-2b])",
        detail=f"hand_retyped_literals_present={hand_retyped} · "
               f"uses_shared_constants={uses_constants}",
    )


# ---------------------------------------------------------------------------
# INF-2 (packet's own recipe)
# ---------------------------------------------------------------------------

def case_timezone_frozen_at_import(proof: H.Proof) -> None:
    zone = zoneinfo.ZoneInfo(ZONE)
    winter_naive, summer_naive = "2026-01-15T12:00:00", "2026-07-15T12:00:00"

    def applied_offset(naive: str) -> float:
        """The UTC offset parse_timestamp assumed, in hours, signed like utcoffset()."""
        parsed = timestamp_utils.parse_timestamp(naive, assume_local_naive=True)
        wall = _dt.datetime.fromisoformat(naive)
        # wall-clock reading minus the UTC result == the offset that was assumed.
        return (wall.replace(tzinfo=_dt.timezone.utc) - parsed).total_seconds() / 3600

    def correct_offset(naive: str) -> float:
        """Same sign convention, so before/after compare like with like. Getting these
        two out of step is how a reproducer ends up unable to flip."""
        return _dt.datetime.fromisoformat(naive).replace(
            tzinfo=zone).utcoffset().total_seconds() / 3600

    got_winter, got_summer = applied_offset(winter_naive), applied_offset(summer_naive)
    want_winter, want_summer = correct_offset(winter_naive), correct_offset(summer_naive)

    proof.case(
        f"a January and a July naive timestamp parsed in {ZONE} (DST differs by 1 h)",
        before=got_winter == got_summer,
        before_msg="one offset stamped on both dates — _LOCAL_TZ is a fixed offset "
                   "captured at module import, so whichever season the install started "
                   "in decides how every timestamp of every other season is read",
        after=got_winter != got_summer
        and abs(got_winter - want_winter) < 0.01
        and abs(got_summer - want_summer) < 0.01,
        after_msg="the offset is resolved per timestamp from its own date, via "
                  "dt_util.DEFAULT_TIME_ZONE read fresh on every call",
        detail=f"applied: Jan {got_winter:+.0f}h, Jul {got_summer:+.0f}h · correct for "
               f"{ZONE}: Jan {want_winter:+.0f}h, Jul {want_summer:+.0f}h · "
               f"dt_util.DEFAULT_TIME_ZONE={dt_util.DEFAULT_TIME_ZONE!r}",
    )


SYNC_CASES = [
    case_new_vacuum_gets_no_sensors,
    case_room_rename_detectable_via_room_name,
    case_active_job_entities_dict_removed,
    case_theme_stored_none_name_renders_none,
    case_suggested_object_id_removed,
    case_maintenance_interval_max_from_component,
    case_maintenance_interval_polls_honestly,
    case_options_flow_keeps_old_vacuum_but_warns,
    case_options_flow_revalidates_vacuum_at_submit,
    case_preflight_available_touched_on_every_blocked_path,
    case_block_source_comment_matches_real_literal,
    case_duration_unit_unrecognized_warns_once,
    case_station_water_requires_capability_check,
    case_watch_map_tuple_arity_annotation,
    case_fallback_panel_uses_shared_constants,
    case_timezone_frozen_at_import,
]

ASYNC_CASES = [
    case_mixed_room_update_reaches_merge_branch,
    case_managed_vacuums_capabilities_populated,
]


async def main() -> int:
    proof = H.Proof("RP-035", "sensor/entity platform batch (RF-34)")
    for case_fn in SYNC_CASES:
        case_fn(proof)
    for case_fn in ASYNC_CASES:
        await case_fn(proof)
    return proof.finish()


H.run(main)
