"""MapSourceCoordinator — the provider-map (map_state_source) backend dispatcher.

Owns the VA-owned read of the provider's OWN segmentation + live pose: the pre-warm dispatcher
(``async_refresh_map_state_source`` → storage / memory / introspect backends), the per-room
static scan + moving-overlay layering, the lightweight live-pose poll
(``async_get_map_live_pose``), the in-memory-vs-storage verify probe
(``async_compare_map_sources``), and the card's own-render raster fetch
(``async_get_map_render_data``). All brand-specific shapes live in the adapter's
``map_state_source`` block; core just dispatches by the declared backend/format.

Extracted from core/manager.py (the orchestrator keeps 1-line delegators for the four public
``async_*`` readers, so the snapshot service / sensors / pose-sampler listener call sites are
unchanged). Two deliberate seams stay on the manager:

- ``_map_state_source_cache`` — the pre-warm writes the normalized result here (via
  ``self._manager._map_state_source_cache``) and the on-loop dashboard snapshot composer + the
  map-overlays sensor READ it directly; keeping it on the manager means those readers (and their
  tests) don't change.
- ``_resolve_live_map_image_entity`` — shared with the dashboard snapshot composer (the live-map
  presence gate); called via ``self._manager._resolve_live_map_image_entity``.

The two caches that are internal to the backends (``_mem_rooms_cache`` content-versioned static
scan, ``_live_pose_geom_cache`` mtime-cached geometry) live here.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

from ..adapters.registry import get_adapter_config as _get_adapter_config

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)

# Last-known-good map retention: hold a previously-present map through a TRANSIENT source
# dropout (e.g. a Roborock cloud map entity going `unavailable` when the vacuum idles/docks —
# its parsed MapData lives only in HA memory, so the introspector reports `no_parsed_map`)
# instead of dropping it. Held for up to this long, then it ages out so a permanently-dead
# source doesn't show an indefinitely-stale map as if live.
_STALE_MAP_TTL_SECONDS = 6 * 3600

# Absent reasons that are STRUCTURAL / terminal, not a transient dropout — these DO clear a
# held map (never hold). Everything else absent (no_parsed_map / no_room_geometry /
# refresh_error) is treated as transient and holds the last-known-good.
_MAP_SOURCE_HARD_CLEAR_REASONS = frozenset({
    "live_map_absent",        # the live-map entity is GONE from the registry (not merely idle)
    "store_version_mismatch",  # fork schema shifted — the held geometry may be misaligned
    "not_configured",          # the adapter has no map_state_source block
    "no_device",               # the device / store path resolved to nothing
})


def _stat_mtime(path: str) -> float | None:
    """Return a file's mtime, or None if it doesn't exist. Blocking — call via executor."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


