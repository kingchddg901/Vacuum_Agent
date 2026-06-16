"""Tests for room-identity reconciliation wired through RoomMapManager.

- discover_rooms attaches a reconciliation block (detection).
- reconcile_room applies (migrate) or dismisses (ignore) the identity shifts.

reconcile_room calls only no-op manager hooks (_refresh_room_derived_state,
_notify_rooms_updated, _room_history_cache_ready.discard) on a MagicMock, plus
the real ensure/get map-bucket helpers — so the MagicMock manager fixture (as in
test_room_crud.py) exercises it end-to-end. The discovery-detection test needs a
real manager + hass to read entity states.

Coverage targets
----------------
[RR-1] discover_rooms attaches reconciliation reviews for an id change.
[RR-2] migrate re-keys the saved rooms onto new ids + preserves settings.
[RR-3] migrate rewrites access-graph grants through the id remap.
[RR-4] migrate drops stale id-keyed rule-status snapshots.
[RR-5] ignore stamps a dismissal and leaves stored data untouched.
[RR-6] an unknown action raises.
[RR-7] migrate with no cached discovery must NOT wipe the saved rooms.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager


_VAC = "vacuum.ivy"
_MAP = "Main floor"


@pytest.fixture
def rmm():
    mgr = MagicMock()
    mgr.data = {}
    mgr.ensure_runtime.return_value = MagicMock()
    return RoomMapManager(mgr), mgr


def _seed_saved(mgr, rooms: dict[str, dict]):
    mgr.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "map_id": _MAP,
        "metadata": {},
        "summary": {},
        "rooms": rooms,
    }


def _seed_discovery(mgr, rooms: list[dict]):
    mgr.data.setdefault("discovery", {}).setdefault(_VAC, {})[_MAP] = {"rooms": rooms}


# --- detection (real manager + hass) ----------------------------------------


def test_discover_attaches_reconciliation(manager, hass):
    """[RR-1]"""
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code",
        "entities": {"active_map": "sensor.ivy_map"},
        "discovery": {
            "room_list_entity": "vacuum_entity",
            "room_list_attribute": "segments",
            "room_id_key": "id",
            "room_name_key": "name",
        },
    })
    # Saved: KITCHEN at old id 16.
    manager.data.setdefault("maps", {}).setdefault(_VAC, {})[_MAP] = {
        "map_id": _MAP, "metadata": {}, "summary": {},
        "rooms": {"16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen"}},
    }
    hass.states.async_set("sensor.ivy_map", _MAP)
    # Discovery now reports KITCHEN at a new id (27) — the re-segment case.
    hass.states.async_set(_VAC, "docked", {"segments": [{"id": 27, "name": "KITCHEN"}]})

    payload = RoomMapManager(manager).discover_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    reviews = payload["reconciliation"]["reviews"]
    assert reviews == [
        {"kind": "id_changed", "slug": "kitchen", "name": "KITCHEN", "old_id": 16, "new_id": 27}
    ]


# --- migrate ----------------------------------------------------------------


def test_reconcile_migrate_rekeys_and_preserves(rmm):
    """[RR-2] + [RR-3]"""
    rm, mgr = rmm
    _seed_saved(mgr, {
        "16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen",
               "profile_name": "deep_clean", "grants_access_to": [17], "enabled": True},
        "17": {"room_id": 17, "name": "Dining Room", "slug": "dining_room",
               "grants_access_to": [], "enabled": True},
    })
    _seed_discovery(mgr, [
        {"room_id": 27, "map_id": _MAP, "name": "KITCHEN", "slug": "kitchen"},
        {"room_id": 18, "map_id": _MAP, "name": "Dining Room", "slug": "dining_room"},
    ])

    result = rm.reconcile_room(vacuum_entity_id=_VAC, map_id=_MAP, action="migrate")

    rooms = mgr.data["maps"][_VAC][_MAP]["rooms"]
    assert set(rooms) == {"27", "18"}
    assert rooms["27"]["profile_name"] == "deep_clean"   # durable setting carried
    assert rooms["27"]["room_id"] == 27
    assert rooms["27"]["grants_access_to"] == [18]        # grant rewritten 17 -> 18
    assert result["action"] == "migrate"
    assert result["id_remap"] == {"16": 27, "17": 18}
    assert result["migrated_room_count"] == 2


def test_reconcile_migrate_drops_stale_rule_status(rmm):
    """[RR-4] transient id-keyed rule-status snapshots for migrated ids are dropped."""
    rm, mgr = rmm
    _seed_saved(mgr, {
        "16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen", "grants_access_to": []},
    })
    _seed_discovery(mgr, [{"room_id": 27, "map_id": _MAP, "name": "KITCHEN", "slug": "kitchen"}])
    mgr.data.setdefault("room_rule_status", {}).setdefault(_VAC, {})[_MAP] = {
        "16": {"last_result": "allowed"},
    }

    rm.reconcile_room(vacuum_entity_id=_VAC, map_id=_MAP, action="migrate")

    assert "16" not in mgr.data["room_rule_status"][_VAC][_MAP]


# --- ignore -----------------------------------------------------------------


def test_reconcile_ignore_dismisses_and_preserves(rmm):
    """[RR-5]"""
    rm, mgr = rmm
    _seed_saved(mgr, {
        "16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen", "grants_access_to": []},
    })
    _seed_discovery(mgr, [{"room_id": 27, "map_id": _MAP, "name": "KITCHEN", "slug": "kitchen"}])

    result = rm.reconcile_room(vacuum_entity_id=_VAC, map_id=_MAP, action="ignore")

    assert result["action"] == "ignore"
    metadata = mgr.data["maps"][_VAC][_MAP]["metadata"]
    assert "reconciliation_dismissed_at" in metadata
    # Stored data untouched — old id stays.
    assert set(mgr.data["maps"][_VAC][_MAP]["rooms"]) == {"16"}


def test_reconcile_unknown_action_raises(rmm):
    """[RR-6]"""
    rm, mgr = rmm
    _seed_saved(mgr, {"16": {"room_id": 16, "slug": "kitchen", "name": "KITCHEN"}})
    with pytest.raises(ValueError):
        rm.reconcile_room(vacuum_entity_id=_VAC, map_id=_MAP, action="bogus")


def test_reconcile_migrate_empty_discovery_preserves(rmm):
    """[RR-7] migrate with no cached discovery must NOT wipe saved rooms."""
    rm, mgr = rmm
    _seed_saved(mgr, {
        "16": {"room_id": 16, "name": "KITCHEN", "slug": "kitchen", "grants_access_to": []},
    })
    # No discovery cached for this map.
    result = rm.reconcile_room(vacuum_entity_id=_VAC, map_id=_MAP, action="migrate")

    assert result["skipped"] == "no_discovery"
    assert result["migrated_room_count"] == 0
    # Saved rooms untouched.
    assert set(mgr.data["maps"][_VAC][_MAP]["rooms"]) == {"16"}
