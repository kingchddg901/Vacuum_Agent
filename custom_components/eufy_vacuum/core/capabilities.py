"""Generic vacuum capability detection for the ha_vacuum_manager framework.

Probes the HA state machine and entity registry for the entities declared
by the adapter, then combines adapter-supplied capability hints with entity
presence to produce a complete capability map.

No brand-specific knowledge lives here. All vacuum-specific inputs are
supplied by the caller (the adapter's registration function):

  entity_candidates — {key: [entity_id, ...]} — entity IDs to probe per
      capability slot. Each list is tried in order; first present wins.
      Standard keys: task_status, work_mode, dock_status, active_map,
      active_cleaning_target, cleaning_area, cleaning_time, water_level,
      robot_position_x, robot_position_y, wash_mop_button, dry_mop_button,
      empty_dust_button, cleaning_intensity.

  model_family — pre-computed model family string ('x10', 'generic', …).
      Used only for logging/return value; capability decisions use hints.

  capability_hints — {flag: bool} — model-based override flags. Each flag
      is OR-ed with entity presence: True from hints means the feature is
      supported even if the entity is absent; False (or absent) means fall
      back to entity presence detection.
      Standard flags: supports_mop_features, supports_mop_wash,
      supports_mop_dry, supports_empty_dust, supports_path_control.

  maintenance_components — {component_id: {sensor_suffix, …}} — the
      maintenance component catalog from the adapter. Passed through to
      _detect_maintenance_sources(). Absent → maintenance_sources empty.

A port to a different brand supplies its own entity_candidates and
capability_hints from its adapter registration function. The probing
logic is universal HA entity detection that works for any brand.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

#: Resolution outcomes reported alongside each role (live:ENT-2).
#: ``absent`` and ``disabled`` used to be indistinguishable — both produced a
#: bare ``None`` — yet they need OPPOSITE fixes: one is ours, the other is a
#: toggle in the user's own UI. Issue #49 burned a round-trip on exactly that
#: ambiguity, with both position sensors present-but-disabled on the device.
REASON_RESOLVED = "resolved"
REASON_DISABLED = "disabled"
REASON_REGISTERED_NO_STATE = "registered_no_state"
REASON_ABSENT = "absent"
#: The user set an override for this role and it did NOT resolve — renamed or
#: deleted since. Resolution fell through to the normal candidates rather than
#: pinning a dead id, but a user choice that has quietly stopped working must be
#: VISIBLE; silently substituting our guess for their stated intent is the
#: failure mode this whole effort exists to remove (live:ENT-7).
REASON_OVERRIDE_UNRESOLVED = "override_unresolved"

#: WHICH rung of the live:ENT-9 ladder decided a contested role. First-class
#: values rather than prose, because six months from now "chosen by: magnitude"
#: sends you somewhere completely different from "chosen by: manual override".
BY_OBJECT_ID = "object_id"
BY_TRANSLATION_KEY = "translation_key"
BY_STATE_CLASS = "state_class"
BY_MAGNITUDE = "magnitude"
#: Where a winning candidate CAME FROM, recorded for every role rather than only
#: contested ones. Without this the table labels an entity "name match" when the
#: sibling search rescued it — asserting something visibly false, which is the
#: manufactured-confidence failure this surface exists to catch.
FROM_DERIVED = "derived"
FROM_OVERRIDE = "override"
FROM_DEVICE_SIBLING = "device_sibling"
FROM_CONFIG_ENTRY_SIBLING = "config_entry_sibling"


# ----------------------------------------------------------------------
# Entity lookup helpers
# ----------------------------------------------------------------------


def _state_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True if entity currently has a state in HA."""
    return hass.states.get(entity_id) is not None


