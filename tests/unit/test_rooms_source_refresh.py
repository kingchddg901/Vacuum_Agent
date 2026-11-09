"""Unit tests for rooms/source_refresh.py — the service-call room source.

Roborock's rooms live ONLY in the get_maps service RESPONSE (a
``{segment_id_str: name}`` mapping per map), never an entity attribute. These
cover the flatten shim (pure), the cache, the async refresher, and the bridge
into the sync discovery path.

Coverage targets
----------------
[SR-1]  flatten turns {id:name} rooms into list-of-dicts keyed by map name.
[SR-2]  flatten unwraps a per-entity response wrapper.
[SR-3]  flatten accepts a bare maps list + already-list rooms.
[SR-4]  flatten skips malformed map entries and names nameless maps.
[SR-5]  cache get/set round-trips; empty -> {}.
[SR-6]  async_refresh calls the service + caches for service_response sources.
[SR-7]  async_refresh is a no-op for attribute sources / missing maps_service.
[SR-8]  the cached source flows through discover_rooms_for_vacuum (int + slug).
[SR-9]  an unavailable vacuum entity -> refresh skips the service cleanly (no
        "did not match any entities" throw); cache untouched.
[SR-16] select_segments_for_map refuses a non-dict source instead of raising.
[SR-17] invalidate drops ONE vacuum's entry or ALL of them (SRC-5) -- the whole
        if/else was unreached, so a reloaded entry's stale cache was untested.
[SR-18] _extract_maps_list prefers the TARGETED entity's wrapper and falls through
        to another entity's when that one's `maps` is not a list.
[SR-19] _active_map_id_from_config: no declaration, and an unusable state value.
[SR-20] flatten's map-NAME ladder (the `flag` rung) + a None-named room is skipped
        without ending the walk + a rooms value of neither shape yields no rooms.
[SR-21] RP-006 (SRC-2): an empty response is refused when there is a cache to
        protect and committed when there is not -- BOTH arms of the `and`.
[SR-22] (SRC-4): a slow response superseded while it awaited is discarded, and
        the newer commit left standing. Driven by a REAL second refresh.
[SR-23] RP-007 (SRC-3): two maps with the SAME human-edited name both survive,
        the second under a collision-safe suffix, and the warning names both.
[SR-24] (SRC-4, the other half): concurrent callers COALESCE onto one in-flight
        refresh -- the service is called once and both callers get that result.
"""

from __future__ import annotations

import logging

import pytest

from homeassistant.core import SupportsResponse

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.rooms.room_discovery import (
    discover_rooms_for_vacuum,
)
from custom_components.eufy_vacuum.rooms.source_refresh import (
    _active_map_id_from_config,
    _do_refresh_room_source,
    _extract_maps_list,
    invalidate_room_source_cache,
    select_segments_for_map,
    get_last_refresh_outcome,
    async_refresh_room_source,
    flatten_maps_response,
    get_cached_room_source,
    set_cached_room_source,
)


_VAC = "vacuum.ivy"

_DISCOVERY = {
    "source": "service_response",
    "maps_service": {"domain": "roborock", "service": "get_maps"},
    "maps_rooms_key": "rooms",
    "map_name_key": "name",
    "room_id_key": "segment_id",
    "room_name_key": "name",
}

# The real captured get_maps shape (rooms is a {segment_id_str: name} mapping,
# names are user-set incl. spaces + "&").
_MAPS = [
    {
        "flag": 0,
        "name": "Main floor",
        "rooms": {"16": "KITCHEN", "17": "Dining Room", "20": "Heidi & Chris"},
    }
]


def _service_response_adapter(vac=_VAC):
    register_adapter_config(vac, {
        "adapter_id": "rb",
        "source": "code",
        "entities": {"active_map": "select.ivy_selected_map"},
        "discovery": dict(_DISCOVERY),
    })


# --- flatten shim (pure) ----------------------------------------------------


def test_flatten_mapping_to_list():
    """[SR-1]"""
    out = flatten_maps_response({"maps": _MAPS}, discovery=_DISCOVERY)
    assert set(out) == {"Main floor"}
    rooms = out["Main floor"]
    assert {r["segment_id"] for r in rooms} == {"16", "17", "20"}
    by_id = {r["segment_id"]: r["name"] for r in rooms}
    assert by_id["20"] == "Heidi & Chris"


