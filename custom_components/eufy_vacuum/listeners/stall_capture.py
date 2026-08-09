"""Stall capture — an OPT-IN consumer of ``EVENT_STALL_DETECTED``.

WHAT THIS IS. When a run stalls, render the room the robot stopped in (see
``mapping/stall_capture_render``), write it beside that vacuum's learning data, raise a
persistent notification, and fire a hook event carrying the path so an automation can send
it wherever the user wants. From issue #47.

WHY IT IS A CONSUMER AND NOT PART OF THE DETECTOR. ``EVENT_STALL_DETECTED`` is NOT this
feature's event. It already feeds ``detect_run_anomalies``, which sets the ``stall`` /
``running_long`` / ``skipped`` fields the card's snapshot reads. Gating the detector on
this feature's switch would silently disable anomaly reporting for anyone who turned off
stall photos — a regression in a subsystem they never touched. So the detector fires
unconditionally and this subscribes like any other listener; the switch arms THIS and
nothing else.

That also makes the two failure modes distinguishable, which matters for the maintainer
dev card: with the switch off, an injected stall still fires the event and still reports
anomalies, so "no picture" means the consumer, not the injector.

WHERE THE IMAGE GOES, AND WHY NOT ``www/``. ``<config>/eufy_vacuum/learning/<vacuum>/
stall/<map_id>.png`` — beside the rest of that vacuum's data. Deliberately NOT under
``www/``: that directory is served at ``/local/`` WITHOUT AUTHENTICATION, and this feature
would otherwise publish a cropped floor-plan of the user's home at a fetchable URL on
every stall. The trade is that a persistent notification (markdown, URL-only) cannot embed
the image — so the notification carries the TEXT and the hook carries the PATH, which is
the half a phone actually needs. An image is of little use to someone already looking at
Home Assistant.

One file per (vacuum, map), overwritten each time: no accumulation, no pruning, and a
STABLE path an automation can hardcode. The write is atomic (tmp + ``os.replace``) so an
automation reading while we render never sees half a PNG.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback

from .. import pose_store
from ..const import DATA_RUNTIME, DOMAIN, EVENT_STALL_DETECTED
from ..core.manager import EufyVacuumManager
from ..mapping.stall_capture_render import render_room_capture
from ._common import get_adapter_value

_LOGGER = logging.getLogger(__name__)

_STALL_CAPTURE_UNSUBS = "_stall_capture_unsubs"

#: Fired after a capture lands. Carries the path so an automation never has to
#: reconstruct <config>/eufy_vacuum/learning/... by hand and break when the layout moves.
EVENT_STALL_CAPTURED = f"{DOMAIN}_stall_captured"

#: Per-vacuum arming, stored on the vacuum record. Absent means OFF: a feature that writes
#: images of someone's home must be opted into, never inherited by an upgrade.
STALL_CAPTURE_KEY = "stall_capture_enabled"

#: The ±window banked around the stall instant. The backward half is free — the pose ring
#: already holds it — and it is what separates "wedged" from "slow": unchanged anchors
#: across the window are real no-movement evidence the counters cannot provide.
_TRAIL_SECONDS = 30


def remove(hass: HomeAssistant) -> None:
    """Remove the stall-capture consumer."""
    domain_data = hass.data.get(DOMAIN, {})
    unsubs: list[Callable[[], None]] = domain_data.pop(_STALL_CAPTURE_UNSUBS, [])
    for unsub in unsubs:
        try:
            unsub()
        except Exception:  # pragma: no cover - best-effort teardown
            _LOGGER.exception("Failed to remove stall-capture listener")


def is_enabled(manager: EufyVacuumManager, vacuum_entity_id: str) -> bool:
    """Whether capture is armed for this vacuum. Absent → OFF."""
    try:
        bucket = (manager.data.get("vacuums") or {}).get(vacuum_entity_id) or {}
    except Exception:  # pragma: no cover - defensive; a broken store must not raise here
        return False
    return bool(bucket.get(STALL_CAPTURE_KEY))


def capture_path(config_dir: str, vacuum_entity_id: str, map_id: Any) -> str:
    """``<config>/eufy_vacuum/learning/<vacuum>/stall/<map_id>.png``.

    ``object_id`` rather than the full entity id, matching the pose and battery stores and
    keeping the path free of dots. The map id is sanitised because Roborock's is a NAME
    ("Main floor"), not a number, and can carry separators.
    """
    object_id = str(vacuum_entity_id).split(".", 1)[-1]
    safe_map = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in str(map_id)
    ).strip("_") or "map"
    return os.path.join(
        config_dir, "eufy_vacuum", "learning", object_id, "stall", f"{safe_map}.png"
    )


def _trail_from_ring(config_dir: str, vacuum_entity_id: str, when: datetime) -> list[Any]:
    """Anchors from the pose ring within ±_TRAIL_SECONDS of ``when``, oldest first.

    Samples whose anchor is null are DROPPED, not zeroed — a docked or held tick is
    recorded as a genuine None-run, and coercing it would draw a line to the origin.
    """
    start = (when - timedelta(seconds=_TRAIL_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (when + timedelta(seconds=_TRAIL_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        samples = pose_store.read_range(
            config_dir=config_dir, vacuum_entity_id=vacuum_entity_id,
            start_iso=start, end_iso=end,
        )
    except Exception:  # pragma: no cover - the ring is best-effort context
        _LOGGER.exception("stall_capture: could not read the pose ring")
        return []
    return [s.get("anchor") for s in samples if isinstance(s, dict) and s.get("anchor")]


def _render_payload(render: dict[str, Any]) -> dict[str, Any] | None:
    """Geometry kwargs for the renderer, taken from the adapter's render-data block.

    Passed through rather than re-derived: the raster is ``ro_*`` sized and OFFSET into a
    ``width x height`` canvas, and its bytes carry ``room_id << rid_shift``. Recomputing
    any of that here is how the renderer got it wrong the first time.
    """
    rp_b64 = render.get("room_pixels")
    if not rp_b64:
        return None
    try:
        room_pixels = base64.b64decode(rp_b64)
    except (ValueError, TypeError):
        return None
    ro_w = int(render.get("ro_width") or render.get("width") or 0)
    ro_h = int(render.get("ro_height") or render.get("height") or 0)
    if ro_w <= 0 or ro_h <= 0:
        return None
    return {
        "room_pixels": room_pixels,
        "ro_width": ro_w,
        "ro_height": ro_h,
        "canvas_width": int(render.get("width") or ro_w),
        "canvas_height": int(render.get("height") or ro_h),
        "ro_dx": int(render.get("ro_dx") or 0),
        "ro_dy": int(render.get("ro_dy") or 0),
        "rid_shift": int(render.get("rid_shift") or 0),
        "flip_y": bool(render.get("flip_y")),
    }


def map_label(hass: HomeAssistant, vacuum_entity_id: str, map_id: Any) -> str:
    """A human map name if the brand declares one, else the map id.

    Read from the adapter's declared ``entities.active_map`` — never a constructed entity
    id. What comes back differs by brand, and the difference is honest rather than papered
    over:

    * Roborock declares ``select.<id>_selected_map``, whose state IS the name
      ("Main floor"), so the message reads well.
    * Eufy declares ``sensor.<id>_active_map``, whose state is the numeric ID ("12"). The
      friendly name ("Home (ID: 12)") lives on the fork's ``select.<id>_switch_map``,
      which the Eufy adapter does NOT declare — see the map-switcher work gated on the
      fork's PR #150. Declaring it would give Eufy a real name here for one line of
      adapter config; until then the id is what we honestly have.

    Guessing an entity id to find a nicer string would be exactly the brand-ism this
    project keeps removing, so it is not done.
    """
    entity_id = get_adapter_value(vacuum_entity_id, "entities", "active_map", fallback=None)
    if isinstance(entity_id, (list, tuple)):
        entity_id = entity_id[0] if entity_id else None
    if isinstance(entity_id, str) and entity_id:
        state = hass.states.get(entity_id)
        value = (state.state or "").strip() if state else ""
        if value and value.lower() not in ("unknown", "unavailable", "none"):
            return value
    return str(map_id)


def _write_atomic(path: str, data: bytes) -> None:
    """Write via tmp + replace so a reader never sees a half-written PNG."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


