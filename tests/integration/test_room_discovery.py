"""Tests for rooms/room_discovery.py — adapter-config-driven room discovery.

Uses the `manager` fixture (active AdapterCoordinator) + real hass states.

Coverage targets
----------------
[RD-1] get_active_map_id reads the adapter active_map entity; sentinels → None.
[RD-2] get_active_map_id: no declared entity → None.
[RD-3] discover_rooms_for_vacuum normalizes + dedups + skips bad rows.
[RD-3b] RP-015/Q4: colliding slugs disambiguated — lowest room_id keeps the bare slug.
[RD-3c] RP-015/Q4: a three-way collision suffixes every non-lowest room_id.
[RD-3d] RP-015/A1-ID-3: a name that slugifies to empty is refused (not just an empty raw name).
[RD-4] discover_rooms_for_vacuum: incomplete discovery config → [].
[RD-5] discover_rooms_payload wraps the room list with counts.
[RD-6] room_list_entity = concrete entity id sources from that entity, not the vacuum.
[RD-7] attribute mode — active_map DECLARED but the entity never created (scalar)
       + implicit_map_id + segments → implicit id.
[RD-8] scalar shape but no rooms visible → None (no phantom map).
[RD-9] a declared active_map entity that EXISTS (has state) wins; implicit never fires.
[RD-10] a declared active_map entity present with a sentinel value → None (don't fork).
[RD-11] implicit map only applies to the vacuum-attribute source.
[RD-12] end-to-end: scalar/Tuya path imports rooms under the implicit id.
[RD-13] BOOT RACE: active_map declared + REGISTERED but stateless → None (must NOT fork
[RD-14] R25: the disambiguation pass must not MANUFACTURE the duplicate it exists
        to prevent. Rewriting a colliding sibling to `{slug}_r{room_id}` never
        checked whether that value was already taken, and "Kitchen R7" slugifies
        to exactly the value the second "Kitchen" is rewritten to.
[RD-15] R25: the outcome depends on the SET of (name, room_id) pairs, not on the
        order the source listed them -- the anchor promises re-discovery of the
        same physical rooms converges on the same identities.
[RD-ANCHOR-1] MAP-ANCHOR-1/ISSUE #60: an active_map state that matches no map key is
        REFUSED (None), never accepted as an anchor and never substituted.
[RD-ANCHOR-2] ...and a state that DOES match still passes through unchanged.
[RD-ANCHOR-3] ...and when the map set is not enumerable (boot window) no judgement is
        made at all -- the ablation target: an unconditional check breaks every restart.
[RD-ANCHOR-4] ...and a flat_list brand is never validated; it carries no map identity.
[RD-ANCHOR-5] ISSUE #62: a map name with surrounding whitespace is the SAME map. The
        cache strips it; this resolver did not, so a real map matched nothing.
[RD-ANCHOR-6] ...and the canonical form is what comes back, not the raw state.
[RD-ANCHOR-7] ...but normalisation is whitespace ONLY -- case stays significant.
        a phantom map for a novel device whose sensor hasn't materialised yet).
[RD-16] a declaration the map enumerator cannot read makes NO [MAP-ANCHOR-1]
        judgement -- the declaration-shaped twin of [RD-ANCHOR-3]'s boot window.
[RD-17] ISSUE #46: the one cached map must actually carry room-shaped rows.
[RD-18] [RD-SHAPE-3]'s refusing twin -- a single per-map attribute with no usable
        rooms anchors nothing.
[RD-19] the attribute branch's OWN completeness check -- the guard [RD-4] names and
        never reaches.
[RD-20] a non-dict row does not stop the walk (junk rows FIRST, by position).
[RD-21] a row missing its name key is skipped, not admitted as a room named "None";
        the companion `raw_id is None` clause is SUBSUMED, measured.
[RD-22] the C16 fixpoint bound is sufficient for the deepest chain a search found.
[RD-23] an OMITTED room_list_entity no longer switches [MAP-ANCHOR-1] off -- the
        measurement that decided the key should carry its documented default.
[RD-24] ...and discovery still finds the rooms.
[RD-25] ...and the implicit single-map anchor still fires.
[RD-26] but an EMPTY declaration is NOT an omitted one, at all three read sites --
        the input that separates `.get(key, default)` from `value or default`.
"""

from __future__ import annotations

import logging

import pytest

from homeassistant.helpers import entity_registry as er

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.rooms.room_discovery import (
    discover_rooms_for_vacuum,
    discover_rooms_payload,
    get_active_map_id,
)
from custom_components.eufy_vacuum.rooms.source_refresh import set_cached_room_source


_VAC = "vacuum.alfred"


def _discovery_adapter():
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })


def test_active_map_id(hass, manager):
    """[RD-1]"""
    _discovery_adapter()
    hass.states.async_set("sensor.alfred_map", "6")
    assert get_active_map_id(hass, _VAC) == "6"
    hass.states.async_set("sensor.alfred_map", "unavailable")
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_no_entity(hass, manager):
    """[RD-2]"""
    register_adapter_config(_VAC, {"adapter_id": "t", "source": "t", "entities": {}})
    assert get_active_map_id(hass, _VAC) is None


def test_discover_rooms(hass, manager):
    """[RD-3] dedup id 1, skip non-int id, skip name-less."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
        {"id": 1, "name": "Dup"},      # duplicate id → skipped
        {"id": "x", "name": "Bad"},    # non-int id → skipped
        {"id": 3, "name": ""},          # empty name → skipped
    ]})
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    assert [r["room_id"] for r in rooms] == [1, 2]
    assert rooms[0]["slug"] == "kitchen"
    assert rooms[0]["map_id"] == "6"


def test_discover_rooms_disambiguates_colliding_slugs(hass, manager):
    """[RD-3b] RP-015/Q4 clause 1: two same-named rooms get distinct slugs —
    the lowest room_id keeps the bare slug, the sibling gets `{slug}_r{id}`."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 7, "name": "Bathroom"},
        {"id": 3, "name": "Bathroom"},   # deliberately discovered out of id order
    ]})
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    by_id = {r["room_id"]: r["slug"] for r in rooms}
    assert by_id == {3: "bathroom", 7: "bathroom_r7"}


def test_discover_rooms_three_way_collision(hass, manager):
    """[RD-3c] a three-way name collision suffixes every non-lowest room_id."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 5, "name": "Office"},
        {"id": 2, "name": "Office"},
        {"id": 9, "name": "Office"},
    ]})
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    by_id = {r["room_id"]: r["slug"] for r in rooms}
    assert by_id == {2: "office", 5: "office_r5", 9: "office_r9"}


def test_discover_rooms_refuses_empty_slug(hass, manager):
    """[RD-3d] RP-015/A1-ID-3: a name that strips to an empty SLUG (not just an
    empty raw name) is refused — an all-punctuation name like a bare pair of
    quote characters slugifies away to nothing."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 9, "name": '""'},
    ]})
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    assert [r["room_id"] for r in rooms] == [1]


def test_discover_incomplete_config(hass, manager):
    """[RD-4]"""
    register_adapter_config(_VAC, {"adapter_id": "t", "source": "t",
                                   "discovery": {"room_list_entity": "vacuum_entity"}})
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []


