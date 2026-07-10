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

import logging
from typing import TYPE_CHECKING, Any

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
        # Device limits (from capabilities): a per-clean zone COUNT cap (defence-in-depth —
        # the card also caps the draw) plus per-zone SIZE bounds checked after the device-mm
        # conversion below. Absent => unconstrained for that brand.
        _zone_caps = (_get_adapter_config(vacuum_entity_id) or {}).get("capabilities", {})
        _zone_max = _zone_caps.get("zone_max")
        if _zone_max is not None and len(zones) > int(_zone_max):
            raise ValueError(
                f"{vacuum_entity_id}: too many zones ({len(zones)}) — this vacuum allows at "
                f"most {int(_zone_max)} per clean"
            )
        # Coordinate frame: most providers de-normalize on their side, so we ship the
        # 0-1 image rects verbatim (Eufy's fork zone_clean). Brands whose command wants
        # WORLD millimetres (Roborock app_zoned_clean) declare ``zone_coords: device_mm``;
        # we convert here via the live map's own projection and REFUSE rather than
        # dispatch if the conversion can't be validated (a wrong inverse cleans the
        # wrong area — see mapping/zone_dispatch.py).
        if cfg.get("zone_coords") == "device_mm":
            from ..mapping import map_source_runtime as _msr
            from ..mapping import zone_dispatch as _zd

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
            # Per-zone size bounds (device mm² -> m²). The device rejects zones outside its
            # range, so refuse with a clear message rather than a silent device failure.
            _min_a = _zone_caps.get("zone_min_area_m2")
            _max_a = _zone_caps.get("zone_max_area_m2")
            for _x0, _y0, _x1, _y1 in mm_rects:
                _area = abs(_x1 - _x0) * abs(_y1 - _y0) / 1_000_000.0
                if _min_a is not None and _area < float(_min_a):
                    raise ValueError(
                        f"{vacuum_entity_id}: a zone is too small ({_area:.2f} m²) — the "
                        f"minimum is {float(_min_a):.2f} m² (~1 ft²); draw a bigger box"
                    )
                if _max_a is not None and _area > float(_max_a):
                    raise ValueError(
                        f"{vacuum_entity_id}: a zone is too large ({_area:.2f} m²) — the "
                        f"maximum is {float(_max_a):.2f} m² (~32.8 ft²); draw a smaller box"
                    )
            # Per-zone repeat cap comes from the adapter, not a hardcoded 3:
            # dispatch.zone_passes_max (a zone-specific override) or the general
            # dispatch.passes_max, default 3 (covers Eufy 1-2 and Roborock 1-3).
            # A brand whose zone command supports more repeats just declares more.
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
            # Enforce any per-SIDE device bound (zone_min_side_m / zone_max_side_m) here by
            # converting each rect to metres via the live map's own dims — the SAME
            # de-normalization the fork applies: side_m = Δnorm * dim * res / 100 (matches
            # coordinator.normalized_rects_to_quads_cm). Refuse with a clear message rather
            # than let the device silently reject. If no live map is readable we skip the
            # check (the card validates at draw time; this is defence-in-depth).
            _min_side = _zone_caps.get("zone_min_side_m")
            _max_side = _zone_caps.get("zone_max_side_m")
            if _min_side is not None or _max_side is not None:
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
                if _w and _h:
                    for _x0, _y0, _x1, _y1 in zones:
                        for _side in (
                            abs(_x1 - _x0) * _w * _res / 100.0,
                            abs(_y1 - _y0) * _h * _res / 100.0,
                        ):
                            if _min_side is not None and _side < float(_min_side):
                                raise ValueError(
                                    f"{vacuum_entity_id}: a zone side is too short "
                                    f"({_side:.2f} m) — the minimum is {float(_min_side):.2f} m; "
                                    "draw a bigger box"
                                )
                            if _max_side is not None and _side > float(_max_side):
                                raise ValueError(
                                    f"{vacuum_entity_id}: a zone side is too long "
                                    f"({_side:.2f} m) — the maximum is {float(_max_side):.2f} m; "
                                    "draw a smaller box"
                                )
            payload = {"zones": zones, "clean_times": int(clean_times)}
            await self._dispatch_clean_payload(
                vacuum_entity_id=vacuum_entity_id,
                payload=payload,
                command_override=zone_command,
            )
        return {
            "status": "dispatched",
            "vacuum_entity_id": vacuum_entity_id,
            "zone_count": len(zones),
            "clean_times": int(clean_times),
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

        from ..rooms.source_refresh import async_refresh_room_source
        from ..rooms.room_discovery import discover_rooms_for_vacuum

        await async_refresh_room_source(self._manager.hass, vacuum_entity_id)
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

        if not slug_to_live_id:
            _LOGGER.warning(
                "dispatch: no live segment source for %s; dispatching stored ids",
                vacuum_entity_id,
            )
            return payload

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
            _LOGGER.warning(
                "dispatch: no target rooms resolved live for %s; dispatching stored ids",
                vacuum_entity_id,
            )
            return payload
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
                if "mop" in str(r.get("clean_mode") or "").strip().lower()
            )
            _mixed_batch = 0 < _mop_rooms < len(resolved_rooms)
            _use_safest = (
                str(entry.get("mixed_mode_water_policy") or "").strip().lower() == "safest"
                and _mixed_batch
            )

            if _use_safest:
                # Only push a safe water if SOMETHING in the batch was rankable at all
                # (mirrors the max-wins "nothing rankable -> leave untouched" contract); a
                # mixed batch always has rankable mop rooms, so this normally targets rank[0].
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
            if canonical_value == "off":
                target_entity_for_opts = service.get("target_entity_id") or vacuum_entity_id
                _sel_state = self._manager.hass.states.get(target_entity_for_opts)
                _opts = (
                    [str(o).strip().lower() for o in _sel_state.attributes.get("options") or []]
                    if _sel_state is not None else []
                )
                if _opts and "off" not in _opts:
                    # Walk the entry's rank ascending for the first option the select has.
                    for _cand in rank:
                        if _cand in _opts:
                            canonical_value = _cand
                            break
            value_map = entry.get("value_map") or {}
            wire_value = value_map.get(canonical_value, canonical_value)

            target_entity = service.get("target_entity_id") or vacuum_entity_id
            try:
                await self._manager.hass.services.async_call(
                    domain,
                    service_name,
                    {"entity_id": target_entity, value_key: wire_value},
                    blocking=True,
                )
            except Exception:  # pragma: no cover - best-effort global pre-call
                _LOGGER.exception(
                    "global pre-call %s.%s failed for %s",
                    domain, service_name, vacuum_entity_id,
                )
