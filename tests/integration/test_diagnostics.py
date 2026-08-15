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
[DIAG-13] an unrecognized cleaning_area unit surfaces as a loud warning — the guardrail for a mis-declared unit.
[DIAG-14] active_map entity EXISTS but its state is a sentinel (`unavailable`) and no
          rooms are visible -> rooms_importable 'no', a loud warning, and a note that
          explains it, instead of the old "maps, rooms and the live map all work".
[DIAG-15] active_map entity exists WITH a real map id -> still reads fully working
          (guards against over-correcting DIAG-14 into a false negative).
[DIAG-16] RP-039/RF-33: entry.title is redacted like entry.data/entry.options.
[DIAG-17] RP-039/RF-33: a collector's repr(err) is masked (_redact) before it
          lands in the dump.
[DIAG-18] RP-039/RF-33: _self_check's generic scan surfaces every collector's
          "<name>_error" / nested {"error": ...} failure, not just the two
          hand-picked warning keys.
[DIAG-19] RP-039/RF-33 (HW-DIAG-1 fix 2): job_active_present resolves via a LIVE
          hass.states lookup, not the stored (possibly-stale) capabilities
          snapshot's entity_resolution.
[DIAG-20] RP-039/RF-33 (HW-DIAG-1 fix 1): the job-active warning no longer claims
          "EVERY run will strand" for a state where no run can even dispatch.