def test_flatten_unwraps_entity_wrapper():
    """[SR-2] response keyed by the target entity id."""
    out = flatten_maps_response(
        {_VAC: {"maps": _MAPS}},
        discovery=_DISCOVERY,
        vacuum_entity_id=_VAC,
    )
    assert "Main floor" in out


def test_flatten_bare_list_and_list_rooms():
    """[SR-3] a bare maps list, and a map whose rooms are already list-of-dicts."""
    bare = flatten_maps_response(_MAPS, discovery=_DISCOVERY)
    assert "Main floor" in bare

    already_list = flatten_maps_response(
        {"maps": [{"name": "Up", "rooms": [{"segment_id": "5", "name": "Loft"}]}]},
        discovery=_DISCOVERY,
    )
    assert already_list["Up"] == [{"segment_id": "5", "name": "Loft"}]


def test_flatten_skips_bad_entries_and_names_unnamed_maps():
    """[SR-4] non-dict entries are skipped; nameless maps get a fallback key."""
    out = flatten_maps_response(
        {"maps": ["junk", {"rooms": {"1": "X"}}, {"name": "Real", "rooms": {"2": "Y"}}]},
        discovery=_DISCOVERY,
    )
    assert set(out) == {"Map 1", "Real"}
    assert out["Map 1"] == [{"segment_id": "1", "name": "X"}]


def test_flatten_uses_active_map_for_single_unnamed_map():
    """[SR-4] Roborock can return name="" while the active map select says Map 0."""
    out = flatten_maps_response(
        {_VAC: {"maps": [{"flag": 0, "name": "", "rooms": {"16": "Спальня"}}]}},
        discovery=_DISCOVERY,
        vacuum_entity_id=_VAC,
        active_map_id="Map 0",
    )
    assert set(out) == {"Map 0"}
    assert out["Map 0"] == [{"segment_id": "16", "name": "Спальня"}]


def test_flatten_unrecognized_response_empty():
    """[SR-4] a response with no maps list -> empty dict."""
    assert flatten_maps_response({"nope": 1}, discovery=_DISCOVERY) == {}
    assert flatten_maps_response(None, discovery=_DISCOVERY) == {}


# --- cache ------------------------------------------------------------------


def test_cache_round_trip(hass):
    """[SR-5]"""
    assert get_cached_room_source(hass, _VAC) == {}
    set_cached_room_source(hass, _VAC, {"Main floor": [{"segment_id": "16", "name": "KITCHEN"}]})
    assert get_cached_room_source(hass, _VAC)["Main floor"][0]["name"] == "KITCHEN"


# --- async refresher --------------------------------------------------------


async def test_async_refresh_caches(hass):
    """[SR-6] service_response source -> service called, result flattened + cached."""
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        return {"maps": _MAPS}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )

    await async_refresh_room_source(hass, _VAC)
    cache = get_cached_room_source(hass, _VAC)
    assert {r["segment_id"] for r in cache["Main floor"]} == {"16", "17", "20"}


async def test_async_refresh_caches_unnamed_map_by_active_select(hass):
    """[SR-6] unnamed Roborock map is cached under the active-map select value."""
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        return {_VAC: {"maps": [{"flag": 0, "name": "", "rooms": {"16": "KITCHEN"}}]}}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("select.ivy_selected_map", "Map 0")

    await async_refresh_room_source(hass, _VAC)

    cache = get_cached_room_source(hass, _VAC)
    assert list(cache) == ["Map 0"]
    assert cache["Map 0"] == [{"segment_id": "16", "name": "KITCHEN"}]


async def test_async_refresh_skips_unavailable_entity(hass):
    """[SR-9] an unavailable vacuum entity -> skip the service call cleanly (the
    transient that throws 'did not match any entities' post-restart); no cache."""
    clear_registry()
    _service_response_adapter()

    called: list = []

    async def _get_maps(call):
        called.append(call)
        return {"maps": _MAPS}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )

    hass.states.async_set(_VAC, "unavailable")
    await async_refresh_room_source(hass, _VAC)
    assert called == []  # service not called for an unavailable entity
    assert get_cached_room_source(hass, _VAC) == {}


