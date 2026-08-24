"""Stall capture — an OPT-IN consumer of ``EVENT_STALL_DETECTED``.

WHAT THIS IS. When a run stalls, render the room the robot stopped in (see
``mapping/stall_capture_render``), write it beside that vacuum's learning data, raise a
persistent notification, and fire a hook event carrying the path so an automation can send
it wherever the user wants. From issue #47.

WHY IT IS A CONSUMER AND NOT PART OF THE DETECTOR. ``EVENT_STALL_DETECTED`` is NOT this
feature's event. ``detect_run_anomalies`` (jobs/active_job.py) is its PRODUCER, not a
consumer: it computes the ``stall`` / ``running_long`` / ``skipped`` fields the card's
snapshot reads and, when ``emit=True``, fires ``EVENT_STALL_DETECTED`` itself. Gating the
detector on this feature's switch would silently disable anomaly reporting for anyone who
turned off stall photos — a regression in a subsystem they never touched. So the detector
fires unconditionally and this subscribes like any other listener; the switch arms THIS
and nothing else.
⚠ was: "It already feeds ``detect_run_anomalies``, which sets the … fields" — the
direction of flow was inverted (L20). The ARGUMENT is unchanged and still sound; only the
mechanism was wrong. Nothing subscribes to the event to DERIVE those fields — the sole
subscriber in the package is this module's ``register()``. A reader hunting for the second
consumer the old paragraph rested on would not find one and might discard the whole
rationale. Other producers of the same event: ``core/manager.py``'s trigger-carrying fire
and the ``dev_inject_stall`` service (services/stall_capture.py).

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
automation reading while we render never sees half a PNG, and the tmp is FSYNCED before
the rename so a power loss cannot leave a zero-length file at that hardcoded path.

Public surface:
    register(hass: HomeAssistant) -> None
    remove(hass: HomeAssistant) -> None
"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback

from .. import pose_store
from ..const import DATA_RUNTIME, DOMAIN, EVENT_STALL_DETECTED
from ..core.manager import EufyVacuumManager
from .. import receipts
from ..mapping.stall_capture_render import render_room_capture, trail_window_seconds
from ._common import get_adapter_value

_LOGGER = logging.getLogger(__name__)

_STALL_CAPTURE_UNSUBS = "_stall_capture_unsubs"

#: Fired after a capture lands. Carries the finished path in ``image_path`` so an
#: automation never has to reconstruct <config>/eufy_vacuum/learning/... by hand and break
#: when the layout moves.
#:
#: ⚠ USE ``image_path``, NOT ``map_id``, TO REACH THE FILE — the payload's ``map_id`` is
#: the RAW id while ``capture_path`` SANITISES it (every character outside [A-Za-z0-9-_]
#: becomes "_", then strip("_"), then "map" if nothing survives). On Roborock the map id
#: is a name, so the event says "Main floor" and the file on disk is "Main_floor.png".
#: This is live today, not a hypothetical future layout move — which is the only break the
#: old comment warned about (D19). It is NOT a broken contract, because ``image_path``
#: carries the correct absolute path in the same payload; it bites only an automation that
#: ignores that field and rebuilds the path from ``map_id`` itself.
EVENT_STALL_CAPTURED = f"{DOMAIN}_stall_captured"

#: Per-vacuum arming, stored on the vacuum record. Absent means OFF: a feature that writes
#: images of someone's home must be opted into, never inherited by an upgrade.
STALL_CAPTURE_KEY = "stall_capture_enabled"

#: Fallback ±window for a vacuum whose adapter declares no pose cadence — the same 30 s
#: this was before the window became brand-derived. See ``pose_refresh_seconds``.
_DEFAULT_TRAIL_SECONDS = 30


def pose_refresh_seconds(vacuum_entity_id: str) -> float | None:
    """The brand's declared pose cadence, or None when it declares none.

    One number, two jobs, and they must agree: it SIZES the ±window banked around the stall
    (via ``trail_window_seconds``) and it tells the renderer how far apart the samples are,
    which decides line-vs-breadcrumbs. Deriving both from one declaration is what stops a
    window from being widened to collect samples the renderer then joins into a route
    nobody observed.
    """
    value = get_adapter_value(
        vacuum_entity_id, "map_state_source", "live_pose", "pose_refresh_s", fallback=None
    )
    try:
        refresh = float(value)
    except (TypeError, ValueError):
        return None
    return refresh if refresh > 0 else None


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


def _trail_from_ring(
    config_dir: str,
    vacuum_entity_id: str,
    when: datetime,
    window_s: int = _DEFAULT_TRAIL_SECONDS,
) -> list[Any]:
    """Anchors from the pose ring within ±``window_s`` of ``when``, oldest first.

    Samples whose anchor is null are DROPPED, not zeroed — a docked or held tick is
    recorded as a genuine None-run, and coercing it would draw a line to the origin.

    The window is a PARAMETER because a brand's pose cadence sets how much history it takes
    to hold a given number of distinct positions; ``trail_window_seconds`` derives it. The
    backward half is free — the ring already holds it — and it is what separates "wedged"
    from "slow": unchanged anchors across the window are real no-movement evidence the
    counters cannot provide.
    """
    start = (when - timedelta(seconds=window_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (when + timedelta(seconds=window_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    """Write via tmp + replace so a reader never sees a half-written PNG.

    THE RENAME IS ATOMIC BUT NOT DURABLE, and this was the shortest of the package's
    four atomic writes — the only one with neither half, while
    ``history_store.write_json`` four files away documents both as IO-7. Without the
    fsync, a power loss between the write and the OS lazily flushing dirty pages
    leaves a ZERO-LENGTH PNG at the stable path the docs tell an automation to
    hardcode, AFTER ``stall.capture.written`` has already reported P and the
    notification has already fired: the picture is announced and the file is empty.

    The unlink is the other half. The tmp sits at a FIXED ``<path>.tmp``, so an
    ``os.replace`` that raises (a vanished directory, a full disk, permissions)
    stranded a full rendered floor-plan of the user's home beside the capture —
    outside the one-file-per-(vacuum, map) contract this module's docstring promises,
    where nothing ever reclaims it, and re-readable at ``/local`` if the user ever
    relocates their learning directory. ``BaseException`` because a cancelled
    executor job leaks the same file a failed one does.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


