"""Proof RP-045 (RF-36 part 4) — battery health is unreportable on every shipped device.

Both live vacuums read health_pct / cc_charge_speed_pct / cv_charge_speed_pct as None,
for two DIFFERENT reasons. Driving both matters, because a fix aimed at one leaves the
other reading nothing:

  1. ANCHOR OUTLIVES ITS COMPARISON SET (alfred). The baseline was anchored from a
     qualifying session on 2026-06-08 and is still there. That session has since
     rotated out of the recent-50 ring, so `qualifying` is empty while the reference
     it produced survives. _compute_regime_pct has a reference and nothing to compare
     it against, and every stat reads None. The packet calls this out as required
     regardless of which remedy is chosen: "a reference outliving its comparison set
     is a bug on any reading."

  2. THE WINDOW DESCRIBES A DISCHARGE PATTERN THESE ROBOTS DO NOT HAVE (ivy). A
     dock-dwelling vacuum charges 100->100, 99->100, 98->98. Nothing ever satisfies
     start <= HEALTH_QUALIFY_START_MAX (50) and end >= HEALTH_QUALIFY_END_MIN (90),
     so no baseline anchors, the stats stay None indefinitely, and NOTHING TELLS THE
     USER WHY. 50 sessions in, the sensor still reads nothing with no reason given.

Case 2's after-check is deliberately implementation-agnostic. RP-045 leaves the remedy
open between (a) widen/accumulate partial spans, (b) retain qualifying sessions apart
from the display ring, and (c) declare it unavailable with an explicit state. Whichever
is chosen, a device that STILL cannot qualify must say so rather than read None forever
-- so the proof asserts that an explicit reason exists, not that a particular fix was
picked. Pre-deciding an open packet question in a reproducer would certify the wrong
answer.

Live evidence, 2026-08-01 (packet's evidence_live):
  vacuum.alfred: baseline cc 2.6214 / cv 2.6262 anchored 2026-06-08, 50 sessions,
                 health_pct None, cc_charge_speed_pct None, cv_charge_speed_pct None.
  vacuum.ivy:    baseline empty, 50 sessions, all three None.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_battery_health.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.battery.manager import (   # noqa: E402
    HEALTH_QUALIFY_END_MIN,
    HEALTH_QUALIFY_START_MAX,
    BatteryHealthManager,
)


def _manager() -> BatteryHealthManager:
    """A manager with only what _update_health touches. No I/O, no hass."""
    mgr = BatteryHealthManager.__new__(BatteryHealthManager)
    mgr._hass = None
    mgr._config_dir = "/tmp"
    mgr._save_cb = lambda: None
    mgr._listeners = []
    mgr._pending_post_job = {}
    mgr._data = {"battery": {"vacuums": {}}}
    mgr._notify = lambda v: None
    mgr._schedule_save = lambda: None
    mgr._lookup_vacuum_for_record = lambda r: "vacuum.test"
    return mgr


def _session(start, end, *, cc=2.60, cv=2.62, ts="2026-06-08T04:00:00Z"):
    return {
        "start_battery": start, "end_battery": end,
        "delta_pct": end - start, "duration_min": max(end - start, 1) * 2.6,
        "cc_min_per_pct": cc, "cv_min_per_pct": cv, "end_ts": ts,
    }


def _stats_after_update(record) -> dict:
    _manager()._update_health(record)
    return record["stats"]


def case_anchor_outlives_its_comparison_set(proof: H.Proof) -> None:
    """alfred — the reference survived, the sessions that produced it did not."""
    record = {
        "stats": {},
        # anchored 2026-06-08 from a session that has since rotated out
        "baseline": {"cc_min_per_pct": 2.6214, "cv_min_per_pct": 2.6262,
                     "session_count": 1, "anchored_at": "2026-06-08T04:00:00Z"},
        # a full ring of ordinary top-ups: none of them qualify
        "session_history_recent": [_session(88, 100) for _ in range(50)],
    }
    stats = _stats_after_update(record)
    has_reference = record["baseline"]["cv_min_per_pct"] is not None

    proof.case(
        "baseline anchored 2026-06-08, its session rotated out of the recent-50 ring",
        before=has_reference and stats.get("health_pct") is None
        and stats.get("cc_charge_speed_pct") is None,
        before_msg="reference outlived its comparison set — the baseline is still "
                   "there but `qualifying` is empty, so every health stat reads None "
                   "while the anchor it is measured against sits right beside them",
        after=has_reference and stats.get("health_pct") is not None,
        after_msg="qualifying sessions are retained apart from the rolling display "
                  "ring, so the comparison set cannot rotate away from its own anchor",
        detail=f"baseline cv={record['baseline']['cv_min_per_pct']} · "
               f"qualifying sessions in ring=0 of 50 · health_pct="
               f"{stats.get('health_pct')!r} · cc={stats.get('cc_charge_speed_pct')!r} "
               f"· cv={stats.get('cv_charge_speed_pct')!r}",
    )


def case_dock_dweller_never_qualifies(proof: H.Proof) -> None:
    """ivy — 50 sessions, no baseline, no stats, and no stated reason."""
    record = {
        "stats": {},
        "baseline": {},
        # the real observed shape: 100->100, 99->100, 98->98 on repeat
        "session_history_recent": [
            _session(s, e) for s, e in [(100, 100), (99, 100), (98, 98)] * 17
        ],
    }
    stats = _stats_after_update(record)
    anchored = record["baseline"].get("cv_min_per_pct") is not None
    all_none = all(
        stats.get(k) is None
        for k in ("health_pct", "cc_charge_speed_pct", "cv_charge_speed_pct")
    )
    # Whatever remedy RP-045 picks, a device that still cannot qualify must SAY so.
    # Any explicit signal satisfies this — a reason string, an availability flag, a
    # count of what is still needed. Bare None is the thing being ruled out.
    explains_itself = any(
        stats.get(k) is not None
        for k in ("health_unavailable_reason", "health_state",
                  "health_qualifying_session_count", "health_requirements")
    )

    proof.case(
        f"a dock-dwelling vacuum: 51 sessions, none reaching "
        f"start<={HEALTH_QUALIFY_START_MAX} and end>={HEALTH_QUALIFY_END_MIN}",
        before=all_none and not anchored and not explains_itself,
        before_msg="the qualification window describes a discharge pattern this "
                   "robot does not have, so nothing ever anchors and all three "
                   "sensors ship reading None indefinitely — with no indication of "
                   "why or what would satisfy them",
        after=explains_itself or (anchored and not all_none),
        after_msg="either the device now qualifies (widened window / partial-span "
                  "accumulation) or it states explicitly that health is unavailable "
                  "and what would satisfy it — no silent permanent None",
        detail=f"baseline anchored={anchored} · health_pct={stats.get('health_pct')!r} "
               f"· cc={stats.get('cc_charge_speed_pct')!r} · "
               f"cv={stats.get('cv_charge_speed_pct')!r} · states a reason="
               f"{explains_itself}",
    )


def main() -> None:
    proof = H.Proof("RP-045", "battery health is unreportable on every shipped device")
    case_anchor_outlives_its_comparison_set(proof)
    case_dock_dweller_never_qualifies(proof)
    proof.finish()


H.run(main)
