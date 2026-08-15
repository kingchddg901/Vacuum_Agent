"""Entity helper utilities for Vacuum Agent."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


#: Entity-state values that carry NO usable information.
#:
#: Hand-copied variants of this set existed at six sites and had drifted into three
#: shapes. The differences were not arbitrary — they tracked how "absent" reaches the
#: state machine on different transports:
#:   "None"  Python's str(None) leaking from a backend that stringifies
#:   "null"  a JSON/JS null leaking from the map/websocket side
#: so each site caught the leak form its own producer emitted and missed the others.
#:
#: Covering BOTH makes every caller strictly more robust rather than merely
#: deduplicated: no legitimate entity state is the literal string "None" or "null".
BLANK_STATE_VALUES: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "null"}
)


def is_blank_state(value: Any) -> bool:
    """Return whether an entity state carries no usable information.

    THE question — "did we actually get a value?" — rather than the raw set, so a caller
    cannot drift by re-listing members. Case- and whitespace-insensitive, and a real
    ``None`` counts as blank without the caller having to stringify first.

    NOT for deciding whether a state is an ERROR: that is brand vocabulary
    (``NOT_ERROR_SENTINELS``, declared per adapter, where Roborock deliberately excludes
    "normal"). Different question, correctly different answer — see the error tracker.
    """
    if value is None:
        return True
    return str(value).strip().lower() in BLANK_STATE_VALUES


def _friendly_vacuum_name(vacuum_entity_id: str) -> str:
    """Return a title-cased display name derived from the vacuum entity_id's object_id."""
    object_id = vacuum_entity_id.split(".", 1)[1]
    return object_id.replace("_", " ").strip().title()


