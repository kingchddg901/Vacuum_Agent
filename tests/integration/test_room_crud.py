"""Tests for rooms/room_crud.py — RoomMapManager (mock manager + .data).

RoomMapManager calls several manager hooks (ensure_vacuum_record,
_refresh_room_derived_state, _notify_rooms_updated, mark_rooms_discovered,
confirm_floor_type, ensure_runtime) — all no-ops on a MagicMock — and the real
build_managed_rooms / rebuild_map_bucket helpers.

Coverage targets
----------------
[RC-1] save_managed_rooms builds managed rooms from discovery.
[RC-2] get_managed_rooms returns the stored rooms + summary.
[RC-3] remove_map deletes the bucket + reports removals.
[RC-4] get_vacuum_maps summarizes known maps.
[RC-5] rebuild_map rebuilds from discovery.
[RC-6] remove_map clears related history/rule/active-job state.
[RC-7] discover_rooms runs discovery + caches the payload.
[RC-8] remove_map leaves sibling maps' access-graph grants untouched
       (grants are map-scoped room IDs; nothing to strip cross-map).
[RC-9] remove_map clears run_profiles/queue/onboarding (RP-016/RF-20 --
       PER_MAP_STORES coverage), leaving sibling maps' buckets untouched.
[RC-16] R16: adding a new PER_MAP_STORES entry cannot crash remove_map. The
        flag name is on the tuple row itself; nothing has to be hand-maintained
        in a sibling dict, and an ablation that puts back the sibling-dict
        subscript is what red-tags the regression. Also pins the PUBLIC RESPONSE
        SHAPE (the exact `_removed` keys), because tests/service callers key
        off them and drift there would be a silent break, not a crash. --
       PER_MAP_STORES coverage), leaving sibling maps' buckets untouched.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec, patch

import pytest

from tests._factories import spec_manager

from custom_components.eufy_vacuum.rooms.reconciliation import (
    compute_plan_token,
    compute_reconciliation,
)
from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def rmm():
    mgr = spec_manager()
    mgr.data = {}
    mgr.ensure_runtime.return_value = MagicMock()
    return RoomMapManager(mgr), mgr


def _seed_discovery(mgr, rooms):
    mgr.data.setdefault("discovery", {}).setdefault(_VAC, {})[_MAP] = {"rooms": rooms}


_DISCOVERED = [
    {"room_id": 1, "map_id": "6", "name": "Kitchen"},
    {"room_id": 2, "map_id": "6", "name": "Bath"},
]


def test_save_managed_rooms(rmm):
    """[RC-1]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    result = rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["room_count"] == 2
    assert set(result["rooms"]) == {"1", "2"}
    assert mgr.data["maps"][_VAC][_MAP]["rooms"]


def test_get_managed_rooms(rmm):
    """[RC-2]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    got = rm.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert got["room_count"] == 2
    assert "summary" in got


def test_remove_map(rmm):
    """[RC-3]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert removed["rooms_removed"] == 2
    assert removed["discovery_removed"] is True
    assert _MAP not in mgr.data["maps"][_VAC]


