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

from homeassistant.exceptions import HomeAssistantError

from ..adapters.registry import get_adapter_config as _get_adapter_config

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


class DispatchManager:
    """Owns send-side wire dispatch. Constructed with the core manager (the
    bundled-subsystem pattern); uses ``manager.hass`` + the manager's map/room helpers
    (``async_get_map_data_dict``, ``map_source``) via ``self._manager``."""

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager

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
        await self._manager.hass.services.async_call(domain, name, data, blocking=True)

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
        cfg = (_get_adapter_config(vacuum_entity_id) or {}).get("dispatch", {})
        zone_command = cfg.get("zone_command")
        if not zone_command:
            raise ValueError(
                f"{vacuum_entity_id}: this vacuum's adapter declares no zone_command "
                "(zone cleaning is not supported for this brand/provider)"
            )
        # ZONE-2: only the card previously consulted supports_zone_clean -- a direct
        # service call or automation reached the device even when the brand declares
        # it unsupported. Checked here so every call path is covered.
        _zone_caps = (_get_adapter_config(vacuum_entity_id) or {}).get("capabilities", {})
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
        if cfg.get("zone_coords") == "device_mm":
            from ..mapping import map_source_runtime as _msr
            from . import zone_dispatch as _zd

            map_obj = self._manager.map_source.get_live_mapdata_obj(
                vacuum_entity_id=vacuum_entity_id, map_id=str(map_id or ""),
            )
            if map_obj is None:
                raise ValueError(
                    f"{vacuum_entity_id}: no live map available to convert the zone to "
                    "device coordinates — open the robot's map and try again"
                )
            corr = _msr.correspondences_from_mapdata(map_obj)
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
            # Per-zone repeat cap comes from the adapter, not a hardcoded 3:
            # dispatch.zone_passes_max (a zone-specific override) or the general
            # dispatch.passes_max, default 3 (covers Roborock 1-3). Unaffected by
            # Q12 -- Q12 is scoped to the non-device_mm (Eufy) branch below.
            _zone_repeat_max = int(cfg.get("zone_passes_max", cfg.get("passes_max", 3)) or 3)
            repeat = max(1, min(int(clean_times), _zone_repeat_max))
            # app_zoned_clean params ARE the zone list: [[x0,y0,x1,y1,repeat], ...] (int mm).
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

    async def _run_global_pre_calls(
        self,
        *,
        vacuum_entity_id: str,
        resolved_rooms: list[dict[str, Any]],
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

        Entry shape::

            {"field": "fan_speed",
             "rank": ["gentle","quiet","balanced","turbo","max"],  # ascending
             "service": {"domain": "vacuum", "service": "set_fan_speed",
                         "value_key": "fan_speed",
                         "target_entity_id": <full id>},   # default: the vacuum
             "value_map": {canonical: wire, ...},           # optional, identity if absent
             "mixed_mode_water_policy": "safest"}           # optional; mixed-batch safe-water
        """
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
