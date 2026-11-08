"""[RPL-6..RPL-8] The replay harnesses re-state three shipped rules. They must AGREE.

`reverdict.py`'s rule -- "IMPORT THE REAL FUNCTIONS, never restate their logic" --
is the right default, and two of its sibling harnesses cannot follow it:

  * `harvest.py` is deliberately STDLIB-ONLY. It runs against a recorder SQLite
    file, and importing the shipped converters pulls the whole Home Assistant
    dependency tree in. MEASURED: with `homeassistant` blocked,
    `import custom_components.eufy_vacuum.learning.utils` dies on `voluptuous`,
    and so do `learning.job_finalizer` and `counter_segmentation`. So its two unit
    tables cannot be replaced by an import. They are a REPLICA SET, not a defect.

  * `reclassify.py` DOES import the shipped segmenter, but a payload SHAPE is not
    importable: it has to construct the counter sample the shipped producer emits.

So all three are registered replica sets in `docs/dev/00c-replicas.md` -- RN0RGR1H
(the area table), RN2ZQ5NG (the duration conversion) and RNBTKYXY (the counter
sample). This file is the half an anchor cannot provide. 00c says so itself, in the
paragraph above its `RN8Q25E5` entry:

    "when a replica's sites collapse to one, ask whether the duplicated *statement*
    has become a measurable *fact*. If it has, a test beats an anchor -- an anchor
    only asks two prose copies to agree, a test asks the data to agree with reality."

Here the sets have not collapsed, so the anchors earn their place as the navigation
between members -- but the agreement IS measurable, so it is measured. An anchor has
no failure mode; these do.

EVERY SHIPPED SIDE IS DERIVED, NEVER RETYPED. Spelling the shipped vocabulary into
this file would make it a THIRD copy and the test would then agree with my own
belief about the shipped code, which is exactly the failure being guarded against.
So the area table is compared object-to-object, the duration aliases are read out of
the shipped function's own AST and the factors come from CALLING it, and the sample
keys are read out of the producer's own dict literal.
"""

from __future__ import annotations

import ast
import inspect
import pytest

from custom_components.eufy_vacuum.jobs import active_job as shipped_active_job
from custom_components.eufy_vacuum.learning import job_finalizer as shipped_finalizer
from custom_components.eufy_vacuum.learning import utils as shipped_utils
from custom_components.eufy_vacuum.listeners import job_metrics as shipped_metrics
from tests.replay import harvest, reclassify


# ---------------------------------------------------------------------------
# [RPL-6] RN0RGR1H -- the cleaning-area unit table
# ---------------------------------------------------------------------------


def test_rpl6_the_harvester_area_table_matches_the_shipped_one():
    """[RPL-6] Object equality, because the whole table is the rule.

    RED ON THE DIVERGENCE THAT WAS ALREADY THERE. Before this was written the
    harvester knew 4 of the shipped table's 11 entries, so a `cleaning_area`
    sensor reporting "sq ft" -- a unit shipped code converts -- was scaled by 1.0
    here and the archived number came out 10.76x too small. The harvest corpus is
    the input to every timing and attribution diagnosis in this repo, so a wrong
    factor is not a cosmetic drift; it is a wrong answer with a plausible shape.

    Equality rather than a subset check, in both directions on purpose: an entry
    HERE that shipped code does not have would convert a unit production leaves
    alone, which is the same defect pointing the other way.
    """
    assert harvest._AREA_TO_M2 == shipped_utils._AREA_TO_M2, (
        "the harvester's area table has drifted from "
        "learning/utils.py::_AREA_TO_M2 -- RN0RGR1H"
    )


def test_rpl6_the_shared_factor_is_not_independently_spelled():
    """[RPL-6] The ft2 factor is ONE number, and the harvester's name for it agrees.

    `harvest.FT2_TO_M2` exists because the table is built from it, and a named
    constant that disagrees with the table it feeds is a specific, quiet failure:
    the table would be right and every other use of the constant wrong.
    """
    assert harvest.FT2_TO_M2 == shipped_utils._AREA_TO_M2["ft2"]
    assert harvest._AREA_TO_M2["ft2"] == harvest.FT2_TO_M2


# ---------------------------------------------------------------------------
# [RPL-7] RN2ZQ5NG -- the duration conversion
# ---------------------------------------------------------------------------


