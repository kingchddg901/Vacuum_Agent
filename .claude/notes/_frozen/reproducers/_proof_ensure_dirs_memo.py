"""Proof RP-037 (RF-29) -- ensure_dirs does a full mkdir pass on every call.

ONE case, out of 9 finding_ids -- the cheapest, most self-contained example
in the packet's own reproducer_script ("32 mkdir calls per snapshot" / "0
mkdir on warm path"). The other eight (ROBORO-2 executor offload, GEO-2
bbox-reject-before-normalize, ONB-5 once-per-cycle summary, SNAP-2 snapshot
purity + event hoist, DRAFT-5 save debounce, TRK-7 executor-dispatch
removal) are NOT driven here -- each independent, left for follow-up. This
packet's title notes blocked_by RP-013c (a hardware-gated capture); that
gate is about REPAIR sequencing for the SNAP-2 clause specifically, not
about whether ensure_dirs' own syscall behavior can be verified against
current master -- it can, directly, with no hardware involved.

LearningHistoryStore.ensure_dirs (learning/history_store.py:152-159) does
FOUR unconditional Path.mkdir(parents=True, exist_ok=True) calls every
single time it runs, with no per-process memoization of which vacuum's
directories have already been created. exist_ok=True makes each call safe
to repeat, but it is NOT free -- every call is a real mkdir(2) syscall
(HA core's PROTECTED_LOOP guard requires this run in the executor
specifically because it hits the filesystem). A function called once per
warm-path operation (job stats reads/writes, snapshot composition, etc.)
repeats this full 4-syscall pass every time instead of confirming
once-per-process-per-vacuum and skipping thereafter.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_ensure_dirs_memo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore   # noqa: E402

VAC = H.VAC


def main() -> int:
    proof = H.Proof("RP-037", "ensure_dirs repeats a full mkdir pass on every call, no memoization")

    with tempfile.TemporaryDirectory() as tmp:
        store = LearningHistoryStore(H.make_hass(tmp))

        call_count = {"n": 0}
        _orig_mkdir = Path.mkdir

        def _counting_mkdir(self, *a, **kw):
            call_count["n"] += 1
            return _orig_mkdir(self, *a, **kw)

        Path.mkdir = _counting_mkdir
        try:
            store.ensure_dirs(vacuum_entity_id=VAC)
            first_call_count = call_count["n"]
            store.ensure_dirs(vacuum_entity_id=VAC)  # SAME vacuum, directories already exist
            second_call_total = call_count["n"]
        finally:
            Path.mkdir = _orig_mkdir

    calls_on_warm_repeat = second_call_total - first_call_count

    proof.case(
        "ensure_dirs called twice in a row for the SAME already-warm vacuum",
        before=(calls_on_warm_repeat == 4),
        before_msg="the second call repeats the SAME 4 mkdir syscalls as "
                   "the first, even though every directory already exists "
                   "and nothing changed since the first call -- no "
                   "memoization of 'already ensured this process'",
        after=(calls_on_warm_repeat == 0),
        after_msg="a per-path-set memo (once per process per vacuum) skips "
                  "the second call's mkdir pass entirely -- the warm path "
                  "does zero filesystem syscalls",
        detail=f"first call mkdir syscalls={first_call_count} · "
               f"second call (warm) mkdir syscalls={calls_on_warm_repeat}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
