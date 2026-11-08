"""Unit tests for saved-zone learning (pure — no HA, no I/O).

[ZL-1]  collect_zone_observations pulls a SINGLE-zone phase's timing into one observation.
[ZL-2]  a MULTI-zone step is skipped (time isn't attributable to one zone_id).
[ZL-3]  non-zone phases, missing/zero-wall timings, and malformed input yield nothing.
[ZL-4]  update_learned_zone: first sample seeds avg=wall, count=1.
[ZL-5]  update_learned_zone: second sample is a running mean; count increments.
[ZL-6]  mop vs vacuum keep separate buckets; different zone_ids keep separate keys.
[ZL-7]  record_observations folds a batch and returns the applied count (0 on empty).
[ZL-8]  estimate_zone_seconds prefers the learned average once a sample exists.
[ZL-9]  estimate falls back to area x per-mode rate before any sample; none with neither.
[ZL-10] estimate is clamped to a sane band (a wild area/sample can't run away).

[ZL-11] one unreadable wall_seconds drops THAT timing, not the run's other zones.
[ZL-12] an unreadable area_m2 keeps the observation and nulls the area — the learnable
        wall time is not thrown away over a cosmetic field.
[ZL-13] a non-dict store is re-seeded rather than raising.
[ZL-14] a corrupt per-zone bucket is re-seeded WITHOUT taking the map's other zones
        down with it.
[ZL-15] unreadable counters in a bucket restart from this sample, and the new average
        is the sample — a corrupt avg must not poison the running mean.
[ZL-16] record_observations skips a malformed observation and reports the applied
        count honestly, because that count is the caller's persistence gate.
[ZL-17] an unreadable bucket falls back to area and must NOT report "learned".
[ZL-18] an unreadable area with no samples gives source "none", seconds 0.
[ZL-19] every store shape that cannot be read falls back; none of them claims learned.
[ZL-20] the combination: one fold into a store corrupt three ways, then an estimate
        off the result.
[ZL-21] a rejected fold mutates nothing — one row per failing conversion, since
        hoisting two of three above the mutation looks exactly like hoisting all three.

WHY [ZL-11]..[ZL-20] ARE TESTS AND NOT CLASSIFICATIONS. They cover `except` arms and
`isinstance` re-seeds, which is usually the shape to leave uncovered and classify --
one stage re-validating the stage before it. These are the other case. The producer
here is not an in-process function with a typed return; it is
``map_bucket["learned_zones"]`` as last month's build left it on disk, read back
across versions and recoverable by hand (this repo's own rule records `.storage`
edits causing `.corrupt` backups). And the consequence is not a discarded value:
`update_learned_zone` MUTATES a store the caller then persists, so an arm that raised
instead of re-seeding would break learning for that whole map permanently, and one
that quietly produced garbage would ship a wrong ETA. Each test below names the input
that reddens it; each was run as an ablation.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.learning import zone_learning as zl


_NOW = "2026-07-13T08:00:00+00:00"


def _zone_phase(zone_ids, *, wall, mode="mop", area=0.5):
    return {
        "phase_type": "zone",
        "zone_ids": list(zone_ids),
        "zone_timing": {
            "zone_ids": list(zone_ids),
            "clean_mode": mode,
            "wall_seconds": wall,
            "area_m2": area,
        },
    }


def test_collect_single_zone_observation():
    """[ZL-1]"""
    job = {"phases": [
        {"phase_type": "room_group"},
        _zone_phase(["z1"], wall=270, mode="mop", area=0.5),
    ]}
    obs = zl.collect_zone_observations(job)
    assert obs == [{"zone_id": "z1", "clean_mode": "mop", "wall_seconds": 270, "area_m2": 0.5}]


def test_collect_skips_multi_zone_step():
    """[ZL-2] a step cleaning two zones at once can't attribute time to one zone_id."""
    job = {"phases": [_zone_phase(["z1", "z2"], wall=400)]}
    assert zl.collect_zone_observations(job) == []


def test_collect_ignores_noise():
    """[ZL-3]"""
    assert zl.collect_zone_observations(None) == []
    assert zl.collect_zone_observations({"phases": "nope"}) == []
    # zero / missing wall, and non-zone phases, all drop
    job = {"phases": [
        {"phase_type": "charge_wait"},
        _zone_phase(["z1"], wall=0),
        {"phase_type": "zone", "zone_ids": ["z9"]},          # no zone_timing
    ]}
    assert zl.collect_zone_observations(job) == []