def test_discover_payload(hass, manager):
    """[RD-5]"""
    _discovery_adapter()
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    payload = discover_rooms_payload(hass, vacuum_entity_id=_VAC)
    assert payload["room_count"] == 1
    assert payload["active_map_id"] == "6"


def _attribute_mode_adapter(*, implicit="main", room_list_entity="vacuum_entity"):
    """Real scalar/Tuya shape: the adapter DECLARES active_map from its naming
    pattern (every Eufy device does, existence-unchecked), but the scalar
    transport never creates that sensor — so the declared entity is absent from
    BOTH the state machine and the entity registry. Tests using this must NOT
    create or register sensor.alfred_map; that absence is what selects the
    attribute-mode path."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        # DECLARED (like the real adapter) but never created on the scalar transport.
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": room_list_entity,
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
            "implicit_map_id": implicit,
        },
    })


def test_active_map_implicit_attribute_mode(hass, manager):
    """[RD-7] active_map declared but the entity is absent from HA (scalar) +
    implicit_map_id + segments → implicit id. (Regression guard: the adapter
    ALWAYS declares active_map, so 'declared' must not block the fallback.)"""
    _attribute_mode_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    # sensor.alfred_map is intentionally never created → attribute-mode.
    assert get_active_map_id(hass, _VAC) == "main"


def test_active_map_implicit_no_segments(hass, manager):
    """[RD-8] scalar shape but no usable rooms → None (no phantom map)."""
    _attribute_mode_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": []})
    assert get_active_map_id(hass, _VAC) is None
    hass.states.async_set(_VAC, "docked", {})  # attribute entirely absent
    assert get_active_map_id(hass, _VAC) is None
    hass.states.async_set(_VAC, "docked", {"segments": ["junk", 5]})  # no dict rows
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_entity_wins_over_implicit(hass, manager):
    """[RD-9] a present active_map entity (real state) wins; implicit never fires."""
    _attribute_mode_adapter()
    hass.states.async_set("sensor.alfred_map", "6")  # entity EXISTS with a value
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) == "6"


def test_active_map_unavailable_not_implicit(hass, manager):
    """[RD-10] a present active_map entity with a sentinel value → None. It must
    NOT fall back to the implicit id — that would fork a second map for a device
    whose real map is merely offline for a moment."""
    _attribute_mode_adapter()
    hass.states.async_set("sensor.alfred_map", "unavailable")  # exists, sentinel
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_registered_but_stateless_boot_race(hass, manager):
    """[RD-13] active_map declared + REGISTERED in the entity registry but with no
    state yet (novel device, restart window) → None. Must NOT fork a phantom
    'main' map even though segments are already populated — registry presence
    distinguishes this from the scalar transport (which never registers it)."""
    _attribute_mode_adapter()
    # Register sensor.alfred_map WITHOUT setting a state (the boot-race window).
    er.async_get(hass).async_get_or_create(
        "sensor", "eufy_vacuum", "alfred_map_unique",
        suggested_object_id="alfred_map",
    )
    assert hass.states.get("sensor.alfred_map") is None  # registered, no state
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) is None


def test_active_map_implicit_only_for_vacuum_attribute(hass, manager):
    """[RD-11] implicit map only applies to the vacuum-attribute room source."""
    _attribute_mode_adapter(room_list_entity="sensor.alfred_rooms")
    hass.states.async_set("sensor.alfred_rooms", "ok",
                          {"segments": [{"id": 1, "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) is None


def test_discover_attribute_mode_end_to_end(hass, manager):
    """[RD-12] scalar/Tuya path: active_map declared but absent, rooms import
    under the implicit id — the exact scenario behind the 'No active map' block."""
    _attribute_mode_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
    ]})
    map_id = get_active_map_id(hass, _VAC)
    assert map_id == "main"
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id=map_id)
    assert [r["room_id"] for r in rooms] == [1, 2]
    assert rooms[0]["map_id"] == "main"


def test_discover_rooms_from_other_entity(hass, manager):
    """[RD-6] room_list_entity = concrete entity id sources from that entity, not the vacuum."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": "sensor.alfred_rooms",  # concrete id, NOT the "vacuum_entity" sentinel
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })
    # Decoy on the vacuum entity: must NOT be sourced.
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 99, "name": "WrongEntity"}]})
    # Real room list lives on the other entity.
    hass.states.async_set("sensor.alfred_rooms", "ok", {"segments": [
        {"id": 1, "name": "Kitchen"},
        {"id": 2, "name": "Bath"},
    ]})

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")

    ids = [r["room_id"] for r in rooms]
    assert ids == [1, 2]                 # sourced from sensor.alfred_rooms
    assert rooms[0]["name"] == "Kitchen"
    assert 99 not in ids                 # vacuum entity's decoy was NOT used


# ---------------------------------------------------------------------------
# [RD-SHAPE-*] room_list_shape — SHAPE declared independently of SOURCE
#
# Until 2026-08-07 the two were conflated: the attribute source assumed a flat
# list and the service source assumed per-map keying, so the diagonal — a
# per-map MAPPING arriving as a live ATTRIBUTE — was unexpressible. A brand
# shaped that way read as "missing or invalid" and discovered ZERO rooms, with
# every other config block then inert. Found by two independent blind ports.
#
# The fix is a declared shape, deliberately NOT a brand check: an `if brand ==`
# in this path would be core learning a brand's name, which is precisely what
# the adapter boundary exists to prevent.
# ---------------------------------------------------------------------------

def _per_map_adapter():
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "rooms",
            "room_list_shape": "per_map_mapping",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })


def test_rd_shape_1_per_map_attribute_selects_the_active_map(hass, manager):
    """[RD-SHAPE-1] {map_name: [rooms]} on an attribute resolves via active_map."""
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "Downstairs")
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Downstairs": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hall"}],
        "Upstairs":   [{"id": 9, "name": "Loft"}],
    }})
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert [r["room_id"] for r in rooms] == [1, 2], "did not select the active map's rooms"
    assert all(r["room_id"] != 9 for r in rooms), "leaked another map's rooms"


def test_rd_shape_2_flat_list_is_still_the_default(hass, manager):
    """[RD-SHAPE-2] an adapter that declares no shape keeps the old behaviour.

    The backward-compatibility pin: both shipped brands omit room_list_shape,
    so a regression here is a regression for every existing install.
    """
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 4, "name": "Den"}]})
    assert [r["room_id"] for r in discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)] == [4]


def _per_map_adapter_single(implicit="Main"):
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "rooms",
            "room_list_shape": "per_map_mapping",
            "room_id_key": "id",
            "room_name_key": "name",
            "implicit_map_id": implicit,  # opt in to the single-map anchor
        },
    })


def test_rd_shape_3_per_map_single_map_anchors_on_a_blank_selector(hass, manager):
    """[RD-SHAPE-3] a single-map per_map_mapping device whose selector is PRESENT but
    UNAVAILABLE (Dreame's steady state with multi-floor mapping off) anchors on its one
    map key instead of refusing at "no map could be identified". The KEY is the anchor,
    not the declared implicit_map_id, so it survives a rename."""
    _per_map_adapter_single()
    # REGISTER it (not just a bare state): the live single-map selector is a real
    # registered entity reporting 'unavailable', so this must exercise the
    # registered-but-blank path — the blind spot that let a fall-through into the
    # registered-but-stateless wait-branch return None on hardware.
    er.async_get(hass).async_get_or_create(
        "sensor", "eufy_vacuum", "alfred_map_unique", suggested_object_id="alfred_map",
    )
    hass.states.async_set("sensor.alfred_map", "unavailable")  # exists, registered, blank
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Main": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hall"}],
    }})
    assert get_active_map_id(hass, _VAC) == "Main"
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert [r["room_id"] for r in rooms] == [1, 2]