def build_vacuum_device_info(vacuum_entity_id: str) -> DeviceInfo:
    """Return a DeviceInfo that groups all entities for one vacuum under a service device.

    All entity classes should attach this so HA can display per-vacuum device pages
    and satisfy the ``has-entity-name`` quality-scale rule.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, vacuum_entity_id.replace(".", "_"))},
        name=_friendly_vacuum_name(vacuum_entity_id),
        entry_type=DeviceEntryType.SERVICE,
    )


def make_room_unique_id(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_id: int,
    suffix: str,
) -> str:
    """Build a stable unique ID for a room entity.

    NON-INJECTIVE JOIN, by decision (RP-009 / INF-5 document_only): "_" appears
    inside vacuum keys, map ids and suffixes, so the concatenation cannot be
    parsed back into its parts — ``vacuum_alfred_2_...`` is both (vacuum.alfred,
    map "2") and (vacuum.alfred_2, any map). No parser exists and none may be
    written; ownership questions are answered by ``entity_belongs_to`` (live
    attributes) or ``unique_ids_for_map`` (forward reconstruction), never by
    string dissection.
    """
    vacuum_key = vacuum_entity_id.replace(".", "_")
    return f"{vacuum_key}_{map_id}_{room_id}_{suffix}"


#: Every suffix a ROOM entity is built with — one per platform room class.
#: setup/delete's closed-set sweep reconstructs ids from these; a NEW room
#: entity class must add its suffix here (the parity test counts the classes).
ROOM_ENTITY_SUFFIXES: tuple[str, ...] = (
    "enabled",           # switch.EufyVacuumRoomEnabledSwitch
    "order",             # number.EufyVacuumRoomOrderNumber
    "cleaning_history",  # sensor.room_history.EufyVacuumRoomCleaningHistorySensor
    "rule_status",       # sensor.room_rule_status.EufyVacuumRoomRuleStatusSensor
)


def unique_ids_for_map(
    *,
    vacuum_entity_id: str,
    map_id: str,
    room_ids: "list[int] | list[str]",
    suffixes: "tuple[str, ...] | list[str]" = ROOM_ENTITY_SUFFIXES,
) -> set[str]:
    """FORWARD-reconstruct the exact unique_id set for one vacuum/map's rooms.

    RP-009 (RF-04): the builder and the matcher live side by side so ownership
    is answered by re-BUILDING ids from stored facts, never by prefix-scanning
    the registry. Five prefix scans existed; one of them (setup/delete) was
    PROVEN to registry-delete every entity of a sibling vacuum whose entity_id
    was the scanned prefix plus a suffix (vacuum.alfred deleting map "2" swept
    vacuum.alfred_2's entities — DR-SETUP-1).
    """
    out: set[str] = set()
    for room_id in room_ids:
        try:
            rid = int(room_id)
        except (TypeError, ValueError):
            continue
        for suffix in suffixes:
            out.add(make_room_unique_id(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id),
                room_id=rid, suffix=suffix,
            ))
    return out


def active_job_unique_id(*, vacuum_entity_id: str, map_id: str) -> str:
    """The one formula for a per-map active-job sensor's unique_id.

    Lives beside the matcher below for the same reason as make_room_unique_id:
    ownership is answered by RE-BUILDING ids from stored facts, never by taking
    a registry id apart.
    """
    return f"{vacuum_entity_id.replace('.', '_')}_active_job_{map_id}"


def orphaned_active_job_unique_ids(
    *,
    known_unique_ids: "Iterable[str]",
    managed_vacuum_ids: "Iterable[str]",
    live_pairs: "Iterable[tuple[str, str]]",
) -> set[str]:
    """Active-job unique_ids whose map no longer exists.

    ``live_pairs`` is the (vacuum, map) set actually built this run — the FORWARD
    reconstruction. Anything carrying a managed vacuum's active-job shape and
    absent from it is stale by construction.

    WHY THIS IS NOT A PREFIX SCAN, despite starting from one. RP-009/RF-04
    records the cost of the naive version: a prefix scan in setup/delete was
    PROVEN to registry-delete every entity of a SIBLING vacuum whose entity_id
    was the scanned prefix plus a suffix -- ``vacuum.alfred`` deleting map "2"
    swept ``vacuum.alfred_2``'s entities (DR-SETUP-1). Two things keep that from
    recurring here:

    1. the deletion set is the COMPLEMENT of a forward-built set, so a live
       entity can only be selected if this run failed to build it at all; and
    2. the remainder after the prefix must not itself contain ``active_job_``,
       which is the only way one managed vacuum's prefix can swallow another's
       id (a vacuum literally named ``<x>_active_job``). Note the missing leading
       underscore: the prefix has already consumed it, so ``vacuum.alfred``
       matching ``vacuum_alfred_active_job_active_job_5`` leaves the remainder
       ``active_job_5``. Testing for ``_active_job_`` there matches nothing and
       the guard silently does not fire -- caught by OAJ-3, not by review.

    Pure and side-effect free so the adversarial cases are testable without a
    registry -- see tests/unit/test_orphan_active_job_sweep.py.
    """
    live = {
        active_job_unique_id(vacuum_entity_id=v, map_id=str(m))
        for v, m in live_pairs
    }
    known = list(known_unique_ids)
    orphans: set[str] = set()
    for vacuum_entity_id in managed_vacuum_ids:
        prefix = f"{vacuum_entity_id.replace('.', '_')}_active_job_"
        for unique_id in known:
            if not unique_id.startswith(prefix):
                continue
            if "active_job_" in unique_id[len(prefix):]:
                continue
            if unique_id in live:
                continue
            orphans.add(unique_id)
    return orphans


def entity_belongs_to(entity: Any, *, vacuum_entity_id: str, map_id: str) -> bool:
    """Whether a live room entity belongs to one vacuum/map — by ATTRIBUTES.

    Consumes the read-only ``vacuum_entity_id`` / ``map_id`` properties the
    shared room base entity exposes (RP-009 / REVIEW D2) — never the unique_id
    string, which is a non-injective join (see make_room_unique_id). An entity
    that does not carry both properties (e.g. a maintenance number sharing a
    platform entity_map — EP-2's victim) is NOT a room entity and never
    "belongs", so a sweep can never classify it stale.
    """
    ent_vac = getattr(entity, "vacuum_entity_id", None)
    ent_map = getattr(entity, "map_id", None)
    if not isinstance(ent_vac, str) or ent_map is None:
        return False
    return ent_vac == vacuum_entity_id and str(ent_map) == str(map_id)


def sort_room_items(
    rooms: dict[str, dict[str, Any]],
    *,
    configured_only: bool = True,
) -> list[tuple[str, dict[str, Any]]]:
    """Return rooms sorted by order then name.

    Filters out unconfigured rooms by default — rooms whose
    ``is_configured`` flag is not True. This is the entity-creation
    gate: discovered-but-not-yet-approved rooms (newly surfaced by the
    drift detector, awaiting user review on the setup tab) do not
    materialize as HA entities until the user explicitly configures
    them via setup_save_rooms.

    ``configured_only=False`` opts out and returns every room
    regardless of state — useful for setup flows and diagnostics that
    need to list discovered rooms pre-approval. No current caller
    needs this; it's available for future setup-side iteration.
    """
    items = list(rooms.items())
    if configured_only:
        items = [
            item for item in items
            if isinstance(item[1], dict) and item[1].get("is_configured")
        ]
    items.sort(
        key=lambda item: (
            int(item[1].get("order", 999)),
            str(item[1].get("name", "")),
        )
    )
    return items


def get_floor_type_label(floor_type: str) -> str:
    """Return user-friendly floor type label.

    ``floor_type`` encodes carpet pile in the value itself (e.g.
    ``"carpet_low_pile"``) — there is no separate carpet_type field.
    """
    mapping = {
        "hardwood": "Hardwood / Engineered Wood",
        "laminate": "Laminate / Vinyl",
        "tile": "Tile / Stone",
        "marble": "Marble / Natural Stone",
        "granite": "Granite / Natural Stone",
        "concrete": "Concrete",
        "carpet_low_pile": "Carpet — Low-Pile / Thin",
        "carpet_high_pile": "Carpet — Medium/High-Pile/Shag",
        # Legacy value — kept for display of old stored data
        "carpet": "Carpet",
    }
    return mapping.get(str(floor_type), str(floor_type).replace("_", " ").title())