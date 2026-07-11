"""Optional learning-system manager for Vacuum Agent.

============================================================
LEARNING MANAGER
============================================================

PURPOSE
-------
Orchestrator for the optional learning system. Coordinates between
the core integration manager, the history store, and the estimation
engine. Does not perform any estimation, confidence, or ETA math —
that all lives in estimator.py.

RESPONSIBILITIES
----------------
- pull payload state from the core manager
- extract ordered rooms as the single source of truth for room execution order
- normalize inputs for the estimator
- call estimator and return the full result
- delegate finalization, snapshotting, and stats rebuilds to their modules
- record estimate accuracy after job finalization
- expose next_room shortcut and reanchor_timeline passthrough
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from .brand_facts import brand_facts_for
from ..const import DOMAIN
from ..profiles.room_profiles import get_default_room_profiles
from ..timestamp_utils import parse_timestamp, utc_now
from .utils import _iso_now, _room_key, _room_profile_key, _safe_float, _safe_int
from .estimator import LearningEstimator
from .history_store import LearningHistoryStore
from .job_finalizer import LearningJobFinalizer
from .stats_rebuilder import LearningStatsRebuilder


def _normalize_graph_targets(value: Any) -> list[int]:
    """Return normalized downstream room ids from grants_access_to."""
    if not isinstance(value, list):
        return []
    normalized: list[int] = []
    for item in value:
        room_id = _safe_int(item, -1)
        if room_id < 0 or room_id in normalized:
            continue
        normalized.append(room_id)
    return normalized


FOUND_PROFILE_TRUST_THRESHOLD = 5


def _trust_level_from_score(score: float) -> str:
    """Return trust label for a normalized score."""
    if score >= 0.85:
        return "strong"
    if score >= 0.65:
        return "good"
    if score >= 0.4:
        return "building"
    return "low"


def _display_label(value: Any) -> str | None:
    """Return a simple title-cased display label for status/reason values."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("_", " ").replace("-", " ").strip()
    if not normalized:
        return None
    return " ".join(part.capitalize() for part in normalized.split())


def _room_label(value: Any) -> str | None:
    """Return a friendly room label from a slug-like value."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    return _display_label(text)


def _reason_text(value: Any) -> str | None:
    """Return human-readable explanatory text for known learning/system reasons."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    explicit = {
        "manual_test_run": "Marked as a manual test run.",
        "short_test_cancel": "Looks like a short test run that was canceled early.",
        "false_completion": "This run appears to have ended before cleaning really completed.",
        "bad_room_attribution": "Room attribution for this run looks unreliable.",
        "interrupted_run": "This run appears to have been interrupted.",
        "extreme_idle_wall": "Held from learning — an unusually long idle stretch off the dock, so it does not define a room baseline. Restore it if the run was legitimate.",
        "failed_sanity": "This run failed the backend sanity checks.",
        "short_duration_vs_profile": "Much shorter than this profile usually takes.",
        "short_duration_vs_room": "Much shorter than this room usually takes.",
        "excluded_from_learning": "This run is currently excluded from learning.",
        "cancel_like": "This run looks like a canceled run.",
        "cancelled": "This run ended as a cancelled job.",
        "failed": "This run ended as a failed job.",
        "interrupted": "This run ended as an interrupted job.",
        "completed": "This run completed normally.",
        "test": "This run is marked as a test job.",
        "no_learning_runs": "There are not enough learned runs yet.",
        "building_samples": "The system is still building enough history to trust this estimate.",
        "accuracy_observed": "Trust is supported by real estimate-versus-actual history.",
        "not_enough_accuracy_data": "More estimate-versus-actual history is needed before trust can improve.",
        "missing_timestamps": "The run did not have enough timestamp data to classify reliably.",
        "not_single_room": "Cancel-likely detection currently only applies to single-room jobs.",
        "no_transition_history": "No state-transition history was available for this run.",
        "service_state_explains_return": "The return looked like a normal service cycle rather than a cancel.",
        "no_cancel_like_transition": "No cancel-like transition pattern was observed.",
    }
    if text in explicit:
        return explicit[text]
    label = _display_label(text)
    return f"{label}." if label else None


