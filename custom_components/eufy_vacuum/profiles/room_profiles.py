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


class ProfileRecord(TypedDict, total=False):
    """Canonical shape of a stored or built-in room profile dict (documentation-only).

    The store key IS the ``profile_name``; the record itself carries no ``id`` /
    ``name`` / ``is_builtin``.

    ``total=False`` is load-bearing for the SETTINGS axes, not a convenience — this
    said "all always present" while a brand catalog declares only the axes its devices
    have. ``clean_intensity`` is absent from every Roborock profile and ``path_type``
    from every Eufy one, those two being one physical property (pass density) under
    each brand's own name. ``label`` / ``clean_mode`` / ``clean_passes`` /
    ``edge_mopping`` / ``mop_required`` are framework-owned and do appear throughout.
    """

    label: str
    clean_mode: str
    fan_speed: str
    water_level: str
    clean_intensity: str        # brand-conditional — absent on Roborock
    path_type: str              # "wide" | "narrow" — brand-conditional, absent on Eufy
    clean_passes: int
    edge_mopping: bool
    mop_required: bool


class EffectiveRoomSettings(TypedDict, total=False):
    """Output shape of ``resolve_room_profile_for_room()`` (documentation-only).

    ``capability_gated`` is added by ``apply_capability_gate()``. ``floor_type``
    encodes material and carpet pile in one value (e.g. ``"carpet_low_pile"``).

    ``path_type`` DEPENDS ON WHICH PRODUCER MADE THE DICT, and the two differ:

      * ``resolve_room_profile_for_room`` ALWAYS emits the key — it writes
        ``"path_type": resolved_path_type`` unconditionally, with ``""`` when neither
        the room nor the brand's profile declared the axis. This TypedDict is that
        function's output shape, so on RESOLVER output the key is always there.
      * ``apply_capability_gate`` is the one that REMOVES it (``if path_type:
        gated["path_type"] = path_type`` / ``else: gated.pop("path_type", None)``). On
        a GATED payload the key is genuinely absent for a device with no path control,
        which is why ``queue_engine`` reads ``gated.get("path_type", "")`` — that
        ``.get`` is load-bearing, not defensive redundancy someone can tidy away.

    ⚠ Until 2026-08-24 this paragraph said "brand-conditional, NOT always present"
    while the field annotation below said "always present after Wave 2". Both were
    live, they were direct opposites, and each refuted the other — so whichever a
    reader believed, the other looked like the bug to go and "fix". Neither was right,
    because neither said which producer it was describing.
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
    path_type: str              # resolver always emits it ("" = undeclared); the gate drops it
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
# Absent must not quietly mean empty, or "this brand has no profiles" becomes
# indistinguishable from "the porter forgot", which is the fail-soft ambiguity
# this change exists to remove.
#
# ⚠ THE GATE IS THE BLOCK, NOT EACH KEY. This comment claimed the opposite until
# 2026-08-24 — "a MISSING key ... ``registry._validate_adapter`` reports it" — and
# it does not. ``registry._validate_room_profiles`` fails exactly three states:
# ``room_profiles`` absent from the config, not a dict, or ``{}``; its own docstring
# says so outright ("The gate is the block, not each key"). The only per-key rule in
# ``_validate_adapter`` is a type check — ``room_profiles.{key} must be a dict if
# present`` — which an absent key skips entirely, and
# ``tests/adapters/test_declaration_contract.py``
# ``::test_a_partially_declared_adapter_registers_and_resolves_empty`` PINS that a
# partial block registers with no ``room_profiles`` issue.
#
# So the ambiguity is closed at BLOCK granularity and is STILL OPEN for ``builtins``
# specifically: ``room_profiles: {"legacy_aliases": {}}`` is non-empty, passes
# registration, and resolves ``builtins: {}``. The porter finds out hours later at
# the first room resolution, as ``UndeclaredProfileCatalogError`` — loud, but far
# from the cause, which is the outcome the registration gate exists to prevent.
# Closing it needs a per-key check in ``_validate_room_profiles``. That is a code
# change and it has NOT been made; do not read this banner as saying it has.
PROTECTED_ROOM_PROFILE_NAMES: frozenset[str] = frozenset({
    "vacuum_quick",
    "vacuum_deep",
    "vacuum_mop_quick",
    "vacuum_mop_deep",
})

#: The profile a newly-discovered room gets when its adapter names none.
#: A KEY, not a vocabulary — it says WHICH profile, never what is in it.
DEFAULT_ROOM_PROFILE_NAME = "vacuum_quick"


def coerce_axis_value(value: Any) -> str:
    """Coerce any stored per-room axis value to a trimmed string; None becomes "".

    One coercer for the question every axis asks — "what did the room store here,
    as a string?" — rather than a per-field one. ``clean_intensity`` had it and
    ``path_type`` did not, and the gap is the whole defect: ``RoomConfig.path_type``
    was ``Optional[str] = None``, ``asdict`` wrote that None into storage, and a bare
    ``str()`` on the way back out produced the literal ``"None"``. That string is in
    no brand's vocabulary, so nothing could match it — and it is TRUTHY, so every
    downstream "did this room set a path?" test answered yes and put it on the wire.
    """
    return str(value if value is not None else "").strip()


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
    bare ``str()`` would write the string ``"None"`` into a room. Kept as its own
    name because the call sites read as intensity questions — SEVEN of them in the
    package as of 2026-08-24, three in ``profiles/manager.py`` and four in this
    module; the coercion is ``coerce_axis_value``, shared with every other axis.

    ⚠ That count said "nine", present tense, until 2026-08-24. It was borrowed from
    the paragraph above, where "nine call sites" is HISTORY — it describes the retired
    ``normalize_clean_intensity``. The count is the entire stated reason for keeping a
    one-line alias rather than calling ``coerce_axis_value`` directly, so anyone
    re-opening that decision counted seven and read the rationale as already stale, or
    went hunting for two call sites that no longer exist.
    """
    return coerce_axis_value(value)


