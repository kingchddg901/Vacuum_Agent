# -*- coding: utf-8 -*-
"""Carry a user's maintenance INTERVAL across a component-key rename.

WHY ONLY THE INTERVAL. Maintenance state is keyed by component id
(``data["maintenance"][vacuum][component]``) and holds three things. Two of them heal
themselves and one does not:

* ``reset_at`` / ``reset_at_usage_hours`` — SELF-HEALING. The next reset writes them again,
  and the card shows the component as never-reset until then, which is visible.
* ``interval_hours`` — A PREFERENCE, and nothing ever prompts the user to restore it. It
  silently reverts to ``default_interval_hours`` and they have no way to notice, because the
  old value only exists in ``.storage``, which they are correctly told never to open.

THIS IS NOT HYPOTHETICAL. The September 2026 canonicalisation (``rolling_brush`` ->
``main_brush``, ``swivel_wheel`` -> ``caster_wheel``) shipped without this, and the cost was
measured on a real box: a 65-hour swivel-wheel interval fell back to the 60-hour default and
the dead row is still sitting in storage next to the live one. Two reset timestamps were lost
with it and did not matter — they were re-reset within weeks.

RENAMES ONLY, NEVER ABSORPTIONS. A rename has exactly one destination. An absorption does not:
Roborock's ``cleaning_brush`` and ``strainer`` both fold into one panel, ``dustbin`` and
``water_filter`` both into ``filter``, and a general "carry the interval forward" would have to
pick between two source values or clobber a destination that already holds one. Those legitimately
drop to the default and are covered by the release note instead. So this table contains only
one-to-one moves, and the destination is skipped if it already has a value.

The legacy rows are LEFT IN PLACE rather than deleted. They are inert — nothing reads a component
id that no adapter declares — and deleting user data to tidy up is a worse trade than leaving a
few dead keys that cost nothing.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: ⚠ BUMP THIS WHENEVER YOU ADD A ROW BELOW. It is a one-shot latch, so a row added under a key
#: that is already ``True`` can NEVER run on a box that has already migrated — including the
#: author's, which makes the new row live-unverifiable exactly where it would be verified. That
#: is not hypothetical: `washboard` below was renamed on 2026-09-12 and no row was ever added,
#: so the miss sat undetected behind a latched `_v1`.
#: RE-RUNNING IS SAFE BY CONSTRUCTION: the planner skips any destination that already holds a
#: value, so a second pass over already-carried data plans nothing.
MIGRATION_KEY = "maintenance_component_renames_v2"

#: ``legacy component id -> canonical component id``. ONE-TO-ONE ONLY; see the module docstring
#: for why absorptions are excluded. Add a row here whenever a component id is renamed.
COMPONENT_RENAMES: dict[str, str] = {
    # Eufy, 2026-09-12 — the regime/key port. "Mopping Cloth" was wrong on five of its ten
    # mop-bearing models (S1, S1 Pro, E28 are rollers; C20, X10 Pro Omni are pads), so the
    # canonical id is the shape-neutral `mop`.
    "mop_cloth": "mop",
    # Eufy, 2026-09-12 — the shared emitter names this panel `omnidirectional_wheel`. Eufy keeps
    # "Swivel Wheel" as its DISPLAY word via label_key; only the storage key moves.
    "caster_wheel": "omnidirectional_wheel",
    # September 2026 canonicalisation, never migrated at the time. Carried here so the interval
    # that was lost then is recovered on the next load rather than staying lost.
    "rolling_brush": "main_brush",
    "swivel_wheel": "omnidirectional_wheel",
    "mopping_cloth": "mop",
    # Dreame, 2026-09-12 (f9cfed39) — the washboard panel became `cleaning_tray`. The rename
    # shipped WITHOUT a row here and the omission survived because the migration key was
    # already latched, so nothing would have run even if the row had been added. Found by the
    # 2026-09-14 audit; the key bump above is what lets it actually execute.
    "washboard": "cleaning_tray",
}

#: Component ids that were RETIRED OUTRIGHT — absorbed into another panel or ruled out of scope
#: — and so have no destination to be renamed to. They are NOT in ``COMPONENT_RENAMES`` on
#: purpose: an absorption has two sources and one destination, so there is no one-to-one move to
#: make and no honest way to choose whose interval survives.
#:
#: ONLY TWO OF THESE EVER MINTED AN ENTITY. Measured against the v2.1.0 tree: ``cleaning_brush``
#: and ``strainer`` each declared a ``sensor_suffix`` that the Roborock integration publishes on
#: a WASH-DOCK machine, so an owner of one has six real registry rows (2 x 3 platforms) that no
#: longer correspond to anything this integration declares. The other six declared no suffix, so
#: they never resolved a source and never became entities — they are listed anyway because
#: costing nothing is not the same as being absent, and a dev build that added a suffix later
#: would otherwise strand them silently.
#:
#: ⚠ THE ONE WAY THIS COULD DELETE A LIVE ENTITY is a component id reappearing in a brand's
#: catalog while still listed here. ``MER-10`` asserts the intersection is empty, so that
#: mistake is red before it can reach a user's registry.
#:
#: Chris ruled prune (2026-09-14): "cleaning_brush / strainer ... prune them". Leaving them
#: means a permanently `unavailable` row per part, forever, for a part the integration no longer
#: has an opinion about.
RETIRED_COMPONENTS: frozenset[str] = frozenset({
    # Roborock 14 -> 7, 2026-09-12. The two that shipped real entities:
    "cleaning_brush",
    "strainer",
    # ...and the six that never did (no sensor_suffix at v2.1.0):
    "dustbin",
    "water_filter",
    "main_wheel",
    "clean_water_tank",
    "dirty_water_tank",
    "dock_dust_bag",
    # The earlier spelling of dock_dust_bag, declared 2026-09-01 -> 09-12.
    "dust_bag",
})


def plan_component_rename_migration(*, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the interval moves this data needs. Reads only; writes nothing.

    ⚠ TWO LEGACY KEYS CAN NAME ONE DESTINATION, and the first version of this function got it
    wrong in a way only real data showed. A component renamed TWICE leaves a chain -- Eufy's
    front wheel was ``swivel_wheel``, then ``caster_wheel``, now ``omnidirectional_wheel`` --
    so a box that lived through both carries two dead rows pointing at the same canonical id.
    Planning each move independently against an empty destination let BOTH be planned, and
    applying them in order let the older one overwrite the newer: a real box had
    ``caster_wheel`` 30h (set an hour earlier) silently replaced by ``swivel_wheel`` 65h (dead
    since September).

    So candidates are grouped by destination and only one survives: the row the user touched
    MOST RECENTLY, by ``reset_at``. A row with no ``reset_at`` loses to one that has it, and a
    tie falls back to ``COMPONENT_RENAMES`` order, which is newest-rename-first.
    """
    changes: list[dict[str, Any]] = []
    maintenance = data.get("maintenance")
    if not isinstance(maintenance, dict):
        return changes

    order = list(COMPONENT_RENAMES)
    for vacuum_entity_id, components in maintenance.items():
        if not isinstance(components, dict):
            continue
        by_destination: dict[str, list[dict[str, Any]]] = {}
        for legacy, canonical in COMPONENT_RENAMES.items():
            old = components.get(legacy)
            if not isinstance(old, dict):
                continue
            interval = old.get("interval_hours")
            if interval is None:
                continue
            new = components.get(canonical)
            # THE DESTINATION WINS. A value already there is the user's more recent choice --
            # they set it AFTER the rename -- and a legacy row must never overwrite it.
            if isinstance(new, dict) and new.get("interval_hours") is not None:
                continue
            by_destination.setdefault(canonical, []).append({
                "vacuum_entity_id": vacuum_entity_id,
                "from": legacy,
                "to": canonical,
                "interval_hours": interval,
                # sort key: most recently reset first, then table order
                "_reset_at": str(old.get("reset_at") or ""),
                "_rank": order.index(legacy),
            })
        for canonical, candidates in by_destination.items():
            candidates.sort(key=lambda c: (c["_reset_at"] == "",
                                           [-ord(ch) for ch in c["_reset_at"]],
                                           c["_rank"]))
            winner = candidates[0]
            if len(candidates) > 1:
                _LOGGER.debug(
                    "maintenance_component_renames: %s has %d legacy rows for %s (%s); "
                    "taking %s, the most recently reset",
                    vacuum_entity_id, len(candidates), canonical,
                    ", ".join("%s=%gh" % (c["from"], c["interval_hours"]) for c in candidates),
                    winner["from"],
                )
            changes.append({k: v for k, v in winner.items() if not k.startswith("_")})
    return changes


def migrate_maintenance_component_renames(
    *,
    data: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    """Apply the interval carry-over once, recording that it ran. Idempotent.

    Returns ``{"ran": bool, "changes": [...]}``. The caller persists ``data``; nothing here
    writes to disk.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(MIGRATION_KEY) and not force:
        return {"ran": False, "changes": []}

    changes = plan_component_rename_migration(data=data)
    for change in changes:
        components = data["maintenance"][change["vacuum_entity_id"]]
        components.setdefault(change["to"], {})["interval_hours"] = change["interval_hours"]

    migrations[MIGRATION_KEY] = True
    if changes:
        _LOGGER.info(
            "maintenance_component_renames: carried %d custom maintenance interval(s) across a "
            "component rename: %s. Components that MERGED rather than moved keep the default "
            "interval — set it again on the merged card if you had customised one.",
            len(changes),
            ", ".join(
                "%s %s->%s (%gh)"
                % (c["vacuum_entity_id"], c["from"], c["to"], c["interval_hours"])
                for c in changes
            ),
        )
    return {"ran": True, "changes": changes}
