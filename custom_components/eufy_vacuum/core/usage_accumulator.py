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


#: Duration units a source may publish, as a multiplier INTO HOURS.
#:
#: MEASURED, not assumed: robin's lifetime clock reads 409 with `unit_of_measurement: min`
#: while alfred's and ivy's read hours. Folding the raw number booked 5 MINUTES of cleaning as
#: 5 HOURS -- a 60x overcount, seen live on the first real run. Same family as the ft2/m2 split
#: already in the notes: the number is right and the unit is the thing that differs.
#:
#: An unknown or absent unit is treated as HOURS, because every maintenance interval in this
#: system is stated in hours and that is the only assumption that leaves a correct source
#: correct. A wrong guess here is visible immediately (60x is not subtle), which is the kind of
#: wrongness worth defaulting into.
UNIT_TO_HOURS: dict[str, float] = {
    "h": 1.0, "hr": 1.0, "hrs": 1.0, "hour": 1.0, "hours": 1.0,
    "min": 1.0 / 60.0, "mins": 1.0 / 60.0, "minute": 1.0 / 60.0, "minutes": 1.0 / 60.0,
    "s": 1.0 / 3600.0, "sec": 1.0 / 3600.0, "secs": 1.0 / 3600.0,
    "second": 1.0 / 3600.0, "seconds": 1.0 / 3600.0,
    "d": 24.0, "day": 24.0, "days": 24.0,
}


def to_hours(value: Any, unit: Any) -> float | None:
    """A reading in the source's own unit -> the same reading in HOURS.

    ⚠ APPLY THIS TO A STATE, NEVER TO THE USAGE ATTRIBUTE. `unit_of_measurement` describes the
    entity's STATE; the accumulator attribute is `usage_hours` and is hours by its own name. On
    alfred the two happen to agree, so a bug here would not have shown up there -- which is
    exactly why it is written down rather than left to coincidence.

    CHANGING A SOURCE'S UNIT NEEDS NO MIGRATION. An old baseline stored in minutes (414) against
    a new reading in hours (6.9) is a move AGAINST expectation, so `observe` re-baselines and
    books nothing. One reading is spent and the counter is correct from the next one -- the same
    branch that absorbs a device reset absorbs this.
    """
    number = _number(value)
    if number is None:
        return None
    return number * UNIT_TO_HOURS.get(str(unit or "").strip().lower(), 1.0)


def learned_direction(
    declared: str | None, moves_up: int, moves_down: int
) -> str | None:
    """Which way this source counts, or None while we still have no idea.

    A DECLARATION WINS WHEN THERE IS ONE. HA's `state_class` says it outright for some
    integrations — `total` / `total_increasing` is a counter that rises, `measurement` on a
    remaining-hours sensor is one that falls. Roborock declares nothing on any sensor, so that
    signal covers two brands of three and cannot be the whole rule.

    OTHERWISE THE SOURCE TELLS US ITSELF, because of what a reset is. During ordinary use a
    counter only ever moves ONE way; a reset is a single move the other way, and it returns the
    counter to an extreme — measured on Chris's own machines, both shapes, same day:

        robin  side_brush  state 193 ->  200   a new HIGH (its full life)   countdown
        alfred rolling_brush state 314 -> 360  a new HIGH (total_life)      countdown
        alfred rolling_brush usage  46 ->   0  a new LOW                    count-up

    THE MAJORITY IS THE SHAPE. Usage is frequent and small, a reset is rare and large, so the
    direction moved more OFTEN is the direction of use. That makes the rule self-correcting: if
    the very first movement we ever see happens to be a reset, the next two ordinary ticks
    outvote it. Locking the direction on the first movement would be right almost always and
    wrong silently and permanently the rest of the time.

    ⚠ IT IDENTIFIES THE SOURCE, NOT THE BRAND OR THE DEVICE. Chris: "even if we assume both
    sides were not published." Alfred's sensor publishes a falling STATE and a rising ATTRIBUTE;
    watch either alone and this names that one correctly. Which is what the design needs, since
    the user picks the source.
    """
    if declared in (UP, DOWN):
        return declared
    if moves_up == 0 and moves_down == 0:
        return None
    if moves_up == moves_down:
        return None
    return UP if moves_up > moves_down else DOWN


