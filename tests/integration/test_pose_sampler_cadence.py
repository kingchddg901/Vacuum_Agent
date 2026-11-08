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


async def test_pc4_a_vacuum_with_no_declared_interval_is_skipped_mid_loop(
    hass, manager, monkeypatch
):
    """[PC-4] A mixed fleet is the normal case, and one member declares nothing.

    Eufy and Roborock declare `room_attribution`; a Dreame, or any vacuum whose
    adapter has no such block, yields None from `_room_attribution_interval_s`.
    Without the `if own_interval is None: continue`, `now_ts - last < None` raises
    TypeError — and it raises in the TICK BODY, outside the per-vacuum try that
    POSE-5 installed, so the whole tick dies and every vacuum after it goes
    unsampled for that cycle.

    ⚠ THE INTERVAL-LESS VACUUM IS IN THE MIDDLE OF THE LIST ON PURPOSE. At the end,
    a `continue` wrongly written as `break` or `return` would be indistinguishable
    from the correct behaviour. In the middle, the vacuum AFTER it is what proves
    the loop continued rather than merely stopped quietly — the same positional
    reasoning as [LS-23].

    `register()` filters None intervals out of its own `min()`, so the ticker is
    still registered; this is purely about the per-vacuum loop.

    RED: delete the guard and the tick raises TypeError, leaving `sampled` empty.
    """
    sampled: list[str] = []

    async def _fake_sample(hass_arg, manager_arg, vacuum_entity_id):
        sampled.append(vacuum_entity_id)
        return 0

    no_interval = "vacuum.noattr"
    monkeypatch.setattr(pose_sampler, "_sample_vacuum_once", _fake_sample)
    tick, fake_time = _register_tick(hass, manager, monkeypatch)

    # AFTER _register_tick, which sets get_known_vacuum_ids itself -- setting it
    # before would simply be overwritten. Registering with two vacuums and ticking
    # with three is also the realistic shape: the fleet can change between
    # register() and any later tick.
    monkeypatch.setattr(
        manager, "get_known_vacuum_ids",
        lambda: [_VAC_FAST, no_interval, _VAC_SLOW],
    )
    # _INTERVALS has no entry for `no_interval`, so the patched resolver returns None
    # for it -- which is exactly what an adapter with no room_attribution block gives.
    assert _INTERVALS.get(no_interval) is None, "precondition: this vacuum declares none"
    fake_time[0] = 10.0

    await tick(None)

    assert sampled == [_VAC_FAST, _VAC_SLOW], (
        "the interval-less vacuum must be skipped, and the one AFTER it must still "
        f"be reached -- got {sampled}"
    )


