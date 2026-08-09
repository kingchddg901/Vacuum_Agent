"""One-shot repair: lift a stored pause timeout of 0 to the new default.

WHAT WAS WRONG. ``pause_timeout_minutes_default`` fell back to 0 — the timeout
OFF — and no adapter declared otherwise, so every vacuum on every install shipped
with no pause safety net. Worse, ``get_pause_timeout_settings`` PERSISTED its own
fallback on read, so the first time anything asked, a hard 0 was written into the
store. After that "never configured" and "deliberately disabled" were
byte-identical, and no change of default could ever reach the install.

The consequence is a run that never ends. A paused job is owned by the pause
reaper and nothing else; with the timeout at 0 the reaper never fires, so the run
sits open indefinitely, holding its slot and masking whatever runs next. Observed
on a live install 2026-08-09: a vacuum paused mid-run with
``pause_timeout_minutes_default: 0`` had no mechanism that would ever close it.

WHY THIS OVERWRITES A REAL VALUE, WHICH IS NOT A THING TO DO LIGHTLY. A stored 0
CAN be deliberate: ``set_pause_timeout_settings`` is a registered service and
anyone can call it from Developer Tools. So this migration knowingly overrides a
setting some user may have chosen on purpose, and the release notes say so.

The judgement, stated plainly so it can be argued with later: the card offers
15/30/45/60 and no Off, so 0 is a value the interface can produce silently but
never display or offer; the overwhelming majority of stored 0s are the old
read-side write-back rather than anyone's choice; the failure it causes is a run
that never closes; and the remedy for someone who did mean it is one service call
to set it back. Leaving every install without a pause safety net to preserve a
preference almost nobody expressed is the worse trade.

The data repair is only half of it: a 0 that nobody could see was the symptom of a
control nobody could reach. The control has since moved out of the capability-gated
Base Station tab into the rooms sidebar, where every vacuum can see it, and gained an
explicit Off chip so 0 is now a visible choice rather than an invisible default. This
module repairs the values that were written while that was not true.

NO ADAPTER DECLARATION IS NEEDED to judge a target here, so unlike the room
vocabulary repair this cannot be blocked by a provider that has not finished
setting up, and it latches unconditionally.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

MIGRATION_KEY = "pause_timeout_default_v1"

#: The value a 0 is lifted to. Deliberately the lowest the card offers, so the
#: repair is the gentlest one that still closes a run.
REPAIRED_MINUTES = 15


def plan_pause_timeout_migration(*, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the changes this migration would make. Pure; mutates nothing."""
    changes: list[dict[str, Any]] = []
    for vacuum_entity_id, bucket in (data.get("vacuums") or {}).items():
        if not isinstance(bucket, dict):
            continue
        stored = bucket.get("pause_timeout_minutes_default")
        # ONLY an explicit 0. An ABSENT value is left absent on purpose — the
        # getter now computes the default instead of recording one, so absence is
        # how a vacuum inherits any future change. Writing 15 here would recreate
        # exactly the stamping this repair exists to undo.
        if stored == 0:
            changes.append({
                "vacuum_entity_id": vacuum_entity_id,
                "field": "pause_timeout_minutes_default",
                "old": 0,
                "new": REPAIRED_MINUTES,
            })
    return changes


def migrate_pause_timeout_defaults(
    *,
    data: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    """Apply the repair once, recording that it ran. Idempotent.

    Returns ``{"ran": bool, "changes": [...]}``. The caller persists ``data``;
    nothing here writes to disk.
    """
    migrations = data.setdefault("migrations", {})
    if migrations.get(MIGRATION_KEY) and not force:
        return {"ran": False, "changes": []}

    changes = plan_pause_timeout_migration(data=data)
    for change in changes:
        bucket = (data.get("vacuums") or {}).get(change["vacuum_entity_id"])
        if isinstance(bucket, dict):
            bucket[change["field"]] = change["new"]

    migrations[MIGRATION_KEY] = True
    if changes:
        _LOGGER.info(
            "pause_timeout_migration: raised the paused-job timeout from OFF to %d "
            "minutes on %d vacuum(s): %s. A paused run was previously never "
            "cancelled on these. Set it back from the Rooms tab if you want it off.",
            REPAIRED_MINUTES,
            len(changes),
            ", ".join(c["vacuum_entity_id"] for c in changes),
        )
    return {"ran": True, "changes": changes}
