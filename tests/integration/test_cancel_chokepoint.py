"""RP-010/RF-06 — cancel/pause effective at the dispatch chokepoint (phase_runner half).

_dispatch_active_phase performed four sequential awaits without ever re-reading
the job, so a cancel/pause landing anywhere in that window still reached the
wire send; maybe_advance_phase never consulted _cancel_in_flight, so a
cancel's own return-to-base dock could read as phase completion and advance
the job mid-cancel. See test_cancel_single_flight.py for the active_job.py
half (single-flight latch + failure recovery).

[CC-1] _dispatch_active_phase aborts at the chokepoint when _cancel_in_flight
       is set on the stored job (the re-read happens after the last await).
[CC-2] _dispatch_active_phase aborts when status is no longer "started"
       (the pause flavour -- pause needs no new flag, this re-read is the guard).
[CC-3] _dispatch_active_phase proceeds normally on the happy path (sanity).
[CC-6] maybe_advance_phase suppresses (returns False, no mutation) while
       _cancel_in_flight is set.
[CC-7] maybe_advance_phase behaves normally when no cancel is in flight (sanity).
[CC-8] IN5TNKMD: the chokepoint re-reads FROM THE STORE, not from the `job`
       parameter, for an intent that lands INSIDE the await window.
"""

from __future__ import annotations

import copy
from unittest.mock import create_autospec

import pytest

_VAC = "vacuum.alfred"
_MAP = "6"


def _room_phase(room_ids: list[int]) -> dict:
    return {
        "phase_type": "room_group",
        "queue_room_ids": list(room_ids),
        "resolved_rooms": [{"room_id": r, "slug": f"room_{r}"} for r in room_ids],
        "payload": {"segments": list(room_ids), "repeat": 1},
    }


def _seed_phased_job(manager, **extra) -> dict:
    job = {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "status": "started",
        "job_id": "j1", "started_at": "2026-01-01T00:00:00+00:00",
        "queue_room_ids": [1, 2],
        "phases": [_room_phase([1]), _room_phase([2])],
        "current_phase_index": 0,
        "resolved_rooms": [{"room_id": 1, "slug": "room_1"}],
        "payload": {"segments": [1], "repeat": 1},
    }
    job.update(extra)
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


# ---------------------------------------------------------------------------
# [CC-1..3] _dispatch_active_phase chokepoint
# ---------------------------------------------------------------------------

async def _wire_dispatch_collaborators(manager, monkeypatch, *, sends: list) -> None:
    async def _pre_calls(**kw):
        return None

    async def _apply_settings(*a, **kw):
        return None

    async def _resolve(**kw):
        return kw.get("payload", {})

    async def _send(**kw):
        sends.append(kw.get("payload"))

    monkeypatch.setattr(manager, "_run_global_pre_calls", _pre_calls)
    monkeypatch.setattr(manager.active_job, "apply_per_room_live_settings_awaited", _apply_settings)
    monkeypatch.setattr(manager, "_resolve_live_dispatch_payload", _resolve)
    monkeypatch.setattr(manager, "_dispatch_clean_payload", _send)


async def test_dispatch_aborts_when_cancel_in_flight(manager, monkeypatch):
    """[CC-1] the stored job's _cancel_in_flight (set by a concurrent cancel
    between this attempt's read and its send) aborts the send."""
    job = _seed_phased_job(manager)
    sends: list = []
    await _wire_dispatch_collaborators(manager, monkeypatch, sends=sends)
    # simulate a cancel landing after this attempt read `job` but before the send
    manager.data["active_jobs"][_VAC][_MAP]["_cancel_in_flight"] = True

    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=job, attempt=1,
    )
    assert sends == []


async def test_dispatch_aborts_when_no_longer_started(manager, monkeypatch):
    """[CC-2] pause flavour: status flips away from "started" (pause's own
    round-trip landed) -- the chokepoint's status re-read is the guard; pause
    needs no dedicated flag."""
    job = _seed_phased_job(manager)
    sends: list = []
    await _wire_dispatch_collaborators(manager, monkeypatch, sends=sends)
    manager.data["active_jobs"][_VAC][_MAP]["status"] = "paused"

    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=job, attempt=1,
    )
    assert sends == []


