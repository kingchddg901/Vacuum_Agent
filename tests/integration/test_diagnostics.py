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


def _issue_60_out(maps, *, brand=None):
    """The reporter's shape, from the real diagnostics on ISSUE #60.

    active_map overridden onto a CAMERA, whose state is the map's last-updated
    timestamp — not a sentinel, and not a map id. Every other room signal is zero,
    exactly as his payload had them.
    """
    out = {
        "capabilities": {"supports_room_clean": True, "supports_rooms": True},
        "entity_resolution": {
            "active_map": {
                "entity_id": "camera.doomba_iii_map",
                "exists": True,
                "state": "2026-10-02 11:04:35",
            }
        },
        "vacuum_state": {"segment_count": 0},
        "maps": maps,
        "managed_rooms_by_map": {},
        "discoverable_room_count": 0,
    }
    if brand:
        out["adapter"] = {"brand": brand}
    return out


def test_self_check_anchor_1_state_naming_no_map_is_not_healthy():
    """[DIAG-ANCHOR-1] THE RED INPUT (ISSUE #60).

    Before this, the report said rooms_importable "yes", "maps, rooms and the live
    map all work", room_control "available (via active map)" and warnings [] — on a
    vacuum whose import refused and whose room_count was 0 in the same payload. The
    report and the behaviour disagreed, which is the defect DIAG-14 fixed for
    sentinels and missed for a value that merely names nothing.
    """
    sc = _self_check(_issue_60_out({"maps": [{"map_id": "1", "room_count": 0}]}))

    assert sc["rooms_importable"] == "no", "claimed importable while the importer refuses"
    assert "all work" not in sc["note"]
    assert sc["room_control"] != "available (via active map)"
    assert sc["warnings"], "went green and silent on a device that cannot import"
    assert any(
        "camera.doomba_iii_map" in w and "map SELECTOR" in w for w in sc["warnings"]
    ), "the warning must name the mis-bound role, not blame the vacuum integration"


def test_self_check_anchor_2_no_enumerated_maps_means_no_judgement():
    """[DIAG-ANCHOR-2] THE ABLATION TARGET.

    Same unmatched state, but the maps block is empty — a cold start before the map
    list has landed, the scar in 39-the-entry-point.md §2 ("the matching was never
    wrong, the list was empty when it ran"). With nothing to judge against, the
    check must not fire. Drop the `not _enumerated_map_ids` term and this goes red:
    every install reporting a map id before its map list loads would read as broken.
    """
    sc = _self_check(_issue_60_out({"maps": []}))

    assert sc["rooms_importable"] == "yes"
    assert sc["note"] == "Standard transport — maps, rooms and the live map all work."


def test_self_check_anchor_3_map_image_does_not_name_another_brand():
    """[DIAG-ANCHOR-3] core must not speak one brand's words to another brand's owner.

    This line named the eufy-clean fork unconditionally, so a Dreame owner reading
    their own diagnostics was told the backdrop depends on a Eufy integration they
    will never install.
    """
    healthy = _issue_60_out({"maps": [{"map_id": "1", "room_count": 2}]}, brand="dreame")
    healthy["entity_resolution"]["active_map"]["state"] = "1"  # a real map id
    sc = _self_check(healthy)

    assert sc["rooms_importable"] == "yes"
    assert "eufy-clean" not in sc["map_image"], "leaked a brand name to another brand"
    assert "dreame" in sc["map_image"]


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
    itself.

    ⚠ WHAT THIS TEST ACTUALLY PINS IS NARROWER THAN "the DISTINCTION", which it
    used to claim. Its vacuum is not in the entity registry, so the census returns
    `reason: vacuum_entity_not_in_registry` and the body that does the
    distinguishing never runs -- 23 statements of it. The four `isinstance` checks
    below are SHAPE, not vocabulary, and the only substantive assertions sit under
    `if summary["likely_naming_mismatch"]:`, which is False here: a conditional
    assertion that never fires. Kept as the shape-and-degradation test it really
    is; [DIAG-24] produces the populated census and asserts the distinction
    unconditionally.
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
        "_entity_candidates": {"battery": ["sensor.alfred_battery"]},
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
        "_entity_candidates": {"work_mode": ["sensor.alfred_work_mode"]},
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


# --- ISSUE #55: "we cannot support this yet" gets its own answer ------------