def test_get_vacuum_maps(rmm):
    """[RC-4]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    maps = rm.get_vacuum_maps(vacuum_entity_id=_VAC)
    assert maps["map_count"] == 1
    assert maps["maps"][0]["room_count"] == 2


def test_rebuild_map(rmm):
    """[RC-5]"""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    # discovery now reports only one room → rebuild drops the stale one
    _seed_discovery(mgr, [{"room_id": 1, "map_id": "6", "name": "Kitchen"}])
    rebuilt = rm.rebuild_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert rebuilt["room_count"] == 1
    assert set(rebuilt["rooms"]) == {"1"}


# ---------------------------------------------------------------------------
# RP-005/RF-02: the wipe guard at the room_crud chokepoints
# ---------------------------------------------------------------------------

def test_save_managed_rooms_refuses_empty_replacement(rmm):
    """[RP-005] An empty discovery must not wipe a non-empty stored room map."""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    stored_before = dict(mgr.data["maps"][_VAC][_MAP]["rooms"])
    assert stored_before

    _seed_discovery(mgr, [])  # a discovery glitch: zero rooms returned
    result = rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    assert result == {
        "saved": False,
        "reason": "empty_replacement_refused",
        "source": "save_managed_rooms",
        "stored_room_count": 2,
    }
    assert mgr.data["maps"][_VAC][_MAP]["rooms"] == stored_before


def test_save_managed_rooms_first_import_still_writes_empty(rmm):
    """[RP-005] Compatibility: a first-ever save with nothing stored yet must still
    write freely, even if the discovery happens to be empty (nothing to refuse)."""
    rm, mgr = rmm
    _seed_discovery(mgr, [])
    result = rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert "reason" not in result
    assert result["room_count"] == 0
    assert mgr.data["maps"][_VAC][_MAP]["rooms"] == {}


def test_save_managed_rooms_explicit_subset_still_prunes(rmm):
    """[RP-005] Compatibility: an explicit non-empty enabled_room_ids subset still
    prunes normally -- only a wipe TO EMPTY is refused."""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    result = rm.save_managed_rooms(
        vacuum_entity_id=_VAC, map_id=_MAP, enabled_room_ids=[1]
    )
    assert "reason" not in result
    assert set(result["rooms"]) == {"1"}


def test_rebuild_map_refuses_empty_replacement(rmm):
    """[RP-005] Same guard for rebuild_map -- an empty discovery must not wipe a
    non-empty stored room map. rebuild_map_bucket (maps/map_manager.py) is out of
    this packet's scope, so the guard fires BEFORE calling it."""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    stored_before = dict(mgr.data["maps"][_VAC][_MAP]["rooms"])

    _seed_discovery(mgr, [])
    result = rm.rebuild_map(vacuum_entity_id=_VAC, map_id=_MAP)

    assert result["saved"] is False
    assert result["reason"] == "empty_replacement_refused"
    assert result["source"] == "rebuild_map"
    assert mgr.data["maps"][_VAC][_MAP]["rooms"] == stored_before


def test_reconcile_room_migrate_refuses_partial_discovery(rmm):
    """[RP-005] Minimum-evidence guard: a discovery smaller than what is stored
    that would drop MORE THAN HALF the stored rooms on migrate is refused --
    distinct from the no_discovery guard (a totally empty discovery), and
    distinct from reconcile_room's own harness above (a normal shrink)."""
    rm, mgr = rmm
    stored = {
        str(i): {"room_id": i, "map_id": _MAP, "name": f"Room {i}", "slug": f"room-{i}"}
        for i in range(1, 5)  # 4 stored rooms
    }
    mgr.data["maps"] = {_VAC: {_MAP: {"rooms": stored}}}
    # Discovery now sees only 1 of the 4 (dropping 3 of 4 = more than half).
    mgr.data.setdefault("discovery", {}).setdefault(_VAC, {})[_MAP] = {
        "rooms": [{"room_id": 1, "map_id": _MAP, "name": "Room 1", "slug": "room-1"}]
    }

    # RP-019/REC-5: reconcile_room requires a plan_token matching what the current
    # discovery/existing rooms fingerprint to — a valid one here so this test still
    # exercises the partial-discovery guard, not the token gate.
    discovered = mgr.data["discovery"][_VAC][_MAP]["rooms"]
    token = compute_plan_token(
        reviews=compute_reconciliation(
            discovered_rooms=discovered, existing_rooms=stored,
        )["reviews"],
        discovered_rooms=discovered,
    )

    refused = rm.reconcile_room(
        vacuum_entity_id=_VAC, map_id=_MAP, action="migrate", plan_token=token
    )
    assert refused["skipped"] == "partial_discovery_refused"
    assert refused["migrated_room_count"] == 0
    assert mgr.data["maps"][_VAC][_MAP]["rooms"] == stored  # untouched

    forced = rm.reconcile_room(
        vacuum_entity_id=_VAC, map_id=_MAP, action="migrate", force=True, plan_token=token
    )
    assert forced.get("skipped") is None
    assert forced["migrated_room_count"] == 1


