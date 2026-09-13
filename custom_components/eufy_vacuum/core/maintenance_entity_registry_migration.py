# -*- coding: utf-8 -*-
"""Carry the ENTITY REGISTRY across a maintenance component-key rename.

THE SIBLING MODULE CARRIES THE INTERVAL; THIS ONE CARRIES THE ENTITY. They share
``COMPONENT_RENAMES`` and nothing else, because they write to two different stores and only one
of those stores is ours.

WHY STORAGE ALONE WAS NOT ENOUGH. A component id is half of an entity's ``unique_id``
(``vacuum_alfred_swivel_wheel_maintenance_interval``). Rename the component and the platforms
mint entities under the NEW id while Home Assistant's registry still holds a row under the old
one. That row does not go away — it becomes ``restored`` and shows in the UI as permanently
``unavailable``. Three consequences, none of which self-heal:

* every automation, script, dashboard card and template bound to the old entity_id keeps
  resolving it and silently reads a corpse;
* long-term statistics are keyed by entity_id, so the series STOPS rather than continues; and
* the dead row still OWNS its entity_id, so when the new entity asks for the same slug HA
  appends ``_2``. Eufy keeps its own display word via ``label_key``, so the two friendly names
  are identical and the collision is guaranteed rather than incidental.

MEASURED, NOT HYPOTHESISED. A real box carried FIFTEEN orphan rows and three ``_2`` entity_ids
after the 2026-09-12 canonicalisation, and its three interval numbers had frozen at their
add-time values while the sibling sensors moved.

⏱ WHEN IT RUNS IS LOAD-BEARING: BEFORE ``async_forward_entry_setups``. The platforms are what
mint the canonical rows. Run first and the legacy row is still the only holder of that
unique_id, so the rename is an in-place update that KEEPS the entity_id, the history and every
reference to it — a normal upgrader sees nothing at all, which is the point. Run after, and
every component collides, because the canonical row already exists. That is not a hypothetical
ordering bug: it is precisely how the author's box reached fifteen-for-fifteen collisions.

WHY ITS OWN MIGRATION KEY. ``maintenance_component_renames_*`` is a one-shot latch that is
already ``True`` on every box that has run this version, so a pass added under it could never
run there — the author's own box included, which would make it live-unverifiable.

TWO LEGACY KEYS CAN NAME ONE DESTINATION. Eufy's front wheel was ``swivel_wheel``, then
``caster_wheel``, now ``omnidirectional_wheel``, so a box that lived through both carries two
dead rows pointing at one canonical id — and only ONE of them can become it. The winner is
``COMPONENT_RENAMES`` order, which is newest-rename-first; the loser is pruned. This mirrors
the sibling module's documented tie-break rather than inventing a second convention. Unlike the
sibling we cannot prefer "most recently reset", because a registry row carries no such fact.

PRUNING IS A RULING, NOT A DEFAULT (Chris, 2026-09-14). A collided legacy row cannot be renamed
— the id it wants is taken — so it can only be kept as permanent clutter or removed. He ruled
prune. Note what that costs and does not cost: the pruned row's own history goes, but it is the
row nothing has written to since the rename, and the canonical row that survives is the one the
UI has been showing all along.
"""

from __future__ import annotations

import logging
from typing import Any

from ..const import DOMAIN
from .maintenance_component_rename_migration import COMPONENT_RENAMES, RETIRED_COMPONENTS

_LOGGER = logging.getLogger(__name__)

#: Separate from the interval migration's key ON PURPOSE — see the module docstring.
REGISTRY_MIGRATION_KEY = "maintenance_entity_registry_renames_v1"

#: ``unique_id suffix -> the platform domain that owns it``. These three are the whole
#: maintenance entity surface; each component gets exactly one of each when it has a source.
#: Derived from the three ``_attr_unique_id`` expressions, which must stay in step:
#: ``button.py``, ``number.py`` and ``sensor/maintenance.py``.
PLATFORM_SUFFIXES: dict[str, str] = {
    "maintenance_reset": "button",
    "maintenance_interval": "number",
    "maintenance_remaining": "sensor",
}