def _q7_m5_out(refresh: dict | None = None) -> dict:
    """The reporter's install, reduced to the shape `_vacuum_diagnostics` assembles.

    A Roborock Q7 M5 is a B01-protocol device: Home Assistant creates no map selector,
    no current_room and no binary sensors for it, and `roborock.get_maps` raises
    ServiceNotSupported. Eleven entities, none of them map-anything.
    """
    out = {
        "capabilities": {
            "detected_model": "roborock.vacuum.sc05",
            "model_family": "generic",
            "supports_room_clean": True,   # the ADAPTER's claim about the brand
            "supports_rooms": False,
        },
        "entity_resolution": {"active_map": {"exists": False}},
        "vacuum_state": {"segment_count": None},
        "adapter": {"brand": "Roborock"},
        "maps": {"map_count": 1, "maps": [{"map_id": "1", "room_count": 0}]},
        "managed_rooms_by_map": {"1": {"room_count": 0}},
        "roborock_geometry_drift": {"present": False, "reason": "no_geometry"},
        "active_map_id": None,
    }
    if refresh is not None:
        out["room_source_refresh"] = refresh
    return out


def test_self_check_says_not_yet_supported_when_ha_refused():
    """[DIAG-20] A recorded refusal is READ, not deduced from entity shapes."""
    sc = _self_check(_q7_m5_out({"ok": False, "reason": "service_not_supported"}))

    assert "NOT YET SUPPORTED" in sc["note"]
    assert "Roborock integration" in sc["note"], (
        "name the integration that lacks support — 'not supported' with no subject "
        "reads as 'your vacuum is not supported', which is false and discouraging"
    )
    assert "nothing to report" in sc["note"], (
        "issue #55 was filed because we asked for a report; the self-check must not "
        "reintroduce the ask by omission"
    )
    assert sc["rooms_importable"] == "no"
    assert "unavailable" in sc["room_control"], (
        "supports_room_clean is the adapter's claim about the BRAND and is True for "
        "every Roborock; it cannot see that HA declines for THIS device. Left alone "
        "it says 'available, but no rooms visible yet' — a wait that never resolves."
    )
    for word in ("Eufy", "eufy-clean", "smcneece"):
        assert word not in str(sc), f"{word!r} shown to a Roborock owner"


def test_self_check_does_not_claim_unsupported_without_evidence():
    """[DIAG-20] The negative control, and the trap: {} means NEVER ASKED.

    Absence of a refusal and a refusal read alike if the code branches on falsiness.
    Without this, `not_yet_supported` could be written as `not _refresh.get("ok")` and
    every never-refreshed vacuum would be declared permanently unsupported.
    """
    for refresh in (None, {}, {"ok": False, "reason": "entity_unavailable"},
                    {"ok": False, "reason": "service_call_failed"}):
        sc = _self_check(_q7_m5_out(refresh))
        assert "NOT YET SUPPORTED" not in sc["note"], (
            f"refresh={refresh!r} is not a statement that the device is unsupported"
        )


def test_self_check_fallback_never_names_a_brand_the_owner_lacks():
    """[DIAG-21] ⚠ EUFY IS NOT THE DEFAULT — a fallback yielding a brand word IS the bug.

    Issue #46 fixed this in the import message. The same text survived in the
    self-check's `else` branches, so issue #55's Roborock owner was told to set his
    rooms up in "the Eufy app" and to install "the smcneece eufy-clean fork".
    """
    sc = _self_check(_q7_m5_out())  # no refresh recorded -> the generic fallback

    for word in ("Eufy", "eufy-clean", "smcneece"):
        assert word not in sc["note"], f"{word!r} in the note for a Roborock owner"
        assert word not in sc["map_image"], f"{word!r} in map_image for a Roborock owner"
    assert "Roborock app" in sc["note"], (
        "the fallback should name the owner's OWN app, which is the actionable thing"
    )


def test_self_check_still_helps_a_eufy_owner():
    """[DIAG-21] The other side: de-branding the fallback must not strip real help.

    A Eufy owner on the reduced transport genuinely does need the eufy-clean fork for
    a map picture. Removing the brand word for everyone would have cost them that.
    """
    out = _q7_m5_out()
    out["adapter"] = {"brand": "Eufy"}
    out["capabilities"] = dict(out["capabilities"], detected_model="T2262")

    sc = _self_check(out)

    assert "eufy-clean fork" in sc["map_image"], (
        "a Eufy owner still needs the fork; the fix was to stop showing it to "
        "everyone else, not to delete the advice"
    )
    assert "Eufy app" in sc["note"]