def test_update_first_sample_seeds():
    """[ZL-4]"""
    store = zl.update_learned_zone(
        {}, zone_id="z1", clean_mode="mop", wall_seconds=270, area_m2=0.5, now_iso=_NOW
    )
    b = store["z1"]["mop"]
    assert b["avg_wall_seconds"] == 270 and b["sample_count"] == 1
    assert b["last_wall_seconds"] == 270 and b["last_area_m2"] == 0.5


def test_update_second_sample_is_running_mean():
    """[ZL-5]"""
    store = zl.update_learned_zone(
        {}, zone_id="z1", clean_mode="mop", wall_seconds=200, area_m2=0.5, now_iso=_NOW
    )
    store = zl.update_learned_zone(
        store, zone_id="z1", clean_mode="mop", wall_seconds=300, area_m2=0.5, now_iso=_NOW
    )
    b = store["z1"]["mop"]
    assert b["avg_wall_seconds"] == 250 and b["sample_count"] == 2


def test_modes_and_zones_stay_separate():
    """[ZL-6]"""
    store = zl.update_learned_zone(
        {}, zone_id="z1", clean_mode="mop", wall_seconds=300, area_m2=0.5, now_iso=_NOW
    )
    store = zl.update_learned_zone(
        store, zone_id="z1", clean_mode="vacuum", wall_seconds=60, area_m2=0.5, now_iso=_NOW
    )
    store = zl.update_learned_zone(
        store, zone_id="z2", clean_mode="mop", wall_seconds=120, area_m2=0.3, now_iso=_NOW
    )
    assert store["z1"]["mop"]["avg_wall_seconds"] == 300
    assert store["z1"]["vacuum"]["avg_wall_seconds"] == 60
    assert store["z2"]["mop"]["avg_wall_seconds"] == 120


def test_record_observations_batch_and_empty():
    """[ZL-7]"""
    obs = [
        {"zone_id": "z1", "clean_mode": "mop", "wall_seconds": 270, "area_m2": 0.5},
        {"zone_id": "z2", "clean_mode": "vacuum", "wall_seconds": 40, "area_m2": 0.3},
    ]
    store, applied = zl.record_observations({}, obs, now_iso=_NOW)
    assert applied == 2 and set(store) == {"z1", "z2"}
    store2, applied2 = zl.record_observations(store, [], now_iso=_NOW)
    assert applied2 == 0 and store2 is store


def test_estimate_prefers_learned():
    """[ZL-8] a learned average wins over the area fallback the moment a sample exists."""
    store, _ = zl.record_observations(
        {}, [{"zone_id": "z1", "clean_mode": "mop", "wall_seconds": 285, "area_m2": 0.5}],
        now_iso=_NOW,
    )
    est = zl.estimate_zone_seconds(store, zone_id="z1", clean_mode="mop", area_m2=0.5)
    assert est["source"] == "learned" and est["seconds"] == 285 and est["sample_count"] == 1


def test_estimate_area_fallback_then_none():
    """[ZL-9]"""
    fb = zl.estimate_zone_seconds({}, zone_id="z1", clean_mode="vacuum", area_m2=2.0)
    assert fb["source"] == "area_fallback" and fb["seconds"] == 120  # 2.0 * 60
    none = zl.estimate_zone_seconds({}, zone_id="z1", clean_mode="vacuum", area_m2=None)
    assert none["source"] == "none" and none["seconds"] == 0


def test_estimate_is_clamped():
    """[ZL-10] a huge area can't produce an hours-long ETA; a tiny one can't go sub-floor."""
    hi = zl.estimate_zone_seconds({}, zone_id="z", clean_mode="mop", area_m2=10_000.0)
    assert hi["seconds"] == 3600
    lo = zl.estimate_zone_seconds({}, zone_id="z", clean_mode="vacuum", area_m2=0.0001)
    assert lo["seconds"] == 30


# ---------------------------------------------------------------------------
# Reading a store that is not the shape this build writes — [ZL-11]..[ZL-20]
# ---------------------------------------------------------------------------

def test_zl11_one_unreadable_wall_does_not_lose_the_runs_other_zones():
    """[ZL-11] A corrupt timing is dropped; its siblings in the same run survive.

    The consequence is the whole point, and it is not "a line is covered". These
    timings arrive as a LIST from one finished job, so an unguarded `int()` would
    raise out of `observations_from_timings` and take every other zone in that run
    with it — a single bad field costing a whole clean's learning. Asserting only
    that the bad one is absent would pass just as well if the good one were lost too,
    so the good one is the assertion.

    RED: delete the `except (TypeError, ValueError): continue` and this raises
    TypeError instead of returning the surviving observation.
    """
    obs = zl.observations_from_timings([
        {"zone_ids": ["z_bad"], "wall_seconds": "not a number", "area_m2": 0.5},
        {"zone_ids": ["z_good"], "wall_seconds": 120, "area_m2": 0.5},
        {"zone_ids": ["z_none"], "wall_seconds": None, "area_m2": 0.5},
    ])

    assert [o["zone_id"] for o in obs] == ["z_good"]
    assert obs[0]["wall_seconds"] == 120