def test_rd_shape_4_per_map_multi_map_with_blank_selector_still_waits(hass, manager):
    """[RD-SHAPE-4] the narrowing: a MULTI-map device with a blank selector must NOT
    anchor a guess — >1 map key means the selector genuinely carried information we no
    longer have, so return None and wait (the per_map analogue of [RD-10])."""
    _per_map_adapter_single()
    er.async_get(hass).async_get_or_create(
        "sensor", "eufy_vacuum", "alfred_map_unique", suggested_object_id="alfred_map",
    )
    hass.states.async_set("sensor.alfred_map", "unavailable")
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Main": [{"id": 1, "name": "Kitchen"}],
        "Upstairs": [{"id": 9, "name": "Loft"}],
    }})
    assert get_active_map_id(hass, _VAC) is None


def test_rd_shape_3_a_mapping_without_the_declaration_still_discovers_nothing(hass, manager):
    """[RD-SHAPE-3] the shape must be DECLARED — it is never sniffed.

    Guessing from the payload's runtime type would make the config a suggestion
    rather than a contract, and would silently change behaviour for any brand
    whose attribute happened to arrive as a dict once.
    """
    _discovery_adapter()   # declares no shape -> flat_list
    hass.states.async_set(_VAC, "docked", {"segments": {
        "Downstairs": [{"id": 1, "name": "Kitchen"}],
    }})
    assert discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []


def test_rd_shape_4_unresolvable_single_map_falls_back_but_a_resolved_miss_does_not(hass, manager):
    """[RD-SHAPE-4] the RP-019/ID-2 guard holds on the attribute path too.

    The selection rule is shared with the service-response source precisely so
    it cannot drift: one map + genuinely unknown active map is served; an
    explicit map id that does not match is NEVER served another map's rooms
    relabelled with the requested id.
    """
    _per_map_adapter()
    # No active_map entity value at all -> resolved id "unknown", single map -> served.
    hass.states.async_set(_VAC, "docked", {"rooms": {"Only": [{"id": 7, "name": "Shed"}]}})
    assert [r["room_id"] for r in discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)] == [7]

    # Two maps and an unresolvable active map -> ambiguous, so nothing is served.
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "A": [{"id": 1, "name": "Kitchen"}], "B": [{"id": 2, "name": "Hall"}],
    }})
    assert discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []

    # A RESOLVED map id that misses is never substituted.
    hass.states.async_set("sensor.alfred_map", "Missing")
    assert discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC) == []


# ---------------------------------------------------------------------------
# [RD-14] - [RD-15] R25: the uniqueness pass must not create a duplicate
# ---------------------------------------------------------------------------


def _rooms_named(hass, names_and_ids):
    """Discover rooms from the vacuum attribute carrying these (name, id) pairs."""
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {
        "segments": [{"id": rid, "name": name} for name, rid in names_and_ids],
    })
    return discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")


async def test_rd14_the_disambiguator_does_not_manufacture_a_duplicate(hass, manager):
    """[RD-14] RED BEFORE THE FIX.

    Two rooms named "Kitchen" (ids 3 and 7) plus one named "Kitchen R7" (id 9).
    `slugify_room_name` maps "Kitchen R7", "Kitchen r7" and "Kitchen_r7" all to
    `kitchen_r7` -- which is exactly what the single-pass disambiguator rewrote the
    id-7 "Kitchen" to. Result: kitchen, kitchen_r7, kitchen_r7.

    The colliding name is not contrived. A user who has already disambiguated two
    kitchens BY HAND writes precisely this.

    Asserted as "all slugs distinct" rather than against a hardcoded expected list:
    the anchor's promise is UNIQUENESS, and pinning one exact spelling would go red
    for a different-but-still-unique scheme, which is not the defect.
    """
    rooms = _rooms_named(hass, [("Kitchen", 3), ("Kitchen", 7), ("Kitchen R7", 9)])

    slugs = [r["slug"] for r in rooms]
    assert len(slugs) == 3
    assert len(set(slugs)) == 3, f"the uniqueness pass produced a duplicate: {slugs}"
    # the lowest id keeps the bare slug -- the documented, convergent half
    assert next(r["slug"] for r in rooms if r["room_id"] == 3) == "kitchen"


async def test_rd15_disambiguation_is_order_independent(hass, manager):
    """[RD-15] RED IF THE FIXPOINT IS MADE ORDER-DEPENDENT.

    The anchor promises "re-discovery of the same physical rooms always converges on
    the same suffixed identities". A source that lists the same rooms in a different
    order on the next poll must not re-key them -- the slug is what reconciliation
    matches on and what the learning baselines hang durable per-room data from, so a
    reshuffle would orphan settings and history.

    A fixpoint loop is where this is easy to lose: resolving collisions in iteration
    order rather than by a property of the rooms themselves would pass [RD-14] and
    silently fail here.
    """
    forward = _rooms_named(
        hass, [("Kitchen", 3), ("Kitchen", 7), ("Kitchen R7", 9)]
    )
    reverse = _rooms_named(
        hass, [("Kitchen R7", 9), ("Kitchen", 7), ("Kitchen", 3)]
    )

    by_id_forward = {r["room_id"]: r["slug"] for r in forward}
    by_id_reverse = {r["room_id"]: r["slug"] for r in reverse}

    assert by_id_forward == by_id_reverse, (
        f"slug assignment depends on source order: {by_id_forward} vs {by_id_reverse}"
    )


# ---------------------------------------------------------------------------
# [RD-ANCHOR-*] MAP-ANCHOR-1 / ISSUE #60 — the active_map entity's state is only
# a map id if it looks like one.
#
# The reporter's vacuum was `vacuum.apartment_doomba_iii_doomba_iii` while every
# sibling entity was `doomba_iii_*`, so each derived id missed. He overrode
# active_map onto `camera.doomba_iii_map` — the entity called "map" — and that
# camera's state is the map's LAST-UPDATED TIMESTAMP. The resolver returned
# "2026-10-02 11:04:35" as a map id, it matched nothing, and import refused.
#
# The guard DECLINES; it never substitutes. Substituting the single map when the
# lookup misses is the RP-019/ID-2 failure 17-room-identity.md forbids.
# ---------------------------------------------------------------------------

def test_rd_anchor_1_value_that_is_not_a_map_id_is_refused(hass, manager):
    """[RD-ANCHOR-1] THE RED INPUT. A per-map vacuum whose active_map entity reports a
    value absent from its map keys resolves to None, not to that value.

    Before MAP-ANCHOR-1 this returned the timestamp verbatim and it travelled on into
    diagnostics as `active_map_id`."""
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "2026-10-02 11:04:35")  # a camera's state
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "1": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hall"}],
    }})
    assert get_active_map_id(hass, _VAC) is None, (
        "a value that matches no map key was accepted as a map anchor"
    )


