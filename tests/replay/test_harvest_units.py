"""The harvester's unit handling, proved on cases the live corpus does not contain.

Every run in the harvested corpus reports one unit throughout, so the per-row
conversion path never actually fires against real data. A guard that exists reads
as complete whether or not it works; these build the cases the house has not
happened to produce.
"""

from __future__ import annotations

import json
import sqlite3

from tests.replay.harvest import _AREA_TO_M2, _progress_total, _readings

FT2 = 10.7639104167097   # 1 m² expressed in ft²


def _db(rows: list[tuple[float, str, str | None]]) -> sqlite3.Connection:
    """A recorder-shaped in-memory DB holding one sensor's history.

    Only the three columns the harvester joins on — the point is the JOIN and the
    per-row attributes, not a faithful copy of Home Assistant's schema.
    """
    con = sqlite3.connect(":memory:")
    con.executescript(
        "CREATE TABLE state_attributes (attributes_id INTEGER PRIMARY KEY, shared_attrs TEXT);"
        "CREATE TABLE states (metadata_id INT, last_updated_ts REAL, state TEXT, attributes_id INT);"
    )
    attr_ids: dict[str | None, int | None] = {}
    for ts, state, unit in rows:
        if unit not in attr_ids:
            if unit is None:
                attr_ids[unit] = None
            else:
                # Real recorders DEDUPE attributes: many states share one row.
                # Inserting per distinct unit mirrors that, so the test would
                # catch a harvester that assumed one attributes_id per state.
                aid = len(attr_ids) + 1
                con.execute("INSERT INTO state_attributes VALUES (?, ?)",
                            (aid, json.dumps({"unit_of_measurement": unit})))
                attr_ids[unit] = aid
        con.execute("INSERT INTO states VALUES (1, ?, ?, ?)", (ts, state, attr_ids[unit]))
    con.commit()
    return con


def test_a_unit_change_mid_window_does_not_look_like_cleaning():
    """THE fencepost. The user flips HA to imperial while the robot is running.

    The RAW series leaps — 3 m² becomes 32.29 the instant the display changes —
    and anything that resolved one unit for the whole window would either read
    that jump as ~29 m² of sudden sweeping, or scale the metric readings as if
    they had been imperial all along. Neither happened: the robot cleaned 5 m²,
    and a settings page does not clean floors.
    """
    con = _db([
        # An explicit pre-window floor, so this test measures the UNIT CHANGE and
        # not the "an unknown floor is not zero" policy - without it the first
        # reading is only a baseline and the run correctly measures 4 m², which
        # would make this assert about the wrong thing.
        (50.0, "0", "m²"),
        (100.0, "1", "m²"), (200.0, "2", "m²"), (300.0, "3", "m²"),
        # --- user switches to imperial here; same 3 m², new number ---
        (400.0, f"{3 * FT2}", "ft²"), (500.0, f"{4 * FT2}", "ft²"),
        (600.0, f"{5 * FT2}", "ft²"),
    ])
    values, floor, seen = _readings(con, 1, 60.0, 1000.0, _AREA_TO_M2)
    assert seen == {"m²", "ft²"}, "both units must be reported, not just the last"
    assert [round(v, 6) for v in values] == [1.0, 2.0, 3.0, 3.0, 4.0, 5.0]
    assert floor and round(floor[0], 6) == 0.0
    # 5.0, not 7.0: the ft² round-trip lands 3 m² back as 2.9999999999999942, a
    # DECREASE. Read as a reset it re-adds the whole reading as fresh progress.
    assert round(_progress_total(values, floor[0]), 6) == 5.0


def test_the_pre_window_floor_uses_its_own_unit_not_the_windows():
    """The floor PREDATES the window, so the window's unit cannot describe it.

    A run that opens after a switch to metric has a floor recorded in ft². Scaling
    that floor with the window's m² would leave it 10.76x too large, the counter
    would read as having gone backwards, and the reset branch would swallow the
    run's opening reading.
    """
    con = _db([
        (100.0, f"{6 * FT2}", "ft²"),   # floor: 6 m², recorded while imperial
        # --- switched to metric before the run ---
        (200.0, "1", "m²"), (300.0, "2", "m²"),
    ])
    values, floor, _seen = _readings(con, 1, 150.0, 400.0, _AREA_TO_M2)
    assert round(floor[0], 6) == 6.0, "floor must convert with the unit it was written in"
    # 1 m² < the 6 m² floor, so the counter reset: the run swept 2 m², not 2 - 6.
    assert round(_progress_total(values, floor[0]), 6) == 2.0


def test_an_absent_unit_is_never_guessed_at():
    """No attributes at all. The reading is taken as already canonical and the
    absence is reported, rather than a factor being invented for it — the same
    policy as the production cleaning_area_to_m2."""
    con = _db([(100.0, "1", None), (200.0, "3", None)])
    values, _floor, seen = _readings(con, 1, 0.0, 300.0, _AREA_TO_M2)
    assert values == [1.0, 3.0]
    assert seen == set()


def test_unavailable_readings_are_gaps_not_zeroes():
    """A sensor that drops out must not read as the counter returning to zero,
    which the reset-aware total would book as a whole run's worth of sweeping."""
    con = _db([(100.0, "1", "m²"), (200.0, "unavailable", "m²"), (300.0, "4", "m²")])
    values, floor, _seen = _readings(con, 1, 0.0, 400.0, _AREA_TO_M2)
    assert values == [1.0, 4.0]
    assert round(_progress_total(values, floor[0] if floor else None), 6) == 3.0
