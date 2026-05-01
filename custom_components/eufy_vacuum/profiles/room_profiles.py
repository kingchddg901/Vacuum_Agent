"""Room profile definitions, resolution, and capability gating for the Eufy Vacuum integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]


class ProfileRecord(TypedDict, total=False):
    """Canonical shape for a stored or built-in room profile dict (documentation-only)."""

    profile_id: str
    name: str
    label: str
    is_builtin: bool
    clean_mode: Optional[str]
    fan_speed: Optional[str]
    water_level: Optional[str]
    clean_intensity: Optional[str]
    clean_passes: Optional[int]
    edge_mopping: Optional[bool]
    path_type: Optional[str]    # "wide" | "narrow" | None
    mop_required: Optional[bool]


class EffectiveRoomSettings(TypedDict, total=False):
    """Output shape of ``resolve_room_profile_for_room()`` (documentation-only).

    ``path_type`` is always present. ``capability_gated`` is added by
    ``apply_capability_gate()``. ``floor_type`` encodes material and carpet
    pile in one value (e.g. ``"carpet_low_pile"``).
    """

    selected_profile_name: str
    resolved_profile_name: str
    selected_profile_label: str
    resolved_profile_label: str
    floor_type: str
    clean_mode: str
    fan_speed: str
    water_level: str
    clean_intensity: str
    path_type: str              # always present after Wave 2
    clean_passes: int
    edge_mopping: bool
    capability_gated: bool      # added by apply_capability_gate() in Wave 3

BUILT_IN_ROOM_PROFILES: dict[str, dict[str, Any]] = {
    "vacuum_quick": {
        "label": "Vacuum Only Quick",
        "clean_mode": "vacuum",
        "fan_speed": "Standard",
        "water_level": "Off",
        "clean_intensity": "Quick",
        "path_type": "wide",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_deep": {
        "label": "Vacuum Only Deep",
        "clean_mode": "vacuum",
        "fan_speed": "Max",
        "water_level": "Off",
        "clean_intensity": "Deep",
        "path_type": "narrow",
        "clean_passes": 2,
        "edge_mopping": False,
        "mop_required": False,
    },
    "vacuum_mop_quick": {
        "label": "Quick",
        "clean_mode": "vacuum_mop",
        "fan_speed": "Standard",
        "water_level": "Medium",
        "clean_intensity": "Quick",
        "path_type": "wide",
        "clean_passes": 1,
        "edge_mopping": False,
        "mop_required": True,
    },
    "vacuum_mop_deep": {
        "label": "Deep",
        "clean_mode": "vacuum_mop",
        "fan_speed": "Max",
        "water_level": "Medium",
        "clean_intensity": "Deep",
        "path_type": "narrow",
        "clean_passes": 2,
        "edge_mopping": True,
        "mop_required": True,
    },
}

DEFAULT_CUSTOM_ROOM_PROFILE: dict[str, Any] = {
    "label": "User Profile 1",
    "clean_mode": "vacuum",
    "fan_speed": "Max",
    "water_level": "Off",
    "clean_intensity": "Standard",
    "path_type": "wide",
    "clean_passes": 1,
    "edge_mopping": False,
    "mop_required": False,
}

LEGACY_PROFILE_ALIASES: dict[str, str] = {
    "vacuum_standard": "vacuum_quick",
    "vacuum_mop_standard": "vacuum_mop_quick",
}

FLOOR_TYPE_WATER_DEFAULTS: dict[str, str] = {
    "hardwood": "Low",
    "laminate": "Low",
    "tile": "Medium",
    "marble": "Low",
    "carpet_low_pile": "Off",
    "carpet_high_pile": "Off",
}

# Carpet suction defaults keyed by pile height encoded in floor_type.
FLOOR_TYPE_FAN_DEFAULTS: dict[str, str] = {
    "carpet_low_pile": "Max",
    "carpet_high_pile": "Standard",
}


def get_default_room_profiles() -> dict[str, dict[str, Any]]:
    """Return default room profiles including the legacy user slot."""
    profiles = deepcopy(BUILT_IN_ROOM_PROFILES)
    profiles["user_1"] = deepcopy(DEFAULT_CUSTOM_ROOM_PROFILE)
    return profiles


def normalize_room_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Return a fully normalized room profile dict with safe defaults for all keys."""
    source = profile or {}

    return {
        "label": str(source.get("label", "User Profile 1")),
        "clean_mode": str(source.get("clean_mode", "vacuum")),
        "fan_speed": str(source.get("fan_speed", "Max")),
        "water_level": str(source.get("water_level", "Off")),
        "clean_intensity": str(source.get("clean_intensity", "Standard")),
        "path_type": str(source.get("path_type", "wide")),
        "clean_passes": int(source.get("clean_passes", 1)),
        "edge_mopping": bool(source.get("edge_mopping", False)),
        "mop_required": bool(source.get("mop_required", False)),
    }


