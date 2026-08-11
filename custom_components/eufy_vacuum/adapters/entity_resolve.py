"""Rescue declared entity IDs whose NAMING PATTERN does not match reality.

WHY THIS EXISTS. Adapters derive companion entity IDs from the vacuum's object_id
(``build_entity_id``: ``sensor.{object_id}{suffix}``). That assumes one device per
vacuum, and it is wrong for at least two shipping cases:

- **Multi-device brands.** Eufy's dock is a SEPARATE device with its own name, so its
  entities land under that device's slug. On a live X10 the four dock-owned roles resolve
  to nothing while the entities plainly exist::

      declared  sensor.alfred_total_cleaning_area              (absent)
      actual    sensor.dining_room_alfred_total_cleaning_area  17975.73

- **Renamed devices/entities.** A user renaming the vacuum or its device breaks every
  derived ID at once.

Both failed SILENTLY: a declared-but-absent entity reads as "this brand does not report
that", which is exactly the capability leak the project keeps removing. It got worse on
HA 2026.8, which removed ``battery_level`` from the vacuum entity — the fallback that used
to paper over a missed battery sensor is gone, so the derived ID is now load-bearing alone.

WHAT THIS DOES. For each declared ID that does NOT resolve in the state machine, look for
the real entity **within the vacuum's own config entry**, matching domain + ID suffix. The
config-entry scope is what keeps it honest: it can only find entities belonging to the same
integration instance as this vacuum, never another install's.

SAFETY PROPERTIES, in order of importance:

1. **It never changes a resolution that already works.** A declared ID present in the
   state machine is returned untouched, so no working install can be altered by this.
2. **It refuses to guess.** Zero candidates, or two or more it cannot disambiguate, and the
   declared ID is left exactly as it was. A wrong remap would be worse than no remap.
3. **It is loud.** Every remap is logged at INFO with both IDs, and returned in a report so
   diagnostics can show what was rescued rather than presenting a repaired config as if it
   had always been right.

WHAT IT DOES NOT FIX. An entity that is REGISTERED but has no state (HA 2026.7 stopped
creating some Roborock entities while their registry rows survived the upgrade) is not a
naming problem — the ID is correct and the entity is simply absent. This returns the
declared ID unchanged for that case, which is correct and is why it is not a fix for it.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


def _suffix_of(declared: str, vacuum_object_id: str) -> str | None:
    """The naming suffix a declared ID was built from, e.g. ``_total_cleaning_area``.

    Returns None when the declared ID was not derived from this vacuum's object_id — in
    which case there is no suffix to match on and we must not guess.
    """
    try:
        object_part = declared.split(".", 1)[1]
    except IndexError:
        return None
    if not object_part.startswith(vacuum_object_id):
        return None
    suffix = object_part[len(vacuum_object_id):]
    return suffix or None


def resolve_declared_entities(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    entities: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    """Return ``(entities, report)`` with unresolvable IDs repaired where unambiguous.

    ``report`` maps role -> ``{"declared": ..., "resolved": ...}`` for each remap, and is
    empty when nothing needed rescuing (the overwhelmingly common case).
    """
    report: dict[str, dict[str, str]] = {}
    if not isinstance(entities, dict) or not entities:
        return entities, report

    vacuum_object_id = vacuum_entity_id.split(".", 1)[-1]

    try:
        registry = er.async_get(hass)
        vacuum_entry = registry.async_get(vacuum_entity_id)
    except Exception:  # pragma: no cover - defensive; never break config build
        return entities, report

    config_entry_id = getattr(vacuum_entry, "config_entry_id", None) if vacuum_entry else None
    if not config_entry_id:
        # No config entry to scope the search to. Scoping is the safety property, so
        # without it we do nothing rather than searching the whole registry.
        return entities, report

    try:
        siblings = er.async_entries_for_config_entry(registry, config_entry_id)
    except Exception:  # pragma: no cover - defensive
        return entities, report

    for role, declared in list(entities.items()):
        if not isinstance(declared, str) or "." not in declared:
            continue
        if hass.states.get(declared) is not None:
            continue  # already works — never touch it

        suffix = _suffix_of(declared, vacuum_object_id)
        if not suffix:
            continue

        domain = declared.split(".", 1)[0]
        candidates = [
            e.entity_id
            for e in siblings
            if e.entity_id.startswith(f"{domain}.")
            and e.entity_id.split(".", 1)[1].endswith(suffix)
            and e.entity_id != declared
        ]
        if not candidates:
            continue

        if len(candidates) > 1:
            # Prefer a candidate that still carries the vacuum's own object_id (Eufy's
            # dock entities are named "<area>_<vacuum>_<suffix>", so this survives).
            narrowed = [c for c in candidates if vacuum_object_id in c]
            if len(narrowed) != 1:
                _LOGGER.debug(
                    "%s: %s -> %d ambiguous candidates for suffix %r; leaving declared "
                    "ID unchanged rather than guessing: %s",
                    vacuum_entity_id, role, len(candidates), suffix, candidates,
                )
                continue
            candidates = narrowed

        resolved = candidates[0]
        entities[role] = resolved
        report[role] = {"declared": declared, "resolved": resolved}
        _LOGGER.info(
            "%s: entity role %r did not resolve as %s; using %s from the same config "
            "entry (derived-ID naming did not match this install)",
            vacuum_entity_id, role, declared, resolved,
        )

    return entities, report