async def test_missing_job_active_warning_names_both_causes(hass):
    """[DIAG-22] ⚠ TWO CAUSES, ONE SIGNATURE — name both or name neither.

    "Declared but never created" is produced by at least two different things:
    HA 2026.7 capability-gating (home-assistant/core#173282), and the brand
    integration simply not building that entity for the model at all. Issue #55's
    Roborock Q7 M5 is the second kind — HA's binary_sensor.py does not serve B01
    coordinators, so that binary was never going to exist for him — yet the dump
    told him, with confidence, that it was #173282.

    The dump cannot see which, so it must not pick. The CONSEQUENCE is identical
    either way and is the part the user can act on.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    manager = _FakeManager(
        caps=_caps(), maps={"vacuum_entity_id": VACUUM, "map_count": 0, "maps": []},
        rooms={}, upkeep={"highest_priority_status": "good"}, dashboard={},
    )
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    register_adapter_config(VACUUM, {
        "adapter_id": "rb", "source": "code", "brand": "Roborock",
        "entities": {"vacuum": VACUUM, "job_active": "binary_sensor.alfred_cleaning"},
        "completion": {"require_job_active_clear": True},
    })
    hass.states.async_set(VACUUM, "docked")   # the binary is NEVER created

    entry = _entry()
    entry.add_to_hass(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    warning = (diag["vacuums"][0].get("completion_health") or {}).get("warning") or ""

    assert "never created" in warning.lower(), "wrong branch — fixture is not set up"
    assert "173282" in warning, "the known gating cause must still be offered"
    assert "does not build that entity" in warning, (
        "the OTHER cause — the integration never builds it for this model — was the "
        "true one for issue #55's reporter and was not mentioned at all"
    )
    assert "This is the Home Assistant 2026.7" not in warning, (
        "that phrasing asserts one cause as fact; it is the sentence being fixed"
    )
    # The actionable part must survive the hedging.
    assert "interrupted" in warning and "completion cannot arm" in warning.lower()


# ---------------------------------------------------------------------------
# issue #61 — the self-check spoke Eufy to a Roborock owner, and was green on a
# failing install
# ---------------------------------------------------------------------------

def _issue61_out(**over):
    """The shape _vacuum_diagnostics assembled for the issue-61 reporter: a Roborock S7
    that DOES resolve active_map (so the native-brand branch never fires) with battery
    and charging unresolved because his entity ids are Spanish."""
    out = {
        "capabilities": {
            "detected_model": "roborock.vacuum.a15",
            "model_family": "generic",
            "supports_room_clean": True,
            "supports_rooms": False,
        },
        "entity_resolution": {
            "active_map": {"entity_id": "select.s7_mapa_seleccionado", "exists": True,
                           "registered": True, "state": "Habitaciones"},
            "battery": {"entity_id": "sensor.s7_battery", "exists": False,
                        "registered": False, "state": None},
            "charging": {"entity_id": "binary_sensor.s7_charging", "exists": False,
                         "registered": False, "state": None},
        },
        "vacuum_state": {"segment_count": None},
        "adapter": {"brand": "Roborock"},
        "maps": {"map_count": 2, "maps": [
            {"map_id": "Comedor", "room_count": 4},
            {"map_id": "Habitaciones", "room_count": 3},
        ]},
        "managed_rooms_by_map": {"Habitaciones": {"room_count": 3}},
        "roborock_geometry_drift": {"present": True, "aligned": True},
        "active_map_id": "Habitaciones",
    }
    out.update(over)
    return out


def test_diag19_transport_does_not_speak_eufy_to_another_brand():
    """[DIAG-19] issue #61. `novel` is Eufy's api_type and MQTT is its transport; a
    Roborock has neither. The branch fires for ANY brand whose active_map resolves, so
    this reporter was told his vacuum runs on another manufacturer's transport. Same
    family as the "eufy-clean fork" line issue #60 showed to Dreame owners."""
    sc = _self_check(_issue61_out())

    assert "novel" not in sc["transport"].lower()
    assert "mqtt" not in sc["transport"].lower()
    assert "Roborock" in sc["transport"]
    # the OBSERVATION is unchanged — only who it is attributed to
    assert "active-map" in sc["transport"]


def test_diag19b_eufy_still_gets_its_own_transport_words():
    """[DIAG-19b] The fix must not strip Eufy's correct description from Eufy."""
    sc = _self_check(_issue61_out(adapter={"brand": "Eufy"}))
    assert "novel / MQTT" in sc["transport"]


def test_diag20_a_missing_battery_role_is_a_warning_not_silence():
    """[DIAG-20] issue #61. The self-check returned `warnings: []` on an install
    throwing a TypeError every few seconds, with `battery: exists false` sitting in the
    same payload. Both roles degrade SILENTLY — get_battery_level returns None and
    is_charging returns a flat False — so if the self-check does not say it, nothing
    does."""
    sc = _self_check(_issue61_out())
    joined = " | ".join(sc["warnings"])

    assert sc["warnings"], "a self-check cannot be green on an install that is throwing"
    assert "sensor.s7_battery" in joined
    assert "binary_sensor.s7_charging" in joined
    # actionable, not just named
    assert "refused" in joined and "NOT charging" in joined


