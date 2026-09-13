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
    declared_direction,
    direction_for,
    learned_direction,
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
    assert out == {"baseline": 250.0, "total": 42.0, "counted": 0.0,
                   "rejected": None, "moved": None}


def test_unavailable_mid_sequence_does_not_break_the_span():
    """[UAC-6b] and the span across it is still counted correctly afterwards."""
    out = _run([300, "unavailable", 290, "unknown", 285])
    assert out["total"] == 15.0
    assert out["baseline"] == 285


def test_the_first_reading_establishes_the_baseline_only():
    """[UAC-7] a fresh install must not book the hours already on the part."""
    out = observe(130.0, baseline=None, total=0.0, direction=DOWN)
    assert out == {"baseline": 130.0, "total": 0.0, "counted": 0.0,
                   "rejected": None, "moved": None}


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


# ---------------------------------------------------------------------------
# [UAC-13..17] learning the direction from the source itself
# ---------------------------------------------------------------------------


def _learn(readings, *, declared=None):
    """Fold a sequence with NOTHING declared, learning direction as it goes."""
    baseline, total, up, down = None, 0.0, 0, 0
    for r in readings:
        direction = learned_direction(declared, up, down)
        out = observe(r, baseline=baseline, total=total, direction=direction)
        baseline, total = out["baseline"], out["total"]
        if out["moved"] == UP:
            up += 1
        elif out["moved"] == DOWN:
            down += 1
    return {"total": total, "up": up, "down": down,
            "direction": learned_direction(declared, up, down)}


def test_a_countdown_teaches_us_its_direction():
    """[UAC-13] no declaration, no metadata — the source's own movement names it.

    Roborock declares no `state_class` on any sensor, so this is the path its parts take.
    """
    out = _learn([300, 299, 297, 295])
    assert out["direction"] == DOWN
    # THE LEARNING COST, stated as a number rather than a hope: real use across this sequence
    # is 5 h (300 -> 295) and we book 4. The single hour lost is the 300 -> 299 tick that
    # taught us the direction. That is the whole price, it is paid once per source, and it is
    # bounded — unlike a wrong lock, which is unbounded and silent.
    assert out["total"] == 4.0


def test_a_count_up_teaches_us_the_other_direction():
    """[UAC-14] the mirror, from the same rule."""
    out = _learn([0, 1, 3, 5])
    assert out["direction"] == UP
    assert out["total"] == 4.0


def test_a_first_movement_that_is_a_reset_is_outvoted():
    """[UAC-15] THE CASE THAT MADE LOCKING ON THE FIRST TICK UNSAFE.

    If the very first movement we ever see is a reset, a lock-on-first rule learns the INVERSE
    and then books every later reset as runtime while ignoring all real use — permanently, and
    silently, because every number still looks plausible.

    Measured shape: robin's side brush went 193 -> 200 on a reset. Here that jump lands first;
    the ordinary ticks that follow outvote it and the counter recovers on its own.

    THE INPUT THAT MAKES THIS RED: make `learned_direction` return on the first movement
    instead of the majority, and direction comes back UP with total 0.
    """
    out = _learn([193, 200, 199, 198, 197])
    assert out["direction"] == DOWN, "the reset was outvoted by ordinary use"
    assert out["up"] == 1 and out["down"] == 3


def test_nothing_is_booked_while_the_direction_is_unknown():
    """[UAC-16] booking on a guess is worse than booking late.

    A wrong guess counts resets as runtime and ignores real hours forever. Learning costs at
    most the first couple of movements, which is bounded and visible; a wrong lock is neither.
    """
    assert _learn([300])["total"] == 0.0
    assert _learn([300, 299])["total"] == 0.0        # first movement teaches, books nothing
    assert _learn([300, 299, 298])["total"] == 1.0   # thereafter it counts


def test_a_declaration_short_circuits_the_learning():
    """[UAC-17] HA's own `state_class` is a head start where it exists — measured per brand.

    alfred's total clock says `total`, robin's says `total_increasing`, alfred's part counters
    say `measurement`. ivy says NOTHING on any sensor, which is why the declaration can only
    ever be a shortcut and never the rule.
    """
    assert declared_direction("total", None, "usage_hours") == UP
    assert declared_direction("total_increasing", None, "usage_hours") == UP
    assert declared_direction("measurement", None, "usage_hours") == DOWN
    assert declared_direction(None, None, "usage_hours") is None
    assert declared_direction("", {"usage_hours": 46}, "usage_hours") == UP

    # declared -> counted from the very first movement, no learning tick spent
    out = _learn([300, 299, 297], declared=DOWN)
    assert out["total"] == 3.0
