"""Tests for diagnostics.py — the Download Diagnostics dump.

The dump is driven through a small fake manager so the tests exercise the
diagnostics logic (entity-resolution table, active-map derivation, the
no-active-map branch, redaction) rather than the whole integration.

Coverage targets
----------------
[DIAG-1]  Full path: entity_resolution resolves each role to {entity_id,
          exists, state}; active_map_id derived from the sensor; managed_rooms
          + dashboard_snapshot included; map_state_source refreshed.
[DIAG-2]  No active map (the common onboarding failure): active_map_id is None,
          managed_rooms is None + an explanatory note, dashboard_snapshot is
          None, and the map_state_source refresh is NOT called.
[DIAG-3]  Secrets in entry data are redacted; entity_ids/map_ids are kept.
[DIAG-4]  Missing runtime manager → a clean error block, no crash.
[DIAG-5]  Malformed (non-string) entity value in the adapter map → no crash; the
          role resolves to exists=False.
[DIAG-6]  Brand-agnostic rooms: a vacuum with NO active_map sensor (Roborock) but
          a stored map still dumps that map's rooms (managed_rooms_by_map).
[DIAG-7]  Slimming: per-item upkeep `guide` stripped, managed-rooms `summary`
          stripped, vacuum_state.rooms (== segments) dropped.
[DIAG-8]  self_check interprets the scalar/Tuya transport (no active_map entity
          but rooms via segments) into plain-English status lines, surfaced first.
[DIAG-9]  self_check on a native-brand integration (Roborock): rooms come from its
          own integration + the raw map decodes to a raster -> reports rooms/map
          WORKING (brand-named), not the Eufy-shaped 'unknown/unavailable/no'.
[DIAG-10] Same native brand, map not yet decoded + brand string absent: rooms still
          read working, map reads 'pending', phrasing degrades to generic.
[DIAG-11] self_check surfaces a completion_health warning (missing job_active binary
          on a require_job_active_clear brand) at the top as a warnings entry.
[DIAG-12] self_check with no completion_health problem → empty warnings list.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eufy_vacuum.const import (
    CONF_NOTES,
    CONF_VACUUM_ENTITY_ID,
    DATA_RUNTIME,
    DOMAIN,
)
from custom_components.eufy_vacuum.diagnostics import (
    _self_check,
    async_get_config_entry_diagnostics,
)

VACUUM = "vacuum.alfred"


class _FakeManager:
    """Minimal stand-in for EufyVacuumManager covering the methods diagnostics calls."""

    def __init__(self, *, caps, maps, rooms, upkeep, dashboard):
        self._caps = caps
        self._maps = maps
        self._rooms = rooms
        self._upkeep = upkeep
        self._dashboard = dashboard
        self.refreshed: list[tuple[str, str]] = []
        self.dashboard_calls = 0

    def get_known_vacuum_ids(self) -> list[str]:
        return [VACUUM]

    def get_vacuum_capabilities(self, *, vacuum_entity_id, refresh=False):
        return self._caps

    def get_vacuum_maps(self, *, vacuum_entity_id):
        return self._maps

    def get_managed_rooms(self, *, vacuum_entity_id, map_id):
        return self._rooms

    def get_upkeep_snapshot(self, *, vacuum_entity_id):
        return self._upkeep

    async def async_refresh_map_state_source(self, *, vacuum_entity_id, map_id):
        self.refreshed.append((vacuum_entity_id, map_id))

    def get_dashboard_snapshot(self, *, vacuum_entity_id, map_id):
        self.dashboard_calls += 1
        return self._dashboard


def _caps() -> dict[str, Any]:
    return {
        "entities": {
            "vacuum": VACUUM,
            "active_map": "sensor.alfred_active_map",
            "live_map": "camera.alfred_map",
        },
        "supports_room_clean": True,
        "model": "T2351",
    }


def _make_manager() -> _FakeManager:
    return _FakeManager(
        caps=_caps(),
        maps={
            "vacuum_entity_id": VACUUM,
            "map_count": 1,
            "maps": [{"map_id": "6", "room_count": 5}],
        },
        # `summary` re-lists the rooms — the dump should strip it.
        rooms={
            "rooms": [{"room_id": 1, "name": "Kitchen"}],
            "summary": {"enabled_count": 1},
        },
        # `guide` is static boilerplate — the dump should strip it per item.
        upkeep={
            "highest_priority_status": "good",
            "replacement_items": [
                {"component": "filter", "status": "good", "guide": {"steps": ["x"]}}
            ],
            "maintenance_items": [
                {"component": "filter", "status": "good", "guide": {"steps": ["x"]}}
            ],
        },
        dashboard={"snapshot": "ok"},
    )


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Vacuum Agent",
        # password is synthetic — proves the redactor strips secrets while
        # keeping the (non-secret) vacuum entity id.
        data={
            CONF_VACUUM_ENTITY_ID: VACUUM,
            "password": "supersecret",
            CONF_NOTES: "eufy login pw: hunter2",
        },
        options={},
        version=1,
    )


async def test_diagnostics_full(hass):
    """[DIAG-1][DIAG-3] Full dump with a resolved active map."""
    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager

    hass.states.async_set("sensor.alfred_active_map", "6")
    hass.states.async_set("camera.alfred_map", "idle")
    hass.states.async_set(
        VACUUM,
        "docked",
        {
            "segments": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hall"}],
            # byte-identical to segments — the dump should drop it.
            "rooms": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hall"}],
        },
    )

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    vac = diag["vacuums"][0]
    res = vac["entity_resolution"]

    assert res["active_map"] == {
        "entity_id": "sensor.alfred_active_map",
        "exists": True,
        "state": "6",
    }
    assert res["live_map"]["exists"] is True
    assert vac["active_map_id"] == "6"
    assert vac["vacuum_state"]["segment_count"] == 2
    # [DIAG-7] slimming — the `summary` re-list is stripped (this equality excludes
    # it), the per-item upkeep `guide` is gone, and vacuum_state.rooms is dropped.
    assert vac["managed_rooms_by_map"] == {
        "6": {"rooms": [{"room_id": 1, "name": "Kitchen"}]}
    }
    up = vac["upkeep_snapshot"]
    assert "guide" not in up["replacement_items"][0]
    assert "guide" not in up["maintenance_items"][0]
    assert up["replacement_items"][0]["status"] == "good"  # the useful bit stays
    assert "rooms" not in vac["vacuum_state"]
    assert "segments" in vac["vacuum_state"]

    assert vac["capabilities"]["supports_room_clean"] is True

    # [DIAG-1] read-only: the side-effecting dashboard snapshot is NOT collected,
    # so no room-rollover events fire and map_state_source is never refreshed.
    assert "dashboard_snapshot" not in vac
    assert manager.dashboard_calls == 0
    assert manager.refreshed == []

    # [DIAG-3] secrets redacted (incl. the free-text notes field); entity id kept.
    assert diag["entry"]["data"]["password"] == "**REDACTED**"
    assert diag["entry"]["data"][CONF_NOTES] == "**REDACTED**"
    assert diag["entry"]["data"][CONF_VACUUM_ENTITY_ID] == VACUUM


async def test_diagnostics_no_active_map(hass):
    """[DIAG-2] The common onboarding failure: active_map sensor blank, nothing imported."""
    manager = _FakeManager(
        caps=_caps(),
        maps={"vacuum_entity_id": VACUUM, "map_count": 0, "maps": []},
        rooms={},
        upkeep={"highest_priority_status": "good"},
        dashboard={},
    )
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager

    # active_map sensor reports a sentinel (eufy-clean hasn't received a map yet);
    # the live_map camera entity isn't created at all.
    hass.states.async_set("sensor.alfred_active_map", "unknown")
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    vac = diag["vacuums"][0]

    assert vac["entity_resolution"]["active_map"]["state"] == "unknown"
    assert vac["entity_resolution"]["live_map"]["exists"] is False
    assert vac["active_map_id"] is None
    assert vac["managed_rooms_by_map"] == {}
    assert "managed_rooms_note" in vac
    # Read-only + no map: no dashboard snapshot key, no refresh, no event fire.
    assert "dashboard_snapshot" not in vac
    assert manager.dashboard_calls == 0
    assert manager.refreshed == []


async def test_diagnostics_no_manager(hass):
    """[DIAG-4] Missing runtime manager yields a clean error block, not a crash."""
    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "error" in diag
    assert "vacuums" not in diag
    # entry block (with redaction) is still present.
    assert diag["entry"]["data"]["password"] == "**REDACTED**"


async def test_diagnostics_malformed_entities(hass):
    """[DIAG-5] A non-string entity value in the adapter map must not crash the dump."""
    caps = _caps()
    caps["entities"]["active_map"] = 12345  # malformed — an int, not an entity id
    manager = _FakeManager(caps=caps, maps={}, rooms={}, upkeep={}, dashboard={})
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    # Must not raise — the dump degrades the bad role to exists=False.
    diag = await async_get_config_entry_diagnostics(hass, entry)
    res = diag["vacuums"][0]["entity_resolution"]["active_map"]
    assert res == {"entity_id": None, "exists": False, "state": None}
    assert diag["vacuums"][0]["active_map_id"] is None


async def test_diagnostics_rooms_without_active_map_sensor(hass):
    """[DIAG-6] Roborock-style: no active_map sensor, but a stored map still dumps rooms."""
    manager = _FakeManager(
        caps={"entities": {"vacuum": VACUUM}},  # no active_map role at all
        maps={
            "vacuum_entity_id": VACUUM,
            "map_count": 1,
            "maps": [{"map_id": "Main floor", "room_count": 10}],
        },
        rooms={"room_count": 10},
        upkeep={},
        dashboard={},
    )
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    vac = diag["vacuums"][0]

    # No active_map sensor → active_map_id is None, but the stored map's rooms
    # are still dumped (the brand-agnostic fix).
    assert vac["active_map_id"] is None
    assert vac["managed_rooms_by_map"] == {"Main floor": {"room_count": 10}}
    assert "managed_rooms_note" not in vac


async def test_diagnostics_self_check_attribute_mode(hass):
    """[DIAG-8] self_check interprets the scalar/Tuya transport.

    No active_map entity, but the room list is present in the vacuum's `segments`
    attribute (Peter's X10 Pro Omni). The summary should read: attribute-mode
    transport, rooms importable, map image needs the fork, model resolved — and
    appear as the first block after the vacuum id."""
    caps = {
        "entities": {"vacuum": VACUUM},  # NO active_map entity (scalar transport)
        "detected_model": "T2351",
        "model_family": "x10",
        "supports_rooms": True,
        "supports_segments": True,
        "supports_active_map": False,
    }
    manager = _FakeManager(
        caps=caps,
        maps={"vacuum_entity_id": VACUUM, "map_count": 1,
              "maps": [{"map_id": "main", "room_count": 2}]},
        rooms={"rooms": [{"room_id": 1, "name": "Kitchen"}]},
        upkeep={"highest_priority_status": "good"},
        dashboard={},
    )
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {
        "segments": [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hall"}],
    })

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    vac = diag["vacuums"][0]
    sc = vac["self_check"]

    assert "attribute-mode" in sc["transport"]
    assert sc["rooms_importable"] == "yes"
    assert "segments attribute" in sc["room_control"]
    assert "eufy-clean fork" in sc["map_image"]
    assert sc["model_detection"] == "T2351 → x10"
    # Surfaced as the first signal, right after the id.
    assert list(vac.keys())[:2] == ["vacuum_entity_id", "self_check"]


def test_self_check_roborock_native_brand():
    """[DIAG-9] Roborock: rooms come from its own integration (no active_map sensor,
    no `segments` attribute) and the raw map decodes to a raster. The summary must
    report rooms + map WORKING — not the Eufy-shaped 'unknown / unavailable / no'
    that the old transport-only heuristic produced for a device whose rooms work.

    Pure function of `out` (the exact shape _vacuum_diagnostics assembles for Ivy),
    so no hass / adapter registry needed."""
    out = {
        "capabilities": {
            "detected_model": "roborock.vacuum.s6",
            "model_family": "generic",
            "supports_room_clean": True,   # true "can clean rooms" capability
            "supports_rooms": False,       # Eufy-shaped exposure flag — False here
        },
        "entity_resolution": {"active_map": {"exists": False}},  # no active_map sensor
        "vacuum_state": {"segment_count": None},                 # no Eufy segments attr
        "adapter": {"brand": "Roborock"},
        "maps": {"map_count": 1, "maps": [{"map_id": "Main floor", "room_count": 10}]},
        "managed_rooms_by_map": {"Main floor": {"room_count": 10}},
        "roborock_geometry_drift": {"present": True, "aligned": True},
        "active_map_id": None,
    }

    sc = _self_check(out)

    # transport: native-integration, brand-named — NOT "unknown".
    assert "native integration" in sc["transport"] and "Roborock" in sc["transport"]
    assert "unknown" not in sc["transport"]
    # rooms: available via the brand integration, importable — NOT "unavailable".
    assert sc["room_control"].startswith("available") and "10 rooms" in sc["room_control"]
    assert sc["rooms_importable"] == "yes"
    # map: decoded raster available — NOT "unavailable / needs the fork".
    assert "decoded" in sc["map_image"] and "unavailable" not in sc["map_image"]
    assert "eufy-clean fork" not in sc["map_image"]
    assert sc["model_detection"] == "roborock.vacuum.s6 → generic"
    assert "Roborock device" in sc["note"]


def test_self_check_native_brand_map_pending():
    """[DIAG-10] Same native brand but the raw map hasn't decoded yet (no drift block):
    rooms still read as working, map reads 'pending' (not a Eufy-fork message), and a
    missing brand string degrades to generic 'native integration' phrasing."""
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": False}},
        "vacuum_state": {"segment_count": None},
        # no "adapter" key -> brand unknown
        "maps": {"map_count": 1, "maps": [{"map_id": "Main floor", "room_count": 7}]},
        "managed_rooms_by_map": {"Main floor": {"room_count": 7}},
        "active_map_id": None,
    }

    sc = _self_check(out)

    assert "native integration" in sc["transport"]
    assert sc["room_control"].startswith("available") and "7 rooms" in sc["room_control"]
    assert sc["rooms_importable"] == "yes"
    assert "pending" in sc["map_image"] and "eufy-clean fork" not in sc["map_image"]
    assert "Native-integration device" in sc["note"]


def test_self_check_surfaces_missing_job_active_warning():
    """[DIAG-11] a require_job_active_clear brand whose job_active binary is missing
    (completion_health.warning) surfaces as a loud warnings entry — the tripwire for
    an upstream capability-gating that would silently strand every run."""
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": False}},
        "vacuum_state": {"segment_count": None},
        "adapter": {"brand": "roborock"},
        "maps": {"map_count": 1, "maps": [{"map_id": "Main", "room_count": 5}]},
        "managed_rooms_by_map": {"Main": {"room_count": 5}},
        "completion_health": {
            "requires_job_active_clear": True,
            "job_active_entity": "binary_sensor.ivy_job_active",
            "job_active_present": False,
            "warning": "Completion requires the job-active binary "
                       "(binary_sensor.ivy_job_active) but it is missing — EVERY run "
                       "will strand (never finalize). Check the upstream integration "
                       "didn't drop this entity.",
        },
    }

    sc = _self_check(out)

    assert len(sc["warnings"]) == 1
    assert "EVERY run will strand" in sc["warnings"][0]


def test_self_check_no_warning_when_healthy():
    """[DIAG-12] no completion_health problem → an empty warnings list."""
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": True}},
        "vacuum_state": {"segment_count": None},
        "completion_health": {"requires_job_active_clear": False, "job_active_present": False},
    }
    assert _self_check(out)["warnings"] == []
