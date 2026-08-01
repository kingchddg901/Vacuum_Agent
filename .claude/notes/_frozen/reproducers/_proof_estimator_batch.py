"""Proof RP-036 (RF-21) — estimator correctness batch.

STRUCTURE-ONLY per the packet's own rule (no re-tuning of empirical
constants). Two cases (of twelve finding_ids -- EST-3 through EST-6 and the
ACC-2..7 reanchor/rebuild-parity group are NOT driven here; time-boxed,
left for a follow-up pass).

  EST-1 -- _breakpoint_for_score (learning/estimator.py:165-170) checks
    each of the three breakpoints' [min_score, max_score] IN ORDER
    (high 0.80-1.00, medium 0.50-0.79, low 0.00-0.49) and falls through to
    `_BREAKPOINTS[-1]` ("low") when nothing matches. A score of 0.795 is
    IN NEITHER interval (> medium's 0.79 max, < high's 0.80 min) -- the
    dead band -- so it silently lands on LOW, the bucket furthest from its
    actual value, rather than the nearest one (MEDIUM).
  EST-2 -- build_job_stats_payload (learning/stats_rebuilder.py:257-339)
    appends `_safe_float(battery.get("used"), 0.0)` to battery_used_values
    for EVERY job unconditionally (line 293/302), including a job whose
    `battery` block is entirely absent (an external/app-started run, which
    never records one). The averaging at line 339 (`sum(...) / count`)
    divides by the TOTAL job count, so battery-absent jobs are counted as
    "0% used" and drag the mean down -- absent is silently treated as 0,
    not excluded.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_estimator_batch.py
"""

from __future__ import annotations

import sys
import tempfile

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.learning.estimator import _breakpoint_for_score   # noqa: E402
from custom_components.eufy_vacuum.learning.stats_rebuilder import LearningStatsRebuilder   # noqa: E402

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-036", "estimator correctness batch (structure-only)")

    # -------------------------------------------------------------------
    # Case 1 (EST-1): the 0.79-0.80 dead band falls through to LOW.
    # -------------------------------------------------------------------
    bp = _breakpoint_for_score(0.795)

    proof.case(
        "a room confidence score of 0.795 (between medium's 0.79 max and high's 0.80 min)",
        before=bp["key"] == "low",
        before_msg="0.795 matches neither breakpoint's inclusive range and "
                   "falls through to _BREAKPOINTS[-1] ('low') -- a room "
                   "whose confidence is one thousandth short of HIGH "
                   "renders as the WORST possible tier",
        after=bp["key"] == "medium",
        after_msg="the dead band is closed (MEDIUM max == HIGH min, "
                  "half-open) -- the fall-through returns the NEAREST "
                  "bucket, not a hardcoded LOW",
        detail=f"_breakpoint_for_score(0.795)={bp}",
    )

    # -------------------------------------------------------------------
    # Case 2 (EST-2): a battery-absent (external) job dilutes the average.
    # -------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        rebuilder = LearningStatsRebuilder(H.make_hass(tmp))
        jobs = [
            {"job": {"room_count": 1, "duration_minutes": 10.0,
                      "started_at": "2026-01-01T09:00:00+00:00",
                      "ended_at": "2026-01-01T09:10:00+00:00"},
             "battery": {"used": 20}},
            # an external/app-started run: no battery block was ever recorded.
            {"job": {"room_count": 1, "duration_minutes": 12.0,
                      "started_at": "2026-01-01T10:00:00+00:00",
                      "ended_at": "2026-01-01T10:12:00+00:00"}},
        ]
        payload = rebuilder.build_job_stats_payload(vacuum_entity_id=VAC, jobs=jobs)
        avg_battery = payload["job_stats"]["avg_battery_used"]

    proof.case(
        "one job reports battery.used=20, the other never recorded a battery block",
        before=avg_battery == 10.0,
        before_msg="the battery-absent job is silently treated as "
                   "battery_used=0 and divides into the average with the "
                   "real sample -- (20+0)/2=10.0 understates every "
                   "vacuum's actual battery draw by roughly half whenever "
                   "external runs are common",
        after=avg_battery == 20.0,
        after_msg="a battery_sample_count tracks only jobs that actually "
                  "recorded a battery block (mirroring the existing area "
                  "sample-count pattern) -- absent != 0, so the average "
                  "reflects only real samples",
        detail=f"avg_battery_used={avg_battery} (job 1: 20, job 2: absent)",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
