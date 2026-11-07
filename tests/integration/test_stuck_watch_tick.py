"""core/manager.py::apply_stuck_watch_tick — the WIRING, not the logic.

ISSUE #51. `jobs/stuck_watch.py` is well covered by tests/unit/test_stuck_watch.py:
the area gate, the error edge and `tunables` are all exercised as pure logic. The
function that WIRES that logic to the manager had no test at all, and it shipped a
`NameError` on 2026-08-09 that a user hit ten days later:

    adapter_cfg = get_adapter_config(vacuum_entity_id) or {}
    NameError: name 'get_adapter_config' is not defined.
               Did you mean: '_get_adapter_config'?

Line 62 of that module imports the function `as _get_adapter_config`. Eleven call
sites used the alias; this one used the bare name. The tick fires every 5 seconds,
so a single user's log filled with the same traceback until they reported it.

WHY NOTHING CAUGHT IT, and this is the part worth keeping. The crash is on the line
immediately AFTER `if not active_job: return {"fired": None, "reason": "no_job"}`.
Anything that called this without seeding an active job returned cleanly and
proved nothing — the bug lives past a guard that most setups never get through.
A NameError is the loudest possible signal that a line has ZERO coverage: it cannot
survive a single execution. So the test below is written to REACH the line, and
[SWT-1] would have failed on the day the bug shipped.

It is also a counter-example worth recording. The 2026-08-17 walk concluded that
"not one of the 22 families was a defect in unclaimed code — every one was a defect
in something that already had a rule, a guard, a table or a declaration." This one
is a defect in genuinely unclaimed code: no rule, no guard, no test, no anchor.
"""

from __future__ import annotations

import pytest

_VAC = "vacuum.alfred"
_MAP = "6"


def _seed_active_job(manager) -> dict:
    """A minimal STARTED job, seeded the way the live store holds one.

    Deliberately not a mock: the tick reads the real active-job accessor, and a
    mock would agree with the caller rather than the callee — which is how a
    NameError past a guard survives a green suite in the first place.
    """
    job = {
        "vacuum_entity_id": _VAC,
        "map_id": _MAP,
        "status": "started",
        "job_id": "stuck-watch-1",
        "started_at": "2026-01-01T00:00:00+00:00",
        "queue_room_ids": [1],
        "resolved_rooms": [{"room_id": 1, "slug": "room_1"}],
    }
    manager.data.setdefault("active_jobs", {}).setdefault(_VAC, {})[_MAP] = job
    return job


async def test_tick_runs_past_the_active_job_guard(manager):
    """[SWT-1] The tick executes its body when a job IS active.

    The assertion is deliberately weak on CONTENT and strict on EXECUTION: any
    NameError, AttributeError or TypeError past the guard fails here. That is the
    class of defect this file exists for, and a richer assertion on the returned
    dict would not have caught the one that shipped.
    """
    _seed_active_job(manager)
    result = manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    assert isinstance(result, dict)
    # `area` is produced ONLY by the body's final return, which is past the line
    # that raised. Asserting its PRESENCE is what makes this test unable to pass
    # vacuously; asserting its value would not have caught a NameError.
    assert "area" in result, (
        f"the tick returned {result!r} without reaching its body — this test "
        "proves nothing unless the body ran"
    )


async def test_the_no_job_guard_is_UNREACHABLE(manager):
    """[SWT-2] The tick's `if not active_job` guard is DEAD CODE, and this pins it.

    Written as the control for [SWT-1] — "prove the guard still works, so [SWT-1]
    cannot be satisfied by a tick that never guards at all" — and it failed, which
    is how the second defect surfaced.

    `get_active_job` NEVER returns falsy: it substitutes
    `_default_active_job_state(...)` for a missing entry and normalises the result.
    So `if not active_job: return {"fired": None, "reason": "no_job"}` can never
    fire, and no caller will ever see `reason: "no_job"` however it is invoked.

    BENIGN TODAY, and recorded rather than removed. With no job seeded the body runs
    and reports `excluded: True`, which is the right answer by a different route. But
    a guard that cannot fire reads as protection and is none —
    feedback_partial_guard_blind_spot — and the shape is A6-PRE-1's: a branch
    unreachable for every input the system can produce. Whether to delete the guard
    or make `get_active_job` able to say "absent" is a behaviour decision, not a
    test one.

    This test asserts the CURRENT truth, so it goes red the moment either is done —
    which is exactly when someone should look at it.
    """
    manager.data.pop("active_jobs", None)
    result = manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result.get("reason") != "no_job", (
        "the no_job guard fired — get_active_job can now return falsy, so the "
        "guard is live and this test's premise is out of date"
    )
    assert "area" in result, "the body should have run instead of the dead guard"


