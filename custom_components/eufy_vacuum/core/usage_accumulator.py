# -*- coding: utf-8 -*-
"""A reset-detecting usage counter: we own the total, the device owns the reading.

WHY THIS EXISTS. Doc 41 §1 states the rule the framework already lives by — *the device owns
the state and we own a reference to it* — and the countdown half of that was never actually
built. `_consumed_hours` read a countdown as a POINT value (``default_interval_hours - state``),
which is not a counter at all: when a device resets its own consumable, the countdown jumps back
to full, consumed drops toward zero, and the stored snapshot now exceeds it. Clamp 1 then absorbs
the difference and the card reads BRAND NEW. Absorbing a reset is not the same as counting it.

THE RULE, in one block. It is a standard reset-detecting counter:

    read is not a number        -> do nothing at all      (no total, no baseline)
    no baseline yet             -> baseline = read        (accumulate zero)
    moved the EXPECTED way      -> total += |delta|; baseline = read
    moved AGAINST expectation   -> baseline = read        (count NOTHING)

BOTH HALVES OF THE LAST LINE ARE REQUIRED and either alone breaks it:

  * count nothing but do NOT re-baseline -> `baseline` stays at the old value forever, every
    later reading looks like another move against expectation, and the accumulator FREEZES
    permanently after the first reset.
  * re-baseline but DO count it -> the reset itself is booked as runtime.

"Ignore increases" is a plausible-sounding rule that silently dies on its own. The re-baseline is
what makes it work.

DIRECTION IS PER ENTITY, NOT PER BRAND. A countdown falls (roborock, dreame: `*_time_left`); an
accumulator rises (eufy: the `usage_hours` attribute). Doc 41 holds both "without a brand check"
and that stays true here — the caller passes the direction it inferred from the reading itself,
so a brand shipping both shapes still works and no adapter has to declare anything.

WHAT IT IS NOT. Water is not a count, it is a VALUE — a level in a tank, read live. It is a role
(`station_water`), never a maintenance component, and nothing here applies to it.

⚠ THE ONE DIRECTION IT DRIFTS, accepted knowingly. A reset PLUS heavy runtime inside one gap
nets out: if the machine was reset and then ran, and the net movement is still in the expected
direction, only the net is booked. It under-counts, bounded by how long we can go unobserved —
minutes in practice. It fails LOW and SILENT, which is the direction nothing complains about.
"""

from __future__ import annotations

from typing import Any

#: A single reading may never book more than this many hours.
#:
#: THE LONGEST A PART ACTUALLY LASTS, measured: 360 h is the largest device-declared service life
#: seen live (`total_life_hours` on a Eufy filter / rolling brush). A delta is RUNTIME BETWEEN TWO
#: READINGS, so the part's lifespan is the bound that means something.
#:
#: NOT the largest declared interval, which is 720 h (a Eufy sensor's `max_interval_hours`) — that
#: is a USER'S REMINDER CEILING, a different kind of number entirely, and it does not bound how
#: much a machine can run. And NOT an average of the brands: a cap must reject the IMPOSSIBLE, not
#: the unlikely. An average (~150 h) would discard a genuine catch-up after a long outage, which is
#: precisely the case this counter exists to get right.
#:
#: A rejected delta is REPORTED, never absorbed. A sensor that glitches to 0 and back would
#: otherwise book a whole service life in one step and re-baseline, leaving a permanent overcount
#: with nothing to show it happened.
MAX_SINGLE_DELTA_HOURS = 360.0

#: Direction of travel for a healthy reading.
DOWN = "down"   # countdown: hours remaining, falls with use (roborock, dreame)
UP = "up"       # accumulator: hours used, rises with use (eufy's usage_hours attribute)


def _number(value: Any) -> float | None:
    """A reading, or None for anything that is not one.

    ⚠ `unavailable` AND `unknown` LAND HERE, AND THAT IS THE POINT. A countdown goes unavailable
    on every HA restart and whenever the device drops off the network — this is the ordinary
    case, not an exotic one. Coercing it to 0.0 would book a delta the size of the whole
    countdown; treating it as "no value" and then writing a baseline would destroy the reference
    we are counting from. It must touch nothing.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / ±inf
        return None
    return number


def observe(
    reading: Any,
    *,
    baseline: float | None,
    total: float,
    direction: str,
    max_delta_hours: float | None = MAX_SINGLE_DELTA_HOURS,
) -> dict[str, Any]:
    """Fold one reading into ``(baseline, total)``. Pure — no clock, no storage, no entity.

    Returns ``{"baseline", "total", "counted", "rejected"}``:
      counted   hours added by THIS reading (0.0 whenever nothing was booked)
      rejected  the delta that breached the cap, else None — the caller says so out loud

    Every rule in the module docstring is one branch below, in the order it is stated there.
    """
    value = _number(reading)
    if value is None:
        # Not a reading. Not a baseline, not a zero, not a gap — nothing happened.
        return {"baseline": baseline, "total": total, "counted": 0.0, "rejected": None}

    if baseline is None:
        # FIRST READING ESTABLISHES THE BASELINE ONLY. Without this a fresh install books
        # `life - remaining` on its first poll, as if every hour already on the part had
        # elapsed while we were watching.
        return {"baseline": value, "total": total, "counted": 0.0, "rejected": None}

    delta = (baseline - value) if direction == DOWN else (value - baseline)

    if delta <= 0:
        # AGAINST EXPECTATION: a reset, a part swap, a re-pair. Count nothing, and MOVE THE
        # BASELINE — skipping the move is what freezes the accumulator forever.
        return {"baseline": value, "total": total, "counted": 0.0, "rejected": None}

    if max_delta_hours is not None and delta > max_delta_hours:
        # Too large to be real. Re-baseline so we recover on the next reading, book nothing,
        # and hand the caller the number so it can be logged rather than silently swallowed.
        return {"baseline": value, "total": total, "counted": 0.0, "rejected": delta}

    return {"baseline": value, "total": total + delta, "counted": delta, "rejected": None}


def direction_for(state: Any, attributes: dict[str, Any] | None, usage_attribute: str) -> str:
    """Which way a healthy reading moves, inferred from the entity itself.

    An entity publishing the usage attribute is telling us it counts UP; one that publishes only
    a remaining-hours state counts DOWN. This is the same inference `_consumed_hours` has always
    made, kept per-ENTITY on purpose: it is what lets doc 41 hold both ownership models "without
    a brand check", and a brand that ships both shapes still works. A per-adapter declaration
    would be strictly weaker.
    """
    if attributes and _number(attributes.get(usage_attribute)) is not None:
        return UP
    _ = state
    return DOWN
