"""Reads room segment data from the vacuum's HA state and normalizes it for storage.

All brand-specific knowledge (which entity exposes the room list, which
attribute contains it, which keys hold room ID and name) comes from the
adapter registry's discovery config block. This file contains no vacuum
brand assumptions — it reads whatever the adapter declares.

Adapter config shape consumed here (adapters/config_schema.py § discovery). SEVEN
keys are read, not the four this block listed until 2026-08-24 (R26), and the one
it omitted — ``source`` — is the one that selects the whole branch:
    source:              "entity_attribute" (default) | "service_response". A
                         service-response adapter reads NEITHER room_list_ key
                         below; its rooms come from the cache source_refresh.py
                         fills (get_cached_room_source + select_segments_for_map).
    room_list_shape:     "flat_list" (default) | "per_map_mapping" — declared
                         INDEPENDENTLY of source, and read only on the attribute
                         branch (the service flattener always produces per-map
                         keying). Conflating shape with source is what discovered
                         ZERO rooms for Dreame until 2026-08-07.
    implicit_map_id:     str — synthetic map id for an attribute-mode device that
                         creates no active_map sensor (_implicit_attribute_map_id).
    room_list_entity:    "vacuum_entity" | <full entity_id>  (attribute source only).
                         DEFAULTS to "vacuum_entity" when absent, which is what the
                         schema has always documented and what no reader here honoured
                         until 2026-11-08 — see declared_room_list_entity, and note
                         that an absent key used to switch the [MAP-ANCHOR-1] guard off
                         rather than merely decline a room list. A key declared EMPTY
                         is still a refusal; absent and empty are different inputs.
    room_list_attribute: str — attribute name on the entity (attribute source only).
                         Genuinely required: nothing can name it for the adapter.
    room_id_key:         str — key in each room dict for the room ID
    room_name_key:       str — key in each room dict for the room name

The four-key version read as this file's declared interface with the adapter
schema, so a porter working from it declares those four, omits ``source``, lands
on the attribute branch by default and discovers nothing — the same failure the
source/shape split was made to end.

Degradation when the adapter is not registered or the discovery config is absent
is per-function, and there are THREE public functions here, not the "both" this
said until 2026-08-24 (R26):
    get_active_map_id          -> None
    discover_rooms_for_vacuum  -> []
    discover_rooms_payload     -> always a dict (``rooms: []``, ``room_count: 0``,
                                  ``active_map_id: None``) — never None
"""

# System invariants that bind in this file. Declared and explained elsewhere
# (docs/dev/00b-invariants.md); `scripts/doc_anchor.py --show <TOKEN>` from here.
# The findings under each are the FAILURES THAT PRODUCED the rule -- history, with
# the packet that OWNS them. They are not a to-do list; see OPEN-FIX-CHECKLIST.
#
# A packet id here is the ledger's ATTRIBUTION, not a verification that the fix
# landed in THIS file. Measured 2026-08-18 (.claude/notes/_audit_closure_claims.py):
# 35 of 60 claims name a packet whose commits -- full git footprint, not just the
# ledger's list -- never touched the file the claim sits in. Two were then read and
# both were still LIVE: DQ-Q-7 (queue_engine) and A5-PP-RP-8 (this pattern, in both
# copies). These blocks were written 2026-08-17 by transcribing the ledger, so they
# inherited its mis-attributions into source -- where prose at the site reads as
# authority. Verify before citing one as closed.
#   INMKEHPQ  `rooms/room_manager.py#INMKEHPQ`
#       A1-ID-2 (closed RP-019): discover_rooms_for_vacuum's single-map fallback serves ANOTHER map's room list and
#              relabels it with the REQUESTED map_id, defeating the map_id filter at both room


from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import slugify_room_name
from .source_refresh import (
    SHAPE_PER_MAP_MAPPING,
    SOURCE_SERVICE_RESPONSE,
    get_cached_room_source,
    select_segments_for_map,
)
from ..adapters.registry import get_adapter_config
from ..entity_helpers import BLANK_STATE_VALUES, is_blank_state, normalize_map_id

_LOGGER = logging.getLogger(__name__)