def _shipped_duration_aliases() -> set[str]:
    """Every unit string `_duration_state_to_seconds` tests against, from its AST.

    DERIVED, NOT RETYPED. The shipped side is an if-chain over set literals, so
    there is no object to import -- but there is source, and reading it keeps this
    test honest when shipped grows a family. Spelling the aliases here instead
    would make this file a third copy of the vocabulary, and it would then pass for
    as long as my transcription matched my own belief.

    Returns the lowercase strings. Empty is a FAILURE, not a clean result: an
    extraction that silently finds nothing would make every assertion below vacuous
    (the empty-set trap), so the caller asserts on the count.
    """
    src = inspect.getsource(shipped_finalizer._duration_state_to_seconds)
    tree = ast.parse(ast.unparse(ast.parse(src)))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            for el in node.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    out.add(el.value.strip().lower())
    return out


def test_rpl7_the_alias_extraction_actually_finds_the_vocabulary():
    """[RPL-7] The extraction is load-bearing, so prove it is not returning nothing.

    Without this, a refactor of the shipped function into a dict lookup would make
    `_shipped_duration_aliases()` return an empty set and every comparison below
    would pass over nothing at all -- a green test measuring an empty vocabulary.
    The floor is deliberately loose (the exact count is not the contract) but a
    recognisable member of each family has to be in there.
    """
    aliases = _shipped_duration_aliases()
    assert len(aliases) >= 8, f"suspiciously few aliases extracted: {sorted(aliases)}"
    for family in ("ms", "minutes", "hours"):
        assert family in aliases, (
            f"{family!r} missing -- the shipped function's shape changed and this "
            f"extraction no longer reads it: {sorted(aliases)}"
        )


@pytest.mark.parametrize("raw", [1000.0, 7.5])
def test_rpl7_the_harvester_converts_durations_like_the_shipped_function(raw):
    """[RPL-7] Same answer for every unit either side recognises.

    The union is the point. Iterating only the harvester's keys would miss a family
    SHIPPED grew and this did not -- which is the drift direction that actually
    happened on the area table. Iterating only the shipped aliases would miss an
    entry here that production does not have.

    The factors come from CALLING the shipped function rather than from a table in
    this file, so the only thing asserted is agreement.

    THE COMPARISON IS ON THE FACTOR, NOT THE RETURN VALUE, and that distinction is
    measured rather than assumed. The shipped function ends in `int(round(...))` --
    it returns WHOLE SECONDS -- while the harvester keeps the fractional value and
    rounds to one decimal at the call site, because a recorder tape can carry
    sub-second counter deltas. At 7.5 ms those disagree (0 against 0.0075) with no
    drift in the table at all, which is what the first draft of this test reported
    before being corrected: red on the first run is the probe, not the code. So the
    harvester's factor is put through the same integer rounding before comparing,
    which isolates the thing the replica set is actually about.
    """
    aliases = _shipped_duration_aliases() | set(harvest._TIME_TO_S)
    assert aliases, "nothing to compare"

    for unit in sorted(aliases):
        shipped = shipped_finalizer._duration_state_to_seconds(raw, unit)
        scale, _how = harvest._scale_for(unit, harvest._TIME_TO_S, 1.0)
        assert shipped == int(round(raw * scale)), (
            f"unit {unit!r}: shipped says {shipped} s, the harvester scales by "
            f"{scale} -> {raw * scale} s -- RN2ZQ5NG"
        )


def test_rpl7_an_unknown_unit_is_left_canonical_on_both_sides():
    """[RPL-7] The FALLBACK is part of the rule, and it is a policy not an accident.

    Both sides refuse to guess: an unrecognised unit is treated as already
    canonical. If one side started guessing -- or raising -- the corpus and the
    integration would disagree on exactly the readings nobody looked at.
    """
    assert shipped_finalizer._duration_state_to_seconds(42, "furlongs") == 42
    scale, how = harvest._scale_for("furlongs", harvest._TIME_TO_S, 1.0)
    assert scale == 1.0 and how.startswith("unrecognised")

    assert shipped_finalizer._duration_state_to_seconds(42, None) == 42
    scale, how = harvest._scale_for(None, harvest._TIME_TO_S, 1.0)
    assert scale == 1.0 and how == "absent"


