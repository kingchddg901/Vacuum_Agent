"""Proof RP-042 (RF-36 part 1) — an unreadable battery is reported as 0 %.

get_battery_level is annotated ``-> int``, so it cannot express "unknown" and invents a
reading instead. When the adapter's battery sensor is unavailable/unknown, _safe_int
returns -1 and the code falls through to the vacuum entity, whose missing battery_level
attribute then defaults to 0 (core/charging.py:56-64). A dropout becomes indistinguishable
from a flat pack, and 0 is the most damaging value in this domain because every consumer
treats it as empty.

RP-006's defect class exactly — read_json's lying default — in a different file.

TWO cases, matching the packet's expected_before/after:

  1. THE READING. The dropout matrix: sensor unavailable / unknown / absent, crossed with
     the vacuum attribute present / absent. Every row where nothing is readable must
     return None, not 0. The row where the attribute IS present is the control: the
     fallback is legitimate there and must keep working.

  2. THE SESSION. A recorder handed that 0 writes a session ending at zero. An
     end_battery of 0 whose start_battery is far above it is not an observation. Per the
     packet, the session must be recorded as ENDED-UNKNOWN. Landing case 1 stops new bad
     rows; the six existing ones age out of the 50-entry ring on their own.

DELIBERATELY ABSENT: a drain-accumulator case. The packet forbids it, and it is worth
recording why, because an earlier version of RP-042 claimed the dropouts inflated
Alfred's cycle counter ~285 %. That was FABRICATED — reasoned from the accumulator code
to the impossible history rows without checking the guard sitting between them.
battery/manager.py:526 wraps BOTH the drain accumulator and the rate metrics in
``if abs(raw_delta) <= MAX_DELTA_PCT`` (3.0), symmetrically, so the 98-point flip is
rejected in both directions. Measured on the live install: alfred's samples.jsonl holds
592 samples, 42 carry rejected_delta_pct, and ALL 42 have |delta| > 50. Every dropout
was caught; none leaked. A drain case would therefore report the same shape before AND
after and would prove nothing — worse, it would re-certify the fabricated claim.

Nor may the fix carry the previous reading forward: a carried-forward reading is the
same lie as the 0, just quieter. Case 1 asserts None specifically, not "not 0".

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_battery_unknown.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import (   # noqa: E402
    register_adapter_config,
)
from custom_components.eufy_vacuum.core.charging import get_battery_level   # noqa: E402

VAC = "vacuum.alfred"
BATT = "sensor.alfred_battery"


def _hass_with(sensor_state, *, attribute, vacuum_present=True):
    """A hass whose battery sensor reads `sensor_state` (None = entity absent) and
    whose vacuum carries `attribute` as battery_level (None = attribute absent).
    `vacuum_present=False` removes the vacuum entity itself — a distinct branch
    (charging.py `if vacuum_state is None: return 0`), not a duplicate of the others.

    The noop_* engine declarations are inert scaffolding: without them the registry
    logs three fallback warnings per registration and drowns the verdict. They select
    no behaviour this proof exercises.
    """
    hass = H.make_hass()
    register_adapter_config(VAC, {
        "entities": {"battery": BATT},
        "mapping": {"segmenter_engine": "noop_fallback"},
        "job_segmenter": {"engine": "noop_job_fallback"},
        "room_attribution": {"engine": "noop_room_attribution"},
    })
    if sensor_state is not None:
        hass.states.async_set(BATT, sensor_state)
    if vacuum_present:
        hass.states.async_set(VAC, "docked", {} if attribute is None
                              else {"battery_level": attribute})
    return hass


# (label, sensor state, vacuum attribute, vacuum present) — nothing readable in any row.
MATRIX = [
    ("sensor unavailable, no attribute", "unavailable", None, True),
    ("sensor unknown, no attribute", "unknown", None, True),
    ("sensor entity absent, no attribute", None, None, True),
    ("sensor unavailable, vacuum entity absent too", "unavailable", None, False),
]
CONTROL = ("sensor unavailable, vacuum attribute IS readable", "unavailable", 64)


def case_unreadable_reading(proof: H.Proof) -> None:
    results = {
        label: get_battery_level(_hass_with(s, attribute=a, vacuum_present=v), VAC)
        for label, s, a, v in MATRIX
    }
    label_c, s_c, a_c = CONTROL
    control = get_battery_level(_hass_with(s_c, attribute=a_c), VAC)

    proof.case(
        "battery unreadable by every route (4 dropout shapes)",
        before=all(v == 0 for v in results.values()) and control == 64,
        before_msg="level=0 on an unreadable sensor — a dropout is indistinguishable "
                   "from a flat pack, and every consumer reads 0 as empty",
        # None specifically: the packet forbids carrying the previous reading forward,
        # which would be the same lie told more quietly.
        after=all(v is None for v in results.values()) and control == 64,
        after_msg="level=None on an unreadable sensor; the legitimate attribute "
                  "fallback still returns its real value",
        detail=" · ".join(f"{k}={v!r}" for k, v in results.items())
        + f" · CONTROL {label_c}={control!r}",
    )


def case_session_ended_at_zero(proof: H.Proof) -> None:
    """The recorder's view: what a dropout writes into the session ring."""
    reading = get_battery_level(_hass_with("unavailable", attribute=None), VAC)

    # Model the recorder's decision without importing its whole update path: a session
    # opened at 85 % closes on whatever get_battery_level last returned.
    session = {"start_battery": 85, "end_battery": reading}
    ended_at_zero = session["end_battery"] == 0
    ended_unknown = session["end_battery"] is None

    proof.case(
        "a session opened at 85 % closes while the battery is unreadable",
        before=ended_at_zero,
        before_msg="session recorded as ended-at-zero — an 85->0 row that never "
                   "happened, indistinguishable in the ring from a genuine full drain",
        after=ended_unknown,
        after_msg="session recorded as ended-unknown — the ring keeps the row but "
                  "does not claim a reading nobody took",
        detail=f"start_battery=85 · end_battery={session['end_battery']!r} "
               f"(get_battery_level returned {reading!r})",
    )


def main() -> None:
    proof = H.Proof("RP-042", "an unreadable battery must not be reported as 0 %")
    case_unreadable_reading(proof)
    case_session_ended_at_zero(proof)
    proof.finish()


H.run(main)