def test_rd_anchor_2_a_real_map_id_still_passes_through(hass, manager):
    """[RD-ANCHOR-2] The no-op pin. Every install whose selector already reports a real
    map key must behave EXACTLY as before — this guard is subtractive only."""
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "Upstairs")
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Downstairs": [{"id": 1, "name": "Kitchen"}],
        "Upstairs":   [{"id": 9, "name": "Loft"}],
    }})
    assert get_active_map_id(hass, _VAC) == "Upstairs"
    assert [r["room_id"] for r in discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)] == [9]


def test_rd_anchor_3_unknowable_map_set_must_not_reject(hass, manager):
    """[RD-ANCHOR-3] THE ABLATION TARGET, and the reason the guard is conditional.

    Per-map shape, but the room attribute has not landed yet — the boot window. The map
    set is not enumerable, so NO judgement is possible and the entity must be trusted.
    Drop the `known is not None` condition and this goes red: a valid map id would be
    refused on every restart, which is a far worse failure than the one being fixed."""
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "Downstairs")
    hass.states.async_set(_VAC, "docked", {})           # attribute absent entirely
    assert get_active_map_id(hass, _VAC) == "Downstairs"
    hass.states.async_set(_VAC, "docked", {"rooms": {}})  # present but empty
    assert get_active_map_id(hass, _VAC) == "Downstairs"


def test_rd_anchor_5_the_warning_fires_once_not_every_resolution(hass, manager, caplog):
    """[RD-ANCHOR-5] this resolver runs on a ~60s timer, so an unthrottled warning is
    ~1440 identical lines a day per vacuum — a log that repeats that hard is a log
    nobody reads, which costs the diagnostic the warning exists to provide.

    THE KEY IS THE ROLE, NOT THE VALUE, and this test pins that: the value here is a
    CHANGING timestamp, exactly like the camera state in ISSUE #60. Key on (role, value)
    and the set grows without bound AND warns on nearly every pass."""
    from custom_components.eufy_vacuum.rooms.room_discovery import (
        _MISBOUND_ACTIVE_MAP_WARNED,
    )
    _MISBOUND_ACTIVE_MAP_WARNED.clear()
    _per_map_adapter()
    hass.states.async_set(_VAC, "docked", {"rooms": {"1": [{"id": 1, "name": "Kitchen"}]}})

    caplog.clear()
    for tick in range(5):
        # A DIFFERENT bad value each pass — the camera's timestamp moves.
        hass.states.async_set("sensor.alfred_map", f"2026-10-02 11:04:3{tick}")
        assert get_active_map_id(hass, _VAC) is None

    warnings = [r for r in caplog.records if r.levelname == "WARNING"
                and "not one of" in r.getMessage()]
    assert len(warnings) == 1, f"warned {len(warnings)} times across 5 resolutions"
    assert len(_MISBOUND_ACTIVE_MAP_WARNED) == 1, "the warned set grew per value"


def test_rd_anchor_6_a_clean_resolution_rearms_the_warning(hass, manager, caplog):
    """[RD-ANCHOR-6] a warn-once latch that never clears is the shape that silently
    stops reporting real recurrences. Fix the binding, break it again, and the user
    must be told again."""
    from custom_components.eufy_vacuum.rooms.room_discovery import (
        _MISBOUND_ACTIVE_MAP_WARNED,
    )
    _MISBOUND_ACTIVE_MAP_WARNED.clear()
    _per_map_adapter()
    hass.states.async_set(_VAC, "docked", {"rooms": {"1": [{"id": 1, "name": "Kitchen"}]}})

    def _bad_then_count():
        caplog.clear()
        hass.states.async_set("sensor.alfred_map", "2026-10-02 11:04:35")
        assert get_active_map_id(hass, _VAC) is None
        return len([r for r in caplog.records if r.levelname == "WARNING"
                    and "not one of" in r.getMessage()])

    assert _bad_then_count() == 1, "first breakage must warn"

    # The user fixes the binding — a clean resolution must disarm the latch.
    hass.states.async_set("sensor.alfred_map", "1")
    assert get_active_map_id(hass, _VAC) == "1"
    assert not _MISBOUND_ACTIVE_MAP_WARNED, "a good resolution did not clear the latch"

    assert _bad_then_count() == 1, "a RECURRENCE after a good resolution went unreported"


def test_rd_anchor_4_flat_list_brand_is_never_validated(hass, manager):
    """[RD-ANCHOR-4] Backward-compatibility pin for both shipped brands. A flat_list
    room source carries no map identity at all, so there is nothing to validate against
    and the value passes through untouched — however odd it looks."""
    _discovery_adapter()  # no room_list_shape → flat_list
    hass.states.async_set("sensor.alfred_map", "2026-10-02 11:04:35")
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 4, "name": "Den"}]})
    assert get_active_map_id(hass, _VAC) == "2026-10-02 11:04:35"


def test_rd_anchor_5_trailing_whitespace_is_the_same_map(hass, manager):
    """[RD-ANCHOR-5] ISSUE #62, from a real German install.

    `rooms/source_refresh.py` strips a map name before using it as the cache key. This
    resolver compared the SELECTOR'S RAW STATE against those stripped keys, so a map
    named "Obergeschoss " was cached under "Obergeschoss", looked up as "Obergeschoss ",
    matched nothing, and MAP-ANCHOR-1 then refused it as "not a map id" -- telling the
    owner his correctly-bound role pointed at the wrong entity. He could never import
    that map, and nothing about his configuration was wrong.
    """
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "Obergeschoss ")   # the selector's value
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Erdgeschoss":  [{"id": 1, "name": "Wohnzimmer"}],
        "Obergeschoss": [{"id": 9, "name": "Schlafzimmer"}],      # the cached key
    }})
    assert get_active_map_id(hass, _VAC) == "Obergeschoss", (
        "a map whose only difference is invisible whitespace was refused"
    )
    assert [r["room_id"] for r in discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)] == [9]


def test_rd_anchor_6_the_canonical_form_is_returned(hass, manager):
    """[RD-ANCHOR-6] Matching on the normalised value and returning the raw one would
    move the failure rather than fix it -- every downstream lookup is keyed on the
    stripped name."""
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "  Upstairs  ")
    hass.states.async_set(_VAC, "docked", {"rooms": {"Upstairs": [{"id": 3, "name": "Loft"}]}})
    assert get_active_map_id(hass, _VAC) == "Upstairs"


def test_rd_anchor_7_case_is_still_significant(hass, manager):
    """[RD-ANCHOR-7] The limit of the normalisation, pinned so it cannot quietly widen.
    "junk map" and "Junk map" may be two deliberate maps; a vendor app that allows both
    allows the distinction. Only the difference a user cannot SEE is normalised away."""
    _per_map_adapter()
    hass.states.async_set("sensor.alfred_map", "upstairs")
    hass.states.async_set(_VAC, "docked", {"rooms": {"Upstairs": [{"id": 3, "name": "Loft"}]}})
    assert get_active_map_id(hass, _VAC) is None, (
        "case-folding would merge two maps a user deliberately named differently"
    )