async def _capture(hass: HomeAssistant, event_data: dict[str, Any]) -> None:
    """Render and deliver one stall capture. Best-effort throughout."""
    manager: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        return

    vacuum_entity_id = str(event_data.get("vacuum_entity_id") or "")
    map_id = event_data.get("map_id")
    room_id = event_data.get("room_id")
    room_name = event_data.get("room_name") or f"Room {room_id}"
    if not vacuum_entity_id or room_id is None:
        return
    if not is_enabled(manager, vacuum_entity_id):
        return

    render = await manager.async_get_map_render_data(vacuum_entity_id=vacuum_entity_id)
    if not isinstance(render, dict) or not render.get("present"):
        _LOGGER.debug("stall_capture: no map render data for %s", vacuum_entity_id)
        return
    geometry = _render_payload(render)
    if geometry is None:
        _LOGGER.debug("stall_capture: unusable render data for %s", vacuum_entity_id)
        return

    config_dir = hass.config.config_dir
    now = datetime.now(timezone.utc)
    live_pose = await manager.async_get_map_live_pose(vacuum_entity_id=vacuum_entity_id)
    anchor = live_pose.get("robot_anchor") if isinstance(live_pose, dict) else None
    trail = await hass.async_add_executor_job(
        _trail_from_ring, config_dir, vacuum_entity_id, now
    )

    # The raster scan is a width*height Python loop — never on the event loop.
    png = await hass.async_add_executor_job(
        lambda: render_room_capture(
            room_id=int(room_id), anchor=anchor, trail=trail,
            label=str(room_name), **geometry,
        )
    )
    if png is None:
        # Pillow absent, or the room has no cells. Both are ABSENCE: no picture, no noise.
        _LOGGER.debug(
            "stall_capture: nothing to render for %s room %s", vacuum_entity_id, room_id
        )
        return

    path = capture_path(config_dir, vacuum_entity_id, map_id)
    await hass.async_add_executor_job(_write_atomic, path, png)

    vacuum_name = vacuum_entity_id.split(".", 1)[-1].replace("_", " ").title()
    label = map_label(hass, vacuum_entity_id, map_id)
    message = f"{vacuum_name} likely stalled in {room_name} on {label}"

    # "likely" is load-bearing. The detector is an elapsed-vs-estimate ratio, not proof of
    # stillness, and estimates are cold while the learning store rebuilds. A notification
    # that is sometimes wrong is fine; one that sounds certain and is wrong is not.
    try:
        from homeassistant.components import persistent_notification

        persistent_notification.async_create(
            hass, message, title="Vacuum Agent",
            notification_id=f"{DOMAIN}_stall_{vacuum_entity_id}",
        )
    except Exception:  # pragma: no cover - the artifact matters more than the banner
        _LOGGER.exception("stall_capture: could not raise the notification")

    hass.bus.async_fire(
        EVENT_STALL_CAPTURED,
        {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": str(map_id),
            "room_id": room_id,
            "room_name": room_name,
            "image_path": path,
            "message": message,
        },
    )


def register(hass: HomeAssistant) -> None:
    """Subscribe to EVENT_STALL_DETECTED and capture when armed."""
    remove(hass)

    @callback
    def _on_stall(event: Event) -> None:
        data = dict(event.data or {})

        async def _run() -> None:
            try:
                await _capture(hass, data)
            except Exception:  # pragma: no cover - a picture must never kill a run
                _LOGGER.exception("stall_capture: capture failed")

        hass.async_create_task(_run())

    hass.data.setdefault(DOMAIN, {})[_STALL_CAPTURE_UNSUBS] = [
        hass.bus.async_listen(EVENT_STALL_DETECTED, _on_stall)
    ]