async def test_async_refresh_noop_for_attribute_source(hass):
    """[SR-7] attribute sources have nothing to refresh.

    THE REASON IS ASSERTED, not just the empty cache. `get_cached_room_source(...)
    == {}` is equally true of a vacuum that was never configured at all, so on its
    own it is an expectation the FALLBACK also produces -- the shape this campaign
    keeps paying for. `not_service_source` was the one `reason` in this module's
    eight-string vocabulary that nothing anywhere asserted, so renaming that literal
    broke no test.

    RED: return any other reason from the non-service exit.
    """
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": "eufy", "source": "code",
        "discovery": {"source": "entity_attribute", "room_list_attribute": "segments"},
    })
    outcome = await async_refresh_room_source(hass, _VAC)
    assert get_cached_room_source(hass, _VAC) == {}
    assert outcome["reason"] == "not_service_source", outcome


async def test_async_refresh_noop_missing_maps_service(hass):
    """[SR-7] service_response with no maps_service declared -> no-op (no crash)."""
    clear_registry()
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "discovery": {"source": "service_response"},
    })
    await async_refresh_room_source(hass, _VAC)
    assert get_cached_room_source(hass, _VAC) == {}


# --- bridge into discovery --------------------------------------------------


def test_cached_source_flows_into_discovery(hass):
    """[SR-8] discover_rooms_for_vacuum reads the cache for service sources and
    applies the normal int-coerce + slug normalization downstream."""
    clear_registry()
    _service_response_adapter()
    hass.states.async_set("select.ivy_selected_map", "Main floor")
    set_cached_room_source(hass, _VAC, flatten_maps_response({"maps": _MAPS}, discovery=_DISCOVERY))

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)

    by_id = {r["room_id"]: r for r in rooms}
    assert set(by_id) == {16, 17, 20}  # str ids coerced to int
    assert by_id[16]["slug"] == "kitchen"
    assert by_id[20]["slug"] == "heidi_and_chris"  # "&" -> "and", space -> "_"
    assert by_id[16]["map_id"] == "Main floor"


def test_single_map_fallback_when_active_map_unknown(hass):
    """[SR-8] a single cached map is used even if active_map didn't resolve to
    its key (e.g. active_map unknown at refresh time)."""
    clear_registry()
    _service_response_adapter()
    # active_map sentinel -> get_active_map_id returns None -> resolved "unknown".
    hass.states.async_set("select.ivy_selected_map", "unknown")
    set_cached_room_source(hass, _VAC, flatten_maps_response({"maps": _MAPS}, discovery=_DISCOVERY))

    rooms = discover_rooms_for_vacuum(hass, vacuum_entity_id=_VAC)
    assert {r["room_id"] for r in rooms} == {16, 17, 20}


# --- ISSUE #55: "not supported" is not "failed" -----------------------------
#
# A Roborock Q7 M5 is a B01-protocol device. Home Assistant routes it to
# `RoborockQ7Vacuum`, whose `get_maps()` is a stub raising ServiceNotSupported
# unconditionally (components/roborock/vacuum.py, HA 2026.8); the Q10 class is the
# same, and only the V1 class implements it. Folded into `service_call_failed`, that
# reached the owner as "failed ... please report it with diagnostics", so he did.
#
# These two tests are a PAIR and only mean something together: SR-13 pins that a
# permanent refusal is named as one, SR-14 pins that a genuine fault is still named a
# fault. Either alone passes if both reasons collapse back into one string.


async def test_service_not_supported_is_not_a_failure(hass):
    """[SR-13] ServiceNotSupported -> its own reason, never `service_call_failed`."""
    from homeassistant.exceptions import ServiceNotSupported

    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        raise ServiceNotSupported("roborock", "get_maps", _VAC)

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    result = await async_refresh_room_source(hass, _VAC)

    assert result["ok"] is False
    assert result["reason"] == "service_not_supported", (
        "a device Home Assistant refuses to answer for must not be reported as a "
        "transient failure — that is what asked a user to file issue #55 about his "
        "own hardware's documented limits."
    )


async def test_a_real_service_error_is_still_a_failure(hass):
    """[SR-14] the negative control: SR-13 must not swallow genuine faults."""
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        raise RuntimeError("connection reset by peer")

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    result = await async_refresh_room_source(hass, _VAC)

    assert result["ok"] is False
    assert result["reason"] == "service_call_failed", (
        "a transient upstream error must still ask for a report; if this returns "
        "`service_not_supported` the two branches have collapsed and real bugs will "
        "be told they are unsupported hardware."
    )


