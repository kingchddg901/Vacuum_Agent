"""Zone phase — clean a saved zone (or several) as a step in a phased run (Wave: zone step).

A zone is a CLEAN action, not a pause: it dispatches saved-zone rects via
``dispatch_zone_clean`` and completes like a room group (the external completion hook
advances it — completion is dock/clean-complete-signal driven, not room-counter gated),
unlike a charge_wait/wait which a dock poller drives.

[ZN-1] _build_steps_phases: a zone step -> a zone phase interleaved between room groups.
[ZN-2] a rooms+zone run with NO charge/wait stays MULTI-phase (never collapses to one atomic clean).
[ZN-3] a zone whose ids resolve to no geometry is dropped (like an empty room_group).
[ZN-4] advancing INTO a zone phase routes to the room watchdog, NOT the dock poller.
[ZN-5] _dispatch_active_phase on a zone phase fires dispatch_zone_clean with the rects (no segment payload).
[ZN-6] a completed zone phase advances to the next phase (participates in the normal cycle).
"""

from __future__ import annotations

import custom_components.eufy_vacuum.jobs.phase_runner as phase_runner_mod

_VAC = "vacuum.ivy"
_MAP = "Main floor"


def _room_phase(rid: int, slug: str) -> dict:
    return {"resolved_rooms": [{"room_id": rid, "slug": slug}], "queue_room_ids": [rid],
            "payload": {}, "room_count": 1}


def _zone_phase(zone_ids=("z_a",), zones=None) -> dict:
    return {"phase_type": "zone", "zone_ids": list(zone_ids),
            "zones": zones if zones is not None else [[0.1, 0.1, 0.2, 0.2]],
            "resolved_rooms": [], "queue_room_ids": [], "payload": {}, "room_count": 0}


def _rg(*ids):
    return {"type": "room_group", "rooms": [{"room_id": i} for i in ids]}


def _zn(*zone_ids):
    return {"type": "zone", "zone_ids": list(zone_ids)}


def _seed(manager, job: dict) -> None:
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job


async def _noop_coro():
    return None


def _spy(name: str, calls: dict):
    def _f(**kw):
        calls[name] += 1
        return _noop_coro()
    return _f


def _steps_phases(manager, monkeypatch, run_steps, included, *, resolves=True):
    """Materialize steps -> phases with the brand engine + zone resolver faked, so we test
    the interleave/collapse logic. resolves=False -> the zone resolver finds no geometry."""
    monkeypatch.setattr(
        manager.run_plan, "_build_dispatch_phases",
        lambda **kw: [{"ids": list(kw["queue_room_ids"]), "queue_room_ids": list(kw["queue_room_ids"])}],
    )

    def _resolve(**kw):
        return [] if not resolves else [[0.1, 0.1, 0.2, 0.2] for _ in kw["zone_ids"]]

    monkeypatch.setattr(manager, "_resolve_saved_zone_rects", _resolve)
    return manager.run_plan._build_steps_phases(
        vacuum_entity_id=_VAC, map_id=_MAP, effective_rooms={}, included_room_ids=set(included),
        run_steps=run_steps, strict_order=False,
    )


async def test_zone_step_interleaves(hass, manager, monkeypatch):
    """[ZN-1] a zone step becomes a zone phase between the room groups, one rect per id."""
    phases = _steps_phases(manager, monkeypatch, [_rg(1, 2), _zn("z_a", "z_b"), _rg(3)], included={1, 2, 3})
    assert phases[0]["ids"] == [1, 2]
    assert phases[1]["phase_type"] == "zone"
    assert phases[1]["zone_ids"] == ["z_a", "z_b"]
    assert len(phases[1]["zones"]) == 2
    assert phases[2]["ids"] == [3]


async def test_rooms_plus_zone_stays_multiphase(hass, manager, monkeypatch):
    """[ZN-2] no charge/wait, but a zone still forces multi-phase (else the zone would be lost)."""
    phases = _steps_phases(manager, monkeypatch, [_rg(1), _zn("z_a"), _rg(2)], included={1, 2})
    assert [p.get("phase_type", "room") for p in phases] == ["room", "zone", "room"]


async def test_zone_no_geometry_dropped(hass, manager, monkeypatch):
    """[ZN-3] a zone that resolves to nothing is skipped; with no zone/break left, collapses to atomic."""
    phases = _steps_phases(manager, monkeypatch, [_rg(1), _zn("z_missing"), _rg(2)],
                           included={1, 2}, resolves=False)
    assert all(p.get("phase_type") != "zone" for p in phases)
    assert phases[0]["ids"] == [1, 2]  # rooms folded into one atomic clean


async def test_advance_into_zone_spawns_room_watchdog(hass, manager, monkeypatch):
    """[ZN-4] a zone is a clean phase -> the room watchdog, not the charge/wait dock poller."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    calls = {"charge": 0, "room": 0}
    monkeypatch.setattr(manager.phase_runner, "_run_charge_wait_phase", _spy("charge", calls))
    monkeypatch.setattr(manager.phase_runner, "_run_advanced_phase", _spy("room", calls))
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase()],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 5, "slug": "kitchen"}], "queue_room_ids": [5],
        "counter_samples": [],
    }
    _seed(manager, job)
    assert await manager.phase_runner.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert calls == {"charge": 0, "room": 1}


async def test_zone_phase_dispatches_via_zone_clean(hass, manager, monkeypatch):
    """[ZN-5] dispatching a zone phase fires dispatch_zone_clean with the phase's rects and
    sends NO room/segment payload."""
    calls = {"zone": None, "room": 0}

    async def _zone_clean(**kw):
        calls["zone"] = kw.get("zones")
        return {"ok": True}

    async def _room_dispatch(**kw):
        calls["room"] += 1

    monkeypatch.setattr(manager, "dispatch_zone_clean", _zone_clean)
    monkeypatch.setattr(manager, "_dispatch_clean_payload", _room_dispatch)
    rects = [[0.1, 0.1, 0.3, 0.3], [0.5, 0.5, 0.7, 0.7]]
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase(("z_a", "z_b"), rects)],
        "current_phase_index": 1, "phase_count": 2,
        "resolved_rooms": [], "queue_room_ids": [],
    }
    _seed(manager, job)
    await manager.phase_runner._dispatch_active_phase(vacuum_entity_id=_VAC, map_id=_MAP, job=job)
    assert calls["zone"] == rects
    assert calls["room"] == 0


async def test_zone_phase_completes_and_advances(hass, manager, monkeypatch):
    """[ZN-6] a completed zone advances to the next phase (the external completion hook drives
    it exactly like a room group), re-dispatching the following room via the watchdog."""
    monkeypatch.setattr(phase_runner_mod, "_iso_now", lambda: "2026-01-01T00:05:00Z")
    calls = {"charge": 0, "room": 0}
    monkeypatch.setattr(manager.phase_runner, "_run_charge_wait_phase", _spy("charge", calls))
    monkeypatch.setattr(manager.phase_runner, "_run_advanced_phase", _spy("room", calls))
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "phases": [_room_phase(5, "kitchen"), _zone_phase(), _room_phase(8, "dining")],
        "current_phase_index": 1,
        "resolved_rooms": [], "queue_room_ids": [], "counter_samples": [],
    }
    _seed(manager, job)
    assert await manager.phase_runner.maybe_advance_phase(vacuum_entity_id=_VAC, map_id=_MAP) is True
    assert manager.data["active_jobs"][_VAC][_MAP]["current_phase_index"] == 2
    assert calls == {"charge": 0, "room": 1}  # advanced into the next ROOM phase via the watchdog
