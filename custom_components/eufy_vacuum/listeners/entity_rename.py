"""Entity-rename detection — a managed vacuum's entity id is a storage ADDRESS.

WHY THIS EXISTS (D4). Renaming a vacuum entity in Home Assistant is a one-click,
entirely reasonable thing for a user to do, and until this listener existed nothing
in the integration noticed. It is not a cosmetic change here:

  - **seventeen sections of the HA store are keyed by ``vacuum_entity_id``** — among
    them ``maps`` (every room and every per-room setting), ``run_profiles``,
    ``setup_progress``, ``onboarding``, ``capabilities``, ``maintenance``, and the
    ``vacuums`` record itself; and
  - the learning tree's per-vacuum directory is derived from the object id
    (``learning/history_store.py::_vacuum_slug``), so the job archive, the learned
    statistics and the pose ring live under it too.

``core/manager.py::EufyVacuumManager.ensure_vacuum_record`` then ``setdefault``s a
FRESH record for the new id, so the vacuum comes back looking brand new and
unconfigured while everything it had stands stranded under a key nothing will ask
for again. Silent, total, and triggered by a rename.

WHAT THIS MODULE DOES, AND WHAT IT DELIBERATELY DOES NOT. It **detects and records**.
It does not move the store sections and it does not move the tree — that is a
migration over the user's only copy of their own data and it lands separately, on
its own review. Recording the pair is what makes that migration possible at all:
once Home Assistant has renamed the entity, the OLD id exists nowhere else, so a
repair pass run later has no way to learn what the data used to be called. This
listener is the only moment that fact is observable.

Detection is therefore useful on its own even while the repair does not exist: the
failure goes from silent to stated.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

from ..const import DATA_RUNTIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

_RENAME_UNSUB = "_entity_rename_unsub"

#: Where a detected rename is recorded, on the manager's own data dict so it is
#: persisted with everything else. A list, not a dict: two renames of the same
#: vacuum are two facts and the second must not overwrite the first, or a
#: rename-then-rename-again leaves a pair whose old half nothing can resolve.
PENDING_RENAMES = "pending_entity_renames"

#: Read locally rather than imported from services/_common: that module reaches the
#: manager, which imports the listeners, and the cycle is not worth one string.
_VACUUMS = "vacuums"


def _iso_now() -> str:
    from ..learning.utils import _iso_now as _now

    return _now()


def remove(hass: HomeAssistant) -> None:
    """Unsubscribe the registry listener."""
    unsub: Callable[[], None] | None = hass.data.get(DOMAIN, {}).pop(_RENAME_UNSUB, None)
    if unsub is None:
        return
    try:
        unsub()
    except Exception:  # pragma: no cover - defensive
        _LOGGER.debug("eufy_vacuum: entity-rename listener unsub failed", exc_info=True)


def register(hass: HomeAssistant) -> None:
    """Subscribe to entity-registry updates and record renames of managed vacuums."""
    remove(hass)

    @callback
    def _on_registry_updated(event: Event) -> None:
        data: dict[str, Any] = event.data or {}
        if data.get("action") != "update":
            return
        changes = data.get("changes")
        # `changes` carries the PREVIOUS value of each field that moved. An update
        # that did not touch entity_id (an icon, a friendly name, a device link) is
        # not our concern and is by far the common case — leave early.
        if not isinstance(changes, dict) or "entity_id" not in changes:
            return

        old_entity_id = str(changes.get("entity_id") or "")
        new_entity_id = str(data.get("entity_id") or "")
        if not old_entity_id or not new_entity_id or old_entity_id == new_entity_id:
            return

        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return
        # The authority is the same one `services/_common.is_managed_vacuum` uses.
        # Checked against the OLD id: by the time this fires the registry already
        # holds the new one, and the new one is exactly what we have never seen.
        if old_entity_id not in (manager.data.get(_VACUUMS) or {}):
            return

        record = {
            "old_entity_id": old_entity_id,
            "new_entity_id": new_entity_id,
            "detected_at": _iso_now(),
            "applied": False,
        }
        pending = manager.data.setdefault(PENDING_RENAMES, [])
        if not isinstance(pending, list):
            pending = []
            manager.data[PENDING_RENAMES] = pending
        pending.append(record)

        _LOGGER.warning(
            "eufy_vacuum: managed vacuum renamed %s -> %s. Its stored configuration "
            "and learning history are addressed by the OLD id and have NOT been "
            "moved: rooms, run profiles, setup progress and the job archive are "
            "still filed under %s. Recorded for repair.",
            old_entity_id, new_entity_id, old_entity_id,
        )
        # A callback, not a coroutine — the coalescing write is the right one here
        # (see core/storage.py DRAFT-5): losing a couple of seconds of a rename
        # record to a crash is recoverable, a full-store write per registry event
        # is not proportionate.
        manager.async_save_delayed()

    hass.data.setdefault(DOMAIN, {})[_RENAME_UNSUB] = hass.bus.async_listen(
        EVENT_ENTITY_REGISTRY_UPDATED, _on_registry_updated
    )