#: Per-room settings whose VALUES are a brand's vocabulary. ``clean_passes`` /
#: ``edge_mopping`` are numeric/boolean and belong to no vocabulary.
VOCABULARY_FIELDS: tuple[str, ...] = (
    "clean_mode",
    "fan_speed",
    "water_level",
    "clean_intensity",
    "path_type",
)


def declared_profile_fields(catalog: dict[str, Any] | None) -> set[str]:
    """Every field name appearing in any profile THIS brand declares.

    The single answer to "does this brand have such an axis at all?", asked in two
    places that must agree: the one-shot store repair
    (``rooms/vocabulary_migration.py``) and every room save
    (``ProfileManager._finalize_room_update``). They diverged once and the result was
    a repair that undid itself — the migration dropped ``clean_intensity`` from ten
    Roborock rooms and the next save put it back as ``""``, one room at a time.

    Absence of an OPTION LIST is not absence of an axis: Roborock withholds
    ``water_level_options`` on models whose mop is not settable, which is a capability
    statement. Only absence from the brand's own PROFILES means the axis does not
    exist.
    """
    declared: set[str] = set()
    template = (catalog or {}).get("custom_template")
    if isinstance(template, dict):
        declared |= set(template)
    for profile in ((catalog or {}).get("builtins") or {}).values():
        if isinstance(profile, dict):
            declared |= set(profile)
    return declared


def no_water_value(catalog: dict[str, Any] | None) -> str:
    """The word THIS brand uses for "no water", read from its declaration.

    Carpet is the one surface where the framework guarantees water off, so a brand's
    ``floor_type_water_defaults`` entry for carpet IS its no-water word.
    ``resolve_room_profile_for_room`` already reads it this way; ``apply_capability_gate``
    did not, and assigned the Eufy literal ``"Off"`` at three sites. THE DEFECT IS
    CASE. Roborock's own no-water word is ``"off"``, and ``"off"`` IS in its declared
    ``water_level_options`` — ``adapters/roborock/vocabulary.py::WATER_LEVEL_OPTIONS``
    is ``off`` / ``low`` / ``medium`` / ``high``, declared on exactly the mop-settable
    models. The value that was never declared is the capital-O ``"Off"`` this sibling
    hardcoded: dispatch's ``options_key`` filter dropped it, so mop intensity was never
    applied on a mop-settable model. The literal was removed from one function and left
    in its sibling.

    ⚠ Until 2026-08-24 this paragraph read "Roborock's value is ``off``, which is not
    in its declared ``water_level_options``" — inverting the lesson into "this brand's
    own word is invalid against this brand's own option list". The repairs that invites
    are editing the carpet entry in ``FLOOR_TYPE_WATER_DEFAULTS`` or adding a value to
    ``WATER_LEVEL_OPTIONS``; either breaks the carpet-water-off guarantee this helper
    exists to source.

    Undeclared yields ``""`` rather than a guess — there is no framework word for this.
    """
    defaults = (catalog or {}).get("floor_type_water_defaults") or {}
    for carpet in ("carpet_low_pile", "carpet_high_pile"):
        if carpet in defaults:
            return str(defaults[carpet])
    return ""


