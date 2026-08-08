"""Is this vacuum_entity_id a REAL vacuum, or just a string somebody passed?

Per-vacuum state is created by ``setdefault(vacuum_entity_id, ...)`` in a dozen
places. None of them asked whether the id referred to anything, so any string that
reached a service became a permanent record — and two did on a live install:

  onboarding["vacuum.your_vacuum"]   the CARD'S OWN PLACEHOLDER (src/main.js),
                                     persisted because a status query created state
  setup_progress["vacuum.iv"]        a truncated entity id, with a full
                                     completed_steps / room_drift_history record

Neither corrupts anything, which is why they sat there unnoticed. The problem is that
the set only grows: every typo, every placeholder, every renamed entity leaves a record
nothing ever reaps, and "which vacuums does this install have?" stops having one answer.

The discriminator is deliberately NOT "already known to the manager" — that would make
adding a vacuum impossible, since a new one is by definition not yet known. It is
"names an entity Home Assistant actually has", which admits a genuinely new vacuum and
rejects a placeholder.
"""

from __future__ import annotations

from typing import Any


def is_real_vacuum(hass: Any, data: dict[str, Any], vacuum_entity_id: str) -> bool:
    """True when this id names a vacuum this install actually has.

    Accepts either of two proofs, because neither alone is sufficient:

    - **Home Assistant knows the entity.** Covers a brand-new vacuum being added,
      which has no stored record yet. Checked against the entity REGISTRY as well as
      the state machine, so a vacuum that is merely offline or not yet loaded still
      counts — its state can be absent while the entity is perfectly real.
    - **We already have a record for it.** Covers the reverse: an entity that has
      been removed or renamed in HA, whose stored history must stay reachable rather
      than becoming unaddressable the moment the entity goes away.

    Unknown ``hass`` (tests constructing a bare manager) falls back to the stored
    record alone rather than rejecting everything.
    """
    if not isinstance(vacuum_entity_id, str) or not vacuum_entity_id.startswith("vacuum."):
        return False

    if vacuum_entity_id in (data.get("vacuums") or {}):
        return True
    # A stored record anywhere is proof enough — the same aggregate
    # get_known_vacuum_ids uses, so this never disagrees with it.
    for bucket in ("maps", "active_jobs"):
        if vacuum_entity_id in (data.get(bucket) or {}):
            return True

    if hass is None:
        return False

    if getattr(hass, "states", None) is not None:
        if hass.states.get(vacuum_entity_id) is not None:
            return True

    try:  # registry check: an offline/disabled entity is still a real one
        from homeassistant.helpers import entity_registry as er

        if er.async_get(hass).async_get(vacuum_entity_id) is not None:
            return True
    except Exception:  # pragma: no cover - no registry in a bare test harness
        pass

    return False


def orphaned_vacuum_keys(hass: Any, data: dict[str, Any], bucket: str) -> list[str]:
    """Keys in ``data[bucket]`` that name no vacuum this install has.

    Used by the one-shot sweep. Deliberately a separate, pure function so what would
    be deleted can be ENUMERATED and reviewed before anything is deleted — a guard
    that newly activates over existing data has to be measured against that data
    first, not trusted because it passes its own tests.
    """
    node = data.get(bucket)
    if not isinstance(node, dict):
        return []
    return sorted(
        key for key in node
        if isinstance(key, str)
        and key.startswith("vacuum.")
        and not is_real_vacuum(hass, data, key)
    )


#: One-shot sweep flag, stored alongside the vocabulary repair's.
SWEEP_KEY = "orphaned_vacuum_keys_v1"

#: Buckets that are keyed by vacuum_entity_id. Deliberately explicit rather than
#: "any dict whose keys look like entity ids": a bucket added later that happens to
#: use entity-id-shaped keys for something else must not be swept by accident.
VACUUM_KEYED_BUCKETS = (
    "_pending_run_steps", "active_jobs", "capabilities", "discovery", "dock_events",
    "error_tracker", "learning_pending_runs", "maintenance", "maps", "onboarding",
    "payloads", "queue", "room_history", "room_rule_status", "run_profiles",
    "setup_progress", "vacuums",
)


def plan_orphan_sweep(hass: Any, data: dict[str, Any]) -> list[tuple[str, str]]:
    """(bucket, key) for every record naming a vacuum this install does not have.

    Pure. The sweep DELETES USER DATA, so what it would remove has to be reviewable
    before it removes anything — passing its own tests says nothing about what is
    already on somebody's disk.
    """
    return [
        (bucket, key)
        for bucket in VACUUM_KEYED_BUCKETS
        for key in orphaned_vacuum_keys(hass, data, bucket)
    ]


def sweep_orphaned_vacuums(
    hass: Any, data: dict[str, Any], *, force: bool = False
) -> dict[str, Any]:
    """Remove per-vacuum records for vacuums this install does not have. Runs once.

    Two got onto a live install: the card's own placeholder ``vacuum.your_vacuum``,
    persisted because a status QUERY created the record it was asking about, and
    ``vacuum.iv``, a truncated entity id carrying a full setup record. Neither broke
    anything, which is why they sat there — the problem is that the set only ever
    grew, and "which vacuums does this install have?" stopped having one answer.

    The guards in ``drift._get_progress_record`` and
    ``OnboardingManager._get_map_onboarding`` stop new ones appearing; this clears
    what is already there. Caller persists ``data``.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(SWEEP_KEY) and not force:
        return {"ran": False, "removed": []}

    planned = plan_orphan_sweep(hass, data)
    for bucket, key in planned:
        node = data.get(bucket)
        if isinstance(node, dict):
            node.pop(key, None)

    migrations[SWEEP_KEY] = True
    return {"ran": True, "removed": planned}
