"""Unit tests for maps/map_manager.py — pure per-vacuum map-bucket storage ops.

Coverage targets
----------------
[MAP-1]  ensure_map_bucket creates and returns the bucket shape.
[MAP-2]  save_map_discovery_snapshot stores discovery metadata.
[MAP-3]  get_map_bucket returns the bucket, else an empty default.
[MAP-4]  get_vacuum_maps_summary counts maps + enabled/disabled rooms.
[MAP-5]  rebuild_map_bucket builds rooms, preserves settings, drops stale, summarizes.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.maps.map_manager import (
    ensure_map_bucket,
    get_map_bucket,
    get_vacuum_maps_summary,
    rebuild_map_bucket,
    save_map_discovery_snapshot,
)


_VAC = "vacuum.alfred"


def test_ensure_map_bucket():
    """[MAP-1]"""
    data: dict = {}
    bucket = ensure_map_bucket(data=data, vacuum_entity_id=_VAC, map_id=6)
    assert bucket["map_id"] == "6"
    assert bucket == data["maps"][_VAC]["6"]
    assert set(bucket) >= {"metadata", "rooms", "summary"}


def test_save_discovery_snapshot():
    """[MAP-2]"""
    data: dict = {}
    save_map_discovery_snapshot(
        data=data, vacuum_entity_id=_VAC, map_id="6",
        discovery_payload={"active_map_id": "6", "room_count": 3, "rooms": [{"room_id": 1}]})
    meta = data["maps"][_VAC]["6"]["metadata"]
    assert meta["last_discovery"]["room_count"] == 3
    assert meta["discovered_rooms"] == [{"room_id": 1}]


def test_get_map_bucket():
    """[MAP-3]"""
    data: dict = {}
    ensure_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="6")
    assert get_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="6")["map_id"] == "6"
    # absent → empty default
    empty = get_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="99")
    assert empty["rooms"] == {} and empty["map_id"] == "99"


def test_vacuum_maps_summary():
    """[MAP-4]"""
    data: dict = {}
    b = ensure_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="6")
    b["rooms"] = {"1": {"enabled": True}, "2": {"enabled": False}}
    # DR-MAP-2: a deliberately stale cached summary -- enabled/disabled counts
    # must be derived live from rooms (1/1), not read from this cache (0/2).
    b["summary"] = {"enabled_count": 0, "disabled_count": 2}
    summary = get_vacuum_maps_summary(data=data, vacuum_entity_id=_VAC)
    assert summary["map_count"] == 1
    assert summary["maps"][0]["room_count"] == 2
    assert summary["maps"][0]["enabled_room_count"] == 1
    assert summary["maps"][0]["disabled_room_count"] == 1


def test_rebuild_map_bucket():
    """[MAP-5]"""
    data: dict = {}
    # seed an existing room with custom settings + a stale room
    b = ensure_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="6")
    b["rooms"] = {
        "1": {"room_id": 1, "name": "Old Kitchen", "enabled": False, "clean_mode": "mop"},
        "9": {"room_id": 9, "name": "Stale"},
    }
    result = rebuild_map_bucket(
        data=data, vacuum_entity_id=_VAC, map_id="6",
        discovered_rooms=[{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Bath"}])
    rooms = result["rooms"]
    assert set(rooms) == {"1", "2"}           # stale room 9 dropped
    assert rooms["1"]["enabled"] is False     # preserved
    assert rooms["1"]["clean_mode"] == "mop"  # preserved
    assert rooms["2"]["enabled"] is True      # new room defaults
    assert result["summary"]["enabled_count"] == 1
    assert result["summary"]["disabled_count"] == 1


def test_rebuild_map_bucket_preserves_color():
    """[MAP-5b] a map rebuild must not drop a per-room map fill color override."""
    data: dict = {}
    b = ensure_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="6")
    b["rooms"] = {"1": {"room_id": 1, "name": "Kitchen", "color": "#00ff00"}}
    result = rebuild_map_bucket(
        data=data, vacuum_entity_id=_VAC, map_id="6",
        discovered_rooms=[{"room_id": 1, "name": "Kitchen"}])
    assert result["rooms"]["1"]["color"] == "#00ff00"


def test_rebuild_map_bucket_preserves_configured_flags():
    """[MAP-5c] BUG-A: a rebuild must carry the setup-approval flags forward — else
    rebuilt rooms read as unconfigured and get filtered out of HA entity creation +
    flagged by the drift tracker. A previously-configured room keeps
    is_configured/configured_at; a room missing the key (e.g. from an older rebuild)
    defaults is_configured True (a saved map-bucket room is an approved room)."""
    data: dict = {}
    b = ensure_map_bucket(data=data, vacuum_entity_id=_VAC, map_id="6")
    b["rooms"] = {
        "1": {"room_id": 1, "name": "Kitchen",
              "is_configured": True, "configured_at": "2026-01-01T00:00:00Z"},
        "2": {"room_id": 2, "name": "Bath"},  # no is_configured (e.g. a prior buggy rebuild)
    }
    result = rebuild_map_bucket(
        data=data, vacuum_entity_id=_VAC, map_id="6",
        discovered_rooms=[{"room_id": 1, "name": "Kitchen"}, {"room_id": 2, "name": "Bath"}])
    rooms = result["rooms"]
    assert rooms["1"]["is_configured"] is True
    assert rooms["1"]["configured_at"] == "2026-01-01T00:00:00Z"   # preserved
    assert rooms["2"]["is_configured"] is True                      # defaults True (saved = approved)