async def _capture(hass: HomeAssistant, event_data: dict[str, Any]) -> None:
    """Render and deliver one stall capture. Best-effort throughout."""
    # Read the call BEFORE the runtime check, so a decline can name its own station. These
    # are dict reads with no side effects, so the reorder is behaviour-neutral.
    vacuum_entity_id = str(event_data.get("vacuum_entity_id") or "")
    map_id = event_data.get("map_id")
    room_id = event_data.get("room_id")
    room_name = event_data.get("room_name") or f"Room {room_id}"

    manager: EufyVacuumManager | None = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        receipts.emit("stall.capture.declined", "ANY", "listeners.stall_capture",
                      "D", vacuum_entity_id, "no_runtime")
        return
    if not vacuum_entity_id or room_id is None:
        receipts.emit("stall.capture.declined", "ANY", "listeners.stall_capture",
                      "D", vacuum_entity_id, "no_room")
        return
    if not is_enabled(manager, vacuum_entity_id):
        # THE decline this pilot exists for. On 2026-08-09 this returned silently and
        # "why is there no image" cost four queries and a .storage read to answer. It is a
        # deliberate configuration, not a fault, and the difference is now on the wire.
        receipts.emit("stall.capture.declined", "ANY", "listeners.stall_capture",
                      "D", vacuum_entity_id, "not_armed")
        return

    receipts.emit("stall.capture.heard", "ANY", "listeners.stall_capture",
                  "R", vacuum_entity_id, map_id, room_id)

    render = await manager.async_get_map_render_data(vacuum_entity_id=vacuum_entity_id)
    if not isinstance(render, dict) or not render.get("present"):
        receipts.emit("stall.capture.declined", "ANY", "listeners.stall_capture",
                      "D", vacuum_entity_id, "no_render_data")
        _LOGGER.debug("stall_capture: no map render data for %s", vacuum_entity_id)
        return
    geometry = _render_payload(render)
    if geometry is None:
        receipts.emit("stall.capture.declined", "ANY", "listeners.stall_capture",
                      "D", vacuum_entity_id, "unusable")
        _LOGGER.debug("stall_capture: unusable render data for %s", vacuum_entity_id)
        return

    config_dir = hass.config.config_dir
    now = datetime.now(timezone.utc)
    receipts.emit("stall.capture.pose.called", "mapping.map_source", "listeners.stall_capture",
                  "C", vacuum_entity_id)
    live_pose = await manager.async_get_map_live_pose(vacuum_entity_id=vacuum_entity_id)
    anchor = live_pose.get("robot_anchor") if isinstance(live_pose, dict) else None
    # The readability report — a QUALITY claim by the receiver, not an acknowledgement.
    # `broken` = the source did not answer usably at all; `weak` = it answered and carried
    # no position, which is exactly the state that hid a brand having no dot for months.
    _read = ("broken" if not (isinstance(live_pose, dict) and live_pose.get("present"))
             else "lc" if anchor else "weak")
    receipts.emit("stall.capture.pose.observed", "ANY", "listeners.stall_capture",
                  "P", vacuum_entity_id, _read)

    # The window is sized to the brand's pose cadence, and the SAME number goes to the
    # renderer so the draw style matches the density it is actually getting. A brand
    # declaring nothing keeps the historical ±30 s and the historical line.
    pose_refresh_s = pose_refresh_seconds(vacuum_entity_id)
    window_s = (
        trail_window_seconds(pose_refresh_s) if pose_refresh_s is not None
        else _DEFAULT_TRAIL_SECONDS
    )
    trail = await hass.async_add_executor_job(
        _trail_from_ring, config_dir, vacuum_entity_id, now, window_s
    )
    # A separate call gets a separate reply — folding this into the pose receipt would make
    # that one claim a boundary it does not sit at. `window_s` is on the wire because it is
    # DERIVED from the brand's declared cadence, so a dump shows why one brand got 7 points
    # and another got 30 without anyone looking up a constant.
    receipts.emit("stall.capture.trail.read", "ANY", "listeners.stall_capture",
                  "P", vacuum_entity_id, len(trail), window_s)

    # The user's own map orientation — display-only state the card applies with CSS.
    # A capture at the raw raster angle is correct and UNRECOGNISABLE, which for a
    # glanced notification is worse than no picture.
    rotation_deg = 0
    try:
        bucket = ((manager.data.get("maps") or {}).get(vacuum_entity_id) or {}).get(str(map_id)) or {}
        rotation_deg = int(bucket.get("live_map_rotation") or 0) % 360
    except (TypeError, ValueError):
        rotation_deg = 0

    # The raster scan is a width*height Python loop — never on the event loop.
    png = await hass.async_add_executor_job(
        lambda: render_room_capture(
            room_id=int(room_id), anchor=anchor, trail=trail,
            trail_gap_s=pose_refresh_s,
            label=str(room_name), rotation_deg=rotation_deg, **geometry,
        )
    )
    if png is None:
        # Pillow absent, or the room has no cells. Both produce no picture, and the old
        # comment called them "both ABSENCE" — but they are DIFFERENT absences with
        # different fixes, and collapsing them is why "no image" was a four-way guess.
        # The import is on the failure path only, so its cost never touches a good run.
        #
        # ⚠ THE COLLAPSE IS ONLY HALF SPLIT — C33, STILL OPEN, and it is a CODE change
        # (new decline reasons + the receipts DECLINE_REASONS vocabulary), so it is not
        # made here. `no_pillow` came out; `"unusable"` still stands for FOUR distinct
        # causes across TWO emit sites: at the `_render_payload` decline above it means
        # (1) no `room_pixels` in the render data, (2) `room_pixels` that base64 will not
        # decode, or (3) ro_width/ro_height resolving to <= 0; here it means (4) Pillow
        # IS importable but the room has no cells to draw. Do not read the past tense
        # above as "the guess is gone" — it moved one layer down.
        from ..mapping import stall_capture_render as _scr
        receipts.emit("stall.capture.declined", "ANY", "listeners.stall_capture", "D",
                      vacuum_entity_id, "no_pillow" if _scr.Image is None else "unusable")
        _LOGGER.debug(
            "stall_capture: nothing to render for %s room %s", vacuum_entity_id, room_id
        )
        return
    receipts.emit("stall.capture.rendered", "ANY", "listeners.stall_capture",
                  "P", vacuum_entity_id, room_id, len(png))

    path = capture_path(config_dir, vacuum_entity_id, map_id)
    try:
        await hass.async_add_executor_job(_write_atomic, path, png)
    except Exception:  # noqa: BLE001 - disk full, permissions, a vanished directory
        # A FAILURE MAY NOT BE SILENT EITHER — the sibling of §4's rule. Before this, a
        # write that raised aborted the capture and emitted NOTHING: the chain simply
        # stopped after `rendered`, and an absence with no explanation is the four-way
        # guess this pilot exists to end. Report it, then stop — with no artifact on disk
        # there is nothing to notify about and nothing to announce.
        receipts.emit("stall.capture.written", "ANY", "listeners.stall_capture",
                      "F", vacuum_entity_id, path)
        _LOGGER.exception("stall_capture: could not write %s", path)
        return
    receipts.emit("stall.capture.written", "ANY", "listeners.stall_capture",
                  "P", vacuum_entity_id, path)

    vacuum_name = vacuum_entity_id.split(".", 1)[-1].replace("_", " ").title()
    label = map_label(hass, vacuum_entity_id, map_id)
    # "on map X" rather than "on X". The label is a NAME on brands that declare one
    # (Roborock: "Main floor") and the bare id on brands that do not (Eufy: "12"), and
    # "stalled in Kitchen on 12" reads like a truncated sentence. The word carries the
    # bare id without needing per-brand phrasing — which would be a brand-ism in the
    # message layer, the exact place they like to hide.
    message = f"{vacuum_name} likely stalled in {room_name} on map {label}"

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
    # ALL STATIONS THIS NET. A broadcast obliges nobody, so its silence means nothing on its
    # own — the listener COUNT is what makes it readable. Zero means nobody was on the net,
    # so no answer is correct and no fault exists; N with no answers is a real fault. It
    # costs no coupling, because the count never names who is listening. This is the runtime
    # form of the zero-caller class that took a robot-watching session to find in
    # `cancel_active_job`, which passed two hostile audits with no callers at all.
    if receipts.armed():
        receipts.emit("stall.capture.announced", "ANY", "listeners.stall_capture", "B",
                      vacuum_entity_id, path,
                      hass.bus.async_listeners().get(EVENT_STALL_CAPTURED, 0))


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
