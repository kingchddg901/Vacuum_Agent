"""Stuck detection — the area gate, and the error edge.

TWO TRIGGERS, BECAUSE ONE ROBOT GETS STUCK TWO WAYS. Both observed on hardware
2026-08-09 by deliberately trapping a Roborock S6 twice:

  CASE 1 — corner trap. The robot was MOVING the whole time, retrying, and freed
  itself after ~3 minutes. No error code ever fired; `vacuum.<id>` stayed
  "cleaning". A pose-delta detector would have called it healthy, because it WAS
  moving. `cleaning_area` went 0.0 -> 0.6 in the first 15s and then flat. Only the
  swept-area delta caught it.

  CASE 2 — box wedge. Full error cascade within seconds: `bumper_stuck` on every
  error surface at once. The area was also flat, but the code said it first and
  said it precisely.

So: the ERROR EDGE is fast and exact but only fires when the robot knows it is
beaten; the AREA GATE is slow and catches what the robot never reports. Neither
subsumes the other, and a detector with only one of them has a blind side.

WHAT THIS MODULE DOES NOT DO, AND MUST NEVER DO. It does not command the robot.
Not `return_to_base`, not anything. Two reasons, both decided:

  * A stuck robot cannot drive out. For `bumper_stuck` the firmware will not even
    release until the bumper is PHYSICALLY actuated, so a homing command is theatre.
  * A run we did not dispatch is not ours to redirect. An app-started clean is
    somebody else's intent.

Every stuck state gets the same answer: tell the user, they go get it. The one
place the framework DOES command a robot home is the pause-timeout path, and that
is a different situation — a paused robot can move, and the user configured that
timeout themselves.

Pure and synchronous by construction: state in, decision out, no I/O and no awaits.
The caller reads the signals and owns the dict. Being synchronous is not a style
choice — the active-job dict is a shallow copy handed out and written back by whole
slot replacement, and the stranded reaper can finalize a job at any await point, so
a trigger that awaited between reading and writing its dedup state could resurrect
a finalized job.
"""

from __future__ import annotations

from typing import Any

#: How long the swept area must stay flat before the area gate fires.
#:
#: MUST STAY LONGER THAN ``STRANDED_REAP_GRACE_MINUTES`` (5.0, job_monitor.py). An
#: errored or docked run belongs to the reaper; this gate's domain is a run that
#: still LOOKS alive — `is_stranded_started() is False` — which is exactly hardware
#: Case 1. Shorten this below the grace, or lengthen the grace above it, and the two
#: fight over the same run. Nothing tests that interaction.
#:
#: 15 also matches the observed recovery: the corner-trap robot freed herself inside
#: ~3 minutes, so a 10-minute window would have cried wolf on a robot that was going
#: to be fine.
DEFAULT_WINDOW_MINUTES = 15.0

#: Progress that counts as "still cleaning", in m².
#:
#: NOT ``swept_area_min_m2`` (0.5) from room_attribution.tuning. Eufy quantises
#: cleaning_area to whole 1 m² device steps, so 0.5 is either zero quanta or one and
#: the test degenerates to "did the counter tick at all" on one brand while being a
#: real bar on the other — the same literal meaning two different things per brand.
#: 2.0 clears one Eufy quantum with margin for the ft²->m² round trip (a nominal 1.0
#: lands at 0.99964) and sits comfortably above Case 1's 0.6-over-3-minutes.
DEFAULT_MIN_PROGRESS_M2 = 2.0

#: Abstain if the area entity was unreadable for more than this fraction of the window.
#:
#: A DELIBERATE COVERAGE HOLE, stated out loud: a robot that wedges AND drops Wi-Fi is
#: missed by both triggers. The trade is asymmetric — an MQTT hiccup or an integration
#: reload is a common event, and a detector that cries wolf on every dropout gets
#: turned off before it ever catches a real trap.
DEFAULT_MAX_UNREADABLE_FRACTION = 0.5

