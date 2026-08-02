"""Fault SOURCE classification — is an Eufy error code the station's or the robot's?

Exists because total_error_seconds is subtracted from cleaning_time_seconds, so a fault
that never stopped the robot cleaning silently zeroes a productive run. Live evidence:
alfred job_2026-08-01T23-23-35 cleaned 4 m2 for 360 s and recorded cleaning_time_seconds
0, because five dock-side 6013 faults were counted against it.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.eufy.vocabulary import (
    EUFY_DOCK_SOURCED_ERROR_CODES,
    EUFY_EVIDENCE_SAFE_ROBOT_CODES,
    EUFY_ROBOT_SOURCED_ERROR_CODES,
    eufy_error_invalidates_cleaning,
    eufy_error_source,
)


def test_no_code_is_both_dock_and_robot():
    assert not (EUFY_DOCK_SOURCED_ERROR_CODES & EUFY_ROBOT_SOURCED_ERROR_CODES)


def test_both_sets_are_populated():
    """A silently-emptied set would make every code resolve to unknown and the
    consumer would subtract nothing — quiet, and wrong in the other direction."""
    assert len(EUFY_DOCK_SOURCED_ERROR_CODES) > 30
    assert len(EUFY_ROBOT_SOURCED_ERROR_CODES) > 150


@pytest.mark.parametrize(
    "code,expected",
    [
        (6013, "dock"),    # STATION CLEAN WATER PUMP SHORT — the live incident
        (6021, "dock"),    # STATION DIRTY TANK FULL
        (6113, "dock"),    # STATION NO DUST BAG INSTALLED
        (2112, "robot"),   # ROLLER BRUSH OVERCURRENT — genuinely stops cleaning
        (7004, "robot"),   # MACHINE STUCK
        (1013, "robot"),   # LEFT WHEEL OVERCURRENT
    ],
)
def test_representative_codes(code, expected):
    assert eufy_error_source(code) == expected


@pytest.mark.parametrize("code", [41, 70, 73, 74, 79, 81, 82, 83, 5014])
def test_unprefixed_station_faults_are_dock(code):
    """Eufy prefixes MOST station faults 'STATION' — these carry no prefix and are still
    the dock's (airdryer, dust collector, tanks, tray, sewage, station power). Matching on
    the prefix alone would count every one of them against the robot's cleaning time."""
    assert eufy_error_source(code) == "dock"


@pytest.mark.parametrize("code", [21, 52, 55, 7031, 7033, 7055])
def test_station_named_but_robot_sourced(code):
    """The prefix lies in the other direction too: 7031 STATION RETURN FAILED, 7033
    STATION EXPLORATION FAILED and 7055 STATION NOT FOUND are all the ROBOT failing to
    reach the dock, not the dock failing."""
    assert eufy_error_source(code) == "robot"


@pytest.mark.parametrize("code", [99999, -1, None, "x", "", 3.7, 2112.9, True, object()])
def test_unrecognised_is_unknown_not_robot(code):
    """UNKNOWN IS A REAL ANSWER. Eufy ships new codes and this table goes stale by
    design. A consumer that treated an unrecognised fault as robot-sourced would resume
    zeroing productive runs the moment that happens, which is the defect this table
    exists to fix. Defaulting to the majority class is the trap.

    3.7 and 2112.9 are the sharp ones: int() would truncate them to 3 (SIDE BRUSH STUCK)
    and 2112 (ROLLER BRUSH OVERCURRENT), both real robot codes, so a malformed reading
    would classify as a genuine fault and be subtracted. bool is an int subclass in
    Python, so True would otherwise resolve to code 1."""
    assert eufy_error_source(code) == "unknown"


@pytest.mark.parametrize("code,expected", [("6013", "dock"), (" 2112 ", "robot")])
def test_string_codes_are_accepted(code, expected):
    """HA state attributes arrive as strings; a string of digits is an exact integer."""
    assert eufy_error_source(code) == expected


def test_the_codes_we_classify_come_from_eufys_own_list():
    """Sanity on the table's provenance: every classified code is a plausible Eufy code
    (positive int), and the two bands Eufy uses for station faults are represented."""
    everything = EUFY_DOCK_SOURCED_ERROR_CODES | EUFY_ROBOT_SOURCED_ERROR_CODES
    assert all(isinstance(c, int) and c > 0 for c in everything)
    assert any(6000 <= c < 7000 for c in EUFY_DOCK_SOURCED_ERROR_CODES)
    assert any(7000 <= c < 8000 for c in EUFY_ROBOT_SOURCED_ERROR_CODES)


# ---------------------------------------------------------------------------
# The second dimension: does the fault invalidate the run's cleaning evidence?
# ---------------------------------------------------------------------------

def test_every_evidence_safe_code_is_robot_sourced():
    """The exception list only makes sense against the robot default. A dock code in
    here would be dead weight, and a code in NEITHER source set would be a typo."""
    assert EUFY_EVIDENCE_SAFE_ROBOT_CODES <= EUFY_ROBOT_SOURCED_ERROR_CODES


def test_the_live_incident_no_longer_invalidates():
    """alfred job_2026-08-01T23-23-35: five 6013 faults zeroed a 360 s / 4 m2 run."""
    assert eufy_error_source(6013) == "dock"
    assert eufy_error_invalidates_cleaning(6013) is False


@pytest.mark.parametrize("code", [2112, 7004, 1013, 4011, 3013])
def test_robot_faults_invalidate_by_default(code):
    """Stuck brush, stuck machine, wheel overcurrent, blocked radar, empty tank --
    the floor work cannot be trusted."""
    assert eufy_error_invalidates_cleaning(code) is True


@pytest.mark.parametrize("code", [21, 7031, 7035, 7040, 5015, 7010])
def test_robot_faults_that_happen_outside_the_clean_do_not(code):
    """The two dimensions diverge here, which is why source alone was insufficient:
    every one of these is robot-sourced, and every one leaves the floor work valid --
    docking and undocking bracket the clean, ENTERED NO-GO ZONE is informational, and
    LOW BATTERY (NO SCHEDULED CLEAN) means the run never began."""
    assert eufy_error_source(code) == "robot"
    assert eufy_error_invalidates_cleaning(code) is False


@pytest.mark.parametrize("code", [99999, None, 3.7, "x", True])
def test_unknown_never_invalidates(code):
    """Wrongly crediting a run adds noise that averages out; wrongly zeroing one
    destroys a real observation and teaches the model that area takes no time. The
    default leans toward keeping the evidence."""
    assert eufy_error_invalidates_cleaning(code) is False


def test_no_dock_fault_invalidates():
    """A station fault by definition leaves the floor work untouched. If this ever
    needs an exception, it belongs in a named set, not in an ad-hoc branch."""
    assert not any(eufy_error_invalidates_cleaning(c)
                   for c in EUFY_DOCK_SOURCED_ERROR_CODES)