def test_zl12_an_unreadable_area_keeps_the_observation_and_nulls_the_area():
    """[ZL-12] Area is cosmetic here; wall time is the thing being learned.

    `area_m2` only ever feeds the cold-start fallback and the stored
    `last_area_m2`, so an unreadable one must not cost the observation — the wall
    seconds are what `update_learned_zone` folds into the average. Note the
    asymmetry with [ZL-11]: an unreadable wall DROPS the timing, an unreadable area
    KEEPS it. Two `except` arms, three lines apart, deliberately doing opposite
    things.

    RED: change `area = None` in that handler to `continue` and the observation
    disappears, taking a perfectly good 120-second sample with it.
    """
    obs = zl.observations_from_timings([
        {"zone_ids": ["z1"], "wall_seconds": 120, "area_m2": "wide"},
    ])

    assert len(obs) == 1
    assert obs[0]["area_m2"] is None
    assert obs[0]["wall_seconds"] == 120, "the learnable field must survive"


def test_zl13_a_non_dict_store_is_reseeded_rather_than_raising():
    """[ZL-13] Fold into a store that is not a dict at all.

    RED: delete `if not isinstance(store, dict): store = {}` and `store.setdefault`
    raises AttributeError on the string.
    """
    out = zl.update_learned_zone(
        "this is not a store", zone_id="z1", clean_mode="mop",
        wall_seconds=300, area_m2=0.5, now_iso=_NOW,
    )

    assert out["z1"]["mop"]["sample_count"] == 1
    assert out["z1"]["mop"]["avg_wall_seconds"] == 300.0


def test_zl14_a_corrupt_zone_bucket_does_not_take_the_other_zones_with_it():
    """[ZL-14] Re-seeding ONE zone's bucket must not clear the map's other zones.

    `learned_zones` holds every zone on the map in one dict, and the caller
    persists whatever comes back. So the interesting question is not whether the
    corrupt key recovers — it is whether the recovery is surgical. A re-seed written
    as `store = {}` would pass an assertion about `z_bad` alone while silently
    discarding every other zone's samples on save.

    RED: delete the `by_mode = {}` / `store[str(zone_id)] = by_mode` pair and
    `by_mode.get(mode)` raises AttributeError on the string.
    """
    store = {
        "z_ok": {"vacuum": {"avg_wall_seconds": 90.0, "sample_count": 4}},
        "z_bad": "corrupt, as an older build or a hand-edit left it",
    }

    out = zl.update_learned_zone(
        store, zone_id="z_bad", clean_mode="vacuum",
        wall_seconds=300, area_m2=0.5, now_iso=_NOW,
    )

    assert out["z_bad"]["vacuum"]["sample_count"] == 1
    assert out["z_ok"]["vacuum"] == {"avg_wall_seconds": 90.0, "sample_count": 4}, (
        "the untouched zone's samples must survive the re-seed"
    )


def test_zl15_unreadable_counters_restart_without_poisoning_the_mean():
    """[ZL-15] A bucket whose numbers cannot be read starts over AT this sample.

    The running mean is `(avg * n + wall) / (n + 1)`, so an unreadable `avg` or `n`
    that fell through as anything other than zero would fold a garbage value into
    every future sample for that zone — permanently, because the result is
    persisted. Asserting `sample_count == 1` alone would not see that; the average
    has to be checked too.

    RED: delete the `except (TypeError, ValueError): n, avg = 0, 0.0` and this
    raises ValueError on `int("many")`.
    """
    store = {"z1": {"mop": {"sample_count": "many", "avg_wall_seconds": "ages"}}}

    out = zl.update_learned_zone(
        store, zone_id="z1", clean_mode="mop",
        wall_seconds=300, area_m2=0.5, now_iso=_NOW,
    )

    assert out["z1"]["mop"]["sample_count"] == 1
    assert out["z1"]["mop"]["avg_wall_seconds"] == 300.0, (
        "the new average must BE the new sample, not a blend with garbage"
    )