#: Job statuses the area gate will watch. `paused` is absent on purpose: a paused run
#: belongs to the pause-timeout reaper, which owns it and does command the robot home.
WATCHED_STATUSES: frozenset[str] = frozenset({"started", "external"})


def tunables(adapter_cfg: dict[str, Any] | None) -> dict[str, float]:
    """Framework defaults, overridable per adapter via a ``stuck_watch`` block.

    NEITHER SHIPPED ADAPTER DECLARES ONE, and that is the point. Roborock declares no
    ``anomaly`` block at all, so anything given a default only on Eufy is inherited by
    Roborock as somebody else's number — the "Eufy is not the default" invariant.
    Framework defaults sidestep it: both brands get the same value until a brand has a
    measured reason to differ.
    """
    block = (adapter_cfg or {}).get("stuck_watch") or {}

    def _f(key: str, fallback: float) -> float:
        try:
            value = float(block.get(key, fallback))
        except (TypeError, ValueError):
            return fallback
        return value if value > 0 else fallback

    return {
        "window_minutes": _f("window_minutes", DEFAULT_WINDOW_MINUTES),
        "min_progress_m2": _f("min_progress_m2", DEFAULT_MIN_PROGRESS_M2),
        "max_unreadable_fraction": _f(
            "max_unreadable_fraction", DEFAULT_MAX_UNREADABLE_FRACTION
        ),
    }


def new_window(*, now_iso: str, area_m2: float | None, phase_index: int | None) -> dict[str, Any]:
    """A fresh measuring window, anchored at the current reading."""
    base = float(area_m2) if area_m2 is not None else 0.0
    return {
        "started_at": now_iso,
        "baseline_m2": base,
        "high_water_m2": base,
        "phase_index": phase_index,
        "excluded_last_tick": False,
        "unreadable_ticks": 0,
        "total_ticks": 0,
    }


