"""
Room-drift detection and setup-step bookkeeping.

The setup state machine is data-driven by the adapter's `setup.steps`
declaration. Each step ID has a completion predicate and may correspond
to a service the user (or card) calls to advance the step.

Drift between the vacuum's reported room list and the integration's
configured rooms is the key signal that the `save_rooms` step has
re-opened — discovered rooms with no `is_configured` flag, or
configured rooms no longer visible to the vacuum, both flip the
overall setup state out of "ready".

To prevent transient API glitches from producing spurious removal
notifications, removed rooms must be missing for
`removal_confirmation_passes` consecutive discovery passes before
they are flagged. New rooms surface on first sighting by default.

This module is framework-only — every brand-specific input
(adapter config, room list source, step list) is read from the
adapter registry. The Eufy adapter is the reference declaration.

Public entry points:

    compute_room_drift(manager, vacuum_entity_id) -> dict
        Live drift snapshot — new/removed/transient/in_sync.

    update_drift_history(manager, vacuum_entity_id, discovered_ids)
        Called by every discovery pass. Increments missing-pass
        counters and resets last_seen timestamps.

    reject_rooms(manager, vacuum_entity_id, room_ids, map_id) -> dict
    unreject_rooms(manager, vacuum_entity_id, room_ids, map_id) -> dict
        Hide / un-hide phantom room ids. Scoped to ONE map — ids are
        reissued per map, so a ghost id downstairs is a real room
        upstairs (A4-SETUP-6).

    rejected_room_ids(record, map_id) -> set[int]
        The single reader for "is this id rejected here?" — resolves the
        per-map store and the legacy flat list together.

    record_step_completed(manager, vacuum_entity_id, step_id)
        Mark a setup step as complete in setup_progress.

    is_step_completed(progress, step_id) -> bool
        Predicate for "has this step been marked complete?"

    SETUP_STEP_IDS
        Closed enum of legal step IDs the framework understands.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config
from ..const import DATA_RUNTIME, DOMAIN
from ..learning.utils import _iso_now

# Closed enum of setup step IDs. Adapters must declare a subset of these
# values; the registry rejects unknown IDs at adapter registration time.
SETUP_STEP_IDS: frozenset[str] = frozenset({
    "add_vacuum",
    "import_active_map",
    "save_rooms",
    # Future:
    "calibrate_map",
    "set_dock_position",
})

# Display labels for each step ID. Adapters do not override these —
# the framework controls step semantics, the adapter only declares
# which steps apply.
SETUP_STEP_LABELS: dict[str, str] = {
    "add_vacuum": "Add vacuum",
    "import_active_map": "Import active map",
    "save_rooms": "Configure rooms",
    "calibrate_map": "Calibrate map",
    "set_dock_position": "Set dock position",
}

# Service each step ID maps to. The card calls these via
# eufy_vacuum.<service_name>.
SETUP_STEP_SERVICES: dict[str, str] = {
    "add_vacuum": "setup_add_vacuum",
    "import_active_map": "setup_import_active_map",
    "save_rooms": "setup_save_rooms",
    "calibrate_map": "calibrate_map",         # mapping_services
    "set_dock_position": "set_dock_anchor",   # mapping_services
}

# Default discovery cadence values when the adapter omits them.
_DEFAULT_REMOVAL_CONFIRM_PASSES = 3
_DEFAULT_NEW_ROOM_CONFIRM_PASSES = 1
_DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS = 21_600  # 6 hours
_DEFAULT_AUTO_REFRESH_TRIGGERS: tuple[str, ...] = (
    "vacuum_docked",
    "active_map_changed",
    "config_entry_reload",
)

# Default setup.steps when the adapter omits the section. Brand-new
# adapters get the minimum viable setup flow.
_DEFAULT_SETUP_STEPS: tuple[str, ...] = ("add_vacuum", "save_rooms")


def get_adapter_setup_steps(vacuum_entity_id: str) -> list[str]:
    """Return the adapter-declared list of setup steps for one vacuum.

    Filters out unknown step IDs (defence in depth — registration should
    have rejected them, but if they slipped through, ignore rather than
    crash). Falls back to the default minimal step list when absent.
    """
    cfg = (get_adapter_config(vacuum_entity_id) or {}).get("setup", {}) or {}
    declared = cfg.get("steps")
    if not declared:
        return list(_DEFAULT_SETUP_STEPS)
    return [s for s in declared if s in SETUP_STEP_IDS]


def get_discovery_cadence(vacuum_entity_id: str) -> dict[str, Any]:
    """Read auto-discovery cadence config with safe defaults."""
    disc = (get_adapter_config(vacuum_entity_id) or {}).get("discovery", {}) or {}
    return {
        # DR-SETUP-2: `is not None` (not `or`), matching auto_refresh_interval_seconds
        # right below -- `or` silently reverts a configured falsy value (an adapter
        # declaring auto_refresh_on: [] to wire NO auto-discovery triggers) back to
        # the default, exactly the CS-2 shape already fixed for this dict's other keys.
        "auto_refresh_on": list(
            disc.get("auto_refresh_on")
            if disc.get("auto_refresh_on") is not None
            else _DEFAULT_AUTO_REFRESH_TRIGGERS
        ),
        "auto_refresh_interval_seconds": int(
            disc.get("auto_refresh_interval_seconds")
            if disc.get("auto_refresh_interval_seconds") is not None
            else _DEFAULT_AUTO_REFRESH_INTERVAL_SECONDS
        ),
        # An explicit value is honored down to the meaningful floor of 1 (flag on
        # the first pass). Use `is not None` (not `or`) so a configured low value
        # isn't silently reverted to the default — but clamp with max(1, ...): a
        # literal 0 would make `missing_passes >= n_remove` a tautology (every
        # configured room flagged removed, even present ones), so 0/negative means
        # "as aggressive as valid" = 1, not the surprising default.
        "removal_confirmation_passes": max(1, int(
            disc.get("removal_confirmation_passes")
            if disc.get("removal_confirmation_passes") is not None
            else _DEFAULT_REMOVAL_CONFIRM_PASSES
        )),
        "new_room_confirmation_passes": max(1, int(
            disc.get("new_room_confirmation_passes")
            if disc.get("new_room_confirmation_passes") is not None
            else _DEFAULT_NEW_ROOM_CONFIRM_PASSES
        )),
    }


def _get_progress_record(
    manager: Any, vacuum_entity_id: str
) -> dict[str, Any]:
    """Return the setup_progress record for one vacuum, creating it if absent.

    Always returns the live mutable dict on manager.data — callers can
    write directly and changes persist on the next manager.async_save().
    """
    root = manager.data.setdefault("setup_progress", {})
    record = root.setdefault(
        vacuum_entity_id,
        {
            "completed_steps": [],
            "last_advanced_at": None,
            "rejected_rooms": [],
            "room_drift_history": {},
        },
    )
    # Defence in depth — older records may be missing the history field.
    record.setdefault("room_drift_history", {})
    record.setdefault("rejected_rooms", [])
    record.setdefault("rejected_rooms_by_map", {})
    record.setdefault("completed_steps", [])
    return record


def rejected_room_ids(
    record: dict[str, Any], *, map_id: str | None = None
) -> set[int]:
    """Ids the user has rejected as phantoms, resolved FOR ONE MAP.

    A4-SETUP-6. Rejection used to be stored as one flat per-VACUUM list while the
    thing being rejected is per-MAP: Eufy reissues ids 1..N from scratch on every
    map, so id 3 is a different physical room on each floor. Rejecting a ghost id 3
    on the ground floor therefore made the REAL id 3 upstairs unconfigurable —
    permanently, and silently, because a rejected id never surfaces in ``new_rooms``
    for the user to notice. Nothing in the record said which map the rejection was
    made on, so nothing could tell the two apart.

    Two backings, deliberately:

    * ``rejected_rooms_by_map`` — every rejection written from now on. Applies to
      its own map only.
    * ``rejected_rooms`` — the LEGACY flat list. Applied to every map, because the
      id genuinely carries no map and inventing one would be a guess. That is also
      what the user meant: these were recorded when one map existed, so "every map"
      and "the map I was looking at" were the same set. It is read but never
      appended to again, so the ambiguity stops growing. ``unreject_rooms`` is the
      way out of a legacy entry that blocks a real room on a second floor.

    ``map_id=None`` unions every map. That is a REPORTING superset — "every id
    rejected anywhere on this vacuum" — and it is the wrong input for any decision
    about a specific room, because over-reporting here hides a real room, which is
    the defect itself. Every production caller passes a map; the WRITE paths
    refuse rather than default (``_resolve_rejection_map``). Do not reach for the
    None form to avoid resolving a map.
    """
    ids: set[int] = set()

    def _absorb(values: Any) -> None:
        for raw in values or []:
            try:
                ids.add(int(raw))
            except (TypeError, ValueError):
                continue

    _absorb(record.get("rejected_rooms"))

    by_map = record.get("rejected_rooms_by_map") or {}
    if not isinstance(by_map, dict):
        return ids
    if map_id is None:
        for per_map in by_map.values():
            _absorb(per_map)
    else:
        _absorb(by_map.get(str(map_id)))
    return ids


def rejected_room_ids_for(
    manager: Any, vacuum_entity_id: str, *, map_id: str | None = None
) -> set[int]:
    """``rejected_room_ids`` for a vacuum, read WITHOUT creating its record.

    Deliberately not routed through ``_get_progress_record``: that helper
    ``setdefault``s the record into existence, which is right for the write paths
    that own it but wrong here. This is called from ``save_managed_rooms``, and a
    room save must not materialise setup-progress state as a side effect of
    asking a question. Missing record -> no rejections, which is the correct
    answer for a vacuum that has never rejected anything.
    """
    record = (manager.data.get("setup_progress") or {}).get(vacuum_entity_id) or {}
    return rejected_room_ids(record, map_id=map_id)


def _known_map_ids(manager: Any, vacuum_entity_id: str) -> list[str]:
    """Every map id this vacuum has a stored bucket for, sorted."""
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    return sorted(str(m) for m in vac_maps if isinstance(vac_maps.get(m), dict))


def _resolve_rejection_map(
    manager: Any, vacuum_entity_id: str, map_id: str | None
) -> tuple[str | None, dict[str, Any] | None]:
    """Pin a rejection to one map, or REFUSE when that cannot be done.

    ``map_id=None`` means "the only map" — never "every map". That distinction is
    the whole of A4-SETUP-6: room ids are reissued per map, so treating an
    unqualified id as vacuum-global is what let a ghost id downstairs block a real
    room upstairs. A recovery path that quietly did the same thing in reverse
    would be the same defect wearing the other hat, so both directions refuse.

    Returns ``(resolved_map_id, refusal)``. Exactly one is meaningful:

    * 0 maps  -> ``(None, None)``. Nothing to scope to, nothing to get wrong.
    * 1 map   -> ``(that map, None)``. Unambiguous, so no reason to make the
      caller say it.
    * 2+ maps -> ``(None, refusal)``. We genuinely do not know which floor the
      user meant, and guessing "all of them" is how this defect happened. The
      refusal NAMES the maps so the caller can re-issue with one, mirroring
      ``save_managed_rooms``' ``{"saved": False, "reason": ...}`` and the access
      graph's refuse-without-writing contract.
    """
    if map_id is not None:
        return str(map_id), None
    known = _known_map_ids(manager, vacuum_entity_id)
    if len(known) > 1:
        return None, {
            "status": "error",
            "reason": "map_ambiguous",
            "message": (
                "This vacuum has more than one map and room IDs are reused "
                "across maps, so a room ID alone does not identify a room. "
                f"Re-send with one of map_id: {', '.join(known)}."
            ),
            "map_ids": known,
        }
    return (known[0] if known else None), None


def is_step_completed(progress: dict[str, Any], step_id: str) -> bool:
    """Has this setup step been marked complete?"""
    return step_id in (progress.get("completed_steps") or [])


def record_step_completed(
    manager: Any, vacuum_entity_id: str, step_id: str
) -> None:
    """Mark one setup step as complete in setup_progress.

    Idempotent — repeated calls don't duplicate the step. Updates
    last_advanced_at to the current ISO timestamp.
    """
    if step_id not in SETUP_STEP_IDS:
        return
    record = _get_progress_record(manager, vacuum_entity_id)
    completed = record["completed_steps"]
    if step_id not in completed:
        completed.append(step_id)
    record["last_advanced_at"] = _iso_now()


def active_map_configured(manager: Any, vacuum_entity_id: str) -> bool | None:
    """Whether the ACTIVE map currently has >= 1 configured room.

    Returns ``None`` when the active map can't be determined — the adapter declares no
    ``entities.active_map`` (brand without an active-map concept) or the entity is
    unknown/unavailable — so callers leave sticky step completion untouched.

    This backs the "re-open save_rooms" guard: the save_rooms completion flag is sticky,
    but a factory reset / switch to a fresh map id can leave it set against a now-dead
    map while the ACTIVE map has no configured rooms. Scoping the check to the active map
    (not "any map ever configured") is what distinguishes a genuinely-configured setup
    from a stale flag pointing at a map that no longer matters.
    """
    entities = (get_adapter_config(vacuum_entity_id) or {}).get("entities", {}) or {}
    am_entity = entities.get("active_map")
    if not am_entity:
        return None
    state = manager.hass.states.get(am_entity)
    if state is None or state.state in ("unknown", "unavailable", "", None):
        return None
    bucket = (
        manager.data.get("maps", {})
        .get(vacuum_entity_id, {})
        .get(str(state.state))
    )
    if not isinstance(bucket, dict):
        return False
    return any(
        isinstance(room, dict) and room.get("is_configured")
        for room in (bucket.get("rooms") or {}).values()
    )


def _list_configured_room_ids(
    manager: Any, vacuum_entity_id: str
) -> set[int]:
    """Every configured room ID across all maps for one vacuum.

    A room is "configured" iff `is_configured` is True. The migration
    shim stamps existing rooms True; new rooms enter False and require
    the save_rooms step to flip them.
    """
    out: set[int] = set()
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    for bucket in vac_maps.values():
        if not isinstance(bucket, dict):
            continue
        for room_id_key, room in (bucket.get("rooms") or {}).items():
            if not isinstance(room, dict):
                continue
            if not room.get("is_configured"):
                continue
            try:
                out.add(int(room.get("room_id", room_id_key)))
            except (TypeError, ValueError):
                continue
    return out


def _room_lookup(
    manager: Any, vacuum_entity_id: str
) -> dict[int, dict[str, Any]]:
    """Return {room_id: {name, map_id}} for every room on every map.

    Used to enrich the new/removed lists in compute_room_drift with
    display-friendly metadata.
    """
    out: dict[int, dict[str, Any]] = {}
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    for map_id, bucket in vac_maps.items():
        if not isinstance(bucket, dict):
            continue
        for room_id_key, room in (bucket.get("rooms") or {}).items():
            if not isinstance(room, dict):
                continue
            try:
                rid = int(room.get("room_id", room_id_key))
            except (TypeError, ValueError):
                continue
            out[rid] = {
                "room_id": rid,
                "name": str(room.get("name", f"Room {rid}")),
                "map_id": str(map_id),
            }
    return out


def update_drift_history(
    manager: Any,
    vacuum_entity_id: str,
    discovered_room_ids: set[int],
    map_id: str | None = None,
) -> None:
    """Update per-room missing-pass counters from one discovery pass.

    Called every time a discovery pass runs (auto-trigger or manual).
    Increments `missing_passes` for configured rooms not in the
    discovered set; resets counters for rooms that reappear.

    ``map_id`` is the map ``discovered_room_ids`` was read from — the live room
    list describes whichever map is LOADED, so a pass always has one. It selects
    which rejections apply (A4-SETUP-6); omitting it falls back to the union over
    every map, which is what a single-map install has always done.

    The history dict lives on the manager's setup_progress storage and
    is persisted on the next manager.async_save().
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    history: dict[str, dict[str, Any]] = record["room_drift_history"]
    now = _iso_now()

    configured_ids = _list_configured_room_ids(manager, vacuum_entity_id)
    rejected_ids = rejected_room_ids(record, map_id=map_id)

    # Update history for every room the framework cares about — both
    # configured and newly-discovered. Rejected rooms never enter the
    # history (they're explicitly out of scope).
    relevant_ids = (configured_ids | discovered_room_ids) - rejected_ids

    for rid in relevant_ids:
        key = str(rid)
        entry = history.setdefault(
            key,
            {
                "missing_passes": 0,
                "seen_passes": 0,
                "last_seen_at": None,
                "first_missed_at": None,
                "first_seen_at": None,
            },
        )
        if rid in discovered_room_ids:
            if entry.get("first_seen_at") is None:
                entry["first_seen_at"] = now
            entry["seen_passes"] = int(entry.get("seen_passes", 0)) + 1
            entry["missing_passes"] = 0
            entry["last_seen_at"] = now
            entry["first_missed_at"] = None
        else:
            entry["missing_passes"] = int(entry.get("missing_passes", 0)) + 1
            if entry.get("first_missed_at") is None:
                entry["first_missed_at"] = now
            # Reset seen_passes — a new sighting streak starts when the
            # room reappears.
            entry["seen_passes"] = 0

    # Clean up stale entries for rooms that no longer exist anywhere
    # (configured AND not currently discovered AND not in history-relevant
    # set). This prevents history from growing unboundedly across years.
    # DR-SETUP-3: guarded like every other room-id coercion in this module
    # (_room_lookup, _list_configured_room_ids) -- a hand-edited or migrated
    # record with a non-numeric key must not crash the whole discovery pass.
    stale_keys = []
    for key in list(history.keys()):
        try:
            rid = int(key)
        except (TypeError, ValueError):
            continue
        if rid not in relevant_ids:
            stale_keys.append(key)
    for key in stale_keys:
        history.pop(key, None)