# ---------------------------------------------------------------------------
# [RPL-7d] RN2ZQ5NG -- the THIRD copy, on the live-state side
#
# The registry entry declared two copies until 2026-11-08. `listeners/job_metrics.py`
# has its own `_duration_state_to_seconds` -- the live-state side, reading units off
# the HA entity as values arrive -- and it carried no REPLICA marker, appeared nowhere
# in 00c-replicas, and was pinned by nothing: RPL-7 above derives the vocabulary from
# the PRIMARY's AST, so the listener copy could drift alone with every gate green. It
# surfaced while writing tests for its uncovered `ms` and hour branches, not from a
# gate, which is what this file exists to prevent.
# ---------------------------------------------------------------------------


def _aliases_from(func) -> set[str]:
    """Every unit string a duration if-chain tests against, from its own AST.

    The generalisation of `_shipped_duration_aliases`, so the third copy is read the
    same way rather than having its vocabulary retyped here. Empty is a FAILURE, not
    a clean result -- see the caller.
    """
    tree = ast.parse(ast.unparse(ast.parse(inspect.getsource(func))))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            for el in node.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    out.add(el.value.strip().lower())
    return out


def test_rpl7d_the_listener_alias_extraction_finds_a_vocabulary():
    """[RPL-7d] The empty-set trap, for the new side.

    Without this, a refactor of the listener's if-chain into a dict lookup makes the
    extraction return nothing and the comparison below passes over an empty union --
    a green test measuring no aliases at all. Same floor and same reasoning as
    `test_rpl7_the_alias_extraction_actually_finds_the_vocabulary`.
    """
    aliases = _aliases_from(shipped_metrics._duration_state_to_seconds)
    assert len(aliases) >= 8, f"suspiciously few aliases extracted: {sorted(aliases)}"
    for family in ("ms", "minutes", "hours"):
        assert family in aliases, (
            f"{family!r} missing -- the listener's shape changed and this extraction "
            f"no longer reads it: {sorted(aliases)}"
        )


@pytest.mark.parametrize("raw", [300000.0, 0.5, 7.0])
def test_rpl7d_the_listener_converts_durations_like_the_primary(raw):
    """[RPL-7d] Same answer, for every alias EITHER copy knows.

    The union is the point, and in both directions: iterating only the listener's
    aliases would miss a family the primary grew, and iterating only the primary's
    would miss one the listener grew. Both sides are CALLED -- no factor table in
    this file -- so the only thing asserted is agreement.

    The primary takes a `default` and may return None where the listener returns an
    int, so it is called with the default that makes the two comparable; the
    signature difference is not part of the replicated rule, the unit arithmetic is.
    """
    aliases = (
        _aliases_from(shipped_metrics._duration_state_to_seconds)
        | _shipped_duration_aliases()
        | set(shipped_metrics._SECOND_UNIT_ALIASES)
    )
    assert aliases, "nothing to compare"

    for unit in sorted(aliases):
        listener = shipped_metrics._duration_state_to_seconds(raw, unit)
        primary = shipped_finalizer._duration_state_to_seconds(raw, unit)
        assert listener == primary, (
            f"unit {unit!r}: listeners/job_metrics says {listener} s, "
            f"learning/job_finalizer says {primary} s -- RN2ZQ5NG"
        )


def test_rpl7d_both_copies_leave_an_unknown_unit_canonical():
    """[RPL-7d] The refusal-to-guess policy holds on the live-state side too.

    The registry entry calls the fallback part of the rule rather than an edge case:
    if one copy started guessing, or raising, the live-state path and the finalizer
    would disagree on exactly the readings nobody looked at. The listener also WARNS
    on an unrecognised unit, which the primary does not -- that is a signal, not a
    different answer, and the answer is what is asserted here.
    """
    for unit in ("furlongs", None, "", "d"):
        assert (
            shipped_metrics._duration_state_to_seconds(42, unit)
            == shipped_finalizer._duration_state_to_seconds(42, unit)
            == 42
        ), f"unit {unit!r} must be treated as already canonical by both copies"


# ---------------------------------------------------------------------------
# [RPL-8] RNBTKYXY -- the counter-sample payload
# ---------------------------------------------------------------------------