def _unique_id(vacuum_entity_id: str, component: str, suffix: str) -> str:
    """The unique_id the platforms build. ONE definition, three call sites over there."""
    return f"{vacuum_entity_id.replace('.', '_')}_{component}_{suffix}"


def _known_vacuums(data: dict[str, Any]) -> list[str]:
    """Every vacuum this install has ever stored maintenance or a record for."""
    found: set[str] = set()
    for section in ("maintenance", "vacuums"):
        block = data.get(section)
        if isinstance(block, dict):
            found.update(k for k in block if isinstance(k, str) and "." in k)
    return sorted(found)


def plan_entity_registry_renames(hass, *, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the registry moves this install needs. Reads only; writes nothing.

    Each move carries an ``action``: ``rename`` when the canonical unique_id is free, ``prune``
    when something already holds it. The applier re-checks before acting — see there for why
    that belt-and-braces matters.
    """
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    moves: list[dict[str, Any]] = []
    # Destination -> already claimed by an earlier move in THIS plan. Two legacy ids can name
    # one canonical id, and only the first may take it.
    claimed: set[tuple[str, str]] = set()

    for vacuum_entity_id in _known_vacuums(data):
        for legacy, canonical in COMPONENT_RENAMES.items():
            for suffix, domain in PLATFORM_SUFFIXES.items():
                old_uid = _unique_id(vacuum_entity_id, legacy, suffix)
                entity_id = registry.async_get_entity_id(domain, DOMAIN, old_uid)
                if entity_id is None:
                    continue
                new_uid = _unique_id(vacuum_entity_id, canonical, suffix)
                key = (domain, new_uid)
                taken_by = registry.async_get_entity_id(domain, DOMAIN, new_uid)
                blocked = taken_by is not None or key in claimed
                if not blocked:
                    claimed.add(key)
                moves.append(
                    {
                        "vacuum_entity_id": vacuum_entity_id,
                        "from": legacy,
                        "to": canonical,
                        "domain": domain,
                        "entity_id": entity_id,
                        "old_unique_id": old_uid,
                        "new_unique_id": new_uid,
                        "action": "prune" if blocked else "rename",
                        "reason": "destination_taken" if blocked else "renamed",
                        "blocked_by": taken_by,
                    }
                )

        # RETIRED OUTRIGHT — absorbed or ruled out of scope, so there is nowhere to rename to.
        # Only `cleaning_brush` and `strainer` ever minted entities (a wash-dock Roborock
        # publishes their counters); the rest are listed defensively. Leaving these is a
        # permanently `unavailable` row per part, forever, for something the integration no
        # longer declares — Chris ruled prune.
        for retired in sorted(RETIRED_COMPONENTS):
            for suffix, domain in PLATFORM_SUFFIXES.items():
                old_uid = _unique_id(vacuum_entity_id, retired, suffix)
                entity_id = registry.async_get_entity_id(domain, DOMAIN, old_uid)
                if entity_id is None:
                    continue
                moves.append(
                    {
                        "vacuum_entity_id": vacuum_entity_id,
                        "from": retired,
                        "to": None,
                        "domain": domain,
                        "entity_id": entity_id,
                        "old_unique_id": old_uid,
                        "new_unique_id": None,
                        "action": "prune",
                        "reason": "component_retired",
                        "blocked_by": None,
                    }
                )
    return moves


def migrate_maintenance_entity_registry(
    hass,
    *,
    data: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    """Rename the registry rows a component rename orphaned. Idempotent.

    Returns ``{"ran": bool, "renamed": [...], "pruned": [...]}``. The caller persists ``data``
    for the migration flag; the registry saves itself.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(REGISTRY_MIGRATION_KEY) and not force:
        return {"ran": False, "renamed": [], "pruned": [], "failed": []}

    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    moves = plan_entity_registry_renames(hass, data=data)
    renamed: list[dict[str, Any]] = []
    pruned: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    if moves:
        _LOGGER.info(
            "maintenance_entity_registry: %d registry row(s) to carry across a component rename",
            len(moves),
        )

    for move in moves:
        try:
            # RE-CHECKED AT APPLY TIME, not trusted from the plan. `async_update_entity` raises
            # ValueError when the unique_id is already in use, and a raise here would abort the
            # whole pass partway — leaving a box half-migrated, which is worse than either end
            # state. The plan already avoids this; this is the guard that makes it true.
            free = bool(move["new_unique_id"]) and registry.async_get_entity_id(
                move["domain"], DOMAIN, move["new_unique_id"]
            ) is None
            if move["action"] == "rename" and free:
                registry.async_update_entity(
                    move["entity_id"], new_unique_id=move["new_unique_id"]
                )
                renamed.append(move)
            else:
                registry.async_remove(move["entity_id"])
                pruned.append(move)
        except Exception:  # one bad row must not abort the rest
            # ⚠ THIS WAS `debug` AND THAT HID A REAL FAILURE. On the first live upgrade test
            # the pass planned nine renames, applied zero, and set its own completion flag —
            # and said NOTHING at any level a user or maintainer would ever see. The failure
            # was indistinguishable from "there was nothing to do", which is the worst possible
            # way for a one-shot migration to fail: the latch means it never tries again.
            # A migration that cannot do its job must say so loudly enough to be reported.
            failed.append(move)
            _LOGGER.warning(
                "maintenance_entity_registry: could not carry %s (%s -> %s); it will stay "
                "under its old id and show as unavailable",
                move["entity_id"],
                move["old_unique_id"],
                move["new_unique_id"],
                exc_info=True,
            )

    # ⚠ THE LATCH IS SET EVEN ON FAILURE, DELIBERATELY -- retrying every startup would hammer
    # a registry that is refusing us, and the honest state is "we tried once and could not".
    # That is only defensible because the failure is now LOUD; it was not, and a silent
    # never-ran was indistinguishable from a silent nothing-to-do.
    migrations[REGISTRY_MIGRATION_KEY] = True

    if failed:
        _LOGGER.error(
            "maintenance_entity_registry: %d of %d row(s) could not be carried. Those entities "
            "keep their old ids and will read `unavailable`; the new ones are created alongside "
            "them. This is reportable -- please open an issue with the warnings above.",
            len(failed), len(moves),
        )

    if renamed:
        _LOGGER.info(
            "maintenance_entity_registry: carried %d entit%s across a component rename, keeping "
            "their entity ids and history: %s",
            len(renamed),
            "y" if len(renamed) == 1 else "ies",
            ", ".join("%s (%s->%s)" % (m["entity_id"], m["from"], m["to"]) for m in renamed),
        )
    # SPLIT BY REASON, because they are two different facts a reader needs to tell apart: one
    # says "your replacement already exists", the other says "this part is no longer tracked at
    # all". A single combined count reads as the first and hides the second.
    superseded = [m for m in pruned if m["reason"] == "destination_taken"]
    retired = [m for m in pruned if m["reason"] == "component_retired"]
    if superseded:
        _LOGGER.info(
            "maintenance_entity_registry: removed %d orphaned entit%s whose replacement already "
            "existed: %s",
            len(superseded),
            "y" if len(superseded) == 1 else "ies",
            ", ".join("%s (%s->%s)" % (m["entity_id"], m["from"], m["to"]) for m in superseded),
        )
    if retired:
        _LOGGER.info(
            "maintenance_entity_registry: removed %d entit%s for component(s) this integration "
            "no longer tracks: %s",
            len(retired),
            "y" if len(retired) == 1 else "ies",
            ", ".join("%s (%s)" % (m["entity_id"], m["from"]) for m in retired),
        )
    return {"ran": True, "renamed": renamed, "pruned": pruned, "failed": failed}