async def test_refusal_is_RECORDED_not_just_returned(hass):
    """[SR-15] the outcome must OUTLIVE the call, or diagnostics is back to guessing.

    The room-source cache only ever stored successes, so a refusal left no trace and
    the self-check had to infer "why has this device no rooms" from the shape of its
    entity list — which is how a Roborock owner got told to use the Eufy app. Without
    this test the recording call can be deleted and every other test stays green.
    """
    from homeassistant.exceptions import ServiceNotSupported

    clear_registry()
    _service_response_adapter()

    assert get_last_refresh_outcome(hass, _VAC) == {}, (
        "{} must mean NEVER ASKED — a vacuum with no recorded outcome is not a "
        "vacuum known to be unsupported, and the two read alike"
    )

    async def _get_maps(call):
        raise ServiceNotSupported("roborock", "get_maps", _VAC)

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    await async_refresh_room_source(hass, _VAC)

    recorded = get_last_refresh_outcome(hass, _VAC)
    assert recorded.get("reason") == "service_not_supported"
    assert recorded.get("ok") is False
    assert recorded.get("at"), "an outcome with no timestamp cannot be aged out later"


async def test_success_is_recorded_too(hass):
    """[SR-15] the negative control: recording only failures would make a stale
    refusal permanent — a device fixed upstream would still read 'unsupported'."""
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        return {"maps": _MAPS}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    await async_refresh_room_source(hass, _VAC)

    recorded = get_last_refresh_outcome(hass, _VAC)
    assert recorded.get("ok") is True and recorded.get("reason") is None


# ---------------------------------------------------------------------------
# [SR-16] - [SR-20]  the refusal guards and the naming ladder.
#
# These are the small half of a 24-unit gap; the two NAMED RULINGS at the tail of
# `_do_refresh_room_source` (SRC-2's empty-response cache keep, SRC-4's generation
# check) are [SR-21]/[SR-22].
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("per_map", [
    pytest.param(None, id="none"),
    pytest.param([], id="a_list"),
    pytest.param("rooms", id="a_string"),
])
def test_sr16_a_non_dict_source_is_refused(per_map):
    """[SR-16] `None`, not a raise and not a relabelled guess.

    This is read on the discovery path with whatever the cache holds, and the cache
    is fed by a service RESPONSE -- so a brand that answers with a list, or a cache
    that was never populated, reaches here. `a_string` is in the set because `str`
    has `.get`-less iteration that would otherwise look dict-ish to a looser guard.

    RED: delete `if not isinstance(per_map, dict)` and `None.get` /
    `[].get` / `'rooms'.get` raises AttributeError.
    """
    assert select_segments_for_map(per_map, "7") is None


def test_sr17_invalidate_drops_one_vacuum_or_all_of_them(hass):
    """[SR-17] SRC-5: a reloaded entry must not serve the previous life's cache.

    BOTH ARMS WERE UNREACHED -- not one of them, the whole `if/else`. Every call in
    the suite arrived with no cache dict at all and returned at the guard above, so
    nothing had ever driven the clearing itself. A function whose only tested path
    is its early return reads as covered.

    THE TWO ARMS ARE ASSERTED AGAINST EACH OTHER, which is what makes either one
    mean something: the targeted call must leave the OTHER vacuum's entry alone, and
    the untargeted call must take both. A `clear()` in place of the `pop` satisfies
    a single-vacuum test perfectly.

    RED: swap the `pop` for a `clear()` and the first half fails; swap the `clear()`
    for a `pop` and the second half fails.
    """
    set_cached_room_source(hass, _VAC, {"Main floor": [{"id": "16"}]})
    set_cached_room_source(hass, "vacuum.other", {"Attic": [{"id": "9"}]})

    invalidate_room_source_cache(hass, _VAC)
    assert get_cached_room_source(hass, _VAC) == {}
    assert get_cached_room_source(hass, "vacuum.other") != {}, (
        "a targeted invalidate took another vacuum's cache with it"
    )

    invalidate_room_source_cache(hass)
    assert get_cached_room_source(hass, "vacuum.other") == {}


