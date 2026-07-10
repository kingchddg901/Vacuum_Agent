"""start_run_profile — a stepped-profile stash must not LEAK when the start is refused.

start_run_profile stashes a charge/wait profile's ordered steps into
``data['_pending_run_steps'][vac][map]`` and then calls start_selected_rooms, which POPS the
stash only deep in _build_effective_start_plan. When start_selected_rooms returns EARLY (blocked,
or requires_confirmation without a token) it never reaches the pop, so the stash leaks — and the
NEXT plain Start on that map pops the leak and silently becomes a charge/wait run.

start_run_profile now deletes the leftover stash whenever the start did not report started.

[LEAK-1] a refused start (blocked) deletes the leaked stash.
[LEAK-2] a refused start (confirmation required, no token) deletes the leaked stash.
[LEAK-3] a SUCCESSFUL start does not touch the stash cleanup path (the plan builder already
         popped it — nothing to delete, and a foreign stash for another map is untouched).
[LEAK-4] a profile with NO charge/wait steps never stashes, so there is nothing to leak.
"""

from __future__ import annotations

import pytest

_VAC = "vacuum.ivy"
_MAP = "Main floor"

_STEPS = [
    {"type": "room_group", "rooms": [{"room_id": 1}]},
    {"type": "charge_wait", "target_battery_percent": 95},
    {"type": "room_group", "rooms": [{"room_id": 2}]},
]


def _stub_profile(manager, monkeypatch, *, steps):
    """Stub the profile plumbing start_run_profile calls so the test isolates the stash
    lifecycle. apply_run_profile succeeds; the saved store returns a profile with `steps`;
    build_queue / build_room_payload are no-ops."""
    monkeypatch.setattr(
        manager.profiles, "apply_run_profile",
        lambda **kw: {"applied": True, "profile": {"id": kw.get("profile_id")}},
    )
    monkeypatch.setattr(
        manager.profiles, "_get_saved_run_profile_store",
        lambda **kw: {"p1": {"steps": steps}},
    )
    monkeypatch.setattr(manager, "build_queue", lambda **kw: None)
    monkeypatch.setattr(manager, "build_room_payload", lambda **kw: None)


def _pending(manager):
    return manager.data.get("_pending_run_steps", {}).get(_VAC, {})


async def test_refused_blocked_start_clears_stash(hass, manager, monkeypatch):
    """[LEAK-1]"""
    _stub_profile(manager, monkeypatch, steps=_STEPS)

    async def _blocked(**kw):
        return {"started": False, "reason": "vacuum_busy", "message": "blocked"}

    monkeypatch.setattr(manager, "start_selected_rooms", _blocked)

    out = await manager.start_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1")
    assert out["started"] is False
    assert _MAP not in _pending(manager)   # leaked stash cleaned up


async def test_refused_confirmation_clears_stash(hass, manager, monkeypatch):
    """[LEAK-2]"""
    _stub_profile(manager, monkeypatch, steps=_STEPS)

    async def _needs_confirm(**kw):
        return {"started": False, "reason": "confirmation_required", "message": "confirm"}

    monkeypatch.setattr(manager, "start_selected_rooms", _needs_confirm)

    out = await manager.start_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1")
    assert out["started"] is False
    assert _MAP not in _pending(manager)


async def test_successful_start_leaves_foreign_stash(hass, manager, monkeypatch):
    """[LEAK-3] the started path consumes THIS map's stash in the plan builder; the cleanup
    must not touch an unrelated map's stash. We simulate the real pop (started=True) and seed
    a foreign-map stash to prove the cleanup is scoped to this map only."""
    _stub_profile(manager, monkeypatch, steps=_STEPS)

    async def _started(**kw):
        # The real plan builder pops THIS map's stash on a started dispatch; emulate that.
        manager.data.get("_pending_run_steps", {}).get(_VAC, {}).pop(_MAP, None)
        return {"started": True, "reason": "started"}

    monkeypatch.setattr(manager, "start_selected_rooms", _started)
    # A stash for a DIFFERENT map that must survive.
    manager.data.setdefault("_pending_run_steps", {}).setdefault(_VAC, {})["Upstairs"] = _STEPS

    out = await manager.start_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1")
    assert out["started"] is True
    assert _MAP not in _pending(manager)       # this map consumed (by the builder emulation)
    assert "Upstairs" in _pending(manager)     # foreign stash untouched


async def test_no_charge_step_never_stashes(hass, manager, monkeypatch):
    """[LEAK-4] a plain rooms-only profile has no charge/wait step, so nothing is ever
    stashed and the refused-start cleanup is a harmless no-op."""
    _stub_profile(manager, monkeypatch, steps=[{"type": "room_group", "rooms": [{"room_id": 1}]}])

    async def _blocked(**kw):
        return {"started": False, "reason": "vacuum_busy"}

    monkeypatch.setattr(manager, "start_selected_rooms", _blocked)

    out = await manager.start_run_profile(vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1")
    assert out["started"] is False
    assert _MAP not in _pending(manager)