# ---------------------------------------------------------------------------
# [RD-16] - [RD-22]  the gaps a coverage run named and the test NAMES did not.
#
# [RD-4] IS CALLED "incomplete discovery config -> []" AND NEVER REACHES THE GUARD
# IT NAMES. Its adapter omits room_id_key/room_name_key, so discover_rooms_for_vacuum
# returns at the FIRST incompleteness check -- the one BOTH sources share -- and the
# attribute branch's own check below it never executes. Measured, not inferred: that
# line stayed in coverage's missing set with [RD-4] green, which is the one shape
# `scripts/check_covers.py` exists to catch. [RD-19] is the test [RD-4] reads like.
#
# NO `covers` MARKERS HERE, AND THE REASON IS WORTH KNOWING: that gate's SPAN check
# is per SYMBOL -- the tests declaring a target must together leave no line of it
# uncovered -- so a marker only says something true about a symbol small enough for
# its declaring tests to cover whole. Every guard below sits inside a function far
# larger than the one branch its test drives, and `discover_rooms_for_vacuum` holds a
# permanently unreachable line ([RD-22]'s else-arm), so a marker on it could never go
# green. Declaring one anyway was tried and the gate refused it, correctly. What
# proves reach for these is the pair of instruments that caught [RD-4]: the
# before/after coverage diff, and an ablation per clause.
# ---------------------------------------------------------------------------


def _per_map_adapter_with(**discovery):
    """`_per_map_adapter` with discovery keys replaced, or REMOVED by passing None.

    Removal and empty-string are different inputs here and the distinction is
    load-bearing -- see [RD-19].
    """
    base = {
        "room_list_entity": "vacuum_entity",
        "room_list_attribute": "rooms",
        "room_list_shape": "per_map_mapping",
        "room_id_key": "id",
        "room_name_key": "name",
    }
    base.update(discovery)
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {k: v for k, v in base.items() if v is not None},
    })


_NOT_A_MAP_ID = "2026-10-02 11:04:35"   # the ISSUE #60 camera state, verbatim


@pytest.mark.parametrize("override,shape", [
    pytest.param({"room_list_attribute": None},
                 "no attribute is NAMED, so there is nothing to read",
                 id="no_attribute"),
    pytest.param({"room_list_entity": "sensor.alfred_rooms"},
                 "the rooms live on ANOTHER entity, whose attributes this "
                 "enumerator never reads",
                 id="another_entity"),
])
def test_rd16_a_declaration_it_cannot_enumerate_makes_no_map_judgement(
    hass, manager, override, shape
):
    """[RD-16] [MAP-ANCHOR-1] is conditional on being able to ENUMERATE the maps, and
    [RD-ANCHOR-3] pins only one way of failing to: the boot window, where the attribute
    has not landed yet. These are the other two -- the DECLARATION itself gives the
    enumerator nothing to read, on a config that is otherwise perfectly valid.

    Both rows reach the same `return None`, and the consequence is the one
    [RD-ANCHOR-3] argues for: `known is None` means no judgement is possible, so the
    selector's value is TRUSTED rather than refused. The assertion is therefore the
    INVERSE of [RD-ANCHOR-1] on a byte-identical bad value -- the ISSUE #60 camera
    timestamp comes back out.

    THE CONTROL IS THE WHOLE TEST. "returns the state unchanged" is also what a
    resolver with no guard at all does, and this value is the exact string the guard
    was written for, so the properly-declared adapter is run against the SAME state
    and must refuse it. Without that half this passes against a deleted
    [MAP-ANCHOR-1].

    ONLY THE `another_entity` ROW HAS A RED INPUT, and that is measured rather than
    assumed. Delete the whole guard and that row reddens: the enumerator reads the
    VACUUM's `rooms` attribute, gets a real map set, and refuses the timestamp. The
    `not attr` clause is SUBSUMED -- ablated on its own it reddens nothing, because
    `state.attributes.get(None)` yields None, the key set comes out empty, and
    `return keys or None` already answers None by the longer road. The row stays
    because it is a real declaration shape and because its subsumption is only
    checkable while something drives it.

    RED: delete the guard and the `another_entity` row is refused instead of trusted
    -- the every-restart regression [RD-ANCHOR-3] names, arriving through a
    declaration rather than a race.
    """
    _per_map_adapter_with(**override)
    hass.states.async_set("sensor.alfred_map", _NOT_A_MAP_ID)
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Downstairs": [{"id": 1, "name": "Kitchen"}],
    }})

    assert get_active_map_id(hass, _VAC) == _NOT_A_MAP_ID, (
        f"the map set is not enumerable ({shape}) so no judgement is possible"
    )

    # CONTROL: same hass, same states, same bad value -- only the declaration differs.
    _per_map_adapter()
    assert get_active_map_id(hass, _VAC) is None, (
        "control: with a readable declaration [MAP-ANCHOR-1] must still refuse this"
    )


def _service_response_adapter():
    """The ISSUE #46 shape: a service-response brand with NO active_map declared.

    HA 2026.7 (home-assistant/core#173282) stopped creating the map-selector entity on
    some devices, so there is no entity to read and the anchor has to come from the
    cached room source itself.
    """
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {},
        "discovery": {
            "source": "service_response",
            "room_id_key": "segment_id",
            "room_name_key": "name",
        },
    })


@pytest.mark.parametrize("segments,shape", [
    pytest.param([], "empty -- the docstring's own case: an empty list anchors "
                     "nothing", id="empty_list"),
    pytest.param(["Kitchen", 7], "a list carrying no room-shaped row",
                 id="no_dict_rows"),
    pytest.param("corrupt", "not a list at all", id="string"),
    pytest.param({"segment_id": "16"}, "a bare dict where a list of them belongs",
                 id="bare_dict"),
    pytest.param(7, "not even iterable", id="not_iterable"),
])
def test_rd17_the_one_cached_map_must_actually_carry_rooms(
    hass, manager, segments, shape
):
    """[RD-17] ISSUE #46's anchor is narrow on purpose, and this is the third of its
    three narrowings -- "the map must actually carry rooms".

    The cost of getting this wrong is named in the source and in
    17-room-identity.md: serving one map's rooms under another map's id (RP-019/ID-2).
    Anchoring on a map whose room list is junk invents a map id from nothing, and
    every downstream key -- the room cache, managed_rooms_by_map, the per-map camera
    slug -- is then hung off it.

    BOTH CLAUSES OF THE GUARD ARE DRIVEN, and the `not_iterable` row is here because
    without it one of them is subsumed. `any(isinstance(row, dict) for row in
    segments)` happily walks a string's characters and a dict's keys, finds no dict,
    and refuses on its own -- so the `isinstance(segments, list)` clause changes
    nothing for the string or the bare dict. A bare `7` is what makes it bite: without
    the isinstance clause, `for row in 7` raises TypeError out of a resolver whose
    whole contract is to refuse one bad value without raising.

    The empty list is not a contrived input: the service flattener writes a map key
    with no rooms whenever a response enumerates a floor it returned no segments for.

    RED: drop the clause and the junk map's KEY is returned as this vacuum's active
    map id.
    """
    _service_response_adapter()
    set_cached_room_source(hass, _VAC, {"Main": segments})

    assert get_active_map_id(hass, _VAC) is None, (
        f"a single cached map whose segments are {shape} was accepted as an anchor"
    )

    # CONTROL: the same single-map cache, one real room -- the ISSUE #46 fix itself.
    set_cached_room_source(hass, _VAC, {"Main": [{"segment_id": "16", "name": "Kitchen"}]})
    assert get_active_map_id(hass, _VAC) == "Main", (
        "control: with one usable room the single-map anchor must still resolve, or "
        "this test passes against a helper that answers None for everything"
    )


