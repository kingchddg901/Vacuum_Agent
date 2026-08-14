"""ISSUE #50 — a saved run profile's room ORDER must survive the trip to dispatch.

`strict_order` makes a path-optimising brand clean rooms in queue order by dispatching one
room per phase. It reached `start_selected_rooms` from the direct service only. A profile
never passed it, so `start_run_profile` always dispatched with the default — and the exposed
profile BUTTON, which carries no service data at all, had no route to opt in by any means.
On Roborock (`honors_clean_order: False`) that silently discarded the profile's saved order
on every run, while the card's drag handles kept implying the order was honoured.

The flag is now persisted on the profile record and read at dispatch.

[SO-1] a profile saved with strict_order dispatches with strict_order=True
[SO-2] a LEGACY profile record with no such key dispatches False — the migration guarantee:
       every profile saved before this key existed keeps today's behaviour untouched
[SO-3] an explicit argument overrides a profile saved True  (True -> False)
[SO-4] an explicit argument overrides a profile saved False (False -> True)
[SO-5] the read path normalises a legacy record to False rather than KeyError-ing, which is
       what makes [SO-2] true for records already on disk
"""

from __future__ import annotations

_VAC = "vacuum.ivy"
_MAP = "Main floor"


def _stub_profile(manager, monkeypatch, *, profile):
    """Isolate the strict-order decision: apply succeeds, the store returns `profile`,
    queue/payload building are no-ops. Mirrors test_run_profile_step_leak's helper."""
    monkeypatch.setattr(
        manager.profiles, "apply_run_profile",
        lambda **kw: {"applied": True, "profile": {"id": kw.get("profile_id")}},
    )
    monkeypatch.setattr(
        manager.profiles, "_get_saved_run_profile_store",
        lambda **kw: {"p1": profile},
    )
    monkeypatch.setattr(manager, "build_queue", lambda **kw: None)
    monkeypatch.setattr(manager, "build_room_payload", lambda **kw: None)


def _capture_dispatch(manager, monkeypatch):
    """Record the kwargs start_run_profile hands to dispatch."""
    seen: dict = {}

    async def _started(**kw):
        seen.update(kw)
        return {"started": True, "reason": "started"}

    monkeypatch.setattr(manager, "start_selected_rooms", _started)
    return seen


async def test_saved_strict_order_reaches_dispatch(hass, manager, monkeypatch):
    """[SO-1] The whole bug: this kwarg never used to arrive."""
    _stub_profile(manager, monkeypatch, profile={"strict_order": True})
    seen = _capture_dispatch(manager, monkeypatch)

    out = await manager.start_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1"
    )

    assert out["started"] is True
    assert seen["strict_order"] is True


async def test_legacy_profile_without_key_dispatches_false(hass, manager, monkeypatch):
    """[SO-2] MIGRATION GUARANTEE. Every profile saved before this key existed has no
    'strict_order' member at all. Those users' runs must be byte-identical to before —
    a new flag that silently switched existing profiles to sequenced per-room dispatch
    would change run duration, dock trips and learning attribution without asking."""
    _stub_profile(manager, monkeypatch, profile={"name": "saved long ago"})
    seen = _capture_dispatch(manager, monkeypatch)

    await manager.start_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1"
    )

    assert seen["strict_order"] is False


async def test_explicit_argument_overrides_saved_true(hass, manager, monkeypatch):
    """[SO-3] A service call can opt OUT for one run without editing the profile."""
    _stub_profile(manager, monkeypatch, profile={"strict_order": True})
    seen = _capture_dispatch(manager, monkeypatch)

    await manager.start_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1", strict_order=False
    )

    assert seen["strict_order"] is False


async def test_explicit_argument_overrides_saved_false(hass, manager, monkeypatch):
    """[SO-4] ...and opt IN, which is the reporter's own service-call workaround."""
    _stub_profile(manager, monkeypatch, profile={"strict_order": False})
    seen = _capture_dispatch(manager, monkeypatch)

    await manager.start_run_profile(
        vacuum_entity_id=_VAC, map_id=_MAP, profile_id="p1", strict_order=True
    )

    assert seen["strict_order"] is True


def test_read_path_normalises_legacy_record(hass, manager):
    """[SO-5] The enrich step is the only migration: `.get(key, False)` on read, so a
    record written before the key existed reads False instead of raising. No stored-data
    rewrite runs, and none is needed."""
    legacy = manager.profiles._enrich_saved_run_profile("p1", {"name": "saved long ago"})
    assert legacy["strict_order"] is False

    opted_in = manager.profiles._enrich_saved_run_profile(
        "p2", {"name": "ordered", "strict_order": True}
    )
    assert opted_in["strict_order"] is True
