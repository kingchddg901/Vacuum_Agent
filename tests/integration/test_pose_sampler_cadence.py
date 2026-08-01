"""RP-012/RF-31 — pose sampler per-vacuum cadence, in-flight guard, tick isolation.

ONE shared ticker runs at min(intervals) across configured vacuums, but before
this each tick sampled EVERY vacuum regardless of its OWN declared interval --
a slower vacuum's samples were then valued at the ticker's (faster) cadence by
the room-attribution engine's dwell=n*interval_s math, over-weighting it. A
raising sample for one vacuum also killed the whole tick (no per-vacuum
isolation), and nothing stopped a slow live-pose await from overlapping with
the NEXT tick for the SAME vacuum.

[PC-1] POSE-1: each vacuum is sampled only at its OWN declared interval, not
       the shared ticker's (faster) cadence.
[PC-2] POSE-5: one vacuum's sampling exception does not stop a later vacuum
       from being sampled the same tick.
[PC-3] POSE-2: a vacuum whose previous sample is still in flight is skipped,
       not sampled again, on the next tick.
"""

from __future__ import annotations

import asyncio

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.listeners import pose_sampler

_VAC_FAST = "vacuum.alfred"   # 1s interval
_VAC_SLOW = "vacuum.ivy"      # 5s interval

_INTERVALS = {_VAC_FAST: 1.0, _VAC_SLOW: 5.0}


def _register_tick(hass, manager, monkeypatch):
    """Register the sampler with a captured (not scheduled) tick handler, and
    a controllable fake loop clock. Returns (tick_handler, fake_time_box)."""
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = manager
    monkeypatch.setattr(manager, "get_known_vacuum_ids", lambda: [_VAC_FAST, _VAC_SLOW])
    monkeypatch.setattr(
        pose_sampler, "_room_attribution_interval_s",
        lambda vid: _INTERVALS.get(vid),
    )

    fake_time = [0.0]
    monkeypatch.setattr(hass.loop, "time", lambda: fake_time[0])

    captured: list = []

    def _capture(hass_arg, handler, interval):
        captured.append(handler)
        return lambda: None

    original = pose_sampler.async_track_time_interval
    pose_sampler.async_track_time_interval = _capture
    try:
        pose_sampler.register(hass)
    finally:
        pose_sampler.async_track_time_interval = original

    assert captured, "pose_sampler did not register a tick (interval resolution failed?)"
    return captured[0], fake_time


async def test_each_vacuum_sampled_at_its_own_interval(hass, manager, monkeypatch):
    """[PC-1] the shared 1s ticker fires 5 times over 5 simulated seconds; the
    fast vacuum (1s) is sampled every tick, the slow vacuum (5s) only once."""
    sampled: list[str] = []

    async def _fake_sample(hass_arg, manager_arg, vacuum_entity_id):
        sampled.append(vacuum_entity_id)
        return 0

    monkeypatch.setattr(pose_sampler, "_sample_vacuum_once", _fake_sample)
    tick, fake_time = _register_tick(hass, manager, monkeypatch)
    # Start well past zero -- hass.loop.time() is a real monotonic uptime clock
    # in production, never near zero; starting at 0.0 here would artificially
    # collide with _last_sample_ts's own 0.0 default on the very first tick.
    fake_time[0] = 100.0

    for _ in range(5):
        await tick(None)
        fake_time[0] += 1.0

    assert sampled.count(_VAC_FAST) == 5
    assert sampled.count(_VAC_SLOW) == 1


async def test_one_vacuum_exception_does_not_block_the_other(hass, manager, monkeypatch):
    """[PC-2] POSE-5: vacuum.alfred's sample raises; vacuum.ivy must still be
    reached the same tick (both due -- fake_time starts past both intervals)."""
    sampled: list[str] = []

    async def _fake_sample(hass_arg, manager_arg, vacuum_entity_id):
        if vacuum_entity_id == _VAC_FAST:
            raise RuntimeError("sample failed (test fixture)")
        sampled.append(vacuum_entity_id)
        return 0

    monkeypatch.setattr(pose_sampler, "_sample_vacuum_once", _fake_sample)
    tick, fake_time = _register_tick(hass, manager, monkeypatch)
    fake_time[0] = 10.0  # both vacuums' intervals already elapsed

    await tick(None)

    assert sampled == [_VAC_SLOW]


async def test_in_flight_vacuum_is_skipped_not_resampled(hass, manager, monkeypatch):
    """[PC-3] POSE-2: a second tick firing while the first vacuum's sample is
    still running must skip it, not sample it again concurrently."""
    entered = asyncio.Event()
    release = asyncio.Event()
    call_count = {"n": 0}

    async def _fake_sample(hass_arg, manager_arg, vacuum_entity_id):
        if vacuum_entity_id == _VAC_FAST:
            call_count["n"] += 1
            entered.set()
            await release.wait()
        return 0

    monkeypatch.setattr(pose_sampler, "_sample_vacuum_once", _fake_sample)
    tick, fake_time = _register_tick(hass, manager, monkeypatch)
    fake_time[0] = 10.0

    first = asyncio.ensure_future(tick(None))
    await asyncio.wait_for(entered.wait(), timeout=5)

    await tick(None)   # second tick: vacuum.alfred is in flight -> must skip
    await asyncio.sleep(0)
    assert call_count["n"] == 1, "the in-flight vacuum was sampled concurrently"

    release.set()
    await first
