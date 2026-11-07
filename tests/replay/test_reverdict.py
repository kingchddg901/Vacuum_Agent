"""[RPL-2..RPL-5] The re-judge harness must DERIVE its verdicts, never restate them.

`reverdict.py` exists to say what the *shipped* code concludes about runs that are
already on disk, and its own docstring states the rule that makes its output worth
believing: "IMPORT THE REAL FUNCTIONS, never restate their logic. A
re-implementation agrees with whatever the author believed while writing it, which
is the one thing a validation must not do."

It broke that rule in exactly one place. The attribution-shift verdict was written
out as `if run >= 2` -- a hand copy of `external_ingest._SHIFT_BLOCK_MIN_RUN` --
while importing `monotone_shift_run` for the number beside it. Half the rule
imported, half retyped.

WHY THAT IS WORTH A TEST AND NOT JUST A FIX. A copy that agrees today is invisible:
every number the harness prints is correct, and stays correct right up until the
shipped threshold moves. Then the report says "records the NEW rule blocks: N" with
N computed by the OLD rule, over real device telemetry, in the one artifact whose
entire purpose is to be trusted about what the current build does -- and the
operator reading it has no way to tell. Nothing else in the tree can see it either:
the `RN` replica register's scanner reads `SOURCE_ROOTS` (`custom_components`,
`scripts`, `src`, `harness`), so a shipped constant copied into `tests/` has no
anchorable second site and is invisible to `test_replica_ratchet.py`; coverage sees
a line that runs.

SO THE GATE HAS TO MOVE THE THRESHOLD. Asserting "a run of 2 blocks" would be a
third copy of the same number, green against the very defect it was written for.
[RPL-3] patches the shipped constant and requires the report to follow it.

THE SHIPPED FUNCTIONS ARE THE ORACLE HERE, fixtures included: [RPL-2] asserts the
four row chains really are runs of 0/1/2/3 using `monotone_shift_run` itself, so a
mis-built chain fails as a stated precondition instead of letting the threshold
assertions pass for the wrong reason.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.learning import external_ingest
from custom_components.eufy_vacuum.learning.external_ingest import monotone_shift_run
from tests.replay.reverdict import check_attribution_shift

#: The queue order these chains walk -- real ids from alfred's map 12, so the rows
#: look like the corpus the harness actually reads.
_QUEUE = [5, 8, 9, 7]


def _row(room_id: int, pose_room: int | None) -> dict:
    """One `room_timings` row in the shape the pose reconcile writes.

    `reconcile_dispatched_identity` sets `attribution_disagreement` to
    `{"positional": <positional id>, "pose": <window id>}` on the FLAG branch and
    leaves `room_id` alone -- a shifted row keeps its positional id, which is
    exactly why one row at a time reads as ordinary border ambiguity.
    """
    row: dict = {"room_id": room_id}
    if pose_room is not None:
        row["attribution_disagreement"] = {"positional": room_id, "pose": pose_room}
    return row


def _record(name: str, poses: list[int | None], *, learned: bool = True) -> tuple:
    """A `(vacuum, filename, job record)` triple in the envelope `load_records` yields.

    The envelope is `build_completed_job_payload`'s: rows under `job.room_timings`,
    the verdict frozen at finalize time under `outcome.used_for_learning`.
    """
    rows = [_row(rid, pose) for rid, pose in zip(_QUEUE, poses)]
    return (
        "vacuum.alfred",
        name,
        {"job": {"room_timings": rows}, "outcome": {"used_for_learning": learned}},
    )


# Four records spanning the threshold. Each pose names the NEXT row's room, so the
# run length is the count of leading shifted rows; the final row can never
# contribute, having no successor to point at.
_RECORDS = [
    _record("job_clean.json", [None, None, None, None]),
    _record("job_ambiguous.json", [8, None, None, None]),
    _record("job_slide2.json", [8, 9, None, None]),
    _record("job_slide3.json", [8, 9, 7, None], learned=False),
]


def _names(hits) -> list[str]:
    return [name for _vac, name, *_rest in hits]


def test_the_fixture_chains_span_the_threshold():
    """[RPL-2] Precondition: the four chains are runs of 0/1/2/3.

    Counted by the shipped function, not by eye. Without this the threshold
    assertions below could agree with a wrong fixture and prove nothing -- a run
    length is a small integer, and every plausible mistake lands on another one.
    """
    runs = [monotone_shift_run(rec["job"]["room_timings"]) for _v, _n, rec in _RECORDS]
    assert runs == [0, 1, 2, 3]


def test_the_report_follows_the_shipped_threshold(monkeypatch):
    """[RPL-3] THE BITE -- move `_SHIFT_BLOCK_MIN_RUN`, and the report must move too.

    `attribution_shift_blocks_learning` resolves the constant as a module global on
    every call, so patching it here changes what the SHIPPED predicate decides. A
    harness that derives its verdict follows; a harness carrying its own copy of
    the number stays put. The old `if run >= 2` passes the first assertion below
    and fails both others, which is the whole reason this test exists rather than
    one asserting the current threshold's value.
    """
    assert _names(check_attribution_shift(_RECORDS)) == [
        "job_slide2.json",
        "job_slide3.json",
    ], "at the shipped threshold, the runs of 2 and 3 are the blocked ones"

    monkeypatch.setattr(external_ingest, "_SHIFT_BLOCK_MIN_RUN", 3)
    assert _names(check_attribution_shift(_RECORDS)) == ["job_slide3.json"], (
        "a STRICTER shipped threshold must drop the run-of-2 record from the report"
    )

    monkeypatch.setattr(external_ingest, "_SHIFT_BLOCK_MIN_RUN", 1)
    assert _names(check_attribution_shift(_RECORDS)) == [
        "job_ambiguous.json",
        "job_slide2.json",
        "job_slide3.json",
    ], "a LOOSER shipped threshold must pull the single-disagreement record in"


def test_each_row_carries_the_run_length_and_the_frozen_verdict():
    """[RPL-4] The printed row is the operator's whole reading, so pin its shape.

    `run` and `rooms` are adjacent small integers and a swap would be silent -- both
    look plausible either way round, and the report's headline claim ("shift_run=2/4
    rooms") is built from their order. `used_for_learning` is READ from the record
    rather than recomputed, because the report's one job is to show what a fix
    CHANGES: recomputing it would print the new verdict on both sides of the
    comparison and quietly answer a different question.
    """
    assert check_attribution_shift(_RECORDS) == [
        ("vacuum.alfred", "job_slide2.json", 2, 4, True),
        ("vacuum.alfred", "job_slide3.json", 3, 4, False),
    ]


def test_an_unreadable_record_does_not_abort_the_corpus():
    """[RPL-5] A record this check cannot read is skipped, not fatal.

    `load_records` returns every JSON file under `jobs/`, phase children and older
    schemas included, so shapes without a usable `job` block do reach here. A pass
    over 68 records that raises on one of them reports nothing about the other 67 --
    and the harness is run by hand against a live learning dir, where re-running it
    is the only feedback there is.

    THE GUARD THIS PROVES IS THE `or {}`, and only that one. It is
    expression-level -- no line, no branch of its own -- so coverage cannot show it
    exercised and ablation is the only evidence available; removing it reddens this
    test on the first record. The `or []` beside it is SUBSUMED and cannot be
    bitten here: a `None` room_timings reaches `monotone_shift_run`, which
    normalises with its own `or []` and returns 0, so the record never becomes a
    hit and `len(timings)` is never reached. Measured, not assumed -- removing it
    leaves all four tests green. It stays as the local statement of the contract,
    not because anything here depends on it.
    """
    assert check_attribution_shift([
        ("vacuum.alfred", "job_empty.json", {}),
        ("vacuum.alfred", "job_null_block.json", {"job": None}),
        ("vacuum.alfred", "job_null_timings.json", {"job": {"room_timings": None}}),
    ]) == []