def test_zl16_a_malformed_observation_is_skipped_and_the_count_says_so():
    """[ZL-16] The applied count is the caller's persistence gate, so it must be true.

    `record_observations` documents the count as what lets the caller "skip
    persistence" when there is nothing to learn. An inflated count causes a pointless
    write; an unguarded loop loses the whole batch to one bad entry. Both halves are
    asserted, plus that the store holds only the good zone.

    A REJECTED FOLD TOUCHES NOTHING, which is the half this test could not assert when
    it was written. `update_learned_zone` used to run `store.setdefault(str(zone_id),
    {})` before its conversions could raise, so an observation rejected for a bad wall
    time still minted its zone key — and because `applied` is non-zero from the good
    observation, the caller persisted that empty bucket. It was inert (every reader
    goes through `estimate_zone_seconds`, which treats `{}` like an absent key) but it
    was on disk, and only a rebuild cleared it. The conversions now happen above the
    first mutation, so `list(store)` is the assertion it should always have been.

    RED, two ways: delete the `except (KeyError, TypeError, ValueError): continue` in
    `record_observations` and the missing `zone_id` raises KeyError, losing the good
    observation with it; or move any conversion in `update_learned_zone` back below
    `store.setdefault` and `z_bad` reappears as an empty bucket.
    """
    store, applied = zl.record_observations(
        {},
        [
            {"clean_mode": "mop", "wall_seconds": 300},          # no zone_id
            {"zone_id": "z_good", "clean_mode": "mop", "wall_seconds": 300},
            {"zone_id": "z_bad", "clean_mode": "mop", "wall_seconds": "nope"},
        ],
        now_iso=_NOW,
    )

    assert applied == 1, "two of the three were unusable"
    assert store["z_good"]["mop"]["sample_count"] == 1
    assert list(store) == ["z_good"], (
        "a rejected observation must leave no trace at all, not even an empty bucket"
    )


@pytest.mark.parametrize("wall,area,why", [
    pytest.param("nope", None, "wall_seconds is not a number at all",
                 id="wall-not-a-number"),
    pytest.param("300.5", None,
                 "float() accepts it, int() does not - the second conversion alone",
                 id="wall-float-ok-int-not"),
    pytest.param(300, "unreadable",
                 "the AREA is the third conversion, the one I first missed",
                 id="area-not-a-number"),
])
def test_zl21_every_failing_conversion_leaves_the_store_untouched(wall, area, why):
    """[ZL-21] All three conversions must reject BEFORE the store is touched.

    The fix that made [ZL-16] assertable hoisted the conversions above
    `store.setdefault`, and there are THREE of them. A row per conversion, because
    hoisting two of three is indistinguishable from hoisting all three unless
    something exercises the one left behind — and that is exactly what happened: my
    first pass moved the two `wall_seconds` conversions and left `round(area_m2, 2)`
    below the mutation, where it raises on a non-number for the same reason.

    The middle row is the one to keep in mind: `"300.5"` passes `float()` and fails
    `int()`, so a fix that hoisted only the `float` call would still mint the key
    here. Each row asserts the store is untouched AND that the exception the caller
    relies on still escapes — a fix that swallowed it would make `record_observations`
    count an application that never happened.

    The explicit `id=` on each row is not cosmetic. With the `why` string generating
    the ids, the node ids contained spaces and parentheses, and the ablation harness
    that checks these rows can go red parses `pytest -v` with `::(\\S+?)\\s+(PASSED|
    FAILED)` — which cannot cross a space, so it matched none of these rows and
    reported "nothing reddened" for an ablation that reddens all three. The test was
    fine and the instrument was blind; the only visible symptom was its baseline
    counting 20 tests in a file holding 21.
    """
    store = {}
    with pytest.raises((TypeError, ValueError)):
        zl.update_learned_zone(
            store, zone_id="z_bad", clean_mode="mop",
            wall_seconds=wall, area_m2=area, now_iso=_NOW,
        )

    assert store == {}, f"store was mutated despite rejection ({why})"


def test_zl17_an_unreadable_bucket_falls_back_and_never_claims_learned():
    """[ZL-17] The `source` field is a claim to the user, and it must not lie.

    The card renders this: "learned" means the number came from this zone's own
    observed history. A bucket whose counters cannot be read has no usable history,
    so reporting `learned` — with whatever `sample_count` survived — would present a
    fabricated figure as measured. The fallback is the honest answer.

    RED: delete the `except (TypeError, ValueError): n, avg = 0, 0.0` in
    `estimate_zone_seconds` and this raises ValueError.
    """
    store = {"z1": {"mop": {"sample_count": "lots", "avg_wall_seconds": "ages"}}}

    got = zl.estimate_zone_seconds(store, zone_id="z1", clean_mode="mop", area_m2=2.0)

    assert got["source"] == "area_fallback"
    assert got["sample_count"] == 0
    assert got["seconds"] == 480  # 2.0 m2 x the 240 s/m2 mop rate