def test_sr18_the_targeted_entity_wins_and_the_walk_falls_through():
    """[SR-18] Prefer the entity we asked about; otherwise take the first that answers.

    TWO CLAIMS IN ONE RESPONSE, because each needs the other to be visible. The
    targeted wrapper carries a `maps` that is NOT a list, so the preference arm is
    entered and REJECTED -- and the walk then has to find the other entity's good
    list. A response where the targeted entity answers correctly cannot show the
    fall-through; one where it is absent cannot show the preference.

    THE BAD WRAPPER IS DECLARED FIRST so the loop's own order is exercised rather
    than coincidence -- `_extract_maps_list` returns the FIRST dict value carrying a
    list, and with the bad one last a `break`-shaped rewrite would still pass.

    RED: drop the `isinstance(inner, list)` test and the non-list `maps` is returned
    verbatim; drop the loop and the fall-through yields `[]`.
    """
    response = {
        _VAC: {"maps": "not-a-list"},
        "vacuum.other": {"maps": [{"name": "Attic", "rooms": {"9": "ATTIC"}}]},
    }

    got = _extract_maps_list(response, vacuum_entity_id=_VAC)
    assert got == [{"name": "Attic", "rooms": {"9": "ATTIC"}}], got

    # ...and the preference IS a preference: when the targeted entity answers with a
    # real list, that one wins over the other entity's.
    response[_VAC] = {"maps": [{"name": "Main floor"}]}
    assert _extract_maps_list(response, vacuum_entity_id=_VAC) == [
        {"name": "Main floor"}
    ]


def test_sr19_an_undeclared_or_unusable_active_map_resolves_to_none(hass):
    """[SR-19] No declaration and no usable state both answer None.

    This feeds `flatten_maps_response`'s single-map naming rung, so a value invented
    here would name a map after the string `unknown` and make the cache key
    undiscoverable -- which is why the unusable set is checked rather than just
    truthiness.

    THE POSITIVE CONTROL IS ASSERTED LAST: a real state DOES come back, so the two
    Nones above are refusals rather than a function that always answers None.

    RED: delete either `return None` -- the undeclared case then reads
    `hass.states.get(None)`, and the unusable case returns the literal
    `"unavailable"` as a map name.
    """
    assert _active_map_id_from_config(hass, {}, _VAC) is None
    assert _active_map_id_from_config(hass, {"entities": {}}, _VAC) is None

    config = {"entities": {"active_map": "select.ivy_selected_map"}}
    for bad in ("", "unknown", "unavailable", "none", "None", "   "):
        hass.states.async_set("select.ivy_selected_map", bad)
        assert _active_map_id_from_config(hass, config, _VAC) is None, bad

    hass.states.async_set("select.ivy_selected_map", "Main floor")
    assert _active_map_id_from_config(hass, config, _VAC) == "Main floor", (
        "the control: a usable state must survive, or the Nones above prove nothing"
    )


def test_sr20_the_name_ladder_the_skipped_room_and_a_shapeless_rooms_value():
    """[SR-20] Three structural claims about the flatten shim, in one response.

    * THE MIDDLE RUNG OF THE NAME LADDER. With more than one map the active-map
      shortcut cannot apply, so an entry carrying a `flag` is named `Map <flag>`
      rather than by its index. The code's own comment says someone reconciling a
      cache key that came back "Map 3" is looking at this rung, not at a bug.
    * A None-NAMED ROOM IS SKIPPED AND THE WALK CONTINUES. It is declared FIRST in
      its mapping on purpose -- with it last, `continue` and `break` produce the
      same output and the claim is untestable.
    * A `rooms` VALUE OF NEITHER SHAPE yields an empty room list rather than
      raising: the map still appears, so a consumer sees a known map with no rooms
      instead of the map vanishing.

    RED: name the flag rung by index and the first key changes; turn the `continue`
    into a `break` and room 17 disappears; drop the `isinstance(rooms, list)` elif
    and the shapeless entry raises.
    """
    out = flatten_maps_response(
        {
            "maps": [
                {"flag": 3, "rooms": {"16": None, "17": "DINING"}},
                {"flag": 4, "rooms": "not-a-shape"},
            ]
        },
        discovery=dict(_DISCOVERY),
        vacuum_entity_id=_VAC,
        active_map_id="Main floor",
    )

    # The flag rung, not the index rung: `Map 3`/`Map 4`, never `Map 0`/`Map 1`.
    assert sorted(out) == ["Map 3", "Map 4"], sorted(out)
    # The None-named room is gone and the one AFTER it survived.
    assert out["Map 3"] == [{"segment_id": "17", "name": "DINING"}], out["Map 3"]
    # The shapeless rooms value costs the rooms, not the map.
    assert out["Map 4"] == []