def test_diag20b_resolved_roles_raise_no_warning():
    """[DIAG-20b] The complement, so the warning cannot be a constant. A declared role
    that EXISTS must stay silent, or the block becomes noise every reader learns to
    skip."""
    out = _issue61_out()
    out["entity_resolution"]["battery"] = {
        "entity_id": "sensor.s7_bateria", "exists": True, "registered": True, "state": "87"
    }
    out["entity_resolution"]["charging"] = {
        "entity_id": "binary_sensor.s7_cargando", "exists": True, "registered": True,
        "state": "off",
    }
    sc = _self_check(out)
    joined = " | ".join(sc["warnings"])
    assert "bateria" not in joined and "cargando" not in joined


def test_diag21_a_blank_active_map_is_not_a_misbound_role():
    """[DIAG-21] Found on live hardware 2026-10-04, not by the suite.

    Roborock's `select.ivy_selected_map` sits at `unknown` between maps. `unknown` names
    none of the vacuum's maps because it names NOTHING, so the #60 mismatch predicate
    classified it as a mis-bound role and told the owner to go re-point a role that was
    bound perfectly correctly. The warning should still fire -- rooms genuinely cannot be
    imported -- but with the other message, the one about the integration not providing a
    map id yet.

    The guard's own comment had always said "a value that is NOT A SENTINEL but names no
    known map"; only the second half was implemented."""
    out = _issue61_out(
        adapter={"brand": "Roborock"},
        entity_resolution={
            "active_map": {"entity_id": "select.ivy_selected_map", "exists": True,
                           "registered": True, "state": "unknown"},
        },
        maps={"map_count": 1, "maps": [{"map_id": "Main floor", "room_count": 10}]},
        managed_rooms_by_map={},
        active_map_id=None,
        discoverable_room_count=0,
    )
    sc = _self_check(out)
    joined = " | ".join(sc["warnings"])

    assert joined, "a blank active_map still blocks importing and must warn"
    assert "bound to the wrong entity" not in joined, (
        "a sentinel is an absent value, not a wrong one"
    )
    assert "not providing a current map id" in joined


def test_diag21b_a_real_wrong_value_still_reads_as_misbound():
    """[DIAG-21b] The complement, so the sentinel check cannot be over-applied: a value
    that is genuinely present and genuinely names no map IS a mis-bound role, which is
    the whole finding of #60. A camera's state is a timestamp."""
    out = _issue61_out(
        adapter={"brand": "Roborock"},
        entity_resolution={
            "active_map": {"entity_id": "camera.ivy_map", "exists": True,
                           "registered": True, "state": "2026-10-04 19:51:07"},
        },
        maps={"map_count": 1, "maps": [{"map_id": "Main floor", "room_count": 10}]},
        managed_rooms_by_map={},
        active_map_id=None,
        discoverable_room_count=0,
    )
    joined = " | ".join(_self_check(out)["warnings"])
    assert "bound to the wrong entity" in joined


async def test_diag22_the_dock_branch_reaches_the_dump(hass):
    """[DIAG-22] ISSUE #69 follow-up — `dock_detection` surfaces when a brand records it.

    `dock_controls` reports the OUTCOME. This reports how it was reached, which the
    outcome cannot imply: a live probe that resolved a dockless machine and a probe
    that declined and fell back to a catalogue default saying the same thing produce
    identical controls. [DD-3] pins that the two are distinguishable at the adapter;
    this pins that the distinction actually travels to the artifact a maintainer reads.

    ABLATION: delete the `dock_detection` block in diagnostics.py and this goes red.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    register_adapter_config(VACUUM, {
        "adapter_id": "roborock", "source": "code",
        "_dock_detection": {
            "resolved": True, "source": "device", "catalog_family": "generic",
            "dock_type": 7, "dock_type_name": "o4_dock", "reason": None,
        },
    })
    hass.states.async_set(VACUUM, "docked")
    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    dd = diag["vacuums"][0].get("dock_detection")

    assert dd is not None, "the block the brand recorded never reached the dump"
    assert dd["resolved"] is True and dd["source"] == "device"
    assert dd["dock_type"] == 7 and dd["dock_type_name"] == "o4_dock"
    assert dd["catalog_family"] == "generic"


async def test_diag22b_a_brand_that_records_nothing_gets_no_block(hass):
    """[DIAG-22b] Core holds no opinion: absent means absent, not an empty shell.

    An empty `dock_detection: {}` would read as "we looked and found nothing", which is
    a claim. A brand that does not record this has not looked, and the honest dump says
    so by having no key — the same distinction `_known_map_ids` draws between None and
    an empty set.

    ABLATION: drop the `and _dock_detection` truthiness guard, or emit the key
    unconditionally, and this goes red.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    register_adapter_config(VACUUM, {"adapter_id": "eufy", "source": "code"})
    hass.states.async_set(VACUUM, "docked")
    entry = _entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "dock_detection" not in diag["vacuums"][0]