async def test_in_flight_vacuum_is_skipped_not_resampled(hass, manager, monkeypatch):
    """[PC-3] POSE-2: a second tick firing while the first vacuum's sample is
    still running must skip it, not sample it again concurrently.

    ⚠ THE CLOCK MUST ADVANCE, and that is the correction this test carries. It used
    to fire both ticks at the same `fake_time` of 10.0, so the second tick's CADENCE
    guard (`now_ts - last < own_interval`, i.e. `0.0 < 1.0`) skipped alfred before
    the in-flight guard was ever reached. It passed — and it passed with the
    in-flight guard DELETED, measured by ablation. Coverage had been saying so all
    along: line 436 was never executed. Reaching the guard requires the cadence to
    have ELAPSED while the first sample is still suspended, which is why the second
    tick runs at 11.5.

    ⚠ `asyncio.wait_for` CANNOT BOUND ANYTHING IN THIS TEST, and that is why the
    second tick is scheduled and polled with `sleep(0)` instead of awaited under a
    timeout. `_register_tick` monkeypatches `hass.loop.time` to a frozen `fake_time`,
    and asyncio's timer machinery schedules against `loop.time()` — so a `wait_for`
    deadline of `11.5 + 5` is compared against a clock that never leaves 11.5 and
    never fires. Two drafts of this test hung on exactly that: without the guard the
    tick parks on `release.wait()` and the "timeout" waits forever. `sleep(0)` is a
    bare yield, special-cased by asyncio and clock-independent, so it still works
    under a frozen clock. (The pre-existing `wait_for(entered.wait(), timeout=5)`
    here was the same illusion: it only ever returned because the event was already
    set, never because it timed out.)

    The failure signal is therefore `second.done()`, not an exception: with the guard
    the tick finishes within a yield or two, and without it the tick is still parked,
    which makes the assertion red instead of leaving the suite stuck. The `finally`
    then releases unconditionally, so neither outcome leaves the loop holding a task
    that can never finish — which is where the hang moves to if cleanup is skipped.

    vacuum.ivy is the POSITIVE CONTROL. "alfred was not sampled twice" is equally
    what a second tick that did nothing at all produces. ivy is sampled exactly ONCE
    across both ticks, and the arithmetic is worth stating because it looks wrong:
    the first tick parks inside alfred before reaching ivy; the second tick samples
    ivy (11.5 - 0.0 >= 5.0) and stamps its `_last_sample_ts` at 11.5; when the first
    tick resumes, its own `now_ts` is still 10.0, so `10.0 - 11.5` is negative and
    its cadence check skips ivy rather than double-sampling it.

    RED: delete `if vacuum_entity_id in _in_flight: continue` and alfred is sampled
    a second time while its first sample is still in flight.
    """
    entered = asyncio.Event()
    release = asyncio.Event()
    sampled: list[str] = []

    async def _fake_sample(hass_arg, manager_arg, vacuum_entity_id):
        sampled.append(vacuum_entity_id)
        if vacuum_entity_id == _VAC_FAST:
            entered.set()
            await release.wait()
        return 0

    monkeypatch.setattr(pose_sampler, "_sample_vacuum_once", _fake_sample)
    tick, fake_time = _register_tick(hass, manager, monkeypatch)
    fake_time[0] = 10.0

    async def _settle(predicate, limit=50):
        """Yield until `predicate` holds, or `limit` yields have passed.

        `sleep(0)` rather than a timeout: see the clock note above.
        """
        for _ in range(limit):
            if predicate():
                return True
            await asyncio.sleep(0)
        return predicate()

    first = asyncio.ensure_future(tick(None))
    second = None
    try:
        assert await _settle(entered.is_set), "the first tick never reached alfred"
        assert sampled == [_VAC_FAST], (
            "precondition: the first tick is parked INSIDE alfred's sample, and has "
            "not yet reached ivy"
        )

        # Past alfred's own 1.0s interval (measured from 10.0), so the cadence guard
        # cannot be what skips it this time, and past ivy's 5.0s (from 0.0) so ivy
        # is due.
        fake_time[0] = 11.5
        second = asyncio.ensure_future(tick(None))

        assert await _settle(second.done), (
            "the second tick never finished: it sampled the in-flight vacuum and is "
            "parked on that sample's release, which is the overlap the guard exists "
            "to prevent"
        )
        second.result()   # surface anything the tick raised rather than swallowing it

        assert sampled.count(_VAC_FAST) == 1, (
            "the in-flight vacuum was sampled concurrently"
        )
        assert sampled.count(_VAC_SLOW) == 1, (
            "positive control: the second tick ran at all and got past alfred"
        )
    finally:
        # Unconditional: however the block above exits, the parked sample has to be
        # released and both ticks awaited, or the loop keeps a task that can never
        # finish and the hang reappears in teardown instead of failing here.
        release.set()
        for pending in (second, first):
            if pending is not None:
                await asyncio.gather(pending, return_exceptions=True)

    assert sampled.count(_VAC_FAST) == 1, "no resample once the first tick resumed"
    assert sampled.count(_VAC_SLOW) == 1, "and the resumed tick does not double-sample ivy"
