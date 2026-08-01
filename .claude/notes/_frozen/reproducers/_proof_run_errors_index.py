"""Proof CARD-3 (carried CF-7) — run_errors never reach the card's history index.

ONE case. NOTE ON SCOPE — the packet's own file list (src/renderers/, src/state/,
i18n) implies the backend already carries this data all the way to what the card
consumes ("the backend carries app-started-run error evidence end to end;
nothing displays it" / "No new polling — the data is already in the payloads").
That is only PARTLY true: completed_job["outcome"]["had_errors"/"error_count"/
"errors"] IS written durably by job_finalizer.py (confirmed: lines 860-862,
"Verbatim latch"). But the card never reads completed_job directly — it reads
the CARD-FRIENDLY jobs_index built by LearningStatsRebuilder.build_jobs_index_
payload (learning/stats_rebuilder.py:797-915), which is what get_learning_
history_snapshot serves to the frontend. That function already hand-picks
specific outcome.* fields onto each index entry — outcome.get("cancel_
detection"), outcome.get("used_for_learning"), outcome.get("sanity_passed")
(lines 906-907, 912) — but never outcome.get("had_errors") / "error_count" /
"errors". So no frontend code can render this data today no matter what the
renderer does: the field is dropped one layer before the card ever sees a
payload. A faithful CARD-3 needs a one-line addition to stats_rebuilder.py's
job_entries.append(...) dict IN ADDITION TO the frontend files the packet
lists -- flagging this rather than silently scoping the proof around it, per
this session's "licensed to say the packet is wrong" standing instruction.

Confirmed independently (grep, not inference): `had_errors|error_count` has
zero matches anywhere under src/ -- the frontend has no code path that even
COULD consume this field yet, consistent with the backend gap above rather
than a frontend oversight alone.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_run_errors_index.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.learning.stats_rebuilder import LearningStatsRebuilder   # noqa: E402

VAC = H.VAC


def main() -> int:
    proof = H.Proof("CARD-3", "run_errors never reach the card's history index")

    completed_job = {
        "record_type": "completed_job",
        "job_id": "job-with-errors-1",
        "job": {
            "started_at": "2026-01-01T09:00:00+00:00",
            "ended_at": "2026-01-01T09:20:00+00:00",
            "room_count": 1,
            "duration_minutes": 20.0,
        },
        "battery": {"used": 15},
        "water": {},
        "job_profile": {"rooms": []},
        "outcome": {
            "status": "completed",
            "used_for_learning": True,
            "sanity_passed": True,
            "cancel_detection": {"cancel_likely": False},
            # verbatim latch shape per core/error_tracker.py:761-772 + 781-796
            "had_errors": True,
            "error_count": 2,
            "errors": {
                "error_count": 2,
                "current_message": "",
                "recovered": True,
                "errors": [
                    {"message": "Wheel stuck", "code": "E001", "captured_at": "2026-01-01T09:05:00+00:00", "recovered_at": "2026-01-01T09:05:30+00:00"},
                    {"message": "Dustbin full", "code": "E014", "captured_at": "2026-01-01T09:12:00+00:00", "recovered_at": "2026-01-01T09:12:10+00:00"},
                ],
            },
        },
    }

    rebuilder = LearningStatsRebuilder(H.make_hass())
    index_payload = rebuilder.build_jobs_index_payload(vacuum_entity_id=VAC, jobs=[completed_job])
    entry = (index_payload.get("jobs") or [{}])[0]

    proof.case(
        "a completed job whose outcome carries had_errors=True, error_count=2, "
        "and two captured error entries",
        before=("had_errors" not in entry and "error_count" not in entry and "errors" not in entry),
        before_msg="build_jobs_index_payload hand-picks specific outcome.* "
                   "fields (cancel_detection, used_for_learning, sanity_passed) "
                   "onto the card-friendly index entry but never had_errors/ "
                   "error_count/errors -- the same job that recorded two real "
                   "device faults produces a history-index row indistinguishable "
                   "from a clean run",
        after=(entry.get("had_errors") is True and entry.get("error_count") == 2),
        after_msg="the index entry carries had_errors/error_count (and, for "
                  "the detail view, the errors[] list) through from outcome, "
                  "so the card has something to render at all",
        detail=f"index entry keys={sorted(entry.keys())} · "
               f"had_errors={entry.get('had_errors')!r} · "
               f"error_count={entry.get('error_count')!r}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