def test_rc18_a_rename_plus_renumber_records_the_slug_alias(rmm):
    """[RC-18] D5/REC-3 end to end: the alias must reach the STORE, not just the plan.

    [REC-19] pins that `plan_migration` now reports `slug_remap` for a room that was
    renamed AND renumbered in one re-map. This is the other half, and it is the half
    that was actually broken for the user: `reconcile_room` gates BOTH history
    remedies on a non-empty `slug_remap`, so a plan that reported none meant neither
    `record_slug_alias` (which repairs `room_stats`, rebuilt from the job records) nor
    `rekey_accuracy_slugs` (which repairs `accuracy_stats`, append-only and never
    rebuilt) ever ran. The room kept its floor type, passes and grants and read as
    never cleaned.

    A plan-level assertion alone would not have caught it: the plan is pure and the
    consumer is 200 lines away in another module, so this drives the real
    `reconcile_room(action="migrate")` with a real plan token and spies on the store
    it constructs. `create_autospec` so the spy agrees with the real method
    signatures rather than accepting any call.

    RED: drop `slug_remap[leftover_existing_slugs[0]] = slug` from the REC-3 pairing
    in `plan_migration` and both assertions fail -- `if _slug_remap:` is false and
    neither call is made.
    """
    rm, mgr = rmm
    stored = {
        "16": {"room_id": 16, "map_id": _MAP, "name": "Kitchen", "slug": "kitchen",
               "grants_access_to": [17]},
        "17": {"room_id": 17, "map_id": _MAP, "name": "Den", "slug": "den",
               "clean_passes": 3},
    }
    mgr.data["maps"] = {_VAC: {_MAP: {"rooms": stored}}}
    # Den is renamed to Study and the re-segment moves it 17 -> 20. Kitchen is
    # untouched, so the pairing has exactly one leftover and one unmatched room.
    discovered = [
        {"room_id": 16, "map_id": _MAP, "name": "Kitchen"},
        {"room_id": 20, "map_id": _MAP, "name": "Study"},
    ]
    _seed_discovery(mgr, discovered)

    token = compute_plan_token(
        reviews=compute_reconciliation(
            discovered_rooms=discovered, existing_rooms=stored,
        )["reviews"],
        discovered_rooms=discovered,
    )

    from custom_components.eufy_vacuum.learning.history_store import (
        LearningHistoryStore,
    )
    spy = create_autospec(LearningHistoryStore, instance=True)
    with patch(
        "custom_components.eufy_vacuum.learning.history_store.LearningHistoryStore",
        return_value=spy,
    ):
        out = rm.reconcile_room(
            vacuum_entity_id=_VAC, map_id=_MAP, action="migrate", plan_token=token,
        )

    assert out.get("skipped") is None, out
    spy.record_slug_alias.assert_called_once_with(
        vacuum_entity_id=_VAC, map_id=_MAP, old_slug="den", new_slug="study",
    )
    spy.rekey_accuracy_slugs.assert_called_once_with(
        vacuum_entity_id=_VAC, map_id=_MAP, slug_remap={"den": "study"},
    )
    # and the settings carry that already worked is unaffected
    assert mgr.data["maps"][_VAC][_MAP]["rooms"]["20"]["clean_passes"] == 3


