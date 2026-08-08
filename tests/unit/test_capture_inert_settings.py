"""A captured setting the mode cannot apply is not a measurement.

External (app-started) runs are captured by reading the vacuum's global setting
selects per tick — they are the only window into what the app set, because VA did not
dispatch the job and has no payload for it.

But those selects keep reporting a value whether or not the current mode uses it.
Confirmed on hardware 2026-08-08: the Eufy app DISABLES the suction picker in
mop-only mode, and `select.<vac>_suction_level` went on reading "Max" throughout.
Capturing that recorded the run as having used Max suction — a number that was never
applied, entering Learning Review and the estimate buckets looking exactly like a
real measurement. Indistinguishable from one, which is why it would never be noticed.

Symmetric on the other side: in vacuum-only mode the mop dials are equally inert.

Absent says "this mode does not use that", which is true and which downstream can
reason about. It mirrors the dispatch side, where queue_engine only writes
water_level / edge_mopping for mop modes.

Coverage targets
----------------
[CAP-1] mop-only drops fan_speed.
[CAP-2] vacuum-only drops the mop dials.
[CAP-3] vacuum_mop keeps everything — both halves apply.
[CAP-4] an unknown/absent mode drops nothing (never guess).
[CAP-5] water_level and mop_intensity go together — one device value, two labels.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.jobs.active_job import (
    _drop_settings_the_mode_does_not_use as drop_inert,
)


def _captured(mode: str) -> dict[str, str]:
    """What the selects report — everything, regardless of what the mode uses."""
    return {
        "clean_mode": mode,
        "fan_speed": "Max",
        "water_level": "High",
        "mop_intensity": "Max",
        "clean_intensity": "Quick",
    }


def test_cap_1_mop_only_drops_suction():
    """[CAP-1] The live case: the app greys out suction, the select still reads Max."""
    out = drop_inert(_captured("mop"))
    assert "fan_speed" not in out
    # ...and the settings mopping DOES use are untouched.
    assert out["water_level"] == "High"
    assert out["clean_intensity"] == "Quick"


def test_cap_2_vacuum_only_drops_the_mop_dials():
    """[CAP-2] The mirror image — no water is applied, so no water was measured."""
    out = drop_inert(_captured("vacuum"))
    assert "water_level" not in out
    assert "mop_intensity" not in out
    assert out["fan_speed"] == "Max"


def test_cap_3_vacuum_mop_keeps_everything():
    """[CAP-3] Both halves apply, so nothing is inert. The guard against a fix that
    "works" by dropping too much."""
    out = drop_inert(_captured("vacuum_mop"))
    assert out["fan_speed"] == "Max"
    assert out["water_level"] == "High"
    assert out["mop_intensity"] == "Max"


@pytest.mark.parametrize("mode", ["", "unknown", "Vacuum and mop", "Mopping after sweeping"])
def test_cap_4_an_unrecognised_mode_drops_nothing(mode):
    """[CAP-4] Never guess. An unknown mode means we cannot say what is inert, and
    discarding a real measurement is worse than keeping an inert one.

    "Vacuum and mop" is included deliberately: it canonicalises to vacuum_mop, so it
    must keep everything rather than falling through to the drop-nothing path by
    accident — the assertion is the same either way, but the reason differs.
    """
    out = drop_inert(_captured(mode))
    assert out["fan_speed"] == "Max"
    assert out["water_level"] == "High"


def test_cap_5_the_two_mop_labels_are_dropped_together():
    """[CAP-5] water_level and mop_intensity are ONE device value under two label
    sets — upstream maps Quiet/Automatic/Max onto Low/Medium/High. Dropping one and
    keeping the other would leave a phantom reading of the same inert setting."""
    out = drop_inert(_captured("vacuum"))
    assert "water_level" not in out and "mop_intensity" not in out


def test_cap_6_mutates_and_returns_the_same_dict():
    """[CAP-6] The caller uses the return value; pinning identity so a future refactor
    to a copy does not silently leave the caller with the un-filtered original."""
    captured = _captured("mop")
    assert drop_inert(captured) is captured