async def test_every_adapter_config_read_uses_the_module_alias(manager):
    """[SWT-3] No call site in core/manager.py uses the BARE name.

    The specific defect was one call site out of twelve. This asserts the whole
    file, because the next one will be a different line — and unlike [SWT-1] it
    costs nothing and needs no fixture state to reach.
    """
    import pathlib
    import re

    src = pathlib.Path(
        "custom_components/eufy_vacuum/core/manager.py"
    ).read_text(encoding="utf-8")
    bare = re.findall(r"(?<![\w.])get_adapter_config\s*\(", src)
    assert not bare, (
        f"{len(bare)} call site(s) in core/manager.py use the bare "
        "`get_adapter_config`; the module imports it as `_get_adapter_config` "
        "(line 62), so a bare use is a NameError at runtime"
    )

# --- C36 — the non-cleaning phase exemption, which was INERT until 2026-08-21 -------
#
# `_stuck_watch_excluded` read `(phases[idx] or {}).get("type")`, but a phase is stamped
# `phase_type` — planning/run_plan.py:887/961/968/986, handed to the active job verbatim
# by queue/queue_engine.py:512. A bare `type` key is stamped on a PHASE nowhere in the
# tree. So ptype was always "", never a member of NON_CLEANING_PHASE_TYPES, and the
# exemption could not fire for any input.
#
# THE KEY IS THE ASSERTION. These tests build the phase dict the way PRODUCTION builds
# it — `phase_type`. A test written with `type` would pass against the bug and prove
# nothing, which is exactly how this survived: the guard, its comment and its set were
# all correct; only the key was wrong, and nothing read the key.


def _seed_phase(manager, hass, *, phase_type: str) -> dict:
    """A started job sitting in one phase, with live state that reaches the phase check.

    Every earlier guard in `_stuck_watch_excluded` has to NOT fire or the phase branch
    is unreachable and the test proves nothing: watched status, observed lifecycle, no
    error edge, not paused, a cleaning vacuum state, not charging.
    """
    job = _seed_active_job(manager)
    job["has_observed_active_lifecycle"] = True
    job["phases"] = [{"phase_type": phase_type}]
    job["current_phase_index"] = 0
    hass.states.async_set(_VAC, "cleaning", {})
    return job


@pytest.mark.parametrize("phase_type", ["zone", "charge_wait", "wait"])
async def test_non_cleaning_phase_exempts_the_stall_watch(manager, hass, phase_type):
    """[SWT-4] C36. Every member of NON_CLEANING_PHASE_TYPES must exempt the watch.

    charge_wait allows up to 180 minutes with a flat counter BY DESIGN, and a zone is
    often smaller than the counter's ~1 m2 floor. Without the exemption a legitimate
    zone clean is reported to the user as a stall.
    """
    job = _seed_phase(manager, hass, phase_type=phase_type)
    excluded = manager._stuck_watch_excluded(
        vacuum_entity_id=_VAC, active_job=job, err_open=False
    )
    assert excluded is True, (
        f"a {phase_type!r} phase did not exempt the stall watch. The phase is stamped "
        "`phase_type` by run_plan; a guard reading any other key is inert and every "
        "small zone phase is flagged stalled."
    )


async def test_a_cleaning_phase_does_NOT_exempt_the_stall_watch(manager, hass):
    """[SWT-5] C36's other half — the exemption must still REFUSE.

    Without this, [SWT-4] passes against a guard hard-wired to True. The real defect
    class here is a mute that swallows the detector: 'a critique that only adds mutes
    is how you ship a detector that never fires', per the docstring on the function
    under test.
    """
    job = _seed_phase(manager, hass, phase_type="cleaning")
    excluded = manager._stuck_watch_excluded(
        vacuum_entity_id=_VAC, active_job=job, err_open=False
    )
    assert excluded is False, (
        "a cleaning phase exempted the stall watch — the exemption is no longer "
        "discriminating and the detector is muted for every phase"
    )


# --- SWT-6..9 — the ERROR trigger's wiring, from the 2026-11-07 coverage triage ----
#
# `jobs/stuck_watch.error_episode_is_open` is covered as pure logic in
# tests/unit/test_stuck_watch.py. What had no test is the manager's half: the latch
# that makes one error episode produce ONE notification instead of one every five
# seconds, and the rule that the error trigger OWNS a run so the area gate stays
# quiet. [SWT-1] reaches the body but asserts only that it ran.
#
# A note on the triage itself: it listed the tick's `if not active_job` early return
# as TESTABLE. It is not — [SWT-2] above already establishes that `get_active_job`
# never returns falsy, so that guard is unreachable. Same root cause as the
# `isinstance(active_job_state, dict)` guards in learning/history_store.py:
# jobs/active_job.py's `_normalize_active_job` coerces anything to a dict, so every
# "what if it is absent" branch downstream is dead. Recorded here because the two
# findings were classified independently and are one fact.


_STUCK_LATCH = {"current_code": "S1", "current_message": "Robot is stuck"}


def _install_tracker(manager, latch):
    """Put an error tracker in hass.data the way async_setup_entry does.

    `latch` is re-read on every tick, so the test mutates the holder rather than
    re-installing: that is what lets one episode be opened, closed and reopened.
    """
    from custom_components.eufy_vacuum.const import DATA_ERROR_TRACKER, DOMAIN

    holder = {"latch": latch}

    class _Tracker:
        def get_active_run_latch(self, _vacuum_entity_id):
            return holder["latch"]

    manager.hass.data.setdefault(DOMAIN, {})[DATA_ERROR_TRACKER] = _Tracker()
    return holder