def test_discover_rooms_keeps_cache_on_empty_result(manager):
    """[RP-005] A discovery glitch that returns zero rooms must not replace a
    previously-good cache -- save_managed_rooms reads FROM this cache, so an
    unguarded overwrite here would wipe stored rooms on the NEXT save too."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {"room_list_entity": "vacuum_entity",
                      "room_list_attribute": "segments",
                      "room_id_key": "id", "room_name_key": "name"},
    })
    manager.hass.states.async_set("sensor.alfred_map", "6")
    manager.hass.states.async_set(_VAC, "docked",
                                   {"segments": [{"id": 1, "name": "Kitchen"},
                                                 {"id": 2, "name": "Bath"}]})
    rm = RoomMapManager(manager)
    good = rm.discover_rooms(vacuum_entity_id=_VAC, map_id="6")
    assert good["room_count"] == 2

    # The next poll returns zero segments (a transient discovery glitch).
    manager.hass.states.async_set(_VAC, "docked", {"segments": []})
    kept = rm.discover_rooms(vacuum_entity_id=_VAC, map_id="6")

    assert kept.get("cache_kept") is True
    assert kept.get("reason") == "empty_discovery_kept"
    assert kept["room_count"] == 2
    assert manager.data["discovery"][_VAC]["6"]["rooms"] == good["rooms"]


def test_discover_rooms_genuinely_empty_first_discovery_still_writes(manager):
    """[RP-005] Compatibility: a genuinely-empty FIRST discovery (no prior cache)
    still writes normally -- absent != failed."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {"room_list_entity": "vacuum_entity",
                      "room_list_attribute": "segments",
                      "room_id_key": "id", "room_name_key": "name"},
    })
    manager.hass.states.async_set("sensor.alfred_map", "6")
    manager.hass.states.async_set(_VAC, "docked", {"segments": []})
    rm = RoomMapManager(manager)
    payload = rm.discover_rooms(vacuum_entity_id=_VAC, map_id="6")

    assert payload.get("cache_kept") is None
    assert payload["room_count"] == 0
    assert "6" in manager.data["discovery"][_VAC]


def test_remove_map_clears_related_state(rmm):
    """[RC-6] remove_map also clears history / rule-status / active-job slots and
    leaves any remaining map's access graph untouched."""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.data.setdefault("room_history", {}).setdefault(_VAC, {})[_MAP] = {"1": {}}
    mgr.data.setdefault("room_rule_status", {}).setdefault(_VAC, {})[_MAP] = {"x": 1}
    mgr.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = {"status": "started"}
    # a second map remains, with an access-graph grant list
    mgr.data["maps"][_VAC]["7"] = {"rooms": {"5": {"grants_access_to": [1, 2]}}}

    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert removed["history_removed"] is True
    assert removed["rule_status_removed"] is True
    assert removed["active_job_cleared"] is True
    # the remaining map's grant list is left exactly as-is
    assert mgr.data["maps"][_VAC]["7"]["rooms"]["5"]["grants_access_to"] == [1, 2]


def test_remove_map_clears_run_profiles_queue_onboarding(rmm):
    """RP-016/RF-20: remove_map used to leave run_profiles/queue/onboarding
    behind -- a re-import at the same map_id resurrected a run profile and a
    queue payload holding room ids from the DELETED segmentation. All three
    are per-(vacuum, map) stores in PER_MAP_STORES, same as the five it
    already cleared."""
    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    mgr.data.setdefault("run_profiles", {}).setdefault(_VAC, {})[_MAP] = {"rp_1": {"name": "Weeknight"}}
    mgr.data.setdefault("queue", {}).setdefault(_VAC, {})[_MAP] = {"queue_room_ids": [1, 2]}
    mgr.data.setdefault("onboarding", {}).setdefault(_VAC, {})[_MAP] = {"rooms_discovered": True}
    # a second map's own buckets must be left untouched
    mgr.data["run_profiles"][_VAC]["7"] = {"rp_2": {"name": "Other Map"}}

    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)
    assert removed["run_profiles_removed"] is True
    assert removed["queue_removed"] is True
    assert removed["onboarding_removed"] is True
    assert _MAP not in mgr.data["run_profiles"][_VAC]
    assert _MAP not in mgr.data["queue"][_VAC]
    assert _MAP not in mgr.data["onboarding"][_VAC]
    assert mgr.data["run_profiles"][_VAC]["7"] == {"rp_2": {"name": "Other Map"}}