# ---------------------------------------------------------------------------
# [DIAG-24] - [DIAG-28]  the two bodies that no test had ever entered.
#
# Both are guarded by an early return that every existing test takes, which is why
# 23 of this module's 36 uncovered statements sit in just two functions. The
# guards were covered; the work was not.
# ---------------------------------------------------------------------------

def _vacuum_on_device(hass, *, companions=(), device=True, config_entry=True):
    """Put VACUUM in the entity registry, optionally on a device with companions.

    `device=False` is the issue #49 shape: a vacuum on the CONFIG ENTRY with no
    device at all, which is the install the census used to come back empty on.
    """
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(domain=DOMAIN, entry_id="diag24")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    # BOTH scopes off is the only way to an EMPTY sweep: the vacuum counts as its
    # own sibling, so a registered vacuum on either scope finds at least one.
    device_id = None
    if device:
        device_id = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "alfred-device")},
        ).id

    registry.async_get_or_create(
        "vacuum", DOMAIN, "alfred_vac", suggested_object_id="alfred",
        config_entry=entry if config_entry else None, device_id=device_id,
    )
    for kwargs in companions:
        registry.async_get_or_create(
            kwargs.pop("domain", "sensor"), DOMAIN, kwargs.pop("unique_id"),
            config_entry=entry, device_id=device_id, **kwargs,
        )
    return registry


async def test_diag24_a_populated_census_is_the_naming_mismatch(hass):
    """[DIAG-24] live:ENT-1 / issue #48 - a POPULATED census beside failed
    resolutions IS the naming mismatch, and an empty one is a reduced device.

    This is the case [DIAG-14] names and never produces. Ten roles at exists=false
    has two causes that print identically, and answering "which?" cost a
    round-trip to the reporter for entity ids the dump could have carried. The
    census is what makes them different IN THE DUMP -- so it has to actually list
    something.

    BOTH SCOPES ARE ASSERTED SEPARATELY (live:ENT-5). The census was device-scoped
    only and bailed when the vacuum had no device, which made it empty on exactly
    the installs it exists to explain: issue #49's device search found nothing
    while the config-entry search rescued battery on the same box. A blank census
    on a naming problem is worse than none, because it reads as "this device
    exposes nothing".

    RED: make the sweep device-scoped again and `config_entry_entity_count` goes
    to 0 with the companion missing from `entities`; drop the two counts and the
    dump can no longer say WHICH scope found what.
    """
    # THREE companions, not one, and the reason is measured: with only
    # `sensor.alfred_battery` beside the vacuum, the sweep's natural order is the
    # EXACT REVERSE of sorted order, so `ids == sorted(ids)` holds whether the
    # census sorts or reverses. A two-element list cannot see that mutation.
    _vacuum_on_device(hass, companions=[
        {"unique_id": "uid_batt", "suggested_object_id": "alfred_battery"},
        {"unique_id": "uid_zzz", "suggested_object_id": "alfred_zzz_last"},
        {"unique_id": "uid_aaa", "suggested_object_id": "alfred_aaa_first"},
    ])

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    census = diag["vacuums"][0]["device_entities"]

    # The precondition that makes everything below meaningful: the early return
    # every other test in this file takes was NOT taken.
    assert "reason" not in census, census
    assert census["device_id"], census

    ids = [item["entity_id"] for item in census["entities"]]
    assert VACUUM in ids and "sensor.alfred_battery" in ids, ids
    assert census["entity_count"] == len(ids)
    # The two scopes are reported APART, not summed.
    assert census["device_entity_count"] >= 4, census
    assert isinstance(census["config_entry_entity_count"], int)
    # Sorted, so two dumps from one box diff cleanly. The registration order above
    # is deliberately NOT sorted order, so this can see a reversal.
    assert ids == sorted(ids), ids