[DIAG-21] RP-039/RF-33: get_vacuum_capabilities_snapshot never writes, even with
          no stored snapshot yet. [DIAG-21b] the diagnostics capabilities
          collector itself is inert end-to-end (isolated, via a stub, from the
          SEPARATE get_upkeep_snapshot non-inertness). [DIAG-21c] RF-33 cont'd:
          get_upkeep_snapshot itself (plus its internal per-component
          get_maintenance_remaining call) fixed the same way — proven WITHOUT
          the stub, end-to-end.
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

    def get_vacuum_capabilities_snapshot(self, *, vacuum_entity_id):
        """RP-039/RF-33: diagnostics now calls this (genuinely read-only) instead
        of get_vacuum_capabilities(refresh=False) -- the fake returns the same
        canned caps either way, since it never actually detects/writes."""
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
        # REGISTERED is reported beside EXISTS so a dump can tell "never created"
        # from "correct ID, entity absent" — the distinction issue #46 turned on.
        "registered": False,
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
    assert res == {
        "entity_id": None,
        "exists": False,
        "registered": False,
        "state": None,
    }
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
    an upstream capability-gating that would silently strand every run.

    RP-039/RF-33 (HW-DIAG-1 fix 1): the warning text itself was reworded away from
    "EVERY run will strand" (a run-time-failure framing for a state where no run
    can even be DISPATCHED) toward "device appears disconnected" — this fixture
    mirrors what _vacuum_diagnostics now actually builds.
    """
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
                       "(binary_sensor.ivy_job_active) but it is missing — the "
                       "device appears disconnected from Home Assistant right now "
                       "(no run can even be dispatched in this state). Check it's "
                       "online and wake it (e.g. a state refresh); if this persists, "
                       "the upstream integration may have dropped the entity.",
        },
    }

    sc = _self_check(out)

    assert len(sc["warnings"]) == 1
    assert "device appears disconnected" in sc["warnings"][0]
    assert "EVERY run will strand" not in sc["warnings"][0]


def test_self_check_no_warning_when_healthy():
    """[DIAG-12] no completion_health problem → an empty warnings list.

    active_map carries a real map id: "exists" alone is NOT a healthy device (see
    DIAG-14), so a genuinely-healthy fixture has to supply the state too.
    """
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": True, "state": "3"}},
        "vacuum_state": {"segment_count": None},
        "completion_health": {"requires_job_active_clear": False, "job_active_present": False},
    }
    assert _self_check(out)["warnings"] == []


def test_self_check_active_map_present_but_unavailable():
    """[DIAG-14] active_map exists but reports `unavailable` and nothing else shows rooms.

    The real report this comes from (issue #44, Eufy Omni C20): the vacuum
    integration never delivers map/room data, so the sensor is created but never
    gets a value. Keying on existence made the self-check claim everything worked
    while the importer refused the device — the user reasonably read that as a
    Vacuum Agent bug.
    """
    out = {
        "capabilities": {"supports_room_clean": True, "supports_rooms": True},
        "entity_resolution": {
            "active_map": {
                "entity_id": "sensor.ferraye_active_map",
                "exists": True,
                "state": "unavailable",
            }
        },
        "vacuum_state": {"segment_count": 0},
        "maps": {"maps": []},
        "managed_rooms_by_map": {},
    }
    sc = _self_check(out)

    assert sc["rooms_importable"] == "no"
    assert "all work" not in sc["note"]
    assert "unavailable" in sc["note"]
    assert "nothing to configure" in sc["note"]
    assert any(
        "sensor.ferraye_active_map" in w and "cannot be imported" in w
        for w in sc["warnings"]
    )
    # Still classified as the full MQTT transport — the sensor's PRESENCE is a valid
    # transport tell even when its value is missing.
    assert "full (novel / MQTT)" in sc["transport"]
    assert "unavailable" in sc["map_image"]


def test_self_check_active_map_with_real_id_still_healthy():
    """[DIAG-15] a real map id keeps the working verdict — no over-correction."""
    out = {
        "capabilities": {"supports_room_clean": True, "supports_rooms": True},
        "entity_resolution": {
            "active_map": {
                "entity_id": "sensor.alfred_active_map",
                "exists": True,
                "state": "12",
            }
        },
        "vacuum_state": {"segment_count": 0},
    }
    sc = _self_check(out)

    assert sc["rooms_importable"] == "yes"
    assert sc["note"] == "Standard transport — maps, rooms and the live map all work."
    assert sc["room_control"] == "available (via active map)"
    assert sc["warnings"] == []


def test_self_check_surfaces_area_unit_warning():
    """[DIAG-13] an unrecognized cleaning_area unit (area_units.warning) surfaces as a loud
    warning — the guardrail for a user-toggled or mis-declared unit."""
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": True}},
        "vacuum_state": {"segment_count": None},
        "area_units": {
            "detected_unit": "widgets", "recognized": False,
            "warning": "cleaning_area unit 'widgets' is unrecognized — the value is used AS-IS "
                       "(assumed m²); if it is an imperial unit the stored area will be wrong.",
        },
    }
    assert any("unrecognized" in w for w in _self_check(out)["warnings"])


async def test_diagnostics_area_units_detects_ft2(hass):
    """[DIAG-14] area_units reports the CURRENTLY detected cleaning_area unit + normalized m²
    (imperial HA presents Eufy's in ft²; user-toggleable → read live, converted here)."""
    from custom_components.eufy_vacuum.diagnostics import _vacuum_diagnostics

    manager = _FakeManager(
        caps={"entities": {"vacuum": VACUUM, "cleaning_area": "sensor.alfred_cleaning_area"}},
        maps={}, rooms={}, upkeep={}, dashboard={},
    )
    hass.states.async_set("sensor.alfred_cleaning_area", "53.82", {"unit_of_measurement": "ft²"})
    au = _vacuum_diagnostics(hass, manager, VACUUM)["area_units"]
    assert au["detected_unit"] == "ft²" and au["converted"] is True
    assert round(au["normalized_m2"], 2) == 5.0
    assert "warning" not in au  # ft² is recognized


async def test_diagnostics_area_units_unknown_warns(hass):
    """[DIAG-15] an unrecognized cleaning_area unit warns (the silent-miss guard)."""
    from custom_components.eufy_vacuum.diagnostics import _vacuum_diagnostics

    manager = _FakeManager(
        caps={"entities": {"vacuum": VACUUM, "cleaning_area": "sensor.alfred_cleaning_area"}},
        maps={}, rooms={}, upkeep={}, dashboard={},
    )
    hass.states.async_set("sensor.alfred_cleaning_area", "12.0", {"unit_of_measurement": "widgets"})
    au = _vacuum_diagnostics(hass, manager, VACUUM)["area_units"]
    assert au["recognized"] is False and "unrecognized" in au["warning"]


# ---------------------------------------------------------------------------
# RP-039/RF-33 additions
# ---------------------------------------------------------------------------

async def test_diagnostics_entry_title_redacted(hass):
    """[DIAG-16] entry.title is free-text + user-editable (same class as "notes")
    and must be redacted like entry.data/entry.options -- it never was before."""
    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN,
        title="hunter2 is my vacuum's wifi password",
        data={CONF_VACUUM_ENTITY_ID: VACUUM}, options={}, version=1,
    )
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["title"] == "**REDACTED**"


async def test_diagnostics_repr_err_sites_are_redacted(hass):
    """[DIAG-17] a collector that raises must have its repr(err) masked before it
    lands in the dump -- async_redact_data only matches by DICT KEY name, so none
    of the nine (now ten, counting entry.title separately) repr(err) sinks were
    ever covered by it; a token embedded in an exception's own message/args would
    otherwise reach the dump verbatim."""
    class _BoomManager(_FakeManager):
        def get_vacuum_maps(self, *, vacuum_entity_id):
            raise RuntimeError("upstream call failed: token=abc123secret")

    manager = _BoomManager(caps=_caps(), maps={}, rooms={}, upkeep={}, dashboard={})
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    vac = diag["vacuums"][0]
    assert "maps_error" in vac
    assert "abc123secret" not in vac["maps_error"]
    assert "«redacted»" in vac["maps_error"]


def test_self_check_generic_scan_surfaces_uncaught_collector_errors():
    """[DIAG-18] _self_check used to build its warnings list from ONLY
    completion_health.warning and area_units.warning -- every OTHER collector's
    {"error": repr(err)} failure shape (capabilities_error, maps_error,
    upkeep_snapshot_error, roborock_geometry_drift_error, plus a per-map entry
    inside managed_rooms_by_map) was silently dropped. The generic scan must
    surface all of them."""
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": False}},
        "vacuum_state": {"segment_count": None},
        "capabilities_error": "RuntimeError('boom-caps')",
        "maps_error": "RuntimeError('boom-maps')",
        "upkeep_snapshot_error": "RuntimeError('boom-upkeep')",
        "roborock_geometry_drift_error": "RuntimeError('boom-drift')",
        "managed_rooms_by_map": {
            "6": {"error": "RuntimeError('boom-room-6')"},
            "7": {"room_count": 3},  # healthy map — must NOT appear as a warning
        },
    }
    warnings = _self_check(out)["warnings"]
    assert any("boom-caps" in w for w in warnings)
    assert any("boom-maps" in w for w in warnings)
    assert any("boom-upkeep" in w for w in warnings)
    assert any("boom-drift" in w for w in warnings)
    assert any("boom-room-6" in w for w in warnings)
    assert not any("boom-room-7" in w for w in warnings)


