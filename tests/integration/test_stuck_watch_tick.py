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