#: Roles already complained about by [MAP-ANCHOR-1], keyed (vacuum_entity_id,
#: active_map_entity_id). Module-level because get_active_map_id is a module function
#: with no instance to hang it on; the instance-level twin is
#: ``jobs/active_job.py::_multi_in_flight_warned``.
#:
#: BOUNDED BY CONSTRUCTION: one entry per vacuum+role, never per value — see the
#: comment at the warn site for why keying on the value would both grow without bound
#: and defeat the throttle. Cleared on a clean resolution so a later regression is
#: reported rather than swallowed.
_MISBOUND_ACTIVE_MAP_WARNED: set[tuple[str, str]] = set()

#: The core SENTINEL meaning "the room list is an attribute on the vacuum entity
#: itself", as opposed to a full entity id naming another entity. A sentinel, not a
#: brand's word -- the same class as ``default_profile`` -- so defaulting to it does
#: not make core speak Eufy.
ROOM_LIST_ENTITY_SELF = "vacuum_entity"


def declared_room_list_entity(discovery: dict | None) -> str:
    """Which entity the room list is declared on, WITH the schema's documented default.

    ONE QUESTION, FOUR ASKERS. ``discovery.room_list_entity`` is documented in
    ``adapters/config_schema.py`` as "Default: 'vacuum_entity'", and until 2026-11-08
    that default existed in exactly one of the four places that read the key --
    ``onboarding/manager.py``, whose own reader sits in a method with no production
    callers. The three live readers in this file each treated an absent key as "NOT the
    vacuum entity", which is a different answer, so the documented contract was honoured
    in zero live paths.

    THE COST WAS NOT A MISSING ROOM LIST, and that is why this resolves to the default
    rather than the refusal. At ``_known_map_ids`` an absent key makes the map set
    unenumerable, which switches OFF the [MAP-ANCHOR-1] / ISSUE #60 guard entirely --
    measured, with a positive control: with the key absent a camera's last-updated
    timestamp ``'2026-10-02 11:04:35'`` comes back as the vacuum's active map id, and
    with it present the same value is refused. An absent declaration silently disabling
    a guard is not a diagnosis problem; it is the hole the guard was added to close.

    ``.get(key, default)``, NEVER ``value or default``. The two differ on exactly one
    input and the difference is deliberate: a key declared EMPTY stays empty and is
    still a refusal, because someone who cleared a field did not ask to read the vacuum.
    ``RD-19[empty_entity]`` is the row that separates the two forms, and the ``or``
    spelling reddens it.
    """
    return (discovery or {}).get("room_list_entity", ROOM_LIST_ENTITY_SELF)

# HA sentinel states that mean "no usable value".
#: Kept as a NAME (diagnostics imports it) but derived from the shared vocabulary so the
#: MEMBERSHIP cannot drift again. It gains "null" — this sensor previously caught only
#: the Python str(None) leak form and missed the JSON one.
#: ⚠ was: "so it cannot drift again", unqualified, until 2026-08-24 (RM27). The
#: VOCABULARY was centralised; the QUESTION was not. This module never tests the set
#: directly — it asks `is_blank_state`, which strips and lowercases. Its one importer,
#: `diagnostics.py`, asks raw set membership instead (`active_map_state not in
#: _ACTIVE_MAP_SENTINELS`), so a provider publishing "Unknown" or " unknown " is BLANK
#: here (`get_active_map_id` returns None and the import refuses) and USABLE there (the
#: self-check reports the map resolves) — the same report-vs-behaviour disagreement
#: diagnostics.py records fixing for the `exists` tell, one predicate along. Sharing the
#: constant is not sharing the question; only routing both through `is_blank_state` is.
_ACTIVE_MAP_SENTINELS = BLANK_STATE_VALUES