def test_zl18_an_unreadable_area_with_no_samples_is_none_not_a_guess():
    """[ZL-18] With no history and no usable area, the answer is "I don't know".

    `source == "none"` with `seconds == 0` is what makes the caller render
    "learning…" rather than a number. Clamping would turn a bad area into a
    confident-looking 30 seconds, which is worse than admitting nothing is known.

    RED: delete the `except (TypeError, ValueError): a = None` and this raises
    ValueError on `float("quite big")`.
    """
    got = zl.estimate_zone_seconds(
        {}, zone_id="z1", clean_mode="vacuum", area_m2="quite big",
    )

    assert got == {"seconds": 0, "source": "none", "sample_count": 0}


@pytest.mark.parametrize("store", [
    None,
    "corrupt",
    [],
    {"z1": "not a per-mode dict"},
    {"z1": {"mop": "not a bucket"}},
    {"z1": {"vacuum": {"sample_count": 3, "avg_wall_seconds": 90.0}}},  # wrong MODE
])
def test_zl19_no_unreadable_store_shape_ever_claims_learned(store):
    """[ZL-19] Every way the store can fail to answer, and none of them lies.

    One shape is not enough here: the read walks three separate `isinstance` gates
    (`store`, `store[zone_id]`, the bucket) and a missing key, and a test of one arm
    says nothing about the others. The last row is the one worth noticing — a
    perfectly VALID store that simply has no sample for the mode being asked about,
    which must behave exactly like the corrupt ones rather than borrowing the other
    mode's average. That is the whole reason the two modes are keyed separately.

    RED: make any of those gates fall through (e.g. drop the
    `if isinstance(by_mode, dict)` test) and the corresponding row raises or returns
    `learned` off a value it cannot read.
    """
    got = zl.estimate_zone_seconds(store, zone_id="z1", clean_mode="mop", area_m2=2.0)

    assert got["source"] == "area_fallback"
    assert got["sample_count"] == 0
    assert got["seconds"] == 480


def test_zl20_a_store_corrupt_three_ways_folds_and_then_estimates():
    """[ZL-20] The combination, end to end, because defects live in the pairing.

    [ZL-13]..[ZL-18] each exercise one arm with one bad field. A store recovered
    from a real older build is not polite enough to be wrong in one place at a time,
    and "every field validated individually" is the sound a combination gap makes.
    So: one fold into a store that is corrupt at the zone level AND the bucket level
    AND the counter level, from a timing whose area is also unreadable — then an
    estimate off the result, which is what the user actually sees.

    The timing names `mop` deliberately so the fold lands ON the corrupt bucket. An
    earlier draft left `clean_mode` absent, which defaults to `vacuum` — and the
    corrupt `mop` bucket then sat untouched beside the new one, so the test looked
    like a combination and exercised a single arm.

    RED: the area handler in `observations_from_timings`, or the counter handler in
    `update_learned_zone` — both are on this path, and each reddens this as well as
    its own single-arm test. With both present the fold must still produce a store
    the estimator reports as `learned`, because after a successful recovery there IS
    one real sample.
    """
    store = {
        "z_keep": {"mop": {"avg_wall_seconds": 100.0, "sample_count": 2}},
        "z_target": {"mop": {"sample_count": "?", "avg_wall_seconds": None}},
        "z_rotten": "not a dict at all",
    }
    obs = zl.observations_from_timings([
        {"zone_ids": ["z_target"], "clean_mode": "mop",
         "wall_seconds": 300, "area_m2": "unreadable"},
    ])
    assert obs == [{
        "zone_id": "z_target", "clean_mode": "mop",
        "wall_seconds": 300, "area_m2": None,
    }]

    out, applied = zl.record_observations(store, obs, now_iso=_NOW)

    assert applied == 1
    # the recovered bucket, the untouched sibling zone, and the still-rotten key
    assert out["z_target"]["mop"]["sample_count"] == 1
    assert out["z_target"]["mop"]["avg_wall_seconds"] == 300.0, (
        "recovered from unreadable counters, so the average IS the one real sample"
    )
    assert out["z_target"]["mop"]["last_area_m2"] is None
    assert out["z_keep"]["mop"] == {"avg_wall_seconds": 100.0, "sample_count": 2}
    assert out["z_rotten"] == "not a dict at all", (
        "a zone nothing touched is left exactly as found, not helpfully repaired"
    )

    got = zl.estimate_zone_seconds(out, zone_id="z_target", clean_mode="mop")
    assert got == {"seconds": 300, "source": "learned", "sample_count": 1}
