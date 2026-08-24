"""Evaluates protection level for destructive setup operations.

The backend is the single source of truth for protection level; the panel
only displays it. Levels: ``normal`` (one-click), ``elevated`` (confirm
click), ``high`` (typed confirmation — must match the map display name).
"""

from __future__ import annotations

from typing import Any


def evaluate_map_protection(
    manager,
    *,
    vacuum_entity_id: str,
    map_id: str,
) -> dict[str, Any]:
    """Return protection metadata for deleting one imported map.

    Result shape:
    {
        "protection_level":           "normal" | "elevated" | "high",
        "reasons": [
            {"code": str, "message": str}   # has_learning_data also carries
                                            # "params": {"count": int}
        ],
        "requires_typed_confirmation": bool,   # True only for a NAMED high map
        "requires_confirmation":       bool,   # one-click confirm (elevated, or unnamed high)
        "typed_confirmation_value":   str | None,   # stored map name; None when unnamed
    }
    """
    reasons: list[dict[str, str]] = []
    map_id_str = str(map_id)

    vacuum_maps = manager.data.get("maps", {}).get(vacuum_entity_id, {})
    bucket      = vacuum_maps.get(map_id_str, {})
    # DR-SETUP-4: a malformed bucket/room record must not raise AttributeError out
    # of a function both the delete gate and get_setup_status's per-map summaries
    # call -- one bad record would otherwise take out the whole Setup tab.
    #
    # ⚠ THE PARITY WITH drift.py IS PARTIAL, AND THIS COMMENT CLAIMED IT WAS WHOLE
    # UNTIL 2026-08-24 (D20). It said the degradation matches "drift.py's
    # isinstance(bucket, dict) guards", but drift.py's idiom has TWO parts and only
    # the first was copied. drift.py writes
    # `if not isinstance(bucket, dict): ...` AND THEN `(bucket.get("rooms") or {})`;
    # the line below is `bucket.get("rooms", {})`, whose default only fires on an
    # ABSENT key. A bucket carrying `"rooms": None` (or a list) therefore reaches
    # `rooms.values()` further down and raises the exact AttributeError this guard
    # was added to prevent. Closing that is a CODE change and is not made here.
    #
    # ⚠ SECOND HALF, ALSO STILL OPEN: the `imported_map_ids` comprehension below
    # ("isinstance(b, dict) and b.get('rooms')") is a hand copy of the predicate
    # that has since been centralised as `maps/map_manager.map_ids_with_rooms`
    # (MAP-GHOST-1). drift.py migrated -- its `_known_map_ids` now delegates to that
    # helper. This copy did not, so it is the one that will drift.
    #
    # ⚠ NO LIVE CALLER REACHES THIS TODAY, and it stays anyway (ledger C34, filed as
    # dead twice). Both callers pre-filter: status.py:127 rejects the non-dict bucket
    # by isinstance BEFORE calling in (and landed 2.5 months BEFORE this guard), and
    # delete.py:68 raises upstream of the call. Three of the four guards that commit
    # added are live; this is the fourth.
    #
    # It is a BOUNDARY NORMALIZER, not a redundant check. Its value is for the NEXT
    # caller — the one that has not pre-filtered — and the cost of being wrong is
    # asymmetric: a single malformed bucket in a user .storage (hand-edit, truncated
    # write, pre-1.0 schema) raises out of a function get_setup_status calls once per
    # map per managed vacuum, so ONE bad record takes out the entire Setup tab. Two
    # lines against that is not a trade worth optimising.
    if not isinstance(bucket, dict):
        bucket = {}
    rooms       = bucket.get("rooms", {})
    # Raw stored name, or None when unnamed. None is load-bearing: a synthesized
    # "Map N" token would be locale-dependent and break the typed match, so an
    # unnamed map drops to a one-click confirm. The card renders setup.map_n.
    stored_name = bucket.get("metadata", {}).get("display_name") or None

    imported_map_ids = [
        mid for mid, b in vacuum_maps.items()
        if isinstance(b, dict) and b.get("rooms")
    ]
    if len(imported_map_ids) <= 1:
        reasons.append({
            "code":    "only_map",
            "message": "This is the only imported map for this vacuum.",
        })

    active_job = (
        manager.data.get("active_jobs", {})
        .get(vacuum_entity_id, {})
        .get(map_id_str, {})
    )
    if isinstance(active_job, dict) and active_job.get("has_observed_active_lifecycle"):
        reasons.append({
            "code":    "has_active_job",
            "message": "A cleaning job is running or was recently active on this map.",
        })

    map_history = (
        manager.data.get("room_history", {})
        .get(vacuum_entity_id, {})
        .get(map_id_str, {})
    )
    if map_history:
        reasons.append({
            "code":    "has_learning_data",
            # params ride alongside so the card can localize the sentence with
            # the count (setup.protection_reason.has_learning_data); message
            # stays the non-card / older-card fallback.
            "params":  {"count": len(map_history)},
            "message": f"This map has cleaning history for {len(map_history)} room(s).",
        })

    has_rules = any(
        isinstance(room, dict) and room.get("rules") for room in rooms.values()
    )
    if has_rules:
        reasons.append({
            "code":    "has_rules",
            "message": "One or more rooms have automation rules configured.",
        })

    has_access_graph = any(
        isinstance(room, dict) and room.get("grants_access_to") for room in rooms.values()
    )
    if has_access_graph:
        reasons.append({
            "code":    "has_access_graph",
            "message": "One or more rooms are part of an access graph.",
        })

    elevated_codes = {r["code"] for r in reasons}
    if "has_active_job" in elevated_codes:
        level = "high"
    elif len(reasons) >= 2:
        level = "high"
    elif reasons:
        level = "elevated"
    else:
        level = "normal"

    # Typed confirmation only when we have a real, locale-invariant name to match
    # against. An unnamed map keeps high-level friction via a one-click confirm
    # (requires_confirmation) but cannot demand a typed token it has no name for.
    requires_typed = level == "high" and bool(stored_name)
    requires_confirmation = level != "normal"

    return {
        "protection_level":            level,
        "reasons":                     reasons,
        "requires_typed_confirmation": requires_typed,
        "requires_confirmation":       requires_confirmation,
        "typed_confirmation_value":    stored_name if requires_typed else None,
    }
