"""Diagnostics support for Vacuum Agent.

Powers the **Download Diagnostics** button on the integration's page
(Settings → Devices & Services → Vacuum Agent → ⋮). The dump is
support-oriented and brand-agnostic:

- **entity_resolution** — for every role the adapter declares, the entity_id it
  resolves to, whether that entity exists in HA, and its current state. This is
  the #1 onboarding signal: the most common "I can't configure my rooms" report
  is a missing or blank ``active_map`` sensor, which shows up here at a glance.
- map / room / capability state, the raw provider vacuum entity, and the upkeep
  snapshot. (The dashboard snapshot is intentionally excluded: computing it can
  advance room timing and fire room-transition events during a live clean, and a
  diagnostics download must stay read-only.)

Credentials are redacted; entity_ids and map_ids are not secret and are kept
because support needs them.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_RUNTIME, DOMAIN

# Keys whose values may carry secrets. entity_ids and map_ids are NOT secret and
# are needed for support, so they are deliberately NOT redacted.
TO_REDACT = {
    # Free-text Setup field — a classic place users paste account passwords.
    "notes",
    "password",
    "username",
    "email",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "openudid",
}

# HA sentinel values that mean "no real value".
_SENTINELS = {"", "unknown", "unavailable", "none", "None"}


def _entity_snapshot(hass: HomeAssistant, entity_id: Any) -> dict[str, Any]:
    """Resolve one adapter role to {entity_id, exists, state}.

    Defensive against a malformed adapter config that declares a non-string
    entity value: diagnostics is exactly the tool reached for on a broken config,
    so it must not crash on one (``hass.states.get`` would call ``.lower()`` on a
    non-str and raise).
    """
    if not isinstance(entity_id, str) or not entity_id:
        return {
            "entity_id": entity_id if isinstance(entity_id, str) else None,
            "exists": False,
            "state": None,
        }
    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        return {"entity_id": entity_id, "exists": False, "state": None}
    return {"entity_id": entity_id, "exists": True, "state": state_obj.state}


def _resolve_active_map_id(entity_resolution: dict[str, Any]) -> str | None:
    """Derive the active map id from the resolved active_map entity's state."""
    state = (entity_resolution.get("active_map") or {}).get("state")
    if state is None or str(state) in _SENTINELS:
        return None
    return str(state)


def _vacuum_diagnostics(
    hass: HomeAssistant, manager: Any, vacuum_entity_id: str
) -> dict[str, Any]:
    """Collect the per-vacuum diagnostic block (best-effort, never raises)."""
    out: dict[str, Any] = {"vacuum_entity_id": vacuum_entity_id}

    # Capabilities + the adapter entity-resolution table (the headline signal).
    try:
        caps = manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id, refresh=False
        )
    except Exception as err:  # pragma: no cover - defensive
        caps = {}
        out["capabilities_error"] = repr(err)

    entities_map = (caps.get("entities") or {}) if isinstance(caps, dict) else {}
    entity_resolution = {
        role: _entity_snapshot(hass, entity_id)
        for role, entity_id in sorted(entities_map.items())
    }
    out["entity_resolution"] = entity_resolution

    # Capability flags (the entities sub-dict is already expanded above).
    if isinstance(caps, dict):
        out["capabilities"] = {k: v for k, v in caps.items() if k != "entities"}

    # Raw provider vacuum entity — state + the attributes discovery reads.
    v_state = hass.states.get(vacuum_entity_id)
    if v_state is None:
        out["vacuum_state"] = {"exists": False}
    else:
        attrs = dict(v_state.attributes)
        segments = attrs.get("segments")
        out["vacuum_state"] = {
            "exists": True,
            "state": v_state.state,
            "attribute_keys": sorted(attrs.keys()),
            "segment_count": len(segments) if isinstance(segments, list) else None,
            "segments": segments,
            "rooms": attrs.get("rooms"),
        }

    # Map + room resolution.
    active_map_id = _resolve_active_map_id(entity_resolution)
    out["active_map_id"] = active_map_id

    try:
        out["maps"] = manager.get_vacuum_maps(vacuum_entity_id=vacuum_entity_id)
    except Exception as err:  # pragma: no cover - defensive
        out["maps_error"] = repr(err)

    if active_map_id:
        try:
            out["managed_rooms"] = manager.get_managed_rooms(
                vacuum_entity_id=vacuum_entity_id, map_id=active_map_id
            )
        except Exception as err:  # pragma: no cover - defensive
            out["managed_rooms_error"] = repr(err)
    else:
        out["managed_rooms"] = None
        out["managed_rooms_note"] = (
            "skipped — no active map resolved (the active_map sensor is missing or "
            "blank). Import an active map first (Setup → Import Active Map)."
        )

    # Upkeep (maintenance / dock) — side-effect-free.
    try:
        out["upkeep_snapshot"] = manager.get_upkeep_snapshot(
            vacuum_entity_id=vacuum_entity_id
        )
    except Exception as err:  # pragma: no cover - defensive
        out["upkeep_snapshot_error"] = repr(err)

    return out


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Vacuum Agent config entry."""
    diag: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
    }

    manager = getattr(entry, "runtime_data", None) or hass.data.get(DOMAIN, {}).get(
        DATA_RUNTIME
    )
    if manager is None:
        diag["error"] = "runtime manager unavailable (entry not set up)"
        return diag

    # Integration version (from the manifest).
    try:
        from homeassistant.loader import async_get_integration

        integration = await async_get_integration(hass, DOMAIN)
        diag["integration_version"] = str(integration.version)
    except Exception as err:  # pragma: no cover - defensive
        diag["integration_version_error"] = repr(err)

    try:
        vacuum_ids = list(manager.get_known_vacuum_ids())
    except Exception as err:  # pragma: no cover - defensive
        diag["vacuums_error"] = repr(err)
        return diag

    # Read-only: the dashboard snapshot is deliberately NOT collected here (see
    # the module docstring) — computing it can fire room-transition events and
    # persist during a live clean. Everything in _vacuum_diagnostics is read-only.
    vacuums = [_vacuum_diagnostics(hass, manager, vac) for vac in vacuum_ids]

    diag["vacuums"] = async_redact_data(vacuums, TO_REDACT)
    return diag