async def test_diagnostics_job_active_present_uses_live_state(hass):
    """[DIAG-19] HW-DIAG-1 fix 2: job_active_present must resolve via a LIVE
    hass.states lookup, not the STORED (possibly-stale) capabilities snapshot's
    entity_resolution -- a snapshot taken before job_active existed would
    otherwise report "missing" (and warn) even though the entity is live right
    now."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.diagnostics import _vacuum_diagnostics

    register_adapter_config(VACUUM, {
        "adapter_id": "t", "source": "t",
        "entities": {"job_active": "binary_sensor.alfred_job_active"},
        "completion": {"require_job_active_clear": True},
    })
    # The STORED snapshot's entities map lacks job_active entirely (as if
    # detected before the adapter declared it) — the old bug's exact shape.
    manager = _FakeManager(
        caps={"entities": {"vacuum": VACUUM}}, maps={}, rooms={}, upkeep={}, dashboard={},
    )
    # But the entity genuinely exists live right now.
    hass.states.async_set("binary_sensor.alfred_job_active", "off")

    out = _vacuum_diagnostics(hass, manager, VACUUM)
    health = out["completion_health"]
    assert health["job_active_present"] is True
    assert "warning" not in health


def test_self_check_job_active_warning_reworded():
    """[DIAG-20] HW-DIAG-1 fix 1: the warning no longer claims "EVERY run will
    strand" (a run-time-failure framing) for a state where no run can even be
    dispatched -- it reads as a disconnected-device tell instead."""
    out = {
        "capabilities": {"supports_room_clean": True},
        "entity_resolution": {"active_map": {"exists": False}},
        "vacuum_state": {"segment_count": None},
        "completion_health": {
            "requires_job_active_clear": True,
            "job_active_entity": "binary_sensor.ivy_job_active",
            "job_active_present": False,
            "warning": "Completion requires the job-active binary "
                       "(binary_sensor.ivy_job_active) but it is missing — the "
                       "device appears disconnected from Home Assistant right now "
                       "(no run can even be dispatched in this state). Check it's "
                       "online and wake it (e.g. a state refresh); if this persists, "
                       "the upstream integration may have dropped the entity.",
        },
    }
    warnings = _self_check(out)["warnings"]
    assert any("disconnected" in w for w in warnings)
    assert not any("EVERY run will strand" in w for w in warnings)


async def test_get_vacuum_capabilities_snapshot_never_writes(manager):
    """[DIAG-21] The new read-only accessor itself: no stored snapshot exists yet
    for this vacuum (the exact case get_vacuum_capabilities(refresh=False) used
    to force a first-detect + WRITE for, despite refresh=False) -- the snapshot
    accessor must return {} without touching manager.data at all."""
    manager.ensure_vacuum_record(vacuum_entity_id=VACUUM)
    assert VACUUM not in manager.data.get("capabilities", {})

    caps = manager.get_vacuum_capabilities_snapshot(vacuum_entity_id=VACUUM)

    assert caps == {}
    assert VACUUM not in manager.data.get("capabilities", {})  # still no write


async def test_diagnostics_capabilities_collector_is_genuinely_inert(
    hass, manager, monkeypatch
):
    """[DIAG-21b] End-to-end through _vacuum_diagnostics's OWN capabilities
    collector (the exact call site RP-039 targets): NOTHING has ever been
    detected for this vacuum, and the dump must not trigger a write. Stubs out
    get_upkeep_snapshot (a SEPARATE collector diagnostics.py also calls) so this
    test isolates just the ONE call path RP-039 itself fixed; the SEPARATE
    get_upkeep_snapshot non-inertness (this stub's original reason for existing)
    is fixed and proven unstubbed by
    test_diagnostics_fully_inert_including_upkeep_snapshot below."""
    manager.ensure_vacuum_record(vacuum_entity_id=VACUUM)
    monkeypatch.setattr(manager, "get_upkeep_snapshot", lambda **kw: {})
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    assert VACUUM not in manager.data.get("capabilities", {})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    # No detection ever ran -- the snapshot stays genuinely empty rather than
    # forcing a first-detect (accepted tradeoff: "read whatever exists, even if
    # incomplete/stale", per the fix).
    assert diag["vacuums"][0]["capabilities"] == {}
    # The real proof: no write landed in manager.data via diagnostics' own path.
    assert VACUUM not in manager.data.get("capabilities", {})


async def test_diagnostics_fully_inert_including_upkeep_snapshot(hass, manager):
    """[DIAG-21c] RF-33 cont'd: get_upkeep_snapshot was a SECOND, independent
    non-inert path -- its own capabilities lookup, plus a THIRD one per
    maintenance component via the internal get_maintenance_remaining call, both
    called get_vacuum_capabilities(refresh=False) (self-heals/writes even with
    refresh=False in three cases; see get_vacuum_capabilities_snapshot's own
    docstring in core/manager.py). Both now read via the read-only accessor. This
    is the same scenario as test_diagnostics_capabilities_collector_is_genuinely_
    inert but WITHOUT stubbing get_upkeep_snapshot -- a full diagnostics pull
    through the REAL MaintenanceManager, with nothing ever detected for this
    vacuum, must still leave manager.data['capabilities'] untouched."""
    manager.ensure_vacuum_record(vacuum_entity_id=VACUUM)
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    assert VACUUM not in manager.data.get("capabilities", {})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    vac = diag["vacuums"][0]
    assert vac["capabilities"] == {}
    # The real upkeep snapshot ran (not stubbed) and came back empty-shaped --
    # no adapter maintenance components registered for this vacuum -- rather
    # than raising or forcing detection.
    assert vac["upkeep_snapshot"]["replacement_items"] == []
    assert vac["upkeep_snapshot"]["maintenance_items"] == []
    assert "upkeep_snapshot_error" not in vac
    # The real proof: no write landed in manager.data via either collector.
    assert VACUUM not in manager.data.get("capabilities", {})


async def test_device_entity_census_distinguishes_the_two_failure_modes(hass):
    """[DIAG-14] live:DIAG-1 — a failed resolution must be distinguishable from
    an absent capability.

    `entity_resolution` lists each declared role with exists true/false, and a
    role reading exists=false has two completely different causes producing
    byte-identical output: the device genuinely has no such entity, or the
    adapter DERIVED the wrong id from the vacuum's own entity_id (live:ENT-1 —
    an area prefix, a rename). Issue #48 is the worked example: ten roles at
    exists=false, and answering "which is this?" needed a round-trip to the
    reporter for entity ids the dump could have carried.

    The census plus the summary make the two visibly different in the dump
    itself. This test pins the DISTINCTION, not the wording.
    """
    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    vac = diag["vacuums"][0]

    assert "device_entities" in vac, "the dump cannot answer 'what does the device have?'"
    assert "entity_resolution_summary" in vac

    summary = vac["entity_resolution_summary"]
    assert isinstance(summary["declared"], int)
    assert isinstance(summary["unresolved"], list)
    # The verdict is only claimed when it can be: it needs BOTH unresolved roles
    # and a known sibling count, so an unreadable registry never produces a
    # confident wrong answer.
    assert isinstance(summary["likely_naming_mismatch"], bool)
    if summary["likely_naming_mismatch"]:
        assert summary["unresolved"]
        assert isinstance(summary["device_entity_count"], int)
        assert summary["device_entity_count"] > 0


async def test_device_entity_census_never_costs_the_dump(hass):
    """[DIAG-14b] live:DIAG-1 — the census is best-effort, always.

    Diagnostics is the tool reached for when things are already broken, so a
    registry lookup that fails must degrade to a reason string rather than take
    the whole dump with it. A vacuum entity that is not in the registry at all
    is the ordinary version of that.
    """
    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    census = diag["vacuums"][0]["device_entities"]

    # Whatever happened, the block exists and says WHY rather than being empty.
    assert isinstance(census, dict)
    assert any(k in census for k in ("entities", "reason", "error")), census
    # ...and the rest of the dump is intact.
    assert diag["vacuums"][0]["entity_resolution"]


async def test_probe_roles_a_brand_never_offers_are_not_counted_as_unresolved(hass):
    """[DIAG-22] A role this brand does not have is not a failure to resolve.

    `detect_capabilities()` returns a FIXED `entities` dict and emits every key
    unconditionally, `None` where the probe found nothing. That vocabulary is
    EUFY'S -- work_mode, dock_status, water_level, robot_position_x/y. A Roborock
    S6 declares none of them (no dock station, no settable water, and robot
    position is a Eufy-only concept), so all five arrived as None, were counted as
    unresolved, and flipped `likely_naming_mismatch` to True on a healthy device.

    Measured on the maintainer's box 2026-08-15: BOTH vacuums reported "likely
    naming mismatch" while nothing was wrong. That field is the one that tells a
    reporter "your entities exist under names we did not derive" rather than "your
    device genuinely lacks this", so a false positive there sends them hunting.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.diagnostics import _vacuum_diagnostics

    # A brand offering candidates for ONE role only.
    register_adapter_config(VACUUM, {
        "adapter_id": "t", "source": "t",
        "entities": {},
        "entity_candidates": {"battery": ["sensor.alfred_battery"]},
        # REQUIRED or registration refuses the config and this test silently
        # exercises the fallback instead of the config under test.
        "room_profiles": {"builtins": {}},
    })
    caps = {
        "entities": {
            "vacuum": VACUUM,
            "battery": "sensor.alfred_battery",   # offered AND found
            "work_mode": None,                    # Eufy vocabulary, not this brand
            "dock_status": None,
            "water_level": None,
        },
    }
    manager = _FakeManager(caps=caps, maps={}, rooms={}, upkeep={}, dashboard={})
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    hass.states.async_set("sensor.alfred_battery", "100")

    out = _vacuum_diagnostics(hass, manager, VACUUM)

    assert out["roles_not_applicable"] == ["dock_status", "water_level", "work_mode"], (
        "roles the brand offers no candidates for must be MOVED to "
        "roles_not_applicable, not silently dropped and not counted as failures"
    )
    for role in ("work_mode", "dock_status", "water_level"):
        assert role not in out["entity_resolution"]
    assert out["entity_resolution_summary"]["unresolved"] == []
    assert out["entity_resolution_summary"]["likely_naming_mismatch"] is False