async def test_dispatch_proceeds_on_happy_path(manager, monkeypatch):
    """[CC-3] sanity: an untouched, still-started job dispatches normally."""
    job = _seed_phased_job(manager)
    sends: list = []
    await _wire_dispatch_collaborators(manager, monkeypatch, sends=sends)

    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=job, attempt=1,
    )
    assert len(sends) == 1


# ---------------------------------------------------------------------------
# [CC-8] IN5TNKMD — the re-read is FROM THE STORE, not from the parameter
# ---------------------------------------------------------------------------
# WHY [CC-1..3] DO NOT COVER THIS. Those three pass `job` as the SAME OBJECT
# `_seed_phased_job` stored, so `manager.data[...][_MAP] is job` and writing to
# the store writes to the parameter. Store and parameter are indistinguishable,
# and a chokepoint that consults the stale parameter passes all three. Measured:
# replacing the store read in `_dispatch_active_phase` with the `job` parameter
# leaves [CC-1..3] green. That is the aliasing form of [DE-W1] — the assertion
# looks at a subject that cannot disagree with itself.
#
# A real attempt's `job` is a SNAPSHOT: read before four sequential awaits, and
# blind to anything written after. So these tests pass a deep copy, and land the
# intent INSIDE the last await (`_resolve_live_dispatch_payload`) — the exact
# interleaving IN5TNKMD names, which also makes a re-read hoisted ABOVE that
# await go red rather than a re-read that merely exists.
#
# The three landings are the chokepoint's own three abort conditions, verbatim
# from its predicate — a missing record is a different bug from a live cancel.

def _land_cancel_in_flight(manager) -> None:
    """A Cancel Run latched by jobs/active_job.py while this attempt was awaiting."""
    manager.data["active_jobs"][_VAC][_MAP]["_cancel_in_flight"] = True


def _land_status_not_started(manager) -> None:
    """A Pause whose own round-trip landed while this attempt was awaiting."""
    manager.data["active_jobs"][_VAC][_MAP]["status"] = "paused"


def _land_record_gone(manager) -> None:
    """The stored record vanished mid-window (finalize/reset raced this attempt)."""
    del manager.data["active_jobs"][_VAC][_MAP]


def _wire_chokepoint_harness(manager, monkeypatch, *, land=None):
    """Wire the four awaits that precede the wire send; return the send stand-in.

    ``land`` fires INSIDE the last of them, so the store changes after this
    attempt's snapshot was taken and before the chokepoint reads.

    The send is a ``create_autospec`` of the REAL bound method rather than a
    ``**kw`` closure: the closure agrees with its caller and would accept a call
    the manager itself would reject, so it can prove the send happened but not
    that it happened in a shape production could make.
    """
    async def _pre_calls(**kw):
        return None

    async def _apply_settings(*a, **kw):
        return None

    async def _resolve(**kw):
        if land is not None:
            land(manager)
        return kw.get("payload", {})

    # Spec off the CLASS, bound to this manager: by the second call in a test the
    # INSTANCE attribute is already a mock from the first, and create_autospec
    # refuses to spec a mock (which is the right refusal -- a mock of a mock
    # inherits the first one's permissiveness and specs nothing).
    real_send = type(manager)._dispatch_clean_payload.__get__(manager)
    send = create_autospec(real_send)
    monkeypatch.setattr(manager, "_run_global_pre_calls", _pre_calls)
    monkeypatch.setattr(manager.active_job, "apply_per_room_live_settings_awaited", _apply_settings)
    monkeypatch.setattr(manager, "_resolve_live_dispatch_payload", _resolve)
    monkeypatch.setattr(manager, "_dispatch_clean_payload", send)
    return send


