"""A lens must be SUFFICIENT for its question, not merely smaller.

Cutting a recording is only safe if what survives still answers the thing the
lens is named for. These pin that, and pin the trap that a suffix match walks
straight into.
"""

from __future__ import annotations

from tests.replay.refocus import LENSES, ODOMETER_SUFFIXES, refocus


def _bundle(events, initial=None):
    return {"meta": {"source": "test"}, "initial": initial or {}, "events": events}


def test_the_timing_lens_keeps_the_counters_that_answer_it():
    """The counters ARE the measurement; losing either makes the lens a lie."""
    b = _bundle([
        ["t1", "sensor.alfred_cleaning_time", "0.5"],
        ["t2", "sensor.alfred_cleaning_area", "10.76"],
        ["t3", "sensor.alfred_task_status", "Cleaning"],
        ["t4", "vacuum.alfred", "cleaning"],
        ["t5", "sensor.alfred_filter_remaining", "87"],     # irrelevant here
        ["t6", "sensor.alfred_robot_position_x_raw", "123"],  # deliberately not in scope
    ])
    kept = {e[1] for e in refocus(b, "timing")["events"]}
    assert "sensor.alfred_cleaning_time" in kept
    assert "sensor.alfred_cleaning_area" in kept
    assert "sensor.alfred_task_status" in kept, "the frame, not a topic"
    assert "vacuum.alfred" in kept, "the frame, not a topic"
    assert "sensor.alfred_filter_remaining" not in kept
    assert "sensor.alfred_robot_position_x_raw" not in kept


def test_a_lifetime_odometer_never_impersonates_the_per_run_counter():
    """THE trap. `sensor.dining_room_alfred_total_cleaning_area` ends with
    "_cleaning_area", so a suffix match written for the per-run counter swallows
    it — and because the odometer is a monotonic lifetime total in the
    thousands, summing the two does not look wrong, it just returns a number
    hundreds of times too large. That is not hypothetical: it is exactly what my
    own verification script did before this existed."""
    b = _bundle([
        ["t1", "sensor.alfred_cleaning_area", "10.76"],
        ["t2", "sensor.dining_room_alfred_total_cleaning_area", "11757.4"],
        ["t3", "sensor.dining_room_alfred_total_cleaning_time", "202.78"],
    ])
    kept = {e[1] for e in refocus(b, "timing")["events"]}
    assert kept == {"sensor.alfred_cleaning_area"}

    # ...but they are not deleted from existence: ask for them and they are there.
    odo = {e[1] for e in refocus(b, "odometer")["events"]}
    assert odo == {"sensor.dining_room_alfred_total_cleaning_area",
                   "sensor.dining_room_alfred_total_cleaning_time"}
    assert all(any(o.endswith(s) for s in ODOMETER_SUFFIXES) for o in odo)


def test_initial_keeps_a_flat_sensor_rather_than_erasing_it():
    """"It never moved" is an observation. Dropping an entity from `initial`
    because it produced no events turns a flat sensor into a missing one, which
    reads as a different fault entirely."""
    b = _bundle(
        [["t1", "sensor.alfred_cleaning_time", "0.5"]],
        {"sensor.alfred_cleaning_area": "0.0", "sensor.alfred_filter_remaining": "87"},
    )
    out = refocus(b, "timing")
    assert out["initial"] == {"sensor.alfred_cleaning_area": "0.0"}


def test_every_lens_says_why_it_is_that_set():
    """A lens with no rationale is a guess that will be widened by the next
    person who finds it inconvenient."""
    for name, (_suffixes, why) in LENSES.items():
        assert why and len(why) > 40, f"lens {name} has no real rationale"


def test_the_cut_is_recorded_in_the_output():
    """A focused bundle that does not say what it is focused on cannot be told
    apart from a complete one that is missing data."""
    b = _bundle([["t1", "sensor.alfred_cleaning_time", "0.5"],
                 ["t2", "sensor.alfred_filter_remaining", "87"]])
    meta = refocus(b, "timing")["meta"]
    assert meta["lens"] == "timing"
    assert meta["dropped_events"] == 1
    assert meta["lens_rationale"]