def get_active_map_id(hass: HomeAssistant, vacuum_entity_id: str) -> str | None:
    """Return the active map ID for a vacuum, if available.

    The adapter declares ``entities.active_map`` from a NAMING PATTERN for every
    device, so the config always carries an entity id — "declared" does NOT mean
    "exists". Resolution therefore keys off whether the entity actually exists:

    - Entity present in the state machine → it is the source of truth, but no longer
      an UNCONDITIONAL one. Since [MAP-ANCHOR-1] (ISSUE #60) its state is checked
      against the vacuum's enumerable map ids: a value that is not one of them is
      refused and this returns None, because an overridden role can point at an
      entity whose state was never a map id (a camera reporting a timestamp). The
      check is skipped entirely when the map set is not enumerable — see
      `_known_map_ids` — so it cannot reject a valid id during a boot window.
      (A sentinel value still returns None — wait, don't fork a second map.)
    - Entity absent from the state machine but present in the ENTITY REGISTRY →
      a novel device whose sensor hasn't materialised yet (boot/restart window):
      return None and wait. Must NOT fork a phantom implicit map.
    - Entity absent from BOTH state machine and registry → the sensor is never
      created. TWO fallbacks are tried in order, and the ladder does not stop at
      the first: `_implicit_attribute_map_id`, for an attribute-mode device (e.g.
      Eufy on the scalar/Tuya transport) that surfaces its room list as a vacuum
      attribute; then, when that returns None, `_single_cached_map_id`, which
      serves a SERVICE-RESPONSE brand (Roborock) whose cached room source holds
      exactly one map.

    ⚠ This branch was described as attribute-mode-only, and the docstring closed
    with a flat "Returns None when no path yields an id", until 2026-08-24 (R11).
    Both stopped being true when `_single_cached_map_id` was added for ISSUE #46:
    the fall-through is `return _single_cached_map_id(...)`, not `return None`, so
    a Roborock with no map-selector entity CAN resolve a map id here. Anyone
    auditing whether this function can invent a map anchor has to read that helper
    — its narrowing rules (exactly one cached map, service source only, the map
    must actually carry rooms) are the real answer, not this ladder.

    Returns None only when every path above declines.
    """
    config = get_adapter_config(vacuum_entity_id)
    active_map_entity = (config or {}).get("entities", {}).get("active_map")

    if active_map_entity:
        state = hass.states.get(active_map_entity)
        if state is not None:
            value = state.state
            if not is_blank_state(value):
                # [MAP-ANCHOR-1] The entity's state is the id ONLY if it looks like one.
                #
                # ISSUE #60. `entities.active_map` is a naming declaration resolved at
                # runtime, and an entity OVERRIDE pins it with no domain check (see
                # adapters/entity_resolve.py — the override pass runs before the state
                # check and applies none of its own). A Dreame owner whose vacuum was
                # named `vacuum.apartment_doomba_iii_doomba_iii` while its siblings were
                # `doomba_iii_*` saw every derived id miss, overrode active_map onto
                # `camera.doomba_iii_map` — the entity literally called "map" — and that
                # camera's state is the map's LAST-UPDATED TIMESTAMP. So this returned
                # "2026-10-02 11:04:35" as a map id. It matched no map, import refused
                # with "No map could be identified", and the value had already travelled
                # into diagnostics as `active_map_id`.
                #
                # DECLINE, NEVER SUBSTITUTE. Returning None costs an import the user was
                # not getting anyway; substituting the single map when the lookup misses
                # is the RP-019/ID-2 failure that 17-room-identity.md §"two no-selector
                # fallbacks" explicitly forbids — serving one map's rooms relabelled with
                # another map's id. select_segments_for_map draws the same line and
                # reserves "unknown" for the genuinely-unresolvable case.
                #
                # SILENT WHEN UNKNOWABLE. `_known_map_ids` returns None whenever the map
                # set cannot be enumerated — a flat_list brand, a service brand whose
                # cache has not refreshed, the boot window before the attribute lands.
                # Validating then would reject a VALID id on every restart, so the guard
                # only fires against a map set we actually have.
                known = _known_map_ids(hass, vacuum_entity_id, config)
                # ISSUE #62 — normalise BOTH sides. `source_refresh` already strips the
                # name it caches under, so comparing this entity's raw state against
                # those keys fails on any map whose name carries surrounding whitespace,
                # and [MAP-ANCHOR-1] then refuses it as "not a map id". It is a real map
                # and the only difference is invisible.
                _value = normalize_map_id(value)
                if known is not None and _value not in {normalize_map_id(k) for k in known}:
                    # WARN ONCE PER MIS-BOUND ROLE, not once per resolution. This
                    # resolver runs on a ~60s timer, so an unthrottled warning gives the
                    # one user it exists for ~1440 identical lines a day, per vacuum,
                    # forever — and a log that repeats that hard is a log nobody reads,
                    # which costs exactly the diagnostic this was added to provide.
                    #
                    # KEYED ON THE ROLE, NOT THE VALUE, and that is the whole trick. The
                    # value that triggered ISSUE #60 is a camera's last-updated
                    # TIMESTAMP: it changes every map update, so a (role, value) key
                    # would grow without bound AND still warn on nearly every pass. The
                    # user needs telling that the role is mis-bound; which wrong value
                    # it happened to hold is incidental.
                    warn_key = (vacuum_entity_id, active_map_entity)
                    if warn_key not in _MISBOUND_ACTIVE_MAP_WARNED:
                        _MISBOUND_ACTIVE_MAP_WARNED.add(warn_key)
                        _LOGGER.warning(
                            "Active map entity %s for %s reports %r, which is not one of "
                            "this vacuum's maps (%s). Refusing it as a map anchor — check "
                            "that this role points at the map SELECTOR and not at a camera "
                            "or another entity whose state is not a map id. (Logged once "
                            "per role; it will log again if this recurs after a good "
                            "resolution.)",
                            active_map_entity, vacuum_entity_id, value,
                            ", ".join(sorted(known)) or "none",
                        )
                    return None
                # Resolved cleanly — forget any past complaint about this role so a
                # LATER regression is reported again instead of being swallowed by a
                # latch that never clears. A warn-once set that is never cleared is the
                # shape that silently stops reporting real recurrences.
                _MISBOUND_ACTIVE_MAP_WARNED.discard((vacuum_entity_id, active_map_entity))
                # Return the CANONICAL form, not the raw state. Matching on the
                # normalised value and then handing back the unnormalised one would move
                # the failure rather than fix it: every downstream lookup -- the room
                # cache, managed_rooms_by_map, the per-map camera slug -- is keyed on the
                # stripped name, so a trailing space would miss them all exactly as it
                # missed the comparison above.
                return _value
            # Blank/unavailable selector. The meaning depends on the room-list SHAPE:
            #
            #  * per_map_mapping (Dreame): this is the STEADY state of a SINGLE-map
            #    device — the upstream integration only makes select.<id>_selected_map
            #    available while multi-floor mapping is ON, so a one-map device leaves it
            #    `unavailable`. The rooms live in the vacuum attribute keyed by map, so
            #    fall through to the single-map fallback (narrow: exactly one map with
            #    rooms; a real multi-map device has >1 key and still returns None).
            #  * flat_list (Eufy scalar/Tuya): the selector IS the map identity and a
            #    blank is TRANSIENT (the map momentarily offline). Falling through would
            #    fork a phantom map for a device whose real map is about to return — the
            #    [RD-10] guard. So keep waiting: return None.
            if (config or {}).get("discovery", {}).get("room_list_shape") != SHAPE_PER_MAP_MAPPING:
                _LOGGER.debug(
                    "Active map entity %s sentinel value for %s: %s",
                    active_map_entity, vacuum_entity_id, value,
                )
                return None
            # per_map single-map: the selector is PRESENT-but-blank, so it is also
            # REGISTERED — the registered-but-stateless wait-branch below (meant for a
            # state-is-None entity) would wrongly return None and never reach the
            # fallback. Go straight to the single-map anchor here; a >1-map device still
            # returns None inside it.
            _LOGGER.debug(
                "Active map entity %s blank for per-map-mapping %s (%s) — trying "
                "single-map fallback", active_map_entity, vacuum_entity_id, value,
            )
            return _implicit_attribute_map_id(hass, vacuum_entity_id, config)
        # Declared but not in the state machine. Distinguish a registered-but-
        # not-yet-materialised sensor (novel boot race → wait) from a sensor that
        # is never created (scalar/attribute mode → implicit fallback).
        if _entity_registered(hass, active_map_entity):
            _LOGGER.debug(
                "Active map entity %s registered but no state yet for %s — waiting",
                active_map_entity, vacuum_entity_id,
            )
            return None
        _LOGGER.debug(
            "Active map entity %s declared but never created for %s — trying "
            "implicit attribute map", active_map_entity, vacuum_entity_id,
        )

    implicit = _implicit_attribute_map_id(hass, vacuum_entity_id, config)
    if implicit is not None:
        return implicit
    return _single_cached_map_id(hass, vacuum_entity_id, config)


