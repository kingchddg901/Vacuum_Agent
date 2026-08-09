"""jobs/stuck_watch.py — the area gate and the error edge, as pure logic.

Both triggers exist because a robot gets stuck two ways, and each was observed on
hardware on 2026-08-09 by deliberately trapping a Roborock S6:

  CASE 1 — corner trap. Robot MOVING, retrying, freed itself after ~3 minutes. No
  error code ever fired and `vacuum.<id>` stayed "cleaning". `cleaning_area` went
  0.0 -> 0.6 in the first 15s then flat. Only the swept-area delta caught it.
  CASE 2 — box wedge. `bumper_stuck` on every error surface within seconds.

These tests are written against those two shapes, not against the implementation.

Coverage targets
----------------
[SW-1]  a flat window past its duration FIRES.
[SW-2]  real progress resets instead of firing (the anti-false-positive).
[SW-3]  a window still inside its duration holds — the 15 minutes is real.
[SW-4]  an exclusion resets, and LEAVING one rebases rather than resuming.
[SW-5]  a counter re-baseline (Eufy per-phase reset) is not read as a stall.
[SW-6]  dither cannot manufacture progress — high-water, not a delta sum.
[SW-7]  a phase change resets.
[SW-8]  an unreadable sensor holds and abstains past the tolerance.
[SW-9]  the error edge fires once per episode, not once per tick.
[SW-10] a code=None episode FIRES (the Eufy stuck path), and a silenced code does not.
[SW-11] tunables fall back to framework defaults and reject nonsense.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.jobs.stuck_watch import (
    DEFAULT_MIN_PROGRESS_M2,
    DEFAULT_WINDOW_MINUTES,
    error_episode_is_open,
    evaluate_area_window,
    new_window,
    tunables,
)

LIMITS = {"window_minutes": 15.0, "min_progress_m2": 2.0, "max_unreadable_fraction": 0.5}
T0 = "2026-08-09T01:30:00Z"
T1 = "2026-08-09T01:45:00Z"


def _win(**over):
    w = new_window(now_iso=T0, area_m2=0.6, phase_index=None)
    w.update(over)
    return w


def _step(window, *, area, elapsed, excluded=False, phase_index=None, now=T1):
    return evaluate_area_window(
        window=window, area_m2=area, elapsed_minutes=elapsed, phase_index=phase_index,
        excluded=excluded, now_iso=now, limits=LIMITS,
    )


# ---------------------------------------------------------------------------
# The case the feature exists for
# ---------------------------------------------------------------------------

def test_sw1_flat_window_past_its_duration_fires():
    """[SW-1] Hardware Case 1: area flat, robot still 'cleaning', no error.

    0.6 m² accrued in the first seconds and nothing since. Fifteen minutes later
    nothing else in the system has noticed — no error, not paused, not docked.
    """
    result = _step(_win(), area=0.6, elapsed=16.0)
    assert result["action"] == "fire"
    assert result["progress_m2"] == pytest.approx(0.0)


def test_sw2_real_progress_resets_instead_of_firing():
    """[SW-2] The anti-false-positive, and the one that matters most.

    A detector that fires on a working robot gets switched off, after which it
    catches nothing at all. Progress past the threshold restarts the window.
    """
    result = _step(_win(), area=0.6 + 2.5, elapsed=16.0)
    assert result["action"] == "reset"
    assert result["reason"] == "progress"


def test_sw3_a_window_inside_its_duration_holds():
    """[SW-3] The 15 minutes has to be real.

    Case 1's robot freed herself after ~3 minutes. A gate that fired early would
    have cried wolf on a robot that was going to be fine, which is [SW-2]'s failure
    wearing a different hat.
    """
    result = _step(_win(), area=0.6, elapsed=14.0)
    assert result["action"] == "hold"
    assert result["reason"] == "measuring"


# ---------------------------------------------------------------------------
# The rules that stop it crying wolf
# ---------------------------------------------------------------------------

def test_sw4_exclusion_resets_and_leaving_one_rebases():
    """[SW-4] Mute must REBASE, not suppress. The concrete failure if it does not:

    the robot returns to charge, sits 70 minutes, the mute lifts — and the area
    does not move for another few minutes while it drives back out. A suppress-only
    mute compares against a 70-minute-old flat baseline and fires on the first
    unmuted tick, on every mid-run recharge, on a perfectly healthy robot.
    """
    muted = _step(_win(), area=0.6, elapsed=16.0, excluded=True)
    assert muted["action"] == "reset"
    assert muted["window"]["excluded_last_tick"] is True

    # First tick after the mute lifts: must rebase, NOT evaluate the stale window.
    resumed = _step(muted["window"], area=0.6, elapsed=99.0, excluded=False)
    assert resumed["action"] == "reset"
    assert resumed["reason"] == "mute_exit_rebase"


def test_sw5_a_counter_rebase_is_not_a_stall():
    """[SW-5] Eufy resets cleaning_area per phase; a live run was seen falling
    21.5 -> 10.8 mid-run. A drop is neither progress nor evidence of a stall."""
    result = _step(_win(area_m2=None) | {"baseline_m2": 21.5, "high_water_m2": 21.5},
                   area=10.8, elapsed=16.0)
    assert result["action"] == "reset"
    assert result["reason"] == "counter_rebased"


def test_sw6_dither_cannot_manufacture_progress():
    """[SW-6] High-water mark, not a sum of positive increments.

    Summing deltas over a 15-minute window at a ~15s cadence is ~60 samples, so
    ±0.1 m² of noise on a MOTIONLESS robot sums to ~3 m² — more than the 2.0
    threshold. The gate would then never fire on the exact case it exists for.
    Here the reading jitters up and down and ends where it started.
    """
    w = _win()
    for reading in (0.6, 0.7, 0.6, 0.7, 0.6, 0.7, 0.6):
        out = _step(w, area=reading, elapsed=5.0)
        assert out["action"] == "hold", reading
        w = out["window"]
    # High water reached 0.7; progress is 0.1, nowhere near 2.0.
    final = _step(w, area=0.6, elapsed=16.0)
    assert final["action"] == "fire"
    assert final["progress_m2"] == pytest.approx(0.1, abs=1e-6)


def test_sw7_a_phase_change_resets():
    """[SW-7] A new phase is new floor; carrying the old window across would
    measure two unrelated stretches as one."""
    result = _step(_win(phase_index=0), area=0.6, elapsed=16.0, phase_index=1)
    assert result["action"] == "reset"
    assert result["reason"] == "phase_changed"


def test_sw8_unreadable_holds_then_abstains():
    """[SW-8] Absence of a reading is not absence of progress.

    A deliberate coverage hole: a robot that wedges AND drops Wi-Fi is missed. The
    trade is that an integration reload is common, and a detector that cries wolf
    on every dropout is uninstalled before it catches a real trap.
    """
    held = _step(_win(), area=None, elapsed=1.0)
    assert held["action"] == "hold"
    assert held["window"]["unreadable_ticks"] == 1

    # The ABSTAIN is a different path, and reaching it needs a READABLE tick: a None
    # reading short-circuits above, correctly — you cannot evaluate progress from a
    # reading you do not have. Abstain is for the window that has now elapsed, shows
    # no progress, and spent most of its life blind. Firing on that would report a
    # stall on the strength of a sensor that was mostly absent.
    mostly_blind = _win(unreadable_ticks=9, total_ticks=9)
    out = _step(mostly_blind, area=0.6, elapsed=16.0)
    assert out["action"] == "hold"
    assert out["reason"] == "abstain_unreadable"

    # …and a window that could SEE for most of its life still fires.
    mostly_sighted = _win(unreadable_ticks=1, total_ticks=9)
    assert _step(mostly_sighted, area=0.6, elapsed=16.0)["action"] == "fire"


# ---------------------------------------------------------------------------
# The error edge
# ---------------------------------------------------------------------------

def test_sw9_error_edge_is_an_episode_not_a_level():
    """[SW-9] Open episodes fire once. The tick runs every 5 seconds, so a
    level-triggered test would notify twelve times a minute until a human arrived."""
    latch = {"current_code": "bumper_stuck", "current_message": "Bumper stuck"}
    assert error_episode_is_open(latch, frozenset()) is True
    assert error_episode_is_open({**latch, "recovered": True}, frozenset()) is False
    assert error_episode_is_open(None, frozenset()) is False


def test_sw10_a_codeless_episode_fires_and_a_silenced_code_does_not():
    """[SW-10] `code is None` MUST fire — that is the Eufy stuck path.

    When the error grace expires with no code, the adapter records code=None with a
    generic message, and its own notes say that is exactly what a trapped Eufy does.
    A predicate written as `code in IMMOBILIZING` is totally blind to it — which is
    why the silence set is an inverse list, not a whitelist of known traps.
    """
    assert error_episode_is_open(
        {"current_code": None, "current_message": "Unknown error during run"}, frozenset()
    ) is True

    # A brand may declare codes not worth interrupting someone for.
    silenced = frozenset({"5110"})
    assert error_episode_is_open(
        {"current_code": "5110", "current_message": "WiFi error"}, silenced
    ) is False
    # …and silencing one must not silence the rest.
    assert error_episode_is_open(
        {"current_code": "robot_trapped", "current_message": "Robot trapped"}, silenced
    ) is True


def test_sw10b_an_empty_message_is_not_an_episode():
    """[SW-10b] The latch can exist with nothing to say. Firing on that would
    notify about a fault the user cannot be told anything about."""
    assert error_episode_is_open({"current_code": "x", "current_message": "  "}, frozenset()) is False


def test_sw11_tunables_fall_back_and_reject_nonsense():
    """[SW-11] Framework defaults, because NEITHER adapter declares this block.

    Roborock declares no anomaly block at all, so a value defaulted only on Eufy
    would be inherited by Roborock as another brand's number.
    """
    assert tunables(None)["window_minutes"] == DEFAULT_WINDOW_MINUTES
    assert tunables({})["min_progress_m2"] == DEFAULT_MIN_PROGRESS_M2
    assert tunables({"stuck_watch": {"window_minutes": 20}})["window_minutes"] == 20.0
    # A zero or negative window would fire on every tick forever.
    assert tunables({"stuck_watch": {"window_minutes": 0}})["window_minutes"] == DEFAULT_WINDOW_MINUTES
    assert tunables({"stuck_watch": {"window_minutes": "nonsense"}})["window_minutes"] == DEFAULT_WINDOW_MINUTES
