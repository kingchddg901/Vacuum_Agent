"""Shared helpers and common schemas for service handlers.

Three things live here:

1. Helpers used by every domain module — manager accessor, the
   ``map_id`` auto-resolver, the job-finished event payload builder,
   and the run-incomplete event payload builder (both used by domains
   that fire those events, currently only ``job_control`` for the
   cancel path).

2. Schemas that are genuinely shared across domains — VACUUM_ONLY,
   VACUUM_MAP, JOB_CONTROL. Domain-specific schemas live with their
   domain.

Each domain module exposes ``register(hass) -> None`` and
``SERVICES: tuple[str, ...]``. The package ``__init__.py`` calls
every domain's register on setup and walks every domain's SERVICES
tuple on teardown.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import DATA_RUNTIME, DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_manager(hass: HomeAssistant):
    """Return the integration manager."""
    return hass.data[DOMAIN][DATA_RUNTIME]


def resolved_call_data(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return call.data with map_id auto-resolved when absent.

    Services are adapter-agnostic, so the map_id field is optional on every
    service that takes one. When the caller omits it (or passes a blank
    string), look up the vacuum's current active map via the adapter's
    declared `entities.active_map` entity and substitute that value.

    The lookup is delegated to `rooms.room_discovery.get_active_map_id`,
    which reads from `adapter_config.entities.active_map`. Any adapter that
    declares an active-map entity gets a free auto-resolve path; adapters
    that don't declare one require callers to pass map_id explicitly.

    Pass-through behavior:
      - map_id already present and non-empty -> returned unchanged.
      - vacuum_entity_id missing -> returned unchanged (validation surface
        will reject the call anyway).
      - active_map entity missing or sentinel-valued -> returned unchanged;
        the manager method will raise its own clear error on the missing
        kwarg, which is the desired behavior (silent fallback to a wrong
        map would be worse).
    """
    data = dict(call.data)
    if data.get("map_id"):
        return data
    vacuum_entity_id = data.get("vacuum_entity_id")
    if not vacuum_entity_id:
        return data
    # Imported lazily to keep the services package import-time clean —
    # the rooms subpackage pulls in adapter machinery we don't need at
    # module load.
    from ..rooms.room_discovery import get_active_map_id

    resolved = get_active_map_id(hass, vacuum_entity_id)
    if resolved:
        data["map_id"] = resolved
    return data



# anchor: INKV8ZQD  durable per-vacuum state is minted only for a MANAGED vacuum;
# a write to an unmanaged one refuses, a read returns the empty shape with a reason
def is_managed_vacuum(hass: HomeAssistant, vacuum_entity_id: str) -> bool:
    """True when this integration actually manages ``vacuum_entity_id``.

    ``cv.entity_id`` validates the SHAPE ``domain.object_id`` and nothing else —
    not that the entity exists, and certainly not that we manage it. Every
    per-vacuum store keyed off an unchecked id therefore mints a durable bucket
    for whatever string an automation happened to pass.

    The authority is ``data["vacuums"]``, the same dict ``get_managed_vacuums``
    reads. It only became usable as an authority on 2026-08-18, when
    ``get_pause_timeout_settings`` — a registered READ service — stopped
    setdefault-ing into it. A gate cannot be built on a dict its own read path
    writes to.
    """
    manager = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME)
    if manager is None:
        return False
    return str(vacuum_entity_id) in (manager.data.get("vacuums") or {})


def require_managed_vacuum(hass: HomeAssistant, vacuum_entity_id: str) -> None:
    """Refuse a WRITE aimed at a vacuum this integration does not manage.

    Raises ``ServiceValidationError`` (caller error, not internal failure), so HA
    surfaces it as a toast rather than a traceback — see ``INT62M7A``: a mutation
    either refuses with a reason or succeeds carrying what it applied. Silently
    minting a bucket and reporting success is the third thing, and it is the bug.

    WRITES ONLY. Reads return their empty shape with a ``reason`` instead, because
    a read is how a card discovers state and turning discovery into an error trades
    a blank panel for a red toast. The split is inspectable per handler — mutating
    or not — rather than a judgement call per service.

    Ruled 2026-08-18. Safe to activate: every per-vacuum store on the reference
    install keyed only on the three managed vacuums, so there was no existing
    phantom for this to start rejecting.
    """
    if not is_managed_vacuum(hass, vacuum_entity_id):
        raise ServiceValidationError(
            f"{vacuum_entity_id} is not a vacuum this integration manages.",
            translation_domain=DOMAIN,
            translation_key="unmanaged_vacuum",
            translation_placeholders={"vacuum_entity_id": str(vacuum_entity_id)},
        )