def _shipped_sample_keys() -> set[str]:
    """The keys `_record_counter_sample` appends, from the producer's own literal.

    Derived for the same reason as the duration aliases: a hand-typed key list
    here would be a third copy, and the test would pass whenever my list matched
    my belief rather than the producer.
    """
    src = inspect.getsource(shipped_active_job.ActiveJobMixin._record_counter_sample) \
        if hasattr(shipped_active_job, "ActiveJobMixin") \
        else inspect.getsource(shipped_active_job)
    for node in ast.walk(ast.parse(ast.unparse(ast.parse(src)))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "append"):
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Dict):
            continue
        keys = {k.value for k in node.args[0].keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if "cleaning_time" in keys:
            return keys
    return set()


def test_rpl8_the_producer_key_extraction_finds_the_sample():
    """[RPL-8] Prove the extraction found the real dict before trusting a comparison.

    An empty or wrong-dict result would make the next test compare the harness
    against nothing. This is the same empty-set trap as [RPL-7]'s floor.
    """
    keys = _shipped_sample_keys()
    assert keys, "the producer's sample dict was not found"
    assert {"t", "cleaning_time", "cleaning_area"} <= keys, sorted(keys)


def test_rpl8_the_tape_harness_builds_the_shipped_sample_shape():
    """[RPL-8] Every field the shipped producer emits, the tape harness emits.

    RED BEFORE THE FIX, and quietly: the harness built four of the five keys, and
    the one it dropped was `vacuum_state`. The shipped classifier reads it
    (`counter_segmentation._left_cleaning`), and its documented behaviour for a
    window carrying none is to return None -- "no information" -- so the harness
    was not producing WRONG verdicts, it was running the classifier in its
    pre-signal degraded mode on every tape, unable to exercise the arm the current
    build added. For a harness whose entire purpose is "re-judge with the CURRENT
    code", that is the defect even though nothing is false.

    The bundle is shaped like a real tape: a flat event log of
    ``[ts, entity_id, state]`` rows, which is what `tests/replay/bundle.py`
    produces from a recorder export.
    """
    bundle = {"events": [
        ["2026-08-03T06:04:00+00:00", "vacuum.alfred", "cleaning"],
        ["2026-08-03T06:04:10+00:00", "sensor.alfred_cleaning_area", "6.0"],
        ["2026-08-03T06:04:20+00:00", "sensor.alfred_battery", "88"],
        ["2026-08-03T06:04:30+00:00", "sensor.alfred_cleaning_time", "1.0"],
        ["2026-08-03T06:10:00+00:00", "vacuum.alfred", "docked"],
        ["2026-08-03T06:12:00+00:00", "sensor.alfred_cleaning_time", "2.0"],
    ]}

    samples = reclassify.build_samples(bundle, "alfred")

    assert len(samples) == 2, "one sample per cleaning_time observation"
    assert set(samples[0]) == _shipped_sample_keys(), (
        "the tape harness no longer builds the shipped counter sample -- RNBTKYXY"
    )

    # The carried-forward semantics, which is what makes the field usable: the
    # shipped producer stamps the vacuum's state AT THE TICK, so the harness has to
    # carry the last observation forward rather than join on an exact timestamp.
    assert samples[0]["vacuum_state"] == "cleaning"
    assert samples[1]["vacuum_state"] == "docked", (
        "the dock that happened BETWEEN the two ticks must reach the second sample, "
        "or _left_cleaning can never see a dock trip"
    )


def test_rpl8_a_missing_area_is_left_for_the_shipped_default():
    """[RPL-8] The harness does NOT restate the shipped missing-area sentinel.

    It used to write `-1.0` by hand, which is `counter_segmentation._prepare_window`'s
    own default for an absent `cleaning_area` copied into the caller. Deleting the
    copy is behaviour-identical -- `_prepare_window` applies the same default to a
    None -- and it removes a replica rather than registering one, which is the
    better rung of the ladder whenever it is available.

    Pinned because the obvious "tidy-up" is to put the literal back.
    """
    bundle = {"events": [
        ["2026-08-03T06:04:30+00:00", "sensor.alfred_cleaning_time", "1.0"],
    ]}
    samples = reclassify.build_samples(bundle, "alfred")

    assert samples[0]["cleaning_area"] is None, (
        "a missing area must stay None and let _prepare_window apply its own "
        "default; a hand-written -1.0 here is a replica of that default"
    )

    # No source grep for the literal: the behavioural assertion above IS the guard.
    # Put `-1.0` back and `cleaning_area` stops being None, which reddens this test.
    # A grep would also have gone red on the COMMENT that explains the removal --
    # it asserted on prose rather than behaviour, which is the weaker claim.