# ---------------------------------------------------------------------------
# [SR-21] / [SR-22]  the two NAMED RULINGS at the tail of `_do_refresh_room_source`.
#
# Both are REFUSALS TO COMMIT, and that is why neither had ever run: every other
# refresh test in this file hands the shim a good response on a quiet cache, which
# is exactly the input both guards let through.
# ---------------------------------------------------------------------------

#: A cache worth protecting. Its segment id is the one that must SURVIVE [SR-21] and
#: the one that must NOT be resident at the end of [SR-22] -- distinct values on both
#: sides of each comparison, so neither arm can be satisfied by the other's data, and
#: no rung of flatten's name ladder produces either.
_PREVIOUSLY_GOOD = {"Main floor": [{"segment_id": "16", "name": "KITCHEN"}]}


async def test_sr21_an_empty_response_must_not_blank_a_good_cache(hass):
    """[SR-21] RP-006 (SRC-2): a response that flattens to NOTHING is refused when
    there is a previously-good cache, and committed when there is not.

    BOTH ARMS OF THE `and`, ASSERTED AGAINST EACH OTHER, because the guard is a
    conjunction and either arm alone is satisfied by the other's rewrite. The ruling
    is about WHICH empty response is a glitch: with a cache behind it an empty answer
    is a transient upstream hiccup, and committing it blanks the room source for
    every consumer until the next success; with no cache behind it the same answer is
    simply the truth about a vacuum that has no maps, and refusing it reports a
    failure that did not happen.

    THE NO-CACHE ARM RUNS FIRST on purpose. It leaves `{"per_map": {}}` resident,
    which `get_cached_room_source` still reads as `{}` -- so the second arm has to
    seed a real cache rather than inherit a truthy one.

    RED (measured in a HEAD snapshot, each ablation applied alone):
      * delete the whole `if not per_map and get_cached_room_source(...)` block ->
        `assert second["ok"] is False` / `assert True is False`. The guard is NOT
        shadowed by what follows it: the empty `per_map` flows straight through the
        generation check into `set_cached_room_source`.
      * drop only the `and get_cached_room_source(...)` conjunct -> ARM 1 fails
        (`assert (False is True)`), on a vacuum that never had a cache.
      * keep the guard but write `per_map` before its return -> only the final cache
        assertion fires (`assert {} == {'Main floor': ...}`), which is what proves
        that assertion carries the ruling rather than riding on the reason above it.

    TWO-CAUSE SIGNATURE, so a future red localises correctly: ARM 1 also goes red if
    SRC-4's `!=` is flipped to `==`, because the committing exit is downstream of
    that guard too. The failure text discriminates -- a dropped conjunct shows
    `ok=False`, an inverted SRC-4 shows `reason='superseded_by_newer_refresh'`.
    """
    clear_registry()
    _service_response_adapter()

    async def _get_maps(call):
        # The device answered; it has no maps. A valid response that flattens to {}.
        return {"maps": []}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    # ARM 1 -- nothing to protect, so the empty answer is the truth and commits.
    assert get_cached_room_source(hass, _VAC) == {}, "arm 1 needs a virgin cache"
    first = await async_refresh_room_source(hass, _VAC)
    assert first["ok"] is True and first["reason"] is None, (
        "with no cache behind it an empty response is not a glitch, it is a vacuum "
        "with no maps; reporting `empty_response_kept_cache` here names a kept "
        "cache that does not exist and turns a first refresh into a failure"
    )

    # ARM 2 -- the same response, now with a good cache behind it.
    set_cached_room_source(hass, _VAC, dict(_PREVIOUSLY_GOOD))
    second = await async_refresh_room_source(hass, _VAC)

    assert second["ok"] is False
    assert second["reason"] == "empty_response_kept_cache"
    assert get_cached_room_source(hass, _VAC) == _PREVIOUSLY_GOOD, (
        "a response that flattened to nothing replaced a previously-good room "
        "source -- one transient upstream glitch blanks rooms for every consumer "
        "until the next successful refresh, which is the whole of RP-006/SRC-2"
    )


