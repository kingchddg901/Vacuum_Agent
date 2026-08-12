"""Stall-capture services — arming (production) and injection (maintainer only).

TWO SERVICES, TWO AUDIENCES, DELIBERATELY SEPARATED.

``set_stall_capture`` is production. The capture consumer reads
``vacuums[<id>].stall_capture_enabled`` and treats absent as OFF, so without this the
feature is correct and unreachable — a switch with no way to flip it. This is what the
rooms-card switch calls.

``dev_inject_stall`` is the maintainer instrument. It fires the CANONICAL
``EVENT_STALL_DETECTED`` using the vacuum's real current job/map/room state, so every
downstream consumer runs for real — the room raster is read, the live pose supplies the
dot, the pose ring supplies whatever trail its banked anchors support, the actual
notification path runs. Manufacture the stimulus; let production own every consequence.

What "whatever the anchors support" means, because it is the difference between a thin
capture and a broken one: the trail is drawn only when the ring actually holds distinct
positions across the window, and how many that is depends on the brand's declared pose
cadence (``map_state_source.live_pose.pose_refresh_s``). A coarse brand yields breadcrumbs
rather than a line by design — see ``mapping/stall_capture_render``. An injected stall on a
vacuum whose ring is still filling shows the dot and no trail; that is the feature reporting
what it has, not the instrument misfiring.

IT IS REGISTERED UNCONDITIONALLY, AND FLAGGED HARD INSTEAD (Chris, 2026-08-08). An earlier
draft gated it behind a marker file. Registration is simpler, keeps the declaration-parity
gate honest, and — the real argument — a conditionally-registered service is one that
nobody can find when they need it and nobody is warned about when they don't. The warning
belongs where a caller actually reads it: the ``services.yaml`` description, which IS the
Developer Tools field editor, and the docs.

What it can confuse, and why the warning is not decorative: a stall event is not private
to this feature. It reaches ``detect_run_anomalies`` and therefore the card's snapshot, so
an injected stall makes a run look anomalous in reporting that had nothing wrong with it.

WHAT IT DOES NOT DO. Injection gains no permission to command hardware. It fires an event.
Nothing here pauses, cancels, or dispatches to a robot — those already exist as ordinary
lifecycle services and stay that way, so a maintainer composing them is visibly moving a
vacuum rather than doing it through a button labelled as a timing test.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    EVENT_STALL_DETECTED,
    SERVICE_DEV_INJECT_STALL,
    SERVICE_SET_STALL_CAPTURE,
)
from .. import receipts
from ._common import get_manager

_LOGGER = logging.getLogger(__name__)

SERVICES = (SERVICE_SET_STALL_CAPTURE, SERVICE_DEV_INJECT_STALL)

_SET_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Required("enabled"): cv.boolean,
    }
)

_INJECT_SCHEMA = vol.Schema({vol.Required("vacuum_entity_id"): cv.entity_id})


def register(hass: HomeAssistant) -> None:
    """Register the arming service and the maintainer stall injector."""

    async def _set_stall_capture(call: ServiceCall) -> dict:
        manager = get_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]
        enabled = bool(call.data["enabled"])

        vacuums = manager.data.setdefault("vacuums", {})
        if vacuum_entity_id not in vacuums:
            # Never mint a record for a vacuum this install does not manage — that is the
            # phantom-bucket defect, and a status query that CREATES what it asks about
            # has reached this store before.
            raise ServiceValidationError(
                f"{vacuum_entity_id} is not a managed vacuum"
            )
        vacuums[vacuum_entity_id]["stall_capture_enabled"] = enabled
        await manager.async_save()
        return {"vacuum_entity_id": vacuum_entity_id, "enabled": enabled}

    hass.services.async_register(
        DOMAIN, SERVICE_SET_STALL_CAPTURE, _set_stall_capture,
        schema=_SET_SCHEMA, supports_response="only",
    )

    async def _dev_inject_stall(call: ServiceCall) -> dict:
        """Fire the canonical stall event with the vacuum's REAL current context."""
        manager = get_manager(hass)
        vacuum_entity_id = call.data["vacuum_entity_id"]

        map_id = manager.resolve_active_map_id(vacuum_entity_id=vacuum_entity_id)
        if map_id is None:
            raise ServiceValidationError(
                f"{vacuum_entity_id} has no active map to stall on"
            )

        job = manager.active_job.get_active_job(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)
        )
        room_id = job.get("current_room_id")
        if room_id is None:
            # Refusing here is the honest failure. A stall with no current room has no
            # room to render, and the pose ring is empty at the dock by design, so an
            # injected one would exercise the ABSENCE path and look like a broken
            # renderer. The instrument must not hand anyone that.
            raise ServiceValidationError(
                f"{vacuum_entity_id} is not currently cleaning a room — start a run and "
                "let it move for ~30s before injecting a stall, or the capture has no "
                "pose history to draw"
            )

        rooms = manager.get_managed_rooms(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)
        ).get("rooms", {})
        room = rooms.get(str(room_id)) or {}
        payload = {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": room_id,
            "room_name": room.get("name") or f"Room {room_id}",
            "elapsed_minutes": None,
            "expected_minutes": None,
            "stall_ratio": None,
            "injected": True,
        }
        # PROVENANCE IS A SECTION, NEVER A BRANCH: nothing downstream reads it or behaves
        # differently. This injector exists precisely so every consumer runs FOR REAL, and
        # gating on the caller would build an instrument that certifies itself.
        # (The ARTIFACT still carries no provenance — one file per (vacuum, map),
        # overwritten, so a synthetic capture replaces a real one indistinguishably. That is
        # a retention question, tracked as docs/dev/deltas `live:STALL-PROV-1`.)
        # THE INJECTION POINT, and the ONLY receipt that carries `synth`. Everything
        # downstream truthfully reports `live`, because it truthfully IS live — the capture
        # really reads the map, really renders, really writes. What is synthetic is the
        # STIMULUS, which is a fact about this line and not about its consequences.
        receipts.emit("stall.inject.fired", "ANY", "services.stall_capture", "B",
                      vacuum_entity_id, map_id, room_id, prov="synth")
        hass.bus.async_fire(EVENT_STALL_DETECTED, payload)
        _LOGGER.warning(
            "dev_inject_stall: fired a SYNTHETIC stall for %s room %s — development mode",
            vacuum_entity_id, room_id,
        )
        return payload

    hass.services.async_register(
        DOMAIN, SERVICE_DEV_INJECT_STALL, _dev_inject_stall,
        schema=_INJECT_SCHEMA, supports_response="only",
    )
