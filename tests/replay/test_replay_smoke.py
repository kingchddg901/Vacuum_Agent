"""[RPL-1] Replay-harness proof-of-life: the pj_2026-08-02T23-04-45 group phase.

Replays the REAL recorder window of 2026-08-03 06:04–06:21Z (Kitchen phase →
1-min wait → Entryway+Home Office group dispatch → dock) through the production
listener layer. No dispatched job exists in this environment, so the lifecycle
listener must classify the activity as an EXTERNAL (app-started) run — which
makes this a real end-to-end exercise of external capture driven by the
device's own recorded signals rather than synthetic fixtures.

Asserts three things a mock-based test cannot certify:
  1. the run was NOTICED — an active-job slot opened for the vacuum during
     replay (observed mid-replay via the probe hook, not inferred at the end);
  2. counter evidence was BUFFERED from the real stream;
  3. the final state settled — the vacuum is docked and no slot is left
     claiming to be mid-run ("started"/"external" with no end).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN

from ..replay.bundle import load_bundle
from ..replay.harness import apply_initial, replay, _t

FIXTURE = Path(__file__).parent.parent / "fixtures" / "replays" / "alfred_pj_group_phase.json"
VAC = "vacuum.alfred"

# Static context the states-only CSV export cannot carry (these entities never
# changed inside the export window). Each line is an explicit assumption about
# the source install, mirrored from its diagnostics at capture time.
SUPPLEMENT = {
    "sensor.alfred_active_map": "12",
}


async def test_replay_pj_group_phase_drives_external_capture(hass, mock_config_entry, freezer):
    bundle = load_bundle(FIXTURE)

    # Pin the clock to the window start BEFORE anything initializes, so setup
    # itself happens at the recorded moment.
    freezer.move_to(_t(bundle["meta"]["window"][0]))

    # Same full-boot pattern as test_init_setup: real http, panel surface patched
    # out (the bare test env has no frontend component). Setup runs FIRST, on an
    # empty state machine, so the integration's own entities register under their
    # canonical ids — the registry then tells us which bundle entities are OURS.
    await async_setup_component(hass, "http", {})
    # Real Eufy installs have the vacuum in the entity registry owned by `robovac_mqtt`;
    # brand resolution matches on that platform, so without it no adapter registers.
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "alfred_unique_id", suggested_object_id="alfred"
    )
    mock_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.panel_custom.async_register_panel", AsyncMock()),
        patch("homeassistant.components.frontend.async_remove_panel"),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    manager = hass.data[DOMAIN][DATA_RUNTIME]

    # Replay is stimulus-only: the export also captured this integration's own
    # output entities, and those must not be echoed back in as inputs.
    registry = er.async_get(hass)
    ours = {e.entity_id for e in er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)}

    apply_initial(hass, bundle, SUPPLEMENT, skip=ours)
    await hass.async_block_till_done()

    # Manage the vacuum + mirror the source install's map 12 rooms so room
    # resolution has the same world the recorded run happened in.
    manager.ensure_vacuum_record(vacuum_entity_id=VAC)
    manager.data.setdefault("discovery", {}).setdefault(VAC, {})["12"] = {
        "active_map_id": "12",
        "rooms": [
            {"room_id": 5, "map_id": "12", "name": "Kitchen"},
            {"room_id": 8, "map_id": "12", "name": "Entryway"},
            {"room_id": 9, "map_id": "12", "name": "Home Office"},
        ],
    }
    manager.save_managed_rooms(vacuum_entity_id=VAC, map_id="12")

    # Probe: record the first moment an active-job slot exists, and the most
    # counter evidence ever seen buffered — the slot is CONSUMED by finalize, so
    # mid-run observation is the only honest way to assert capture happened.
    seen_slot_at: list[str] = []
    max_samples = 0

    def probe(_i, t_iso, _entity, _state):
        nonlocal max_samples
        slots = manager.data.get("active_jobs", {}).get(VAC) or {}
        if slots and not seen_slot_at:
            seen_slot_at.append(t_iso)
        for s in slots.values():
            if isinstance(s, dict):
                max_samples = max(max_samples, len(s.get("counter_samples") or []))

    # settle_s covers EXTERNAL_FINALIZE_GRACE_S (300s) plus recheck headroom —
    # the finalize is SCHEDULED off the run's tail and needs the clock to reach it.
    n = await replay(hass, bundle, freezer, skip=ours, settle_s=900, on_event=probe)
    assert 0 < n <= len(bundle["events"])

    # 1. The run was noticed while it was happening.
    assert seen_slot_at, "no active-job slot ever opened — the lifecycle listener never noticed the run"

    # 2. Real counter evidence was buffered mid-run from the recorded stream.
    assert max_samples > 0, "no counter_samples ever buffered — job-metrics listener saw none of the stream"

    # 3. The world settled: docked, the grace-finalize consumed the capture (no
    #    slot still claims to be mid-run), and the run reached the review queue.
    assert hass.states.get(VAC).state == "docked"
    for s in (manager.data.get("active_jobs", {}).get(VAC) or {}).values():
        if isinstance(s, dict) and s.get("status") in ("started", "external"):
            assert s.get("ended_at"), f"slot still mid-run after the recorded run ended: {s.get('job_id')}"
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore

    ext_dir = LearningHistoryStore(hass).get_paths(vacuum_entity_id=VAC).root / "external_jobs"
    written = list(ext_dir.glob("job_*.json")) if ext_dir.exists() else []
    assert written, "external finalize wrote no pending record to external_jobs/"