def unmanaged_vacuum_read_result(vacuum_entity_id: str, **empty_shape) -> dict:
    """The empty-but-honest payload a READ returns for an unmanaged vacuum.

    Carries ``reason`` so a consumer can tell "nothing here" from "not ours" —
    the distinction the phantom buckets destroyed, since minting one made the two
    byte-identical forever after.
    """
    return {
        "vacuum_entity_id": str(vacuum_entity_id),
        "reason": "unmanaged_vacuum",
        **empty_shape,
    }


def job_finished_event_payload(
    *,
    vacuum_entity_id: str,
    map_id: str,
    result: dict | None,
) -> dict:
    """Build consistent payload for the job-finished event.

    Used by the cancel-active-job service handler (job_control domain)
    when the cancel path also finalizes the job. The listener-side
    paths use a similarly-shaped helper in listeners/_common.py; the
    two shapes are kept in sync but live separately because the
    services-side caller has `result` with a "finalize_result" wrapper
    while the listeners-side caller has a raw finalize result.
    """
    result = result if isinstance(result, dict) else {}
    completed_job = result.get("completed_job") or result.get("finalize_result", {}).get("completed_job", {})
    if not isinstance(completed_job, dict):
        completed_job = {}
    outcome = completed_job.get("outcome", {}) if isinstance(completed_job.get("outcome", {}), dict) else {}
    job_info = completed_job.get("job", {}) if isinstance(completed_job.get("job", {}), dict) else {}
    job_path = result.get("job_path")
    if job_path is None and isinstance(result.get("finalize_result"), dict):
        job_path = result["finalize_result"].get("job_path")
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "map_id": str(map_id),
        "job_id": result.get("job_id") or result.get("finalize_result", {}).get("job_id"),
        "status": outcome.get("status", "completed"),
        "reason_detail": outcome.get("lifecycle_message") or outcome.get("status"),
        "used_for_learning": outcome.get("used_for_learning"),
        "finalized_at": completed_job.get("finalized_at"),
        "room_count": job_info.get("room_count"),
        "duration_minutes": job_info.get("duration_minutes"),
        "actual_cleaning_minutes": job_info.get("actual_cleaning_minutes"),
        "job_path": job_path,
    }


def run_incomplete_event_payload(
    *,
    vacuum_entity_id: str,
    result: dict | None,
) -> dict | None:
    """Build the run-incomplete event payload, or None when nothing was missed.

    Used by the cancel-active-job service handler (job_control domain): a manual
    cancel finalizes as ``cancelled``, which writes an ``incomplete_run_log`` when
    rooms were queued but never cleaned. When that log names at least one missed
    room this returns the ``EVENT_RUN_INCOMPLETE`` payload; otherwise ``None`` so
    the caller skips the fire.

    Mirrors ``listeners/_common.run_incomplete_event_data`` (kept in sync, lives
    separately for the same reason as ``job_finished_event_payload``). Accepts
    either the raw finalize result or a ``{"finalize_result": ...}`` wrapper.
    """
    result = result if isinstance(result, dict) else {}
    incomplete_log = result.get("incomplete_run_log")
    if incomplete_log is None and isinstance(result.get("finalize_result"), dict):
        incomplete_log = result["finalize_result"].get("incomplete_run_log")
    if not isinstance(incomplete_log, dict) or not incomplete_log.get("missed_room_ids"):
        return None
    return {
        "vacuum_entity_id": vacuum_entity_id,
        "job_id": incomplete_log.get("job_id"),
        "outcome_status": incomplete_log.get("outcome_status"),
        "missed_room_ids": list(incomplete_log.get("missed_room_ids", [])),
        "missed_rooms": list(incomplete_log.get("missed_rooms", [])),
    }


# Shared schemas used across multiple domain modules. Domain-specific
# schemas live with their domain file.

VACUUM_ONLY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)

VACUUM_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
    }
)

JOB_CONTROL_SCHEMA = VACUUM_MAP_SCHEMA