def test_remove_map_leaves_sibling_grants_with_shared_ids(rmm):
    """[RC-8] Grant targets are map-scoped room IDs, so removing one map must
    never touch a sibling map's grants — even when both maps reuse the same
    numeric room IDs.

    Regression guard: an earlier cleanup loop tried to strip the removed map's
    room IDs from every other map's ``grants_access_to``. That was a no-op as
    written, but had it ever fired it would have corrupted sibling grants that
    happen to share a numeric ID with the removed map (here: map ``9`` grants
    to rooms 1/2, which are *its own* rooms, not map ``6``'s).
    """
    rm, mgr = rmm
    mgr.data["maps"] = {
        _VAC: {
            # the map being removed — its rooms use ids 1 and 2
            "6": {"rooms": {"1": {"room_id": 1}, "2": {"room_id": 2}}},
            # sibling map reuses the SAME numeric ids; its grants mean its own rooms
            "9": {
                "rooms": {
                    "1": {"room_id": 1, "grants_access_to": [2]},
                    "2": {"room_id": 2, "grants_access_to": [1]},
                }
            },
        }
    }

    rm.remove_map(vacuum_entity_id=_VAC, map_id="6")

    assert "6" not in mgr.data["maps"][_VAC]
    sibling = mgr.data["maps"][_VAC]["9"]["rooms"]
    assert sibling["1"]["grants_access_to"] == [2]
    assert sibling["2"]["grants_access_to"] == [1]


