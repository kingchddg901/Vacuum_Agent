"""Setup panel services — onboarding wizard backend.

Services driving the panel-based setup flow:
- setup_get_status: read the current setup state
- setup_add_vacuum: register a vacuum with the integration
- setup_import_active_map: import the vacuum's active map
- setup_get_map_rooms: list managed rooms for a map
- setup_save_rooms: persist the room selection
- setup_delete_map: delete a map (gated by protection)
- setup_reject_rooms: mark rooms as phantoms on ONE map (never re-surface)
- setup_unreject_rooms: undo that, so the room can be configured again
- setup_force_remove_room: bypass missing-pass counter for one room
- setup_set_map_camera / setup_set_panel_title: panel presentation
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INJSETB0  `services/queue.py#INJSETB0`
#       A4-SETUP-15 (closed RP-032): None of the 10 setup_* services and 5 of the 6 adapter-config services have
#              services.yaml or translation entries
#   INYA5T84  `adapters/config_schema.py#INYA5T84`
#       A4-SETUP-9 (closed RP-033): adapter `setup.steps` is never validated at registration despite two docstrings and
#              the schema claiming it is; two declared step IDs have no completion writer and
#   INC63FDF  `rooms/room_crud.py#INC63FDF`
#       A4-SETUP-1: setup_save_rooms rebuilds the map from the stale/absent `data["discovery"]` cache
#              and REPLACES the map's rooms wholesale — returns {"status": "success"}
#   INT62M7A  `themes/services.py#INT62M7A`
#       A4-SETUP-12: setup_get_map_rooms returns a success-shaped empty room list when the runtime
#              manager is missing — the caller cannot tell "integration not loaded" from "map has
#              no rooms"
#       A4-SETUP-8: setup_save_rooms stamps the setup step complete unconditionally, unlike both of its
#              sibling step-advancing handlers


from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from ..const import (
    DATA_RUNTIME,
    DOMAIN,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_REPAIR_RENAME,
    SERVICE_SET_ENTITY_OVERRIDE,
    ENTITY_OVERRIDES_KEY,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_SETUP_FORCE_REMOVE_ROOM,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_IMPORT_MAP,
    SERVICE_SETUP_REJECT_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
    SERVICE_SETUP_SET_MAP_CAMERA,
    SERVICE_SETUP_SET_PANEL_TITLE,
    SERVICE_SETUP_UNREJECT_ROOMS,
)
from ..learning.utils import _iso_now
from ._common import get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_SETUP_GET_STATUS,
    SERVICE_SETUP_ADD_VACUUM,
    SERVICE_SETUP_IMPORT_MAP,
    SERVICE_SETUP_GET_MAP_ROOMS,
    SERVICE_SETUP_SAVE_ROOMS,
    SERVICE_SETUP_DELETE_MAP,
    SERVICE_SETUP_REJECT_ROOMS,
    SERVICE_SETUP_UNREJECT_ROOMS,
    SERVICE_SETUP_FORCE_REMOVE_ROOM,
    SERVICE_SETUP_SET_MAP_CAMERA,
    SERVICE_SETUP_SET_PANEL_TITLE,
    SERVICE_SETUP_REPAIR_RENAME,
)


def _completed_step_result(result: object) -> bool:
    """Return true when a setup workflow result should advance progress."""
    if not isinstance(result, dict):
        return True
    return result.get("status") in {"success", "already_done"}


_SETUP_ADD_VACUUM_SCHEMA = vol.Schema(
    {vol.Required("vacuum_entity_id"): cv.entity_id}
)
_SETUP_SET_PANEL_TITLE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        # Blank/omitted title reverts the sidebar entry to the default name.
        vol.Optional("title", default=""): vol.All(cv.string, vol.Length(max=48)),
    }
)
_SETUP_SET_MAP_CAMERA_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        # The live-map image/camera entity_id to use as the backdrop. Blank/omitted
        # clears the override (falls back to the adapter pattern). Kept a plain string
        # (not cv.entity_id) so "" is accepted as the clear sentinel; the resolver
        # existence-checks whatever is stored.
        vol.Optional("entity_id", default=""): cv.string,
    }
)
_SETUP_IMPORT_MAP_SCHEMA = vol.Schema(
    {vol.Required("vacuum_entity_id"): cv.entity_id}
)
_SET_ENTITY_OVERRIDE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("role"): cv.string,
        # Plain string, not cv.entity_id, so "" is accepted as the CLEAR
        # sentinel — same convention as setup_set_map_camera.
        vol.Optional("entity_id", default=""): cv.string,
    }
)
_SETUP_GET_STATUS_SCHEMA = vol.Schema({})
_SETUP_GET_MAP_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
    }
)
def _enabled_room_ids_validator(value):
    """RP-005/RF-02 (ROOMS-2). Reject null and [] as loud schema errors instead of
    letting cv.ensure_list(None) == [] coerce a "no selection" mistake into "delete
    every room" -- the key must be OMITTED to keep the current selection. (Same
    validator as services/rooms.py's _SAVE_MANAGED_ROOMS_SCHEMA -- kept local since
    the two service modules share no common schema-helper module in scope here.)
    """
    if value is None:
        raise vol.Invalid(
            "enabled_room_ids: null is not a selection; omit the key to keep the current selection"
        )
    coerced = cv.ensure_list(value)
    if not coerced:
        raise vol.Invalid(
            "enabled_room_ids: empty selection cannot delete rooms; use enabled flags or remove_map"
        )
    return [vol.Coerce(int)(v) for v in coerced]


_SETUP_SAVE_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Optional("enabled_room_ids"): _enabled_room_ids_validator,
        vol.Optional("floor_types"): vol.Schema({cv.string: cv.string}),
    }
)
_SETUP_DELETE_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        # confirmation_token: truthy string for elevated; map display name for high
        vol.Optional("confirmation_token"): cv.string,
    }
)
_SETUP_REJECT_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("room_ids"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        # A4-SETUP-6: optional so every existing caller keeps working; when
        # omitted the handler resolves the ACTIVE map rather than falling back
        # to the old every-map rejection.
        vol.Optional("map_id"): cv.string,
    }
)
_SETUP_UNREJECT_ROOMS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("room_ids"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional("map_id"): cv.string,
    }
)
_SETUP_FORCE_REMOVE_ROOM_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("room_id"): vol.Coerce(int),
    }
)


_SETUP_REPAIR_RENAME_SCHEMA = vol.Schema(
    {
        vol.Required("old_entity_id"): cv.entity_id,
        vol.Required("new_entity_id"): cv.entity_id,
        vol.Optional("overwrite_destination", default=False): cv.boolean,
    }
)


async def _handle_repair_renamed_vacuum(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Migrate a vacuum's data after a rename this integration never saw.

    WHY A MANUAL SERVICE EXISTS AT ALL. The automatic path
    (``core/manager.py::_apply_pending_entity_renames``) is driven by
    ``listeners/entity_rename.py``, which only records renames that happen while it is
    running. **A rename that happened before that listener shipped left no record, and
    the old entity id is not recoverable from anywhere** — Home Assistant's registry has
    moved on. Only the user knows what the vacuum used to be called, so only the user
    can supply it.

    ONE MIGRATION, NOT TWO. This appends a record and calls the same applier the
    automatic path uses, so the section discovery, the tree-before-store ordering and
    the collision rules are identical by construction rather than by review.

    THE COLLISION IS EXPECTED HERE, unlike the automatic path. By the time a user
    notices, the new id usually holds an auto-created empty shell —
    ``ensure_vacuum_record`` made one on the first start after the rename. The first
    call therefore reports what stands in the way and changes nothing; passing
    ``overwrite_destination`` discards those entries and proceeds.
    """
    manager = get_manager(hass)
    old_id = str(call.data["old_entity_id"])
    new_id = str(call.data["new_entity_id"])
    overwrite = bool(call.data.get("overwrite_destination", False))

    if old_id == new_id:
        return {"repaired": False, "reason": "same_entity_id",
                "old_entity_id": old_id, "new_entity_id": new_id}

    sections = [
        key for key, value in manager.data.items()
        if isinstance(value, dict) and old_id in value
    ]
    if not sections:
        # Nothing under the old id. Either the name is wrong or it was already
        # repaired — say which is impossible to know, so say neither.
        return {"repaired": False, "reason": "nothing_stored_under_old_id",
                "old_entity_id": old_id, "new_entity_id": new_id}

    record = {
        "old_entity_id": old_id,
        "new_entity_id": new_id,
        "detected_at": _iso_now(),
        "applied": False,
        "manual": True,
        "overwrite_destination": overwrite,
    }
    pending = manager.data.setdefault("pending_entity_renames", [])
    if not isinstance(pending, list):
        pending = []
        manager.data["pending_entity_renames"] = pending
    pending.append(record)

    applied = await manager._apply_pending_entity_renames()
    if not record.get("applied"):
        return {
            "repaired": False,
            "reason": "destination_not_empty" if record.get("blocked_on") else "migration_failed",
            "blocked_on": record.get("blocked_on", []),
            "old_entity_id": old_id,
            "new_entity_id": new_id,
            "message": (
                f"{new_id} already holds data in: "
                f"{', '.join(record.get('blocked_on') or [])}. That is usually the empty "
                f"record created on the first start after the rename. Re-run with "
                f"overwrite_destination: true to discard it and move the real data over."
            ) if record.get("blocked_on") else
            "The learning tree could not be moved; nothing was changed. See the log.",
        }

    return {
        "repaired": True,
        "old_entity_id": old_id,
        "new_entity_id": new_id,
        "sections_moved": record.get("sections_moved", []),
        "tree_moved": record.get("tree_moved", False),
        "overwrote": record.get("overwrote", []),
        "applied_count": applied,
    }