@pytest.mark.parametrize("segments,shape", [
    pytest.param([], "the one map's room list is empty", id="empty_list"),
    pytest.param(["Loft", 3], "the one map's rows are not room-shaped",
                 id="no_dict_rows"),
    pytest.param("corrupt", "the one map's value is not a list", id="string"),
    pytest.param(7, "the one map's value is not even iterable", id="not_iterable"),
])
def test_rd18_a_single_per_map_attribute_with_no_usable_rooms_anchors_nothing(
    hass, manager, segments, shape
):
    """[RD-18] [RD-SHAPE-3]'s refusing twin. A per-map-mapping device (Dreame) with its
    selector unavailable -- the steady state with multi-floor mapping off -- anchors on
    its one map's KEY, but only when that map has rooms.

    This is the arm where exactly ONE map is present and its room list is unusable, so
    neither the single-map anchor nor the flat-list fallback below it may fire. A
    phantom map here is worse than no map: import would succeed under an id whose
    rooms do not exist, and the user's real map would later arrive as a SECOND one.

    [RD-8] covers the flat_list shape's version of this refusal; the per-map arm had
    never been driven -- a coverage run named it after [RD-SHAPE-3] had been green for
    months.

    The `not_iterable` row carries the `isinstance(seg, list)` clause, which the other
    three cannot: `any(isinstance(r, dict) for r in seg)` walks a string's characters
    and refuses by itself, so only a non-iterable distinguishes the two clauses. Same
    shoulder as [RD-17].

    RED: drop the `isinstance(seg, list) and any(... dict ...)` test and the junk map's
    key is returned as the anchor.
    """
    _per_map_adapter_with(implicit_map_id="Main")
    # REGISTERED and present-but-blank: Dreame's real steady state, and the path that
    # reaches the single-map fallback directly rather than through the never-created
    # branch ([RD-SHAPE-3]).
    er.async_get(hass).async_get_or_create(
        "sensor", "test", "alfred_map_unique", suggested_object_id="alfred_map",
    )
    hass.states.async_set("sensor.alfred_map", "unavailable")
    hass.states.async_set(_VAC, "docked", {"rooms": {"Loft": segments}})

    assert get_active_map_id(hass, _VAC) is None, (
        f"a phantom map was anchored although {shape}"
    )

    # CONTROL: one map, one real room -> its KEY (not the declared implicit id).
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Loft": [{"id": 9, "name": "Study"}],
    }})
    assert get_active_map_id(hass, _VAC) == "Loft", (
        "control: the single-map anchor must still fire for a usable room list"
    )


@pytest.mark.parametrize("override,missing", [
    pytest.param({"room_list_attribute": None},
                 "room_list_attribute is not declared at all", id="no_attribute"),
    pytest.param({"room_list_entity": ""},
                 "room_list_entity is declared EMPTY", id="empty_entity"),
])
def test_rd19_the_attribute_branch_reports_an_incomplete_config_as_one(
    hass, manager, caplog, override, missing
):
    """[RD-19] The guard [RD-4] is named after and never reaches.

    `discover_rooms_for_vacuum` checks completeness TWICE and the two checks are not
    the same check. The first is shared by both sources and asks for room_id_key /
    room_name_key. The second belongs to the attribute branch alone and asks for
    room_list_entity / room_list_attribute, which the service branch never reads at
    all. [RD-4] omits the SHARED keys, so it returns at the first check with the
    second still unexecuted -- green, and naming a line coverage reported missing.

    THE CONTROL IS THE PROOF OF PATH, and it is why the shared keys are declared in
    every row here: if the first check could still be what answers, the control -- same
    adapter, both room_list_ keys present, identical attribute payload -- would return
    [] as well. It returns the room, so the shared check is passed and the branch's own
    check is what refuses.

    THE ASSERTION IS ON THE DIAGNOSIS, NOT THE RETURN VALUE, because the return value
    cannot distinguish this guard from its absence. Ablated, an adapter naming no
    attribute reads `state.attributes.get(None)`, gets None, and falls out at
    "missing or invalid"; one with an empty entity key looks up the entity `""`, gets
    no state, and falls out at "missing for". Both answer `[]` by a longer road, so an
    assertion on `== []` alone is SUBSUMED and would pass with the guard deleted --
    measured, not assumed. What the guard actually buys is the right diagnosis: the
    user is told their CONFIG is incomplete rather than that a device attribute is
    missing, which is the difference between editing an adapter and chasing a device.

    NEITHER ROW IS THE ABSENT-`room_list_entity` CASE, deliberately. The schema
    documents that key as "Default: 'vacuum_entity'" while this function reads it with
    no default, so an adapter that omits it discovers zero rooms. Which of the two is
    right is an open question and not one a test should settle in passing, so these
    rows use an EMPTY declaration and an absent ATTRIBUTE -- incomplete under either
    reading.

    RED: delete the branch's own check and the log says the attribute is missing or
    invalid, which is a report about the device for a fault in the declaration.
    """
    _per_map_adapter_with(room_list_shape=None, **override)
    hass.states.async_set(_VAC, "docked", {"rooms": [{"id": 1, "name": "Kitchen"}]})

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="custom_components.eufy_vacuum.rooms.room_discovery"):
        assert discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6") == [], (
            f"discovery proceeded although {missing}"
        )

    messages = [r.getMessage() for r in caplog.records]
    # The full prefix, not "discovery config incomplete": the SHARED check one guard
    # up logs "Discovery config incomplete for ..." and a substring that matched both
    # would let [RD-4]'s path satisfy this assertion.
    assert any("Attribute discovery config incomplete" in m for m in messages), (
        f"the config fault was not reported as one -- logged instead: {messages}"
    )
    assert not any("missing or invalid" in m or "missing for" in m for m in messages), (
        "the fault was reported against the DEVICE rather than the declaration: "
        f"{messages}"
    )

    # CONTROL: both keys declared, same payload -- so the SHARED check is not what
    # answered above.
    _per_map_adapter_with(room_list_shape=None)
    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    assert [r["room_id"] for r in rooms] == [1], (
        "control: a complete attribute declaration must discover the room, or the "
        "first completeness check is what refused and this names the wrong guard"
    )


def _discover_segments(hass, rows):
    """Discover from a RAW segment list -- rows exactly as given.

    `_rooms_named` builds well-formed `{"id": ..., "name": ...}` dicts from (name, id)
    pairs, which cannot express a row that is not a dict or is missing a key.
    """
    _discovery_adapter()
    hass.states.async_set(_VAC, "docked", {"segments": rows})
    return discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")