@pytest.mark.parametrize(
    "land",
    [_land_cancel_in_flight, _land_status_not_started, _land_record_gone],
    ids=["_cancel_in_flight", "status_not_started", "record_gone"],
)
async def test_chokepoint_re_reads_the_store_not_the_attempt_snapshot(
    manager, monkeypatch, land,
):
    """[CC-8] IN5TNKMD: an intent that lands inside the await window is seen.

    The consequence if it is not: "User presses Cancel Run. The robot heads for
    the dock, then turns around and cleans the next room" -- and the run is then
    recorded as a successful full completion and fed to the learning set.

    Two halves, and the first is load-bearing. Half 1 is the POSITIVE CONTROL:
    the identical harness, with nothing landing, must reach the wire carrying
    this phase's real payload. Without it "the send did not happen" is satisfied
    by any harness that never reaches the send -- including a degenerate `job`,
    for which the control's payload assertion is what goes red.
    """
    stored = _seed_phased_job(manager)
    # what a real attempt carries: a snapshot, not the live record
    snapshot = copy.deepcopy(stored)
    assert snapshot is not manager.data["active_jobs"][_VAC][_MAP]

    # --- half 1: the control. This harness DOES reach the wire. ---
    send = _wire_chokepoint_harness(manager, monkeypatch)
    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=snapshot, attempt=1,
    )
    assert send.await_count == 1, (
        "the control never reached the wire send, so the abort half below proves "
        "nothing -- fix the harness before reading its result"
    )
    assert send.await_args.kwargs["vacuum_entity_id"] == _VAC
    assert send.await_args.kwargs["payload"] == {"segments": [1], "repeat": 1}

    # --- half 2: same harness, the intent lands inside the last await. ---
    send = _wire_chokepoint_harness(manager, monkeypatch, land=land)
    await manager.phase_runner._dispatch_active_phase(
        vacuum_entity_id=_VAC, map_id=_MAP, job=snapshot, attempt=2,
    )

    # the store learned; the parameter, being a snapshot, could not
    assert snapshot["status"] == "started"
    assert "_cancel_in_flight" not in snapshot
    assert send.await_count == 0, (
        "the chokepoint dispatched to a moving robot after the intent landed: it "
        "read the stale `job` parameter (or re-read above the last await) instead "
        "of the stored job -- IN5TNKMD, jobs/phase_runner.py"
    )


# ---------------------------------------------------------------------------
# [CC-6..7] maybe_advance_phase suppression during cancel
# ---------------------------------------------------------------------------

async def test_maybe_advance_phase_suppressed_during_cancel(manager):
    """[CC-6] a cancel's own return-to-base dock must not read as phase
    completion -- maybe_advance_phase suppresses and leaves the phase index
    untouched while a cancel owns finalization."""
    _seed_phased_job(
        manager,
        _cancel_in_flight=True,
        _phase_dispatch_pending=False,  # released by the cancel path, by design
    )
    advanced = await manager.phase_runner.maybe_advance_phase(
        vacuum_entity_id=_VAC, map_id=_MAP,
    )
    assert advanced is False
    assert manager.data["active_jobs"][_VAC][_MAP]["current_phase_index"] == 0


async def test_maybe_advance_phase_normal_when_no_cancel(manager, monkeypatch):
    """[CC-7] sanity: a genuinely finished phase with no cancel in flight still
    advances normally."""
    job = _seed_phased_job(manager)
    monkeypatch.setattr(manager, "_phase_timing", lambda _vac: {
        "settle_seconds": 0, "dock_settle_seconds": 0, "verify_seconds": 0,
        "confirm_seconds": 0, "poll_seconds": 0, "max_attempts": 1,
    })
    monkeypatch.setattr(manager.hass, "async_create_task", lambda coro: coro.close())

    advanced = await manager.phase_runner.maybe_advance_phase(
        vacuum_entity_id=_VAC, map_id=_MAP,
    )
    assert advanced is True
    assert manager.data["active_jobs"][_VAC][_MAP]["current_phase_index"] == 1
