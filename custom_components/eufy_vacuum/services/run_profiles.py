"""Saved run-profile library services — read / save / apply / rename / overwrite / delete.

Six services for the named-runs library. The start_run_profile service
(apply + start in one shot) lives in job_control.py — it's a job
lifecycle operation, not a library mutation.
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INGZFYXX  `profiles/manager.py#INGZFYXX`
#       A5-RUNPROF-2 (closed RP-031): apply_run_profile persists a full room-selection wipe and reports no error when the
#              profile's rooms no longer exist on the map
#       A5-RUNPROF-3 (closed RP-031): overwrite_run_profile exposes the step-sequence destruction with no warning, no
#              confirmation, no response signal — and commits it with async_save
#   INT62M7A  `themes/services.py#INT62M7A`
#       A5-RUNPROF-1: save_run_profile never inspects the manager's `saved` flag — a save that stored
#              nothing returns a success-shaped response and raises nothing
#       A5-RUNPROF-5: rename_run_profile accepts a blank name and silently relabels the profile
#              'Untitled', returning renamed:True — the sibling save rejects the same input
#       A5-RUNPROF-6: overwrite_run_profile with no rooms enabled returns overwritten:False as a success —
#              the raise gate matches one literal reason, not the failure flag


from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ..const import (
    DOMAIN,
    SERVICE_APPLY_RUN_PROFILE,
    SERVICE_DELETE_RUN_PROFILE,
    SERVICE_GET_SAVED_RUN_PROFILES,
    SERVICE_OVERWRITE_RUN_PROFILE,
    SERVICE_RENAME_RUN_PROFILE,
    SERVICE_SAVE_RUN_PROFILE,
    SERVICE_SET_RUN_PROFILE_STEPS,
)
from ._common import VACUUM_MAP_SCHEMA, get_manager, resolved_call_data

_LOGGER = logging.getLogger(__name__)


SERVICES = (
    SERVICE_GET_SAVED_RUN_PROFILES,
    SERVICE_SAVE_RUN_PROFILE,
    SERVICE_SET_RUN_PROFILE_STEPS,
    SERVICE_APPLY_RUN_PROFILE,
    SERVICE_RENAME_RUN_PROFILE,
    SERVICE_OVERWRITE_RUN_PROFILE,
    SERVICE_DELETE_RUN_PROFILE,
)


_RUN_PROFILE_NAME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Optional("expose_as_button"): cv.boolean,
        # ISSUE #50: persisted per-profile opt-in to strict room order. The button
        # entity carries no service data, so the stored flag is its only way in.
        vol.Optional("strict_order"): cv.boolean,
    }
)

_RUN_PROFILE_ID_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
    }
)

_RUN_PROFILE_OVERWRITE_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("expose_as_button"): cv.boolean,
        # ISSUE #50: tri-state on overwrite — absent leaves the saved flag untouched.
        vol.Optional("strict_order"): cv.boolean,
    }
)

_RUN_PROFILE_RENAME_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)

# RP-021b / #13:A5-RUNPROF-4. `steps` used to be a bare `list` — any list of
# anything passed the schema, and the manager's normalizer then silently dropped
# whatever it could not read. A YAML author who mistyped a step type or a percent
# got `saved: True` and a profile that had quietly lost its charge stop.
#
# Per-step shapes below reject the malformed call at the service boundary, where
# the error still points at the caller's own YAML. The manager ALSO reports what
# it rejected (set_run_profile_steps -> reason=invalid_steps) — deliberately two
# layers, because the manager is reachable from the card and the websocket API
# too, not only from this schema.
#
# Ranges are NOT enforced here: voluptuous would raise before the manager could
# name the offending step, and an out-of-range value is a better error than a
# schema traceback. The manager clamps and reports it.
_STEP_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Required("type"): "room_group",
            vol.Required("rooms"): [vol.Any(int, str, dict)],
        },
        extra=vol.ALLOW_EXTRA,
    ),
    vol.Schema({
        vol.Required("type"): "charge_wait",
        vol.Required("target_battery_percent"): vol.Coerce(int),
    }),
    vol.Schema({
        vol.Required("type"): "wait",
        vol.Required("wait_minutes"): vol.Coerce(int),
    }),
    vol.Schema({
        vol.Required("type"): "zone",
        vol.Required("zone_ids"): [cv.string],
    }),
)

_RUN_PROFILE_STEPS_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
        vol.Optional("map_id"): cv.string,
        vol.Required("profile_id"): cv.string,
        vol.Required("steps"): [_STEP_SCHEMA],
    }
)


async def _handle_get_saved_run_profiles(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Return saved run profiles for one vacuum/map."""
    payload = get_manager(hass).get_saved_run_profiles(**resolved_call_data(hass, call))
    _LOGGER.debug("get_saved_run_profiles complete: %s", payload)
    return payload