def test_discover_rooms_caches_payload(manager, hass):
    """[RC-7] discover_rooms runs discovery, caches the payload, and points the
    runtime at the active map."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    register_adapter_config(_VAC, {
        "adapter_id": "t", "source": "t",
        "entities": {"active_map": "sensor.alfred_map"},
        "discovery": {"room_list_entity": "vacuum_entity",
                      "room_list_attribute": "segments",
                      "room_id_key": "id", "room_name_key": "name"},
    })
    hass.states.async_set("sensor.alfred_map", "6")
    hass.states.async_set(_VAC, "docked",
                          {"segments": [{"id": 1, "name": "Kitchen"},
                                        {"id": 2, "name": "Bath"}]})
    rm = RoomMapManager(manager)
    payload = rm.discover_rooms(vacuum_entity_id=_VAC, map_id="6")
    assert payload["room_count"] == 2
    assert "6" in manager.data["discovery"][_VAC]
    assert manager.ensure_runtime(_VAC).active_map_id == payload.get("active_map_id")


# ---------------------------------------------------------------------------
# [RC-16] R16 — PER_MAP_STORES is the single source of truth for (key, mode, flag)
# ---------------------------------------------------------------------------

def test_rc16_adding_a_new_per_map_store_does_not_crash_remove_map(rmm, monkeypatch):
    """[RC-16] RED BEFORE THE FIX (against the 2-tuple + sibling-dict shape).

    The pre-fix code held two hand-maintained lists: PER_MAP_STORES (2-tuple) plus a
    FLAG_NAMES dict inside remove_map, indexed with a BARE subscript. Adding a 9th
    entry to PER_MAP_STORES without also editing FLAG_NAMES raised KeyError inside the
    delete loop and took remove_map down entirely, deleting NOTHING for the map the
    user was trying to remove. The comment right next to the loop told the maintainer
    the addition was safe.

    Reproduces the shape here: monkeypatch PER_MAP_STORES to include one new store
    (with no data behind it), and assert remove_map completes cleanly and returns a
    response that neither carries a phantom flag nor omits a known one.
    """
    import custom_components.eufy_vacuum.maps.map_manager as mm
    import custom_components.eufy_vacuum.rooms.room_crud as rc

    rm, mgr = rmm
    _seed_discovery(mgr, _DISCOVERED)
    rm.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    # A newly added per-map store, no data, no historical flag. Under the old shape
    # this alone would raise KeyError on the flag lookup.
    extended = mm.PER_MAP_STORES + (("some_new_store", "delete", "some_new_removed"),)
    monkeypatch.setattr(mm, "PER_MAP_STORES", extended)
    monkeypatch.setattr(rc, "PER_MAP_STORES", extended)

    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)

    # The bucket did not exist, so the flag stays False rather than True -- but the
    # key is PRESENT, because the response shape derives from the registry.
    assert removed["some_new_removed"] is False, removed
    # And the map really was removed; the loop completed instead of crashing.
    assert _MAP not in mgr.data["maps"][_VAC]


def test_rc16_the_response_shape_is_the_declared_flag_set(rmm):
    """[RC-16] The response carries EVERY declared flag as False by default, plus
    rooms_removed. Callers key off exact names, so this is a public contract test.

    Ablation: change a flag name in PER_MAP_STORES -- this goes red for the OLD name
    (missing) AND the NEW name (unexpected), so a rename cannot ship silently.
    """
    import custom_components.eufy_vacuum.maps.map_manager as mm

    rm, mgr = rmm

    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id="nope")

    declared_flags = {flag for (_k, _m, flag) in mm.PER_MAP_STORES if flag}
    expected = {"vacuum_entity_id", "map_id", "rooms_removed"} | declared_flags
    assert set(removed) == expected, (
        f"response shape drifted from PER_MAP_STORES: only in response "
        f"{set(removed) - expected}; only in registry {expected - set(removed)}"
    )
    # And the flag names themselves are the ones callers rely on.
    assert declared_flags == {
        "discovery_removed", "history_removed", "rule_status_removed",
        "run_profiles_removed", "queue_removed", "payloads_removed",
        "onboarding_removed", "active_job_cleared",
    }, sorted(declared_flags)


def test_rc17_remove_map_clears_the_payloads_bucket(rmm):
    """[RC-17] `payloads` was a per-map store this registry went a release without.

    `core/manager.py` writes `queue` and `payloads` on ADJACENT LINES, keyed by the same
    `str(map_id)`. RP-016 registered the first and missed its twin, so every delete left
    a payload behind. Found on a live install: one vacuum carried `payloads` for maps 6,
    7, 11 and 12 while `maps` held only 7, 11 and 12.

    It is the QUIET half of the pair, which is why it survived unnoticed: `queue` has
    visible consequences, while `payloads` is only read back by an addressed lookup
    (`get_payload_state`), so a survivor sits inert until a future map reaches the same
    id. remove_map already spells out why that matters, for `rejected_rooms` — "Eufy
    only ever rolls map ids FORWARD, so an id is not gone for good" — and that argument
    was applied to one store and not its neighbour.

    ABLATION: drop the `payloads` row from PER_MAP_STORES and this goes red, while
    [RC-16]'s contract assertion goes red on the flag — the registry row and the public
    response are the same change seen twice.
    """
    rm, mgr = rmm

    mgr.data.setdefault("payloads", {}).setdefault(_VAC, {})[_MAP] = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "payload": {"rooms": []},
    }
    mgr.data["payloads"][_VAC]["other_map"] = {"map_id": "other_map"}

    removed = rm.remove_map(vacuum_entity_id=_VAC, map_id=_MAP)

    assert removed["payloads_removed"] is True
    assert _MAP not in mgr.data["payloads"][_VAC], "the deleted map's payload survived"
    assert "other_map" in mgr.data["payloads"][_VAC], (
        "a sibling map's payload must be untouched — the sweep is per (vacuum, map)"
    )
