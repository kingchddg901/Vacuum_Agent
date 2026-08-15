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

import asyncio
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .core.capabilities import _sweep_siblings

from .const import DATA_RUNTIME, DOMAIN
from .debug_capture import _redact

# Shared with the IMPORT path on purpose. rooms.room_discovery.get_active_map_id
# rejects these states and returns None (no map id -> nothing to import), so the
# self-check has to reject exactly the same set or it reports "everything works"
# for a device the importer will refuse. See _self_check.
from .rooms.room_discovery import _ACTIVE_MAP_SENTINELS
from .entity_helpers import is_blank_state

# Keys whose values may carry secrets. entity_ids and map_ids are NOT secret and
# are needed for support, so they are deliberately NOT redacted.
TO_REDACT = {
    # Free-text Setup field — a classic place users paste account passwords.
    "notes",
    # Free-text config-entry NAME — same class as "notes": user-editable, and
    # diagnostics is exactly where a pasted secret would otherwise leak.
    "title",
    "password",
    "username",
    "email",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "openudid",
}


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
            "registered": False,
            "state": None,
        }
    # REGISTERED is reported separately from EXISTS because they answer different
    # questions and two support reports in two days both turned on the difference.
    # exists=False + registered=False -> the entity is not created at all (a naming
    # mismatch, or the brand does not ship it). exists=False + registered=True -> the
    # ID is CORRECT and the entity is merely absent, which is what a stale registry row
    # looks like after an upgrade stops an integration creating something. Collapsing
    # the two into one flag makes those indistinguishable in a dump (issue #46).
    registered = False
    try:
        registered = er.async_get(hass).async_get(entity_id) is not None
    except Exception:  # pragma: no cover - defensive; a dump must never raise
        registered = False
    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        return {
            "entity_id": entity_id,
            "exists": False,
            "registered": registered,
            "state": None,
        }
    return {
        "entity_id": entity_id,
        "exists": True,
        "registered": registered,
        "state": state_obj.state,
    }