async def _handle_save_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Save current enabled-room run as a named reusable profile."""
    try:
        payload = get_manager(hass).save_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to save run profile: {err}") from err
    _LOGGER.debug("save_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_apply_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Apply one saved run profile back onto room selections/settings."""
    try:
        payload = get_manager(hass).apply_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to apply run profile: {err}") from err
    if not payload.get("applied") and payload.get("reason") == "profile_not_found":
        _LOGGER.debug(
            "apply_run_profile blocked: profile_id=%s not found",
            call.data.get("profile_id"),
        )
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("apply_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_rename_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Rename one saved run profile."""
    try:
        payload = get_manager(hass).rename_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to rename run profile: {err}") from err
    if not payload.get("renamed") and payload.get("reason") == "profile_not_found":
        _LOGGER.debug(
            "rename_run_profile blocked: profile_id=%s not found",
            call.data.get("profile_id"),
        )
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("rename_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_overwrite_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Overwrite one saved run profile from the current enabled-room snapshot."""
    try:
        payload = get_manager(hass).overwrite_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to overwrite run profile: {err}") from err
    if not payload.get("overwritten") and payload.get("reason") == "profile_not_found":
        _LOGGER.debug(
            "overwrite_run_profile blocked: profile_id=%s not found",
            call.data.get("profile_id"),
        )
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("overwrite_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_delete_run_profile(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Delete one saved run profile."""
    try:
        payload = get_manager(hass).delete_run_profile(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to delete run profile: {err}") from err
    if not payload.get("deleted") and payload.get("reason") == "profile_not_found":
        _LOGGER.debug(
            "delete_run_profile blocked: profile_id=%s not found",
            call.data.get("profile_id"),
        )
        raise ServiceValidationError(
            f"Run profile '{call.data.get('profile_id')}' not found"
        )
    _LOGGER.debug("delete_run_profile complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


async def _handle_set_run_profile_steps(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Replace a saved profile's ordered steps (room_group | charge_wait)."""
    try:
        payload = get_manager(hass).set_run_profile_steps(**resolved_call_data(hass, call))
    except Exception as err:
        raise HomeAssistantError(f"Failed to set run-profile steps: {err}") from err
    if not payload.get("saved"):
        raise ServiceValidationError(
            f"Could not set run-profile steps: {payload.get('reason', 'unknown')}"
        )
    _LOGGER.debug("set_run_profile_steps complete: %s", payload)
    await get_manager(hass).async_save()
    return payload


def register(hass: HomeAssistant) -> None:
    """Register run-profile services."""

    async def get_saved_run_profiles(call: ServiceCall) -> dict:
        return await _handle_get_saved_run_profiles(hass, call)

    async def save_run_profile(call: ServiceCall) -> dict:
        return await _handle_save_run_profile(hass, call)

    async def apply_run_profile(call: ServiceCall) -> dict:
        return await _handle_apply_run_profile(hass, call)

    async def rename_run_profile(call: ServiceCall) -> dict:
        return await _handle_rename_run_profile(hass, call)

    async def overwrite_run_profile(call: ServiceCall) -> dict:
        return await _handle_overwrite_run_profile(hass, call)

    async def delete_run_profile(call: ServiceCall) -> dict:
        return await _handle_delete_run_profile(hass, call)

    async def set_run_profile_steps(call: ServiceCall) -> dict:
        return await _handle_set_run_profile_steps(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_GET_SAVED_RUN_PROFILES, get_saved_run_profiles,
        schema=VACUUM_MAP_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_RUN_PROFILE, save_run_profile,
        schema=_RUN_PROFILE_NAME_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_RUN_PROFILE, apply_run_profile,
        schema=_RUN_PROFILE_ID_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RENAME_RUN_PROFILE, rename_run_profile,
        schema=_RUN_PROFILE_RENAME_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OVERWRITE_RUN_PROFILE, overwrite_run_profile,
        schema=_RUN_PROFILE_OVERWRITE_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_RUN_PROFILE, delete_run_profile,
        schema=_RUN_PROFILE_ID_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_RUN_PROFILE_STEPS, set_run_profile_steps,
        schema=_RUN_PROFILE_STEPS_SCHEMA, supports_response=True,
    )
