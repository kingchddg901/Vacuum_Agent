"""Room profile definitions, resolution, and capability gating for the Eufy Vacuum integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]


class UndeclaredProfileCatalogError(RuntimeError):
    """Resolution was asked for a profile and the catalog supplies none.

    Deliberately not a ``HomeAssistantError`` — this module is HA-free pure logic
    and stays testable without a hass fixture. Service layers translate it.
    """


class ProfileRecord(TypedDict):
    """Canonical shape of a stored or built-in room profile dict (documentation-only).

    Exactly the 9 keys ``normalize_room_profile`` produces and every brand catalog
    declares — all always present. The store key IS the ``profile_name``; the record
    itself carries no ``id`` / ``name`` / ``is_builtin``.
    """

    label: str
    clean_mode: str
    fan_speed: str
    water_level: str
    clean_intensity: str
    path_type: str              # "wide" | "narrow"
    clean_passes: int
    edge_mopping: bool
    mop_required: bool


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

# CORE OWNS THE KEY SPACE. IT DOES NOT OWN ANY BRAND'S WORDS.
#
# The profile VALUES that used to live here were Eufy's — Eufy was the first
# brand, so its vocabulary was written as "the" vocabulary and every other brand
# inherited it by omission. They now live in ``adapters/eufy/room_profiles.py``,
# where the brand that speaks them can own them.
#
# What legitimately stays is the KEY space: these four names are framework
# identity, and both shipped brands declare exactly them on purpose so stored
# rooms and the profile picker survive a brand switch. They are also the source
# of the protected-name set that stops a user renaming or deleting a built-in.
#
# There is NO framework default catalog and no fallback. An adapter declares its
# own profiles, or declares the contract supported with none (``builtins: {}``).
# A MISSING key is neither — it is an incomplete declaration, and
# ``registry._validate_adapter`` reports it. Absent must not quietly mean empty,
# or "this brand has no profiles" becomes indistinguishable from "the porter
# forgot", which is the fail-soft ambiguity this change exists to remove.
PROTECTED_ROOM_PROFILE_NAMES: frozenset[str] = frozenset({
    "vacuum_quick",
    "vacuum_deep",
    "vacuum_mop_quick",
    "vacuum_mop_deep",
})

#: The profile a newly-discovered room gets when its adapter names none.
#: A KEY, not a vocabulary — it says WHICH profile, never what is in it.
DEFAULT_ROOM_PROFILE_NAME = "vacuum_quick"


def coerce_clean_intensity(value: Any) -> str:
    """Coerce a stored ``clean_intensity`` to a trimmed string; None becomes "".

    Carries NO vocabulary. This used to be ``normalize_clean_intensity``, which
    additionally folded the retired Eufy values ``standard``/``normal`` to
    ``"Quick"`` — a Eufy word in core, executed on every read from nine call
    sites to repair data written before 2026-07-26. That fold is now a one-shot
    store repair (``rooms/vocabulary_migration.py``) reached without any
    retired-value map: ``Standard`` is simply absent from Eufy's declared
    ``clean_intensity_options``, and the brand's own ``default_profile`` supplies
    ``"Quick"``. Same answer, from a declaration rather than a constant, computed
    once instead of forever.

    The coercion itself stays and is load-bearing: a brand that declares no
    intensity axis (Roborock omits it from every profile) yields None here, and a
    bare ``str()`` would write the string ``"None"`` into a room.
    """
    return str(value if value is not None else "").strip()


def no_water_value(catalog: dict[str, Any] | None) -> str:
    """The word THIS brand uses for "no water", read from its declaration.

    Carpet is the one surface where the framework guarantees water off, so a brand's
    ``floor_type_water_defaults`` entry for carpet IS its no-water word.
    ``resolve_room_profile_for_room`` already reads it this way; ``apply_capability_gate``
    did not, and assigned the literal ``"Off"`` at three sites. Roborock's value is
    ``"off"``, which is not in its declared ``water_level_options``, so dispatch
    filtered the setting out and mop intensity was never applied on a mop-settable
    model. The literal was removed from one function and left in its sibling.

    Undeclared yields ``""`` rather than a guess — there is no framework word for this.
    """
    defaults = (catalog or {}).get("floor_type_water_defaults") or {}
    for carpet in ("carpet_low_pile", "carpet_high_pile"):
        if carpet in defaults:
            return str(defaults[carpet])
    return ""


def _catalog_key(block: dict[str, Any], key: str, default: Any) -> Any:
    """RP-025/RF-18 clause (ii): presence, not truthiness — ``key in block`` so a
    brand's DECLARED-empty value (e.g. ``builtins: {}``, "this brand ships no
    framework built-ins") is honored, not conflated with the key being absent
    entirely. The old ``block.get(key) or default`` treated any falsy declared
    value identically to "absent", silently injecting the Eufy in-code default
    in its place — the brand's explicit "we have none" was unrepresentable.
    An explicit ``None`` is still treated as absent (there is no meaningful
    "declared None" for any of these dict/str-typed fields)."""
    if key not in block or block[key] is None:
        return default
    return block[key]


def resolve_profile_catalog(block: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve an adapter's ``room_profiles`` block. There is NO framework default.

    Returns the seven catalog keys (builtins / custom_template / legacy_aliases /
    default_profile / floor_type_water_defaults / floor_type_fan_defaults /
    normalize_defaults), carrying exactly what the adapter declared.

    Core holds no brand's vocabulary, so an undeclared key resolves EMPTY rather
    than to somebody else's words. What used to sit here was Eufy's catalog
    wearing a framework badge: a brand that declared nothing inherited ``"Max"``
    and ``"Boost"``, the card matched no option, and an unedited room applied no
    suction at all.

    Absent and declared-empty resolve the SAME WAY here, and that is deliberate —
    this function's job is resolution, not judgement. The two states are
    distinguished where the distinction is actionable: ``registry._validate_adapter``
    reports a missing ``builtins`` as an incomplete declaration, and the brand-
    agnostic contract suite makes it a hard failure. Were absence quietly
    equivalent to ``{}`` everywhere, "this brand has no profiles" and "the porter
    forgot" would be the same state, which is precisely the fail-soft ambiguity
    removing the fallback was meant to end.

    ``default_profile`` is the one key that still carries a framework value, and
    it is not vocabulary: it names WHICH profile a new room starts on, never what
    is inside it.
    """
    block = block if isinstance(block, dict) else {}
    return {
        "builtins": _catalog_key(block, "builtins", {}),
        "custom_template": _catalog_key(block, "custom_template", {}),
        "legacy_aliases": _catalog_key(block, "legacy_aliases", {}),
        "default_profile": _catalog_key(block, "default_profile", DEFAULT_ROOM_PROFILE_NAME),
        "floor_type_water_defaults": _catalog_key(block, "floor_type_water_defaults", {}),
        "floor_type_fan_defaults": _catalog_key(block, "floor_type_fan_defaults", {}),
        "normalize_defaults": _catalog_key(block, "normalize_defaults", {}),
    }