class MapSourceCoordinator:
    """Owns the map_state_source backend dispatch. Constructed with the core manager (the
    bundled-subsystem pattern); uses ``manager.hass``, writes the normalized result to
    ``manager._map_state_source_cache``, and shares ``manager._resolve_live_map_image_entity``."""

    def __init__(self, *, manager: "EufyVacuumManager") -> None:
        self._manager = manager
        # Backend-internal caches (read only by the methods below): the content-versioned
        # static per-room scan + converted map_data, and the mtime-cached live-pose geometry.
        self._mem_rooms_cache: dict[str, dict[str, Any]] = {}
        self._live_pose_geom_cache: dict[str, dict[str, Any]] = {}

    def _commit_result(
        self,
        vacuum_entity_id: str,
        map_id: str,
        result: dict[str, Any],
        *,
        mtime: float | None = None,
        present_gate: bool | None = None,
    ) -> dict[str, Any]:
        """Write a pre-warm result to ``manager._map_state_source_cache``, holding the
        last-known-good map through a TRANSIENT source dropout instead of dropping it.

        Rule (Chris's "replace only on a genuinely new valid update"): an ABSENT new result
        does NOT overwrite a PRESENT cached result for the SAME map_id — the last-good map is
        kept and flagged ``stale`` (the card dims/badges it and freezes the pose). It is
        replaced only when the new result is itself present, when the reason is a hard-clear
        (entity removed / structural — see ``_MAP_SOURCE_HARD_CLEAR_REASONS``), when the active
        map_id changed, or when the held map has aged past ``_STALE_MAP_TTL_SECONDS``. Holding
        the whole prior result freezes the pose with it (no re-applied live pose = no drift).

        Returns the EFFECTIVE result (the held one when holding, else the new one), so callers
        that return it hand the card the map that's actually cached.
        """
        entry: dict[str, Any] = {"mtime": mtime, "map_id": str(map_id), "result": result}
        if present_gate is not None:
            entry["present_gate"] = present_gate

        if not result.get("present"):
            reason = result.get("reason") or ""
            hard_clear = (
                reason in _MAP_SOURCE_HARD_CLEAR_REASONS
                or reason.startswith("unknown_backend")
            )
            cached = self._manager._map_state_source_cache.get(vacuum_entity_id) or {}
            cached_res = cached.get("result")
            if (
                not hard_clear
                and isinstance(cached_res, dict)
                and cached_res.get("present")
                and cached.get("map_id") == str(map_id)      # never serve another map's geometry
            ):
                since = cached_res.get("stale_since")
                now = time.time()
                if since is None:
                    since = now
                if now - since <= _STALE_MAP_TTL_SECONDS:
                    # Keep the last-good result; stamp staleness (stale_since is set ONCE so
                    # "held for N min" + the TTL stay accurate across repeated holds).
                    held = dict(cached_res)
                    held["stale"] = True
                    held["stale_since"] = since
                    held["stale_reason"] = reason
                    held_entry = dict(cached)  # preserve the original mtime/present_gate/map_id
                    held_entry["result"] = held
                    self._manager._map_state_source_cache[vacuum_entity_id] = held_entry
                    return held
                # Aged past the TTL — fall through and let the absent marker clear the map.

        self._manager._map_state_source_cache[vacuum_entity_id] = entry
        return result

    async def async_refresh_map_state_source(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any]:
        """Pre-warm the map_state_source cache for one vacuum (async, off-loop IO).

        Reads the adapter's `map_state_source` block, applies the presence gate
        (live-map artifact), and populates manager._map_state_source_cache so the sync
        on-loop snapshot can include the result without doing the blocking .storage
        read itself. Called from the dashboard-snapshot service handler before the
        sync snapshot. Degrades to an absent marker on any failure — never raises.

        Returns the result dict it cached (also handy for tests / a future sensor).
        """
        from ..mapping import map_source_runtime as _msr

        adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        source_cfg = adapter_cfg.get("map_state_source")
        if not isinstance(source_cfg, dict):
            result = {"present": False, "reason": "not_configured"}
            return self._commit_result(vacuum_entity_id, map_id, result)

        # Presence gate — most backends require the live-map artifact (the same
        # gate the card uses to show the live backdrop). An adapter can opt out
        # with present_requires_live_map_image: False. The resolved entity_id is
        # also handed to the Roborock introspector (the parsed MapData likely lives
        # on that image entity object).
        live_img = self._manager._resolve_live_map_image_entity(
            vacuum_entity_id=vacuum_entity_id, map_id=map_id, adapter_cfg=adapter_cfg
        )
        present = (live_img is not None) if source_cfg.get(
            "present_requires_live_map_image", True
        ) else True

        backend = source_cfg.get("backend")
        result: dict[str, Any]
        # Defense-in-depth: this runs ON THE EVENT LOOP inside the dashboard-snapshot service,
        # and the docstring promises "never raises". The branches are individually guarded, but
        # wrap the whole dispatch so any unforeseen error degrades to an absent marker rather
        # than propagating out of the snapshot service.
        try:
            if backend == "storage":
                # Memory-PRIMARY when the adapter declares a `memory` block (the fork holds the
                # same map_data in memory — fresher + loop-safe); it FALLS BACK to the .storage
                # read internally when the in-memory MapData is absent/malformed. Without a
                # `memory` block, the plain .storage read (legacy / other forks).
                if isinstance(source_cfg.get("memory"), dict):
                    result = await self._refresh_eufy_map_source(
                        vacuum_entity_id=vacuum_entity_id, map_id=map_id,
                        source_cfg=source_cfg, present=present,
                    )
                else:
                    result = await self._refresh_storage_map_source(
                        vacuum_entity_id=vacuum_entity_id, map_id=map_id,
                        source_cfg=source_cfg, present=present,
                    )
                    # Verify line (symmetric with the memory branch): present/reason + room
                    # count. DEBUG, not INFO — it rides the 60s pre-warm, so at INFO it floods
                    # the log over a long run; enable debug logging to see it after a deploy.
                    _LOGGER.debug(
                        "map_state_source[%s] storage read: present=%s reason=%s rooms=%d",
                        vacuum_entity_id, result.get("present"), result.get("reason"),
                        len(result.get("rooms") or []),
                    )
            elif backend == "memory":
                # In-memory introspection (no IO) — safe to run on the loop.
                candidates = _msr.roborock_candidates(
                    self._manager.hass, source_cfg, image_entity_id=live_img
                )
                result = _msr.roborock_result_from_candidates(candidates, present=present)
                if result.get("diagnostics") is not None:
                    _LOGGER.debug(
                        "map_state_source[%s] memory introspect: present=%s reason=%s diag=%s",
                        vacuum_entity_id, result.get("present"),
                        result.get("reason"), result.get("diagnostics"),
                    )
                result = self._commit_result(vacuum_entity_id, map_id, result)
            else:
                result = {"present": False, "reason": f"unknown_backend:{backend}"}
                result = self._commit_result(vacuum_entity_id, map_id, result)
        except Exception:  # noqa: BLE001 - never let the pre-warm break the snapshot service
            _LOGGER.exception(
                "map_state_source[%s] refresh failed; serving absent marker", vacuum_entity_id
            )
            result = {"present": False, "reason": "refresh_error"}
            result = self._commit_result(vacuum_entity_id, map_id, result)
        return result

    async def _refresh_storage_map_source(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        source_cfg: dict[str, Any],
        present: bool,
    ) -> dict[str, Any]:
        """Storage-backend branch of the map_state_source pre-warm (Eufy fork).

        Stats the Store file; re-parses (off-loop) only when the mtime changed since
        the cached read, so an unchanged map costs one stat, not a 200 KB parse +
        base64 decode every snapshot.
        """
        from ..mapping import map_source_runtime as _msr

        path = _msr.eufy_store_path(self._manager.hass, vacuum_entity_id, source_cfg)
        if not path:
            result = {"present": False, "backend": "storage", "reason": "no_device"}
            return self._commit_result(vacuum_entity_id, map_id, result)

        try:
            mtime: float | None = await self._manager.hass.async_add_executor_job(
                _stat_mtime, path
            )
        except OSError:
            mtime = None

        cached = self._manager._map_state_source_cache.get(vacuum_entity_id) or {}
        # Reuse the cached normalized result iff the file is unchanged AND the
        # presence gate is unchanged (live-map could appear/disappear between calls).
        if (
            mtime is not None
            and cached.get("mtime") == mtime
            and cached.get("present_gate") == present
            and isinstance(cached.get("result"), dict)
        ):
            return cached["result"]

        store_json = await self._manager.hass.async_add_executor_job(_msr.load_store_json, path)
        expected_version = source_cfg.get("store_version")
        result = _msr.eufy_result_from_store(
            store_json, expected_version=expected_version, present=present
        )
        if result.get("reason") == "store_version_mismatch":
            _LOGGER.warning(
                "map_state_source[%s]: store version mismatch (expected %s) — "
                "the fork schema may have shifted; re-point the adapter's "
                "map_state_source.store_version. Treating as unavailable.",
                vacuum_entity_id, expected_version,
            )
        # Override the MOVING overlays (robot/dock/current-room/path) with the fork's fresh
        # in-memory pose, keeping the static segmentation from .storage. store_json is None on a
        # missing/corrupt file (load_store_json degrades to None) — stay None-safe so the
        # on-loop snapshot never crashes (the result is already the absent marker in that case).
        map_data = ((store_json or {}).get("data") or {}).get("map_data") or {}
        self._apply_inmem_pose_to_result(
            result, map_data, vacuum_entity_id, source_cfg.get("live_pose"),
        )
        return self._commit_result(
            vacuum_entity_id, map_id, result, mtime=mtime, present_gate=present,
        )

    def _apply_inmem_pose_to_result(
        self,
        result: dict[str, Any],
        map_data: dict[str, Any],
        vacuum_entity_id: str,
        live_cfg: Any,
    ) -> None:
        """Layer the fork's fresh in-memory pose onto a map_state_source `result`, IN PLACE.

        Shared by the storage and memory backends: reads the live robot/dock/trail off the
        coordinator and makes the live pose AUTHORITATIVE for the moving overlay fields
        (apply_live_pose_override clears stale current_room/path first). Adapter-declared
        `live_pose`; absent => the overlays stay on the base values. Defensive: this runs ON
        THE EVENT LOOP inside the dashboard-snapshot service, and a provider-internal property
        could raise (esp. across the pending fork #136 merge) — so a failure degrades to the
        base overlays rather than aborting the snapshot. (The introspector is also guarded.)
        """
        if not (isinstance(live_cfg, dict) and result.get("present")):
            return
        try:
            pose = self._read_inmem_pose(vacuum_entity_id, live_cfg)
            if pose.get("present"):
                from ..mapping.map_source import (
                    apply_live_pose_override,
                    live_pose_overlay,
                )
                overlay = live_pose_overlay(
                    map_data, pose.get("robot_pixel"),
                    pose.get("dock_pixel"), pose.get("robot_heading"),
                    pose.get("trail_pixels"),
                )
                apply_live_pose_override(result, overlay)
        except Exception:  # noqa: BLE001 - never let the pose read break the snapshot
            _LOGGER.debug(
                "live_pose override failed for %s; keeping base overlays",
                vacuum_entity_id, exc_info=True,
            )

    def get_live_mapdata_obj(self, *, vacuum_entity_id: str, map_id: str):
        """Locate the live parser MapData OBJECT (not the normalized dict) for a vacuum.

        Zone dispatch needs the object — it projects a drawn zone back to device-mm via the
        parser's OWN transform (the same ``_mapdata_projector`` the overlays use), which the
        converted dict has lost. Routes by the adapter's ``map_state_source`` backend;
        in-memory introspection only (no IO, loop-safe). Returns the object, or ``None`` when
        no live map is available — the caller MUST then refuse to dispatch. Never raises.
        """
        from ..mapping import map_source_runtime as _msr

        adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        source_cfg = adapter_cfg.get("map_state_source")
        if not isinstance(source_cfg, dict):
            return None
        backend = source_cfg.get("backend")
        try:
            if backend == "memory":
                live_img = self._manager._resolve_live_map_image_entity(
                    vacuum_entity_id=vacuum_entity_id, map_id=map_id, adapter_cfg=adapter_cfg,
                )
                candidates = _msr.roborock_candidates(
                    self._manager.hass, source_cfg, image_entity_id=live_img,
                )
                for cand in candidates or []:
                    root = cand[2] if isinstance(cand, (list, tuple)) and len(cand) >= 3 else cand
                    md, _path = _msr.find_mapdata(root)
                    if md is not None:
                        return md
            elif backend == "storage" and isinstance(source_cfg.get("memory"), dict):
                mem_cfg = source_cfg["memory"]
                candidates = _msr.eufy_inmem_candidates(self._manager.hass, mem_cfg)
                found = _msr.eufy_mapdata_obj_from_candidates(
                    candidates,
                    mapdata_attrs=mem_cfg.get("mapdata_attrs"),
                    field_attrs=mem_cfg.get("field_attrs"),
                )
                if found.get("present"):
                    return found.get("obj")
        except Exception:  # noqa: BLE001 - never break dispatch; caller refuses on None
            _LOGGER.debug(
                "get_live_mapdata_obj failed for %s", vacuum_entity_id, exc_info=True,
            )
        return None

    async def _refresh_eufy_map_source(
        self,
        *,
        vacuum_entity_id: str,
        map_id: str,
        source_cfg: dict[str, Any],
        present: bool,
    ) -> dict[str, Any]:
        """Memory-PRIMARY branch of the Eufy map_state_source pre-warm.

        Reads the fork's fresh in-memory ``_map_data`` (loop-safe, no save-throttle lag) and
        builds the static segmentation from it; the per-room scan is cached by a content
        version so it only re-runs on a re-map (matching the storage path's mtime cache). The
        moving overlays are layered on from the live pose. FALLS BACK to the .storage read when
        the in-memory MapData is absent/malformed (early session, or fork shape drift). Never
        raises — degrades to the storage path.
        """
        from ..mapping import map_source_runtime as _msr
        from ..mapping.map_source import mapdata_dict_from_obj

        mem_cfg = source_cfg.get("memory") or {}
        if present:
            candidates = _msr.eufy_inmem_candidates(self._manager.hass, mem_cfg)
            # CHEAP locate: the raw MapData object + a version from the raw raster bytes, WITHOUT
            # the ~180 KB base64 conversion — so an unchanged map skips both the convert and the
            # per-room scan (only the BFS + a sha1 of the raw bytes run each refresh).
            mem = _msr.eufy_mapdata_obj_from_candidates(
                candidates, mapdata_attrs=mem_cfg.get("mapdata_attrs"),
                field_attrs=mem_cfg.get("field_attrs"),
            )
        else:
            mem = {"present": False, "reason": "live_map_absent"}

        if not mem.get("present"):
            # No usable in-memory map — fall back to the .storage read (logs its own reason).
            _LOGGER.debug(
                "map_state_source[%s] memory miss (%s) — falling back to .storage",
                vacuum_entity_id, mem.get("reason"),
            )
            return await self._refresh_storage_map_source(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id,
                source_cfg=source_cfg, present=present,
            )

        version = mem["version"]
        cache = self._mem_rooms_cache.get(vacuum_entity_id)
        if cache and cache.get("version") == version:
            static = cache["result"]
            map_data = cache["map_data"]            # reuse the converted dict — no re-encode
        else:
            # Re-map (or first read): convert + scan ONCE, then cache both for the pose path.
            map_data = mapdata_dict_from_obj(mem["obj"], field_attrs=mem_cfg.get("field_attrs"))
            if map_data is None:
                return await self._refresh_storage_map_source(
                    vacuum_entity_id=vacuum_entity_id, map_id=map_id,
                    source_cfg=source_cfg, present=present,
                )
            static = _msr.eufy_result_from_mapdata(map_data, present=True)
            self._mem_rooms_cache[vacuum_entity_id] = {
                "version": version, "result": static, "map_data": map_data,
            }

        # Shallow-copy the cached static result, then layer the FRESH pose on the copy (the
        # pose changes every refresh; the static rooms scan does not). The copy keeps the
        # cached static clean of the moving fields.
        result = dict(static)
        self._apply_inmem_pose_to_result(
            result, map_data, vacuum_entity_id, source_cfg.get("live_pose"),
        )
        _LOGGER.debug(
            "map_state_source[%s] memory read: present=%s rooms=%d (version=%s)",
            vacuum_entity_id, result.get("present"),
            len(result.get("rooms") or []), version,
        )
        return self._commit_result(
            vacuum_entity_id, map_id, result, present_gate=present,
        )

    def _read_inmem_pose(
        self, vacuum_entity_id: str, live_cfg: dict[str, Any]
    ) -> dict[str, Any]:
        """Read the fork's in-memory live robot/dock PIXEL (fresh ~2s). In-memory only —
        loop-safe. Returns the pose + a diagnostics breadcrumb (structure dump when the
        attr path isn't found — the deploy-and-discover signal). Never raises."""
        from ..mapping import map_source_runtime as _msr

        candidates = _msr.eufy_inmem_candidates(self._manager.hass, live_cfg)
        pose = _msr.eufy_live_pose_from_candidates(
            candidates,
            robot_attrs=live_cfg.get("robot_pixel_attrs"),
            dock_attrs=live_cfg.get("dock_pixel_attrs"),
            heading_attrs=live_cfg.get("heading_attrs"),
            trail_attrs=live_cfg.get("trail_pixel_attrs"),
        )
        _LOGGER.debug(
            "live_pose[%s]: present=%s reason=%s pose_at=%s",
            vacuum_entity_id, pose.get("present"), pose.get("reason"),
            (pose.get("diagnostics") or {}).get("pose_at"),
        )
        return pose

    async def _load_live_pose_geom(
        self, vacuum_entity_id: str, source_cfg: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Load (mtime-cached) the static map_data the live-pose normalization needs."""
        from ..mapping import map_source_runtime as _msr

        path = _msr.eufy_store_path(self._manager.hass, vacuum_entity_id, source_cfg)
        if not path:
            return None
        mtime = await self._manager.hass.async_add_executor_job(_stat_mtime, path)
        cache = self._live_pose_geom_cache.get(vacuum_entity_id)
        if cache and mtime is not None and cache.get("mtime") == mtime:
            return cache.get("map_data")
        store_json = await self._manager.hass.async_add_executor_job(_msr.load_store_json, path)
        map_data = None
        if isinstance(store_json, dict):
            map_data = (store_json.get("data") or {}).get("map_data")
        if isinstance(map_data, dict):
            self._live_pose_geom_cache[vacuum_entity_id] = {
                "mtime": mtime, "map_data": map_data,
            }
            return map_data
        return None

    async def async_get_map_live_pose(
        self, *, vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return ONLY the moving overlays (robot/dock anchors + current-room + heading)
        from the fork's fresh in-memory pose — the lightweight payload the card polls at
        the ~2s live cadence (vs the full snapshot). Adapter-driven; degrades to an absent
        marker (+ diagnostics for discovery)."""
        from ..mapping.map_source import live_pose_overlay

        adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        source_cfg = adapter_cfg.get("map_state_source")
        live_cfg = source_cfg.get("live_pose") if isinstance(source_cfg, dict) else None
        if not isinstance(live_cfg, dict):
            return {"present": False, "reason": "not_configured"}
        pose = self._read_inmem_pose(vacuum_entity_id, live_cfg)
        if not pose.get("present"):
            return {
                "present": False, "reason": pose.get("reason", "no_pose"),
                "diagnostics": pose.get("diagnostics"),
            }
        map_data = await self._load_live_pose_geom(vacuum_entity_id, source_cfg)
        if not map_data:
            return {"present": False, "reason": "no_geom",
                    "diagnostics": pose.get("diagnostics")}
        overlay = live_pose_overlay(
            map_data, pose.get("robot_pixel"), pose.get("dock_pixel"),
            pose.get("robot_heading"), pose.get("trail_pixels"),
        )
        return {"present": True, **overlay, "diagnostics": pose.get("diagnostics")}

    async def async_compare_map_sources(
        self, *, vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """VERIFY PROBE (P1, diagnostic): read the fork's IN-MEMORY _map_data AND the .storage
        map_data and compare them, to confirm the in-memory bytes are byte-identical before
        repointing the map source. Returns a per-field comparison (rasters by len+sha1) + a
        `normalization_safe` verdict over the geometry/raster fields the decoders use. Adapter-
        driven via map_state_source.memory; degrades to a marker (+ diagnostics) on absence."""
        from ..mapping import map_source_runtime as _msr
        from ..mapping.map_source import compare_map_data

        adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        source_cfg = adapter_cfg.get("map_state_source")
        if not isinstance(source_cfg, dict):
            return {"present": False, "reason": "not_configured"}
        mem_cfg = source_cfg.get("memory")
        if not isinstance(mem_cfg, dict):
            return {"present": False, "reason": "memory_not_configured"}

        # In-memory MapData (loop-safe).
        candidates = _msr.eufy_inmem_candidates(self._manager.hass, mem_cfg)
        mem = _msr.eufy_mapdata_from_candidates(
            candidates, mapdata_attrs=mem_cfg.get("mapdata_attrs"),
            field_attrs=mem_cfg.get("field_attrs"),
        )
        # .storage map_data (off-loop read).
        path = _msr.eufy_store_path(self._manager.hass, vacuum_entity_id, source_cfg)
        store_json = (
            await self._manager.hass.async_add_executor_job(_msr.load_store_json, path)
            if path else None
        )
        store_md = None
        if isinstance(store_json, dict):
            store_md = (store_json.get("data") or {}).get("map_data")

        out: dict[str, Any] = {
            "in_memory_present": bool(mem.get("present")),
            "storage_present": isinstance(store_md, dict),
            "diagnostics": mem.get("diagnostics"),
        }
        if mem.get("present") and isinstance(store_md, dict):
            out["compare"] = compare_map_data(mem["map_data"], store_md)
        return out

    def _roborock_render_room_names(self, vacuum_entity_id: str) -> dict[str, str]:
        """``{str(room_id): name}`` for a vacuum's stored rooms — the labels the render raster
        maps its resolved room ids to. Roborock's ``room_id`` is the segment id, which matches
        the raster's ``byte >> 3`` id. Best-effort: ``{}`` on any missing piece; never raises."""
        out: dict[str, str] = {}
        try:
            maps = (self._manager.data.get("maps", {}) or {}).get(vacuum_entity_id, {}) or {}
            for bucket in maps.values():
                if not isinstance(bucket, dict):
                    continue
                for room in (bucket.get("rooms") or {}).values():
                    if isinstance(room, dict):
                        rid = room.get("room_id")
                        name = room.get("name")
                        if rid is not None and name:
                            out[str(rid)] = str(name)
        except Exception:  # noqa: BLE001 - render labels are cosmetic; degrade to unnamed
            return {}
        return out

    async def async_get_map_render_data(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return the raster + decode params for the card's OWN map render (Wave 1).

        Adapter-DRIVEN: the adapter's `map_render.format` selects the decode, and the
        source pointer is REUSED from `map_state_source` (no duplicate schema). Core just
        dispatches by format — no brand assumptions here. The card calls this on demand
        (when the VA-rendered backdrop is selected) and caches by the returned `version`;
        the raster is static (changes only on re-map), so it's fetch-once, not snapshot
        bloat. Off-loop `.storage` read via executor. Degrades to an absent marker.
        """
        from ..mapping import map_source_runtime as _msr

        adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        render_cfg = adapter_cfg.get("map_render")
        if not isinstance(render_cfg, dict):
            return {"present": False, "reason": "not_configured"}
        fmt = render_cfg.get("format")
        source_cfg = adapter_cfg.get("map_state_source")

        # Roborock: re-decode the raw map blob (the v1 MapContent.raw_api_response, cached in
        # HA memory) to a room-id raster and shape it as the card's GENERIC render-data — the
        # parser only keeps bboxes. No map_id / image entity needed: roborock_candidates scans
        # the roborock runtime_data roots. In-memory + pure -> loop-safe; degrades to an absent
        # marker (roborock_render_data_from_candidates never raises).
        if (
            fmt == "roborock_raw_map_v1"
            and isinstance(source_cfg, dict)
            and source_cfg.get("backend") == "memory"
        ):
            candidates = _msr.roborock_candidates(self._manager.hass, source_cfg)
            return _msr.roborock_render_data_from_candidates(
                candidates, self._roborock_render_room_names(vacuum_entity_id)
            )

        if not (
            fmt == "eufy_room_pixels_v1"
            and isinstance(source_cfg, dict)
            and source_cfg.get("backend") == "storage"
        ):
            return {"present": False, "reason": f"unknown_format:{fmt}"}

        # Memory-PRIMARY: the fork's in-memory _map_data carries the same raster, fresher +
        # loop-safe (no file read). render_data_from_storage takes the SAME map_data dict
        # shape the shim produces, so the card decode params are identical.
        from ..mapping.map_source import render_data_from_storage
        mem_cfg = source_cfg.get("memory")
        if isinstance(mem_cfg, dict):
            candidates = _msr.eufy_inmem_candidates(self._manager.hass, mem_cfg)
            mem = _msr.eufy_mapdata_from_candidates(
                candidates, mapdata_attrs=mem_cfg.get("mapdata_attrs"),
                field_attrs=mem_cfg.get("field_attrs"),
            )
            if mem.get("present"):
                rd = render_data_from_storage(mem["map_data"])
                if rd is not None:
                    return rd
            # else fall through to the .storage read

        # .storage fallback (or no memory block).
        path = _msr.eufy_store_path(self._manager.hass, vacuum_entity_id, source_cfg)
        if not path:
            return {"present": False, "reason": "no_device"}
        store_json = await self._manager.hass.async_add_executor_job(_msr.load_store_json, path)
        return _msr.eufy_render_data_from_store(
            store_json, expected_version=source_cfg.get("store_version")
        )

    async def async_get_map_data_dict(
        self, *, vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the raw decoded Eufy ``map_data`` dict (room_pixels + origin/res/dims)
        for a vacuum's CURRENT map — the input the pure readers (``rooms_from_room_pixels``,
        ``current_room_for_pixel``, ``zone_membership``) consume. Memory-PRIMARY (the fork's
        in-memory ``_map_data``, loop-safe) with an off-loop ``.storage`` fallback.

        Returns ``None`` for a non-raster backend (Roborock memory), an old install with no
        map, or any read failure — callers degrade gracefully. Never raises.
        """
        from ..mapping import map_source_runtime as _msr

        try:
            adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
            source_cfg = adapter_cfg.get("map_state_source")
            # Only the Eufy storage backend carries a room_pixels raster; the Roborock
            # memory backend has no per-pixel room mask (no map_data dict of this shape).
            if not (isinstance(source_cfg, dict) and source_cfg.get("backend") == "storage"):
                return None

            # Memory-PRIMARY: the fork's in-memory _map_data (same dict shape, fresher).
            mem_cfg = source_cfg.get("memory")
            if isinstance(mem_cfg, dict):
                candidates = _msr.eufy_inmem_candidates(self._manager.hass, mem_cfg)
                mem = _msr.eufy_mapdata_from_candidates(
                    candidates, mapdata_attrs=mem_cfg.get("mapdata_attrs"),
                    field_attrs=mem_cfg.get("field_attrs"),
                )
                if mem.get("present") and isinstance(mem.get("map_data"), dict):
                    return mem["map_data"]

            # .storage fallback (or no memory block).
            path = _msr.eufy_store_path(self._manager.hass, vacuum_entity_id, source_cfg)
            if not path:
                return None
            store_json = await self._manager.hass.async_add_executor_job(
                _msr.load_store_json, path
            )
            map_data = ((store_json or {}).get("data") or {}).get("map_data")
            return map_data if isinstance(map_data, dict) else None
        except Exception:  # noqa: BLE001 — best-effort accessor, never break the caller
            _LOGGER.debug(
                "async_get_map_data_dict failed for %s", vacuum_entity_id, exc_info=True
            )
            return None