def test_rd20_a_row_that_is_not_a_dict_does_not_stop_the_walk(hass, manager):
    """[RD-20] The room list arrives from the device, so its ROWS are outside data even
    when the list itself is well-formed.

    THE JUNK ROWS COME FIRST ON PURPOSE. `continue` and `break` are indistinguishable
    when the bad row is last; with the real room AFTER them, the discovered room is
    what proves the walk resumed rather than quietly stopped -- the same positional
    reasoning as [LS-23] and [PC-4].

    There is no `try` around this walk, so without the guard `"not a dict".get(...)`
    raises AttributeError straight out of `discover_rooms_for_vacuum`. The cost is
    therefore not one lost room: the caller gets an exception instead of a room list,
    so one malformed row in a payload costs the whole discovery.

    RED: delete the guard and this raises AttributeError on the first row.
    """
    rooms = _discover_segments(hass, [
        "not a dict",
        None,
        7,
        ["nested", "list"],
        {"id": 4, "name": "Pantry"},
    ])

    assert [r["room_id"] for r in rooms] == [4], (
        f"the row after four junk rows was not discovered -- got {rooms}"
    )


def test_rd21_a_row_missing_its_name_is_skipped_not_named_none(hass, manager):
    """[RD-21] A row whose declared name key is ABSENT -- not empty, absent.

    [RD-3] covers an empty name (`""`) and a non-integer id. Neither reaches this
    guard, because an absent key yields None rather than a falsy string, and None is
    tested one guard EARLIER.

    ONLY ONE HALF OF THIS COMPOUND GUARD CAN BE MADE RED, and that is the finding
    rather than the coverage:

      * `raw_name is None` is LOAD-BEARING. Delete it and the row is admitted with
        `name = str(None).strip()` -- a room literally called "None", slug `none`,
        which then becomes a stable identity key that reconciliation matches on and
        the learning baselines hang durable per-room data from.
      * `raw_id is None` is SUBSUMED, red set deliberately EMPTY. `int(None)` raises
        TypeError four lines below, inside the `except (TypeError, ValueError):
        continue` that the non-integer id case already needs, so the row is skipped by
        the same route and nothing distinguishes the code with that clause from the
        code without it. Measured by ablation, not argued.

    Both rows are still driven, because both are real device payloads and the id row is
    what makes the subsumption claim checkable.

    RED: delete `raw_name is None` and the first row arrives as a room named "None".
    """
    rooms = _discover_segments(hass, [
        {"name": "No Id Key"},            # the SUBSUMED half
        {"id": 11},                       # the LOAD-BEARING half
        {"id": 12, "name": "Study"},
    ])

    assert [r["room_id"] for r in rooms] == [12], f"got {rooms}"
    assert [r["name"] for r in rooms] == ["Study"], (
        "a row with no name key was admitted as a room -- check whether it is called "
        "'None'"
    )


def test_rd22_the_fixpoint_bound_is_sufficient_for_the_deepest_chain(
    hass, manager, caplog
):
    """[RD-22] The C16 bound on the uniqueness pass, measured rather than asserted.

    The loop runs `len(rooms) + 1` passes and takes a `for ... else` on non-convergence
    that WARNS and leaves duplicate slugs in place. Coverage says that else-arm has
    never executed, and the question a search answered is whether it can: over 608,093
    simulated (slug, room_id) configurations -- suffix-chain alphabets with distinct
    ids, and again with duplicate ids -- nothing exhausted the bound. The worst case
    needs exactly N passes for N rooms, so the bound has exactly ONE pass of slack.
    Not generous: sufficient.

    This is that worst case, four rooms deep, and it is a real input rather than a
    constructed one -- it is [RD-14]'s hand-disambiguated "Kitchen R7" user, one floor
    further on. `slugify_room_name` folds "Attic R2" and "Attic R2 R3" onto exactly the
    values passes one and two produce (verified: 'Attic R2' -> 'attic_r2',
    'Attic R2 R3' -> 'attic_r2_r3'), so each pass's output lands on the next room's
    slug and the collision walks one level deeper per pass.

    [RD-14] is depth three and converges in two rewriting passes, so it stays green on
    a bound of two. This is the shallowest input that does not.

    THE WARNING ASSERTION IS THE POINT, not the uniqueness one: unique slugs are also
    what a loop that converged by luck produces. "Did not converge" not being logged is
    what says the fixpoint was REACHED inside the bound, and it is what makes a
    shrunken bound red even where the slugs happen to come out distinct.

    RED: `range(len(rooms) + 1)` -> `range(2)` and this is the only test in the suite
    that reddens -- with a duplicate slug AND the non-convergence warning, which is
    the else-arm's only route to being executed at all.
    """
    caplog.clear()
    rooms = _rooms_named(hass, [
        ("Attic", 1), ("Attic", 2), ("Attic R2", 3), ("Attic R2 R3", 4),
    ])

    slugs = [r["slug"] for r in rooms]
    assert len(slugs) == 4, f"a room was dropped before disambiguation: {rooms}"
    assert len(set(slugs)) == 4, f"the uniqueness pass left a duplicate: {slugs}"
    assert next(r["slug"] for r in rooms if r["room_id"] == 1) == "attic", (
        "the lowest room_id must keep the bare slug -- the convergence promise"
    )
    assert not [
        r for r in caplog.records
        if r.levelname == "WARNING" and "did not converge" in r.getMessage()
    ], "the bound was exhausted on the deepest chain a search could find"


# ---------------------------------------------------------------------------
# NOT TESTED -- `room_discovery.py::discover_rooms_for_vacuum`'s non-convergence
# `else:` arm (the "did not converge" warning under the uniqueness pass).
#
# UNREACHABLE. Each pass resolves exactly one level of collision depth, and the
# deepest chain N rooms can form is N - 1 levels, so N passes always suffice while the
# bound is N + 1. Searched rather than argued: 608,093 configurations over two shapes
# -- distinct room_ids with suffix-chain slug alphabets (exhaustive for N <= 4, two
# bases, sampled to N = 8) and duplicate room_ids (the `seen_room_ids` dedup normally
# makes those impossible, so its removal is the other shape) -- and the worst observed
# was N passes of an N + 1 bound. [RD-22] pins the input that gets closest, so the one
# pass of remaining slack cannot be spent silently.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# [RD-23] - [RD-26]  room_list_entity now carries the default the schema always
# documented, and these are the inputs that make that claim able to go red.
#
# THE CHANGE REDDENED NOTHING IN 5663 TESTS, which is exactly why these exist: a
# behaviour change no test can see is a behaviour change with no test. The schema has
# documented `Default: 'vacuum_entity'` since the key was added; of the four readers,
# only `onboarding/manager.py` applied it, and that reader sits in a method with no
# production callers -- so the documented contract was honoured in zero live paths
# while three live readers in room_discovery.py refused instead.
#
# WHAT DECIDED THE DIRECTION was not statement-counting. At `_known_map_ids` an absent
# key does not decline an action: it makes the map set unenumerable, which switches the
# [MAP-ANCHOR-1] / ISSUE #60 guard OFF. [RD-23] is that measurement, run with a
# positive control before the fix and kept as the regression.
#
# `absent` AND `empty` ARE DIFFERENT INPUTS throughout, and the resolver uses
# `.get(key, default)` rather than `value or default` for that reason alone. See
# [RD-26]; `RD-19[empty_entity]` is the pre-existing row that separates the two forms
# at the third read site.
# ---------------------------------------------------------------------------


def _per_map_no_entity(**extra):
    """A per-map attribute adapter that declares everything EXCEPT room_list_entity.

    The realistic shape for a fourth-brand port: the schema marks the key
    `required: False` and documents its default, so a porter reasonably omits it.
    """
    discovery = {
        "room_list_attribute": "rooms",
        "room_list_shape": "per_map_mapping",
        "room_id_key": "id",
        "room_name_key": "name",
    }
    discovery.update(extra)
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": discovery,
    })