def _registry_entry_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True if entity exists in registry, even if disabled."""
    registry = er.async_get(hass)
    return registry.async_get(entity_id) is not None


def _find_existing_entity(
    hass: HomeAssistant,
    candidates: list[str],
) -> str | None:
    """Return first candidate that currently has a state."""
    for entity_id in candidates:
        if _state_exists(hass, entity_id):
            return entity_id
    return None


def _find_registered_entity(
    hass: HomeAssistant,
    candidates: list[str],
) -> str | None:
    """Return first candidate that exists in the entity registry."""
    for entity_id in candidates:
        if _registry_entry_exists(hass, entity_id):
            return entity_id
    return None


def resolve_with_reason(
    hass: HomeAssistant,
    candidates: list[str],
) -> tuple[str | None, str]:
    """Return ``(entity_id, reason)`` for the first candidate that explains itself.

    live:ENT-2. ``_find_existing_entity`` answers "which id has a state" and
    erases everything else, so a role reads ``None`` whether the entity is
    missing, switched off, or simply not added yet. Those need different fixes
    and only one of them is a bug in this integration.

    Order matters: a candidate with a STATE always wins, so a working install
    resolves exactly as before and never pays for the extra registry lookups.
    Only an unresolved role walks the registry to explain itself.
    """
    for entity_id in candidates:
        if _state_exists(hass, entity_id):
            return entity_id, REASON_RESOLVED

    try:
        registry = er.async_get(hass)
    except Exception:  # pragma: no cover - defensive; never break detection
        return None, REASON_ABSENT

    for entity_id in candidates:
        entry = registry.async_get(entity_id)
        if entry is None:
            continue
        # Registered but stateless. `disabled_by` is the authoritative signal —
        # it names WHO disabled it (user, integration, config entry). An entry
        # with no state and no disabled_by is mid-startup or unavailable, which
        # is a third thing again and must not be reported as "disabled".
        if getattr(entry, "disabled_by", None) is not None:
            return entity_id, REASON_DISABLED
        return entity_id, REASON_REGISTERED_NO_STATE

    return None, REASON_ABSENT


def _find_registry_entity_by_tokens(
    hass: HomeAssistant,
    *,
    domain: str,
    object_id_prefix: str,
    required_tokens: list[str],
) -> str | None:
    """Find a registry entity by prefix + token match.

    Used for entities whose exact suffix may differ between versions
    or may be disabled by default.
    """
    registry = er.async_get(hass)
    prefix = f"{domain}.{object_id_prefix}".lower()

    for entry in registry.entities.values():
        entity_id = str(entry.entity_id).lower()
        if not entity_id.startswith(prefix):
            continue
        if all(token in entity_id for token in required_tokens):
            return entry.entity_id

    return None


# ----------------------------------------------------------------------
# Maintenance source detection
# ----------------------------------------------------------------------


def _sweep_siblings(registry: Any, entry: Any) -> tuple[list[str], int]:
    """Entities on the vacuum's DEVICE, then on its CONFIG ENTRY. Device first.

    live:ENT-5. Two scopes because only one of them has field evidence: on issue
    #49 the config-entry search rescued battery on the same install, at the same
    instant, that the device search rescued nothing. Device first because it is
    the tighter scope and order is priority; config-entry entries only fill gaps
    it left.

    Returns ``(siblings, device_count)`` so a caller can report the split — the
    two numbers side by side are what tell you WHICH scope is failing.
    """
    siblings: list[str] = []
    seen: set[str] = set()

    if getattr(entry, "device_id", None):
        for item in er.async_entries_for_device(
            registry, entry.device_id, include_disabled_entities=True
        ):
            if item.entity_id not in seen:
                siblings.append(item.entity_id)
                seen.add(item.entity_id)
    device_count = len(siblings)

    config_entry_id = getattr(entry, "config_entry_id", None)
    if config_entry_id:
        for item in er.async_entries_for_config_entry(registry, config_entry_id):
            if item.entity_id not in seen:
                siblings.append(item.entity_id)
                seen.add(item.entity_id)

    return siblings, device_count


def _rescue_maintenance_source(
    siblings: Iterable[str],
    suffix: str,
) -> str | None:
    """Find a companion ending in ``_{suffix}`` when the derived name missed.

    live:ENT-8. Maintenance sources are derived as ``sensor.{object_id}_{suffix}``
    with NO fallback of any kind — a fourth code path carrying the same naming
    assumption that ENT-1/ENT-5 repaired elsewhere, and the one behind issue #49's
    missing mop and brush life.

    It matters more than one dead row: per docs/dev/13-maintenance-manager.md the
    REPLACEMENT rows come from these upstream percentage sensors, and the
    integration's own maintenance row decrements off ``usage_hours`` on the very
    same entity. One unresolved source kills both halves.

    Exactly-one or nothing, matching live:ENT-6 — a component resolving to the
    wrong consumable would report confident, wrong remaining life.
    """
    wanted = f"_{suffix}"
    matches = [
        sibling
        for sibling in siblings
        if sibling.startswith("sensor.") and sibling.partition(".")[2].endswith(wanted)
    ]
    return matches[0] if len(matches) == 1 else None


def _detect_maintenance_sources(
    hass: HomeAssistant,
    *,
    object_id: str,
    maintenance_components: dict[str, Any],
    siblings: Iterable[str] = (),
    overrides: dict[str, str] | None = None,
) -> dict[str, str | None]:
    """Return a component → source entity_id map for maintenance tracking.

    maintenance_components is the adapter's component catalog dict:
    {component_id: {sensor_suffix, proxy_for, label, icon, …}}.

    ``sensor_suffix`` is the full suffix appended to ``sensor.{object_id}_`` to
    form the counter entity ID — no brand naming is assumed here. A component
    with ``proxy_for`` set sources from that component's sensor when present,
    falling back to its own ``sensor_suffix`` (e.g. swivel_wheel -> filter).
    """

    def _resolve(suffix: Any) -> str | None:
        if not suffix:
            return None
        candidate = f"sensor.{object_id}_{suffix}"
        if _state_exists(hass, candidate) or _registry_entry_exists(hass, candidate):
            return candidate
        # live:ENT-8 — the derived name missed; look for the real companion.
        return _rescue_maintenance_source(siblings, str(suffix))

    user_choices = overrides if isinstance(overrides, dict) else {}
    sources: dict[str, str | None] = {}
    for component, meta in maintenance_components.items():
        # live:ENT-7 — a user's explicit choice outranks derivation here too.
        chosen = user_choices.get(component)
        if isinstance(chosen, str) and "." in chosen:
            sources[component] = chosen
            continue
        own = _resolve(meta.get("sensor_suffix"))
        proxy_id = meta.get("proxy_for")
        if proxy_id:
            proxy_meta = maintenance_components.get(proxy_id, {})
            sources[component] = _resolve(proxy_meta.get("sensor_suffix")) or own
        else:
            sources[component] = own

    return sources


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


#: Every flag ``capability_hints`` may carry — the ONLY keys this module reads.
#:
#: A hint is a silent no-op if the key is not in this set: ``_hints.get(name)`` simply
#: misses and the derived/default value stands. That makes a typo indistinguishable from
#: an undeclared capability, which is the same silent-wrong-answer shape as the hardcoded
#: `True` that ``_hint_wins`` exists to prevent — a brand declaring
#: ``supports_zone_cleen: False`` would be ignored exactly as thoroughly as one declaring
#: nothing. ``registry._validate_adapter`` checks adapter ``capability_hints`` against this
#: set so the typo is caught at registration instead of at "why is this control showing?".
#:
#: Keep in sync with the ``_hints`` reads below; the contract test asserts it matches.
KNOWN_CAPABILITY_HINTS: frozenset[str] = frozenset({
    "has_attribute_rooms",
    "supports_custom_room_config",
    "supports_edge_mopping",
    "supports_empty_dust",
    "supports_mop_dry",
    "supports_mop_features",
    "supports_mop_wash",
    "supports_passes",
    "supports_path_control",
    "supports_room_clean",
    "supports_water_control",
    "supports_zone_clean",
})


#: A competing candidate must be this many times larger before magnitude alone
#: decides. A per-run figure against a lifetime counter is ~4000x on real
#: hardware (2.9 m² vs 11,814 m²), so the bar is set high enough that only an
#: unmistakable gap counts and two similar readings stay ambiguous.
_MAGNITUDE_RATIO = 10.0


def _sibling_traits(registry: Any, siblings: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Registry metadata per sibling — available at STARTUP, with no state.

    live:ENT-9. The entity registry carries ``translation_key``, ``capabilities``
    (which holds ``state_class``), ``device_class`` and the unit, all persisted
    and readable before the upstream integration has produced a single state.
    That makes these discriminators safe during setup in a way that reading
    ``hass.states`` is not.
    """
    traits: dict[str, dict[str, Any]] = {}
    for entity_id in siblings:
        try:
            entry = registry.async_get(entity_id)
        except Exception:  # pragma: no cover - defensive
            continue
        if entry is None:
            continue
        capabilities = getattr(entry, "capabilities", None) or {}
        traits[entity_id] = {
            "translation_key": getattr(entry, "translation_key", None),
            "state_class": capabilities.get("state_class"),
            "device_class": (
                getattr(entry, "original_device_class", None)
                or getattr(entry, "device_class", None)
            ),
            "unit": getattr(entry, "unit_of_measurement", None),
        }
    return traits


