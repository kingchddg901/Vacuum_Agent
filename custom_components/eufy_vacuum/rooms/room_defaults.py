"""What settings a freshly-created room starts with.

THE single answer, for every path that creates a room. There were four before this:
``build_managed_rooms`` (the wizard), ``RoomConfig``'s own dataclass field defaults, the
map-rebuild path in ``maps/map_manager.py``, and ``resolve_room_profile_for_room``'s final
fallbacks — each an independently hand-maintained copy of the same Eufy literals
(``"Max"`` / ``"Off"`` / ``"Quick"`` / ``"vacuum_quick"``).

Two things were wrong with that, and they are different problems:

**Brand.** None of the four could consult the adapter — ``build_managed_rooms`` took no
vacuum argument at all — so every Roborock room was created with Eufy display vocabulary.
Roborock's declared option values are lowercase (``"max"``), the framework wrote ``"Max"``,
and the two never met: the card's chip row compares strictly so nothing rendered as
selected, and ``per_room_live_settings`` filters on ``fan_speed_options`` so an unedited
room got no suction applied at all. The Roborock adapter had already grown a comment
explaining that filter as a workaround for this exact default.

**Honesty.** ``build_managed_rooms`` labelled a new room ``profile_name="vacuum_quick"``
while stamping ``fan_speed="Max"`` — but ``vacuum_quick`` itself declares ``"Standard"``.
Since ``resolve_room_profile_for_room`` lets the stored per-room field win and
``build_managed_rooms`` wrote every field, the profile was never consulted. Every
wizard-created Eufy room displayed "Vacuum Only Quick" and ran at Max suction.

Both are fixed by the same move, and no new adapter block was needed to do it: a
brand-declarable answer already existed and was being ignored. ``room_profiles`` carries
``default_profile``, and the profile it names already declares exactly these fields. So a
new room's settings ARE its default profile's settings — one source, no second vocabulary
to drift from the first, and ``profile_name`` finally means what it says.

Per [[feedback_centralize_question_not_vocabulary]]: this centralizes the QUESTION ("what
does a fresh room look like?"), rather than publishing another list of values.
"""

from __future__ import annotations

from typing import Any

from ..profiles.room_profiles import resolve_profile_catalog

#: The per-room setting fields a default profile supplies. Anything a profile does not
#: declare is simply absent from the result — callers keep their own field-level default
#: for it, rather than this module inventing one.
#:
#: ``clean_intensity`` is in the list precisely BECAUSE a brand may not have that axis:
#: Roborock declares no ``clean_intensity_options`` at all, so its default profile omits
#: the key and no meaningless value is written onto its rooms.
NEW_ROOM_SETTING_FIELDS: tuple[str, ...] = (
    "clean_mode",
    "fan_speed",
    "water_level",
    "clean_intensity",
    "path_type",
    "clean_passes",
    "edge_mopping",
)


def resolve_new_room_defaults(
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the settings a new room starts with, for this brand.

    ``catalog`` is a resolved ``room_profiles`` block (``resolve_profile_catalog``); None
    resolves the framework's in-code catalog, which is what a brand that declares no
    ``room_profiles`` block gets today.

    The result always carries ``profile_name`` plus whichever of
    ``NEW_ROOM_SETTING_FIELDS`` the named profile declares. A profile that declares none of
    them yields just the name — the caller's own per-field default then applies, which is
    the correct degradation: silence from the brand is not a value.
    """
    cat = resolve_profile_catalog(catalog if isinstance(catalog, dict) else None)

    profile_name = str(cat.get("default_profile") or "")
    builtins = cat.get("builtins")
    profile = builtins.get(profile_name) if isinstance(builtins, dict) else None

    defaults: dict[str, Any] = {"profile_name": profile_name}
    if isinstance(profile, dict):
        for field in NEW_ROOM_SETTING_FIELDS:
            if field in profile:
                defaults[field] = profile[field]
    return defaults


def resolve_new_room_defaults_for_vacuum(vacuum_entity_id: str) -> dict[str, Any]:
    """``resolve_new_room_defaults`` for one vacuum, via its registered adapter.

    The convenience wrapper for the two production room-creation call sites, which each
    have a ``vacuum_entity_id`` and no catalog. Never raises — an unregistered adapter
    resolves the framework catalog, exactly as a brand declaring no ``room_profiles``
    block does.
    """
    from ..adapters.registry import get_adapter_config

    try:
        config = get_adapter_config(vacuum_entity_id) or {}
        block = config.get("room_profiles")
    except Exception:  # pragma: no cover - defensive
        block = None
    return resolve_new_room_defaults(block if isinstance(block, dict) else None)