def test_rd23_an_omitted_room_list_entity_does_not_switch_off_the_map_anchor(
    hass, manager
):
    """[RD-23] THE FACT THAT DECIDED THE DEFAULT, kept as the regression.

    Before 2026-11-08, omitting `room_list_entity` from an otherwise valid per-map
    declaration made `_known_map_ids` refuse to enumerate, `known` came back None, and
    [MAP-ANCHOR-1] skipped its check entirely -- so ISSUE #60's camera timestamp was
    accepted as this vacuum's active map id. Measured both ways at the time, with the
    key absent returning `'2026-10-02 11:04:35'` and the key present returning None.

    That is the difference between an absent declaration DECLINING an action and an
    absent declaration DISABLING A GUARD. A missing room list is a diagnosis problem; a
    guard that quietly stops running is the hole the guard was added to close, and no
    amount of documenting the refusal would have made it safe.

    BOTH ARMS, SAME STATES, ONLY THE DECLARATION DIFFERS -- and they must now agree.
    Asserting only the absent arm would pass against a resolver that refused
    everything, which is why the declared arm is here and why the control below uses a
    REAL map key: a guard that refuses every value is not the guard being tested.

    RED: restore `discovery.get("room_list_entity")` in `declared_room_list_entity` and
    the absent arm returns the timestamp while the declared arm returns None.
    """
    hass.states.async_set("sensor.alfred_map", _NOT_A_MAP_ID)
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Downstairs": [{"id": 1, "name": "Kitchen"}],
        "Upstairs": [{"id": 9, "name": "Loft"}],
    }})

    _per_map_no_entity()
    assert get_active_map_id(hass, _VAC) is None, (
        "omitting room_list_entity switched [MAP-ANCHOR-1] off: a camera's timestamp "
        "was accepted as this vacuum's active map id"
    )

    _per_map_adapter()      # the same config, with the key declared
    assert get_active_map_id(hass, _VAC) is None, (
        "control: the declared arm must refuse it too, or the two readings do not agree"
    )

    # CONTROL: a REAL map key must still resolve on both arms, or the assertions above
    # are satisfied by a resolver that refuses everything.
    hass.states.async_set("sensor.alfred_map", "Upstairs")
    _per_map_no_entity()
    assert get_active_map_id(hass, _VAC) == "Upstairs", (
        "a real map key must resolve with the key omitted"
    )
    _per_map_adapter()
    assert get_active_map_id(hass, _VAC) == "Upstairs"


def test_rd24_an_omitted_room_list_entity_still_discovers_rooms(hass, manager):
    """[RD-24] The third read site: discovery itself.

    `discover_rooms_for_vacuum`'s attribute branch used to read the key with no default
    and fold it into `not all((entity_key, attribute))`, so an adapter that declared
    its attribute and omitted its entity discovered ZERO rooms and logged that its
    CONFIG was incomplete -- for a config the schema calls complete.

    The room list is the whole point of the block, so this is the site whose absence a
    porter would notice; it is also the one that cost nothing but function, which is why
    [RD-23] rather than this one decided the direction.

    RED: restore the no-default read and this returns [].
    """
    _per_map_no_entity(room_list_shape=None)     # flat_list: the Eufy/Tuya shape
    hass.states.async_set(_VAC, "docked", {"rooms": [
        {"id": 4, "name": "Pantry"},
        {"id": 5, "name": "Porch"},
    ]})

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC, map_id="6")
    assert [r["room_id"] for r in rooms] == [4, 5], (
        f"an omitted room_list_entity discovered nothing -- got {rooms}"
    )
    assert [r["slug"] for r in rooms] == ["pantry", "porch"]


def test_rd25_an_omitted_room_list_entity_still_anchors_the_implicit_map(hass, manager):
    """[RD-25] The second read site: the implicit single-map anchor.

    `_implicit_attribute_map_id` refuses unless the room list is on the vacuum entity,
    because it reads `hass.states.get(vacuum_entity_id)` directly -- that refusal is
    correct and deliberate for a declaration naming ANOTHER entity, and it stays. What
    was wrong was treating an ABSENT declaration as if it named another entity.

    Note `implicit_map_id` and `room_list_attribute` are still required here and still
    short-circuit first, so this arm is only reachable for an adapter that declares
    both and omits the entity.

    RED: restore the no-default read and this returns None.
    """
    _per_map_no_entity(implicit_map_id="Main")
    # No sensor.alfred_map in the state machine or the registry -> the never-created
    # branch, which is the ladder that reaches this helper.
    hass.states.async_set(_VAC, "docked", {"rooms": {
        "Loft": [{"id": 9, "name": "Study"}],
    }})

    assert get_active_map_id(hass, _VAC) == "Loft", (
        "the single-map anchor refused an omitted room_list_entity"
    )


@pytest.mark.parametrize("site", ["known_map_ids", "implicit", "discover"])
def test_rd26_an_empty_declaration_is_not_an_omitted_one(hass, manager, site):
    """[RD-26] `absent` and `empty` are different inputs, at every read site.

    This is the whole reason the resolver is `.get(key, default)` and not
    `value or default`. The two spellings differ on exactly one input -- a key present
    and empty -- and the difference is deliberate: clearing a field in a UI is not a
    request to read the vacuum's own attributes, it is an incomplete declaration. The
    `or` form would silently convert one into the other.

    `RD-19[empty_entity]` already pins this at the discovery site. These rows extend it
    to the two map-anchor readers, because a resolver shared by four callers can only be
    trusted at the callers that are driven -- and the `or` spelling would have been
    invisible at the two that were not.

    RED: spell the resolver `(discovery or {}).get("room_list_entity") or
    ROOM_LIST_ENTITY_SELF` and every row here goes red along with RD-19[empty_entity].
    """
    hass.states.async_set("sensor.alfred_map", _NOT_A_MAP_ID)

    if site == "known_map_ids":
        _per_map_no_entity(room_list_entity="")
        hass.states.async_set(_VAC, "docked", {"rooms": {
            "Downstairs": [{"id": 1, "name": "Kitchen"}],
        }})
        # An empty declaration cannot enumerate, so [MAP-ANCHOR-1] makes no judgement
        # and the bad value is trusted -- the [RD-16] behaviour, unchanged.
        assert get_active_map_id(hass, _VAC) == _NOT_A_MAP_ID
    elif site == "implicit":
        _per_map_no_entity(room_list_entity="", implicit_map_id="Main")
        hass.states.async_set(_VAC, "docked", {"rooms": {
            "Loft": [{"id": 9, "name": "Study"}],
        }})
        hass.states.async_set("sensor.alfred_map", "unavailable")
        assert get_active_map_id(hass, _VAC) is None, (
            "an EMPTY declaration anchored an implicit map as though it were absent"
        )
    else:
        _per_map_no_entity(room_list_entity="", room_list_shape=None)
        hass.states.async_set(_VAC, "docked", {"rooms": [{"id": 4, "name": "Pantry"}]})
        assert discover_rooms_for_vacuum(
            hass, vacuum_entity_id=_VAC, map_id="6"
        ) == [], "an EMPTY declaration discovered rooms as though it were absent"