def resolve_active_map_id(entity_resolution: dict[str, Any]) -> str | None:
    """Derive the active map id from the resolved active_map entity's state."""
    state = (entity_resolution.get("active_map") or {}).get("state")
    if is_blank_state(state):
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
    # EXISTS is a transport tell; only a real VALUE means a map can be resolved.
    # The sensor is declared from a naming pattern and created by the vacuum
    # integration for every MQTT device, so on models whose integration never
    # delivers map/room data it exists but sits at `unavailable` forever. Keying
    # the room/map claims on existence made the self-check report "maps, rooms and
    # the live map all work" for exactly those devices, while the importer
    # (get_active_map_id) refused them — the report and the behaviour disagreed.
    active_map_state = str(active_map_role.get("state") or "")
    active_map_usable = (
        has_active_map_entity and active_map_state not in _ACTIVE_MAP_SENTINELS
    )

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
    has_rooms = bool(room_total or has_segments or active_map_usable)

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
        if active_map_usable:
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

    if active_map_usable:
        map_image = (
            "active_map sensor present — live-map backdrop available when the "
            "eufy-clean fork provides a map camera"
        )
    elif has_active_map_entity:
        map_image = (
            f"unavailable — the active_map sensor exists but reports "
            f"'{active_map_state or 'no value'}', so no map is loaded"
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

    if active_map_usable:
        note = "Standard transport — maps, rooms and the live map all work."
    elif has_active_map_entity:
        note = (
            f"The active_map sensor exists but reports "
            f"'{active_map_state or 'no value'}', and no room list is visible, so "
            "there is no map to import. This is expected on models whose vacuum "
            "integration does not deliver map/room data yet — nothing to configure "
            "here; Vacuum Agent picks the map up automatically once it arrives."
        )
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
    _area_units = out.get("area_units") or {}
    if _area_units.get("warning"):
        warnings.append(_area_units["warning"])
    # Present-but-valueless active_map: the importer will refuse this device, so say
    # so loudly instead of letting the reader infer it from a "no" three lines up.
    if has_active_map_entity and not active_map_usable:
        warnings.append(
            f"active_map entity "
            f"{active_map_role.get('entity_id') or '(unknown entity)'} reports "
            f"'{active_map_state or 'no value'}' — the vacuum integration is not "
            "providing a current map id, so rooms cannot be imported."
        )

    # RP-039/RF-33: every OTHER collector's failure surfaces here too, not just
    # the two hand-picked warning keys above. Two failure shapes: a bare
    # "<name>_error" top-level string (a collector's own try/except caught
    # something) and a nested {"error": ...} dict (a sub-block that failed
    # internally — completion_health/area_units land here too when THEY throw,
    # on top of their own "warning" key handled above). managed_rooms_by_map
    # holds one such dict PER map, so it gets its own pass.
    for _key, _value in out.items():
        if _key.endswith("_error") and _value:
            warnings.append(f"{_key}: {_value}")
        elif isinstance(_value, dict) and _value.get("error"):
            warnings.append(f"{_key}: {_value['error']}")
    for _map_id, _room_block in (out.get("managed_rooms_by_map") or {}).items():
        if isinstance(_room_block, dict) and _room_block.get("error"):
            warnings.append(f"managed_rooms_by_map[{_map_id}]: {_room_block['error']}")

    return {
        "transport": transport,
        "room_control": room_control,
        "rooms_importable": "yes" if importable else "no",
        "map_image": map_image,
        "model_detection": model_detection,
        "note": note,
        "warnings": warnings,
    }


def _pattern_resolution(
    hass: HomeAssistant, manager: Any, vacuum_entity_id: str
) -> dict[str, Any]:
    """Roles resolved from an adapter PATTERN rather than from entity_candidates.

    live:ENT-2. ``entity_resolution`` above enumerates the adapter's DECLARED candidate
    roles, and every one of them can resolve while the install still has a naming
    mismatch — because the live-map camera is not a declared role. It comes from
    ``mapping.live_map_image_entity_pattern``, which the census never looked at.

    On the maintainer's own box that produced a diagnostic reading
    ``{declared: 10, unresolved: [], likely_naming_mismatch: false}`` on an install
    where ``camera.alfred_map`` does not exist and ``camera.dining_room_alfred_map``
    does. Not wrong about what it measured — but a reader trusting the one-line verdict
    would conclude the install is clean, which is the failure this whole diagnostic
    exists to prevent.

    Reports the DERIVATION's health specifically, separate from whether the feature
    works: a manual override (or the ENT-2 device-sibling fallback) can make the live
    map work while the derived id is still wrong, and that combination is exactly what
    hid this for so long.
    """
    from .adapters.registry import get_adapter_config

    out: dict[str, Any] = {}
    config = get_adapter_config(vacuum_entity_id) or {}
    pattern = (config.get("mapping") or {}).get("live_map_image_entity_pattern")
    if not pattern:
        return out
    object_id = str(vacuum_entity_id).split(".", 1)[-1]
    try:
        # map_slug is per-map and diagnostics is map-agnostic; a pattern that uses it
        # yields a partial id here, so only the SUFFIX comparison below is meaningful.
        derived = str(pattern).format(object_id=object_id, map_slug="")
    except (KeyError, IndexError, ValueError):
        return out
    try:
        vac_record = (manager.data.get("vacuums", {}) or {}).get(vacuum_entity_id, {}) or {}
    except Exception:  # pragma: no cover - defensive
        vac_record = {}
    override = vac_record.get("live_map_image_entity")
    out["live_map_image"] = {
        "pattern": str(pattern),
        "derived": derived,
        "derived_exists": bool(derived) and hass.states.get(derived) is not None,
        "override": _redact(override) if override else None,
        "override_exists": bool(override) and hass.states.get(override) is not None,
    }
    return out


def _device_entity_census(hass: HomeAssistant, vacuum_entity_id: str) -> dict[str, Any]:
    """What the vacuum's DEVICE actually exposes, beside what the adapter derived.

    DIAG-1. ``entity_resolution`` lists each declared role with exists true/false
    — and a role that reads ``exists: false`` has two completely different
    causes that produce byte-identical output:

      1. the device genuinely has no such entity (nothing to fix), or
      2. we looked in the WRONG PLACE — the adapter derives companion entity ids
         from the vacuum's own entity_id, so any device whose entities are named
         differently (an area prefix, a rename) resolves to ids that do not
         exist (live:ENT-1).

    Issue #48 is the worked example: ten roles at exists=false, and answering
    "which of the two is this?" needed a round-trip to the reporter for entity
    ids the dump could have carried. Listing the device's real entities makes the
    two cases visibly different — a populated census beside failed resolutions IS
    the naming mismatch, and an empty one is a genuinely reduced device.

    Best-effort by construction: diagnostics is the tool reached for when things
    are already broken, so every failure here degrades to a reason string rather
    than costing the reader the whole dump.
    """
    census: dict[str, Any] = {}
    try:
        registry = er.async_get(hass)
        entry = registry.async_get(vacuum_entity_id)
        if entry is None:
            census["reason"] = "vacuum_entity_not_in_registry"
            return census

        device_id = entry.device_id
        census["device_id"] = device_id

        # live:ENT-5 — TWO SCOPES, the same pair the resolver uses.
        #
        # This census was device-scoped only, and bailed outright when the vacuum
        # had no device. That made it EMPTY on exactly the installs it exists to
        # explain: issue #49's device search found nothing while the config-entry
        # search rescued battery on the same box. A blank census on a naming
        # problem is worse than no census, because it reads as "this device
        # exposes nothing" — the very confusion the DIAG-1 comment above warns
        # about, reintroduced one scope down.
        _all, _device_count = _sweep_siblings(registry, entry)
        siblings = [registry.async_get(eid) for eid in _all]
        siblings = [item for item in siblings if item is not None]
        census["device_entity_count"] = _device_count
        census["config_entry_entity_count"] = len(siblings) - _device_count
        if not siblings:
            census["reason"] = "no_entities_on_device_or_config_entry"
            return census

        census["entity_count"] = len(siblings)
        census["entities"] = [
            {
                "entity_id": item.entity_id,
                # disabled_by is the OTHER silent cause: an entity that exists in
                # the registry but has no state is indistinguishable, through
                # hass.states.get, from one that was never created at all.
                "disabled": bool(item.disabled_by),
                "platform": item.platform,
                # live:ENT-9 — the fields that decide a COLLISION, and the ones a
                # dump could not previously answer. `cleaning_area` and
                # `total_cleaning_area` are both real, enabled sensors with the
                # same domain and a shared suffix; nothing in entity_id, disabled
                # or platform separates them. translation_key and state_class do,
                # and both live in the registry with no state required.
                #
                # Verified across three brands on the maintainer's own install:
                # robovac_mqtt sets state_class and no translation_key, Roborock
                # the reverse, Dreame sets translation_key on 39/39 sensors. A
                # dump carrying only one of the two would be blind to a brand.
                "translation_key": getattr(item, "translation_key", None),
                "state_class": (getattr(item, "capabilities", None) or {}).get(
                    "state_class"
                ),
                "device_class": (
                    getattr(item, "original_device_class", None)
                    or getattr(item, "device_class", None)
                ),
                "unit": getattr(item, "unit_of_measurement", None),
            }
            for item in sorted(siblings, key=lambda i: i.entity_id)
        ]
    except Exception as err:  # pragma: no cover - defensive
        census["error"] = _redact(repr(err))
    return census


def _vacuum_diagnostics(
    hass: HomeAssistant, manager: Any, vacuum_entity_id: str
) -> dict[str, Any]:
    """Collect the per-vacuum diagnostic block (best-effort, never raises)."""
    out: dict[str, Any] = {"vacuum_entity_id": vacuum_entity_id}

    # Capabilities + the adapter entity-resolution table (the headline signal).
    # RP-039/RF-33: get_vacuum_capabilities_snapshot is genuinely read-only
    # (unlike get_vacuum_capabilities(refresh=False), which still triggers a
    # full detection + a WRITE in three cases — see its own docstring) so a
    # diagnostics download stays inert as this module's docstring claims.
    try:
        caps = manager.get_vacuum_capabilities_snapshot(
            vacuum_entity_id=vacuum_entity_id
        )
    except Exception as err:  # pragma: no cover - defensive
        caps = {}
        out["capabilities_error"] = _redact(repr(err))

    entities_map = (caps.get("entities") or {}) if isinstance(caps, dict) else {}
    # The capabilities snapshot carries only the DETECTED roles. Roles the adapter
    # declares outright — battery, charging, the dock counters — were never probed, so a
    # dump could not answer "did the battery sensor resolve?" (issue #49) and the fault
    # had to be reproduced on other hardware instead. Union both: the adapter's declared
    # map is what the framework actually reads at runtime.
    try:
        from .adapters.registry import get_adapter_config as _get_cfg_for_entities

        declared_map = (_get_cfg_for_entities(vacuum_entity_id) or {}).get("entities") or {}
    except Exception:  # pragma: no cover - defensive
        declared_map = {}
    if not isinstance(declared_map, dict):
        declared_map = {}

    # live:ENT-BRAND-1 — GATE THE PROBE'S VOCABULARY TO THIS ADAPTER.
    #
    # `detect_capabilities()` returns a FIXED `entities` dict and emits every key
    # unconditionally, `None` where the probe found nothing. That vocabulary is
    # EUFY'S: work_mode, dock_status, water_level, robot_position_x/y. A Roborock
    # vacuum declares none of them, so all five arrived here as None, counted as
    # unresolved, and flipped `likely_naming_mismatch` to True on a completely
    # healthy S6 — which has no dock station, no settable water, and for which
    # robot_position_x/y is a Eufy-only concept by design.
    #
    # Both vacuums on the maintainer's box reported "likely naming mismatch" while
    # nothing was wrong. That is the single most decision-shaping field in a dump:
    # it is what tells a reporter "your entities exist under names we did not
    # derive" versus "your device genuinely lacks this".
    #
    # THE DISCRIMINATOR IS `entity_candidates`, NOT "did the adapter declare it".
    #
    # The first version of this gate keyed on `declared_map` alone and was WRONG in
    # the more dangerous direction: the Eufy adapter declares ZERO roles in
    # `entities` (they are all probe-resolved), so a genuine Eufy work_mode miss
    # would have been gated away silently. Hiding a real failure is worse than the
    # false alarm being fixed.
    #
    # `entity_candidates` is the right question, and capabilities.py says so in its
    # own module docstring: "{key: [entity_id, ...]} — entity IDs to probe per key",
    # and "a port to a different brand supplies its own entity_candidates". A brand
    # that offers NO candidates for a role does not have that role. A brand that
    # offers candidates and resolved none has a real miss, and still reports it.
    #
    # NOT DROPPED, MOVED: gated roles are reported as `roles_not_applicable` below.
    # Silently omitting them would make this dump indistinguishable from one where
    # the probe never ran.
    try:
        _candidates = (_get_cfg_for_entities(vacuum_entity_id) or {}).get(
            "entity_candidates"
        ) or {}
    except Exception:  # pragma: no cover - defensive
        _candidates = {}
    if not isinstance(_candidates, dict):
        _candidates = {}
    _gated = {
        role: entity_id
        for role, entity_id in entities_map.items()
        if not entity_id and role not in declared_map and role not in _candidates
    }
    merged_map = {
        **declared_map,
        **{k: v for k, v in entities_map.items() if k not in _gated},
    }
    if _gated:
        out["roles_not_applicable"] = sorted(_gated)
    # live:ENT-2 — carry WHY, not just what. A bare `null` per role cannot
    # distinguish "no such entity" from "present but disabled", and those need
    # opposite fixes: one is ours, the other is a toggle in the user's own UI.
    # Issue #49 spent a round-trip on that ambiguity while both position
    # sensors sat disabled on the device.
    _reasons = (caps.get("entity_resolution_reasons") or {}) if isinstance(caps, dict) else {}
    entity_resolution = {}
    for role, entity_id in sorted(merged_map.items()):
        snapshot = _entity_snapshot(hass, entity_id)
        if isinstance(snapshot, dict) and role in _reasons:
            snapshot["reason"] = _reasons[role]
        entity_resolution[role] = snapshot
    out["entity_resolution"] = entity_resolution

    # live:ENT-3 — did the device-sibling rescue actually RUN? Every failure
    # path in it returned the candidates unchanged and logged nothing, so a
    # dump could not tell a rescue that died from one that found nothing.
    if isinstance(caps, dict) and caps.get("entity_augmentation"):
        out["entity_augmentation"] = caps["entity_augmentation"]

    # DIAG-1: the counterpart to the table above. Read them together — declared
    # roles that failed to resolve, against what the device really has.
    out["device_entities"] = _device_entity_census(hass, vacuum_entity_id)

    # The one-line verdict, so a reader does not have to cross-reference two
    # lists by eye. Unresolved roles WITH siblings present is the shape of a
    # naming mismatch (live:ENT-1); unresolved roles with no siblings is a
    # genuinely reduced device.
    _unresolved = sorted(
        role for role, snap in entity_resolution.items() if not snap.get("exists")
    )
    # live:ENT-2 — pattern-resolved roles are NOT in caps["entities"], so without this
    # the verdict below is computed over the declared roles alone and can read
    # "no naming mismatch" on an install whose only broken role is a pattern one.
    out["pattern_resolution"] = _pattern_resolution(hass, manager, vacuum_entity_id)
    _pattern_unresolved = sorted(
        f"{role} (pattern)"
        for role, info in out["pattern_resolution"].items()
        if not info.get("derived_exists")
    )
    _sibling_count = out["device_entities"].get("entity_count")
    out["entity_resolution_summary"] = {
        "declared": len(entity_resolution) + len(out["pattern_resolution"]),
        # A pattern role appears here when its DERIVATION fails, even if an override or
        # the device-sibling fallback makes the feature work — "the derived name is
        # wrong" and "the feature is broken" are different facts, and conflating them is
        # what let this hide behind a manual repair.
        "unresolved": _unresolved + _pattern_unresolved,
        "device_entity_count": _sibling_count,
        "likely_naming_mismatch": bool(
            (_unresolved or _pattern_unresolved)
            and isinstance(_sibling_count, int)
            and _sibling_count > 0
        ),
    }

    # live:ENT-11 — the Setup -> System binding table, verbatim.
    #
    # `entity_resolution_summary` above answers "did anything fail to resolve".
    # That is structurally blind to the defect the System tab exists for: a
    # COLLISION resolves successfully, to a real enabled entity, just the wrong
    # one — a per-run cleaning-area role bound to a lifetime counter reads
    # thousands of times too high and never errors. A summary of failures reports
    # that install as healthy.
    #
    # Shipping the same rows here means a reporter attaches ONE diagnostics file
    # instead of being asked to find a screen and screenshot it — the round trip
    # that has cost issue #49 several exchanges. Same builder as the card's, so
    # the two can never drift into disagreeing about what we read.
    try:
        out["entity_bindings"] = manager._entity_bindings(vacuum_entity_id)
    except Exception:  # pragma: no cover - defensive
        # Best-effort, exactly like the rest of this file: a diagnostics dump that
        # raises is worth less than one missing a section.
        out["entity_bindings"] = {"error": "unavailable"}

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

    # Completion / lifecycle health — the tripwire for upstream capability-gating
    # dropping the job-active binary (HA 2026.7, home-assistant/core#173282).
    #
    # A brand that gates completion on it (completion.require_job_active_clear,
    # e.g. Roborock) cannot ARM the completion gate without it, and the
    # consequence is NOT a quiet stall: is_stranded_started's unarmed branch
    # (jobs/job_monitor.py) returns True on AGE ALONE at NEVER_STARTED_SECONDS,
    # so the 1-minute reaper force-closes the run as "interrupted" a grace period
    # later — roughly 15 minutes after dispatch, possibly MID-CLEAN.
    #
    # Presence now distinguishes DECLARED-BUT-NEVER-CREATED (absent from the
    # state machine AND the registry — the #46 shape) from registered-but-
    # momentarily-stateless (an ordinary restart window). The previous wording
    # collapsed both into "the device appears disconnected ... no run can even be
    # dispatched", which is wrong twice over: no dispatch path reads
    # entities.job_active at all, and a real affected dump (Roborock Q5, issue
    # #46) shows every OTHER entity reporting normally while only this binary is
    # gone. Telling that user to check their connection sends them after a
    # problem they do not have.
    try:
        from .adapters.registry import get_adapter_config as _get_cfg2
        from .job_active_signal import probe_presence as _probe_job_active

        _cfg2 = _get_cfg2(vacuum_entity_id) or {}
        _requires_job_active = bool(
            (_cfg2.get("completion") or {}).get("require_job_active_clear")
        )
        _presence = _probe_job_active(hass, vacuum_entity_id)
        _ents2 = _cfg2.get("entities") or {}

        def _fallback_signal(key: str) -> dict[str, Any]:
            _eid = _ents2.get(key)
            _st = hass.states.get(_eid) if _eid else None
            return {
                "entity_id": _eid,
                "exists": _st is not None,
                "state": str(_st.state) if _st is not None else None,
            }

        _health: dict[str, Any] = {
            "requires_job_active_clear": _requires_job_active,
            # kept as-is: existing consumers/tests read these two names
            "job_active_entity": _presence.entity_id,
            "job_active_present": _presence.has_state,
            "job_active": _presence.as_dict(),
            # Candidate substitutes for a missing binary. Reported so an affected
            # install's FIRST dump answers "is there anything to rebuild the
            # signal from?" instead of costing a round trip to ask. Neither gates
            # anything today — see job_active_signal.py.
            "fallback_signals": {
                "last_clean_end": _fallback_signal("last_clean_end"),
                "total_cleaning_count": _fallback_signal("total_cleaning_count"),
            },
        }
        if _requires_job_active and not _presence.has_state:
            if _presence.never_created:
                _health["warning"] = (
                    f"The job-active binary ({_presence.entity_id}) is DECLARED but "
                    "was never created — absent from both the state machine and the "
                    "entity registry. This is the Home Assistant 2026.7 "
                    "capability-gating change (home-assistant/core#173282), not a "
                    "connectivity problem: check whether this vacuum's other "
                    "entities are reporting normally above. Completion cannot arm, "
                    "so a dispatched run is force-closed as 'interrupted' about 15 "
                    "minutes in — possibly while it is still cleaning. Tracked as "
                    "issue #46."
                )
            else:
                _health["warning"] = (
                    f"The job-active binary "
                    f"({_presence.entity_id or 'not declared'}) is in the entity "
                    "registry but has no state right now — normally the brief window "
                    "after a restart, or a device that is offline. Check it is online "
                    "and wake it (e.g. a state refresh). If it never comes back, the "
                    "upstream integration may have dropped the entity (issue #46)."
                )
        out["completion_health"] = _health
    except Exception as err:  # pragma: no cover - defensive
        out["completion_health"] = {"error": _redact(repr(err))}

    # cleaning_area unit — a USER-TOGGLEABLE flag (the HA unit system AND the Eufy app), so we
    # normalize to m² LIVE on every read (learning/utils.cleaning_area_to_m2) rather than caching
    # it. Surface the CURRENTLY detected unit + the normalized value here so a flipped or
    # mis-declared unit is a visible, checkable fact — not something inferred from a weird area
    # later. Recorded live 2026-07-11: Alfred cleaning_area = ft², Ivy = m².
    try:
        from .learning.utils import _AREA_TO_M2, cleaning_area_to_m2

        _ca_entity = entities_map.get("cleaning_area")
        if _ca_entity:
            _ca_state = hass.states.get(_ca_entity)
            _raw = getattr(_ca_state, "state", None) if _ca_state else None
            _unit = (
                getattr(_ca_state, "attributes", {}).get("unit_of_measurement")
                if _ca_state
                else None
            )
            _u = str(_unit or "").strip().lower()
            _recognized = (not _u) or (_u in _AREA_TO_M2)
            _area_units: dict[str, Any] = {
                "entity": _ca_entity,
                "detected_unit": _unit,
                "raw_value": _raw,
                "normalized_m2": cleaning_area_to_m2(_raw, _unit),
                # True when we actually rescaled (a non-m² recognized unit, e.g. ft²).
                "converted": bool(_u in _AREA_TO_M2 and _AREA_TO_M2[_u] != 1.0),
                "recognized": _recognized,
            }
            if not _recognized:
                _area_units["warning"] = (
                    f"cleaning_area unit '{_unit}' is unrecognized — the value is used AS-IS "
                    "(assumed m²); if it is an imperial unit the stored area will be wrong."
                )
            out["area_units"] = _area_units
    except Exception as err:  # pragma: no cover - defensive
        out["area_units"] = {"error": _redact(repr(err))}

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
        out["maps_error"] = _redact(repr(err))

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
            managed_rooms_by_map[map_id] = {"error": _redact(repr(err))}
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
        out["roborock_geometry_drift_error"] = _redact(repr(err))

    # Upkeep (maintenance / dock) — side-effect-free. RF-33 cont'd: this used to
    # be the SECOND independent non-inert path (get_upkeep_snapshot's own
    # capabilities lookup, plus its per-component get_maintenance_remaining call,
    # both called get_vacuum_capabilities(refresh=False)) — now both read via the
    # inert get_vacuum_capabilities_snapshot (see maintenance/manager.py), so this
    # collector no longer risks a first-detect write on a diagnostics pull. The
    # per-item care guides (static how-to-clean steps) are stripped below: model
    # boilerplate with no diagnostic value that otherwise dominates the dump's
    # size.
    try:
        out["upkeep_snapshot"] = _slim_upkeep(
            manager.get_upkeep_snapshot(vacuum_entity_id=vacuum_entity_id)
        )
    except Exception as err:  # pragma: no cover - defensive
        out["upkeep_snapshot_error"] = _redact(repr(err))

    # Interpreted, human-readable summary of everything above. Computed last
    # (needs all signals) but surfaced right after the id so it reads first.
    try:
        summary = _self_check(out)
    except Exception as err:  # pragma: no cover - defensive
        summary = {"error": _redact(repr(err))}
    ordered: dict[str, Any] = {
        "vacuum_entity_id": vacuum_entity_id,
        "self_check": summary,
    }
    for key, value in out.items():
        if key != "vacuum_entity_id":
            ordered[key] = value
    return ordered


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for ONE vacuum — the device page's Download button.

    Without this hook HA falls back to the config-entry dump, so pressing
    "Download diagnostics" on Alfred's device page hands you every vacuum on the
    install. The button is per-device; the file should be too. On a two-vacuum box
    that is half the noise, and the irrelevant half is the half a reporter has to
    be told to ignore.

    The device is resolved back to its vacuum by the SAME identifier
    `build_vacuum_device_info` builds it from, never by matching on the device
    NAME — that name is derived from the vacuum's object_id at creation time and
    does not track a later rename (it is why one box shows both
    `sensor.alfred_active_job` and `sensor.other_alfred_active_job`).
    """
    diag = await async_get_config_entry_diagnostics(hass, entry)
    wanted = {ident for domain, ident in device.identifiers if domain == DOMAIN}
    if not wanted or not isinstance(diag.get("vacuums"), list):
        # Unknown shape: hand back the whole entry rather than an empty file.
        # A dump that is merely broad is still usable; one that is empty is not.
        return diag
    scoped = [
        v for v in diag["vacuums"]
        if str(v.get("vacuum_entity_id", "")).replace(".", "_") in wanted
    ]
    # Same reasoning: if the match finds nothing, the identifier convention has
    # drifted and a silent empty list would read as "this vacuum has no data".
    if scoped:
        diag["vacuums"] = scoped
        diag["scope"] = "device"
    else:
        diag["scope"] = "entry (device match found nothing)"
    return diag


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Vacuum Agent config entry."""
    diag: dict[str, Any] = {
        "entry": {
            # RP-039/RF-33: entry.title is the same class as "notes" -- free-text,
            # user-editable, and diagnostics is exactly where a pasted secret
            # would otherwise leak -- so route it through the SAME redaction
            # mechanism as entry.data/entry.options rather than emitting it raw.
            "title": async_redact_data({"title": entry.title}, TO_REDACT)["title"],
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
        diag["integration_version_error"] = _redact(repr(err))

    try:
        vacuum_ids = list(manager.get_known_vacuum_ids())
    except Exception as err:  # pragma: no cover - defensive
        diag["vacuums_error"] = _redact(repr(err))
        return diag

    # Read-only: the dashboard snapshot is deliberately NOT collected here (see
    # the module docstring) — computing it can fire room-transition events and
    # persist during a live clean. Everything in _vacuum_diagnostics is read-only.
    #
    # ROBORO-2: _vacuum_diagnostics is plain sync (no `await` anywhere in it) and, on a
    # Roborock memory-backend device, its geometry-drift check walks
    # roborock_geometry_drift_from_candidates -> geometry_drift -> raster_room_bboxes, a
    # full width*height Python for-loop over the decoded raster (up to ~1M pixels) — real
    # blocking CPU work with no executor dispatch anywhere in that chain. Dispatching each
    # vacuum's block to the executor here (rather than deeper in the call chain) covers the
    # whole synchronous function in one place instead of hunting every CPU-heavy branch
    # inside it individually.
    vacuums = list(await asyncio.gather(
        *(hass.async_add_executor_job(_vacuum_diagnostics, hass, manager, vac)
          for vac in vacuum_ids)
    ))

    diag["vacuums"] = async_redact_data(vacuums, TO_REDACT)
    return diag