def evaluate_area_window(
    *,
    window: dict[str, Any] | None,
    area_m2: float | None,
    elapsed_minutes: float,
    phase_index: int | None,
    excluded: bool,
    now_iso: str,
    limits: dict[str, float],
) -> dict[str, Any]:
    """Advance the area window by one tick. Pure.

    Returns ``{"action": "reset"|"hold"|"fire", "window": <dict>, "reason": str,
    "progress_m2": float}``. The caller persists the window and acts on ``action``.

    ORDER MATTERS and each step is load-bearing:

    1. EXCLUDED -> reset. The gate measures whether a robot that is supposed to be
       cleaning is making progress; while it is legitimately not cleaning, there is
       nothing to measure.
    2. LEAVING an exclusion -> reset, NOT resume. This is the single most important
       rule here. Suppress-only would fire on the first unmuted tick after every
       mid-run recharge: a robot returns to charge, sits 70 minutes, the mute lifts,
       and the baseline is 70 minutes stale and flat while the robot drives back out.
       Mute must REBASE.
    3. PHASE CHANGE -> reset. A new phase is a new piece of floor.
    4. UNREADABLE -> count it, hold. Absence of a reading is not absence of progress.
    5. A DROP -> reset. The counter re-baselined (Eufy resets per phase; a live run
       was observed falling 21.5 -> 10.8 mid-run). Never read a drop as progress, and
       never as a stall.
    6. PROGRESS -> reset. The window restarts from the new high-water mark.

    HIGH-WATER, NOT A DELTA SUM. Summing positive increments over the window would
    manufacture progress out of dither: at a ~15s cadence a 15-minute window is ~60
    samples, and ±0.1 m² of noise on a motionless robot sums to ~3 m² of phantom
    movement — more than the threshold it would have to clear. A high-water mark is
    immune to dither in the direction that matters and monotone-safe against re-baseline.
    """
    limits = limits or {}
    window_minutes = float(limits.get("window_minutes", DEFAULT_WINDOW_MINUTES))
    min_progress = float(limits.get("min_progress_m2", DEFAULT_MIN_PROGRESS_M2))
    max_unreadable = float(
        limits.get("max_unreadable_fraction", DEFAULT_MAX_UNREADABLE_FRACTION)
    )

    def _reset(reason: str) -> dict[str, Any]:
        fresh = new_window(now_iso=now_iso, area_m2=area_m2, phase_index=phase_index)
        if area_m2 is None and isinstance(window, dict):
            # Nothing readable to anchor on — keep the old high water so a transient
            # dropout during a reset does not hand back a zero baseline that the next
            # real reading would clear instantly.
            prior = float(window.get("high_water_m2", 0.0) or 0.0)
            fresh["baseline_m2"] = prior
            fresh["high_water_m2"] = prior
        fresh["excluded_last_tick"] = excluded
        return {"action": "reset", "window": fresh, "reason": reason, "progress_m2": 0.0}

    if excluded:
        return _reset("excluded")

    if not isinstance(window, dict):
        return _reset("no_window")

    # Step 2 — the mute-exit rebase.
    if window.get("excluded_last_tick"):
        return _reset("mute_exit_rebase")

    if window.get("phase_index") != phase_index:
        return _reset("phase_changed")

    updated = dict(window)
    updated["total_ticks"] = int(updated.get("total_ticks", 0)) + 1

    if area_m2 is None:
        updated["unreadable_ticks"] = int(updated.get("unreadable_ticks", 0)) + 1
        return {"action": "hold", "window": updated, "reason": "unreadable", "progress_m2": 0.0}

    baseline = float(updated.get("baseline_m2", 0.0) or 0.0)
    high_water = float(updated.get("high_water_m2", baseline) or baseline)

    # Step 5 — a counter re-baseline is not a stall.
    if area_m2 < baseline - 1e-6:
        return _reset("counter_rebased")

    if area_m2 > high_water:
        high_water = float(area_m2)
        updated["high_water_m2"] = high_water

    progress = high_water - baseline

    if progress >= min_progress:
        return _reset("progress")

    total = max(int(updated.get("total_ticks", 0)), 1)
    unreadable_fraction = int(updated.get("unreadable_ticks", 0)) / total
    if elapsed_minutes >= window_minutes:
        if unreadable_fraction > max_unreadable:
            return {
                "action": "hold",
                "window": updated,
                "reason": "abstain_unreadable",
                "progress_m2": progress,
            }
        return {"action": "fire", "window": updated, "reason": "no_progress", "progress_m2": progress}

    return {"action": "hold", "window": updated, "reason": "measuring", "progress_m2": progress}


def error_episode_is_open(latch: dict[str, Any] | None, silence_codes: frozenset[str]) -> bool:
    """Is there a live, un-recovered error episode the user has to go and fix?

    NOT A WHITELIST OF STUCK CODES. Every stuck state is treated the same, and a
    whitelist is a list of the traps that have already happened. The silence set is
    the inverse: codes a brand declares as NOT worth interrupting someone for.

    ``code is None`` MUST FIRE. When the error grace expires with no code, the Eufy
    adapter records ``code=None`` with a generic message — and its own notes say that
    is exactly the path a stuck or trapped Eufy takes, both channels flipping while
    the message stays empty. A predicate written as ``code in IMMOBILIZING`` is
    totally blind to the fault class this feature exists for.

    The silence set is deliberately NOT ``evidence_invalidating_error_codes``. Same
    idea, opposite content: Roborock declares 6 codes meaning demonstrably immobile,
    while Eufy's is a DERIVED set of ~142 that includes wifi errors and a full
    dustbin. Aliasing them would silence the traps on one brand and shout about
    housekeeping on the other.
    """
    if not isinstance(latch, dict):
        return False
    if latch.get("recovered") is True:
        return False
    if not str(latch.get("current_message") or "").strip():
        return False
    code = latch.get("current_code")
    if code is None:
        return True
    return str(code).strip().lower() not in silence_codes
