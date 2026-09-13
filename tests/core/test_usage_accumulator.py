# -*- coding: utf-8 -*-
"""[UAC] The reset-detecting usage counter.

Every case here is a rule from Chris's spec or a failure it was written to prevent. The ones
that matter most are the two halves of the against-expectation branch: each is individually
plausible and each alone breaks the counter in a different, silent way.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.usage_accumulator import (
    DOWN,
    MAX_SINGLE_DELTA_HOURS,
    UP,
    direction_for,
    observe,
)


def _run(readings, *, direction=DOWN, baseline=None, total=0.0, cap=MAX_SINGLE_DELTA_HOURS):
    """Fold a sequence, returning the final state plus what each step booked."""
    counted = []
    rejected = []
    for r in readings:
        out = observe(r, baseline=baseline, total=total, direction=direction,
                      max_delta_hours=cap)
        baseline, total = out["baseline"], out["total"]
        counted.append(out["counted"])
        rejected.append(out["rejected"])
    return {"baseline": baseline, "total": total, "counted": counted, "rejected": rejected}


def test_a_countdown_books_only_the_decrease():
    """[UAC-1] the ordinary case: 300 -> 299 is one hour."""
    out = _run([300, 299, 297])
    assert out["total"] == 3.0
    assert out["counted"] == [0.0, 1.0, 2.0]
    assert out["baseline"] == 297


def test_a_gap_books_the_whole_drop_in_one_reading():
    """[UAC-2] HA was down for a week and the machine ran — nothing is lost.

    The delta is against the LAST STORED value, not a live stream, so an unobserved week
    arrives as one large legitimate reading. This is the case the cap must not eat.
    """
    out = _run([300, 130])
    assert out["total"] == 170.0
    assert out["rejected"] == [None, None], "a real catch-up must not be mistaken for a glitch"


def test_a_reset_counts_nothing_and_moves_the_baseline():
    """[UAC-3] THE RULE THAT IS EASY TO GET HALF-RIGHT.

    The part is replaced at 10 h left and the device returns to 300. That increase is not
    runtime, so it books nothing — and the baseline MUST move to 300 or the counter dies.
    """
    out = _run([300, 10, 300, 299])
    assert out["counted"] == [0.0, 290.0, 0.0, 1.0]
    assert out["total"] == 291.0
    assert out["baseline"] == 299


def test_skipping_the_rebaseline_would_freeze_the_counter_forever():
    """[UAC-4] the failure [UAC-3]'s second half prevents, stated as its own case.

    "Ignore increases" sounds complete and is not. Without the baseline move, `baseline` stays
    at 10 after the reset, every later reading (299, 298, 297 …) is another increase, and the
    accumulator never books another hour for the life of the install.

    THE ABLATION: an `observe` that returned `{"baseline": baseline}` on the against-expectation
    branch makes this test read total == 290.0 — the counter stopped at the reset.
    """
    out = _run([300, 10, 300, 299, 298, 297])
    assert out["total"] == 293.0, (
        "the counter stopped accumulating after the reset — the against-expectation branch is "
        "not moving the baseline"
    )


def test_counting_the_increase_would_book_the_reset_as_runtime():
    """[UAC-5] the other half of the same branch, from the other side.

    If the 10 -> 300 move were counted, the reset itself books 290 hours of use that never
    happened, and the freshly-replaced part immediately reads overdue.
    """
    out = _run([300, 10, 300])
    assert out["total"] == 290.0, "only the real decrease may be booked"
    assert out["counted"][2] == 0.0


@pytest.mark.parametrize("junk", ["unavailable", "unknown", None, "", "n/a", float("nan")])
def test_a_non_reading_touches_nothing(junk):
    """[UAC-6] THE FAILURE MOST LIKELY TO HAPPEN FIRST — it fires on a normal HA restart.

    A countdown goes unavailable on every restart and whenever the device drops off. Coerced to
    0 it books the whole countdown as runtime; treated as "no value" that still writes a
    baseline, it destroys the reference we count from. It must change nothing at all.
    """
    out = observe(junk, baseline=250.0, total=42.0, direction=DOWN)
    assert out == {"baseline": 250.0, "total": 42.0, "counted": 0.0, "rejected": None}


def test_unavailable_mid_sequence_does_not_break_the_span():
    """[UAC-6b] and the span across it is still counted correctly afterwards."""
    out = _run([300, "unavailable", 290, "unknown", 285])
    assert out["total"] == 15.0
    assert out["baseline"] == 285


def test_the_first_reading_establishes_the_baseline_only():
    """[UAC-7] a fresh install must not book the hours already on the part."""
    out = observe(130.0, baseline=None, total=0.0, direction=DOWN)
    assert out == {"baseline": 130.0, "total": 0.0, "counted": 0.0, "rejected": None}


def test_an_impossible_delta_is_rejected_and_reported_not_absorbed():
    """[UAC-8] a sensor glitching to 0 and back would book a whole service life.

    Absorbed, it leaves a permanent overcount with nothing to show it happened. Rejected, the
    caller gets the number and can say so — and the baseline still moves, so the next reading
    recovers rather than repeating the rejection.
    """
    out = observe(0.0, baseline=400.0, total=10.0, direction=DOWN)
    assert out["counted"] == 0.0
    assert out["total"] == 10.0
    assert out["rejected"] == 400.0
    assert out["baseline"] == 0.0, "must re-baseline or every later reading re-rejects"


def test_the_cap_is_the_longest_part_life_not_the_longest_interval():
    """[UAC-9] 360 h, and the number is load-bearing.

    360 is the largest DEVICE-declared service life measured live (a Eufy filter's
    `total_life_hours`). The largest declared INTERVAL is 720 h (a Eufy sensor's
    `max_interval_hours`) — a user's reminder ceiling, which bounds nothing about runtime. A
    delta is runtime between two readings, so the part's lifespan is the bound with meaning.
    """
    assert MAX_SINGLE_DELTA_HOURS == 360.0
    assert observe(0.0, baseline=359.0, total=0.0, direction=DOWN)["counted"] == 359.0
    assert observe(0.0, baseline=361.0, total=0.0, direction=DOWN)["rejected"] == 361.0


def test_count_up_is_the_same_rule_mirrored():
    """[UAC-10] Eufy's counters RISE — the spec applied as written would count nothing.

    `usage_hours` goes up with use (alfred: filter 46, sensor 24, tray 12) while roborock's
    `time_left` falls. Same rule, expected direction flipped: a device self-reset (46 -> 0) is
    now the move AGAINST expectation, and books nothing.
    """
    out = _run([0, 10, 46], direction=UP)
    assert out["total"] == 46.0
    reset = _run([0, 46, 0, 3], direction=UP)
    assert reset["total"] == 49.0, "the 46 -> 0 reset must count nothing, then resume"
    assert reset["counted"] == [0.0, 46.0, 0.0, 3.0]


def test_direction_is_inferred_from_the_entity_not_the_brand():
    """[UAC-11] doc 41 holds both ownership models "without a brand check", and this keeps it.

    A per-adapter declaration would be strictly weaker: a brand shipping both shapes works here
    and would not there.
    """
    assert direction_for("314", {"usage_hours": 46}, "usage_hours") == UP
    assert direction_for("293.5", {}, "usage_hours") == DOWN
    assert direction_for("293.5", None, "usage_hours") == DOWN
    # an attribute present but not a number is not a usable accumulator
    assert direction_for("293.5", {"usage_hours": "unavailable"}, "usage_hours") == DOWN


def test_a_reset_inside_a_gap_loses_that_gap_and_it_fails_low():
    """[UAC-12] the one direction it drifts, pinned so it is a decision and not a surprise.

    TWO SHAPES, and the first is worse than "under-counts" suggests:

    (a) the reset leaves the reading HIGHER than the old baseline. Countdown at 20 h, part
        replaced (-> 300), machine runs 5 h, we next read 295. Against a baseline of 20 that is
        movement AGAINST expectation, so it books NOTHING and re-baselines — the 5 hours are
        gone, not netted.
    (b) the reading is still lower than the old baseline. Baseline 300, ran to 250, reset to
        300, ran 5 -> 295. We book 5 where the truth is 55: the net only.

    Both fail LOW and SILENT, which is the direction nothing complains about, and both are
    bounded by how long we can go unobserved — minutes in practice, because a reset is a thing
    a person does at the machine while HA is watching. Accepted knowingly; the alternative is
    inventing runtime we cannot measure.
    """
    lost = _run([20, 295])
    assert lost["total"] == 0.0, "a reset that lands above the old baseline books nothing"
    assert lost["baseline"] == 295

    netted = _run([300, 295])
    assert netted["total"] == 5.0, "when the reading is still lower, only the net is booked"