def _profile_name_label(value: Any) -> str | None:
    """Return a friendly label for a preset/custom profile name."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.strip().lower()
    replacements = {
        "vacuum_quick": "Vacuum Quick",
        "vacuum_deep": "Vacuum Deep",
        "vacuum_mop_quick": "Vacuum + Mop Quick",
        "vacuum_mop_deep": "Vacuum + Mop Deep",
        "custom": "Custom",
        "user_1": "Custom",
    }
    if normalized in replacements:
        return replacements[normalized]
    return _display_label(normalized)


def _normalize_profile_setting(value: Any, aliases: dict[str, str] | None) -> Any:
    """Normalize a raw profile-setting display string to a canonical code.

    Room-profile settings are stored as un-normalized display strings (mixed
    case, spaces — e.g. "Vacuum and mop", "Standard", "BoostIQ"), so their
    card-side slug (lowercased, non-alnum -> "_") would miss the vocab key and
    fall back to English. Lowercase + collapse non-alphanumerics to single
    spaces, map through the adapter's alias table (display string -> canonical
    code), and slug anything not aliased. Empty/None passes through unchanged so
    "no setting" stays falsy.
    """
    text = str(value or "").strip().lower()
    if not text:
        return value
    compact = " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())
    if not compact:
        return value
    if aliases:
        mapped = aliases.get(compact)
        if mapped is not None:
            return mapped
    return compact.replace(" ", "_")


def _settings_profile_label(
    *,
    room_slug: Any = None,
    selected_profile_name: Any = None,
    resolved_profile_name: Any = None,
    clean_mode: Any = None,
    clean_intensity: Any = None,
    fan_speed: Any = None,
    water_level: Any = None,
    clean_passes: Any = None,
    edge_mopping: Any = None,
) -> dict[str, Any]:
    """Build strong human-facing labels for observed room-profile settings."""
    room_label = _display_label(room_slug)
    selected_normalized = str(selected_profile_name or "").strip().lower()
    resolved_normalized = str(resolved_profile_name or "").strip().lower()
    selected_label = _profile_name_label(selected_profile_name)
    resolved_label = _profile_name_label(resolved_profile_name)
    mode_label = _display_label(clean_mode)
    intensity_label = _display_label(clean_intensity)
    fan_label = _display_label(fan_speed)
    water_label = _display_label(water_level)
    passes_value = max(_safe_int(clean_passes, 1), 1)
    edge_enabled = bool(edge_mopping)

    is_custom = selected_normalized in {"", "custom", "user_1"} or (
        selected_normalized != resolved_normalized and selected_normalized not in {"vacuum_quick", "vacuum_deep", "vacuum_mop_quick", "vacuum_mop_deep"}
    )

    if not is_custom and selected_label:
        profile_label = f"{room_label} {selected_label}".strip() if room_label else selected_label
    else:
        base_bits = [room_label, "Custom", mode_label]
        if passes_value > 1:
            base_bits.append(f"{passes_value} Pass")
        profile_label = " ".join(bit for bit in base_bits if bit).strip() or "Custom Profile"

    subtitle_bits: list[str] = []
    if not is_custom and selected_label and resolved_label and selected_label != resolved_label:
        subtitle_bits.append(f"{selected_label} via {resolved_label}")
    elif resolved_label and (is_custom or not selected_label):
        subtitle_bits.append(resolved_label)

    for bit in (intensity_label, fan_label):
        if bit and bit not in subtitle_bits:
            subtitle_bits.append(bit)
    if water_label and water_label.lower() != "off" and water_label not in subtitle_bits:
        subtitle_bits.append(water_label)
    if passes_value > 1:
        subtitle_bits.append(f"{passes_value} Passes")
    if edge_enabled:
        subtitle_bits.append("Edge Mopping")

    return {
        "profile_label": profile_label,
        "profile_subtitle": " • ".join(bit for bit in subtitle_bits if bit) or None,
        "selected_profile_label": selected_label,
        "resolved_profile_label": resolved_label,
        "is_custom_profile": is_custom,
    }


def _parse_local_timestamp(value: Any) -> datetime | None:
    """Parse persisted timestamps used by the learning store."""
    return parse_timestamp(value)


def _make_error_source(hass: HomeAssistant):
    """Default finalizer error source — harvests the active-run error latch from the
    ErrorTracker in hass.data (None if it isn't loaded). Injected into the finalizer so
    the finalizer itself holds no hass.data / sibling-subsystem knowledge (§9.3)."""
    from ..const import DATA_ERROR_TRACKER

    def _source(vacuum_entity_id: str, job_id: str) -> dict[str, Any] | None:
        tracker = (hass.data.get(DOMAIN, {}) or {}).get(DATA_ERROR_TRACKER) if hass is not None else None
        return tracker.harvest_active_run(vacuum_entity_id, job_id) if tracker is not None else None

    return _source


def _make_battery_sink(hass: HomeAssistant):
    """Default finalizer battery sink — pushes completed-job metrics to the
    BatteryHealthManager in hass.data (no-op if it isn't loaded)."""
    from ..const import DATA_BATTERY

    def _sink(*, vacuum_entity_id: str, metrics: dict[str, Any], job_id: str) -> None:
        mgr = (hass.data.get(DOMAIN, {}) or {}).get(DATA_BATTERY) if hass is not None else None
        if mgr is not None:
            mgr.record_job_metrics(vacuum_entity_id=vacuum_entity_id, metrics=metrics, job_id=job_id)

    return _sink


class LearningManager:
    """Coordinator for the optional learning system."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = LearningHistoryStore(hass)
        self.finalizer = LearningJobFinalizer(
            hass,
            estimate_fn=self.estimate_from_manager,
            error_source=_make_error_source(hass),
            battery_sink=_make_battery_sink(hass),
        )
        self.rebuilder = LearningStatsRebuilder(hass)
        self.estimator = LearningEstimator(hass)
        self._room_stats_cache: dict[str, dict[str, Any]] = {}
        self._accuracy_stats_cache: dict[str, dict[str, Any]] = {}
        self._learning_stats_loading: set[str] = set()


    def _get_cached_learning_stats(
        self,
        *,
        vacuum_entity_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        """Return cached learning stats without blocking the event loop.

        If no cache is present yet, schedule an async preload and return empty
        defaults. Start-path callers can safely use these defaults until the
        background load completes.
        """
        room_stats_data = self._room_stats_cache.get(vacuum_entity_id)
        accuracy_stats = self._accuracy_stats_cache.get(vacuum_entity_id)

        if not isinstance(room_stats_data, dict) or not isinstance(accuracy_stats, dict):
            self.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
            room_stats_data = room_stats_data if isinstance(room_stats_data, dict) else {}
            accuracy_stats = accuracy_stats if isinstance(accuracy_stats, dict) else {}

        # Use cached data for staleness check to avoid a blocking disk read on
        # the event loop. If the cache is empty the background preload will fill
        # it; treat empty cache as stale so callers retry after the reload.
        if room_stats_data:
            stats_stale = bool(self.estimator._is_stats_stale(
                vacuum_entity_id=vacuum_entity_id,
                room_stats_data=room_stats_data,
            ))
        else:
            stats_stale = True

        return room_stats_data, accuracy_stats, stats_stale

    def _reload_learning_stats_now(
        self,
        *,
        vacuum_entity_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        """Reload learning stats from disk immediately and refresh caches.

        This path is safe for executor-backed service calls and post-rebuild
        refreshes. Unlike the passive preload helper, it guarantees that the
        returned payload reflects the current on-disk learned stats.
        """
        room_stats_data = self.store.load_room_stats(vacuum_entity_id=vacuum_entity_id) or {}
        accuracy_stats = self.estimator._load_accuracy_stats(
            vacuum_entity_id=vacuum_entity_id
        ) or {}

        self._room_stats_cache[vacuum_entity_id] = (
            room_stats_data if isinstance(room_stats_data, dict) else {}
        )
        self._accuracy_stats_cache[vacuum_entity_id] = (
            accuracy_stats if isinstance(accuracy_stats, dict) else {}
        )

        stats_stale = bool(self.estimator._is_stats_stale(vacuum_entity_id=vacuum_entity_id))
        return (
            self._room_stats_cache[vacuum_entity_id],
            self._accuracy_stats_cache[vacuum_entity_id],
            stats_stale,
        )

    def _invalidate_learning_stats_cache(
        self,
        *,
        vacuum_entity_id: str,
    ) -> None:
        """Drop cached learning stats for one vacuum.

        Rebuild/finalize flows write new learned outputs to disk. The next
        explicit estimate read must not continue serving stale cached data.
        """
        self._room_stats_cache.pop(vacuum_entity_id, None)
        self._accuracy_stats_cache.pop(vacuum_entity_id, None)

    def async_preload_learning_stats(
        self,
        *,
        vacuum_entity_id: str,
    ) -> None:
        """Schedule learning stats preload on the executor if needed."""
        if vacuum_entity_id in self._learning_stats_loading:
            return
        if vacuum_entity_id in self._room_stats_cache and vacuum_entity_id in self._accuracy_stats_cache:
            return

        self._learning_stats_loading.add(vacuum_entity_id)

        def _load_sync() -> tuple[dict[str, Any], dict[str, Any]]:
            room_stats_data = self.store.load_room_stats(vacuum_entity_id=vacuum_entity_id) or {}
            accuracy_stats = self.estimator._load_accuracy_stats(
                vacuum_entity_id=vacuum_entity_id
            ) or {}
            return room_stats_data, accuracy_stats

        async def _load() -> None:
            try:
                room_stats_data, accuracy_stats = await self.hass.async_add_executor_job(_load_sync)
                self._room_stats_cache[vacuum_entity_id] = (
                    room_stats_data if isinstance(room_stats_data, dict) else {}
                )
                self._accuracy_stats_cache[vacuum_entity_id] = (
                    accuracy_stats if isinstance(accuracy_stats, dict) else {}
                )
            except Exception:
                _LOGGER.exception("Failed to preload learning stats for %s", vacuum_entity_id)
                self._room_stats_cache.setdefault(vacuum_entity_id, {})
                self._accuracy_stats_cache.setdefault(vacuum_entity_id, {})
            finally:
                self._learning_stats_loading.discard(vacuum_entity_id)

        self.hass.loop.call_soon_threadsafe(self.hass.async_create_task, _load())

    def save_live_snapshot_from_manager(
        self,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        started_at: str,
        battery_start: int,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Save a live job snapshot from current integration manager state."""
        queue_state = manager.get_queue_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        payload_state = manager.get_payload_state(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        active_job_state = manager.get_active_job(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        capabilities = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        self.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
        # Payload state is cleared once a job starts, so pass resolved_rooms
        # from active_job directly to avoid a no_payload error on the snapshot.
        _snapshot_rooms = (
            list(active_job_state.get("resolved_rooms", []))
            if isinstance(active_job_state, dict) and active_job_state.get("resolved_rooms")
            else None
        )
        planned_job_estimate = manager.get_planned_job_estimate(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            resolved_rooms=_snapshot_rooms,
        )
        access_graph_context = self._build_access_graph_context(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            queue_state=queue_state,
            payload_state=payload_state,
        )

        adjacency = access_graph_context.pop("_adjacency", [])
        try:
            self.store.save_access_graph_debug(
                vacuum_entity_id=vacuum_entity_id,
                map_id=str(map_id),
                payload={
                    "schema_version": 1,
                    "vacuum_entity_id": vacuum_entity_id,
                    "map_id": str(map_id),
                    "updated_at": _iso_now(),
                    "edge_count": access_graph_context.get("edge_count", 0),
                    "adjacency": adjacency,
                },
            )
        except Exception:  # pragma: no cover - best-effort debug write, logs and swallows
            _LOGGER.exception("Failed to write access graph debug file")

        return self.finalizer.save_live_snapshot(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            queue_state=queue_state,
            payload_state=payload_state,
            active_job_state=active_job_state,
            capabilities=capabilities,
            planned_job_estimate=planned_job_estimate,
            access_graph_context=access_graph_context,
            started_at=started_at,
            battery_start=battery_start,
            job_id=job_id,
        )

    def _build_access_graph_context(
        self,
        *,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        queue_state: dict[str, Any],
        payload_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Build conservative access-graph context for the current queue order."""
        rooms = manager.get_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=str(map_id),
        ).get("rooms", {})
        if not isinstance(rooms, dict):
            rooms = {}

        grants_by_room: dict[int, list[int]] = {}
        room_names: dict[int, str] = {}
        room_slugs: dict[int, str] = {}
        edge_count = 0
        for room_id_key, room_data in rooms.items():
            if not isinstance(room_data, dict):
                continue
            room_id = _safe_int(room_id_key, -1)
            if room_id < 0:
                room_id = _safe_int(room_data.get("room_id", room_data.get("id", -1)), -1)
            if room_id < 0:
                continue
            grants = _normalize_graph_targets(room_data.get("grants_access_to"))
            grants_by_room[room_id] = grants
            room_names[room_id] = str(room_data.get("name", room_id))
            room_slugs[room_id] = str(room_data.get("slug", room_id))
            edge_count += len(grants)

        queue_room_ids = [
            _safe_int(room_id, -1)
            for room_id in list(queue_state.get("queue_room_ids", []))
            if _safe_int(room_id, -1) >= 0
        ]
        if not queue_room_ids:
            resolved_rooms = payload_state.get("resolved_rooms", []) if isinstance(payload_state, dict) else []
            if isinstance(resolved_rooms, list):
                queue_room_ids = [
                    _safe_int(room.get("room_id", room.get("id", -1)), -1)
                    for room in resolved_rooms
                    if isinstance(room, dict) and _safe_int(room.get("room_id", room.get("id", -1)), -1) >= 0
                ]

        pair_count = max(len(queue_room_ids) - 1, 0)
        graph_transition_count = 0
        graph_jump_count = 0

        for index in range(pair_count):
            current_room_id = queue_room_ids[index]
            next_room_id = queue_room_ids[index + 1]
            if next_room_id in grants_by_room.get(current_room_id, []):
                graph_transition_count += 1
            else:
                graph_jump_count += 1

        graph_present = edge_count > 0
        graph_coherence_score = (
            round(graph_transition_count / pair_count, 4)
            if graph_present and pair_count > 0
            else None
        )

        adjacency = [
            {
                "room_id": room_id,
                "name": room_names.get(room_id, str(room_id)),
                "slug": room_slugs.get(room_id, str(room_id)),
                "grants_access_to": [
                    {
                        "room_id": target_id,
                        "name": room_names.get(target_id, str(target_id)),
                        "slug": room_slugs.get(target_id, str(target_id)),
                    }
                    for target_id in grants
                ],
            }
            for room_id, grants in sorted(grants_by_room.items())
        ]

        return {
            "present": graph_present,
            "edge_count": edge_count,
            "pair_count": pair_count,
            "graph_transition_count": graph_transition_count,
            "graph_jump_count": graph_jump_count,
            "graph_coherence_score": graph_coherence_score,
            "queue_room_ids": queue_room_ids,
            "_adjacency": adjacency,
        }

    def finalize_completed_job(
        self,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        battery_start: int,
        battery_end: int,
        started_at: str,
        ended_at: str | None = None,
        used_for_learning: bool = True,
        rebuild_stats: bool = True,
        rebuild_csv: bool = False,
        forced_outcome_status: str | None = None,
        forced_lifecycle_state: str | None = None,
        forced_lifecycle_message: str | None = None,
    ) -> dict[str, Any]:
        """Finalize a completed job from manager state.

        After finalization, automatically records estimate accuracy if a live
        snapshot exists with estimated room data. This keeps the accuracy
        feedback loop running without requiring a separate manual service call.
        """
        result = self.finalizer.finalize_from_manager_state(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            battery_start=battery_start,
            battery_end=battery_end,
            started_at=started_at,
            ended_at=ended_at,
            used_for_learning=used_for_learning,
            rebuild_stats=rebuild_stats,
            rebuild_csv=rebuild_csv,
            forced_outcome_status=forced_outcome_status,
            forced_lifecycle_state=forced_lifecycle_state,
            forced_lifecycle_message=forced_lifecycle_message,
        )

        if rebuild_stats:
            self._reload_learning_stats_now(vacuum_entity_id=vacuum_entity_id)
        else:
            self._invalidate_learning_stats_cache(vacuum_entity_id=vacuum_entity_id)

        # Auto-record estimate accuracy if the snapshot carried estimated minutes.
        # This fires regardless of used_for_learning — accuracy data is still
        # useful even for jobs that are excluded from stat rebuilds.
        accuracy_result = self._auto_record_accuracy(
            result=result,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
        )
        result["accuracy"] = accuracy_result

        return result

    async def async_finalize_completed_job(
        self,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        battery_start: int,
        battery_end: int,
        started_at: str,
        ended_at: str | None = None,
        used_for_learning: bool = True,
        rebuild_stats: bool = True,
        rebuild_csv: bool = False,
        forced_outcome_status: str | None = None,
        forced_lifecycle_state: str | None = None,
        forced_lifecycle_message: str | None = None,
    ) -> dict[str, Any]:
        """Async version of finalize_completed_job — offloads file I/O to executor."""
        ended_at = ended_at or _iso_now()
        inputs = self.finalizer._collect_finalization_inputs(
            manager=manager,
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            battery_start=battery_start,
            started_at=started_at,
            ended_at=ended_at,
            forced_outcome_status=forced_outcome_status,
            forced_lifecycle_state=forced_lifecycle_state,
            forced_lifecycle_message=forced_lifecycle_message,
        )
        result = await self.hass.async_add_executor_job(
            lambda: self.finalizer.finalize_from_inputs(
                inputs=inputs,
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
                battery_start=battery_start,
                battery_end=battery_end,
                started_at=started_at,
                ended_at=ended_at,
                used_for_learning=used_for_learning,
                rebuild_stats=rebuild_stats,
                rebuild_csv=rebuild_csv,
            )
        )
        accuracy_result = await self.hass.async_add_executor_job(
            lambda: self._auto_record_accuracy(
                result=result,
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
            )
        )
        self._invalidate_learning_stats_cache(vacuum_entity_id=vacuum_entity_id)
        if rebuild_stats:
            self.async_preload_learning_stats(vacuum_entity_id=vacuum_entity_id)
        result["accuracy"] = accuracy_result
        return result

    def _auto_record_accuracy(
        self,
        *,
        result: dict[str, Any],
        vacuum_entity_id: str,
        map_id: str,
    ) -> dict[str, Any] | None:
        """Extract estimated vs actual per room from a finalized job result
        and record accuracy automatically.

        Uses the resolved_rooms from the completed job payload (which carries
        the snapshot's estimated values if present) against the actual job
        duration divided equally across rooms — the same approximation used
        by the stats rebuilder while no per-room actual split is available.

        Returns None if there is no usable data to record.
        """
        completed_job = result.get("completed_job", {})
        if not isinstance(completed_job, dict):
            return None

        job_info = completed_job.get("job", {})
        profile = completed_job.get("job_profile", {})

        actual_total_minutes = _safe_float(
            job_info.get("duration_minutes") if isinstance(job_info, dict) else None, 0.0
        )
        resolved_rooms = (
            profile.get("rooms", []) if isinstance(profile, dict) else []
        )

        if not resolved_rooms or actual_total_minutes <= 0:
            return None

        room_count = len(resolved_rooms)
        # Single-room jobs: actual duration IS the room duration — no division
        # needed. This is the highest-quality baseline data available since
        # there is no allocation approximation across rooms.
        # Multi-room jobs: divide equally — same approximation as stats_rebuilder
        # while no per-room actual split is available.
        actual_per_room = actual_total_minutes if room_count == 1 else actual_total_minutes / room_count
        map_id_int = _safe_int(map_id)

        room_actuals: list[dict[str, Any]] = []
        for room in resolved_rooms:
            if not isinstance(room, dict):
                continue

            slug = str(room.get("slug", "")).strip().lower()
            if not slug:
                continue

            # estimated_minutes may be present on the room if the snapshot
            # recorded a pre-job estimate; fall back to actual if not available.
            estimated = _safe_float(
                room.get("estimated_minutes") or room.get("avg_minutes"), 0.0
            )
            if estimated <= 0:
                # No estimate was stored — nothing useful to record.
                continue

            room_actuals.append(
                {
                    "slug": slug,
                    "clean_mode": str(
                        room.get("clean_mode", room.get("effective_mode", "vacuum"))
                    ).strip().lower(),
                    "clean_passes": _safe_int(
                        room.get("clean_passes", room.get("clean_times", 1)), 1
                    ),
                    "is_carpet": bool(room.get("carpet", False)) or str(room.get("floor_type", "")).startswith("carpet"),
                    "clean_intensity": str(
                        room.get("clean_intensity", "standard")
                    ).strip().lower(),
                    "edge_mopping": bool(room.get("edge_mopping", False)),
                    "map_id": map_id_int,
                    "estimated_minutes": estimated,
                    "actual_minutes": actual_per_room,
                    # single_room=True means actual_minutes is exact, not allocated.
                    # The accuracy store uses this to weight high-quality observations.
                    "single_room": room_count == 1,
                }
            )

        if not room_actuals:
            return None

        return self.estimator.record_estimate_accuracy(
            vacuum_entity_id=vacuum_entity_id,
            room_actuals=room_actuals,
        )

    def rebuild_learning(
        self,
        vacuum_entity_id: str,
        rebuild_csv: bool = False,
    ) -> dict[str, Any]:
        """Rebuild learned stats and optional CSV exports."""
        result = self.rebuilder.rebuild_all(
            vacuum_entity_id=vacuum_entity_id,
            rebuild_csv=rebuild_csv,
        )
        return result

    def get_learning_history_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        room_slug: str | None = None,
        profile_key: str | None = None,
        status: str | None = None,
        used_for_learning: bool | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a card-friendly learning history snapshot from rebuilt files."""
        room_slug_filter = str(room_slug or "").strip().lower() or None
        profile_key_filter = str(profile_key or "").strip().lower() or None
        status_filter = str(status or "").strip().lower() or None
        limit_value = max(_safe_int(limit, 50), 1)
        built_in_profile_names = set(get_default_room_profiles().keys())

        job_stats = self.store.load_job_stats(vacuum_entity_id=vacuum_entity_id) or {}
        room_stats = self.store.load_room_stats(vacuum_entity_id=vacuum_entity_id) or {}
        jobs_index = self.store.load_jobs_index(vacuum_entity_id=vacuum_entity_id) or {}
        accuracy_stats = self.store.load_accuracy_stats(vacuum_entity_id=vacuum_entity_id) or {}
        archived_jobs = self.store.load_all_completed_jobs(vacuum_entity_id=vacuum_entity_id)
        _index_jobs = jobs_index.get("jobs", [])
        # Require "status" (rich vs the compact room-history shape) AND "origin"
        # (added for the external-run badge + area cell) so an index built before
        # those fields self-heals via ONE rebuild on the next snapshot — this is how
        # OLD graduated external runs shed their stale "Sanity Failed" flag.
        _index_is_new_format = (
            isinstance(_index_jobs, list)
            and bool(_index_jobs)
            and isinstance(_index_jobs[0], dict)
            and "status" in _index_jobs[0]
            and "origin" in _index_jobs[0]
        )
        if archived_jobs and not _index_is_new_format:
            try:
                jobs_index = self.rebuilder.build_jobs_index_payload(
                    vacuum_entity_id=vacuum_entity_id,
                    jobs=archived_jobs,
                )
                self.store.save_jobs_index(
                    vacuum_entity_id=vacuum_entity_id,
                    payload=jobs_index,
                )
            except Exception:  # pragma: no cover - best-effort index persist, in-memory data flows on
                _LOGGER.exception("Failed to rebuild jobs index for %s", vacuum_entity_id)
        archived_job_map = {
            str(job.get("job_id", "")).strip(): job
            for job in archived_jobs
            if isinstance(job, dict) and str(job.get("job_id", "")).strip()
        }
        core_manager = self.hass.data[DOMAIN].get("runtime")

        index_jobs = jobs_index.get("jobs", []) if isinstance(jobs_index.get("jobs"), list) else []
        index_rooms = jobs_index.get("rooms", []) if isinstance(jobs_index.get("rooms"), list) else []
        index_room_profiles = (
            jobs_index.get("room_profiles", [])
            if isinstance(jobs_index.get("room_profiles"), list)
            else []
        )
        exact_room_stats = room_stats.get("room_stats", []) if isinstance(room_stats.get("room_stats"), list) else []
        room_baselines = room_stats.get("room_baselines", []) if isinstance(room_stats.get("room_baselines"), list) else []
        # accuracy_stats["rooms"] is canonically a dict keyed by room_key (see
        # estimator.record_estimate_accuracy / _auto_record_accuracy). Older or
        # externally-produced payloads may use a list, so accept both. Each entry
        # is normalized into the field shape build_trust_metrics expects: the
        # writer stores mean_abs_pct_error as a *fraction* (0.0 = perfect) and
        # does not track confidence_weight, whereas build_trust_metrics reads
        # avg_abs_error_percent (a percent) and confidence_weight.
        raw_accuracy_rooms = accuracy_stats.get("rooms")
        if isinstance(raw_accuracy_rooms, dict):
            accuracy_entries: list[Any] = list(raw_accuracy_rooms.values())
        elif isinstance(raw_accuracy_rooms, list):
            accuracy_entries = raw_accuracy_rooms
        else:
            accuracy_entries = []

        accuracy_by_slug: dict[str, dict[str, Any]] = {}
        for entry in accuracy_entries:
            if not isinstance(entry, dict):
                continue
            slug = str(entry.get("slug", "")).strip().lower()
            if not slug:
                continue
            sample_count = max(_safe_int(entry.get("sample_count"), 0), 0)
            # Prefer an explicit percent if present; otherwise derive it from the
            # canonical fractional mean_abs_pct_error.
            if entry.get("avg_abs_error_percent") is not None:
                avg_abs_error_percent = _safe_float(entry.get("avg_abs_error_percent"), 0.0)
            else:
                avg_abs_error_percent = round(
                    _safe_float(entry.get("mean_abs_pct_error"), 0.0) * 100.0, 2
                )
            # The writer doesn't track confidence_weight; synthesize it from the
            # accuracy sample count (capped at the /5 saturation point used by
            # build_trust_metrics) when absent.
            if entry.get("confidence_weight") is not None:
                confidence_weight = _safe_float(entry.get("confidence_weight"), 0.0)
            else:
                confidence_weight = float(min(sample_count, 5))
            normalized = {
                "slug": slug,
                "sample_count": sample_count,
                "avg_abs_error_percent": avg_abs_error_percent,
                "confidence_weight": confidence_weight,
            }
            current = accuracy_by_slug.get(slug)
            if current is None or sample_count > _safe_int(current.get("sample_count"), 0):
                accuracy_by_slug[slug] = normalized

        def build_trust_metrics(
            *,
            run_count: int,
            learning_run_count: int,
            accuracy_entry: dict[str, Any] | None = None,
            threshold: int = FOUND_PROFILE_TRUST_THRESHOLD,
        ) -> dict[str, Any]:
            """Return normalized trust metrics for a room/profile surface."""
            runs_needed = max(threshold - max(learning_run_count, 0), 0)
            sample_ratio = min(max(learning_run_count, 0) / max(threshold, 1), 1.0)
            accuracy_weight = 0.5
            accuracy_reason = "not_enough_accuracy_data"
            accuracy_sample_count = 0
            avg_abs_error_percent = None
            confidence_weight = None
            if isinstance(accuracy_entry, dict):
                accuracy_sample_count = max(_safe_int(accuracy_entry.get("sample_count"), 0), 0)
                avg_abs_error_percent = _safe_float(accuracy_entry.get("avg_abs_error_percent"), 0.0)
                confidence_weight = _safe_float(accuracy_entry.get("confidence_weight"), 0.0)
                if accuracy_sample_count > 0:
                    accuracy_reason = "accuracy_observed"
                    error_ratio = min(max(avg_abs_error_percent, 0.0) / 100.0, 1.0)
                    confidence_component = min(max((confidence_weight or 0.0) / 5.0, 0.0), 1.0)
                    accuracy_weight = max(min((1.0 - error_ratio) * 0.7 + confidence_component * 0.3, 1.0), 0.0)
            trust_score = round(max(min(sample_ratio * 0.7 + accuracy_weight * 0.3, 1.0), 0.0), 2)
            trust_level = _trust_level_from_score(trust_score)
            if learning_run_count <= 0:
                trust_reason = "no_learning_runs"
            elif runs_needed > 0:
                trust_reason = "building_samples"
            else:
                trust_reason = accuracy_reason
            return {
                "trusted": learning_run_count >= threshold,
                "runs_to_trusted": runs_needed,
                "trust_level": trust_level,
                "trust_score": trust_score,
                "trust_reason": trust_reason,
                "trust_reason_text": _reason_text(trust_reason),
                "accuracy_sample_count": accuracy_sample_count,
                "avg_abs_error_percent": round(avg_abs_error_percent, 2) if avg_abs_error_percent is not None else None,
                "confidence_weight": round(confidence_weight, 2) if confidence_weight is not None else None,
                "run_count": run_count,
                "learning_run_count": learning_run_count,
            }

        def build_metrics_summary(
            items: list[dict[str, Any]],
            *,
            dock_events_payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Return aggregate metrics for a list of enriched jobs."""
            metrics_status_counts: dict[str, int] = {}
            total_duration_minutes = 0.0
            total_battery_used = 0.0
            total_robot_water_used_ml = 0.0
            total_water_overhead_ml = 0.0
            total_water_used_ml = 0.0
            learning_used_count = 0
            excluded_count = 0
            wash_cycle_count = 0
            mid_job_recharge_count = 0

            for item in items:
                status_name = str(item.get("status", "unknown")).strip().lower() or "unknown"
                metrics_status_counts[status_name] = metrics_status_counts.get(status_name, 0) + 1
                total_duration_minutes += _safe_float(item.get("duration_minutes"), 0.0)
                total_battery_used += _safe_float(item.get("battery_used"), 0.0)
                total_robot_water_used_ml += _safe_float(item.get("robot_water_used_ml"), 0.0)
                total_water_overhead_ml += _safe_float(item.get("water_overhead_ml"), 0.0)
                total_water_used_ml += _safe_float(item.get("total_water_used_ml"), 0.0)
                if bool(item.get("used_for_learning", False)):
                    learning_used_count += 1
                if bool(item.get("excluded_from_learning", False)) or not bool(item.get("used_for_learning", True)):
                    excluded_count += 1
                archived = archived_job_map.get(str(item.get("job_id", "")).strip(), {})
                water = archived.get("water", {}) if isinstance(archived.get("water"), dict) else {}
                wash_cycle_count += max(_safe_int(water.get("wash_cycle_count"), 0), 0)
                if bool(item.get("mid_job_recharge_observed", False)):
                    mid_job_recharge_count += 1

            summary = {
                "job_count": len(items),
                "learning_used_count": learning_used_count,
                "excluded_count": excluded_count,
                "status_counts": metrics_status_counts,
                "completed_count": metrics_status_counts.get("completed", 0),
                "cancelled_count": metrics_status_counts.get("cancelled", 0),
                "failed_count": metrics_status_counts.get("failed", 0),
                "interrupted_count": metrics_status_counts.get("interrupted", 0),
                "total_duration_minutes": round(total_duration_minutes, 2),
                "total_battery_used": round(total_battery_used, 2),
                "total_robot_water_used_ml": round(total_robot_water_used_ml, 2),
                "total_water_overhead_ml": round(total_water_overhead_ml, 2),
                "total_water_used_ml": round(total_water_used_ml, 2),
                "wash_cycle_count": wash_cycle_count,
                "mid_job_recharge_count": mid_job_recharge_count,
            }
            if isinstance(dock_events_payload, dict):
                summary["dock"] = {
                    "mop_wash_count": max(_safe_int(dock_events_payload.get("mop_wash_count"), 0), 0),
                    "dust_empty_count": max(_safe_int(dock_events_payload.get("dust_empty_count"), 0), 0),
                    "dry_start_count": max(_safe_int(dock_events_payload.get("dry_start_count"), 0), 0),
                    "last_mop_wash": dock_events_payload.get("last_mop_wash"),
                    "last_dust_empty": dock_events_payload.get("last_dust_empty"),
                    "last_dry_start": dock_events_payload.get("last_dry_start"),
                    "last_dry_duration": dock_events_payload.get("last_dry_duration"),
                    "wash_cycle_count_from_jobs": wash_cycle_count,
                    "total_water_overhead_ml": round(total_water_overhead_ml, 2),
                    "avg_water_overhead_ml_per_job": round(
                        total_water_overhead_ml / max(len(items), 1),
                        2,
                    ) if items else 0.0,
                }
            return summary

        def _job_matches(entry: dict[str, Any]) -> bool:
            if room_slug_filter:
                room_slugs = entry.get("room_slugs", [])
                if not isinstance(room_slugs, list) or room_slug_filter not in {
                    str(item or "").strip().lower() for item in room_slugs
                }:
                    return False
            if status_filter and str(entry.get("status", "")).strip().lower() != status_filter:
                return False
            if used_for_learning is not None and bool(entry.get("used_for_learning", False)) != bool(used_for_learning):
                return False
            return True

        def _room_matches(entry: dict[str, Any]) -> bool:
            return not room_slug_filter or str(entry.get("room_slug", "")).strip().lower() == room_slug_filter

        def _profile_matches(entry: dict[str, Any]) -> bool:
            if room_slug_filter and str(entry.get("room_slug", "")).strip().lower() != room_slug_filter:
                return False
            if profile_key_filter and str(entry.get("profile_key", "")).strip().lower() != profile_key_filter:
                return False
            if status_filter:
                counts = entry.get("status_counts", {})
                if not isinstance(counts, dict) or _safe_int(counts.get(status_filter), 0) <= 0:
                    return False
            if used_for_learning is not None:
                if bool(used_for_learning):
                    return _safe_int(entry.get("learning_run_count"), 0) > 0
                return _safe_int(entry.get("run_count"), 0) > _safe_int(entry.get("learning_run_count"), 0)
            return True

        filtered_jobs = [dict(entry) for entry in index_jobs if isinstance(entry, dict) and _job_matches(entry)]
        filtered_rooms = [dict(entry) for entry in index_rooms if isinstance(entry, dict) and _room_matches(entry)]
        filtered_room_profiles = [
            dict(entry) for entry in index_room_profiles if isinstance(entry, dict) and _profile_matches(entry)
        ]
        filtered_exact_room_stats = [
            dict(entry)
            for entry in exact_room_stats
            if isinstance(entry, dict)
            and (not room_slug_filter or str(entry.get("slug", "")).strip().lower() == room_slug_filter)
        ]
        filtered_room_baselines = [
            dict(entry)
            for entry in room_baselines
            if isinstance(entry, dict)
            and (not room_slug_filter or str(entry.get("slug", "")).strip().lower() == room_slug_filter)
        ]
        filtered_accuracy_rooms = [
            dict(entry)
            for entry in accuracy_entries
            if isinstance(entry, dict)
            and (not room_slug_filter or str(entry.get("slug", "")).strip().lower() == room_slug_filter)
        ]

        filtered_jobs.sort(key=lambda item: str(item.get("ended_at") or item.get("started_at") or ""), reverse=True)
        filtered_room_profiles.sort(
            key=lambda item: (
                str(item.get("room_slug", "")),
                str(item.get("profile_key", "")),
            )
        )

        room_average_map = {
            str(item.get("room_slug", "")).strip().lower(): item
            for item in filtered_rooms
            if isinstance(item, dict)
        }
        profile_average_map = {
            str(item.get("profile_key", "")).strip().lower(): item
            for item in filtered_room_profiles
            if isinstance(item, dict)
        }

        enriched_rooms: list[dict[str, Any]] = []
        for item in filtered_rooms:
            enriched = dict(item)
            enriched["room_label"] = _room_label(item.get("room_slug"))
            run_count = max(_safe_int(item.get("run_count"), 0), 0)
            learning_run_count = max(_safe_int(item.get("learning_run_count"), 0), 0)
            avg_duration = _safe_float(item.get("avg_duration_minutes"), 0.0)
            avg_battery = _safe_float(item.get("avg_battery_used"), 0.0)
            avg_robot_water = _safe_float(item.get("avg_robot_water_used_ml"), 0.0)
            avg_water_overhead = _safe_float(item.get("avg_water_overhead_ml"), 0.0)
            avg_total_water = _safe_float(item.get("avg_total_water_used_ml"), 0.0)
            trust = build_trust_metrics(
                run_count=run_count,
                learning_run_count=learning_run_count,
                accuracy_entry=accuracy_by_slug.get(str(item.get("room_slug", "")).strip().lower()),
            )
            enriched["last_cleaned_at"] = item.get("last_ended_at")
            enriched["exclude_candidate_count"] = max(
                _safe_int(item.get("run_count"), 0) - _safe_int(item.get("learning_run_count"), 0),
                0,
            )
            enriched["total_duration_minutes"] = round(avg_duration * run_count, 2)
            enriched["total_battery_used"] = round(avg_battery * run_count, 2)
            enriched["total_robot_water_used_ml"] = round(avg_robot_water * run_count, 2)
            enriched["total_water_overhead_ml"] = round(avg_water_overhead * run_count, 2)
            enriched["total_water_used_ml"] = round(avg_total_water * run_count, 2)
            enriched.update(trust)
            enriched_rooms.append(enriched)

        enriched_room_profiles: list[dict[str, Any]] = []
        # Adapter-owned display-string -> canonical-code maps. The observed
        # profile settings are stored un-normalized; normalizing here means the
        # card always receives a code its vocab is keyed on (no English leak).
        _facts = brand_facts_for(vacuum_entity_id)
        _clean_mode_aliases = _facts.alias_map("clean_mode")
        _clean_intensity_aliases = _facts.alias_map("clean_intensity")
        _fan_speed_aliases = _facts.alias_map("fan_speed")
        _water_level_aliases = _facts.alias_map("water_level")
        for item in filtered_room_profiles:
            enriched = dict(item)
            enriched["room_label"] = _room_label(item.get("room_slug"))
            run_count = max(_safe_int(item.get("run_count"), 0), 0)
            avg_duration = _safe_float(item.get("avg_duration_minutes"), 0.0)
            avg_battery = _safe_float(item.get("avg_battery_used"), 0.0)
            avg_robot_water = _safe_float(item.get("avg_robot_water_used_ml"), 0.0)
            avg_water_overhead = _safe_float(item.get("avg_water_overhead_ml"), 0.0)
            avg_total_water = _safe_float(item.get("avg_total_water_used_ml"), 0.0)
            enriched["last_cleaned_at"] = item.get("last_ended_at")
            room_avg = room_average_map.get(str(item.get("room_slug", "")).strip().lower(), {})
            room_duration_avg = _safe_float(room_avg.get("avg_duration_minutes"), 0.0)
            room_water_avg = _safe_float(room_avg.get("avg_total_water_used_ml"), 0.0)
            profile_duration_avg = _safe_float(item.get("avg_duration_minutes"), 0.0)
            profile_water_avg = _safe_float(item.get("avg_total_water_used_ml"), 0.0)
            learning_run_count = _safe_int(item.get("learning_run_count"), 0)
            trust = build_trust_metrics(
                run_count=run_count,
                learning_run_count=learning_run_count,
                accuracy_entry=accuracy_by_slug.get(str(item.get("room_slug", "")).strip().lower()),
            )
            selected_profile_name = str(item.get("selected_profile_name", "")).strip().lower()
            resolved_profile_name = str(item.get("resolved_profile_name", "")).strip().lower()
            is_builtin_selected = selected_profile_name in built_in_profile_names
            is_builtin_resolved = resolved_profile_name in built_in_profile_names
            custom_observed = (
                not is_builtin_selected
                or selected_profile_name != resolved_profile_name
                or selected_profile_name in {"custom", "user_1", ""}
            )
            suggested_label_parts = [
                str(item.get("room_slug", "")).strip().replace("_", " ").title(),
                str(item.get("clean_mode", "")).strip().replace("_", " ").title(),
            ]
            if str(item.get("clean_intensity", "")).strip():
                suggested_label_parts.append(str(item.get("clean_intensity", "")).strip().title())
            if _safe_int(item.get("clean_passes"), 1) > 1:
                suggested_label_parts.append(f"{_safe_int(item.get('clean_passes'), 1)} Pass")
            suggested_label = " ".join(part for part in suggested_label_parts if part).strip() or "Observed Profile"
            profile_display = _settings_profile_label(
                room_slug=item.get("room_slug"),
                selected_profile_name=item.get("selected_profile_name"),
                resolved_profile_name=item.get("resolved_profile_name"),
                clean_mode=item.get("clean_mode"),
                clean_intensity=item.get("clean_intensity"),
                fan_speed=item.get("fan_speed"),
                water_level=item.get("water_level"),
                clean_passes=item.get("clean_passes"),
                edge_mopping=item.get("edge_mopping"),
            )
            enriched["avg_duration_delta_from_room"] = round(profile_duration_avg - room_duration_avg, 2)
            enriched["avg_water_delta_from_room"] = round(profile_water_avg - room_water_avg, 2)
            enriched["total_duration_minutes"] = round(avg_duration * run_count, 2)
            enriched["total_battery_used"] = round(avg_battery * run_count, 2)
            enriched["total_robot_water_used_ml"] = round(avg_robot_water * run_count, 2)
            enriched["total_water_overhead_ml"] = round(avg_water_overhead * run_count, 2)
            enriched["total_water_used_ml"] = round(avg_total_water * run_count, 2)
            enriched.update(trust)
            enriched["save_candidate"] = True
            enriched["save_candidate_kind"] = "custom_profile" if custom_observed else "preset_variant"
            enriched["save_suggested_label"] = suggested_label
            enriched.update(profile_display)
            # Normalize the flat setting CODES the card reads (via _localizedProfile)
            # to canonical form. The English *_label fallbacks computed above keep
            # the original display string, so degradation is unaffected.
            enriched["clean_mode"] = _normalize_profile_setting(item.get("clean_mode"), _clean_mode_aliases)
            enriched["clean_intensity"] = _normalize_profile_setting(item.get("clean_intensity"), _clean_intensity_aliases)
            enriched["fan_speed"] = _normalize_profile_setting(item.get("fan_speed"), _fan_speed_aliases)
            enriched["water_level"] = _normalize_profile_setting(item.get("water_level"), _water_level_aliases)
            enriched["save_supported"] = False
            enriched["save_service"] = None
            enriched["save_service_data"] = None
            enriched["found_profile"] = {
                "available": True,
                "profile_key": item.get("profile_key"),
                "room_slug": item.get("room_slug"),
                "selected_profile_name": item.get("selected_profile_name"),
                "resolved_profile_name": item.get("resolved_profile_name"),
                "kind": "custom_profile" if custom_observed else "preset_variant",
                "suggested_label": suggested_label,
                "profile_label": profile_display.get("profile_label"),
                "profile_subtitle": profile_display.get("profile_subtitle"),
                "selected_profile_label": profile_display.get("selected_profile_label"),
                "resolved_profile_label": profile_display.get("resolved_profile_label"),
                "is_custom_profile": profile_display.get("is_custom_profile"),
                "trusted": trust["trusted"],
                "runs_to_trusted": trust["runs_to_trusted"],
                "trust_level": trust["trust_level"],
                "trust_score": trust["trust_score"],
                "trust_reason": trust["trust_reason"],
                "trust_reason_text": trust.get("trust_reason_text"),
                "settings": {
                    "clean_mode": item.get("clean_mode"),
                    "clean_intensity": item.get("clean_intensity"),
                    "fan_speed": item.get("fan_speed"),
                    "water_level": item.get("water_level"),
                    "clean_passes": _safe_int(item.get("clean_passes"), 1),
                    "edge_mopping": bool(item.get("edge_mopping", False)),
                    "carpet": bool(item.get("is_carpet", item.get("carpet", False))),
                },
                "save_supported": False,
                "save_service": None,
                "save_service_data": None,
            }
            enriched_room_profiles.append(enriched)

        enriched_jobs: list[dict[str, Any]] = []
        for item in filtered_jobs:
            enriched = dict(item)
            job_id = str(item.get("job_id", "")).strip()
            archived = archived_job_map.get(job_id, {})
            outcome = archived.get("outcome", {}) if isinstance(archived.get("outcome"), dict) else {}

            exclude_allowed = bool(item.get("used_for_learning", False))
            exclude_reason = str(outcome.get("excluded_reason", "")).strip() or None
            excluded_from_learning = bool(outcome.get("excluded_from_learning", False))
            restore_allowed = excluded_from_learning or not bool(item.get("used_for_learning", True))
            restore_reason = (
                exclude_reason
                or ("excluded_from_learning" if excluded_from_learning else None)
            )
            learning_blockers = outcome.get("learning_blockers", []) if isinstance(outcome.get("learning_blockers"), list) else []
            sanity_flags = outcome.get("sanity_flags", []) if isinstance(outcome.get("sanity_flags"), list) else []

            room_slugs = item.get("room_slugs", []) if isinstance(item.get("room_slugs"), list) else []
            primary_room_slug = str(room_slugs[0]).strip().lower() if room_slugs else ""
            room_avg = room_average_map.get(primary_room_slug, {})
            profile_key = None
            profile_settings: dict[str, Any] | None = None
            if len(room_slugs) == 1:
                archived_profile = archived.get("job_profile", {}) if isinstance(archived.get("job_profile"), dict) else {}
                archived_rooms = archived_profile.get("rooms", []) if isinstance(archived_profile.get("rooms"), list) else []
                if archived_rooms and isinstance(archived_rooms[0], dict):
                    room = archived_rooms[0]
                    profile_key = _room_profile_key(room)
                    profile_settings = room
                    profile_display = _settings_profile_label(
                        room_slug=primary_room_slug,
                        selected_profile_name=room.get("selected_profile_name"),
                        resolved_profile_name=room.get("resolved_profile_name"),
                        clean_mode=room.get("clean_mode"),
                        clean_intensity=room.get("clean_intensity"),
                        fan_speed=room.get("fan_speed"),
                        water_level=room.get("water_level"),
                        clean_passes=room.get("clean_passes", room.get("clean_times", 1)),
                        edge_mopping=room.get("edge_mopping"),
                    )
                else:
                    profile_display = _settings_profile_label(room_slug=primary_room_slug)
            else:
                profile_display = _settings_profile_label(room_slug=primary_room_slug)
            profile_avg = profile_average_map.get(str(profile_key or "").strip().lower(), {})

            duration_minutes = _safe_float(item.get("duration_minutes"), 0.0)
            room_duration_avg = _safe_float(room_avg.get("avg_duration_minutes"), 0.0)
            profile_duration_avg = _safe_float(profile_avg.get("avg_duration_minutes"), 0.0)
            duration_vs_room_avg = round(duration_minutes - room_duration_avg, 2) if room_duration_avg > 0 else None
            duration_vs_profile_avg = round(duration_minutes - profile_duration_avg, 2) if profile_duration_avg > 0 else None
            room_count = max(_safe_int(item.get("room_count"), 0), 0)
            is_single_room = room_count == 1
            is_multi_room = room_count > 1
            job_scope = "single_room" if is_single_room else "multi_room" if is_multi_room else "unknown"
            raw_room_slugs = item.get("room_slugs", [])
            room_slugs = raw_room_slugs if isinstance(raw_room_slugs, list) else []
            room_labels = [
                _room_label(slug) or str(slug).strip()
                for slug in room_slugs
                if str(slug or "").strip()
            ]

            short_vs_profile = (
                is_single_room
                and profile_duration_avg > 0
                and duration_minutes > 0
                and duration_minutes <= profile_duration_avg * 0.35
            )
            short_vs_room = (
                is_single_room
                and room_duration_avg > 0
                and duration_minutes > 0
                and duration_minutes <= room_duration_avg * 0.35
            )

            outlier_score = 0.0
            # Only an EXPLICIT False is a sanity failure. A missing/None value (e.g.
            # graduated external runs that don't carry the key) must NOT count as
            # failed — the index stores the key as None, so a `.get(key, True)` default
            # never fired and flagged every such run.
            if item.get("sanity_passed") is False:
                outlier_score += 3.0
            if str(item.get("status", "")).strip().lower() != "completed":
                outlier_score += 2.0
            if duration_vs_profile_avg is not None and profile_duration_avg > 0:
                outlier_score += min(abs(duration_vs_profile_avg) / max(profile_duration_avg, 1.0), 3.0)
            elif duration_vs_room_avg is not None and room_duration_avg > 0:
                outlier_score += min(abs(duration_vs_room_avg) / max(room_duration_avg, 1.0), 2.0)
            if excluded_from_learning:
                outlier_score += 1.0

            exclude_suggested = False
            exclude_suggested_reason = None
            cancel_detection = item.get("cancel_detection", {}) if isinstance(item.get("cancel_detection"), dict) else {}
            if isinstance(cancel_detection, dict):
                cancel_reason = cancel_detection.get("reason")
                cancel_detection = {
                    **cancel_detection,
                    "reason_label": _display_label(cancel_reason),
                    "reason_text": _reason_text(cancel_reason),
                }
            if exclude_allowed:
                if str(item.get("status", "")).strip().lower() in {"cancelled", "failed", "interrupted"}:
                    exclude_suggested = True
                    exclude_suggested_reason = str(item.get("status", "")).strip().lower()
                elif item.get("sanity_passed") is False:
                    exclude_suggested = True
                    exclude_suggested_reason = "failed_sanity"
                elif bool(cancel_detection.get("cancel_likely")):
                    exclude_suggested = True
                    exclude_suggested_reason = str(cancel_detection.get("reason", "cancel_like")).strip() or "cancel_like"
                elif short_vs_profile:
                    exclude_suggested = True
                    exclude_suggested_reason = "short_duration_vs_profile"
                elif short_vs_room:
                    exclude_suggested = True
                    exclude_suggested_reason = "short_duration_vs_room"

            enriched.update(
                {
                    "exclude_allowed": exclude_allowed,
                    "exclude_reason": exclude_reason,
                    "exclude_reason_label": _display_label(exclude_reason),
                    "exclude_reason_text": _reason_text(exclude_reason),
                    "excluded_from_learning": excluded_from_learning,
                    "restore_allowed": restore_allowed,
                    "restore_reason": restore_reason,
                    "restore_reason_label": _display_label(restore_reason),
                    "restore_reason_text": _reason_text(restore_reason),
                    "exclude_suggested": exclude_suggested,
                    "exclude_suggested_reason": exclude_suggested_reason,
                    "exclude_suggested_reason_label": _display_label(exclude_suggested_reason),
                    "exclude_suggested_reason_text": _reason_text(exclude_suggested_reason),
                    "learning_blockers": learning_blockers,
                    "learning_blocker_labels": [_display_label(item) for item in learning_blockers if _display_label(item)],
                    "learning_blocker_texts": [_reason_text(item) for item in learning_blockers if _reason_text(item)],
                    "sanity_flags": sanity_flags,
                    "sanity_flag_labels": [_display_label(item) for item in sanity_flags if _display_label(item)],
                    "sanity_flag_texts": [_reason_text(item) for item in sanity_flags if _reason_text(item)],
                    "outlier_score": round(outlier_score, 2),
                    "duration_vs_room_avg_minutes": duration_vs_room_avg,
                    "duration_vs_profile_avg_minutes": duration_vs_profile_avg,
                    "primary_room_slug": primary_room_slug or None,
                    "primary_room_label": _room_label(primary_room_slug),
                    "room_labels": room_labels,
                    "room_labels_display": ", ".join(room_labels) if room_labels else None,
                    "profile_key": profile_key,
                    "job_scope": job_scope,
                    "is_single_room": is_single_room,
                    "is_multi_room": is_multi_room,
                    "status_label": _display_label(item.get("status")),
                    "status_text": _reason_text(item.get("status")),
                    "trust_level_label": _display_label(item.get("trust_level")),
                    "profile_label": profile_display.get("profile_label"),
                    "profile_subtitle": profile_display.get("profile_subtitle"),
                    "selected_profile_label": profile_display.get("selected_profile_label"),
                    "resolved_profile_label": profile_display.get("resolved_profile_label"),
                    "is_custom_profile": profile_display.get("is_custom_profile"),
                }
            )
            # Flat setting CODES so the card localizes the job's profile in the
            # user's (per-user globe) language via _localizedProfile — the same
            # treatment the profile-aggregate / found_profile path gets above. Only
            # single-room jobs have one profile; multi-room jobs keep the composed
            # English fallback (_localizedProfile degrades to profile_label).
            if profile_settings is not None:
                enriched["room_label"] = _room_label(primary_room_slug)
                enriched["selected_profile_name"] = profile_settings.get("selected_profile_name")
                enriched["resolved_profile_name"] = profile_settings.get("resolved_profile_name")
                enriched["clean_mode"] = _normalize_profile_setting(profile_settings.get("clean_mode"), _clean_mode_aliases)
                enriched["clean_intensity"] = _normalize_profile_setting(profile_settings.get("clean_intensity"), _clean_intensity_aliases)
                enriched["fan_speed"] = _normalize_profile_setting(profile_settings.get("fan_speed"), _fan_speed_aliases)
                enriched["water_level"] = _normalize_profile_setting(profile_settings.get("water_level"), _water_level_aliases)
                enriched["clean_passes"] = _safe_int(profile_settings.get("clean_passes", profile_settings.get("clean_times", 1)), 1)
                enriched["edge_mopping"] = bool(profile_settings.get("edge_mopping", False))
            enriched_jobs.append(enriched)

        selected_room = filtered_rooms[0] if room_slug_filter and filtered_rooms else None
        selected_profile = filtered_room_profiles[0] if profile_key_filter and filtered_room_profiles else None
        if isinstance(selected_room, dict):
            selected_room = next((item for item in enriched_rooms if item.get("room_slug") == selected_room.get("room_slug")), selected_room)
        if isinstance(selected_profile, dict):
            selected_profile = next((item for item in enriched_room_profiles if item.get("profile_key") == selected_profile.get("profile_key")), selected_profile)

        found_profiles = [
            {
                "profile_key": item.get("profile_key"),
                "room_slug": item.get("room_slug"),
                "room_label": item.get("room_label"),
                "selected_profile_name": item.get("selected_profile_name"),
                "resolved_profile_name": item.get("resolved_profile_name"),
                # Raw settings codes (also in nested "settings" below) flattened so
                # the card's _localizedProfile can recompose a localized label —
                # mirrors the profile_filter_options passthrough.
                "clean_mode": item.get("clean_mode"),
                "clean_intensity": item.get("clean_intensity"),
                "fan_speed": item.get("fan_speed"),
                "water_level": item.get("water_level"),
                "clean_passes": item.get("clean_passes"),
                "edge_mopping": item.get("edge_mopping"),
                "run_count": _safe_int(item.get("run_count"), 0),
                "learning_run_count": _safe_int(item.get("learning_run_count"), 0),
                "trusted": bool(item.get("trusted", False)),
                "runs_to_trusted": _safe_int(item.get("runs_to_trusted"), 0),
                "trust_level": item.get("trust_level"),
                "trust_score": item.get("trust_score"),
                "trust_reason": item.get("trust_reason"),
                "trust_reason_text": item.get("trust_reason_text"),
                "save_candidate": bool(item.get("save_candidate", False)),
                "save_candidate_kind": item.get("save_candidate_kind"),
                "save_suggested_label": item.get("save_suggested_label"),
                "profile_label": item.get("profile_label"),
                "profile_subtitle": item.get("profile_subtitle"),
                "selected_profile_label": item.get("selected_profile_label"),
                "resolved_profile_label": item.get("resolved_profile_label"),
                "is_custom_profile": item.get("is_custom_profile"),
                "settings": (
                    dict(item.get("found_profile", {}).get("settings", {}))
                    if isinstance(item.get("found_profile"), dict)
                    else {}
                ),
                "last_cleaned_at": item.get("last_cleaned_at"),
            }
            for item in enriched_room_profiles
        ]

        dock_events = (
            core_manager.get_dock_events(vacuum_entity_id=vacuum_entity_id)
            if core_manager is not None
            else {}
        )
        if not isinstance(dock_events, dict):
            dock_events = {}
        metrics_summary = build_metrics_summary(enriched_jobs, dock_events_payload=dock_events)
        metrics_summary["room_count"] = len(enriched_rooms)
        metrics_summary["room_profile_count"] = len(enriched_room_profiles)

        now_utc = utc_now()
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        last_7_days_start = now_utc - timedelta(days=7)
        last_30_days_start = now_utc - timedelta(days=30)

        def _filter_jobs_since(since: datetime) -> list[dict[str, Any]]:
            filtered: list[dict[str, Any]] = []
            for item in enriched_jobs:
                ended_at = _parse_local_timestamp(item.get("ended_at"))
                started_at = _parse_local_timestamp(item.get("started_at"))
                anchor = ended_at or started_at
                if anchor is not None and anchor >= since:
                    filtered.append(item)
            return filtered

        metrics_windows = {
            "today": build_metrics_summary(_filter_jobs_since(today_start)),
            "last_7_days": build_metrics_summary(_filter_jobs_since(last_7_days_start)),
            "last_30_days": build_metrics_summary(_filter_jobs_since(last_30_days_start)),
        }

        room_filter_options = sorted(
            [
                {
                    "value": str(item.get("room_slug", "")).strip().lower(),
                    "label": _room_label(item.get("room_slug")) or str(item.get("room_slug", "")).strip(),
                }
                for item in index_rooms
                if isinstance(item, dict) and str(item.get("room_slug", "")).strip()
            ],
            key=lambda item: str(item.get("label", "")),
        )

        profile_filter_source = [
            item
            for item in enriched_room_profiles
            if not room_slug_filter
            or str(item.get("room_slug", "")).strip().lower() == room_slug_filter
        ]
        profile_filter_options = sorted(
            [
                {
                    "value": str(item.get("profile_key", "")).strip().lower(),
                    "label": item.get("profile_label")
                    or item.get("selected_profile_label")
                    or item.get("resolved_profile_label")
                    or str(item.get("profile_key", "")).strip(),
                    "subtitle": item.get("profile_subtitle"),
                    "room_slug": item.get("room_slug"),
                    "room_label": item.get("room_label"),
                    # Raw settings codes so the CARD can recompose a localized
                    # label/subtitle in the per-user language. The label/subtitle
                    # above stay as the English fallback; value(=profile_key) is
                    # untouched so filtering still targets the exact variant.
                    "selected_profile_name": item.get("selected_profile_name"),
                    "resolved_profile_name": item.get("resolved_profile_name"),
                    "clean_mode": item.get("clean_mode"),
                    "clean_intensity": item.get("clean_intensity"),
                    "fan_speed": item.get("fan_speed"),
                    "water_level": item.get("water_level"),
                    "clean_passes": item.get("clean_passes"),
                    "edge_mopping": item.get("edge_mopping"),
                }
                for item in profile_filter_source
                if isinstance(item, dict) and str(item.get("profile_key", "")).strip()
            ],
            key=lambda item: (
                str(item.get("room_label", "")),
                str(item.get("label", "")),
            ),
        )

        status_filter_options = sorted(
            [
                {
                    "value": status_name,
                    "label": _display_label(status_name) or status_name,
                }
                for status_name in {
                    str(item.get("status", "")).strip().lower()
                    for item in enriched_jobs
                    if isinstance(item, dict) and str(item.get("status", "")).strip()
                }
            ],
            key=lambda item: str(item.get("label", "")),
        )

        used_for_learning_filter_options = [
            {
                "value": True,
                "value_key": "true",
                "label": "Used For Learning",
            },
            {
                "value": False,
                "value_key": "false",
                "label": "Excluded From Learning",
            },
        ]

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "available": bool(job_stats or room_stats or jobs_index or accuracy_stats),
            "reason": "ready" if (job_stats or room_stats or jobs_index or accuracy_stats) else "no_learning_data",
            "message": (
                "Learning history snapshot ready."
                if (job_stats or room_stats or jobs_index or accuracy_stats)
                else "No learned history is available yet."
            ),
            "filters": {
                "room_slug": room_slug_filter,
                "profile_key": profile_key_filter,
                "status": status_filter,
                "used_for_learning": used_for_learning,
                "limit": limit_value,
            },
            "filter_options": {
                "rooms": room_filter_options,
                "profiles": profile_filter_options,
                "statuses": status_filter_options,
                "used_for_learning": used_for_learning_filter_options,
            },
            "summary": {
                "job_stats": job_stats.get("job_stats", {}) if isinstance(job_stats.get("job_stats"), dict) else {},
                "job_count": _safe_int(jobs_index.get("job_count"), len(index_jobs)),
                "filtered_job_count": len(filtered_jobs),
                "filtered_room_count": len(filtered_rooms),
                "filtered_room_profile_count": len(filtered_room_profiles),
                "selected_room": selected_room,
                "selected_profile": selected_profile,
                "metrics": metrics_summary,
                "metric_windows": metrics_windows,
            },
            "jobs": enriched_jobs[:limit_value],
            "rooms": enriched_rooms,
            "room_profiles": enriched_room_profiles,
            "found_profiles": found_profiles,
            "room_learning_stats": {
                "exact": filtered_exact_room_stats,
                "baselines": filtered_room_baselines,
                "accuracy": filtered_accuracy_rooms,
            },
            "sources": {
                "jobs_index_rebuilt_at": jobs_index.get("rebuilt_at"),
                "job_stats_rebuilt_at": job_stats.get("rebuilt_at"),
                "room_stats_rebuilt_at": room_stats.get("rebuilt_at"),
                "accuracy_stats_updated_at": accuracy_stats.get("updated_at"),
            },
            "updated_at": _iso_now(),
        }

    def get_metrics_snapshot(
        self,
        *,
        vacuum_entity_id: str,
        room_slug: str | None = None,
        profile_key: str | None = None,
        status: str | None = None,
        used_for_learning: bool | None = None,
    ) -> dict[str, Any]:
        """Return a metrics-focused snapshot without the job review list."""
        snapshot = self.get_learning_history_snapshot(
            vacuum_entity_id=vacuum_entity_id,
            room_slug=room_slug,
            profile_key=profile_key,
            status=status,
            used_for_learning=used_for_learning,
            limit=1,
        )
        summary = snapshot.get("summary", {}) if isinstance(snapshot.get("summary"), dict) else {}

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "available": bool(snapshot.get("available", False)),
            "reason": snapshot.get("reason"),
            "message": (
                "Metrics snapshot ready."
                if bool(snapshot.get("available", False))
                else snapshot.get("message")
            ),
            "filters": {
                "room_slug": snapshot.get("filters", {}).get("room_slug"),
                "profile_key": snapshot.get("filters", {}).get("profile_key"),
                "status": snapshot.get("filters", {}).get("status"),
                "used_for_learning": snapshot.get("filters", {}).get("used_for_learning"),
            },
            "filter_options": snapshot.get("filter_options", {}),
            "overview": {
                "job_stats": summary.get("job_stats", {}),
                "metrics": summary.get("metrics", {}),
                "metric_windows": summary.get("metric_windows", {}),
            },
            "selection": {
                "selected_room": summary.get("selected_room"),
                "selected_profile": summary.get("selected_profile"),
            },
            "rooms": snapshot.get("rooms", []),
            "room_profiles": snapshot.get("room_profiles", []),
            "found_profiles": snapshot.get("found_profiles", []),
            "room_learning_stats": snapshot.get("room_learning_stats", {}),
            "sources": snapshot.get("sources", {}),
            "updated_at": snapshot.get("updated_at"),
        }

    def get_incomplete_run_log(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the last incomplete run log for a vacuum, or None if none exists."""
        return self.store.load_incomplete_run(vacuum_entity_id=vacuum_entity_id)

    def clear_incomplete_run_log(self, *, vacuum_entity_id: str) -> None:
        """Delete the incomplete run log file for a vacuum."""
        self.store.clear_incomplete_run(vacuum_entity_id=vacuum_entity_id)

    def get_trouble_rooms_log(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any] | None:
        """Return the chronic trouble rooms log for a vacuum, or None if none exists."""
        return self.store.load_trouble_rooms(vacuum_entity_id=vacuum_entity_id)

    def exclude_learning_job(
        self,
        *,
        vacuum_entity_id: str,
        job_id: str,
        reason: str | None = None,
        rebuild_csv: bool = False,
    ) -> dict[str, Any]:
        """Exclude one archived completed job from learning without deleting it."""
        job = self.store.load_completed_job(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
        )
        if not isinstance(job, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "job_id": job_id,
                "excluded": False,
                "reason": "job_not_found",
                "message": "Completed job was not found.",
            }

        outcome = job.get("outcome", {})
        if not isinstance(outcome, dict):
            outcome = {}

        exclusion_reason = str(reason or "manual_exclusion").strip() or "manual_exclusion"
        learning_blockers = outcome.get("learning_blockers", [])
        if not isinstance(learning_blockers, list):
            learning_blockers = []
        learning_blockers.extend(["manually_excluded", exclusion_reason])

        outcome["used_for_learning"] = False
        outcome["excluded_from_learning"] = True
        outcome["excluded_reason"] = exclusion_reason
        outcome["excluded_at"] = _iso_now()
        outcome["learning_blockers"] = sorted(
            set(str(item) for item in learning_blockers if str(item).strip())
        )
        job["outcome"] = outcome

        path = self.store.save_completed_job(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
            payload=job,
        )
        rebuild_result = self.rebuilder.rebuild_all(
            vacuum_entity_id=vacuum_entity_id,
            rebuild_csv=rebuild_csv,
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "job_id": job_id,
            "excluded": True,
            "reason": "excluded",
            "message": "Completed job excluded from learning and stats rebuilt.",
            "job_path": str(path),
            "completed_job": job,
            "rebuild": rebuild_result,
        }

    def restore_learning_job(
        self,
        *,
        vacuum_entity_id: str,
        job_id: str,
        rebuild_csv: bool = False,
    ) -> dict[str, Any]:
        """Restore one archived completed job back into learning."""
        job = self.store.load_completed_job(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
        )
        if not isinstance(job, dict):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "job_id": job_id,
                "restored": False,
                "reason": "job_not_found",
                "message": "Completed job was not found.",
            }

        outcome = job.get("outcome", {})
        if not isinstance(outcome, dict):
            outcome = {}

        learning_blockers = outcome.get("learning_blockers", [])
        if not isinstance(learning_blockers, list):
            learning_blockers = []
        normalized_blockers = [
            str(item).strip()
            for item in learning_blockers
            if str(item).strip()
            and str(item).strip() not in {"manually_excluded", "manual_exclusion"}
            and str(item).strip() != str(outcome.get("excluded_reason", "")).strip()
        ]

        outcome["used_for_learning"] = True
        outcome["excluded_from_learning"] = False
        outcome["excluded_reason"] = None
        outcome["excluded_at"] = None
        outcome["learning_blockers"] = sorted(set(normalized_blockers))
        job["outcome"] = outcome

        path = self.store.save_completed_job(
            vacuum_entity_id=vacuum_entity_id,
            job_id=job_id,
            payload=job,
        )
        rebuild_result = self.rebuilder.rebuild_all(
            vacuum_entity_id=vacuum_entity_id,
            rebuild_csv=rebuild_csv,
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "job_id": job_id,
            "restored": True,
            "reason": "restored",
            "message": "Completed job restored into learning and stats rebuilt.",
            "job_path": str(path),
            "completed_job": job,
            "rebuild": rebuild_result,
        }

    def estimate_from_manager(
        self,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        current_battery: float = 0.0,
        charge_percent_per_minute: float = 1.0,
        reserve_battery_percent: float = 5.0,
        started_at: str | None = None,
        resolved_rooms: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run a live estimate from manager state.

        Pulls payload state to get the ordered room list — the single source
        of truth for room execution order. Normalizes each room into the shape
        the estimator expects, then delegates all math.

        If resolved_rooms is provided it is used directly, bypassing the
        payload state lookup. This allows callers with an active job snapshot
        to produce a timeline even after the queue/payload has been cleared.
        """
        if resolved_rooms is None:
            payload_state = manager.get_payload_state(
                vacuum_entity_id=vacuum_entity_id,
                map_id=map_id,
            )
            resolved_rooms = payload_state.get("resolved_rooms", [])

        ordered_rooms: list[dict[str, Any]] = []
        for room in resolved_rooms:
            ordered_rooms.append(
                {
                    "room_id": _safe_int(room.get("room_id", room.get("id", 0))),
                    "name": str(room.get("name", room.get("slug", ""))),
                    "slug": str(room.get("slug", "")).strip().lower(),
                    "clean_mode": str(room.get("clean_mode", "vacuum")).strip().lower(),
                    "clean_passes": _safe_int(room.get("clean_passes", 1), 1),
                    "clean_intensity": str(room.get("clean_intensity", "standard")).strip().lower(),
                    "carpet": bool(room.get("carpet", False)) or str(room.get("floor_type", "")).startswith("carpet"),
                }
            )

        return self.estimator.estimate(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id,
            ordered_rooms=ordered_rooms,
            started_at=started_at,
            current_battery=current_battery,
            charge_percent_per_minute=charge_percent_per_minute,
            reserve_battery_percent=reserve_battery_percent,
        )

    def record_estimate_accuracy(
        self,
        vacuum_entity_id: str,
        room_actuals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Record estimated vs actual minutes per room after a job completes.

        Each entry in room_actuals must have:
          slug, clean_mode, clean_passes, is_carpet, clean_intensity,
          estimated_minutes, actual_minutes, map_id.

        Delegates entirely to the estimator — no math here.
        """
        return self.estimator.record_estimate_accuracy(
            vacuum_entity_id=vacuum_entity_id,
            room_actuals=room_actuals,
        )


    def get_room_learning_estimates(
        self,
        manager,
        vacuum_entity_id: str,
        map_id: str,
        current_battery: float | None = None,
    ) -> dict[str, Any]:
        """Return per-room learning estimates for all rooms on a map.

        Queue-independent — every managed room on the map gets an estimate
        based on its current effective persisted settings, regardless of
        whether it is selected for cleaning.

        Parameters
        ----------
        manager:
            Core EufyVacuumManager instance (for room data and protected config).
        vacuum_entity_id:
            Vacuum entity id.
        map_id:
            Map id string.
        current_battery:
            Optional current battery % — informational only, no blocking.
        """
        from ..learning.estimator import (
            _find_room_match,
            _score_room_confidence,
            _confidence_result,
            _learning_velocity,
            _DEFAULT_ROOM_MINUTES,
            _DEFAULT_BATTERY_PER_ROOM,
        )

        map_id_str = str(map_id)
        map_id_int = _safe_int(map_id)

        # Cache-only on this path. get_room_learning_estimates runs on the event
        # loop (the dashboard-snapshot service), so it must never block on disk.
        # _get_cached_learning_stats schedules an executor preload when the cache
        # is cold: that one refresh returns default estimates and the next refresh
        # — after the preload lands — serves the real learned data.
        room_stats_data, accuracy_stats, stats_stale = self._get_cached_learning_stats(
            vacuum_entity_id=vacuum_entity_id
        )
        room_stats: list[dict[str, Any]] = (
            room_stats_data.get("room_stats", []) if room_stats_data else []
        )
        rebuilt_at = (room_stats_data or {}).get("rebuilt_at")

        # Pull all managed rooms from storage.
        rooms_raw: dict[str, Any] = manager.get_managed_rooms(
            vacuum_entity_id=vacuum_entity_id,
            map_id=map_id_str,
        ).get("rooms", {})

        room_entries: list[dict[str, Any]] = []

        for room_id_key, room_data in rooms_raw.items():
            room_id = _safe_int(room_id_key)
            room_name = str(room_data.get("name", f"Room {room_id}"))
            slug = str(room_data.get("slug", "")).strip().lower()

            try:
                # Resolve effective settings through the protection layer.
                protected = manager.protected_room_config(room_data)

                clean_mode = str(protected.get("clean_mode", "vacuum")).strip().lower()
                clean_passes = _safe_int(protected.get("clean_passes", 1), 1)
                clean_intensity = str(
                    protected.get("clean_intensity", "standard")
                ).strip().lower()
                water_level = str(protected.get("water_level", "Off"))
                edge_mopping = bool(protected.get("edge_mopping", False))
                floor_type = str(room_data.get("floor_type", "hardwood")).lower()
                is_carpet = floor_type.startswith("carpet")

                # Look up learned stats.
                match, intensity_mismatch = _find_room_match(
                    room_stats=room_stats,
                    map_id=map_id_int,
                    slug=slug,
                    clean_mode=clean_mode,
                    clean_passes=clean_passes,
                    is_carpet=is_carpet,
                    clean_intensity=clean_intensity,
                )

                if match:
                    minutes = _safe_float(
                        match.get("avg_minutes"), _DEFAULT_ROOM_MINUTES
                    )
                    battery = _safe_float(
                        match.get("avg_battery_used"), _DEFAULT_BATTERY_PER_ROOM
                    )
                    sample_count = _safe_int(match.get("sample_count"), 0)
                    minutes_stddev = _safe_float(match.get("minutes_stddev"), 0.0)
                    source = "learned"
                    room_key = _room_key(
                        map_id_int, slug, clean_mode, clean_passes, is_carpet, clean_intensity, edge_mopping
                    )
                    drift_ratio = self.estimator._drift_ratio_for_room(
                        accuracy_stats=accuracy_stats,
                        room_key=room_key,
                    )
                else:
                    minutes = _DEFAULT_ROOM_MINUTES
                    battery = _DEFAULT_BATTERY_PER_ROOM
                    sample_count = 0
                    minutes_stddev = 0.0
                    intensity_mismatch = False
                    drift_ratio = 0.0
                    source = "default"

                confidence_score = _score_room_confidence(
                    source=source,
                    sample_count=sample_count,
                    avg_minutes=minutes,
                    minutes_stddev=minutes_stddev,
                    intensity_mismatch=intensity_mismatch,
                    accuracy_drift_ratio=drift_ratio,
                )
                confidence = _confidence_result(confidence_score)
                velocity = _learning_velocity(sample_count, confidence_score)

                room_entries.append({
                    "room_id": room_id,
                    "room_name": room_name,
                    "slug": slug,
                    "map_id": map_id_int,
                    "clean_mode": clean_mode,
                    "clean_passes": clean_passes,
                    "clean_intensity": clean_intensity,
                    "water_level": water_level,
                    "edge_mopping": edge_mopping,
                    "is_carpet": is_carpet,
                    "minutes": round(minutes, 2),
                    "battery": round(battery, 2),
                    "source": source,
                    "sample_count": sample_count,
                    "intensity_mismatch": intensity_mismatch,
                    "accuracy_drift_ratio": round(drift_ratio, 4),
                    "confidence_score": confidence["confidence_score"],
                    "confidence_label": confidence["confidence_label"],
                    "confidence_breakpoint": confidence["confidence_breakpoint"],
                    "learning_velocity": velocity,
                    "error": None,
                    "error_detail": None,
                })

            except Exception as exc:
                room_entries.append({
                    "room_id": room_id,
                    "room_name": room_name,
                    "slug": slug,
                    "map_id": map_id_int,
                    "error": "estimate_failed",
                    "error_detail": str(exc),
                    "minutes": None,
                    "battery": None,
                    "confidence_label": None,
                    "confidence_breakpoint": None,
                    "learning_velocity": None,
                })

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "map_id": map_id_int,
            "estimated_at": _iso_now(),
            "room_count": len(room_entries),
            "stats_stale": stats_stale,
            "stats_rebuilt_at": rebuilt_at,
            "current_battery": current_battery,
            "rooms": room_entries,
        }

    def next_room(
        self,
        *,
        reanchored_estimate: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Return the next incomplete room from a reanchored timeline.

        Lightweight shortcut for the card's live job display.
        Delegates entirely to the estimator — no math here.
        """
        return self.estimator.next_room(reanchored_estimate=reanchored_estimate)

    def reanchor_timeline(
        self,
        *,
        original_estimate: dict[str, Any],
        completed_rooms: list[dict[str, Any]],
        reanchor_at: str | None = None,
        current_battery: float | None = None,
        charge_percent_per_minute: float = 1.0,
        reserve_battery_percent: float = 5.0,
    ) -> dict[str, Any]:
        """Reanchor room ETAs using actual completed room durations.

        Called each time eufy_vacuum_room_completed fires mid-job.
        If current_battery is supplied, also updates battery readiness
        for the remaining rooms.
        Delegates entirely to the estimator — no math here.
        """
        return self.estimator.reanchor_timeline(
            original_estimate=original_estimate,
            completed_rooms=completed_rooms,
            reanchor_at=reanchor_at,
            current_battery=current_battery,
            charge_percent_per_minute=charge_percent_per_minute,
            reserve_battery_percent=reserve_battery_percent,
        )
