"""DispatchManager — send-side wire dispatch for room / zone / global-pre-call cleans.

This subsystem owns the SEND SIDE of the clean pipeline: turning a resolved clean
payload into the adapter's on-wire service envelope and pushing it to the vacuum. It is
constructed with the core manager (the bundled-subsystem pattern) and reads the manager's
hass + map/room helpers via ``self._manager``.

Owns:
- ``_dispatch_clean_payload`` — send one clean payload using the adapter's dispatch
  envelope (wrapped ``{command, params}`` or direct merge-into-data).
- ``dispatch_zone_clean`` — ad-hoc free-form zone clean (bypasses the job/queue pipeline);
  per-brand coordinate + size validation, then dispatch via ``_dispatch_clean_payload``.
- ``_resolve_live_dispatch_payload`` — re-resolve segment ids to LIVE ids by slug just
  before dispatch (for brands whose segment ids renumber on re-segment).
- ``_run_global_pre_calls`` — push global device settings (fan / mop) before an atomic
  dispatch for brands that expose them only as global selects.

Extracted from core/manager.py. The manager keeps thin delegators for all four (their
production callers — ``start_selected_rooms``, ``jobs/phase_runner.py``,
``mapping/mapping_services.py``, ``services/job_control.py`` — and the tests reference
``manager.<method>`` / ``self._manager.<method>`` unchanged).
"""

from __future__ import annotations
from ..profiles.room_profiles import may_wet_floor

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as _er
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters.registry import get_adapter_config as _get_adapter_config

# Domains whose CURRENT VALUE lives in the entity STATE rather than an attribute.
# A platform fact, not a brand fact, so core decides it and no adapter declares it:
# Home Assistant's select platform publishes `options` as its only attribute and
# returns `current_option` as the state. Asking a select for an `option` ATTRIBUTE
# reads None every time, which is how a verbatim copy of the per-room suction skip
# would produce a guard that cannot fire.
_STATE_VALUED_DOMAINS = frozenset({"select"})

#: Vacuum states that mean a clean is over and the robot has settled — the moment to
#: restore the globals a zone precall changed. "returning" is NOT terminal (still moving).
_ZONE_DONE_STATES: frozenset[str] = frozenset({"docked", "idle"})
#: Vacuum states that confirm the zone clean actually STARTED (so a restore only arms
#: after motion begins, never firing on the pre-clean docked state).
_ZONE_ACTIVE_STATES: frozenset[str] = frozenset({"cleaning", "returning"})


def _values_match(actual: Any, wire: Any) -> bool:
    """Readback equality tolerant of the str/number gap — a NUMBER entity reports its value
    as ``"16"``/``"16.0"`` while the wire we set was ``16``. None (missing/unavailable) never
    matches, so a setting that did not take is caught."""
    if actual is None:
        return False
    if str(actual) == str(wire):
        return True
    try:
        return abs(float(actual) - float(wire)) < 1e-6
    except (TypeError, ValueError):
        return False

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


