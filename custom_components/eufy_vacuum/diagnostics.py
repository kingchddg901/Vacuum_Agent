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


def resolve_active_map_id(entity_resolution: dict[str, Any]) -> str | None:
    """Derive the active map id from the resolved active_map entity's state."""
    state = (entity_resolution.get("active_map") or {}).get("state")
    if state is None or str(state) in _SENTINELS:
        return None
    return str(state)


def _slim_upkeep(upkeep: Any) -> Any:
    """A diagnostic-sized copy of the upkeep snapshot.

    Drops the per-item ``guide`` (static how-to-clean steps, repeated for
    maintenance / replacement / display — model boilerplate, no diagnostic value
    and the bulk of the dump's size) while keeping status / remaining / entity /
    reset fields. Never mutates the input.
    """
    if not isinstance(upkeep, dict):
        return upkeep
    slim = dict(upkeep)
    for key in ("replacement_items", "maintenance_items"):
        items = slim.get(key)
        if isinstance(items, list):
            slim[key] = [
                {k: v for k, v in item.items() if k != "guide"}
                if isinstance(item, dict)
                else item
                for item in items
            ]
    return slim


def _self_check(out: dict[str, Any]) -> dict[str, Any]:
    """Plain-English interpretation of the raw signals collected below.

    This is the block a support helper (or the user) reads first: it turns the
    entity-resolution / capability / segment data into status lines, so the most
    common report — "why can't I import my rooms?" — is answerable at a glance
    without knowing the internals. The headline tell is transport mode: a device
    on Eufy's reduced (scalar/Tuya) transport exposes no active_map sensor, so
    its rooms come from the vacuum's ``segments`` attribute and its map picture
    won't render. Derived purely from the already-collected ``out`` — never
    raises (the caller still guards it).
    """
    caps = out.get("capabilities") or {}
    entity_res = out.get("entity_resolution") or {}
    vstate = out.get("vacuum_state") or {}
    adapter = out.get("adapter") or {}
    brand = adapter.get("brand")

    active_map_role = entity_res.get("active_map") or {}
    has_active_map_entity = bool(active_map_role.get("exists"))

    seg_count = vstate.get("segment_count")
    has_segments = isinstance(seg_count, int) and seg_count > 0

    # Real, brand-agnostic room presence: rooms already imported (managed_rooms_by_map),
    # any stored map carrying a room_count, the Eufy `segments` attribute, or an
    # active-map entity. Roborock's rooms come from its OWN integration and show up
    # in maps/managed_rooms — NOT via a Eufy transport signal — so the old check that
    # only looked at active_map + segments wrongly reported "no rooms" for a working
    # device.
    managed = out.get("managed_rooms_by_map") or {}
    imported_rooms = sum(
        int(m.get("room_count") or 0)
        for m in managed.values()
        if isinstance(m, dict)
    )
    maps_block = out.get("maps") or {}
    map_rooms = sum(
        int(m.get("room_count") or 0)
        for m in (maps_block.get("maps") or [])
        if isinstance(m, dict)
    )
    room_total = imported_rooms or map_rooms
    has_rooms = bool(room_total or has_segments or has_active_map_entity)

    # Rooms sourced OUTSIDE the Eufy transport (no active_map sensor, no segments
    # attribute) => a native brand integration (e.g. Roborock) provides them.
    native_rooms = has_rooms and not has_active_map_entity and not has_segments

    # Map availability, brand-agnostic: Eufy's active_map entity, or a decoded raster
    # from the raw-map decode (the same layer that feeds Roborock zone-draw).
    drift = out.get("roborock_geometry_drift") or {}
    has_decoded_map = bool(drift.get("present"))

    # supports_room_clean is the true "can this device clean rooms" capability (always
    # True on Roborock); supports_rooms is the Eufy-shaped "how Eufy exposes rooms" flag.
    supports_room_clean = bool(caps.get("supports_room_clean") or caps.get("supports_rooms"))

    if has_active_map_entity:
        transport = "full (novel / MQTT) — active_map sensor present"
    elif native_rooms:
        transport = (
            f"native integration ({brand}) — rooms and map come from the {brand} "
            "integration, not a Eufy transport"
            if brand
            else "native integration — rooms and map come from the device's own "
            "HA integration, not a Eufy transport"
        )
    elif has_segments:
        transport = (
            "attribute-mode (reduced / scalar-Tuya) — no active_map sensor; "
            "the room list is read from the vacuum's segments attribute"
        )
    else:
        transport = (
            "unknown — no active_map sensor and no room segments visible yet"
        )

    if has_rooms and supports_room_clean:
        if has_active_map_entity:
            room_control = "available (via active map)"
        elif has_segments:
            room_control = f"available (via segments attribute — {seg_count} rooms)"
        elif room_total:
            src = f"the {brand} integration" if brand else "the device's integration"
            room_control = f"available (via {src} — {room_total} rooms)"
        else:
            room_control = "available"
    elif supports_room_clean:
        room_control = "reported available, but no rooms are visible yet"
    else:
        room_control = "unavailable (no room source detected)"

    if has_active_map_entity:
        map_image = (
            "active_map sensor present — live-map backdrop available when the "
            "eufy-clean fork provides a map camera"
        )
    elif has_decoded_map:
        who = f"the {brand}" if brand else "the device's"
        map_image = (
            f"available — {who} map is decoded locally to a room raster "
            "(live-map backdrop + zone draw work)"
        )
    elif native_rooms:
        map_image = (
            "pending — no decoded map yet; open the live map or finish a mapping "
            "run once so the raw map can be decoded to a room raster"
        )
    else:
        map_image = (
            "unavailable — the reduced transport has no map sensor; the live-map "
            "backdrop needs the smcneece eufy-clean fork"
        )

    detected_model = caps.get("detected_model")
    family = caps.get("model_family")
    if detected_model and family:
        model_detection = f"{detected_model} → {family}"
    elif family:
        model_detection = str(family)
    else:
        model_detection = "generic (model not detected)"

    importable = has_rooms

    if has_active_map_entity:
        note = "Standard transport — maps, rooms and the live map all work."
    elif native_rooms:
        base = f"{brand} device" if brand else "Native-integration device"
        note = (
            f"{base} — rooms come from its own HA integration and per-room clean "
            + (
                "+ zone draw work; the map is decoded locally to a room raster."
                if has_decoded_map
                else "works. Open the live map once so the raw map can be decoded."
            )
        )
    elif has_segments:
        note = (
            "No active_map sensor — your robot is on Eufy's reduced (scalar/Tuya) "
            "transport. Room cleaning works (rooms come from the vacuum's segments "
            "attribute); the map picture won't render without the eufy-clean fork."
        )
    else:
        note = (
            "No active_map sensor and no room segments yet. If the robot is new, "
            "finish a mapping run with rooms set up in the Eufy app — the room list "
            "loads directly from the vacuum and may take a moment after startup."
        )

    # Loud, actionable warnings that belong at the top of a support read. Today:
    # a completion gate whose required job-active binary is missing → every run
    # strands (see completion_health above).
    warnings: list[str] = []
    _completion_health = out.get("completion_health") or {}
    if _completion_health.get("warning"):
        warnings.append(_completion_health["warning"])

    return {
        "transport": transport,
        "room_control": room_control,
        "rooms_importable": "yes" if importable else "no",
        "map_image": map_image,
        "model_detection": model_detection,
        "note": note,
        "warnings": warnings,
    }


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

    # Adapter identity (brand) — lets _self_check phrase native-integration brands
    # (e.g. Roborock, whose rooms/map come from their OWN HA integration rather than
    # a Eufy transport) correctly instead of reporting Eufy-shaped 'unknown/unavailable'
    # for a device whose rooms actually work. Best-effort; absent -> generic phrasing.
    try:
        from .adapters.registry import get_adapter_config as _get_cfg

        _cfg = _get_cfg(vacuum_entity_id) or {}
        if isinstance(_cfg, dict) and _cfg.get("brand"):
            out["adapter"] = {"brand": _cfg.get("brand")}
    except Exception:  # pragma: no cover - defensive
        pass

    # Completion / lifecycle health — a brand that gates completion on the job_active
    # binary (completion.require_job_active_clear, e.g. Roborock) CANNOT finalize ANY
    # run when that binary is missing: every run strands (FN-1, the lifecycle walk).
    # This is the tripwire for upstream capability-gating dropping the entity
    # (HA 2026.7 #173282) — surface it loud rather than letting runs silently vanish.
    try:
        from .adapters.registry import get_adapter_config as _get_cfg2

        _cfg2 = _get_cfg2(vacuum_entity_id) or {}
        _requires_job_active = bool(
            (_cfg2.get("completion") or {}).get("require_job_active_clear")
        )
        _job_active_entity = (_cfg2.get("entities") or {}).get("job_active")
        _job_active_present = bool((entity_resolution.get("job_active") or {}).get("exists"))
        _health: dict[str, Any] = {
            "requires_job_active_clear": _requires_job_active,
            "job_active_entity": _job_active_entity,
            "job_active_present": _job_active_present,
        }
        if _requires_job_active and not _job_active_present:
            _health["warning"] = (
                f"Completion requires the job-active binary "
                f"({_job_active_entity or 'not declared'}) but it is missing — EVERY run "
                "will strand (never finalize). Check the upstream integration didn't drop "
                "this entity."
            )
        out["completion_health"] = _health
    except Exception as err:  # pragma: no cover - defensive
        out["completion_health"] = {"error": repr(err)}

    # Dock-control entities — resolved INDEPENDENT of the capability gate so the
    # dump shows whether the device physically exposes wash/dry/empty controls
    # even when the model is detected as 'generic' (mop hints off). Answers "can
    # we safely enable the dock actions for this model?" without asking the user
    # to hand-list button entities.
    try:
        _dock_actions = manager.get_dock_action_entities(vacuum_entity_id=vacuum_entity_id)
        out["dock_controls"] = {
            action: {"entity_id": eid, "exists": eid is not None}
            for action, eid in _dock_actions.items()
        }
    except Exception:  # pragma: no cover - defensive
        pass

    # Raw provider vacuum entity — state + the attributes discovery reads.
    v_state = hass.states.get(vacuum_entity_id)
    if v_state is None:
        out["vacuum_state"] = {"exists": False}
    else:
        attrs = dict(v_state.attributes)
        segments = attrs.get("segments")
        # `rooms` is byte-identical to `segments` on Eufy — keep one. attribute_keys
        # still lists every attribute name so nothing is hidden.
        out["vacuum_state"] = {
            "exists": True,
            "state": v_state.state,
            "attribute_keys": sorted(attrs.keys()),
            "segment_count": len(segments) if isinstance(segments, list) else None,
            "segments": segments,
        }

    # Map + room resolution.
    # active_map_id is the ENTITY-derived active map (Eufy's active_map sensor) —
    # it stays a top-level signal because a missing/blank one is the #1 onboarding
    # tell. Room dumping below iterates EVERY stored map instead of just this one,
    # so it's brand-agnostic: Roborock resolves its active map a different way and
    # exposes no such sensor, but its rooms still surface here.
    out["active_map_id"] = resolve_active_map_id(entity_resolution)

    map_ids: list[str] = []
    try:
        maps = manager.get_vacuum_maps(vacuum_entity_id=vacuum_entity_id)
        out["maps"] = maps
        map_ids = [
            str(m["map_id"])
            for m in (maps or {}).get("maps", [])
            if isinstance(m, dict) and m.get("map_id") is not None
        ]
    except Exception as err:  # pragma: no cover - defensive
        out["maps_error"] = repr(err)

    managed_rooms_by_map: dict[str, Any] = {}
    for map_id in map_ids:
        try:
            rooms = manager.get_managed_rooms(
                vacuum_entity_id=vacuum_entity_id, map_id=map_id
            )
            # Drop the `summary` block — it re-lists the rooms already dumped in full.
            if isinstance(rooms, dict):
                rooms = {k: v for k, v in rooms.items() if k != "summary"}
            managed_rooms_by_map[map_id] = rooms
        except Exception as err:  # pragma: no cover - defensive
            managed_rooms_by_map[map_id] = {"error": repr(err)}
    out["managed_rooms_by_map"] = managed_rooms_by_map

    if not map_ids:
        out["managed_rooms_note"] = (
            "no maps imported yet — once the vacuum has completed a mapping run, "
            "run Setup → Import Active Map."
        )

    # Roborock raw-map decode validation. Both geometry paths derive from the SAME segment
    # layer — the parser's per-room bboxes (rooms_from_mapdata) and our raw-blob raster decode
    # — so overlaying them checks the decode: `aligned` => correct on this device (rid /
    # orientation / frame); a systematic centre_delta is the pose/coord calibration signal (a
    # constant offset = the parser's trim, an inverted axis = a flip). Only the roborock memory
    # backend carries the raw blob; absent/no-op elsewhere. Best-effort, never raises.
    try:
        from .adapters.registry import get_adapter_config as _get_cfg
        from .mapping import map_source_runtime as _msr

        _src = (_get_cfg(vacuum_entity_id) or {}).get("map_state_source")
        if isinstance(_src, dict) and _src.get("backend") == "memory":
            _cands = _msr.roborock_candidates(hass, _src)
            out["roborock_geometry_drift"] = _msr.roborock_geometry_drift_from_candidates(_cands)
    except Exception as err:  # pragma: no cover - defensive
        out["roborock_geometry_drift_error"] = repr(err)

    # Upkeep (maintenance / dock) — side-effect-free. The per-item care guides
    # (static how-to-clean steps) are stripped: model boilerplate with no
    # diagnostic value that otherwise dominates the dump's size.
    try:
        out["upkeep_snapshot"] = _slim_upkeep(
            manager.get_upkeep_snapshot(vacuum_entity_id=vacuum_entity_id)
        )
    except Exception as err:  # pragma: no cover - defensive
        out["upkeep_snapshot_error"] = repr(err)

    # Interpreted, human-readable summary of everything above. Computed last
    # (needs all signals) but surfaced right after the id so it reads first.
    try:
        summary = _self_check(out)
    except Exception as err:  # pragma: no cover - defensive
        summary = {"error": repr(err)}
    ordered: dict[str, Any] = {
        "vacuum_entity_id": vacuum_entity_id,
        "self_check": summary,
    }
    for key, value in out.items():
        if key != "vacuum_entity_id":
            ordered[key] = value
    return ordered


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