async def test_sr22_a_superseded_response_is_discarded_not_committed(hass):
    """[SR-22] (SRC-4): a slow response whose generation was superseded while it
    awaited must be dropped, and the newer commit left standing.

    DRIVEN BY A REAL SECOND REFRESH, not by poking `_GENERATION`. `generation` is
    captured BEFORE the service await (`generation = _GENERATION.get(...)` sits
    directly above `hass.services.async_call`), so a value written before the call is
    the value the call reads back and the comparison is `g != g` -- an identity that
    cannot fail. MEASURED: a test that pokes `_GENERATION` before calling gets
    `reason=None` and never enters this branch at all. A test that pokes it from
    inside the stubbed `get_maps` does enter the branch and passes -- AND STAYS GREEN
    WHEN `_GENERATION[vacuum_entity_id] = generation + 1` IS DELETED, because the
    poke supplies the bump the code was supposed to make. Only a real second refresh
    is sensitive to the WRITE side as well as the comparison.

    IT CALLS `_do_refresh_room_source` DIRECTLY, by necessity: `_INFLIGHT` coalescing
    in `async_refresh_room_source` makes two concurrent refreshes of one vacuum
    unreachable through the public entry point -- the second caller awaits the
    first's task instead of starting one. (The race is still reachable in production:
    the `finally` pops `_INFLIGHT` when an AWAITER is cancelled while
    `asyncio.shield` keeps the inner task running, and the next caller then creates a
    second task over the top of it.) Because it bypasses the wrapper it does not
    exercise `record_refresh_outcome`; [SR-15] owns that.

    DISTINCT ROOM IDS UNDER THE SAME MAP NAME. Both responses key on "Main floor", so
    a stale commit OVERWRITES rather than adding a key -- `"99"` vs `"16"` is the only
    thing that says which task won, and no fallback produces either.

    RED (measured in a HEAD snapshot, each ablation applied alone):
      * delete the generation block -> `assert None == 'superseded_by_newer_refresh'`;
      * delete `_GENERATION[vacuum_entity_id] = generation + 1` -> the same
        assertion fails. The guard reads a counter nothing moves.
      * flip `!=` to `==` -> the FAST refresh declares itself superseded, caught by
        the `fast["reason"] is None` control.
      * keep the guard but write `per_map` before its return -> only the final cache
        assertion fires (`assert ['16'] == ['99']`).
    """
    import asyncio

    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

    clear_registry()
    _service_response_adapter()

    gate = asyncio.Event()      # released once the newer refresh has committed
    parked = asyncio.Event()    # set once the slow refresh is inside the call
    seen: list[str] = []

    _STALE = [{"flag": 0, "name": "Main floor", "rooms": {"16": "KITCHEN"}}]
    _NEWER = [{"flag": 0, "name": "Main floor", "rooms": {"99": "STUDY"}}]

    async def _get_maps(call):
        if not seen:
            seen.append("slow")
            parked.set()
            await gate.wait()
            return {"maps": _STALE}
        seen.append("fast")
        return {"maps": _NEWER}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    config = get_adapter_config(_VAC)
    discovery = config["discovery"]

    slow = hass.async_create_task(
        _do_refresh_room_source(hass, _VAC, config, discovery)
    )
    await parked.wait()  # the slow refresh has captured its generation

    fast = await _do_refresh_room_source(hass, _VAC, config, discovery)
    assert fast["ok"] is True and fast["reason"] is None, (
        "the control: the newer refresh must really commit, or there is no race to "
        "lose -- if THIS one says `superseded_by_newer_refresh` the comparison is "
        "inverted and every refresh declares itself stale"
    )

    gate.set()
    stale = await slow

    assert stale["ok"] is True, (
        "a discarded stale response is not a failure: the room source is correct, "
        "it was just written by someone else"
    )
    assert stale["reason"] == "superseded_by_newer_refresh"
    assert seen == ["slow", "fast"], seen  # the premise: the slow one went first

    cached = get_cached_room_source(hass, _VAC)
    assert [r["segment_id"] for r in cached["Main floor"]] == ["99"], (
        f"the stale response overwrote the newer commit: {cached} -- this is the "
        "RP-007/SRC-4 case where a refresh that started before a map switch landed "
        "after it and became the resident snapshot"
    )