async def test_diag25_the_census_carries_what_separates_a_collision(hass):
    """[DIAG-25] live:ENT-9 - `translation_key` and `state_class`, because nothing
    else in the dump separates two real sensors that share a suffix.

    `cleaning_area` and `total_cleaning_area` are both real, enabled sensors with
    the same domain and a shared suffix: entity_id, `disabled` and `platform` do
    not distinguish them. The two fields that do live in the registry and need no
    state. Verified across three brands on the maintainer's own install --
    robovac_mqtt sets state_class and no translation_key, Roborock the reverse,
    Dreame sets translation_key on 39/39 sensors -- so a dump carrying only one of
    the two would be blind to a brand.

    THE TWO SENSORS HERE DIFFER ONLY IN THOSE FIELDS. That is the point: if the
    census omitted either one, the dump would show two indistinguishable rows, and
    the assertion below could not tell them apart either.

    `disabled` IS ASSERTED ON THE SAME RUN, because it is the OTHER silent cause --
    an entity in the registry with no state is indistinguishable, through
    `hass.states.get`, from one that was never created.

    RED: drop `translation_key` or `state_class` from the census dict and the two
    rows become equal; drop `disabled` and the disabled companion reads as live.
    """
    from homeassistant.helpers import entity_registry as er

    registry = _vacuum_on_device(hass, companions=[
        {"unique_id": "uid_area", "suggested_object_id": "alfred_cleaning_area",
         "original_device_class": None, "capabilities": {"state_class": "measurement"}},
        {"unique_id": "uid_total", "suggested_object_id": "alfred_total_cleaning_area",
         "translation_key": "total_cleaning_area"},
    ])
    registry.async_update_entity("sensor.alfred_total_cleaning_area",
                                 disabled_by=er.RegistryEntryDisabler.USER)

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    rows = {i["entity_id"]: i for i in diag["vacuums"][0]["device_entities"]["entities"]}

    area = rows["sensor.alfred_cleaning_area"]
    total = rows["sensor.alfred_total_cleaning_area"]

    # Nothing a dump carried BEFORE these two fields separates them...
    assert area["platform"] == total["platform"]
    # ...and these two do.
    assert area["state_class"] == "measurement", area
    assert total["translation_key"] == "total_cleaning_area", total
    assert (area["state_class"], area["translation_key"]) != (
        total["state_class"], total["translation_key"]
    ), "the census cannot tell a collision pair apart"

    # The other silent cause, on the same run.
    assert total["disabled"] is True, total
    assert area["disabled"] is False, area


async def test_diag26_a_vacuum_with_no_siblings_says_so(hass):
    """[DIAG-26] The honest empty: a sweep that finds nothing says so, rather than
    reporting a device that exposes nothing.

    This is the OTHER half of [DIAG-24]'s claim -- "an empty one is a genuinely
    reduced device" -- and without it the populated case could be satisfied by a
    census that never reports an absence at all.

    ⚠ THE VACUUM COUNTS AS ITS OWN SIBLING, which is what makes this case hard to
    reach and is why an earlier draft of this test did not reach it: on either
    scope a registered vacuum finds at least ONE entity, itself. The only input
    that empties both scopes is a registry entry with NEITHER a device NOR a
    config entry. That draft said so in this docstring and then asserted something
    weaker, which left `no_entities_on_device_or_config_entry` uncovered -- a test
    whose name promised more than its body.

    RED: delete the `if not siblings` block and the census reports
    `entity_count: 0` with an empty list, which reads as a reduced device rather
    than as a sweep that found nothing.
    """
    from custom_components.eufy_vacuum.diagnostics import _device_entity_census

    # Neither scope: no device, no config entry.
    _vacuum_on_device(hass, device=False, config_entry=False)
    census = _device_entity_census(hass, VACUUM)

    # The early return was not taken -- this vacuum IS in the registry.
    assert census.get("reason") == "no_entities_on_device_or_config_entry", census
    assert census["device_entity_count"] == 0, census
    assert census["config_entry_entity_count"] == 0, census
    # The absence is NAMED, not implied by an empty list.
    assert "entities" not in census, census


async def test_diag27_a_working_override_beside_a_wrong_derivation(hass):
    """[DIAG-27] live:ENT-2 - the combination that hid the derivation bug.

    `_pattern_resolution` reports the DERIVATION's health separately from whether
    the feature works, and its docstring names why: "a manual override (or the
    ENT-2 device-sibling fallback) can make the live map work while the derived id
    is still wrong, and that combination is exactly what hid this for so long".

    SO THAT IS THE COMBINATION ASSERTED: `derived_exists` False beside
    `override_exists` True. A test with both true, or both false, would not
    reproduce the state the block exists to make visible -- and every test before
    this one declared no pattern at all, so the whole body (20 lines) never ran.

    THE OVERRIDE IS REDACTED, asserted here because `_redact` is applied to it and
    to nothing else in the block; a dump that leaked a user's entity id verbatim
    while redacting it elsewhere would be inconsistent in the direction that
    matters.

    RED: drop the `derived_exists` lookup and it reads True for an id that does not
    exist; drop `override`/`override_exists` and the dump cannot say why the
    feature works despite a wrong derivation.
    """
    from custom_components.eufy_vacuum.adapters.registry import (
        clear_registry,
        register_adapter_config,
    )

    clear_registry()
    register_adapter_config(VACUUM, {
        "adapter_id": "rb", "source": "code",
        "mapping": {
            "live_map_image_entity_pattern": "image.{object_id}_map",
        },
    })

    manager = _make_manager()
    # ⚠ `_FakeManager` HAS NO `.data` -- it is a pure stub (`_caps`, `_maps`,
    # `_rooms`, `_upkeep`, `_dashboard`). `_pattern_resolution` reads
    # `manager.data.get("vacuums")` inside its own pragma'd `except`, so with the
    # stock fixture the override is ALWAYS None -- which is part of why this block
    # was never covered. Attach it here rather than widen a fixture every other
    # test in this file shares.
    manager.data = {"vacuums": {VACUUM: {
        "live_map_image_entity": "image.upstairs_robot_map",
    }}}
    # The override points at an entity that EXISTS; the derived id does not.
    hass.states.async_set("image.upstairs_robot_map", "idle")
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)
    try:
        diag = await async_get_config_entry_diagnostics(hass, entry)
    finally:
        clear_registry()

    block = diag["vacuums"][0]["pattern_resolution"]["live_map_image"]
    assert block["pattern"] == "image.{object_id}_map"
    assert block["derived"] == "image.alfred_map", block
    # THE COMBINATION: the feature works, the derivation is wrong.
    assert block["derived_exists"] is False, block
    assert block["override_exists"] is True, block
    assert block["override"], block
    # THE THIRD DIVERGENCE PATH, reported so a working live map beside a wrong
    # derivation is explainable. This adapter declares no resolver, so the field must
    # be PRESENT and None -- absent and None read identically to a reader, and a
    # missing key is what sends them looking for a cause the dump does not carry.
    assert "resolver" in block, block
    assert block["resolver"] is None, block