def _entity_registered(hass: HomeAssistant, entity_id: str) -> bool:
    """True if entity_id exists in the HA entity registry.

    Used to tell a sensor that is momentarily stateless (registered, e.g. during
    a restart) from one that is never created at all (the scalar transport never
    registers an active_map sensor). Defensive — never raises.
    """
    try:
        return er.async_get(hass).async_get(entity_id) is not None
    except Exception:  # pragma: no cover - defensive
        return False


def _known_map_ids(
    hass: HomeAssistant, vacuum_entity_id: str, config: dict | None
) -> set[str] | None:
    """The map ids this vacuum actually reports, or None when they are unknowable.

    [MAP-ANCHOR-1]'s evidence source. Enumerates the SAME per-map keying that
    ``select_segments_for_map`` looks a resolved id up in, so "known here" and
    "findable there" cannot drift apart.

    ``None`` and ``set()`` mean different things and the caller depends on it:

    - ``None``  — the map set is not enumerable, so no judgement is possible. A
      ``flat_list`` brand has no per-map keying at all; a service brand whose cache
      has not refreshed yet has nothing to enumerate; the attribute may not have
      landed during the boot window. The caller must trust the entity in this case,
      because rejecting on an empty-because-early set would refuse a VALID id on
      every restart — a far worse failure than the one [MAP-ANCHOR-1] fixes.
    - a non-empty set — these are the ids; anything else is not a map id.

    An empty set is normalised to ``None`` for that reason: "I enumerated and found
    no maps" is indistinguishable here from "I could not enumerate", and the safe
    reading of both is *do not judge*.

    Defensive throughout — a resolver that raises would break map import for every
    brand, and this exists only to refuse one bad value.
    """
    try:
        discovery = (config or {}).get("discovery", {}) or {}

        if discovery.get("source") == SOURCE_SERVICE_RESPONSE:
            cached = get_cached_room_source(hass, vacuum_entity_id)
            keys = {str(k) for k in cached} if isinstance(cached, dict) else set()
            return keys or None

        # Attribute source. Only the per-map shape carries map identity; a flat list
        # is one unkeyed room list and says nothing about which maps exist.
        if discovery.get("room_list_shape") != SHAPE_PER_MAP_MAPPING:
            return None
        attr = discovery.get("room_list_attribute")
        if not attr or declared_room_list_entity(discovery) != ROOM_LIST_ENTITY_SELF:
            return None
        state = hass.states.get(vacuum_entity_id)
        rooms = state.attributes.get(attr) if state is not None else None
        keys = {str(k) for k in rooms} if isinstance(rooms, dict) else set()
        return keys or None
    except Exception:  # pragma: no cover - defensive
        return None