def register(hass: HomeAssistant) -> None:
    """Register setup-panel services."""

    # Lazy imports keep services package import-time clean. The setup
    # subpackage transitively pulls in HA storage and more; deferring
    # the imports until first registration is harmless.
    from ..setup.workflow import add_vacuum as _add_vacuum
    from ..setup.workflow import import_active_map as _import_active_map
    from ..setup.status import get_setup_status as _get_setup_status
    from ..setup.delete import delete_map as _delete_map
    from ..setup.drift import (
        record_step_completed as _record_setup_step,
        reject_rooms as _reject_rooms,
        unreject_rooms as _unreject_rooms,
        force_remove_room as _force_remove_room,
    )

    def _rejection_map_id(manager: Any, call: ServiceCall) -> str | None:
        """The map a rejection applies to: the caller's, else the ACTIVE map.

        A4-SETUP-6. Room ids are reissued per map, so a rejection has to name
        one. The card does not send ``map_id`` today, and the map it was looking
        at when the user clicked is the active one, so resolving it here is both
        correct and back-compatible. None (no resolver, or an adapter that cannot
        say) falls through to the legacy every-map rejection — worse, but it is
        the pre-existing behaviour and never silently no-ops the rejection.
        """
        explicit = call.data.get("map_id")
        if explicit:
            return str(explicit)
        resolver = getattr(manager, "resolve_active_map_id", None)
        if not callable(resolver):
            return None
        resolved = resolver(call.data["vacuum_entity_id"])
        return str(resolved) if resolved else None

    async def setup_get_status(call: ServiceCall) -> dict:
        return _get_setup_status(hass)

    async def setup_add_vacuum(call: ServiceCall) -> dict:
        result = await _add_vacuum(hass, call.data["vacuum_entity_id"])
        # Stamp step complete only when the workflow genuinely completed.
        # "blocked" means the user still needs to take action, so the setup
        # panel should not render the step as done.
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is not None and _completed_step_result(result):
            _record_setup_step(
                manager, call.data["vacuum_entity_id"], "add_vacuum"
            )
            await manager.async_save()
        # A genuinely NEW vacuum needs the per-vacuum wiring that only runs at
        # async_setup_entry — brand adapter registration (auto-detects Roborock vs
        # Eufy), companion entities, lifecycle listeners, and its sidebar panel.
        # add_vacuum only records it + registers a panel; without a reload the new
        # vacuum is half-wired (no adapter, no entities). Reload after the record
        # is saved (same pattern as the options-flow update listener). Scheduled as
        # a task so this service returns first.
        if isinstance(result, dict) and result.get("status") == "success":
            entries = hass.config_entries.async_entries(DOMAIN)
            if entries:
                hass.async_create_task(
                    hass.config_entries.async_reload(entries[0].entry_id)
                )
        return result

    async def set_entity_override(call: ServiceCall) -> dict:
        """Pin a role to an entity the user chose (live:ENT-13).

        The panel's write path for the storage contract in const.ENTITY_OVERRIDES_KEY.
        A blank entity_id CLEARS the override and lets auto-resolution take the
        role back.

        Reloads the config entry afterwards, because the override is consumed at
        adapter-registration time — without the reload the user would save a
        choice and see nothing change, which is the silent failure this whole
        feature exists to remove.
        """
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "reason": "runtime_unavailable"}

        vacuum_entity_id = call.data["vacuum_entity_id"]
        role = str(call.data["role"]).strip()
        entity_id = str(call.data.get("entity_id") or "").strip()
        if not role:
            return {"status": "error", "reason": "missing_role"}

        store = manager.data.setdefault(ENTITY_OVERRIDES_KEY, {})
        per_vacuum = store.setdefault(vacuum_entity_id, {})
        if entity_id:
            per_vacuum[role] = entity_id
        else:
            per_vacuum.pop(role, None)
            if not per_vacuum:
                store.pop(vacuum_entity_id, None)
        await manager.async_save()

        _LOGGER.info(
            "eufy_vacuum: entity override for %s role %r -> %s",
            vacuum_entity_id, role, entity_id or "(cleared)",
        )

        entries = hass.config_entries.async_entries(DOMAIN)
        if entries:
            hass.async_create_task(
                hass.config_entries.async_reload(entries[0].entry_id)
            )
        return {
            "status": "success",
            "role": role,
            "entity_id": entity_id or None,
        }

    async def setup_import_active_map(call: ServiceCall) -> dict:
        result = await _import_active_map(hass, call.data["vacuum_entity_id"])
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is not None and _completed_step_result(result):
            _record_setup_step(
                manager, call.data["vacuum_entity_id"], "import_active_map"
            )
            await manager.async_save()
        return result

    async def setup_get_map_rooms(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        data = resolved_call_data(hass, call)
        if manager is None:
            return {"rooms": [], "vacuum_entity_id": data["vacuum_entity_id"], "map_id": data.get("map_id")}
        result = manager.get_managed_rooms(
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
        )
        rooms_dict = result.get("rooms", {})
        rooms_list = sorted(
            [
                {
                    "room_id": int(room.get("room_id", rid)),
                    "name": str(room.get("name", f"Room {rid}")),
                    "floor_type": str(room.get("floor_type", "hardwood")),
                }
                for rid, room in rooms_dict.items()
                if isinstance(room, dict)
            ],
            key=lambda r: r["room_id"],
        )
        return {
            "vacuum_entity_id": data["vacuum_entity_id"],
            "map_id": str(data["map_id"]),
            "rooms": rooms_list,
        }

    async def setup_save_rooms(call: ServiceCall) -> dict:
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        data = resolved_call_data(hass, call)
        result = manager.save_managed_rooms(
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
            enabled_room_ids=data.get("enabled_room_ids"),
            floor_types=data.get("floor_types") or {},
        )
        if result.get("saved") is False:
            # This service supports_response=True -- the refusal reaches the caller
            # directly rather than a WARNING log. Do not stamp the step complete or
            # save: nothing changed.
            return {
                "status": "error",
                "reason": result.get("reason"),
                "message": f"Save refused: {result.get('reason')}",
            }
        # is_configured stamping is handled by build_managed_rooms —
        # every room returned by save_managed_rooms now carries True
        # plus a configured_at timestamp. Mark the step complete here.
        _record_setup_step(
            manager, data["vacuum_entity_id"], "save_rooms"
        )
        await manager.async_save()
        return {"status": "success", "room_count": result.get("room_count", 0)}

    async def setup_delete_map(call: ServiceCall) -> dict:
        data = resolved_call_data(hass, call)
        return await _delete_map(
            hass,
            vacuum_entity_id=data["vacuum_entity_id"],
            map_id=data["map_id"],
            confirmation_token=data.get("confirmation_token"),
        )

    async def setup_reject_rooms(call: ServiceCall) -> dict:
        """Mark discovered rooms as phantoms — never surface them again."""
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        vacuum_entity_id = call.data["vacuum_entity_id"]
        result = _reject_rooms(
            manager,
            vacuum_entity_id,
            call.data["room_ids"],
            map_id=_rejection_map_id(manager, call),
        )
        # Fire room-update callbacks for every map that lost a room so
        # the entity-platform cleanup (switch/number/sensor) tears down
        # the orphaned entities. The drift module is pure data; service
        # handler dispatches the HA-side notifications.
        for affected_map_id in result.get("affected_map_ids", []):
            manager._notify_rooms_updated(
                vacuum_entity_id=vacuum_entity_id,
                map_id=affected_map_id,
            )
        await manager.async_save()
        return {"status": "success", **result}

    async def setup_unreject_rooms(call: ServiceCall) -> dict:
        """Undo a rejection so the room can be discovered and configured again.

        A4-SETUP-6's escape hatch. Without it a rejection was one-way: the
        rejected id stopped surfacing in ``new_rooms``, so a room rejected by
        mistake — or, before rejections were map-scoped, a REAL room upstairs
        sharing an id with a ghost downstairs — had no route back short of
        hand-editing ``.storage``.

        The room does not reappear immediately: it resurfaces on the next
        discovery pass that sees it, through the normal confirmation cadence.
        """
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        result = _unreject_rooms(
            manager,
            call.data["vacuum_entity_id"],
            call.data["room_ids"],
            map_id=_rejection_map_id(manager, call),
        )
        await manager.async_save()
        return {"status": "success", **result}

    async def setup_force_remove_room(call: ServiceCall) -> dict:
        """Bypass the missing-pass counter and immediately flag a room removed.

        The room stays in managed_rooms (history preserved); only its
        drift signal flips. Pair with a separate delete operation if
        full removal is wanted.
        """
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        result = _force_remove_room(
            manager,
            call.data["vacuum_entity_id"],
            call.data["room_id"],
        )
        await manager.async_save()
        return {"status": "success", **result}

    async def setup_set_panel_title(call: ServiceCall) -> dict:
        """Set (or clear) a vacuum's sidebar panel title and re-register live.

        Stores ``panel_title`` on the managed-vacuum record (a blank title reverts
        to the default), persists it, then re-registers that vacuum's panel with
        the new title so the sidebar updates without a restart. The user may need
        to refresh the browser for the sidebar to repaint.
        """
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        vacuum_entity_id = call.data["vacuum_entity_id"]
        record = manager.data.get("vacuums", {}).get(vacuum_entity_id)
        if record is None:
            return {
                "status": "error",
                "message": f"Vacuum '{vacuum_entity_id}' is not managed.",
            }

        raw_title = str(call.data.get("title") or "").strip()
        if raw_title:
            record["panel_title"] = raw_title
        else:
            record.pop("panel_title", None)  # blank -> revert to the default
        await manager.async_save()

        from ..panels import (
            append_to_panel_ledger,
            async_register_vacuum_panel,
            effective_panel_title,
        )

        title = effective_panel_title(record)
        panel_url = await async_register_vacuum_panel(
            hass, vacuum_entity_id, title=title, replace=True
        )
        # RP-039/RF-16 (INT79PB7): same orphan bug as setup/workflow.py's add_vacuum — this
        # rename service discarded the return value and never touched the entry's
        # panel-teardown ledger, so a vacuum whose panel title was ever renamed
        # never had its panel cleanly removed on unload.
        _entries = hass.config_entries.async_entries(DOMAIN)
        if _entries:
            append_to_panel_ledger(hass, _entries[0].entry_id, panel_url)
        return {
            "status": "success",
            "message": f"Panel renamed to '{title}'. Refresh the page to update the sidebar.",
            "vacuum_entity_id": vacuum_entity_id,
            "panel_title": title,
        }

    async def setup_set_map_camera(call: ServiceCall) -> dict:
        """Set (or clear) a vacuum's live-map image/camera entity override.

        Stores ``live_map_image_entity`` on the managed-vacuum record (a blank value
        clears it, falling back to the adapter's ``live_map_image_entity_pattern``).
        The dashboard snapshot's live-backdrop resolution prefers this override over
        the pattern. No reload needed — the next snapshot fetch picks it up.
        """
        manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
        if manager is None:
            return {"status": "error", "message": "Integration manager not available."}
        vacuum_entity_id = call.data["vacuum_entity_id"]
        record = manager.data.get("vacuums", {}).get(vacuum_entity_id)
        if record is None:
            return {
                "status": "error",
                "message": f"Vacuum '{vacuum_entity_id}' is not managed.",
            }

        raw_entity = str(call.data.get("entity_id") or "").strip()
        if raw_entity:
            record["live_map_image_entity"] = raw_entity
        else:
            record.pop("live_map_image_entity", None)  # blank -> fall back to pattern
        await manager.async_save()
        return {
            "status": "success",
            "message": (
                f"Live-map camera set to '{raw_entity}'."
                if raw_entity
                else "Live-map camera override cleared."
            ),
            "vacuum_entity_id": vacuum_entity_id,
            "live_map_image_entity": raw_entity or None,
        }

    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_GET_STATUS, setup_get_status,
        schema=_SETUP_GET_STATUS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_ADD_VACUUM, setup_add_vacuum,
        schema=_SETUP_ADD_VACUUM_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ENTITY_OVERRIDE, set_entity_override,
        schema=_SET_ENTITY_OVERRIDE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_IMPORT_MAP, setup_import_active_map,
        schema=_SETUP_IMPORT_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_GET_MAP_ROOMS, setup_get_map_rooms,
        schema=_SETUP_GET_MAP_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_SAVE_ROOMS, setup_save_rooms,
        schema=_SETUP_SAVE_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_DELETE_MAP, setup_delete_map,
        schema=_SETUP_DELETE_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_REJECT_ROOMS, setup_reject_rooms,
        schema=_SETUP_REJECT_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_UNREJECT_ROOMS, setup_unreject_rooms,
        schema=_SETUP_UNREJECT_ROOMS_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_FORCE_REMOVE_ROOM, setup_force_remove_room,
        schema=_SETUP_FORCE_REMOVE_ROOM_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_SET_PANEL_TITLE, setup_set_panel_title,
        schema=_SETUP_SET_PANEL_TITLE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_SET_MAP_CAMERA, setup_set_map_camera,
        schema=_SETUP_SET_MAP_CAMERA_SCHEMA, supports_response=True,
    )

    async def setup_repair_renamed_vacuum(call: ServiceCall) -> dict:
        return await _handle_repair_renamed_vacuum(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_SETUP_REPAIR_RENAME, setup_repair_renamed_vacuum,
        schema=_SETUP_REPAIR_RENAME_SCHEMA, supports_response=True,
    )