def _narrow_competing(
    hass: HomeAssistant,
    *,
    role: str,
    object_id: str,
    matches: list[str],
    traits: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None, dict[str, str]]:
    """Choose ONE competing candidate, and say HOW — or None for a human.

    Returns ``(chosen, decided_by, rejected)``. ``rejected`` maps each losing
    candidate to the trait that ruled it out, which is the forensic trail the
    System tab renders: "rejected: translation_key=total_cleaning_area".

    IMPORTANT for any consumer: the ladder SHORT-CIRCUITS on the first decisive
    rung. A role decided by translation_key never evaluated state_class or
    magnitude, so those must render as NOT EVALUATED — never as agreeing.
    Presenting rungs we never ran as corroboration would manufacture confidence,
    which is the exact failure this surface exists to catch.

    live:ENT-9. The colliding pair is almost always per-run versus lifetime —
    ``cleaning_area`` against ``total_cleaning_area`` — and those are not merely
    different entities, they are different QUANTITIES. On live hardware the
    per-run figure reads 2.9 m² while the lifetime counter reads 11,814.2 m².

    Binding the wrong one is not a missing feature, it is a ~4000x error fed
    into the learning store, counter segmentation and battery metrics — and it
    never throws, because a cumulative counter simply looks like a vacuum making
    no progress.

    Ordered strongest evidence first, and each rung must be DECISIVE (exactly
    one survivor) or the next is tried:

      1. the candidate still carrying the vacuum's own object_id
      2. the upstream integration's own ``translation_key`` matching the role —
         its name for the concept, independent of how the entity was named
      3. ``state_class``: ``measurement`` is "the value right now",
         ``total`` is a cumulative counter. HA's own semantics, declared by the
         upstream, and it works on a BRAND-NEW vacuum with no runtime at all
      4. magnitude — only with prior runtime, and only on an unmistakable gap

    Returning None is a real answer: the role stays unresolved and is offered to
    the user, whose question is answerable ("which of these resets after each
    clean?") rather than a blind pick.
    """
    def _losers(winner: str, label: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for item in matches:
            if item == winner:
                continue
            value = (traits.get(item) or {}).get(label)
            out[item] = f"{label}={value}" if value is not None else f"{label} did not match"
        return out

    step = [item for item in matches if object_id in item]
    if len(step) == 1:
        return step[0], BY_OBJECT_ID, {
            item: "does not carry the vacuum's object_id"
            for item in matches if item != step[0]
        }

    step = [
        item for item in matches
        if (traits.get(item) or {}).get("translation_key") == role
    ]
    if len(step) == 1:
        return step[0], BY_TRANSLATION_KEY, _losers(step[0], "translation_key")

    # EXCLUDE the cumulative rather than REQUIRE `measurement`. Dreame marks its
    # lifetime sensor `total_increasing` and leaves the per-run one UNSET — so a
    # test that demanded `measurement` would find zero survivors and fall through
    # on the very hardware it was meant to handle. Verified against the
    # maintainer's live Dreame registry.
    step = [
        item for item in matches
        if (traits.get(item) or {}).get("state_class")
        not in ("total", "total_increasing")
    ]
    if len(step) == 1:
        return step[0], BY_STATE_CLASS, _losers(step[0], "state_class")

    values: dict[str, float] = {}
    for item in matches:
        state = hass.states.get(item)
        try:
            values[item] = float(state.state)  # type: ignore[union-attr]
        except (AttributeError, TypeError, ValueError):
            continue
    if len(values) == len(matches) and len(values) > 1:
        ordered = sorted(values.items(), key=lambda kv: kv[1])
        (smallest_id, smallest), (_, runner_up) = ordered[0], ordered[1]
        # A brand-new vacuum reads 0 for BOTH, and 0 vs 0 is not evidence.
        if smallest >= 0 and runner_up > 0 and runner_up >= smallest * _MAGNITUDE_RATIO:
            return smallest_id, BY_MAGNITUDE, {
                item: f"value={values[item]:g}"
                for item in matches if item != smallest_id
            }

    return None, None, {}


def augment_candidates_from_device(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    entity_candidates: dict[str, list[str]] | None,
    *,
    reserved_suffixes: Iterable[str] | None = None,
    overrides: dict[str, str] | None = None,
    report: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """Append device-registry siblings to each role's candidate list.

    live:ENT-1. Every companion entity is found by DERIVING a name from the
    vacuum's own entity_id — ``sensor.{object_id}_task_status`` and friends —
    with no device lookup anywhere. That silently assumes the companion entities
    were named after the vacuum, which HA does not guarantee: an area prefix, a
    user rename, or an integration that names from the device rather than the
    vacuum entity all produce ids the derivation never generates. The role then
    reads as "this device has no such entity", and the feature is quietly absent
    rather than broken — the worst shape, because nothing errors.

    PROVEN on the maintainer's own install: his companions carry an area prefix,
    so the derived ids do not exist. GitHub issue #48 is the reporter-facing
    version of the same thing.

    THE ADDITION IS PURELY ADDITIVE, and that is the whole safety argument.
    Derived candidates stay FIRST in every list, and detect_capabilities' _find
    takes the first that exists — so an install where derivation already works
    resolves byte-identically and never consults the registry result. Only a role
    that would have resolved to NOTHING can now find something.

    Brand-agnostic by construction: the suffix and domain are read back off the
    candidates the adapter already declared, so this learns no vocabulary of its
    own and a new adapter gets the behaviour for free.

    Best-effort — a registry that cannot be read returns the candidates
    unchanged, because failing to ADD a fallback must never remove one.
    """
    # live:ENT-3 — this function used to fail SILENTLY. Every early return and
    # the blanket except returned the candidates unchanged with no log and no
    # trace, so "the rescue died" and "the rescue ran and found nothing" were
    # indistinguishable in the field. Issue #49 cost a morning of elimination
    # that ONE log line would have answered. `rpt` is that trace; diagnostics
    # publishes it.
    rpt: dict[str, Any] = report if isinstance(report, dict) else {}
    rpt.update(
        {"ran": False, "siblings_seen": 0, "merged": 0, "reason": None, "error": None}
    )

    cands = entity_candidates or {}
    if not cands:
        rpt["reason"] = "no_candidates"
        return dict(cands)

    # live:ENT-7 — APPLY THE OVERRIDE BEFORE ANYTHING CAN FAIL.
    #
    # Every early return below hands back the candidate map unchanged, so an
    # override applied further down would be skipped on exactly the installs it
    # exists to rescue: a vacuum missing from the registry, a registry that
    # raises, a device with no siblings. The user's explicit choice does not
    # depend on the registry search succeeding — it IS the answer the search was
    # looking for.
    user_overrides = overrides if isinstance(overrides, dict) else {}
    applied_overrides: dict[str, str] = {}
    origins: dict[str, dict[str, str]] = {}
    base: dict[str, list[str]] = {}
    for _role, _declared in cands.items():
        _list = list(_declared or [])
        origins[_role] = {item: FROM_DERIVED for item in _list if isinstance(item, str)}
        _override = user_overrides.get(_role)
        if isinstance(_override, str) and "." in _override:
            # First in the list, and _find takes the first that EXISTS — so a
            # resolvable override beats every derived and sibling candidate, and
            # an unresolvable one falls through instead of pinning a dead id.
            _list = [_override] + [item for item in _list if item != _override]
            applied_overrides[_role] = _override
            origins[_role][_override] = FROM_OVERRIDE
        base[_role] = _list
    if applied_overrides:
        rpt["overrides_applied"] = applied_overrides
    rpt["origins"] = origins

    try:
        registry = er.async_get(hass)
        entry = registry.async_get(vacuum_entity_id)
        if entry is None:
            rpt["reason"] = "vacuum_not_in_registry"
            return dict(base)

        # live:ENT-5 — TWO SCOPES, because one of them is proven and the other
        # is the suspect.
        #
        # This function only ever searched the vacuum's DEVICE, while
        # adapters/entity_resolve.resolve_declared_entities searched its CONFIG
        # ENTRY. On issue #49 the config-entry search rescued battery and the
        # dock counters on the very same install, at the very same moment, where
        # the device search rescued nothing — so the config-entry scope is the
        # one with field evidence behind it and the device scope is where the
        # failure lives. Searching both removes an entire class of failure
        # (device_id absent or stale at setup) rather than diagnosing it.
        #
        # DEVICE FIRST, deliberately: it is the tighter, safer scope, and order
        # is priority here. Config-entry entries only fill gaps device scope
        # left, and a config entry shared by TWO vacuums is exactly why the
        # ambiguity guard below refuses to guess.
        siblings, _device_count = _sweep_siblings(registry, entry)
        device_scoped = set(siblings[:_device_count])
        sibling_traits = _sibling_traits(registry, siblings)
        rpt["device_siblings"] = _device_count
        rpt["config_entry_siblings"] = len(siblings) - _device_count

        rpt["siblings_seen"] = len(siblings)
        if not siblings:
            rpt["reason"] = "no_siblings_in_device_or_config_entry"
            return dict(base)
    except Exception as err:
        rpt["reason"] = "registry_error"
        rpt["error"] = repr(err)
        # WARNING, not debug: failing to augment means companion entities go
        # unresolved and features read as absent. That is a user-visible
        # degradation and must not be discoverable only by reading the source.
        _LOGGER.warning(
            "entity augmentation failed for %s — companion entities may not "
            "resolve and features may read as unsupported: %r",
            vacuum_entity_id,
            err,
        )
        return dict(base)

    object_id = vacuum_entity_id.split(".", 1)[-1]
    out: dict[str, list[str]] = {}
    rpt["ran"] = True

    # live:ENT-4 — the SUFFIX UNIVERSE, and why exclusivity is not optional.
    #
    # `endswith` is an unsafe test when one declared suffix is a substring of
    # another: `_cleaning_area` also matches `..._total_cleaning_area`, so a
    # per-run metric can resolve to the LIFETIME TOTAL. That is WRONG DATA, not
    # missing data — the far worse failure, because it reads as working.
    #
    # No amount of name matching separates that pair on its own. The only thing
    # that can is knowing the longer suffix is ALSO declared, so the sibling
    # already has a rightful owner. CONFIRMED on real hardware: issue #49's
    # device carries both entities, and which one won depended on registry order.
    #
    # `reserved_suffixes` exists because the colliding partner is often declared
    # in the adapter's `entities` map rather than in `entity_candidates` — the
    # two halves cannot see each other, so the adapter passes its full suffix
    # vocabulary in. Omit it and this degrades to candidate-vs-candidate
    # exclusivity, which is still strictly better than today.
    universe: set[str] = set()
    for _declared in cands.values():
        for _candidate in _declared or []:
            if not isinstance(_candidate, str) or "." not in _candidate:
                continue
            _, _, _cand_object = _candidate.partition(".")
            if not _cand_object.startswith(object_id):
                continue
            _suffix = _cand_object[len(object_id):]
            if _suffix:
                universe.add(_suffix)
    for _reserved in reserved_suffixes or ():
        if isinstance(_reserved, str) and _reserved:
            universe.add(_reserved)

    def _claimed_by(sib_object: str) -> str | None:
        """The LONGEST declared suffix this sibling ends with — its rightful owner."""
        best: str | None = None
        for known in universe:
            if sib_object.endswith(known) and (best is None or len(known) > len(best)):
                best = known
        return best


    ambiguous: dict[str, list[str]] = {}
    decisions: dict[str, dict[str, Any]] = {}

    for role, declared in cands.items():
        merged = list(base.get(role) or declared or [])

        # live:ENT-7 — the override is already FIRST in `merged` (applied above,
        # before any early return could skip it). Suffix derivation below still
        # walks the ORIGINAL declared ids, so an override that does not follow
        # this vacuum's naming cannot pollute the suffix universe.
        seen = set(merged)

        for candidate in declared or []:
            if not isinstance(candidate, str) or "." not in candidate:
                continue
            domain, _, cand_object = candidate.partition(".")
            # The SUFFIX is whatever the adapter appended to the object_id. Only
            # a candidate actually built from this vacuum's object_id can tell us
            # that, which is exactly the naming assumption being repaired — a
            # candidate that does not start with it teaches us nothing.
            if not cand_object.startswith(object_id):
                continue
            suffix = cand_object[len(object_id):]
            if not suffix:
                continue

            matches: list[str] = []
            for sibling in siblings:
                if sibling in seen:
                    continue
                sib_domain, _, sib_object = sibling.partition(".")
                # Domain AND suffix must both match. Suffix alone would let a
                # `select.*_water_level` satisfy a role that needs the sensor.
                if sib_domain != domain or not sib_object.endswith(suffix):
                    continue
                # EXCLUSIVITY (live:ENT-4): a sibling belongs to the role whose
                # declared suffix explains the most of its name. If a LONGER
                # declared suffix also fits, that role owns it and this one must
                # not borrow it.
                if _claimed_by(sib_object) != suffix:
                    continue
                matches.append(sibling)

            if not matches:
                continue

            # live:ENT-6 — WHEN CANDIDATES COMPETE, DO NOT GUESS.
            #
            # Appending every match and letting the first-existing win makes
            # ENTITY REGISTRY ORDER the tiebreaker, which is not a decision
            # anybody made. Two vacuums on one config entry produce exactly this.
            # entity_resolve.resolve_declared_entities already refuses to guess
            # in the same situation; this now matches that discipline.
            #
            # Two narrowings are tried, cheapest evidence first: a sibling still
            # carrying the vacuum's own object_id, then one matching the majority
            # stem. Neither yielding exactly one leaves the role UNRESOLVED and
            # recorded as ambiguous — which is the signal the options UI needs to
            # pre-fill a choice rather than invent one.
            if len(matches) > 1:
                chosen, decided_by, rejected = _narrow_competing(
                    hass,
                    role=role,
                    object_id=object_id,
                    matches=matches,
                    traits=sibling_traits,
                )
                if chosen is not None:
                    decisions[role] = {
                        "chosen": chosen,
                        "by": decided_by,
                        "rejected": rejected,
                    }
                if chosen is None:
                    # An override means the user already decided this one; do
                    # not report it as needing a decision.
                    if role not in applied_overrides:
                        ambiguous.setdefault(role, sorted(matches))
                    _LOGGER.debug(
                        "%s: role %r has %d competing companions for suffix %r; "
                        "leaving it unresolved rather than guessing: %s",
                        vacuum_entity_id, role, len(matches), suffix, sorted(matches),
                    )
                    continue
                matches = [chosen]

            for sibling in matches:
                merged.append(sibling)
                seen.add(sibling)
                origins.setdefault(role, {})[sibling] = (
                    FROM_DEVICE_SIBLING
                    if sibling in device_scoped
                    else FROM_CONFIG_ENTRY_SIBLING
                )
                rpt["merged"] = int(rpt.get("merged") or 0) + 1

        out[role] = merged

    if ambiguous:
        rpt["ambiguous"] = ambiguous
    if decisions:
        rpt["decisions"] = decisions
    return out


def detect_capabilities(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    detected_model: str | None = None,
    # Adapter-supplied inputs — all optional for graceful degradation
    entity_candidates: dict[str, list[str]] | None = None,
    model_family: str | None = None,
    capability_hints: dict[str, bool] | None = None,
    maintenance_components: dict[str, Any] | None = None,
    # The adapter's FULL suffix vocabulary, including roles it resolves outside
    # `entity_candidates`. Needed so sibling matching knows a longer suffix is
    # already spoken for — see augment_candidates_from_device (live:ENT-4).
    reserved_suffixes: Iterable[str] | None = None,
    # Per-vacuum user overrides, ``{role: entity_id}``. Consulted FIRST — the
    # user's stated choice outranks every derived and sibling candidate
    # (live:ENT-7). Written by both the options flow and the panel's Setup tab;
    # see const.ENTITY_OVERRIDES_KEY for the storage contract.
    entity_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Detect and return a capability map for one vacuum.

    When adapter inputs are provided, entity probing uses the supplied
    candidate lists and model-based hints. When absent (no registered
    adapter), returns a minimal capability set derived from the vacuum
    entity alone.

    "support" flags indicate the entity exists in the registry or the
    model supports the feature; "available" flags indicate the entity is
    currently in the state machine and usable now.
    """
    object_id = vacuum_entity_id.split(".", 1)[1]
    vacuum_state = hass.states.get(vacuum_entity_id)

    supported_features = 0
    if vacuum_state is not None:
        supported_features = int(vacuum_state.attributes.get("supported_features", 0))

    # live:ENT-1: derived names first, device siblings appended behind them. An
    # install where derivation already works resolves byte-identically; only a
    # role that would have found NOTHING can now find something.
    # live:ENT-1: derived names first, device siblings appended behind them. An
    # install where derivation already works resolves byte-identically; only a
    # role that would have found NOTHING can now find something.
    # live:ENT-1: derived names first, device siblings appended behind them. An
    # install where derivation already works resolves byte-identically; only a
    # role that would have found NOTHING can now find something.
    _aug_report: dict[str, Any] = {}
    _cands = augment_candidates_from_device(
        hass,
        vacuum_entity_id,
        entity_candidates,
        reserved_suffixes=reserved_suffixes,
        overrides=entity_overrides,
        report=_aug_report,
    )
    _hints = capability_hints or {}
    _reasons: dict[str, str] = {}
    _sources: dict[str, str] = {}
    _origins = _aug_report.get("origins") or {}
    _overrides = entity_overrides if isinstance(entity_overrides, dict) else {}

    def _find(key: str) -> str | None:
        """Resolve a role, recording WHY it failed (live:ENT-2).

        Returns an id only when the candidate has a STATE — byte-identical to
        the previous behaviour, so no working install changes. A disabled or
        stateless match still resolves to None; it is merely no longer
        indistinguishable from "no such entity" in the report.
        """
        entity_id, reason = resolve_with_reason(hass, _cands.get(key, []))
        # Decide the RETURN before relabelling the reason. Only an entity with a
        # state resolves, exactly as before — otherwise a disabled fall-through
        # would start counting as present and flip capability booleans that read
        # `bool(<role>_entity)`.
        has_state = reason == REASON_RESOLVED
        # live:ENT-7 — an override that did not win must SAY so. It is first in
        # the list, so anything else resolving means the user's choice failed and
        # we fell through. Reporting plain "resolved" there would hide a stale
        # user decision behind a working-looking role.
        wanted = _overrides.get(key)
        if isinstance(wanted, str) and wanted and entity_id != wanted:
            reason = REASON_OVERRIDE_UNRESOLVED
        _reasons[key] = reason
        # live:ENT-12 — where the winner CAME FROM, for every role. Reporting
        # "name match" for an entity the sibling search rescued is a visible
        # falsehood on the one screen built to be trusted.
        if entity_id:
            source = (_origins.get(key) or {}).get(entity_id)
            if source:
                _sources[key] = source
        return entity_id if has_state else None

    def _find_reg(key: str) -> str | None:
        return _find_registered_entity(hass, _cands.get(key, []))

    def _any_present(key: str) -> bool:
        return any(
            _state_exists(hass, e) or _registry_entry_exists(hass, e)
            for e in _cands.get(key, [])
        )

    # --- entity detection ---------------------------------------------------

    task_status_entity                = _find("task_status")
    work_mode_entity                  = _find("work_mode")
    dock_status_entity                = _find("dock_status")
    active_map_entity                 = _find("active_map")
    active_cleaning_target_entity     = _find("active_cleaning_target")
    cleaning_area_entity              = _find("cleaning_area")
    cleaning_time_entity              = _find("cleaning_time")
    water_level_entity                = _find("water_level")
    robot_position_x_entity           = _find("robot_position_x")
    robot_position_y_entity           = _find("robot_position_y")

    task_status_registered            = _find_reg("task_status")
    work_mode_registered              = _find_reg("work_mode")
    dock_status_registered            = _find_reg("dock_status")
    active_map_registered             = _find_reg("active_map")
    active_cleaning_target_registered = _find_reg("active_cleaning_target")
    cleaning_area_registered          = _find_reg("cleaning_area")
    cleaning_time_registered          = _find_reg("cleaning_time")
    water_level_registered            = _find_reg("water_level")
    robot_position_x_registered       = _find_reg("robot_position_x")
    robot_position_y_registered       = _find_reg("robot_position_y")

    # --- dock action button presence ----------------------------------------

    _wash_mop_entity_present      = _any_present("wash_mop_button")
    _dry_mop_entity_present       = _any_present("dry_mop_button")
    _empty_dust_entity_present    = _any_present("empty_dust_button")
    _cleaning_intensity_present   = _any_present("cleaning_intensity")

    # --- capability flags ---------------------------------------------------
    # Hints take precedence (model-confirmed support). Entity presence is the
    # fallback for unrecognised models that still expose the relevant entities.

    robot_position_x_entity_id = robot_position_x_entity or robot_position_x_registered
    robot_position_y_entity_id = robot_position_y_entity or robot_position_y_registered

    # Rooms/segments are available either via an active_map entity OR — for
    # attribute-mode devices that expose the room list as a vacuum attribute but
    # create no map sensor (e.g. Eufy on the scalar/Tuya transport) — via the
    # adapter's `has_attribute_rooms` hint. supports_active_map stays strictly
    # entity-gated: there is no map ENTITY to read in attribute mode, so it must
    # not be reported True (the import path uses the implicit map id instead).
    _has_attribute_rooms            = bool(_hints.get("has_attribute_rooms"))
    supports_rooms                  = bool(active_map_registered or active_map_entity or _has_attribute_rooms)
    supports_segments               = supports_rooms
    supports_active_map             = bool(active_map_registered or active_map_entity)
    supports_active_cleaning_target = bool(
        active_cleaning_target_registered or active_cleaning_target_entity
    )
    supports_task_status    = bool(task_status_registered or task_status_entity)
    supports_work_mode      = bool(work_mode_registered or work_mode_entity)
    supports_dock_status    = bool(dock_status_registered or dock_status_entity)
    supports_cleaning_stats = bool(
        cleaning_area_registered or cleaning_time_registered
        or cleaning_area_entity or cleaning_time_entity
    )
    supports_station_water  = bool(water_level_registered or water_level_entity)
    supports_robot_position = bool(robot_position_x_entity_id and robot_position_y_entity_id)
    robot_position_available = bool(robot_position_x_entity and robot_position_y_entity)

    # Hint OR entity presence — True from either source is sufficient.
    supports_mop_features = bool(_hints.get("supports_mop_features")) or bool(
        water_level_registered or water_level_entity
    )
    supports_mop_wash     = bool(_hints.get("supports_mop_wash"))   or _wash_mop_entity_present
    supports_mop_dry      = bool(_hints.get("supports_mop_dry"))    or _dry_mop_entity_present
    supports_empty_dust   = bool(_hints.get("supports_empty_dust")) or _empty_dust_entity_present
    supports_path_control = bool(_hints.get("supports_path_control")) or _cleaning_intensity_present

    # An explicit adapter hint wins (the Roborock S6 declares supports_water_control
    # False because its mop/water is unsettable — SET_WATER_BOX/MOP_MODE are
    # RoborockUnsupportedFeature); otherwise derive it from mop support as before. Eufy
    # is unchanged (it passes no such hint, or passes True, so it falls through to
    # supports_mop_features=True either way).
    def _hint_wins(name: str, derived: bool) -> bool:
        """An explicit adapter capability_hint overrides the derived/default value.

        Distinct from the permissive "hint OR entity presence" rule above: these are
        capabilities a brand can categorically NOT do, so a declared False must be
        authoritative. A hardcoded default here is unreachable by any adapter -- which is
        exactly how supports_edge_mopping stayed True for a brand declaring it False.
        """
        return bool(_hints[name]) if name in _hints else derived

    supports_water_control      = _hint_wins("supports_water_control", supports_mop_features)
    supports_edge_mopping       = _hint_wins("supports_edge_mopping", True)
    supports_passes             = _hint_wins("supports_passes", True)
    supports_custom_room_config = _hint_wins("supports_custom_room_config", True)
    supports_room_clean         = _hint_wins("supports_room_clean", True)
    # Ad-hoc free-form zone cleaning ("draw a box on the live map"). BOTH shipped adapters
    # hardcoded this True in their config dicts, which is the unreachable-default shape this
    # helper's docstring warns about: a model that categorically cannot zone-clean had no way
    # to say so, because there was nothing to declare AGAINST. True stays the default — both
    # brands do support it today — but it is now a hint a model catalog can override.
    supports_zone_clean         = _hint_wins("supports_zone_clean", True)

    # --- maintenance sources ------------------------------------------------

    maintenance_sources: dict[str, str | None] = {}
    if maintenance_components:
        # live:ENT-8 — hand the same two-scope sibling list to maintenance.
        # Derived-first still wins inside, so an install where the names already
        # match resolves byte-identically and never consults this.
        _maint_siblings: list[str] = []
        try:
            _registry = er.async_get(hass)
            _entry = _registry.async_get(vacuum_entity_id)
            if _entry is not None:
                _maint_siblings, _ = _sweep_siblings(_registry, _entry)
        except Exception:  # pragma: no cover - defensive
            _LOGGER.debug(
                "maintenance sibling sweep failed for %s", vacuum_entity_id,
                exc_info=True,
            )

        maintenance_sources = _detect_maintenance_sources(
            hass,
            object_id=object_id,
            maintenance_components=maintenance_components,
            siblings=_maint_siblings,
            overrides=_overrides,
        )

    # --- live state values --------------------------------------------------

    _task_state = hass.states.get(task_status_entity) if task_status_entity else None
    task_status_value = _task_state.state if _task_state else None
    _dock_state = hass.states.get(dock_status_entity) if dock_status_entity else None
    dock_status_value = _dock_state.state if _dock_state else None

    robot_position_status = (
        "available" if robot_position_available
        else ("registered" if supports_robot_position else "inactive")
    )
    robot_position_message = (
        "Position tracking active." if robot_position_available
        else (
            "Position entities registered but not yet in state machine."
            if supports_robot_position
            else "Robot position entities not found."
        )
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        # live:ENT-2/ENT-3 — WHY each role resolved as it did, and whether the
        # device-sibling rescue ran at all. Both are diagnostics-facing only;
        # nothing branches on them. They exist because issue #49 could not be
        # answered from a dump that reported a bare `null` per role.
        "entity_resolution_reasons": dict(_reasons),
        "entity_sources": dict(_sources),
        "entity_augmentation": dict(_aug_report),
        "detected_model": detected_model,
        "model_family": model_family or "generic",
        "supported_features": supported_features,
        "supports_room_clean": supports_room_clean,
        "supports_custom_room_config": supports_custom_room_config,
        "supports_zone_clean": supports_zone_clean,
        "supports_rooms": supports_rooms,
        "supports_segments": supports_segments,
        "supports_active_map": supports_active_map,
        "active_map_available": bool(active_map_entity),
        "supports_active_cleaning_target": supports_active_cleaning_target,
        "active_cleaning_target_available": bool(active_cleaning_target_entity),
        "supports_task_status": supports_task_status,
        "task_status_available": bool(task_status_entity),
        "supports_work_mode": supports_work_mode,
        "work_mode_available": bool(work_mode_entity),
        "supports_dock_status": supports_dock_status,
        "dock_status_available": bool(dock_status_entity),
        "supports_cleaning_stats": supports_cleaning_stats,
        "cleaning_stats_available": bool(cleaning_area_entity or cleaning_time_entity),
        "supports_station_water": supports_station_water,
        "station_water_available": bool(water_level_entity),
        "supports_robot_position": supports_robot_position,
        "robot_position_available": robot_position_available,
        "robot_position_status": robot_position_status,
        "robot_position_message": robot_position_message,
        "supports_mop_features": supports_mop_features,
        "supports_mop_wash": supports_mop_wash,
        "supports_mop_dry": supports_mop_dry,
        "supports_empty_dust": supports_empty_dust,
        "supports_path_control": supports_path_control,
        "supports_water_control": supports_water_control,
        "supports_edge_mopping": supports_edge_mopping,
        "supports_passes": supports_passes,
        "entities": {
            "task_status": task_status_entity or task_status_registered,
            "work_mode": work_mode_entity or work_mode_registered,
            "dock_status": dock_status_entity or dock_status_registered,
            "active_map": active_map_entity or active_map_registered,
            "active_cleaning_target": (
                active_cleaning_target_entity or active_cleaning_target_registered
            ),
            "cleaning_area": cleaning_area_entity or cleaning_area_registered,
            "cleaning_time": cleaning_time_entity or cleaning_time_registered,
            "water_level": water_level_entity or water_level_registered,
            "robot_position_x": robot_position_x_entity_id,
            "robot_position_y": robot_position_y_entity_id,
        },
        "sources": {
            "rooms_count": 0,
            "segments_count": 0,
            "dock_status_value": dock_status_value,
            "task_status_value": task_status_value,
        },
        "maintenance_sources": maintenance_sources,
    }