def observe(
    reading: Any,
    *,
    baseline: float | None,
    total: float,
    direction: str | None,
    max_delta_hours: float | None = MAX_SINGLE_DELTA_HOURS,
) -> dict[str, Any]:
    """Fold one reading into ``(baseline, total)``. Pure — no clock, no storage, no entity.

    Returns ``{"baseline", "total", "counted", "rejected", "moved"}``:
      counted   hours added by THIS reading (0.0 whenever nothing was booked)
      rejected  the delta that breached the cap, else None — the caller says so out loud
      moved     UP / DOWN / None — which way this reading went, for the caller's tally

    ``direction=None`` means WE DO NOT KNOW YET: the source's shape has not been declared and it
    has not moved enough for us to tell. Nothing is booked while that is true — we only watch,
    report `moved`, and re-baseline. Booking on a guess would be worse than booking late, because
    a wrong guess counts resets as runtime and ignores the real hours, forever and silently.
    Learning costs at most the first couple of movements; see `learned_direction`.
    """
    value = _number(reading)
    if value is None:
        # Not a reading. Not a baseline, not a zero, not a gap — nothing happened.
        return {"baseline": baseline, "total": total, "counted": 0.0,
                "rejected": None, "moved": None}

    if baseline is None:
        # FIRST READING ESTABLISHES THE BASELINE ONLY. Without this a fresh install books
        # `life - remaining` on its first poll, as if every hour already on the part had
        # elapsed while we were watching.
        return {"baseline": value, "total": total, "counted": 0.0,
                "rejected": None, "moved": None}

    moved = None
    if value > baseline:
        moved = UP
    elif value < baseline:
        moved = DOWN

    if direction is None:
        # Watching, not counting. Re-baseline so the NEXT movement is measured from here.
        return {"baseline": value, "total": total, "counted": 0.0,
                "rejected": None, "moved": moved}

    delta = (baseline - value) if direction == DOWN else (value - baseline)

    if delta <= 0:
        # AGAINST EXPECTATION: a reset, a part swap, a re-pair. Count nothing, and MOVE THE
        # BASELINE — skipping the move is what freezes the accumulator forever.
        return {"baseline": value, "total": total, "counted": 0.0,
                "rejected": None, "moved": moved}

    if max_delta_hours is not None and delta > max_delta_hours:
        # Too large to be real. Re-baseline so we recover on the next reading, book nothing,
        # and hand the caller the number so it can be logged rather than silently swallowed.
        return {"baseline": value, "total": total, "counted": 0.0,
                "rejected": delta, "moved": moved}

    return {"baseline": value, "total": total + delta, "counted": delta,
            "rejected": None, "moved": moved}


def declared_direction(state_class: Any, attributes: dict[str, Any] | None,
                       usage_attribute: str) -> str | None:
    """The direction HA itself states, or None when it states nothing.

    A head start, never a requirement. MEASURED ACROSS THE THREE INTEGRATIONS:

        alfred  total_cleaning_time   state_class "total"              -> UP
        robin   total_cleaning_time   state_class "total_increasing"   -> UP
        alfred  *_remaining           state_class "measurement"        -> a falling counter
        ivy     everything            state_class ABSENT               -> nothing

    Roborock publishes no `state_class` on any sensor, so its lifetime clock and its part
    countdowns are indistinguishable by metadata. Anything that REQUIRED this signal would be
    guessing precisely where there is least information — which is why the learning rule above
    is the floor and this is the shortcut.
    """
    if attributes and _number(attributes.get(usage_attribute)) is not None:
        return UP
    sc = str(state_class or "").strip().lower()
    if sc in ("total", "total_increasing"):
        return UP
    if sc == "measurement":
        return DOWN
    return None


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