async def test_diag27b_a_declared_live_map_resolver_is_reported(hass):
    """[DIAG-27b] A declared resolver must appear in the dump, or the dump misleads.

    `live:ENT-2` reports whether the DERIVATION is healthy, separately from whether the
    live map works, and names the ways those two can diverge. #80 added a third: a
    brand-declared resolver, tried after the override, the pattern and the sibling search
    have all missed. On a Roborock whose map was renamed in the app, the derived id is
    permanently wrong and the live map works anyway — with no override and no sibling.

    THE PAIR IS THE POINT. `[DIAG-27]` asserts the field is present and None when no
    resolver is declared; this asserts the declared NAME comes through. Asserting only
    one of those would pass on a hardcoded value.

    RED: drop the `resolver` key from the block and this fails; report it as a bool
    instead of the name and it fails too, because the name is what tells a reader WHICH
    resolver to go and read.
    """
    from custom_components.eufy_vacuum.adapters.registry import (
        clear_registry,
        register_adapter_config,
    )

    clear_registry()
    register_adapter_config(VACUUM, {
        "adapter_id": "rb", "source": "code",
        "mapping": {
            "live_map_image_entity_pattern": "image.{object_id}_map",
            "live_map_image_entity_resolver": "roborock_map_flag",
        },
    })

    manager = _make_manager()
    manager.data = {"vacuums": {VACUUM: {}}}
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})

    entry = _entry()
    entry.add_to_hass(hass)
    try:
        diag = await async_get_config_entry_diagnostics(hass, entry)
    finally:
        clear_registry()

    block = diag["vacuums"][0]["pattern_resolution"]["live_map_image"]
    assert block["resolver"] == "roborock_map_flag", block
    # and the derivation is still reported as wrong, which is the whole combination
    assert block["derived_exists"] is False, block


async def test_diag28_an_unformattable_pattern_is_dropped_not_raised(hass):
    """[DIAG-28] A pattern the adapter wrote wrong costs its block, not the dump.

    The derivation substitutes `{object_id}` and `{map_slug}`; any OTHER
    placeholder raises `KeyError` out of `str.format`, and an adapter is free to
    declare one by mistake. Diagnostics is reached for when things are already
    broken, so a bad pattern must drop its own block and leave the rest readable.

    THE CONTRAST IS ASSERTED IN THE SAME TEST: a well-formed pattern on the same
    fixture DOES produce the block. Without it, `pattern_resolution == {}` is
    equally true of a vacuum that declared no pattern at all -- an expectation the
    fallback also produces.

    RED: drop the `except (KeyError, IndexError, ValueError)` and the dump raises
    instead of degrading.
    """
    from custom_components.eufy_vacuum.adapters.registry import (
        clear_registry,
        register_adapter_config,
    )

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    entry = _entry()
    entry.add_to_hass(hass)

    # The unformattable one: `{floor}` is not a placeholder the derivation knows.
    clear_registry()
    register_adapter_config(VACUUM, {
        "adapter_id": "rb", "source": "code",
        "mapping": {"live_map_image_entity_pattern": "image.{object_id}_{floor}"},
    })
    try:
        bad = await async_get_config_entry_diagnostics(hass, entry)
    finally:
        clear_registry()
    assert bad["vacuums"][0]["pattern_resolution"] == {}, (
        "an unformattable pattern took more than its own block"
    )

    # THE CONTRAST: a well-formed pattern on the same fixture does produce it.
    clear_registry()
    register_adapter_config(VACUUM, {
        "adapter_id": "rb", "source": "code",
        "mapping": {"live_map_image_entity_pattern": "image.{object_id}_map"},
    })
    try:
        good = await async_get_config_entry_diagnostics(hass, entry)
    finally:
        clear_registry()
    assert "live_map_image" in good["vacuums"][0]["pattern_resolution"], (
        "the empty dict above is not a discriminator if a GOOD pattern is empty too"
    )