def _single_cached_map_id(
    hass: HomeAssistant, vacuum_entity_id: str, config: dict | None
) -> str | None:
    """The one map's id for a service-response brand that reports exactly one map.

    ISSUE #46. HA 2026.7 changed how the core Roborock integration decides which
    entities to create (home-assistant/core#173282), and on some devices the
    map-selector entity is no longer created AT ALL. `entities.active_map` is a
    NAMING declaration, so the adapter still names it and every branch above
    returns None: not in the state machine, not in the registry, and the implicit
    fallback is attribute-source-only. Map import then refused at "no map
    detected" while the device's rooms decoded perfectly — the room list was
    never the problem, the anchor was.

    A vacuum with exactly ONE map does not need a selector to say which map is
    active; there is only one answer, and the cached room source is already keyed
    by it. So take that key.

    Deliberately narrow, because the cost of guessing wrong here is serving one
    map's rooms under another's id — the exact bug RP-019/ID-2 guards in
    discover_rooms_for_vacuum:
      * ONLY when the cache holds exactly one map. Two or more and the selector
        genuinely carried information we no longer have, so we return None and
        the caller reports honestly rather than picking a map.
      * ONLY for a service-response source. Attribute brands have their own
        implicit path above and must not reach this one.
      * The map must actually carry rooms — an empty list anchors nothing.
    """
    discovery = (config or {}).get("discovery", {}) or {}
    if discovery.get("source") != SOURCE_SERVICE_RESPONSE:
        return None
    per_map = get_cached_room_source(hass, vacuum_entity_id)
    if not isinstance(per_map, dict) or len(per_map) != 1:
        return None
    map_id, segments = next(iter(per_map.items()))
    if not isinstance(segments, list) or not any(
        isinstance(row, dict) for row in segments
    ):
        return None
    _LOGGER.debug(
        "No active-map entity for %s; the cached room source holds exactly one "
        "map (%s) with rooms — using it as the anchor (issue #46)",
        vacuum_entity_id, map_id,
    )
    return str(map_id)


