"""Shared helpers used across listener modules.

These helpers were previously module-level functions in __init__.py.
They are pure adapter-registry lookups and small data shapes — no
HA wiring of their own — so they live in a private _common module
that every listener can import from.

Public surface:

- get_adapter_vocab(vacuum_entity_id, section, key, fallback) -> frozenset[str]
- get_adapter_value(vacuum_entity_id, *path, fallback) -> Any
- get_lifecycle_watch_entities(vacuum_entity_id) -> list[str]
- completed_finalize_signals(hass, vacuum_entity_id) -> dict[str, str]
- job_finished_event_data(*, vacuum_entity_id, map_id, finalize_result) -> dict
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..adapters.registry import get_adapter_config


def get_adapter_vocab(
    vacuum_entity_id: str,
    section: str,
    key: str,
    fallback: frozenset[str],
) -> frozenset[str]:
    """Read a vocabulary set from the adapter registry with fallback.

    Returns the registry value as a frozenset if present, otherwise
    returns the fallback. Never raises.
    """
    try:
        config = get_adapter_config(vacuum_entity_id)
        if config is None:
            return fallback
        value = config.get(section, {}).get(key)
        if isinstance(value, (list, set, frozenset)):
            return frozenset(str(v).strip().lower() for v in value)
        return fallback
    except Exception:
        return fallback


def get_adapter_value(
    vacuum_entity_id: str,
    *path: str,
    fallback: Any,
) -> Any:
    """Read any scalar value from the adapter registry with fallback.

    ``path`` is a sequence of dict keys to traverse.
    Returns fallback if registry is absent, path is missing, or any
    error occurs.
    """
    try:
        config = get_adapter_config(vacuum_entity_id)
        if config is None:
            return fallback
        value: Any = config
        for key in path:
            if not isinstance(value, dict):
                return fallback
            value = value.get(key)
            if value is None:
                return fallback
        return value
    except Exception:
        return fallback


def get_lifecycle_watch_entities(vacuum_entity_id: str) -> list[str]:
    """Return entity IDs to watch for lifecycle state changes.

    Reads from the adapter registry — always includes the vacuum entity
    itself plus all declared entities whose state changes drive lifecycle
    re-evaluation. Returns only the vacuum entity when no adapter is
    registered, which is still safe (lifecycle functions then read empty
    entity states and produce no-op results).

    No brand-specific entity naming — all entity IDs come from the
    adapter's registered config.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entities = config.get("entities", {})
    watch: list[str] = [vacuum_entity_id]
    # job_active is the recharge-resume signal (a binary sensor that stays on
    # through a mid-job recharge dock); watching it ensures its clear at the true
    # finish re-triggers finalization. Absent for brands that don't declare it.
    for key in (
        "task_status",
        "dock_status",
        "active_cleaning_target",
        "active_map",
        "job_active",
    ):
        entity_id = entities.get(key)
        if entity_id:
            watch.append(entity_id)
    return watch


def is_job_active(hass: HomeAssistant, vacuum_entity_id: str) -> bool:
    """True if the adapter declares a job-active signal and it is currently on.

    ``entities.job_active`` is a binary sensor that stays ON for the whole
    logical job — INCLUDING a mid-job recharge dock where the device reports
    ``task_status=charging`` and will resume. The completion gate uses this to
    avoid finalizing during a recharge. Brands that don't declare
    ``entities.job_active`` always return False, so the guard is a no-op for them
    (e.g. Eufy).
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entity_id = config.get("entities", {}).get("job_active")
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    return state is not None and str(state.state).strip().lower() == "on"


def completed_finalize_signals(
    hass: HomeAssistant,
    vacuum_entity_id: str,
) -> dict[str, Any]:
    """Return current entity states used for completion detection.

    Reads entity IDs from the adapter registry. Returns empty strings
    for absent or unavailable entities — the caller compares values
    against configured sentinels and task_status values.

    No brand-specific entity naming — all entity IDs come from the
    adapter's registered config.
    """
    config = get_adapter_config(vacuum_entity_id) or {}
    entities = config.get("entities", {})

    def _state(entity_id: str | None) -> str:
        if not entity_id:
            return ""
        state_obj = hass.states.get(entity_id)
        if state_obj is None or state_obj.state is None:
            return ""
        return str(state_obj.state).strip().lower()

    return {
        "vacuum_state": _state(vacuum_entity_id),
        "task_status": _state(entities.get("task_status")),
        "dock_status": _state(entities.get("dock_status")),
        "active_target": _state(entities.get("active_cleaning_target")),
    }


def completion_secondary_satisfied(
    vacuum_entity_id: str,
    completion_signals: dict[str, Any],
    clear_sentinels: frozenset[str],
) -> bool:
    """Whether the completion gate's secondary requirement is met.

    The gate is ``task_status == done`` AND this secondary AND
    has_observed_active_lifecycle. Two modes:

      - ``completion.require_job_active_clear`` (Roborock): the job-active
        (cleaning) binary clearing IS the completion signal — enforced by the
        separate ``is_job_active`` guard in the lifecycle handler — so the
        current-room sentinel check is bypassed here (returns True). Needed
        because Roborock's active_cleaning_target (``current_room``) reverts to
        the DOCK room's name at the end of a run, never a sentinel, so the
        default check below would never pass and the job would never finalize.

      - default (Eufy): the active_cleaning_target must read a clear sentinel.
    """
    if bool(get_adapter_value(
        vacuum_entity_id, "completion", "require_job_active_clear", fallback=False
    )):
        return True
    return (
        str(completion_signals.get("active_target", "")).strip().lower()
        in clear_sentinels
    )


def job_finished_event_data(
    *,
    vacuum_entity_id: str,
    map_id: str,
    finalize_result: dict | None,
) -> dict:
    """Build a compact job-finished event payload.

    Used by every listener path that fires EVENT_JOB_FINISHED — lifecycle
    auto-finalization, pause-timeout cancellation, path-blocker forced
    cancellation. Keeps the payload shape consistent across all firing
    sites.
    """
    finalize_result = finalize_result if isinstance(finalize_result, dict) else {}
    completed_job = finalize_result.get("completed_job", {})
    outcome = completed_job.get("outcome", {}) if isinstance(completed_job, dict) else {}
    job_info = completed_job.get("job", {}) if isinstance(completed_job, dict) else {}
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "job_id": finalize_result.get("job_id"),
        "status": outcome.get("status", "completed"),
        "reason_detail": outcome.get("lifecycle_message") or outcome.get("status"),
        "used_for_learning": outcome.get("used_for_learning"),
        "finalized_at": completed_job.get("finalized_at"),
        "room_count": job_info.get("room_count"),
        "duration_minutes": job_info.get("duration_minutes"),
        "actual_cleaning_minutes": job_info.get("actual_cleaning_minutes"),
        "job_path": finalize_result.get("job_path"),
    }
