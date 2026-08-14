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
    overrides: dict[str, Any] | None = None,
    reserved_suffixes: Any = None,
) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    """Return ``(entities, report)`` with unresolvable IDs repaired where unambiguous.

    ``report`` maps role -> ``{"declared": ..., "resolved": ...}`` for each remap, and is
    empty when nothing needed rescuing (the overwhelmingly common case).

    ``overrides`` maps role -> entity_id and is the user's explicit choice, from the
    System tab or the options flow. It is applied HERE, in the shared resolver, rather
    than in each brand adapter, for two reasons. It is the single place both brands
    already funnel their declared map through, so an override cannot work on one brand
    and not the other — this file is the twin that kept the live:ENT-4 bug precisely
    because a fix landed in one copy of a predicate and not the other. And it is
    upstream of everything that reads a binding: ``config["entities"]`` is what the
    runtime, the card and diagnostics consult, while ``detect_capabilities`` sees only
    a 14-role candidate subset — so an override applied only there was a no-op for
    ``battery`` and ten other declared-only roles.
    """
    report: dict[str, dict[str, str]] = {}
    if not isinstance(entities, dict) or not entities:
        return entities, report

    # THE USER'S CHOICE IS A DECLARATION, not a candidate. Pinned before anything else
    # runs so it is what the rescue and exclusivity passes below reason about: its
    # suffix joins `declared_suffixes` and therefore participates in the ownership
    # check, exactly as a brand-declared id would.
    #
    # A role is pinned even when the chosen entity has no state. Silently declining
    # would return the binding to auto-detection while the System tab still showed the
    # override stored, and the two would disagree with no way to see which won. The
    # rescue pass below may still repair it, and REASON_OVERRIDE_UNRESOLVED reports the
    # case that cannot be repaired.
    if isinstance(overrides, dict):
        for _role, _chosen in overrides.items():
            if isinstance(_chosen, str) and "." in _chosen:
                entities[_role] = _chosen

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

    # live:ENT-4 (the SECOND copy of this guard). `endswith` is unsafe when one
    # declared suffix is a substring of another: `_cleaning_area` also matches
    # `..._total_cleaning_area`, and BOTH roles are declared right here in
    # `entities`. The ambiguity check below cannot save us — it excludes the
    # declared id from its own candidate list, so exactly ONE sibling matches
    # and one match looks decisive.
    #
    # FOUND LIVE on the maintainer's own install, by the binding table, minutes
    # after that table first existed: `cleaning_area` was bound to
    # `sensor.dining_room_alfred_total_cleaning_area` reading 17,975 ft² while
    # the real per-run sensor read 0.0 — feeding a lifetime counter into the
    # learning store, counter segmentation and battery metrics. `cleaning_time`
    # was bound to a total reading 41.775 HOURS where minutes were expected.
    #
    # The exclusivity guard was added to augment_candidates_from_device and NOT
    # here — a fix applied to one copy of a predicate and not its twin, which is
    # the shape that keeps producing these.
    declared_suffixes: set[str] = set()
    for _declared in entities.values():
        if not isinstance(_declared, str) or "." not in _declared:
            continue
        _suffix = _suffix_of(_declared, vacuum_object_id)
        if _suffix:
            declared_suffixes.add(_suffix)

    # Deriving the universe from `entities` ALONE makes this guard depend on the
    # caller having declared BOTH halves of a collision — and Roborock declares
    # `_cleaning_area` while binding no lifetime role at all, so replaying the
    # predicate below against its real map returned
    # `_claimed_by("ivy_total_cleaning_area") == "_cleaning_area"`: the counter
    # accepted as the per-run sensor. The brand's full vocabulary closes that,
    # and it is the argument rather than a longer `entities` map because a brand
    # should not have to BIND a role merely to be protected from it. A brand that
    # still omits a suffix now degrades to "no rescue" instead of "wrong rescue".
    if reserved_suffixes:
        for _reserved in reserved_suffixes:
            if isinstance(_reserved, str) and _reserved:
                declared_suffixes.add(_reserved)

    def _claimed_by(object_id: str) -> str | None:
        """The LONGEST declared suffix this id ends with — its rightful owner."""
        best: str | None = None
        for known in declared_suffixes:
            if object_id.endswith(known) and (best is None or len(known) > len(best)):
                best = known
        return best

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
            # A sibling belongs to the role whose declared suffix explains the
            # MOST of its name. If a longer declared suffix also fits, that role
            # owns it and this one must not borrow it.
            and _claimed_by(e.entity_id.split(".", 1)[1]) == suffix
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