def compute_room_drift(
    manager: Any,
    vacuum_entity_id: str,
    discovered_room_ids: set[int] | None = None,
    map_id: str | None = None,
) -> dict[str, Any]:
    """Compute the current room drift snapshot for one vacuum.

    ``discovered_room_ids`` is the live set of room IDs the adapter's
    discovery source currently reports. When None, returns drift based
    only on stored history (no live read) — useful for status responses
    that don't want to re-probe the vacuum.

    ``map_id`` scopes which rejections apply (A4-SETUP-6). Omitted, the snapshot
    unions every map's rejections — the same superset the flat list always gave,
    and the right answer for a whole-vacuum status read that is not asking about
    one map.

    Returns:
        {
            "in_sync": bool,
            "new_rooms":           [{room_id, name, map_id}, ...],
            "removed_rooms":       [{room_id, name, map_id}, ...],
            "transiently_missing": [{room_id, name, map_id}, ...],
            "rejected_rooms":      [room_id, ...],
        }

    New rooms surface after `new_room_confirmation_passes` consecutive
    sightings (default 1 — immediate). Removed rooms surface after
    `removal_confirmation_passes` consecutive misses (default 3).
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    cadence = get_discovery_cadence(vacuum_entity_id)
    history: dict[str, dict[str, Any]] = record["room_drift_history"]
    rejected_ids = rejected_room_ids(record, map_id=map_id)
    configured_ids = _list_configured_room_ids(manager, vacuum_entity_id)
    lookup = _room_lookup(manager, vacuum_entity_id)

    n_remove = cadence["removal_confirmation_passes"]
    n_new = cadence["new_room_confirmation_passes"]

    # Confirmed removals: configured rooms whose missing-pass counter
    # has met the threshold.
    confirmed_removed_ids: set[int] = {
        rid for rid in configured_ids
        if int(history.get(str(rid), {}).get("missing_passes", 0)) >= n_remove
    }

    # New rooms: discovered but not configured and not rejected, with
    # seen_passes >= threshold. When discovered_room_ids is None we
    # derive "new" from history alone — any room in history with
    # missing_passes == 0 and seen_passes >= n_new and not configured.
    if discovered_room_ids is not None:
        new_candidate_ids = (
            discovered_room_ids - configured_ids - rejected_ids
        )
        new_confirmed_ids: set[int] = {
            rid for rid in new_candidate_ids
            if int(history.get(str(rid), {}).get("seen_passes", 0)) >= n_new
            or n_new <= 1  # immediate-surface mode: don't wait
        }
        # Transiently-missing: configured rooms not currently discovered
        # but below the removal threshold.
        transiently_missing_ids: set[int] = (
            configured_ids - discovered_room_ids - confirmed_removed_ids
        )
    else:
        # DR-SETUP-3: guarded like every other room-id coercion in this
        # module -- a hand-edited or migrated record with a non-numeric
        # key must not crash this branch.
        new_confirmed_ids = set()
        for key, entry in history.items():
            try:
                rid = int(key)
            except (TypeError, ValueError):
                continue
            if (
                int(entry.get("seen_passes", 0)) >= n_new
                and int(entry.get("missing_passes", 0)) == 0
                and rid not in configured_ids
                and rid not in rejected_ids
            ):
                new_confirmed_ids.add(rid)
        transiently_missing_ids = {
            rid for rid in configured_ids
            if int(history.get(str(rid), {}).get("missing_passes", 0)) > 0
            and rid not in confirmed_removed_ids
        }

    def _enrich(ids: set[int]) -> list[dict[str, Any]]:
        return sorted(
            (lookup.get(rid) or {"room_id": rid, "name": f"Room {rid}", "map_id": ""}
             for rid in ids),
            key=lambda r: r.get("room_id", 0),
        )

    in_sync = (
        not new_confirmed_ids
        and not confirmed_removed_ids
        and not transiently_missing_ids
    )

    return {
        "in_sync": in_sync,
        "new_rooms": _enrich(new_confirmed_ids),
        "removed_rooms": _enrich(confirmed_removed_ids),
        "transiently_missing": _enrich(transiently_missing_ids),
        "rejected_rooms": sorted(rejected_ids),
    }


def reject_rooms(
    manager: Any,
    vacuum_entity_id: str,
    room_ids: list[int],
    map_id: str | None = None,
) -> dict[str, Any]:
    """Move room IDs into the rejected set for ONE map.

    Rejected rooms never appear in `new_rooms` even when discovery
    re-reports them. If they were configured, they are also removed
    from managed_rooms so their HA entities (switches, numbers,
    sensors) get torn down by the platform-level room-update callbacks.

    ``map_id`` is the map the ghost was seen on (A4-SETUP-6). Both the
    rejection and the managed-room strip are confined to it, because ids are
    reissued per map: id 3 upstairs is not the id 3 the user just rejected
    downstairs. Omitting it means "the only map" and is REFUSED on a vacuum with
    more than one — see ``_resolve_rejection_map``.

    Returns:
        {
            "rejected": [room_id, ...],
            "removed_from_managed": [room_id, ...],
            "affected_map_ids": [map_id, ...],
            "map_id": map_id or None,
        }
    or a ``{"status": "error", "reason": "map_ambiguous", ...}`` refusal, which
    writes nothing.

    Callers should call ``manager._notify_rooms_updated`` for each
    map ID in ``affected_map_ids`` so the entity-platform cleanup
    fires for every map a rejected room used to live on.
    """
    map_id, refusal = _resolve_rejection_map(manager, vacuum_entity_id, map_id)
    if refusal is not None:
        return {
            **refusal,
            "rejected": [],
            "removed_from_managed": [],
            "affected_map_ids": [],
            "map_id": None,
        }

    record = _get_progress_record(manager, vacuum_entity_id)

    if map_id is None:
        bucket_list: list[int] = list(record.get("rejected_rooms") or [])
    else:
        by_map = record.setdefault("rejected_rooms_by_map", {})
        bucket_list = list(by_map.get(str(map_id)) or [])
    rejected_set = set(bucket_list)

    added: list[int] = []
    for rid in room_ids:
        try:
            rid_int = int(rid)
        except (TypeError, ValueError):
            continue
        if rid_int not in rejected_set:
            bucket_list.append(rid_int)
            rejected_set.add(rid_int)
            added.append(rid_int)

    if map_id is None:
        record["rejected_rooms"] = bucket_list
    else:
        record["rejected_rooms_by_map"][str(map_id)] = bucket_list

    # Strip rejected rooms from managed_rooms. Track which maps were
    # touched so the service handler can fire room-update callbacks
    # for those maps — entity-platform cleanup keys off (vacuum, map).
    removed_from_managed: list[int] = []
    affected_map_ids: list[str] = []
    vac_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {}) or {}
    for candidate_map_id, bucket in vac_maps.items():
        if not isinstance(bucket, dict):
            continue
        if map_id is not None and str(candidate_map_id) != str(map_id):
            continue
        rooms = bucket.get("rooms") or {}
        map_touched = False
        for key in list(rooms.keys()):
            room = rooms.get(key)
            if not isinstance(room, dict):
                continue
            try:
                rid_int = int(room.get("room_id", key))
            except (TypeError, ValueError):
                continue
            if rid_int in rejected_set:
                rooms.pop(key, None)
                removed_from_managed.append(rid_int)
                map_touched = True
        if map_touched:
            affected_map_ids.append(str(candidate_map_id))

    # Drop any stale history entries for the rejected rooms.
    history = record["room_drift_history"]
    for rid_int in added:
        history.pop(str(rid_int), None)

    return {
        "rejected": added,
        "removed_from_managed": removed_from_managed,
        "affected_map_ids": affected_map_ids,
        "map_id": str(map_id) if map_id is not None else None,
    }


def unreject_rooms(
    manager: Any,
    vacuum_entity_id: str,
    room_ids: list[int],
    map_id: str | None = None,
) -> dict[str, Any]:
    """Undo a rejection so the room can be discovered and configured again.

    A4-SETUP-6's second half. Rejection was one-way: a room the user rejected
    stopped appearing in ``new_rooms``, which is exactly what makes a WRONG
    rejection unrecoverable — the room never resurfaces to be un-rejected from,
    and the only remaining route was editing ``.storage`` by hand, which this
    project treats as never-do.

    Clears BOTH backings for the ids given: the per-map list for ``map_id``, and
    the legacy flat list. The flat list is cleared because it is the entry that
    cannot say which map it meant — so it is the one blocking a real room on a
    second floor, and clearing it is the documented way out.

    ``map_id`` is subject to the SAME refusal as ``reject_rooms``: omitting it
    means "the only map", and on a multi-map vacuum it refuses instead of
    guessing. Un-rejecting is not the safe direction of an ambiguous call — the
    flat entry it would clear is precisely the vacuum-global one, so an
    unqualified un-reject would un-hide an id on every floor at once. That is
    A4-SETUP-6's own mistake pointed the other way.

    The room does not reappear instantly: it resurfaces on the next discovery
    pass that sees it, through the normal ``new_rooms`` confirmation cadence.

    Returns ``{"unrejected": [...], "still_rejected_on": {map_id: [...]}}`` —
    the second key names any other map that still rejects one of these ids, so
    the caller can say so rather than implying a clean sweep.
    """
    map_id, refusal = _resolve_rejection_map(manager, vacuum_entity_id, map_id)
    if refusal is not None:
        return {**refusal, "unrejected": [], "still_rejected_on": {}, "map_id": None}

    record = _get_progress_record(manager, vacuum_entity_id)

    wanted: set[int] = set()
    for rid in room_ids:
        try:
            wanted.add(int(rid))
        except (TypeError, ValueError):
            continue

    removed: set[int] = set()

    flat = [r for r in (record.get("rejected_rooms") or [])]
    kept_flat: list[int] = []
    for raw in flat:
        try:
            rid_int = int(raw)
        except (TypeError, ValueError):
            continue          # a non-numeric legacy entry is dropped, not carried
        if rid_int in wanted:
            removed.add(rid_int)
        else:
            kept_flat.append(rid_int)
    record["rejected_rooms"] = kept_flat

    by_map = record.setdefault("rejected_rooms_by_map", {})
    if isinstance(by_map, dict) and map_id is not None:
        key = str(map_id)
        kept: list[int] = []
        for raw in by_map.get(key) or []:
            try:
                rid_int = int(raw)
            except (TypeError, ValueError):
                continue
            if rid_int in wanted:
                removed.add(rid_int)
            else:
                kept.append(rid_int)
        if kept:
            by_map[key] = kept
        else:
            by_map.pop(key, None)

    still_rejected_on: dict[str, list[int]] = {}
    if isinstance(by_map, dict):
        for other_map, per_map in by_map.items():
            overlap = sorted(
                rid for rid in wanted
                if rid in {int(r) for r in (per_map or []) if str(r).lstrip("-").isdigit()}
            )
            if overlap:
                still_rejected_on[str(other_map)] = overlap

    return {
        "unrejected": sorted(removed),
        "still_rejected_on": still_rejected_on,
        "map_id": str(map_id) if map_id is not None else None,
    }


def run_discovery_pass(
    hass: HomeAssistant,
    manager: Any,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Run one discovery pass and update drift history.

    Reads the adapter's declared room-list source (via
    ``rooms.room_discovery.discover_rooms_for_vacuum``) and updates the
    per-vacuum drift history counters so subsequent
    ``compute_room_drift`` reads reflect what the vacuum currently sees.

    Cheap to call — pure state read + counter update. Safe to invoke on
    any trigger (state change, periodic timer, manual rescan) without
    debouncing.

    Returns:
        {
            "vacuum_entity_id": str,
            "discovered_room_ids": list[int],
            "updated_at": str (ISO),
        }
    """
    from ..rooms.room_discovery import discover_rooms_for_vacuum

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=vacuum_entity_id)
    discovered_ids: set[int] = set()
    for room in rooms:
        if not isinstance(room, dict):
            continue
        try:
            discovered_ids.add(int(room.get("room_id")))
        except (TypeError, ValueError):
            continue

    # The room-list source describes whichever map is LOADED, so this pass's ids
    # belong to the active map — that is the map whose rejections apply
    # (A4-SETUP-6). Resolution is best-effort: an adapter that cannot name its
    # active map yields None, which unions every map's rejections, i.e. exactly
    # the pre-A4-SETUP-6 behaviour rather than a silently unfiltered pass.
    active_map_id: str | None = None
    resolver = getattr(manager, "resolve_active_map_id", None)
    if callable(resolver):
        try:
            resolved = resolver(vacuum_entity_id)
        except Exception:  # noqa: BLE001 - discovery must survive a bad adapter read
            resolved = None
        active_map_id = str(resolved) if resolved else None

    update_drift_history(
        manager, vacuum_entity_id, discovered_ids, map_id=active_map_id
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "discovered_room_ids": sorted(discovered_ids),
        "map_id": active_map_id,
        "updated_at": _iso_now(),
    }