def get_default_room_profiles(catalog: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return the default room profiles (the built-in catalog).

    ``catalog`` is a resolved ``room_profiles`` block. There are no in-code
    built-ins to fall back to — an absent or empty catalog yields ``{}``, because
    core owns no brand's profile vocabulary.

    The legacy ``user_1`` "starting custom slot" is intentionally NOT injected
    here. It predated multi-profile "Save as New", and as a *pristine* framework
    default it surfaced as an undeletable "User Profile 1" chip in the room editor
    — it lives in no user store, so a delete found nothing (profile_not_found) and
    it reappeared on every fetch. A ``user_1`` a user has actually saved-over still
    lives in the stored profiles and is returned by the merge as real, deletable
    data; ``custom_template`` remains in the resolved catalog for callers that want
    the starting-settings template explicitly."""
    cat = catalog or {}
    return deepcopy(cat.get("builtins") or {})


def normalize_room_profile(
    profile: dict[str, Any] | None, catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return a fully normalized room profile dict with safe defaults for all keys.

    Framework-canonical fields (label/clean_mode/path_type/clean_passes/
    edge_mopping/mop_required) fall back to the catalog's ``normalize_defaults``
    (the adapter's ``normalize_defaults``; empty when the adapter declares none, since
    is None — byte-identical).

    Q2/RP-025 clause (i): the DISPLAY-AXIS fields (fan_speed/water_level/
    clean_intensity) do NOT fall through to that same in-code default — it is
    Eufy's own vocabulary ("Max"/"Off"/"Quick"), and using it as a THIRD-level
    fallback meant any brand (or bare utility call) that declares nothing for an
    axis silently acquired Eufy's literals with no brand ever having said so.
    They fall back only to the catalog's OWN explicitly-declared
    ``normalize_defaults`` (Eufy's adapter declares one, so its real behaviour is
    unchanged) — with no catalog at all, "" ("nobody said"), matching the same
    doctrine resolve_room_profile_for_room already follows.
    """
    source = profile or {}
    d = (catalog or {}).get("normalize_defaults") or {}
    brand_defaults = (catalog or {}).get("normalize_defaults") or {}

    return {
        "label": str(source.get("label", d.get("label", "User Profile 1"))),
        "clean_mode": str(source.get("clean_mode", d.get("clean_mode", "vacuum"))),
        "fan_speed": str(source.get("fan_speed", brand_defaults.get("fan_speed", ""))),
        "water_level": str(source.get("water_level", brand_defaults.get("water_level", ""))),
        "clean_intensity": coerce_clean_intensity(
            source.get("clean_intensity", brand_defaults.get("clean_intensity", ""))
        ),
        "path_type": str(source.get("path_type", d.get("path_type", "wide"))),
        "clean_passes": int(source.get("clean_passes", d.get("clean_passes", 1))),
        "edge_mopping": bool(source.get("edge_mopping", d.get("edge_mopping", False))),
        "mop_required": bool(source.get("mop_required", d.get("mop_required", False))),
    }


def merge_profile_dicts(
    *,
    built_in_profiles: dict[str, dict[str, Any]],
    stored_profiles: dict[str, dict[str, Any]] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return built-in profiles merged with stored custom profiles; stored values overwrite built-ins."""
    merged = deepcopy(built_in_profiles)
    stored_profiles = stored_profiles or {}

    for profile_name, profile in stored_profiles.items():
        profile_key = str(profile_name or "").strip()
        if not profile_key:
            continue
        merged[profile_key] = normalize_room_profile(profile, catalog=catalog)

    return merged


def _normalize_profile_name(
    profile_name: str | None, catalog: dict[str, Any] | None = None
) -> str:
    """Normalize profile names and map legacy aliases."""
    cat = catalog or {}
    default_name = cat.get("default_profile") or DEFAULT_ROOM_PROFILE_NAME
    aliases = cat.get("legacy_aliases") or {}
    raw = str(profile_name or default_name).strip()
    return aliases.get(raw, raw)


def _normalize_floor_type(floor_type: str | None) -> str:
    """Normalize floor type.

    Canonical values: "hardwood", "laminate", "tile", "marble", "granite",
    "concrete", "carpet_low_pile", "carpet_high_pile".
    Legacy value "carpet" is migrated to "carpet_low_pile".
    """
    raw = str(floor_type or "hardwood").strip().lower()
    if raw == "carpet":
        return "carpet_low_pile"
    allowed = {
        "hardwood", "laminate", "tile", "marble", "granite", "concrete",
        "carpet_low_pile", "carpet_high_pile",
    }
    return raw if raw in allowed else "hardwood"


def get_room_profile(
    *,
    profile_name: str | None,
    stored_profiles: dict[str, dict[str, Any]] | None = None,
    catalog: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return ``(resolved_name, normalized_profile)`` for the given profile name.

    An unknown name falls back to the catalog's ``default_profile``. If THAT is not
    present either, the catalog supplies no usable profile and this raises — an
    adapter declaring no ``room_profiles.builtins`` cannot resolve a room, and the
    failure names the declaration rather than the profile that happens to be missing.
    Registration is where this is normally caught (``registry._validate_room_profiles``);
    reaching it here means resolution was handed a catalog that never came from a
    registered adapter.
    """
    merged = merge_profile_dicts(
        built_in_profiles=get_default_room_profiles(catalog=catalog),
        stored_profiles=stored_profiles,
        catalog=catalog,
    )

    normalized_name = _normalize_profile_name(profile_name, catalog=catalog)
    profile = merged.get(normalized_name)

    if profile is None:
        normalized_name = (catalog or {}).get("default_profile") or DEFAULT_ROOM_PROFILE_NAME
        profile = merged.get(normalized_name)
    if profile is None:
        raise UndeclaredProfileCatalogError(
            f"cannot resolve room profile {profile_name!r}: no profile named "
            f"{normalized_name!r} and the catalog supplies none to fall back on. "
            f"Declare room_profiles.builtins on the adapter — core holds no catalog."
        )

    return normalized_name, normalize_room_profile(profile, catalog=catalog)


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
    catalog: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return normalized profiles filtered to those allowed by the vacuum's capabilities."""
    all_profiles = merge_profile_dicts(
        built_in_profiles=get_default_room_profiles(catalog=catalog),
        stored_profiles=stored_profiles,
        catalog=catalog,
    )

    allowed_names = set(get_available_profile_names(capabilities=capabilities))

    return {
        name: normalize_room_profile(profile, catalog=catalog)
        for name, profile in all_profiles.items()
        if name in allowed_names
    }


def resolve_profile_name_for_constraints(
    *,
    profile_name: str,
    floor_type: str,
    catalog: dict[str, Any] | None = None,
) -> str:
    """Resolve the final profile name after applying hard constraints.

    Rule:
    - carpet floor forces vacuum-only behavior
    - vacuum_mop_quick -> vacuum_quick
    - vacuum_mop_deep -> vacuum_deep
    """
    normalized_name = _normalize_profile_name(profile_name, catalog=catalog)

    if not floor_type.startswith("carpet"):
        return normalized_name

    if normalized_name == "vacuum_mop_quick":
        return "vacuum_quick"

    if normalized_name == "vacuum_mop_deep":
        return "vacuum_deep"

    if normalized_name == "vacuum_mop_standard":
        return "vacuum_quick"

    return normalized_name


#: Display spellings the card and older records use for the combined mode. The
#: card writes a DISPLAY label ("Vacuum and mop") through update_room_fields,
#: while the framework and adapter value_maps use the token "vacuum_mop".
_CLEAN_MODE_DISPLAY_ALIASES: dict[str, str] = {
    "vacuum and mop": "vacuum_mop",
    "vacuum & mop": "vacuum_mop",
    "vacuum+mop": "vacuum_mop",
    "vac & mop": "vacuum_mop",
    "vacmop": "vacuum_mop",
}


def canonical_clean_mode(value: Any) -> str:
    """Normalize a clean_mode to its canonical token: vacuum | mop | vacuum_mop.

    ISSUE #48. Every "is this a mop mode?" test in the tree had its own spelling
    of the answer, and the two on the room-settings round trip disagreed:

      - SAVE path (_protected_room_config) asks ``"mop" in clean_mode`` — a
        substring test, which matches "Vacuum and mop" and preserves the value.
      - READ path (below) asked ``clean_mode in {"mop", "vacuum_mop"}`` — an
        exact, case-SENSITIVE set, which does not.

    So a user could enable Edge Mopping, have it correctly persisted, and get it
    back as off on every read, forever, with nothing reporting a problem. Same
    for "Mop" and "VACUUM_MOP", which only the case-sensitive copy rejects.

    learning/utils.py already solved this for its own bucket and its docstring
    names the cause exactly — internal records store the display string while
    value_maps use the token. That fix never reached the profile resolver, which
    is the copy the card reads through. This is now the ONE owner; learning's
    private helper delegates here rather than keeping a second table.

    Unknown values pass through lowercased so a brand-specific mode survives.
    """
    text = str(value or "").strip().lower()
    if not text:
        return text
    if text in _CLEAN_MODE_DISPLAY_ALIASES:
        return _CLEAN_MODE_DISPLAY_ALIASES[text]
    # Any phrasing carrying both verbs is a combined vacuum+mop run.
    if "vacuum" in text and "mop" in text:
        return "vacuum_mop"
    return text


def is_mop_clean_mode(value: Any) -> bool:
    """True when this clean_mode wets the floor. THE question, asked once."""
    return canonical_clean_mode(value) in {"mop", "vacuum_mop"}


def resolve_room_profile_for_room(
    *,
    room_config: dict[str, Any],
    stored_profiles: dict[str, dict[str, Any]] | None = None,
    catalog: dict[str, Any] | None = None,
) -> EffectiveRoomSettings:
    """Resolve final effective settings for a room from its profile and metadata.

    Resolution order: selected profile → floor-type defaults →
    hard constraints (carpet forces vacuum-only) → per-room overrides.
    Returns an ``EffectiveRoomSettings`` dict; does not mutate inputs.

    ``catalog`` (a resolved adapter ``room_profiles`` block) sources the built-ins,
    legacy aliases, and floor-type fan/water defaults; None uses the in-code
    constants (byte-identical)."""
    cat = catalog or {}
    fan_defaults = cat.get("floor_type_fan_defaults") or {}
    water_defaults = cat.get("floor_type_water_defaults") or {}

    selected_profile_name, selected_profile = get_room_profile(
        profile_name=room_config.get("profile_name"),
        stored_profiles=stored_profiles,
        catalog=catalog,
    )

    floor_type = _normalize_floor_type(room_config.get("floor_type"))

    resolved_profile_name = resolve_profile_name_for_constraints(
        profile_name=selected_profile_name,
        floor_type=floor_type,
        catalog=catalog,
    )

    _, resolved_profile = get_room_profile(
        profile_name=resolved_profile_name,
        stored_profiles=stored_profiles,
        catalog=catalog,
    )

    # Last-resort fallbacks are "" ("nobody said"), NOT Eufy display literals. They fire
    # only when the room AND the brand's profile both omit the key; a value here would be
    # this module quietly becoming a fourth source of Eufy vocabulary, which is the exact
    # thing rooms/room_defaults.py exists to stop.
    resolved_clean_mode = str(room_config.get("clean_mode", resolved_profile.get("clean_mode", "vacuum")))
    resolved_clean_intensity = coerce_clean_intensity(
        room_config.get("clean_intensity", resolved_profile.get("clean_intensity", ""))
    )
    resolved_path_type = str(room_config.get("path_type", resolved_profile.get("path_type", "wide")))
    resolved_edge_mopping = bool(room_config.get("edge_mopping", resolved_profile.get("edge_mopping", False)))

    resolved_fan_speed = str(room_config.get("fan_speed", resolved_profile.get("fan_speed", "")))
    resolved_water_level = str(room_config.get("water_level", resolved_profile.get("water_level", "")))

    # Carpet overrides fan speed and suppresses water; hard floors apply
    # per-surface water defaults only when the room has no explicit override.
    #
    # Both come from the CATALOG, which a brand declares. floor_type_water_defaults already
    # maps carpet -> the brand's no-water value, so the carpet arm reads it rather than
    # assigning a literal "Off" — that literal wrote Eufy casing into a Roborock
    # resolution, where the value is "off".
    if floor_type.startswith("carpet"):
        resolved_fan_speed = fan_defaults.get(floor_type, "")
        resolved_water_level = water_defaults.get(floor_type, "")
    elif "water_level" not in room_config and "water_level" not in resolved_profile:
        # Q2/RP-024 clause 1: this used to check ONLY the room's own dict, never
        # whether the SELECTED PROFILE supplied water_level -- so a room relying
        # on its profile (the normal case, no per-room override) always failed
        # the old check, and the floor's hard-floor water default silently
        # overwrote whatever the room > profile ladder above had just resolved,
        # even a real, explicit profile water_level. Every sibling field's
        # ladder is untouched by floor_type at all off carpet; this is the one
        # field where "floor default" outranked "explicit profile value".
        resolved_water_level = water_defaults.get(floor_type, "")

    # Mop mode with no water is invalid — fall back to the floor's water default.
    #
    # "No water" is a FRAMEWORK concept; the WORD for it belongs to the brand, and is
    # read from its declaration (the carpet water default) rather than matched against a
    # literal. This was `in ("", "off")`, which was itself a repair — the original strict
    # == "Off" never fired on Roborock, whose value is lowercase, so a mop room with
    # water off stayed dry-mopping. Widening the literal to a case-insensitive pair fixed
    # the two brands that happen to spell it "off" and left every other brand broken in
    # exactly the same way. A brand declaring "dry", "none" or "0" was silently
    # unrecognised, and the correction never ran.
    no_water = no_water_value(catalog)
    _absent_water = {"", no_water.strip().lower()}
    if (
        is_mop_clean_mode(resolved_clean_mode)
        and resolved_water_level.strip().lower() in _absent_water
        and not floor_type.startswith("carpet")
    ):
        resolved_water_level = water_defaults.get(floor_type, "")

    # Edge mopping is only meaningful for mop modes on non-carpet floors.
    # ISSUE #48: this was an exact, case-SENSITIVE set membership test, so the
    # display spelling the card actually stores ("Vacuum and mop") read as
    # not-a-mop-mode and zeroed a correctly-persisted value on every read.
    if not is_mop_clean_mode(resolved_clean_mode) or floor_type.startswith("carpet"):
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
    catalog: dict[str, Any] | None = None,
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

    no_water = no_water_value(catalog)

    clean_mode = str(settings.get("clean_mode", "vacuum"))
    fan_speed = str(settings.get("fan_speed", ""))
    water_level = str(settings.get("water_level", no_water))
    clean_intensity = coerce_clean_intensity(settings.get("clean_intensity", ""))
    path_type = str(settings.get("path_type", "wide"))
    clean_passes = int(settings.get("clean_passes", 1))
    edge_mopping = bool(settings.get("edge_mopping", False))

    # Mop unsupported — downgrade to the vacuum-only equivalent. Derive path_type /
    # clean_intensity from the corresponding vacuum-only built-in profile rather than
    # hardcoding values, so the downgrade follows whatever vocabulary the profile
    # catalog declares (today the Eufy built-ins → wide/Quick, narrow/Deep).
    if not supports_mop and clean_mode in {"mop", "vacuum_mop"}:
        fallback_name = "vacuum_deep" if resolved_profile_name == "vacuum_mop_deep" else "vacuum_quick"
        _, fallback = get_room_profile(profile_name=fallback_name, catalog=catalog)
        clean_mode = "vacuum"
        water_level = no_water
        edge_mopping = False
        path_type = fallback.get("path_type", path_type)
        clean_intensity = fallback.get("clean_intensity", clean_intensity)

    # Vacuum-only mode — water and edge mopping are irrelevant.
    if clean_mode == "vacuum":
        water_level = no_water
        edge_mopping = False

    if not supports_water:
        water_level = no_water
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
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a copy of ``room_config`` with the given profile's settings applied.

    ``catalog`` (the adapter's resolved room-profile catalog) supplies the
    ``normalize_defaults`` for any field the profile omits, so a non-Eufy brand's
    rooms fill from ITS defaults rather than the in-code Eufy ones (fan ``"Max"`` /
    water ``"Off"`` / intensity ``"Standard"``). Absent catalog → the in-code Eufy
    defaults (byte-identical to the pre-catalog behaviour for Eufy).
    """
    updated = dict(room_config)
    normalized = normalize_room_profile(profile, catalog=catalog)

    updated["profile_name"] = _normalize_profile_name(profile_name, catalog=catalog)
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