def _implicit_attribute_map_id(
    hass: HomeAssistant, vacuum_entity_id: str, config: dict | None
) -> str | None:
    """Single implicit map id for an attribute-mode device (no active_map sensor).

    A device that exposes its room list as a vacuum-entity attribute but creates
    no active_map sensor still has exactly one map. When the adapter declares
    ``discovery.implicit_map_id`` AND that room-list attribute currently holds at
    least one room-shaped (dict) row, return the implicit id so import/discovery
    have an anchor. Returns None otherwise — so brands that don't opt in
    (Roborock, which uses a service-response source and sets no implicit_map_id)
    are unaffected, and the implicit map never appears for a device that exposes
    no usable rooms (an empty or all-junk segments list — which discovery would
    reject anyway).
    """
    discovery = (config or {}).get("discovery", {}) or {}
    implicit = discovery.get("implicit_map_id")
    attr = discovery.get("room_list_attribute")
    # Only the vacuum-attribute room source supports an implicit single map.
    if (
        not implicit
        or not attr
        or declared_room_list_entity(discovery) != ROOM_LIST_ENTITY_SELF
    ):
        return None
    state = hass.states.get(vacuum_entity_id)
    rooms = state.attributes.get(attr) if state is not None else None
    # PER-MAP-MAPPING shape ({map_name: [rooms]}, e.g. Dreame): a device with exactly
    # ONE map whose room list is usable anchors on that map's KEY — which is the value
    # select_segments_for_map looks up, so discovery finds the rooms it just refreshed.
    # `implicit_map_id` is the opt-in flag (checked above); the KEY is the real anchor,
    # so it stays correct if the single map is renamed. Two+ maps -> None (the selector
    # genuinely carried information; do not guess).
    if discovery.get("room_list_shape") == SHAPE_PER_MAP_MAPPING:
        if isinstance(rooms, dict) and len(rooms) == 1:
            (map_name, seg), = rooms.items()
            if isinstance(seg, list) and any(isinstance(r, dict) for r in seg):
                return str(map_name)
        return None
    # FLAT-LIST shape (Eufy scalar/Tuya): the declared implicit id itself is the anchor.
    # Require at least one dict row — a non-empty list of non-dicts is not a usable
    # room list and must not anchor a phantom map (matches discover_rooms' filter).
    if isinstance(rooms, list) and any(isinstance(r, dict) for r in rooms):
        return str(implicit)
    return None