def _capture_stalls(hass):
    from custom_components.eufy_vacuum.const import EVENT_STALL_DETECTED

    seen: list[dict] = []
    hass.bus.async_listen(EVENT_STALL_DETECTED, lambda e: seen.append(dict(e.data)))
    return seen


async def test_an_error_episode_fires_once_not_every_tick(manager, hass):
    """[SWT-6] the dedup latch, which is the whole reason this is not a notification storm.

    The tick runs every 5 seconds and the error stays open until the user goes and
    frees the robot — minutes, often longer. Without `_stuck_err_open` the user is
    notified on every tick for the whole episode, which is worse than not notifying
    at all because they stop reading them.
    """
    job = _seed_active_job(manager)
    job["has_observed_active_lifecycle"] = True
    hass.states.async_set(_VAC, "cleaning", {})
    _install_tracker(manager, dict(_STUCK_LATCH))
    seen = _capture_stalls(hass)

    first = manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    assert first["fired"] == "error", f"the open episode must fire once; got {first!r}"
    assert len(seen) == 1

    for _ in range(3):
        again = manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
        await hass.async_block_till_done()
        assert again["fired"] is None, (
            f"the SAME episode fired again: {again!r} — the user gets one of these "
            "every five seconds until they free the robot"
        )
    assert len(seen) == 1, f"one episode, one event; saw {len(seen)}"


async def test_a_recovered_error_rearms_the_latch(manager, hass):
    """[SWT-7] the latch must CLEAR, or a second real stall is silent.

    The other half of SWT-6 and the one that actually decides whether the feature
    works twice: if the latch only ever sets, the first episode of a run is the only
    one the user ever hears about.
    """
    job = _seed_active_job(manager)
    job["has_observed_active_lifecycle"] = True
    hass.states.async_set(_VAC, "cleaning", {})
    holder = _install_tracker(manager, dict(_STUCK_LATCH))
    seen = _capture_stalls(hass)

    assert manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)["fired"] == "error"
    await hass.async_block_till_done()

    # The user frees the robot; the tracker reports the episode recovered.
    holder["latch"] = dict(_STUCK_LATCH, recovered=True)
    closed = manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    assert closed["fired"] is None
    stored = manager.data["active_jobs"][_VAC][_MAP]
    assert stored.get("_stuck_err_open") is False, (
        "a recovered episode must clear the latch, or the next stall is swallowed"
    )

    # It gets stuck again, in the same run.
    holder["latch"] = dict(_STUCK_LATCH, current_code="S2")
    second = manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()
    assert second["fired"] == "error", "a NEW episode in the same run must fire again"
    assert len(seen) == 2


async def test_an_open_error_owns_the_run_and_mutes_the_area_gate(manager, hass):
    """[SWT-8] one physical stall must not produce two notifications.

    The function's own docstring states this as a rule rather than an accident of two
    timeouts: "The error trigger owns this run." A robot that reports an error has
    also stopped covering floor, so both triggers would otherwise notice the same
    event and the user would be told twice about one problem.
    """
    job = _seed_active_job(manager)
    job["has_observed_active_lifecycle"] = True
    hass.states.async_set(_VAC, "cleaning", {})
    _install_tracker(manager, dict(_STUCK_LATCH))

    excluded = manager._stuck_watch_excluded(
        vacuum_entity_id=_VAC, active_job=job, err_open=True
    )
    assert excluded is True, "an open error episode must exempt the area gate"

    # and the same job WITHOUT the error edge is not exempt — otherwise the
    # assertion above is satisfied by a mute that swallows the detector entirely.
    assert manager._stuck_watch_excluded(
        vacuum_entity_id=_VAC, active_job=job, err_open=False
    ) is False


async def test_the_stall_event_names_the_room_and_the_trigger(manager, hass):
    """[SWT-9] the payload is what the notification is written from.

    One event serves every trigger, so `trigger` is what lets a consumer say "the
    robot reported a problem" rather than "it stopped covering floor" — those need
    different words. The room name is what makes the message actionable; without it
    the user is told the robot is stuck somewhere.
    """
    job = _seed_active_job(manager)
    job["has_observed_active_lifecycle"] = True
    job["current_room_id"] = 1
    hass.states.async_set(_VAC, "cleaning", {})
    _install_tracker(manager, dict(_STUCK_LATCH))
    seen = _capture_stalls(hass)

    manager.apply_stuck_watch_tick(vacuum_entity_id=_VAC, map_id=_MAP)
    await hass.async_block_till_done()

    assert len(seen) == 1
    payload = seen[0]
    assert payload["vacuum_entity_id"] == _VAC
    assert payload["map_id"] == str(_MAP)
    assert payload["trigger"] == "error", "the consumer chooses its wording from this"
    assert payload["room_id"] == 1
    assert payload["room_name"], "a stall with no room name is not actionable"
    # the trigger-specific detail is merged in, not nested
    assert payload["error_code"] == "S1"
    assert payload["error_message"] == "Robot is stuck"