class DispatchManager:
    """Owns send-side wire dispatch. Constructed with the core manager (the
    bundled-subsystem pattern); uses ``manager.hass`` + the manager's map/room helpers
    (``async_get_map_data_dict``, ``map_source``) via ``self._manager``."""

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager
        # ISSUE #78/#79 — what THIS job has already pushed, per global pre-call target.
        # Key `(vacuum_entity_id, target_entity, value_key)` -> the normalised wire value
        # of a push that completed without raising. In memory only; never persisted, so a
        # restart forgets it and the next push is unconditional. Cleared per vacuum unless
        # the caller passes `reuse_pushed_values=True` (the phase runner, mid-job).
        self._pushed_pre_call_values: dict[tuple[str, str, str], str] = {}

    async def _dispatch_clean_payload(
        self,
        *,
        vacuum_entity_id: str,
        payload: dict[str, Any] | list[Any],
        command_override: str | None = None,
        params_as_list_override: bool | None = None,
    ) -> None:
        """Send one clean payload to the vacuum service using the adapter's envelope.

        Reads dispatch config for service_domain/service_name/command. Two
        envelope shapes: wrapped ``{command, params}`` (Eufy/Roborock/Ecovacs
        send_command) when a ``command`` is declared, else direct merge-into-data
        (Dreame's vacuum_clean_segment). Shared by job start and phase advance.

        ``command_override`` forces a specific send_command verb (e.g. an ad-hoc
        ``zone_clean``) in place of the adapter's default clean command; the
        domain/name and params-shaping still come from the adapter dispatch config.
        """
        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        domain = cfg.get("service_domain", "vacuum")
        name = cfg.get("service_name", "send_command")
        # RP-033/DE-3: an EXPLICIT null already mechanically produces the direct-
        # merge envelope below (dict.get only returns the "room_clean" default
        # when the key is ABSENT, not when it's declared null) — that behaviour
        # is correct and unchanged. What used to be silent: an adapter that
        # never declares 'command' at all (the legacy/back-compat shape) also
        # resolves to "room_clean" with no signal that the omission was never
        # actually decided one way or the other.
        if "command" not in cfg:
            _LOGGER.warning(
                "_dispatch_clean_payload: %s's adapter does not declare "
                "dispatch.command — defaulting to the wrapped {command, params} "
                "envelope with command='room_clean'. Declare it explicitly: a "
                "string for the wrapped envelope, or null for the direct-merge "
                "envelope, so the intended shape is never ambiguous.",
                vacuum_entity_id,
            )
        command = command_override or cfg.get("command", "room_clean")
        # Some brands wrap the params payload in a single-element list on the wire
        # (Roborock app_segment_clean: params=[{segments:[...],repeat:n}]); others
        # pass the bare dict (Eufy room_clean). Adapter-declared, default bare.
        # ``params_as_list_override`` lets a specific dispatch opt out of the adapter
        # default — e.g. app_zoned_clean's payload is ALREADY the params list
        # ([[x0,y0,x1,y1,repeat],...]) and must NOT be re-wrapped.
        _as_list = (
            params_as_list_override
            if params_as_list_override is not None
            else cfg.get("params_as_list")
        )
        params = [payload] if _as_list else payload
        if command:
            data = {"entity_id": vacuum_entity_id, "command": command, "params": params}
        else:
            data = {"entity_id": vacuum_entity_id, **payload}
        # ENFV9F37: THIS LINE MOVES A ROBOT IN SOMEONE'S HOUSE. Not a read, not
        # idempotent, not undoable by calling something else. It is the single send
        # chokepoint on purpose, so a dispatch is always visible in a diff at one place.
        await self._manager.hass.services.async_call(domain, name, data, blocking=True)

    def _live_correspondences(
        self, *, vacuum_entity_id: str, map_id: str | None,
    ) -> list[tuple[float, float, float, float]] | None:
        """The live map's ``(nx, ny, mmx, mmy)`` pairs for the normalized→device-mm affine.

        The SINGLE source both go-to and zone dispatch invert — so they cannot disagree on
        the frame. Reads the SAME ``map_state_source.map_frame_offset_mm`` the render applies
        (a bare, offset-less build would cruise/clean ~offset away on Dreame — the frame the
        card draws is the offset one). Returns ``None`` when no live map is available; the
        caller MUST then refuse to dispatch rather than send the robot to a guess.
        """
        from ..mapping import map_source_runtime as _msr

        adapter = _get_adapter_config(vacuum_entity_id) or {}
        map_obj = self._manager.map_source.get_live_mapdata_obj(
            vacuum_entity_id=vacuum_entity_id, map_id=str(map_id or ""),
        )
        if map_obj is None:
            return None
        _off = (adapter.get("map_state_source") or {}).get("map_frame_offset_mm") or (0.0, 0.0)
        return _msr.correspondences_from_mapdata(map_obj, offset=_off)

    def _state_or_none(self, entity_id: str) -> str | None:
        """The entity's state string, or None when missing / unknown / unavailable."""
        st = self._manager.hass.states.get(entity_id)
        if st is None or st.state in ("unknown", "unavailable", "none", ""):
            return None
        return st.state

    async def _dispatch_zone_with_global_precall(
        self,
        *,
        vacuum_entity_id: str,
        gp: dict[str, Any],
        settings: dict[str, str],
        zone_domain: str,
        zone_service: str,
        zone_data: dict[str, Any],
    ) -> None:
        """A zone is a GLOBAL clean. Snapshot the device's global settings + the gate switch,
        flip the gate OFF so the globals become settable, bulk-set the chosen values, READ
        THEM BACK (refuse rather than clean with unconfirmed settings), execute the bare zone,
        and restore the snapshot RIGHT AT ZONE COMPLETION — a zone never persists its settings.

        The gate is ``switch.<obj>_<gate_switch_suffix>`` (Dreame's customized-cleaning
        switch): ON makes the global selects ``unavailable``, so it is flipped OFF for the
        run and restored after. Moves the robot — same chokepoint discipline as
        ``_dispatch_clean_payload`` / ``dispatch_goto``.
        """
        hass = self._manager.hass
        obj = vacuum_entity_id.split(".", 1)[1]  # "vacuum.robin" -> "robin"
        gate_eid = f"switch.{obj}_{gp['gate_switch_suffix']}"

        # Resolve each CHOSEN setting to an apply-plan (domain/service/entity/value_field/wire).
        plan: list[dict[str, Any]] = []
        for s in (gp.get("settings") or []):
            key = s.get("key")
            val = settings.get(key) if key else None
            if val in (None, ""):
                continue
            eid = f"{s.get('domain', 'select')}.{obj}_{s['entity_suffix']}"
            plan.append({
                "key": key,
                "dom": s.get("domain", "select"),
                "svc": s.get("service", "select_option"),
                "vf": s.get("value_field", "option"),
                "eid": eid,
                "wire": (s.get("value_map") or {}).get(val, val),
            })

        # No settings chosen → nothing to pre-set: just run the bare zone (the device keeps
        # its current globals). No gate flip, no restore.
        if not plan:
            await hass.services.async_call(zone_domain, zone_service, zone_data, blocking=True)
            return

        # Snapshot BEFORE any change — the target of the restore-at-completion.
        gate_prior = self._state_or_none(gate_eid)          # "on" / "off" / None
        for p in plan:
            p["prior"] = self._state_or_none(p["eid"])      # may be None while gated

        async def _apply(dom: str, svc: str, eid: str, vf: str, value: Any) -> None:
            await hass.services.async_call(dom, svc, {"entity_id": eid, vf: value}, blocking=True)

        async def _restore() -> None:
            # Globals FIRST (while still ungated), then the gate LAST (re-gates them).
            #
            # A MISSING TARGET MUST SAY SO -- the #51 shape, restore side. Neither
            # `except` below could ever see the most likely failure on a localized or
            # renamed install, because `hass.services.async_call` does NOT raise when
            # the entity does not exist: it collects the id and logs a warning of its
            # own. [GPC-6d] proves exactly that for this same call. So the restore
            # no-opped, `except Exception` never ran, and the user's prior settings were
            # dropped in silence -- the forward path is covered by the read-back below,
            # but nothing reads back the RESTORE.
            #
            # Still best-effort: a missing target is reported and skipped, never raised.
            # Losing the restore must not also lose the run.
            for p in plan:
                if p.get("prior") is not None:
                    if hass.states.get(p["eid"]) is None:
                        _LOGGER.warning(
                            "zone restore: %s no longer exists -- %r was NOT restored, so the "
                            "device keeps the zone's %s setting",
                            p["eid"], p["prior"], p["key"],
                        )
                        continue
                    try:
                        await _apply(p["dom"], p["svc"], p["eid"], p["vf"], p["prior"])
                    except Exception:  # noqa: BLE001 - best-effort restore
                        _LOGGER.warning("zone restore: %s -> %r failed", p["eid"], p["prior"], exc_info=True)
            if gate_prior == "on":
                if hass.states.get(gate_eid) is None:
                    _LOGGER.warning(
                        "zone restore: %s no longer exists -- the settings gate was left OFF, so "
                        "the device's globals stay un-regated until it is switched back on",
                        gate_eid,
                    )
                    return
                try:
                    await hass.services.async_call("switch", "turn_on", {"entity_id": gate_eid}, blocking=True)
                except Exception:  # noqa: BLE001
                    _LOGGER.warning("zone restore: re-enabling %s failed", gate_eid, exc_info=True)

        # 1. Flip the gate OFF so the globals become settable.
        if gate_prior == "on":
            await hass.services.async_call("switch", "turn_off", {"entity_id": gate_eid}, blocking=True)

        # 2. Bulk-set the chosen globals, then 3. READ BACK — refuse (and restore) on mismatch,
        #    rather than clean with settings that did not take.
        try:
            for p in plan:
                await _apply(p["dom"], p["svc"], p["eid"], p["vf"], p["wire"])
            mismatches = [
                f"{p['key']} ({p['eid']}={self._state_or_none(p['eid'])!r}, wanted {p['wire']!r})"
                for p in plan
                if not _values_match(self._state_or_none(p["eid"]), p["wire"])
            ]
            if mismatches:
                await _restore()
                raise ValueError(
                    f"{vacuum_entity_id}: zone settings did not take — refusing to clean with "
                    f"unconfirmed settings: {'; '.join(mismatches)}"
                )
        except ValueError:
            raise
        except Exception:
            await _restore()  # any set/readback failure: put the device back before propagating
            raise

        # 4. EXECUTE the bare zone — the device uses the globals we set + verified.
        # ENFV9F37 sibling: THIS LINE MOVES A ROBOT.
        await hass.services.async_call(zone_domain, zone_service, zone_data, blocking=True)

        # 5. Arm restore-at-completion. Only after the robot ACTUALLY starts (a cleaning/
        #    returning state) does a return to docked/idle count as "done" — so the restore
        #    never fires on the pre-clean docked state. If the run never starts or HA restarts
        #    mid-clean, the device is left in global mode (a known edge, logged).
        started = {"v": False}
        holder: dict[str, Any] = {"unsub": None}

        @callback
        def _on_state(event: Any) -> None:
            new = event.data.get("new_state")
            st = new.state if new is not None else None
            if st in _ZONE_ACTIVE_STATES:
                started["v"] = True
                return
            # THE TWO ARCS LEFT UNCOVERED IN THIS MODULE, classified 2026-11-07 rather than
            # chased, and both are IDEMPOTENCY on a state callback:
            #
            #   314->exit   `_on_state` running for a state that is neither active nor
            #               done-after-started -- a `paused` tick mid-zone, say. Reachable, and
            #               the guard is just "do nothing yet"; a test would assert that nothing
            #               happened, which every other assertion in the zone suite already
            #               implies on every tick that is not the completion.
            #   315->318    the done state arriving while `unsub` is ALREADY None. Not reachable
            #               through `async_track_state_change_event`: the unsub removes the
            #               listener, so the callback cannot fire again. It protects against a
            #               RE-ENTRANT invocation, which this subscription does not produce --
            #               defensive, and the cheap half of not scheduling two restores.
            #
            # Both are kept. Neither is worth a test that would pass for a reason other than
            # the one it names -- which is exactly what happened to two tests written for the
            # slug/id guards above (see that comment).
            if started["v"] and st in _ZONE_DONE_STATES:
                if holder["unsub"] is not None:
                    holder["unsub"]()
                    holder["unsub"] = None
                hass.async_create_task(_restore())

        holder["unsub"] = async_track_state_change_event(hass, [vacuum_entity_id], _on_state)

    @staticmethod
    def _check_zone_bounds(
        *,
        vacuum_entity_id: str,
        side_x_m: float,
        side_y_m: float,
        min_side: float | None,
        max_side: float | None,
        min_area: float | None,
        max_area: float | None,
    ) -> None:
        # anchor: IN76GE4W  limits resolve ABOVE the branch; enforced by declaration, not path
        """Check one zone's side + area bounds. Shared by BOTH coordinate branches
        (RP-022/RF-23) so a declared bound is enforced regardless of which branch
        the adapter takes — previously area bounds only existed inside the
        device_mm branch and side bounds only inside the else branch, so a bound
        declared on the "wrong" branch for a brand was silently never checked."""
        area_m2 = side_x_m * side_y_m
        for _side in (side_x_m, side_y_m):
            if min_side is not None and _side < float(min_side):
                raise ValueError(
                    f"{vacuum_entity_id}: a zone side is too short "
                    f"({_side:.2f} m) — the minimum is {float(min_side):.2f} m; "
                    "draw a bigger box"
                )
            if max_side is not None and _side > float(max_side):
                raise ValueError(
                    f"{vacuum_entity_id}: a zone side is too long "
                    f"({_side:.2f} m) — the maximum is {float(max_side):.2f} m; "
                    "draw a smaller box"
                )
        if min_area is not None and area_m2 < float(min_area):
            raise ValueError(
                f"{vacuum_entity_id}: a zone is too small ({area_m2:.2f} m²) — the "
                f"minimum is {float(min_area):.2f} m² (~1 ft²); draw a bigger box"
            )
        if max_area is not None and area_m2 > float(max_area):
            raise ValueError(
                f"{vacuum_entity_id}: a zone is too large ({area_m2:.2f} m²) — the "
                f"maximum is {float(max_area):.2f} m² (~32.8 ft²); draw a smaller box"
            )

    async def dispatch_zone_clean(
        self,
        *,
        vacuum_entity_id: str,
        zones: list[list[float]],
        clean_times: int = 1,
        map_id: str | None = None,
        settings: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Dispatch an ad-hoc free-form zone clean (fire-and-forget).

        ``zones`` is a list of normalized rectangles ``[x0, y0, x1, y1]`` (fractions
        0-1 of the live-map image, top-left origin); the provider converts them to
        the device world frame on its side. Unlike room cleans this carries no room
        ids, so it deliberately BYPASSES the job/queue/learning pipeline — there is
        nothing to track or roll over per-room. The send verb comes from the
        adapter's ``dispatch.zone_command`` (only declared by brands whose provider
        accepts a zone clean, and gated in the UI by ``supports_zone_clean``).

        ``map_id`` is accepted because the service layer auto-resolves it, but it is
        intentionally NOT sent: the provider uses its own currently-loaded map (the
        same map the live image was drawn on), which avoids a stale-id mismatch.
        """
        if not zones:
            raise ValueError("zone clean requires at least one zone rectangle")
        # Defense-in-depth: reject malformed / near-zero-area rectangles before they
        # reach the device (the card's converter is otherwise the only validator).
        _MIN_SIDE = 0.01
        for _z in zones:
            if not isinstance(_z, (list, tuple)) or len(_z) != 4:
                raise ValueError(f"zone must be [x0, y0, x1, y1], got {_z!r}")
            _x0, _y0, _x1, _y1 = _z
            if abs(_x1 - _x0) < _MIN_SIDE or abs(_y1 - _y0) < _MIN_SIDE:
                raise ValueError(f"zone {_z!r} is degenerate (near-zero area)")
        adapter = _get_adapter_config(vacuum_entity_id) or {}
        cfg = adapter.get("dispatch", {})
        # Two zone-dispatch shapes: a send_command VERB shared with room-clean
        # (`dispatch.zone_command` — Roborock/Eufy), or a DEDICATED service block like
        # `goto` (`zone.service_name` — Dreame, whose vacuum_clean_zone is its own service).
        zone_svc = adapter.get("zone") or {}
        zone_command = cfg.get("zone_command")
        _dedicated = bool(zone_svc.get("service_name"))
        if not zone_command and not _dedicated:
            raise ValueError(
                f"{vacuum_entity_id}: this vacuum's adapter declares no zone service "
                "(zone cleaning is not supported for this brand/provider)"
            )
        # ZONE-2: only the card previously consulted supports_zone_clean -- a direct
        # service call or automation reached the device even when the brand declares
        # it unsupported. Checked here so every call path is covered.
        _zone_caps = adapter.get("capabilities", {})
        if _zone_caps.get("supports_zone_clean") is False:
            raise ValueError(
                f"{vacuum_entity_id}: this vacuum's adapter declares zone cleaning "
                "unsupported (supports_zone_clean: false)"
            )
        # Device limits (from capabilities): a per-clean zone COUNT cap (defence-in-depth —
        # the card also caps the draw) plus per-zone SIZE bounds checked after the device-mm
        # conversion below. Absent => unconstrained for that brand.
        _zone_max = _zone_caps.get("zone_max")
        if _zone_max is not None and len(zones) > int(_zone_max):
            raise ValueError(
                f"{vacuum_entity_id}: too many zones ({len(zones)}) — this vacuum allows at "
                f"most {int(_zone_max)} per clean"
            )
        # Bound resolution HOISTED above the coordinate-space branch (RF-23 item 2):
        # both area and side bounds are read once here and enforced on WHICHEVER
        # branch actually runs, instead of area-only-on-device_mm / side-only-on-else.
        _min_a = _zone_caps.get("zone_min_area_m2")
        _max_a = _zone_caps.get("zone_max_area_m2")
        _min_side = _zone_caps.get("zone_min_side_m")
        _max_side = _zone_caps.get("zone_max_side_m")
        # Coordinate frame: most providers de-normalize on their side, so we ship the
        # 0-1 image rects verbatim (Eufy's fork zone_clean). Brands whose command wants
        # WORLD millimetres (Roborock app_zoned_clean) declare ``zone_coords: device_mm``;
        # we convert here via the live map's own projection and REFUSE rather than
        # dispatch if the conversion can't be validated (a wrong inverse cleans the
        # wrong area — see dispatch/zone_dispatch.py).
        if (zone_svc.get("zone_coords") or cfg.get("zone_coords")) == "device_mm":
            from . import zone_dispatch as _zd

            # Single-source, offset-aware correspondences — the SAME frame go-to inverts, so
            # a drawn box lands where the card drew it (a bare build omits map_frame_offset_mm
            # and cleans ~offset away on Dreame).
            corr = self._live_correspondences(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id,
            )
            if corr is None:
                raise ValueError(
                    f"{vacuum_entity_id}: no live map available to convert the zone to "
                    "device coordinates — open the robot's map and try again"
                )
            mm_rects = _zd.normalized_rects_to_mm(corr, zones)
            if mm_rects is None:
                raise ValueError(
                    f"{vacuum_entity_id}: could not place the drawn zone on the device "
                    "coordinate frame (map projection failed validation) — refusing to "
                    "dispatch rather than risk cleaning the wrong area"
                )
            for _x0, _y0, _x1, _y1 in mm_rects:
                self._check_zone_bounds(
                    vacuum_entity_id=vacuum_entity_id,
                    side_x_m=abs(_x1 - _x0) / 1000.0,
                    side_y_m=abs(_y1 - _y0) / 1000.0,
                    min_side=_min_side, max_side=_max_side,
                    min_area=_min_a, max_area=_max_a,
                )
            if _dedicated:
                # Dreame vacuum_clean_zone — its OWN service. `zone` = [[x0,y0,x1,y1], ...]
                # (4-tuple int mm, NOT Roborock's 5-tuple); `repeats` = one int for every zone.
                _repeat_max = int(zone_svc.get("zone_passes_max", 1) or 1)
                repeat = max(1, min(int(clean_times), _repeat_max))
                zone_data = {
                    "entity_id": vacuum_entity_id,
                    zone_svc.get("zone_field", "zone"): [
                        [int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))]
                        for (x0, y0, x1, y1) in mm_rects
                    ],
                    zone_svc.get("repeats_field", "repeats"): repeat,
                }
                _gp = zone_svc.get("global_precall")
                if _gp:
                    # A zone is a GLOBAL clean: pre-set + READBACK-VERIFY the device's global
                    # settings (ungating them via the customized-cleaning switch), execute the
                    # bare zone, and restore the prior state at zone COMPLETION. One method.
                    await self._dispatch_zone_with_global_precall(
                        vacuum_entity_id=vacuum_entity_id, gp=_gp, settings=settings or {},
                        zone_domain=zone_svc["service_domain"],
                        zone_service=zone_svc["service_name"], zone_data=zone_data,
                    )
                else:
                    # ENFV9F37 sibling: THIS LINE MOVES A ROBOT — the dedicated zone chokepoint.
                    await self._manager.hass.services.async_call(
                        zone_svc["service_domain"], zone_svc["service_name"],
                        zone_data, blocking=True,
                    )
            else:
                # Roborock app_zoned_clean: the params ARE the 5-tuple zone list (repeat baked
                # per-zone). Cap from dispatch.zone_passes_max/passes_max (default 3; RRK 1-3).
                _zone_repeat_max = int(cfg.get("zone_passes_max", cfg.get("passes_max", 3)) or 3)
                repeat = max(1, min(int(clean_times), _zone_repeat_max))
                payload: dict[str, Any] | list[Any] = [
                    [int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)), repeat]
                    for (x0, y0, x1, y1) in mm_rects
                ]
                await self._dispatch_clean_payload(
                    vacuum_entity_id=vacuum_entity_id,
                    payload=payload,
                    command_override=zone_command,
                    params_as_list_override=False,  # payload is already the params list
                )
        else:
            # Eufy ships the 0-1 image rects VERBATIM (the fork de-normalizes on its side).
            # Any declared bound (area OR side) requires the live map's own dims to convert
            # each rect to metres — the SAME de-normalization the fork applies:
            # side_m = Δnorm * dim * res / 100 (matches
            # coordinator.normalized_rects_to_quads_cm). ZONE-4: unreadable dims now REFUSE
            # (parity with the device_mm branch's own refusal for "can't validate the
            # geometry") instead of silently skipping the check. No bound declared at all
            # → no live map needed, matching the card's own draw-time-only validation.
            if _min_side is not None or _max_side is not None or _min_a is not None or _max_a is not None:
                try:
                    _md = await self._manager.async_get_map_data_dict(
                        vacuum_entity_id=vacuum_entity_id,
                    ) or {}
                    _w = int(_md.get("width") or 0)
                    _h = int(_md.get("height") or 0)
                    _res = int(_md.get("resolution") or 5) or 5
                except (TypeError, ValueError):
                    _w = _h = 0
                    _res = 5
                if not _w or not _h:
                    raise ValueError(
                        f"{vacuum_entity_id}: no live map available to validate the zone's "
                        "declared size bounds — open the robot's map and try again"
                    )
                for _x0, _y0, _x1, _y1 in zones:
                    self._check_zone_bounds(
                        vacuum_entity_id=vacuum_entity_id,
                        side_x_m=abs(_x1 - _x0) * _w * _res / 100.0,
                        side_y_m=abs(_y1 - _y0) * _h * _res / 100.0,
                        min_side=_min_side, max_side=_max_side,
                        min_area=_min_a, max_area=_max_a,
                    )
            # Q12 (RF-23): a brand can declare zone repeats unsupported outright
            # (supports_zone_repeat: false, e.g. Eufy) -- normalize to 1 with a
            # warning instead of shipping the requested count verbatim (this
            # branch previously had no clamp at all). No repeat cap declared at
            # all defaults to unsupported here too (this branch's default was
            # "ships verbatim", never a safe cap to fall back to like the
            # device_mm branch's historical 3) -- an adapter that DOES support
            # repeats on this branch declares zone_passes_max/passes_max.
            _zone_repeat_cap = cfg.get("zone_passes_max", cfg.get("passes_max"))
            if _zone_caps.get("supports_zone_repeat") is False or _zone_repeat_cap is None:
                if int(clean_times) > 1:
                    _LOGGER.warning(
                        "%s: zone repeats are not supported by this adapter — "
                        "clean_times=%s requested, normalized to 1",
                        vacuum_entity_id, clean_times,
                    )
                repeat = 1
            else:
                repeat = max(1, min(int(clean_times), int(_zone_repeat_cap)))
            payload = {"zones": zones, "clean_times": repeat}
            await self._dispatch_clean_payload(
                vacuum_entity_id=vacuum_entity_id,
                payload=payload,
                command_override=zone_command,
            )
        return {
            "status": "dispatched",
            "vacuum_entity_id": vacuum_entity_id,
            "zone_count": len(zones),
            "clean_times": repeat,
        }

    async def dispatch_goto(
        self,
        *,
        vacuum_entity_id: str,
        point: list[float],
        map_id: str | None = None,
    ) -> dict[str, Any]:
        """Send the robot to a single POINT (fire-and-forget navigation — NOT a clean, so it
        BYPASSES the job/queue/learning pipeline: nothing to track or roll over).

        ``point`` is a normalized ``[nx, ny]`` (0..1 of the live-map image, top-left origin) —
        the SAME frame the card renders and the user taps. Converted to device-mm via the live
        map's own affine (offset-aware, so it matches the render alignment) and dispatched to
        the adapter's ``goto`` service (declared only by brands whose provider accepts go-to,
        gated by ``supports_path_control``). REFUSES rather than dispatch when the map is absent
        or the affine can't be validated — a wrong inverse drives the robot to the WRONG place.

        ``map_id`` is accepted (the service layer auto-resolves it) but NOT sent: the provider
        cruises on its own currently-loaded map, the one the live image was drawn on.
        """
        adapter = _get_adapter_config(vacuum_entity_id) or {}
        goto = adapter.get("goto") or {}
        name = goto.get("service_name")
        if not name:
            raise ValueError(
                f"{vacuum_entity_id}: this vacuum's adapter declares no goto service "
                "(go-to is not supported for this brand/provider)"
            )
        if (adapter.get("capabilities") or {}).get("supports_path_control") is False:
            raise ValueError(
                f"{vacuum_entity_id}: this vacuum declares path control (go-to) unsupported "
                "(supports_path_control: false)"
            )
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"go-to needs a [nx, ny] point, got {point!r}")
        from . import zone_dispatch as _zd

        corr = self._live_correspondences(vacuum_entity_id=vacuum_entity_id, map_id=map_id)
        if corr is None:
            raise ValueError(
                f"{vacuum_entity_id}: no live map available to place the go-to point on the "
                "device coordinate frame — open the robot's map and try again"
            )
        mm = _zd.normalized_point_to_mm(corr, point)
        if mm is None:
            raise ValueError(
                f"{vacuum_entity_id}: could not place the go-to point on the device coordinate "
                "frame (map projection failed validation) — refusing to dispatch rather than "
                "sending the robot to the wrong place"
            )
        x, y = int(round(mm[0])), int(round(mm[1]))
        domain = goto.get("service_domain", "vacuum")
        xf = goto.get("x_field", "x")
        yf = goto.get("y_field", "y")
        data = {"entity_id": vacuum_entity_id, xf: x, yf: y}
        # ENFV9F37 sibling: THIS LINE MOVES A ROBOT — a single, non-idempotent send, kept at
        # one visible chokepoint exactly like _dispatch_clean_payload.
        await self._manager.hass.services.async_call(domain, name, data, blocking=True)
        return {"status": "dispatched", "vacuum_entity_id": vacuum_entity_id, "point_mm": [x, y]}

    async def _resolve_live_dispatch_payload(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        payload: dict[str, Any],
        resolved_rooms: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Re-resolve segment ids to LIVE ids by slug just before dispatch.

        For brands whose segment ids renumber on re-segment
        (``dispatch.resolve_live_ids_by_slug``), the stored id can be stale and
        clean the WRONG room after a map edit. This re-fetches the room source (a
        fresh get_maps), maps each target room's slug -> current id, and rewrites
        the wire id list — so the correct room is always cleaned regardless of
        whether the user has confirmed the identity-reconciliation review. NEVER
        mutates stored data; the review owns attribution, this owns cleaning
        correctness (the two are deliberately decoupled).

        Falls back to the stored-id payload when the live source is unavailable
        (refresh failed / empty) so an explicit user start still dispatches. A
        target whose slug is absent from the current map is skipped (it can't be
        targeted) rather than cleaned under a stale id.
        """
        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        if not cfg.get("resolve_live_ids_by_slug"):
            return payload
        rooms_field = cfg.get("rooms_field", "segments")
        if rooms_field not in payload:
            return payload

        from ..rooms.source_refresh import (
            REFRESH_TTL_SECONDS,
            async_refresh_room_source,
            get_cached_room_source_with_age,
        )
        from ..rooms.room_discovery import discover_rooms_for_vacuum

        refresh_result = await async_refresh_room_source(
            self._manager.hass, vacuum_entity_id
        )

        # RP-007 step 7 (GATE4 Q16 variant a): dispatch REQUIRES freshness. When
        # the live refresh failed AND the cache is older than the TTL (or has no
        # freshness stamp at all), the ids we would resolve against may describe a
        # map that no longer exists — refuse rather than guess. This includes the
        # asleep/unreachable-Roborock cold boot: NO stored-id fallback, NO
        # dispatch-to-wake. Once a live refresh succeeds, dispatch proceeds
        # normally.
        _, cache_age_s = get_cached_room_source_with_age(
            self._manager.hass, vacuum_entity_id
        )
        cache_fresh = cache_age_s is not None and cache_age_s <= REFRESH_TTL_SECONDS
        if not refresh_result.get("ok") and not cache_fresh:
            raise HomeAssistantError(
                "the robot's live room data is unavailable — wake the robot (or "
                "wait for the Roborock integration to reconnect), then try again"
            )

        live_rooms = discover_rooms_for_vacuum(
            self._manager.hass, vacuum_entity_id=vacuum_entity_id, map_id=str(map_id)
        )
        # DEFENSIVE, AND MEASURED AS SUCH ON 2026-11-07 -- the two guards in this loop
        # are the only statements in this module coverage cannot reach, and they are
        # double-guards over a contract `rooms/room_discovery.py` already enforces:
        #
        #   room_id   coerced with `int(raw_id)` under its own except/continue, so every
        #             row arrives with an int and the key present (room_discovery.py:563)
        #   slug      a row whose name is blank, or whose name slugifies to empty, is
        #             SKIPPED rather than admitted (room_discovery.py:573, :577)
        #   unique    a disambiguation pass suffixes any colliding slug with
        #             `_r{room_id}` until the set is unique (room_discovery.py:644)
        #
        # KEPT ANYWAY, because this function rewrites the wire payload moments before
        # dispatch and its failure mode is a plausible segment list, not an exception --
        # a KeyError here would clean the wrong room. They are the cheap half of a
        # boundary between two modules, not padding.
        #
        # DO NOT WRITE TESTS FOR THEM through this call site: two were written, both
        # PASSED, and both were deleted. The producer's own guarantees meant the
        # assertions held for a different reason than the one they named, and coverage
        # is what exposed it -- these lines stayed missed while the tests went green.
        # Reaching them needs a fabricated producer, which tests the fake.
        slug_to_live_id: dict[str, int] = {}
        for room in live_rooms:
            slug = str(room.get("slug") or "").strip().lower()
            if not slug or slug in slug_to_live_id:
                continue
            try:
                slug_to_live_id[slug] = int(room["room_id"])
            except (TypeError, ValueError, KeyError):
                continue

        new_segments: list[int] = []
        dropped: list[str] = []
        for room in resolved_rooms:
            slug = str(room.get("slug") or "").strip().lower()
            live_id = slug_to_live_id.get(slug)
            if live_id is not None:
                new_segments.append(live_id)
            else:
                dropped.append(slug or str(room.get("room_id")))

        if dropped:
            _LOGGER.warning(
                "dispatch: %d target room(s) not on the current map for %s, skipped: %s",
                len(dropped), vacuum_entity_id, dropped,
            )
        if not new_segments:
            # anchor: INJBNQ2Q  dispatch sends only ids resolved against a LIVE source;
            # a partial miss skips rooms, a TOTAL miss refuses -- they are not the same
            # RP-007 step 5 (DQ-ACT-1/DQ-DE-1): a TOTAL live-resolution miss used
            # to fall back to the STALE stored ids — after a re-segment those
            # numbers belong to whatever rooms the vendor renumbered, and the
            # wrong rooms got cleaned while the log said "dispatching stored ids".
            # Partial-miss skip behaviour (above) is unchanged.
            raise HomeAssistantError(
                "no target rooms resolved on the current map — the map may have "
                "been re-segmented; re-import rooms"
            )
        return {**payload, rooms_field: new_segments}

    def _reported_pre_call_value(
        self,
        *,
        target_entity: str,
        domain: str | None,
        service: dict[str, Any],
        value_key: str,
    ) -> str | None:
        """Return the target's currently reported value, normalised, or ``None``.

        ``None`` means NOTHING USABLE TO COMPARE AGAINST — a missing entity, an
        ``unavailable``/``unknown`` one, an absent attribute, or a blank reading.
        Callers must read it as "no information", never as agreement.

        WHERE THE VALUE LIVES IS A PLATFORM FACT, decided here by service domain
        (``_STATE_VALUED_DOMAINS``) rather than declared per adapter; an entry may
        still name a ``state_attribute`` explicitly to override.

        NORMALISED ON BOTH SIDES, deliberately. ``rank`` is lowercased when it is
        read above, while a select's own option tokens keep their case, and the
        off-fallback sends the select's own capitalisation back on purpose
        (DQ-ACT-7). A case-sensitive comparison would therefore be live on a
        lowercase-option device and DEAD on a capitalised one — install-dependent
        silence, which is the same defect DQ-ACT-7 exists to prevent.
        """
        state = self._manager.hass.states.get(target_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        state_attribute = service.get("state_attribute")
        if state_attribute:
            raw = state.attributes.get(state_attribute)
        elif domain in _STATE_VALUED_DOMAINS:
            raw = state.state
        else:
            raw = state.attributes.get(value_key)
        if raw is None:
            return None
        return str(raw).strip().casefold() or None

    async def _run_global_pre_calls(
        self,
        *,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
        reuse_pushed_values: bool = False,
    ) -> None:
        """Push global device settings (fan/mop) before an atomic dispatch.

        Some brands expose fan/water only as GLOBAL device settings, not per-room
        payload fields (Roborock ``app_segment_clean`` carries passes only). For
        each adapter-declared ``dispatch.global_pre_calls`` entry, pick the run
        value from the selected rooms' canonical field by the entry's ``rank``
        (max-wins: the strongest request applies to the whole run, mirroring the
        batch-passes max rule), map it to the wire value, and call the entry's
        service. Rooms whose value isn't in the rank are ignored; if NONE rank,
        the setting is left as the device currently has it (the run still
        proceeds). Best-effort — a failed pre-call is logged, never aborts the run.

        MIXED-BATCH SAFETY (``mixed_mode_water_policy: "safest"`` entries only): a
        device-GLOBAL water/mop-intensity select can't be zeroed per-room, so a
        mixed mop + vacuum-only batch that max-wins to the strongest water would
        WET-MOP the dry (vacuum-only) rooms. For a mixed batch (>=1 mop room AND >=1
        vacuum-only room) this entry picks the SAFEST (lowest-rank) water instead, so
        a dry room is never wet-mopped (under-mop is accepted over wet-mop). A single-
        mode batch (all-mop OR all-vacuum) keeps max-wins. "Mop room" = ``"mop"`` in
        its ``clean_mode``; this only fires on entries that opt in (the fan_speed entry
        never carries the marker, so suction stays max-wins).

        OFF FALLBACK: if the chosen canonical is ``off`` but the target select exposes no
        ``off`` option, the value is lowered to the select's MINIMUM available option
        rather than silently leaving the prior (possibly HIGH) value on the device.

        Entry shape (fan_speed is used here as a SHAPE example only — no shipped brand
        declares a fan pre-call; both shipped brands use this for WATER, and Roborock
        drives fan through ``per_room_live_settings``. Kept as the example because the
        rank list reads clearly, but do not infer a live fan pre-call from it)::

            {"field": "fan_speed",
             "rank": ["gentle","quiet","balanced","turbo","max"],  # ascending
             "service": {"domain": "vacuum", "service": "set_fan_speed",
                         "value_key": "fan_speed",
                         "target_entity_id": <full id>},   # default: the vacuum
             "value_map": {canonical: wire, ...},           # optional, identity if absent
             "mixed_mode_water_policy": "safest"}           # optional; mixed-batch safe-water
        """
        if not reuse_pushed_values:
            # A NEW JOB knows nothing about what the device is holding: the previous job
            # ended an unknown time ago and the vendor app may have moved the setting
            # since. Forget this vacuum's pushes so the FIRST push of every job is
            # unconditional. Default-off is the fail-safe polarity — a caller that
            # forgets the flag keeps today's behaviour instead of inheriting a stale
            # permission to skip.
            self._pushed_pre_call_values = {
                key: val
                for key, val in self._pushed_pre_call_values.items()
                if key[0] != vacuum_entity_id
            }

        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        for entry in cfg.get("global_pre_calls") or []:
            field = entry.get("field")
            rank = [str(v).strip().lower() for v in (entry.get("rank") or [])]
            service = entry.get("service") or {}
            domain = service.get("domain")
            service_name = service.get("service")
            value_key = service.get("value_key")
            if not (field and rank and domain and service_name and value_key):
                continue

            # A mixed mop + vacuum-only batch flips this entry to the SAFEST water so a dry
            # room isn't wet-mopped by the device-global select. Only entries that opt in
            # (mixed_mode_water_policy=="safest") + an actually mixed batch (>=1 mop room AND
            # >=1 vacuum-only room). "Mop room" = "mop" in its clean_mode. The presence of a
            # dry room IS the signal, so we target the rank's LOWEST value (off) directly —
            # not merely the min of the DECLARED water levels, which a vacuum-only room that
            # carries no water_level field wouldn't lower. Under-mop is accepted over wet-mop.
            _mop_rooms = sum(
                1 for r in resolved_rooms
                if may_wet_floor(r.get("clean_mode"))
            )
            # ANY DRY ROOM, not merely a MIXED batch (issue #51).
            #
            # This read `0 < _mop_rooms < len(resolved_rooms)`, so a batch with NO mop
            # rooms at all — the plainest possible "vacuum only" request — fell straight
            # through to max-wins. And max-wins finds a water level there, because
            # `resolved_rooms` is the framework's INTERNAL record and carries
            # `water_level` unconditionally; it is the WIRE payload that omits it for a
            # dry room (`queue_engine`: `if supports_water and is_mop`). So a single
            # room set to vacuum-only still had its stored water level pushed to the
            # device-global mop select, and the robot mopped. Reported on a Qrevo Curv:
            # "I set up one room for vacuum only ... and it ran it as normal with mopping."
            #
            # The mixed case was reasoned about carefully and the all-dry case sits one
            # step outside the window it closed. A dry room is the signal either way, and
            # zero mop rooms is more certain, not less.
            _any_dry_room = _mop_rooms < len(resolved_rooms)
            _use_safest = (
                str(entry.get("mixed_mode_water_policy") or "").strip().lower() == "safest"
                and bool(resolved_rooms)
                and _any_dry_room
            )

            if _use_safest:
                # Only push a safe water if SOMETHING in the batch was rankable at all
                # (mirrors the max-wins "nothing rankable -> leave untouched" contract); a
                # mixed batch always has rankable mop rooms, so this normally targets rank[0].
                # An ALL-DRY batch reaches here too now, and passes for the same reason the
                # bug existed: `resolved_rooms` keeps `water_level` on a vacuum-only room.
                # A room carrying no rankable value at all still leaves the device alone,
                # which is the honest answer — we were told nothing about water.
                _any_rankable = any(
                    str(room.get(field) or "").strip().lower() in rank
                    for room in resolved_rooms
                )
                if not _any_rankable:
                    continue
                best_index = 0  # the safest (lowest) rung, e.g. "off"
            else:
                best_index = -1
                for room in resolved_rooms:
                    value = str(room.get(field) or "").strip().lower()
                    if value in rank:
                        best_index = max(best_index, rank.index(value))
                if best_index < 0:
                    continue  # nothing rankable -> leave the global setting untouched

            canonical_value = rank[best_index]
            # OFF fallback: chosen "off" but the target select has no "off" option ->
            # lower to the select's minimum available option (never leave a prior HIGH).
            _off_fallback_wire_value: str | None = None
            if canonical_value == "off":
                target_entity_for_opts = service.get("target_entity_id") or vacuum_entity_id
                _sel_state = self._manager.hass.states.get(target_entity_for_opts)
                _opts_raw = (
                    list(_sel_state.attributes.get("options") or [])
                    if _sel_state is not None else []
                )
                _opts = [str(o).strip().lower() for o in _opts_raw]
                if _opts and "off" not in _opts:
                    # Walk the entry's rank ascending for the first option the select has.
                    for _cand in rank:
                        if _cand in _opts:
                            canonical_value = _cand
                            # DQ-ACT-7: send the select's own reported option
                            # string (original case/format) -- _opts is
                            # lowercased only for the membership test above, so
                            # a capitalized or numeric-option select would
                            # otherwise be sent the lowercased rank word and
                            # silently no-op.
                            _off_fallback_wire_value = _opts_raw[_opts.index(_cand)]
                            break
            value_map = entry.get("value_map") or {}
            wire_value = (
                _off_fallback_wire_value
                if _off_fallback_wire_value is not None
                else value_map.get(canonical_value, canonical_value)
            )

            # RESOLVE BY ROLE when the entry names one. An id frozen into the adapter
            # config is the PRE-RESCUE guess — these blocks are built before
            # `resolve_declared_entities` runs — so on a localized or renamed install
            # it names an entity that does not exist. The role is read from the
            # RESOLVED entities map at call time.
            _role = entry.get("service", {}).get("target_role")
            _by_role = (
                (_get_adapter_config(vacuum_entity_id) or {}).get("entities", {}).get(_role)
                if _role else None
            )
            target_entity = (
                _by_role or service.get("target_entity_id") or vacuum_entity_id
            )

            # A MISSING TARGET MUST REFUSE, NOT WARN (issue #51).
            #
            # The abort below could never fire. Home Assistant does NOT raise when a
            # service call names an entity that does not exist: it collects the
            # missing ids and calls log_missing(), a WARNING. So the call no-opped,
            # `except Exception` never ran, the safety abort never happened, and the
            # run proceeded with whatever water the vendor app had last set — the
            # exact wet-mop this guard exists to prevent, with no error anywhere.
            #
            # Checking existence FIRST turns that silence into the same refusal a
            # genuine failure gets. Best-effort entries (fan, single-mode water) keep
            # degrading quietly, as before, but say so at WARNING rather than nothing.
            if self._manager.hass.states.get(target_entity) is None:
                # DISABLED AND ABSENT NEED DIFFERENT ADVICE, and only the user can act
                # on either. "does not exist" is true of a disabled entity and useless
                # to the person who disabled it — they are looking for a missing entity
                # that is right there, switched off, exactly where they left it. #67's
                # reporter spent an upgrade cycle on the wrong half of this sentence.
                #
                # Registry-only, no state machine read: a disabled entity has no state,
                # which is why we are in this branch at all.
                _disabled_by = None
                try:
                    _entry = _er.async_get(self._manager.hass).async_get(target_entity)
                    _disabled_by = getattr(_entry, "disabled_by", None) if _entry else None
                except Exception:  # pragma: no cover - defensive; never mask the abort
                    _disabled_by = None

                if _disabled_by is not None:
                    _msg = (
                        f"{vacuum_entity_id}: global pre-call target {target_entity!r} "
                        f"is DISABLED"
                        + (f" (role {_role!r}, disabled by {_disabled_by})" if _role
                           else f" (disabled by {_disabled_by})")
                        + " — a disabled entity cannot receive the call, so the "
                        "device's global setting cannot be applied. Re-enable it in "
                        "Settings > Devices & Services, or set this on the device's "
                        "own app and avoid mixing mop and vacuum-only rooms in one run"
                    )
                else:
                    _msg = (
                        f"{vacuum_entity_id}: global pre-call target {target_entity!r} "
                        f"does not exist"
                        + (f" (role {_role!r})" if _role else "")
                        + " — the device's global setting cannot be applied"
                    )
                if _use_safest:
                    raise HomeAssistantError(
                        f"could not apply the safe water setting before a run with "
                        f"vacuum-only rooms: {_msg}; dispatch aborted to avoid "
                        f"wet-mopping dry rooms"
                    )
                _LOGGER.warning("%s; leaving it as the device has it", _msg)
                continue

            # ISSUE #78/#79 — DON'T RE-SEND WHAT WE OURSELVES ALREADY SENT THIS JOB.
            #
            # This runs once at job start AND once per phase, so a strict-order run
            # re-sent an identical value at every room start. A robot that
            # acknowledges the write chimes each time, which is how it was reported.
            #
            # THE EVIDENCE IS OUR OWN PUSH, NOT THE REPORTED STATE, and that is the
            # whole design. The per-room suction skip (jobs/active_job.py, same issue)
            # trusts the reported value and states the cost of being wrong there: a
            # redundant call. Here the cost of being wrong is a WET MOP on a floor the
            # user set to vacuum-only — the harm #51 closed — and the asymmetry is
            # stated at adapters/roborock/adapter.py: over-watering a dry room is
            # damage, over-scrubbing only costs time. The reported value cannot carry
            # that weight. HA's Roborock mop-intensity select registers no push
            # listener (unlike its vacuum), so its state moves only on a coordinator
            # poll — 15-60s, and longer while a failing refresh is being suppressed,
            # during which it still reports as available. `off` is the modal reading
            # precisely because we put it there, so a vendor-app change inside that
            # window reads as agreement and would suppress the one call protecting the
            # dry floor.
            #
            # Our own push does carry it: the call below is blocking, and the Roborock
            # entity refreshes its coordinator at the end of every send, so a value we
            # placed that did not raise is known to be on the device. Hence: skip only
            # a value THIS job already pushed to THIS target, and let a reading that
            # DISAGREES veto even that, so an external change the poll has since caught
            # re-arms the push. A reading that is merely ABSENT (missing, unavailable,
            # unknown, blank) is no information: it cannot veto, and on its own it can
            # never create a skip.
            #
            # THE FIRST PUSH OF EVERY JOB IS THEREFORE UNCONDITIONAL — including when
            # the device already reports the value. That is the chime a non-phased run
            # produces, and it stays: it is the one push whose redundancy cannot be
            # established without trusting a reading that may be stale.
            #
            # PLACED AFTER THE EXISTENCE/DISABLED REFUSAL ABOVE, ON PURPOSE. #51's
            # guarantee is that an unapplied safe-water push ABORTS rather than passing
            # silently, and a skip reached before that check would re-open it. A skip is
            # not a failure and must never abort: it never enters the `try`, so neither
            # abort path below can see it.
            _pushed_key = (vacuum_entity_id, target_entity, value_key)
            _wire_norm = str(wire_value).strip().casefold()
            _reported = self._reported_pre_call_value(
                target_entity=target_entity,
                domain=domain,
                service=service,
                value_key=value_key,
            )
            if (
                self._pushed_pre_call_values.get(_pushed_key) == _wire_norm
                and not (_reported is not None and _reported != _wire_norm)
            ):
                _LOGGER.debug(
                    "global pre-call %s.%s skipped for %s: this job already pushed "
                    "%r and the target reports %r",
                    domain, service_name, target_entity, wire_value, _reported,
                )
                continue

            try:
                await self._manager.hass.services.async_call(
                    domain,
                    service_name,
                    {"entity_id": target_entity, value_key: wire_value},
                    blocking=True,
                )
            except Exception as err:
                # RP-007 step 8 (DQ-ACT-5): the mixed-batch SAFEST-water push is
                # SAFETY-critical — if it fails, the device keeps its previous
                # (possibly high) water and the dispatch would wet-mop the dry
                # rooms it exists to protect. Abort the dispatch. Plain max-wins
                # pre-calls (fan, single-mode water) stay best-effort.
                if _use_safest:
                    raise HomeAssistantError(
                        f"could not apply the safe water setting before a mixed "
                        f"mop+vacuum run ({domain}.{service_name} failed: {err}); "
                        f"dispatch aborted to avoid wet-mopping dry rooms"
                    ) from err
                _LOGGER.exception(
                    "global pre-call %s.%s failed for %s",
                    domain, service_name, vacuum_entity_id,
                )
            else:
                # RECORDED ONLY ON A PUSH THAT LANDED. Written in the `else`, so a call
                # that raised leaves no evidence and the next phase pushes again — a
                # failed push must never read as a value the device holds. The log is
                # TWO-SIDED from here on: a skip logs, and a send logs. One-sided, an
                # empty debug log reads the same for "nothing happened" and "everything
                # sent", which is what made the first report of this hard to diagnose.
                self._pushed_pre_call_values[_pushed_key] = _wire_norm
                _LOGGER.debug(
                    "global pre-call %s.%s sent %r to %s",
                    domain, service_name, wire_value, target_entity,
                )

    async def _run_settings_write(
        self,
        *,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
    ) -> None:
        """Bulk-write the device's saved per-room settings before a segment dispatch.

        The THIRD pre-dispatch shape, distinct from ``global_pre_calls`` (one global
        scalar per run) and ``per_room_live_settings`` (one per-room ENTITY write per
        room, mid-run). Dreame's per-room settings are PERSISTENT DEVICE STATE and the
        saved store WINS over the ``vacuum_clean_segment`` payload (settled on hardware
        2026-08-10, docstring at dreame/device.py:6931). So the real control surface is
        ONE ``vacuum_set_custom_cleaning`` call carrying index-aligned INT arrays over
        the queued rooms, applied while the robot is parked — the device refuses to edit
        while running, which is why its per-room entities go ``unavailable`` mid-run.

        Config: ``dispatch.settings_write`` = {domain, service, segment_id_field,
        fields:[{canonical, wire, value_map?, required?, filler?, clamp?,
        gate_room_suffix?}]}. A field with ``gate_room_suffix`` emits ONLY when
        ``select.<obj>_room_<first_id>_<suffix>`` exists (capability by entity presence
        — a registered-but-UI-unavailable entity still means the device is capable; the
        bulk call ignores the per-room UI mode-gate). Required fields always emit; a room
        whose canonical value is empty takes ``filler``; an unmapped value takes it too,
        so no stray string reaches an int-typed selector.

        Best-effort but LOUD: a failed write logs at ERROR and the run proceeds on the
        device's stored settings (there is no wet-mop safety hazard here, unlike the
        Roborock safe-water pre-call, so it does not abort). Absent config => no-op for
        every other brand.
        """
        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        sw = cfg.get("settings_write")
        if not sw or not resolved_rooms:
            return
        domain = sw.get("domain")
        service = sw.get("service")
        seg_field = sw.get("segment_id_field", "segment_id")
        if not (domain and service):
            return

        try:
            seg_ids = [int(r["room_id"]) for r in resolved_rooms]
        except (KeyError, TypeError, ValueError):
            _LOGGER.error(
                "settings_write for %s: resolved rooms missing a numeric room_id; "
                "skipping the per-room settings write",
                vacuum_entity_id,
            )
            return

        object_id = vacuum_entity_id.split(".", 1)[-1]
        data: dict[str, Any] = {"entity_id": vacuum_entity_id, seg_field: seg_ids}

        for fld in sw.get("fields") or []:
            wire = fld.get("wire")
            if not wire:
                continue

            # A CONSTANT field emits a fixed value for every room — a schema-required
            # wire the device ignores (Dreame water_volume, superseded by wetness_level
            # when the device has it). No canonical, no capability gate.
            if "constant" in fld:
                data[wire] = [fld["constant"]] * len(resolved_rooms)
                continue

            canonical = fld.get("canonical")
            if not canonical:
                continue

            # Capability by per-room ENTITY PRESENCE. Registered == capable even when the
            # entity is UI-`unavailable` (the bulk call bypasses the mode-gate). Probing
            # the first queued room is enough — the per-room entity set is uniform.
            # gate_domain defaults to `select`; a NUMBER-backed axis (Dreame's
            # wetness_level lives on number.<obj>_room_N_wetness_level) probes `number`.
            gate = fld.get("gate_room_suffix")
            if gate:
                gate_domain = fld.get("gate_domain", "select")
                probe = f"{gate_domain}.{object_id}_room_{seg_ids[0]}_{gate}"
                if self._manager.hass.states.get(probe) is None:
                    continue

            value_map = fld.get("value_map") or {}
            filler = fld.get("filler", 0)
            clamp = fld.get("clamp")
            column: list[Any] = []
            for room in resolved_rooms:
                raw = room.get(canonical)
                if raw is None or raw == "":
                    value = filler
                elif value_map:
                    # An unmapped value -> filler, never a stray string on an int-typed
                    # wire (the object selector would reject the whole call).
                    value = value_map.get(str(raw).strip().lower(), filler)
                else:
                    value = raw
                if clamp:
                    try:
                        value = max(int(clamp[0]), min(int(clamp[1]), int(value)))
                    except (TypeError, ValueError):
                        value = filler
                column.append(value)
            data[wire] = column

        # This MUTATES persistent device state (the saved per-room store), and the
        # change outlives the job — the same store the vendor app edits. That is the
        # brand's own model, not a leak: customized_cleaning ON means the saved store
        # applies to every run until changed.
        try:
            await self._manager.hass.services.async_call(
                domain, service, data, blocking=True
            )
        except Exception as err:  # noqa: BLE001 — best-effort-loud; the run still proceeds
            _LOGGER.error(
                "settings_write %s.%s failed for %s (%s) — the run will use the "
                "device's stored per-room settings instead of the requested ones",
                domain, service, vacuum_entity_id, err,
            )