def discover_rooms_for_vacuum(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return normalized room dicts from the adapter's declared room list entity.

    Reads discovery config from the adapter registry. ``source`` is read FIRST and
    decides which of the rest apply:
      source              — "entity_attribute" (default) or "service_response"
      room_id_key         — key in each room dict for the room ID   (both sources)
      room_name_key       — key in each room dict for the room name (both sources)
      room_list_entity    — "vacuum_entity" or a full entity ID    (attribute only)
      room_list_attribute — attribute name that holds the room list (attribute only)
      room_list_shape     — "flat_list" (default) or "per_map_mapping" (attribute
                            only; the service flattener always keys per map)

    ⚠ This listed room_list_entity / room_list_attribute / room_id_key /
    room_name_key as the whole contract until 2026-08-24 (R15) — it was written
    before SOURCE and SHAPE were split into two axes on 2026-08-07. On the
    SOURCE_SERVICE_RESPONSE branch the two room_list_ keys are never read at all:
    the rooms come from ``get_cached_room_source`` + ``select_segments_for_map``.
    An adapter declared from the old four-key list omits ``source``, silently
    defaults to the attribute branch and discovers zero rooms — the same failure
    the SHAPE comment in the attribute branch below records happening to Dreame
    when shape was conflated with source.

    Returns an empty list when the adapter is not registered, discovery config is
    absent, room_id_key/room_name_key are missing, or the branch actually taken
    yields no usable rooms. Those last conditions are NOT one condition: on the
    attribute branch it is "the room list attribute is missing/invalid"; on the
    service branch it is "the cache holds nothing for this map", which is a
    refresh/timing state rather than a config error.
    """
    config = get_adapter_config(vacuum_entity_id)
    discovery = (config or {}).get("discovery", {})

    source_kind = discovery.get("source")
    room_id_key = discovery.get("room_id_key")
    room_name_key = discovery.get("room_name_key")

    # Both sources still need to know which keys carry the room id + name.
    if not all((room_id_key, room_name_key)):
        _LOGGER.debug(
            "Discovery config incomplete for %s — skipping room discovery",
            vacuum_entity_id,
        )
        return []

    # ⚠ "unknown" here and the DISCOVERY CACHE KEY disagree when the active map
    # cannot be resolved (2026-08-24, RM22). ``room_crud.discover_rooms`` keys its
    # cache with ``str(payload.get("active_map_id") or map_id or "")`` — the EMPTY
    # STRING, because ``discover_rooms_payload`` has no "unknown" fallback — while
    # every room returned here is stamped ``map_id="unknown"``. See that site for
    # what the mismatch costs ``save_managed_rooms``/``reconcile_room``.
    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id) or "unknown"

    if source_kind == SOURCE_SERVICE_RESPONSE:
        # The room list lives in a cached service response (refreshed at the
        # async boundaries by async_refresh_room_source), keyed by map NAME —
        # the same value entities.active_map reports for these brands.
        per_map = get_cached_room_source(hass, vacuum_entity_id)
        # Selection rule lives in source_refresh.select_segments_for_map so the
        # attribute branch below shares it verbatim — including the RP-019/ID-2
        # guard against serving another map's rooms under the requested id.
        segments = select_segments_for_map(per_map, resolved_map_id)
        if segments is None:
            _LOGGER.debug(
                "No cached room source for %s map %s",
                vacuum_entity_id,
                resolved_map_id,
            )
            return []
    else:
        # Attribute source (default, e.g. Eufy): the room list is a live
        # attribute on an entity.
        #
        # ⚠ THIS COMMENT SAID BOTH KEYS WERE "required here" UNTIL 2026-11-08, AND IT
        # WAS THE ONLY STATEMENT IN THE TREE SAYING SO -- against a schema entry that
        # says `"required": False` and documents `room_list_entity` as defaulting to
        # the vacuum entity, a generated reference that repeats that default, and three
        # retired docs that do too. Prose at the site reads as authority, which is how
        # the contradiction survived. `room_list_attribute` IS still required: nothing
        # can name the attribute for the adapter, and absence of it is what the refusal
        # below now means.
        room_list_entity_key = declared_room_list_entity(discovery)
        room_list_attribute = discovery.get("room_list_attribute")
        if not all((room_list_entity_key, room_list_attribute)):
            _LOGGER.debug(
                "Attribute discovery config incomplete for %s — skipping",
                vacuum_entity_id,
            )
            return []

        source_entity_id = (
            vacuum_entity_id
            if room_list_entity_key == ROOM_LIST_ENTITY_SELF
            else room_list_entity_key
        )
        source_state = hass.states.get(source_entity_id)
        if source_state is None:
            _LOGGER.debug(  # pragma: no cover
                "Room list entity %s missing for %s", source_entity_id, vacuum_entity_id
            )
            return []

        raw = source_state.attributes.get(room_list_attribute)

        # SHAPE is declared independently of SOURCE. Until 2026-08-07 this branch
        # assumed a flat list, so a brand serving {map_name: [rooms]} as a live
        # attribute (Dreame) fell through to "missing or invalid" and discovered
        # ZERO rooms — with every other config block then inert. Declaring the
        # shape is the extension point; an `if brand == ...` here would be core
        # learning a brand's name, which is the thing the adapter boundary exists
        # to prevent.
        if discovery.get("room_list_shape") == SHAPE_PER_MAP_MAPPING:
            segments = select_segments_for_map(raw, resolved_map_id)
            if segments is None:
                _LOGGER.debug(
                    "Room list attribute '%s' holds no rooms for %s map %s",
                    room_list_attribute,
                    vacuum_entity_id,
                    resolved_map_id,
                )
                return []
        else:
            segments = raw
            if not isinstance(segments, list):
                _LOGGER.debug(
                    "Room list attribute '%s' missing or invalid for %s",
                    room_list_attribute,
                    vacuum_entity_id,
                )
                return []

    rooms: list[dict[str, Any]] = []
    seen_room_ids: set[int] = set()

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        raw_name = segment.get(room_name_key)
        raw_id = segment.get(room_id_key)

        if raw_name is None or raw_id is None:
            continue

        try:
            room_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if room_id in seen_room_ids:
            continue

        seen_room_ids.add(room_id)

        name = str(raw_name).strip()
        if not name:
            continue

        slug = slugify_room_name(name)
        if not slug:
            # RP-015/A1-ID-3: only the RAW name was checked for emptiness — an
            # all-punctuation name (e.g. a bare pair of quote characters)
            # strips to an empty slug, which can never be a stable identity
            # key (reconciliation/dispatch/learning all key off it).
            _LOGGER.warning(
                "Room %s for %s slugifies to an empty identity from raw name "
                "%r — skipped rather than admitted with no usable slug",
                room_id, vacuum_entity_id, name,
            )
            continue

        rooms.append(
            {
                "room_id": room_id,
                "map_id": str(resolved_map_id),
                "name": name,
                "slug": slug,
            }
        )

    # anchor: INCFMPP1  one slug derivation, at ONE admission boundary, unique within
    # its map -- lowest room_id keeps the bare slug, colliding siblings get _r{room_id}
    # RP-015/Q4 clause 1 (admission boundary): slugify_room_name is a pure
    # per-name transform with no cross-room uniqueness guarantee — two
    # same-named rooms would otherwise silently share one slug (dispatch's
    # first-wins slug_to_live_id resolves the SAME live segment for both;
    # reconciliation reports a phantom id_changed for the room that never
    # actually renumbered). Disambiguate deterministically: the LOWEST stable
    # room_id keeps the bare slug; every colliding sibling gets
    # ``{slug}_r{room_id}``, so re-discovery of the same physical rooms always
    # converges on the same suffixed identities.
    # ⚠ RUN TO A FIXPOINT, NOT ONE PASS (R25). A single pass rewrote colliding
    # siblings to ``{slug}_r{room_id}`` WITHOUT CHECKING whether that value was
    # already taken by another room in the same map, so the pass that exists to
    # guarantee uniqueness could itself manufacture a duplicate:
    #
    #     "Kitchen" (id 3), "Kitchen" (id 7), "Kitchen R7" (id 9)
    #       -> kitchen, kitchen_r7, kitchen_r7
    #
    # ``slugify_room_name`` maps "Kitchen R7", "Kitchen r7" and "Kitchen_r7" all to
    # ``kitchen_r7`` (verified, 2026-08-24), so the colliding name does not have to be
    # contrived — a user who has already disambiguated two kitchens BY HAND writes
    # exactly this.
    #
    # That is not a cosmetic duplicate. The anchor above is cited as a system
    # invariant and downstream code is written on its strength: ``_existing_by_slug``
    # in ``room_manager.py`` exists only to cope with a store still holding a
    # PRE-RP-015 duplicate, i.e. it treats post-RP-015 duplicates as impossible. And
    # the slug is not a display string — it is the load-bearing identity key that
    # dispatch resolves first-wins, reconciliation matches on, and the learning
    # baselines key durable per-room data to. Two rooms sharing one means one room's
    # settings and history silently answer for both.
    #
    # Each pass leaves the LOWEST room_id holding the contested slug and pushes every
    # other member one suffix deeper, so the outcome depends only on the SET of
    # (name, room_id) pairs and not on the order the source listed them — preserving
    # the convergence promise above. Distinct ids make the rewritten values distinct
    # within a group, so a pass can only ever be undone by a collision with a
    # different group, which the next pass resolves.
    #
    # BOUNDED, deliberately: a slug-uniqueness pass is not worth a hang (C16), so the
    # loop cannot run away. Falling out of the bound leaves a duplicate rather than
    # spinning, and says so — silence there would re-create exactly the invariant
    # violation this block exists to close.
    for _ in range(len(rooms) + 1):
        by_slug: dict[str, list[dict[str, Any]]] = {}
        for room in rooms:
            by_slug.setdefault(room["slug"], []).append(room)
        colliding = [g for g in by_slug.values() if len(g) > 1]
        if not colliding:
            break
        for group in colliding:
            group.sort(key=lambda r: r["room_id"])
            for room in group[1:]:
                room["slug"] = f"{room['slug']}_r{room['room_id']}"
    else:
        _LOGGER.warning(
            "room slug disambiguation did not converge for %s; duplicate slugs "
            "remain: %s",
            vacuum_entity_id,
            sorted(
                s for s, n in
                ((r["slug"], sum(1 for x in rooms if x["slug"] == r["slug"]))
                 for r in rooms)
                if n > 1
            ),
        )

    return rooms


def discover_rooms_payload(
    hass: HomeAssistant,
    *,
    vacuum_entity_id: str,
    map_id: str | None = None,
) -> dict[str, Any]:
    """Return discovery payload shaped for storage, services, and card use."""
    resolved_map_id = map_id or get_active_map_id(hass, vacuum_entity_id)

    rooms = discover_rooms_for_vacuum(
        hass,
        vacuum_entity_id=vacuum_entity_id,
        map_id=resolved_map_id,
    )

    return {
        "vacuum_entity_id": vacuum_entity_id,
        "active_map_id": resolved_map_id,
        "room_count": len(rooms),
        "rooms": rooms,
    }