def merge_profile_dicts(
    *,
    built_in_profiles: dict[str, dict[str, Any]],
    stored_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return built-in profiles merged with stored custom profiles; stored values overwrite built-ins."""
    merged = deepcopy(built_in_profiles)
    stored_profiles = stored_profiles or {}

    for profile_name, profile in stored_profiles.items():
        profile_key = str(profile_name or "").strip()
        if not profile_key:
            continue
        merged[profile_key] = normalize_room_profile(profile)

    return merged


def _normalize_profile_name(profile_name: str | None) -> str:
    """Normalize profile names and map legacy aliases."""
    raw = str(profile_name or "vacuum_quick").strip()
    return LEGACY_PROFILE_ALIASES.get(raw, raw)


def _normalize_floor_type(floor_type: str | None) -> str:
    """Normalize floor type.

    Canonical values: "hardwood", "laminate", "tile", "marble",
    "carpet_low_pile", "carpet_high_pile".
    Legacy value "carpet" is migrated to "carpet_low_pile".
    """
    raw = str(floor_type or "hardwood").strip().lower()
    if raw == "carpet":
        return "carpet_low_pile"
    allowed = {"hardwood", "laminate", "tile", "marble", "carpet_low_pile", "carpet_high_pile"}
    return raw if raw in allowed else "hardwood"


def get_room_profile(
    *,
    profile_name: str | None,
    stored_profiles: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return ``(resolved_name, normalized_profile)`` for the given profile name.

    Falls back to ``vacuum_quick`` when the name is unknown.
    """
    merged = merge_profile_dicts(
        built_in_profiles=get_default_room_profiles(),
        stored_profiles=stored_profiles,
    )

    normalized_name = _normalize_profile_name(profile_name)
    profile = merged.get(normalized_name)

    if profile is None:
        normalized_name = "vacuum_quick"
        profile = merged[normalized_name]

    return normalized_name, normalize_room_profile(profile)


def get_available_profile_names(
    *,
    capabilities: dict[str, Any] | None = None,
) -> list[str]:
    """Return the list of profile names allowed for the given vacuum capabilities.

    Mop profiles are excluded entirely when the vacuum does not support mopping.
    """
    capabilities = capabilities or {}
    supports_mop = bool(capabilities.get("supports_mop_features", False))
    supports_water = bool(capabilities.get("supports_water_control", False))

    if supports_mop and supports_water:
        return [
            "vacuum_quick",
            "vacuum_deep",
            "vacuum_mop_quick",
            "vacuum_mop_deep",
        ]

    return [
        "vacuum_quick",
        "vacuum_deep",
    ]


def get_available_profiles(
    *,
    capabilities: dict[str, Any] | None = None,
    stored_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return normalized profiles filtered to those allowed by the vacuum's capabilities."""
    all_profiles = merge_profile_dicts(
        built_in_profiles=get_default_room_profiles(),
        stored_profiles=stored_profiles,
    )

    allowed_names = set(get_available_profile_names(capabilities=capabilities))

    return {
        name: normalize_room_profile(profile)
        for name, profile in all_profiles.items()
        if name in allowed_names
    }


def resolve_profile_name_for_constraints(
    *,
    profile_name: str,
    floor_type: str,
) -> str:
    """Resolve the final profile name after applying hard constraints.

    Rule:
    - carpet floor forces vacuum-only behavior
    - vacuum_mop_quick -> vacuum_quick
    - vacuum_mop_deep -> vacuum_deep
    """
    normalized_name = _normalize_profile_name(profile_name)

    if not floor_type.startswith("carpet"):
        return normalized_name

    if normalized_name == "vacuum_mop_quick":
        return "vacuum_quick"

    if normalized_name == "vacuum_mop_deep":
        return "vacuum_deep"

    if normalized_name == "vacuum_mop_standard":
        return "vacuum_quick"

    return normalized_name


def resolve_room_profile_for_room(
    *,
    room_config: dict[str, Any],
    stored_profiles: dict[str, dict[str, Any]] | None = None,
) -> EffectiveRoomSettings:
    """Resolve final effective settings for a room from its profile and metadata.

    Resolution order: selected profile → floor-type defaults →
    hard constraints (carpet forces vacuum-only) → per-room overrides.
    Returns an ``EffectiveRoomSettings`` dict; does not mutate inputs.
    """
    selected_profile_name, selected_profile = get_room_profile(
        profile_name=room_config.get("profile_name"),
        stored_profiles=stored_profiles,
    )

    floor_type = _normalize_floor_type(room_config.get("floor_type"))

    resolved_profile_name = resolve_profile_name_for_constraints(
        profile_name=selected_profile_name,
        floor_type=floor_type,
    )

    _, resolved_profile = get_room_profile(
        profile_name=resolved_profile_name,
        stored_profiles=stored_profiles,
    )

    resolved_clean_mode = str(room_config.get("clean_mode", resolved_profile.get("clean_mode", "vacuum")))
    resolved_clean_intensity = str(
        room_config.get("clean_intensity", resolved_profile.get("clean_intensity", "Standard"))
    )
    resolved_path_type = str(room_config.get("path_type", resolved_profile.get("path_type", "wide")))
    resolved_edge_mopping = bool(room_config.get("edge_mopping", resolved_profile.get("edge_mopping", False)))

    resolved_fan_speed = str(room_config.get("fan_speed", resolved_profile.get("fan_speed", "Max")))
    resolved_water_level = str(room_config.get("water_level", resolved_profile.get("water_level", "Off")))

    # Carpet overrides fan speed and suppresses water; hard floors apply
    # per-surface water defaults only when the room has no explicit override.
    if floor_type.startswith("carpet"):
        resolved_fan_speed = FLOOR_TYPE_FAN_DEFAULTS.get(floor_type, "Max")
        resolved_water_level = "Off"
    elif "water_level" not in room_config:
        resolved_water_level = FLOOR_TYPE_WATER_DEFAULTS.get(floor_type, "Low")

    # Mop mode with water Off is invalid — fall back to the floor's water default.
    if resolved_clean_mode in {"mop", "vacuum_mop"} and resolved_water_level == "Off" and not floor_type.startswith("carpet"):
        resolved_water_level = FLOOR_TYPE_WATER_DEFAULTS.get(floor_type, "Low")

    # Edge mopping is only meaningful for mop modes on non-carpet floors.
    if resolved_clean_mode not in {"mop", "vacuum_mop"} or floor_type.startswith("carpet"):
        resolved_edge_mopping = False

    passes = int(room_config.get("clean_passes", resolved_profile.get("clean_passes", 1)))

    return {
        "selected_profile_name": selected_profile_name,
        "resolved_profile_name": resolved_profile_name,
        "selected_profile_label": selected_profile.get("label", selected_profile_name),
        "resolved_profile_label": resolved_profile.get("label", resolved_profile_name),
        "floor_type": floor_type,
        "clean_mode": resolved_clean_mode,
        "fan_speed": resolved_fan_speed,
        "water_level": resolved_water_level,
        "clean_intensity": resolved_clean_intensity,
        "path_type": resolved_path_type,
        "clean_passes": passes,
        "edge_mopping": resolved_edge_mopping,
    }


def apply_capability_gate(
    settings: dict,
    capabilities: dict,
    *,
    resolved_profile_name: str | None = None,
) -> dict:
    """Return a copy of ``settings`` with values clamped to device capabilities.

    Called at payload-build time, not during profile resolution — the resolver
    produces display/storage values; gating is strictly a payload concern.
    Returns a new dict; the input is not mutated.
    """
    capabilities = capabilities or {}

    supports_mop = bool(capabilities.get("supports_mop_features", False))
    supports_water = bool(capabilities.get("supports_water_control", False))
    supports_path = bool(capabilities.get("supports_path_control", False))
    supports_edge = bool(capabilities.get("supports_edge_mopping", False))
    supports_passes = bool(capabilities.get("supports_passes", True))

    clean_mode = str(settings.get("clean_mode", "vacuum"))
    fan_speed = str(settings.get("fan_speed", "Max"))
    water_level = str(settings.get("water_level", "Off"))
    clean_intensity = str(settings.get("clean_intensity", "Standard"))
    path_type = str(settings.get("path_type", "wide"))
    clean_passes = int(settings.get("clean_passes", 1))
    edge_mopping = bool(settings.get("edge_mopping", False))

    # Mop unsupported — downgrade to vacuum-only equivalent.
    if not supports_mop and clean_mode in {"mop", "vacuum_mop"}:
        if resolved_profile_name == "vacuum_mop_deep":
            clean_mode = "vacuum"
            water_level = "Off"
            edge_mopping = False
            path_type = "narrow"
            clean_intensity = "Deep"
        else:
            clean_mode = "vacuum"
            water_level = "Off"
            edge_mopping = False
            path_type = "wide"
            clean_intensity = "Quick"

    # Vacuum-only mode — water and edge mopping are irrelevant.
    if clean_mode == "vacuum":
        water_level = "Off"
        edge_mopping = False

    if not supports_water:
        water_level = "Off"
    if not supports_edge:
        edge_mopping = False
    if not supports_path:
        path_type = "wide"
    if not supports_passes:
        clean_passes = 1

    gated = dict(settings)
    gated.update(
        {
            "clean_mode": clean_mode,
            "fan_speed": fan_speed,
            "water_level": water_level,
            "clean_intensity": clean_intensity,
            "path_type": path_type,
            "clean_passes": clean_passes,
            "edge_mopping": edge_mopping,
            "capability_gated": True,
        }
    )
    return gated


def apply_room_profile_to_config(
    *,
    room_config: dict[str, Any],
    profile_name: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy of ``room_config`` with the given profile's settings applied."""
    updated = dict(room_config)
    normalized = normalize_room_profile(profile)

    updated["profile_name"] = _normalize_profile_name(profile_name)
    updated["clean_mode"] = normalized["clean_mode"]
    updated["fan_speed"] = normalized["fan_speed"]
    updated["water_level"] = normalized["water_level"]
    updated["clean_intensity"] = normalized["clean_intensity"]
    updated["clean_passes"] = normalized["clean_passes"]
    updated["edge_mopping"] = bool(normalized["edge_mopping"])
    updated["path_type"] = normalized.get("path_type")
    # Normalize floor_type on write so legacy "carpet" values are migrated in place.
    updated["floor_type"] = _normalize_floor_type(updated.get("floor_type"))
    return updated