async def test_a_role_the_brand_does_offer_still_reports_when_it_misses(hass):
    """[DIAG-22b] The over-correction guard, and it is the one that matters.

    The first version of this gate keyed on the adapter's `entities` map alone.
    The Eufy adapter declares ZERO roles there -- every one is probe-resolved --
    so a genuine Eufy work_mode miss would have been gated away SILENTLY. Hiding a
    real failure is strictly worse than the false alarm being fixed.

    The discriminator is `entity_candidates`: capabilities.py's own docstring
    defines it as "entity IDs to probe per key", supplied per brand. Offered and
    not found is a MISS; never offered is a role that does not apply.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.diagnostics import _vacuum_diagnostics

    register_adapter_config(VACUUM, {
        "adapter_id": "t", "source": "t",
        "entities": {},
        # This brand DOES offer candidates for work_mode -- none of them resolved.
        "entity_candidates": {"work_mode": ["sensor.alfred_work_mode"]},
        "room_profiles": {"builtins": {}},
    })
    caps = {"entities": {"vacuum": VACUUM, "work_mode": None}}
    manager = _FakeManager(caps=caps, maps={}, rooms={}, upkeep={}, dashboard={})

    out = _vacuum_diagnostics(hass, manager, VACUUM)

    assert "work_mode" not in out.get("roles_not_applicable", []), (
        "a role the brand OFFERS candidates for was gated away -- this is the "
        "silent-failure regression DIAG-22b exists to catch"
    )
    assert "work_mode" in out["entity_resolution"]
    assert "work_mode" in out["entity_resolution_summary"]["unresolved"]


async def test_device_diagnostics_scopes_to_one_vacuum(hass):
    """[DIAG-23] The device page's Download button is per-device; the file should be.

    Without async_get_device_diagnostics HA falls back to the config-entry dump,
    so pressing Download on Alfred's page hands you every vacuum on the install --
    and the irrelevant half is the half a reporter must be told to ignore.
    """
    from types import SimpleNamespace

    from custom_components.eufy_vacuum.diagnostics import async_get_device_diagnostics

    manager = _FakeManager(caps=_caps(), maps={}, rooms={}, upkeep={}, dashboard={})
    manager.get_known_vacuum_ids = lambda: [VACUUM, "vacuum.ivy"]
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    hass.states.async_set("vacuum.ivy", "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    full = await async_get_config_entry_diagnostics(hass, entry)
    assert len(full["vacuums"]) == 2, "premise: the entry dump carries both"

    device = SimpleNamespace(identifiers={(DOMAIN, "vacuum_alfred")})
    scoped = await async_get_device_diagnostics(hass, entry, device)

    assert scoped["scope"] == "device"
    assert [v["vacuum_entity_id"] for v in scoped["vacuums"]] == [VACUUM]
    # The entry-level context (redacted title/data) must survive the scoping.
    assert "entry" in scoped


async def test_device_diagnostics_falls_back_rather_than_returning_nothing(hass):
    """[DIAG-23b] An unmatched device yields the FULL dump, never an empty one.

    If the identifier convention ever drifts, a silent empty list reads as "this
    vacuum has no data" -- the same failure class as a doc omitting a section. A
    dump that is merely too broad is still usable.
    """
    from types import SimpleNamespace

    from custom_components.eufy_vacuum.diagnostics import async_get_device_diagnostics

    manager = _FakeManager(caps=_caps(), maps={}, rooms={}, upkeep={}, dashboard={})
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)

    device = SimpleNamespace(identifiers={(DOMAIN, "vacuum_does_not_exist")})
    out = await async_get_device_diagnostics(hass, entry, device)

    assert out["vacuums"], "an unmatched device must not produce an empty dump"
    assert out["scope"].startswith("entry")