# ---------------------------------------------------------------------------
# [SR-23] / [SR-24]  two more named rulings, neither claimed by the first pass.
#
# Both were found by AUDITING the two tests above rather than by walking coverage:
# the uncovered blocks each carry an `RP-`/`SRC-` id, which is the signature this
# campaign keeps finding -- the code names a ruling and nothing drives it.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("second_flag,expected_key", [
    pytest.param(1, "Main#flag1", id="the_second_carries_a_flag"),
    pytest.param(None, "Main#idx1", id="the_second_has_no_flag"),
])
def test_sr23_two_maps_with_one_name_both_survive(caplog, second_flag, expected_key):
    """[SR-23] RP-007 (SRC-3): a name collision costs a KEY, never a map's rooms.

    Map names are human-editable in the vendor app, so two maps called "Main" is a
    thing a user can simply do. The incident the code records: last-writer-wins
    overwrote the first map's entry, which silently discarded a whole map's rooms
    and -- chained into discovery's single-map fallback -- served one map's segment
    ids under the other map's id.

    THE ROOMS ARE ASSERTED UNDER EACH KEY, not just the key set. A rewrite that
    suffixed correctly while swapping the two maps' rooms would satisfy a
    keys-only assertion and reproduce the exact defect the suffix exists to stop.

    BOTH SUFFIX BRANCHES, because the ternary picks on `flag is not None` and the
    `#idx` arm is what a brand that sends no flag gets. Measured: `Main#flag1` and
    `Main#idx1` respectively.

    THE WARNING IS PART OF THE RULING -- "key collision-safely AND SAY SO". A
    silent rename is the thing that makes a cache key nobody expected
    unexplainable, so the log naming BOTH the original and the new key is asserted.

    RED: delete the `if map_name in out` block and the second map overwrites the
    first -- one key instead of two, and KITCHEN gone.
    """
    second = {"name": "Main", "rooms": {"17": "DINING"}}
    if second_flag is not None:
        second["flag"] = second_flag

    with caplog.at_level(
        logging.WARNING, logger="custom_components.eufy_vacuum.rooms.source_refresh"
    ):
        out = flatten_maps_response(
            {
                "maps": [
                    {"flag": 0, "name": "Main", "rooms": {"16": "KITCHEN"}},
                    second,
                ]
            },
            discovery=dict(_DISCOVERY),
            vacuum_entity_id=_VAC,
        )

    assert sorted(out) == sorted(["Main", expected_key]), sorted(out)
    # The rooms stayed with their own map -- the half a keys-only assertion misses.
    assert out["Main"] == [{"segment_id": "16", "name": "KITCHEN"}], out
    assert out[expected_key] == [{"segment_id": "17", "name": "DINING"}], out

    messages = [r.getMessage() for r in caplog.records]
    assert any("duplicate map name" in m and expected_key in m for m in messages), (
        "the rename has to be explainable: %s" % messages
    )


async def test_sr24_concurrent_callers_coalesce_onto_one_refresh(hass):
    """[SR-24] SRC-4's other half: one in-flight refresh serves every caller.

    The generation check ([SR-22]) is what makes a LOST race safe; this is what
    stops the race being run at all for callers that arrive together. Several
    consumers ask for a room source on the same tick during setup, and a
    service-response brand answers over the network -- so N callers must not mean N
    `get_maps` calls.

    THE OBSERVABLE IS THE HANDLER CALL COUNT, which is the only thing that can tell
    coalescing from two refreshes that happen to agree. Both callers returning the
    same dict is equally true of two independent refreshes against a stable device,
    so that assertion alone would be satisfied by the behaviour this test exists to
    reject.

    The handler parks until both callers are waiting, so the second genuinely
    arrives while the first is in flight rather than after it.

    RED: delete the `if existing is not None and not existing.done()` branch and
    the handler is called twice.
    """
    import asyncio

    clear_registry()
    _service_response_adapter()

    calls: list[str] = []
    release = asyncio.Event()

    async def _get_maps(call):
        calls.append("get_maps")
        await release.wait()
        return {"maps": [{"flag": 0, "name": "Main floor", "rooms": {"16": "KITCHEN"}}]}

    hass.services.async_register(
        "roborock", "get_maps", _get_maps, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(_VAC, "docked")

    first = hass.async_create_task(async_refresh_room_source(hass, _VAC))
    # Let the first reach the parked service call before the second arrives.
    while not calls:
        await asyncio.sleep(0)
    second = hass.async_create_task(async_refresh_room_source(hass, _VAC))
    await asyncio.sleep(0)

    release.set()
    got_first, got_second = await first, await second

    assert calls == ["get_maps"], (
        "the second caller started its own refresh instead of coalescing: %s" % calls
    )
    assert got_first == got_second
    assert got_first["ok"] is True and got_first["reason"] is None
    assert "Main floor" in get_cached_room_source(hass, _VAC)