def force_remove_room(
    manager: Any, vacuum_entity_id: str, room_id: int
) -> dict[str, Any]:
    """Bypass the missing-pass counter and immediately mark a room removed.

    Used by the "I know this room is gone" manual action in the setup
    tab. Sets missing_passes to the configured threshold so the next
    drift computation reports it as removed without waiting for natural
    discovery passes.

    Note: This does NOT delete the room from managed_rooms — that is
    a separate, more destructive action. The user can choose to keep
    historical learning data for the room even after marking it removed.
    """
    record = _get_progress_record(manager, vacuum_entity_id)
    cadence = get_discovery_cadence(vacuum_entity_id)
    n_remove = cadence["removal_confirmation_passes"]
    history = record["room_drift_history"]
    key = str(int(room_id))
    entry = history.setdefault(
        key,
        {
            "missing_passes": 0,
            "seen_passes": 0,
            "last_seen_at": None,
            "first_missed_at": None,
            "first_seen_at": None,
        },
    )
    entry["missing_passes"] = max(int(entry.get("missing_passes", 0)), n_remove)
    if entry.get("first_missed_at") is None:
        entry["first_missed_at"] = _iso_now()
    entry["seen_passes"] = 0
    return {
        "room_id": int(room_id),
        "missing_passes": entry["missing_passes"],
        "threshold": n_remove,
    }