def _catalog_key(block: dict[str, Any], key: str, default: Any) -> Any:
    """RP-025/RF-18 (IN40W49E) clause (ii): presence, not truthiness — ``key in block`` so a
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


# anchor: IN40W49E  core holds no brand's vocabulary - undeclared resolves EMPTY
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
    this function's job is resolution, not judgement. Were absence quietly
    equivalent to ``{}`` EVERYWHERE, "this brand has no profiles" and "the porter
    forgot" would be the same state, which is precisely the fail-soft ambiguity
    removing the fallback was meant to end.

    ⚠ WHERE THE TWO STATES ARE ACTUALLY TOLD APART IS THE WHOLE ``room_profiles``
    BLOCK, NOT THE ``builtins`` KEY. Until 2026-08-24 this paragraph named
    ``registry._validate_adapter`` as reporting a missing ``builtins``, and the
    brand-agnostic contract suite as making it a hard failure. Neither does.
    ``registry._validate_room_profiles`` gates on the block alone — absent, not a
    dict, or ``{}`` — and ``_validate_adapter``'s key loop type-checks ``builtins``
    only ``if present``. In the contract suite,
    ``test_an_undeclared_catalog_fails_loudly_not_silently`` covers a wholly absent
    block and ``test_a_partially_declared_adapter_registers_and_resolves_empty``
    pins the OPPOSITE for a partial one: it registers clean and resolves empty. No
    test makes a block that omits ``builtins`` a failure.

    That sentence was the load-bearing reason it is safe for THIS function to
    collapse absent and ``{}``, so it is worth being exact about what survives. For
    every other key it IS safe — an empty resolved value is a defined answer. For
    ``builtins`` the report is merely deferred: the first room resolution raises
    ``UndeclaredProfileCatalogError`` out of ``get_room_profile``, hours from the
    declaration that caused it. Do not read "caught upstream" here and stop looking.

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

    Framework-canonical fields (label/clean_mode/clean_passes/
    edge_mopping/mop_required) fall back to the catalog's ``normalize_defaults``.
    An adapter that declares none, or a call with no catalog at all, gets an EMPTY
    mapping — there is no in-code default underneath it. (The trailing "since is
    None — byte-identical" here was a fragment of the same pre-catalog sentence
    corrected in the two docstrings below; it survived the edit that removed the
    thing it referred to.)

    Q2/RP-025 clause (i) is the WHY, and it is now HISTORY rather than a live
    two-tier read. The DISPLAY-AXIS fields (fan_speed/water_level/clean_intensity,
    and ``path_type`` with them) used to fall through to an in-code default carrying
    Eufy's own vocabulary ("Max"/"Off"/"Quick"), so any brand — or a bare utility
    call — that declared nothing for an axis silently acquired Eufy's literals with
    no brand ever having said so. That tier was deleted from this module. Eufy's
    adapter declares its own ``normalize_defaults``, so Eufy's real behaviour is
    unchanged; every other brand now gets its own words or none.

    ⚠ THERE IS ONE SECOND-LEVEL SOURCE NOW, NOT TWO, and this docstring described
    the contrast in the present tense until 2026-08-24 — which reads as a live
    mechanism a maintainer should preserve. ``d`` and ``brand_defaults`` below are
    assigned the IDENTICAL expression, ``(catalog or {}).get("normalize_defaults")
    or {}``, on consecutive lines. The duplicate pair is the only remaining trace of
    the removed tier: merging it under one name takes nothing away behaviourally and
    erases the marker, so leave it and read this paragraph instead.

    The two groups still differ at the THIRD level, and only there: the framework-
    owned fields land on ``""`` / ``"vacuum"`` / ``1`` / ``False``, none of which is
    any brand's word, while the display axes and ``path_type`` land on ``""``
    ("nobody said") — the doctrine ``resolve_room_profile_for_room`` already follows.
    """
    source = profile or {}
    d = (catalog or {}).get("normalize_defaults") or {}
    brand_defaults = (catalog or {}).get("normalize_defaults") or {}

    return {
        # "" for the same reason as fan_speed/water_level below: "User Profile 1" is
        # EUFY's custom-template label, declared by its adapter. The invariant gate
        # cannot see this one — `label` is a display string, not a provider-owned
        # field — so it is held by convention and by this comment.
        "label": str(source.get("label", d.get("label", ""))),
        "clean_mode": str(source.get("clean_mode", d.get("clean_mode", "vacuum"))),
        "fan_speed": str(source.get("fan_speed", brand_defaults.get("fan_speed", ""))),
        "water_level": str(source.get("water_level", brand_defaults.get("water_level", ""))),
        "clean_intensity": coerce_clean_intensity(
            source.get("clean_intensity", brand_defaults.get("clean_intensity", ""))
        ),
        # Same doctrine as the display axes above. "wide" sat here as the framework
        # default, so every brand acquired it with nobody having declared it — including
        # brands with no path axis at all. "" means "nobody said"; a brand that HAS the
        # axis declares it in normalize_defaults, and _finalize_room_update strips it
        # where undeclared.
        "path_type": coerce_axis_value(
            source.get("path_type", brand_defaults.get("path_type", ""))
        ),
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

    THE GATE IS A CONJUNCTION: ``supports_mop_features`` AND ``supports_water_control``.
    Fail either one and the caller gets the two vacuum-only names.

    ⚠ This said "mop profiles are excluded entirely when the vacuum does not support
    mopping" until 2026-08-24, naming one of the two conditions. The other one SHIPS.
    The Roborock S6 declares ``has_mop: True`` (``model_catalog.py``), so
    ``supports_mop_features`` is True, while ``adapters/roborock/adapter.py`` sets
    ``"supports_water_control": mop_settable`` — False, because the S6 rejects
    ``SET_WATER_BOX_CUSTOM_MODE`` / ``SET_MOP_MODE`` — and ``core/capabilities.py``
    lets that explicit declared False win over the detector. So a mop-equipped robot
    offering only two profiles is correct behaviour, not a bug; the single stated
    condition sent anyone debugging it looking somewhere else.

    Do NOT "fix" the code to match the old sentence by dropping the ``supports_water``
    conjunct — that restores mop profiles on hardware that rejects every mop command.
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
    """Return normalized profiles surviving BOTH filters below — not capabilities alone.

    ⚠ TWO FILTERS APPLY AND ONLY ONE OF THEM IS A CAPABILITY. This docstring named
    just the capability one until 2026-08-24. ``allowed_names`` comes from
    ``get_available_profile_names``, which returns a hardcoded whitelist of the four
    framework built-in KEYS (``PROTECTED_ROOM_PROFILE_NAMES``), and the comprehension
    keeps only ``if name in allowed_names``. So every stored custom profile that
    ``merge_profile_dicts`` has just merged in is dropped regardless of capabilities,
    as is any brand builtin declared under a key outside that set.

    What that costs: the sole caller, ``sensor/profile.py::_get_profiles``, publishes
    this as ``profile_count`` / ``profiles``, so a user who saved three custom room
    profiles sees none of them on the sensor and is given no stated reason. Whether
    silently discarding user data is right is a CODE question and is not settled here
    — this paragraph exists so the next reader does not conclude a capability removed
    them and go and "fix" the sensor.
    """
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
    """Remap a carpet room's profile NAME off the three mop built-ins. Names only.

    Off carpet the normalized name is returned unchanged. On carpet, exactly three
    literals are remapped:

    - ``vacuum_mop_quick`` -> ``vacuum_quick``
    - ``vacuum_mop_deep`` -> ``vacuum_deep``
    - ``vacuum_mop_standard`` -> ``vacuum_quick`` (undocumented until 2026-08-24, and
      live: it is reachable for any brand whose ``legacy_aliases`` does not already
      fold the name — Roborock declares ``legacy_aliases: {}``)

    ⚠ "carpet floor forces vacuum-only behavior" stood here as a universal rule until
    2026-08-24, over a three-literal whitelist. It is neither universal nor behaviour:
    this function returns a NAME and never touches ``clean_mode``. Every other name
    passes straight through — a user-saved custom profile whose ``clean_mode`` is
    ``vacuum_mop``, and any brand builtin declared under a different key, both reach a
    carpeted room still in a mop mode. The caller's carpet clamp still forces water to
    the brand's no-water word, so the floor stays dry; the MODE is not downgraded. A
    caller that skips its own mop check on the strength of the old sentence dispatches
    a mop ``clean_mode`` on carpet.
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


# anchor: RNY1AHMD  the canonical clean-mode ALIAS TABLE -- the replica set. The card
# carries the same table in src/clean-mode.js, alias for alias. Separate languages,
# so they CANNOT share code and are pinned to each other by test instead: add an
# alias to one, add it to the other. Load-bearing -- there is no unification.
def canonical_clean_mode(value: Any) -> str:
    """Normalize a clean_mode to its canonical token: vacuum | mop | vacuum_mop.

    ISSUE #48. Every "is this a mop mode?" test in the tree had its own spelling
    of the answer, and the two on the room-settings round trip disagreed:

      - SAVE path (_protected_room_config) asked ``"mop" in clean_mode`` — a
        substring test, which matches "Vacuum and mop" and preserved the value.
        (It calls ``is_mop_clean_mode`` now; both sides of this comparison are
        history, which is the point of recording them here.)
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
    """True when this clean_mode IS a mop mode, canonically. THE question, asked once.

    STRICT. Use this to decide what the framework DOES: gate a dispatch payload,
    downgrade for a device without mop hardware, match a room against a preset.
    An unrecognised brand mode answers False, which is the right answer for
    "should I send mop settings to this robot" — do not send settings on a guess.

    For the other question — "might this put water on the floor" — use
    ``may_wet_floor`` below. They are not the same question and must not be
    collapsed into one.
    """
    return canonical_clean_mode(value) in {"mop", "vacuum_mop"}


def may_wet_floor(value: Any) -> bool:
    """True when this clean_mode might involve water. TOLERANT on purpose.

    THE SECOND QUESTION, and it was owned by nobody — which is why it grew five
    private substring copies (water accounting in planning/run_plan, the safest-water
    choice for a mixed batch in dispatch/manager, the post-job water amendment in
    listeners/lifecycle, water allocation in learning/stats_rebuilder, and the
    has_mop_mode job metadata). All five were spelled ``"mop" in clean_mode``, all
    five agreed, and none of them was wrong — which is exactly why nobody noticed
    there were five.

    WHY IT IS DELIBERATELY LOOSER THAN is_mop_clean_mode, and must stay so: every
    caller uses it to decide how much water to ASSUME. Counting a doubtful mode as
    wet over-protects — a safest-water choice, a water estimate slightly high, an
    amendment registered that finds nothing. Missing one under-protects: a wet mop
    dispatched at a vacuum room's water level, or water silently unaccounted. The
    asymmetry is the whole point, so an unrecognised brand mode that merely MENTIONS
    mopping answers True here and False in is_mop_clean_mode.

    ``wash`` counts: a dock wash cycle puts water through the same system, and two
    callers already carried that tolerance by hand.
    """
    if is_mop_clean_mode(value):
        return True
    text = str(value or "").strip().lower()
    return "mop" in text or "wash" in text


def resolve_room_profile_for_room(
    *,
    room_config: dict[str, Any],
    stored_profiles: dict[str, dict[str, Any]] | None = None,
    catalog: dict[str, Any] | None = None,
) -> EffectiveRoomSettings:
    """Resolve final effective settings for a room from its profile and metadata.

    ORDER — corrected 2026-08-24. Values resolve room-explicit > profile > ABSENT
    (``""`` / ``False`` / ``1``), and the CARPET CLAMP is the only rule ABOVE that
    ladder. The anchor ``IN11T0FS`` further down states exactly this and the line
    that used to sit here contradicted it.

    Per-room overrides are therefore read FIRST, not last: each value is
    ``room_config.get(k, resolved_profile.get(k, <absent>))``. On a carpet floor the
    clamp then OVERWRITES ``resolved_fan_speed`` / ``resolved_water_level`` from the
    catalog's ``floor_type_fan_defaults`` / ``floor_type_water_defaults`` even where
    the room set them explicitly — a room-explicit water level LOSES to carpet, on
    purpose, because carpet-is-water-off is a safety property rather than a taste.
    Name-level constraints run before any of that:
    ``resolve_profile_name_for_constraints`` remaps the profile NAME on carpet and the
    remapped profile is what the value ladder then reads.

    ⚠ This said "selected profile → floor-type defaults → hard constraints → per-room
    overrides" until 2026-08-24, and both halves misdirect. The override stage was in
    the wrong place, so anyone tracing why a user's explicit water level did not reach
    a carpeted room reads the clamp as the bug. And "floor-type defaults" has been
    CARPET-ONLY since 2026-08-17 — the per-surface hard-floor rows were retired from
    both brands' ``FLOOR_TYPE_WATER_DEFAULTS`` (see the block comment at the clamp and
    ``docs/dev/history/floor-type-cleaning-defaults.md``), so restoring it as a general
    stage re-adds a table that was deliberately deleted.

    Returns an ``EffectiveRoomSettings`` dict; does not mutate inputs.

    ``catalog`` (a resolved adapter ``room_profiles`` block) sources the built-ins,
    legacy aliases, and floor-type fan/water defaults.

    ``catalog=None`` RAISES. It does not fall back and it does not quietly resolve to
    empty: ``None`` flows through ``get_room_profile`` to
    ``get_default_room_profiles(None)``, which returns ``{}`` by design, the merge
    yields ``{}``, both lookups miss, and ``get_room_profile`` raises
    ``UndeclaredProfileCatalogError``. Verified by calling it, 2026-08-24.

    That is the intended contract — core owns no brand's profile vocabulary, so a
    catalog-less call must FAIL LOUDLY rather than invent one, and
    ``tests/adapters/test_declaration_contract.py`` pins the raise. The signature's
    ``catalog: ... | None = None`` default reads like an optional convenience and is
    not one.

    This said "None uses the in-code constants (byte-identical)" until 2026-08-23,
    describing the world before those constants were removed. The behaviour was
    already correct; the prose described a fallback the repair had deleted, which is
    the direction of staleness that reads as reassurance."""
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

    # Last-resort fallbacks carry NO brand vocabulary. They fire only when the room AND
    # the brand's profile both omit the key; a Eufy display literal here would be this
    # module quietly becoming a fourth source of Eufy vocabulary, which is the exact
    # thing rooms/room_defaults.py exists to stop.
    #
    # ⚠ NOT ALL OF THEM ARE "". This read 'Last-resort fallbacks are ""' until
    # 2026-08-24 and the very next line is the exception: `clean_mode` falls back to the
    # literal "vacuum", and `edge_mopping` below to False. Both are FRAMEWORK-canonical
    # tokens — ProfileRecord documents clean_mode/edge_mopping as framework-owned — so
    # the rule's intent holds and only its universal phrasing did not. Narrowing
    # "vacuum" to "" to match the old sentence would be a real regression, not a tidy-up.
    resolved_clean_mode = str(room_config.get("clean_mode", resolved_profile.get("clean_mode", "vacuum")))
    resolved_clean_intensity = coerce_clean_intensity(
        room_config.get("clean_intensity", resolved_profile.get("clean_intensity", ""))
    )
    # This line was the one exception to the rule stated directly above: a literal
    # default, for every brand, on an axis most of them never declared. "" now, like
    # every other axis here.
    resolved_path_type = coerce_axis_value(
        room_config.get("path_type", resolved_profile.get("path_type", ""))
    )
    resolved_edge_mopping = bool(room_config.get("edge_mopping", resolved_profile.get("edge_mopping", False)))

    resolved_fan_speed = str(room_config.get("fan_speed", resolved_profile.get("fan_speed", "")))
    resolved_water_level = str(room_config.get("water_level", resolved_profile.get("water_level", "")))

    # anchor: IN11T0FS  settings resolve room-explicit > profile > ABSENT; the carpet
    # clamp is the only rule above that ladder, and absent is omitted, never invented
    #
    # CARPET is the framework's ONE surface rule, and it is a safety property: never
    # put water on a carpet. The word for "no water" belongs to the brand and is read
    # from its own carpet entry rather than assigned as a literal -- that literal wrote
    # Eufy casing ("Off") into a Roborock resolution, where the value is "off".
    #
    # There is deliberately NO hard-floor arm here any more. Per-surface water defaults
    # (hardwood -> Low, tile -> Medium, ...) were RETIRED 2026-08-17: they applied the
    # author's preference to every user who had not set a water level, and nothing in
    # the UI ever said that answering "what is the floor here?" would also choose how
    # wet to mop it. See docs/dev/history/floor-type-cleaning-defaults.md. floor_type
    # still drives the map render and the onboarding gate; it no longer drives settings.
    if floor_type.startswith("carpet"):
        resolved_fan_speed = fan_defaults.get(floor_type, "")
        resolved_water_level = water_defaults.get(floor_type, "")

    # NO hard-floor water correction. There used to be one here -- "mop mode with no
    # water is invalid, so fall back to the floor's default" -- and it died with the
    # per-surface table it depended on (2026-08-17, history/floor-type-cleaning-defaults.md).
    #
    # It is NOT simply pending a replacement value, and this is the part worth reading
    # before restoring it:
    #
    #   * A guard that fires and then assigns "" is indistinguishable from one that never
    #     fired. Re-adding it with an empty fallback would be dead code that looks alive.
    #   * The premise is unproven. "Mop mode with no water is invalid" was never argued --
    #     dry mopping is a real mode this integration already exposes as a dock action.
    #     A user who selects mop and turns water off may mean exactly that.
    #   * If it IS restored, the value is canonical `low`, not a per-surface choice and not
    #     a literal. The framework owns canonical water keys -- low/medium/high, see
    #     adapters/config_schema.py's water_level_aliases -- but that vocabulary is only
    #     translated INBOUND (brand -> canonical, for learning and rate estimation). There
    #     is no canonical -> brand direction yet, and inventing one here by reading
    #     declared option ORDER was tried and backed out: order is a convention no adapter
    #     states, and water_level_options lives in the `vocabulary` block, not this catalog.
    #
    # Until that translation exists, a mop room whose water is off keeps water off, and
    # the wire omits the field (queue_engine's value gate). The device keeps its setting.

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
    path_type = coerce_axis_value(settings.get("path_type", ""))
    clean_passes = int(settings.get("clean_passes", 1))
    edge_mopping = bool(settings.get("edge_mopping", False))

    # Mop unsupported — downgrade to the vacuum-only equivalent. Derive path_type /
    # clean_intensity from the corresponding vacuum-only built-in profile rather than
    # hardcoding values, so the downgrade follows whatever vocabulary the profile
    # catalog declares. A brand that declares only one of the two axes carries only
    # that one through the downgrade; the other stays "".
    #
    # ⚠ "...and is dropped below" stood here until 2026-08-24 and holds for ONE axis.
    # Only `path_type` is dropped: the `gated.update({...})` at the bottom of this
    # function writes `clean_intensity` unconditionally, empty or not, and the
    # `if path_type:` / `gated.pop("path_type", None)` pair covers `path_type` alone.
    # So on Roborock — which declares `path_type` and omits `clean_intensity` from
    # every profile — the downgraded payload carries `"clean_intensity": ""` rather
    # than omitting the key, i.e. exactly the state this comment said was dropped.
    # Anything downstream distinguishing an ABSENT key from a declared-empty value
    # (the distinction `_finalize_room_update` and `rooms/vocabulary_migration.py` are
    # built around) therefore reads a brand with no intensity axis as having declared
    # it empty. Making the two axes symmetric is a CODE change and has not been made.
    # ISSUE #48, dispatch side. This was `clean_mode in {"mop", "vacuum_mop"}` —
    # exact and case-SENSITIVE, against a value this function's own docstring says
    # arrives as a DISPLAY/STORAGE value and which is not lowercased on the way in
    # (see `clean_mode = str(settings.get(...))` above). So "Vacuum and mop", the
    # spelling the card actually writes, and "Mop" both slipped past the downgrade
    # and a mop payload went to a device with no mop hardware. Worse than the read
    # path this predicate was first fixed on: that returned a wrong checkbox, this
    # sends a wrong command to the robot.
    if not supports_mop and is_mop_clean_mode(clean_mode):
        fallback_name = "vacuum_deep" if resolved_profile_name == "vacuum_mop_deep" else "vacuum_quick"
        _, fallback = get_room_profile(profile_name=fallback_name, catalog=catalog)
        clean_mode = "vacuum"
        water_level = no_water
        edge_mopping = False
        path_type = coerce_axis_value(fallback.get("path_type", path_type))
        clean_intensity = coerce_clean_intensity(
            fallback.get("clean_intensity", clean_intensity)
        )

    # Vacuum-only mode — water and edge mopping are irrelevant. Same correction as
    # above and the same reason: `clean_mode == "vacuum"` never matched the display
    # label "Vacuum", so a vacuum-only room dispatched carrying a water level and an
    # edge-mopping flag. BOTH halves UNDER-fired, from the one root. This said "failed
    # in opposite directions" until 2026-08-24 and then contradicted itself two clauses
    # later; there was never an over-firing half. The old
    # `clean_mode in {"mop", "vacuum_mop"}` never matched "Vacuum and mop", so the mop
    # downgrade never ran; the old `clean_mode == "vacuum"` never matched the display
    # label "Vacuum", so this water/edge clear never ran. Two missed firings of the same
    # case-sensitivity root, and only the canonical spelling ever exercised either.
    # Anyone sizing the ISSUE #48 blast radius off the old wording hunts for a predicate
    # that needs TIGHTENING — there isn't one.
    if canonical_clean_mode(clean_mode) == "vacuum":
        water_level = no_water
        edge_mopping = False

    if not supports_water:
        water_level = no_water
    if not supports_edge:
        edge_mopping = False
    if not supports_path:
        # A device without the axis gets the field OMITTED, not clamped to a value.
        # Clamping to "wide" wrote a value into every payload the gate touched — the
        # loudest possible answer to "does this device have a path axis?" being asked
        # of devices that do not. An omitted field is exactly how the dispatch layer
        # already expresses "this brand does not expose it" (room_fields
        # field_name=None), so match it.
        path_type = ""
    if not supports_passes:
        clean_passes = 1

    gated = dict(settings)
    gated.update(
        {
            "clean_mode": clean_mode,
            "fan_speed": fan_speed,
            "water_level": water_level,
            "clean_intensity": clean_intensity,
            "clean_passes": clean_passes,
            "edge_mopping": edge_mopping,
            "capability_gated": True,
        }
    )
    # "" is "nobody declared this axis" — carry the key only when it has a real value,
    # so absent stays distinguishable from declared-empty downstream.
    if path_type:
        gated["path_type"] = path_type
    else:
        gated.pop("path_type", None)
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
    ``normalize_defaults`` for any field the profile omits, so a brand's rooms fill
    from ITS declared defaults.

    ABSENT CATALOG DOES NOT MEAN EUFY DEFAULTS. It means ``brand_defaults = {}``, so
    fan speed, water level and clean intensity all come out ``""`` — empty, not
    ``"Max"``/``"Off"``/``"Standard"``. That is the contract: an axis nobody declared
    stays unset rather than acquiring one brand's literals by default.

    This docstring claimed the opposite until 2026-08-23 — that a missing catalog
    fell back to in-code Eufy values "byte-identical to the pre-catalog behaviour".
    Those values are gone. The stale half is the reassuring half: a reader checking
    whether a catalog-less path could leak Eufy vocabulary would have found a
    sentence saying yes, about code that no longer does it.
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
    # Only carry the path axis for a brand that actually declares it. This wrote the
    # key unconditionally, so applying any profile re-stamped path_type onto rooms of
    # brands that have no such axis — regenerating the very fossil the store repair
    # clears. normalize_room_profile yields "" when nobody declared it.
    if normalized.get("path_type"):
        updated["path_type"] = normalized["path_type"]
    else:
        updated.pop("path_type", None)
    # Normalize floor_type on write so legacy "carpet" values are migrated in place.
    updated["floor_type"] = _normalize_floor_type(updated.get("floor_type"))
    return updated
