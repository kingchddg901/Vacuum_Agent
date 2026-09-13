"""Phase 4 integration tests — snapshot service handlers.

Coverage targets
----------------
[SNP-1]  get_pause_timeout_settings returns default settings.
[SNP-2]  set_pause_timeout_settings persists and returns updated value.
[SNP-3]  get_upkeep_snapshot returns a response dict.

Note: get_dashboard_snapshot is excluded — it requires live entity state that
is not available in isolated tests. (Pre-SNAP-2 this docstring also noted it
fires hass.bus.async_fire via _maybe_roll_current_room_by_timing as a snapshot
side effect; that is no longer true — get_job_progress_snapshot is a pure
read, and only the explicit apply_job_progress_tick() call, made by
listeners/job_progress.py's ticker, fires anything.)
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


# ---------------------------------------------------------------------------
# [SNP-1] get_pause_timeout_settings
# ---------------------------------------------------------------------------

async def test_get_pause_timeout_settings_service_returns_default(hass, manager_with_services):
    """[SNP-1] Returns vacuum_entity_id and a default timeout value."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_pause_timeout_settings",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert result["vacuum_entity_id"] == _VAC
    assert "pause_timeout_minutes_default" in result


async def test_get_pause_timeout_settings_service_creates_vacuum_record(hass, manager_with_services):
    """[SNP-1] Calling for an unseen vacuum does not raise."""
    result = await hass.services.async_call(
        DOMAIN,
        "get_pause_timeout_settings",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# [SNP-2] set_pause_timeout_settings
# ---------------------------------------------------------------------------

async def test_set_pause_timeout_settings_service_persists_value(hass, manager_with_services):
    """[SNP-2] Saved timeout is reflected in data after set service call."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 30},
        blocking=True,
        return_response=True,
    )
    stored = manager_with_services.data["vacuums"][_VAC]["pause_timeout_minutes_default"]
    assert stored == 30


async def test_set_pause_timeout_settings_service_returns_updated(hass, manager_with_services):
    """[SNP-2] Service returns updated=True with the persisted value."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 15},
        blocking=True,
        return_response=True,
    )
    assert result["updated"] is True
    assert result["pause_timeout_minutes_default"] == 15
    assert result["vacuum_entity_id"] == _VAC


async def test_set_pause_timeout_settings_service_zero_allowed(hass, manager_with_services):
    """[SNP-2] Zero is a valid pause_timeout_minutes_default (disables timeout)."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "set_pause_timeout_settings",
        {"vacuum_entity_id": _VAC, "pause_timeout_minutes_default": 0},
        blocking=True,
        return_response=True,
    )
    assert result["updated"] is True
    assert result["pause_timeout_minutes_default"] == 0


# ---------------------------------------------------------------------------
# [SNP-3] get_upkeep_snapshot
# ---------------------------------------------------------------------------

async def test_get_upkeep_snapshot_service_returns_dict(hass, manager_with_services):
    """[SNP-3] get_upkeep_snapshot returns a response dict."""
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await hass.services.async_call(
        DOMAIN,
        "get_upkeep_snapshot",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum_entity_id" in result


# ---------------------------------------------------------------------------
# [SNP-5] get_maintenance_source_candidates
# ---------------------------------------------------------------------------

async def test_get_maintenance_source_candidates_service_is_reachable(
    hass, manager_with_services
):
    """[SNP-5] THE POINT OF THIS TEST IS THE CALL SITE, not the payload.

    `get_maintenance_source_candidates` existed on the manager for a day with ZERO callers — no
    service, not on a snapshot, nothing. It was written as "the picker's read half" and the
    picker could not have read it. That is `f/audit_callsite_reachability` exactly: a correct
    function with no call site passes every audit, and the suite was green the whole time.

    So this asserts the SERVICE answers, which is the half that was missing. The response is
    wrapped in a dict because a HA service response must be a mapping, and `candidates` is a
    list even when empty — the card distinguishes "fetch has not landed" (null) from "nothing to
    offer" ([]), and returning the wrong one shows an empty-state to someone still loading.

    THE INPUT THAT MAKES THIS RED: drop the `hass.services.async_register` call, or the
    `services.yaml` entry, or rename the constant on one side only.
    """
    manager_with_services.ensure_vacuum_record(vacuum_entity_id=_VAC)

    assert hass.services.has_service(DOMAIN, "get_maintenance_source_candidates"), (
        "the service is not registered — the manager method is unreachable again"
    )

    result = await hass.services.async_call(
        DOMAIN,
        "get_maintenance_source_candidates",
        {"vacuum_entity_id": _VAC},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert isinstance(result.get("candidates"), list), (
        f"candidates must be a list even when empty, got {result.get('candidates')!r}"
    )


async def test_get_maintenance_source_candidates_refuses_an_unmanaged_vacuum(
    hass, manager_with_services
):
    """[SNP-5b] INKV8ZQD — a read answers empty-with-a-reason rather than inventing a record.

    Every other read service in this module carries the same guard; without it, asking about a
    vacuum this install does not have would reach the manager and could MINT a record for it
    (the shape that bit `get_pause_timeout_settings` in August).
    """
    result = await hass.services.async_call(
        DOMAIN,
        "get_maintenance_source_candidates",
        {"vacuum_entity_id": "vacuum.not_ours"},
        blocking=True,
        return_response=True,
    )
    assert isinstance(result, dict)
    assert "vacuum.not_ours" not in (manager_with_services.data.get("vacuums") or {}), (
        "a read must not create the vacuum record it was asked about"
    )