async def test_diag29_the_memory_backend_gets_the_drift_block(hass):
    """[DIAG-29] The on-device decode validator is wired into the dump, and only
    for the backend that can answer it.

    `geometry_drift` overlays the vendor parser's per-room bboxes with the
    raster-decoded ones: both come from the SAME segment layer, so aligned boxes
    confirm the decode and a systematic delta is the calibration signal. Only the
    roborock MEMORY backend carries the raw blob, so the block is gated on it.

    THE CONTRAST IS THE TEST. "The key is present" is satisfied by a dump that
    always adds it, which would invite a reader to interpret an empty drift report
    on a brand that cannot produce one. So a non-memory backend must NOT carry it.

    This is a CALL-SITE test, not an engine test: `geometry_drift` itself is
    covered by `RRD-10`/`RRD-20` in tests/unit/test_roborock_raw_map.py. What was
    untested is that the dump reaches it at all.

    RED: drop the `backend == "memory"` gate and the storage case gains the key;
    drop the two calls and the memory case loses it.
    """
    from custom_components.eufy_vacuum.adapters.registry import (
        clear_registry,
        register_adapter_config,
    )

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    entry = _entry()
    entry.add_to_hass(hass)

    async def _dump(backend):
        clear_registry()
        register_adapter_config(VACUUM, {
            "adapter_id": "rb", "source": "code",
            "map_state_source": {"backend": backend},
        })
        try:
            diag = await async_get_config_entry_diagnostics(hass, entry)
        finally:
            clear_registry()
        return diag["vacuums"][0]

    mem = await _dump("memory")
    other = await _dump("storage")

    # The gate fired: the validator ran for the backend that can answer it...
    assert "roborock_geometry_drift" in mem, sorted(mem)
    # ...and stayed out of the dump for the one that cannot, so an empty report is
    # never shown for a brand with no raw blob to compare.
    assert "roborock_geometry_drift" not in other, sorted(other)
    # And it degraded rather than raising -- there is no live coordinator here.
    assert "roborock_geometry_drift_error" not in mem, mem.get(
        "roborock_geometry_drift_error")


async def test_diag30_a_recorded_refresh_outcome_is_read_not_deduced(hass):
    """[DIAG-30] ISSUE #55 - the dump carries the last room-source refresh outcome,
    and its ABSENCE means "never asked" rather than "nothing wrong".

    The incident is recorded at the call site: without this field the self-check
    had to infer "why has this device no rooms" from the shape of its entity list,
    and that inference told a ROBOROCK owner to go and set his rooms up in the
    EUFY app. A recorded reason is a reading, not a guess.

    BOTH STATES ARE ASSERTED, because `get_last_refresh_outcome`'s own docstring
    warns that they read alike and are opposite: "{} MEANS 'NEVER ASKED', NOT
    'NOTHING WRONG'". The `if outcome:` guard at the call site is what keeps the
    two apart in the dump, and a test of either state alone cannot see it.

    This is the call-site half of work whose engine is now at 100 %:
    `SR-16`..`SR-24` cover the refresher itself.

    RED: drop the `if outcome:` and the never-asked case gains an empty block;
    drop the assignment and the recorded reason never reaches the dump.
    """
    from custom_components.eufy_vacuum.rooms.source_refresh import (
        record_refresh_outcome,
    )

    manager = _make_manager()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    hass.states.async_set(VACUUM, "docked", {"segments": []})
    entry = _entry()
    entry.add_to_hass(hass)

    # NEVER ASKED: the key must be absent, not an empty block.
    before = await async_get_config_entry_diagnostics(hass, entry)
    assert "room_source_refresh" not in before["vacuums"][0], (
        "an un-refreshed vacuum must not carry an empty outcome -- that reads as "
        "'asked, nothing wrong'"
    )

    # ASKED, AND REFUSED FOR A NAMED REASON -- the #55 case.
    record_refresh_outcome(
        hass, VACUUM, {"ok": False, "reason": "not_service_source"}
    )
    after = await async_get_config_entry_diagnostics(hass, entry)

    outcome = after["vacuums"][0]["room_source_refresh"]
    assert outcome["ok"] is False, outcome
    assert outcome["reason"] == "not_service_source", outcome
