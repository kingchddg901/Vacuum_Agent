# FINDING (live, 2026-08-02) — a DOCK fault zeroes a productive run's cleaning time

**Found by hardware observation, not audit. Not yet a packet.**
Evidence: `config/eufy_vacuum/learning/alfred/jobs/job_2026-08-01T23-23-35.json`.

## What happened

Alfred cleaned the kitchen for **360 s**, covered **4.0 m²**, used **3 %** battery
and consumed **30.8 ml** of mop water. The record says it cleaned for **zero
seconds**:

    cleaning_time_seconds_raw:  360     <- RP-013f's phase sum. CORRECT.
    total_error_seconds:        455
    cleaning_time_seconds:        0     <- max(0, 360 - 455)

`used_for_learning: true`. The model just learned that 4 m² takes no time.

## The five "errors"

All the same code, all `STATION CLEAN WATER PUMP SHORT` (6013), at job-elapsed
**72, 83, 478, 486, 525 s**. `recovered: false` on every one.

**This is a DOCK fault.** The station's clean-water pump was complaining while the
robot was out on the floor cleaning normally. Nothing about it interrupted the run
— the area, duration, battery draw and water consumption all prove the robot kept
working through it.

## Three distinguishable defects, in order of severity

1. **NO ROBOT-vs-STATION CLASSIFICATION EXISTS.** Grepped: nothing in the codebase
   distinguishes a fault that stops cleaning from one that does not. (`error_source`
   in job_finalizer.py:273 is a callable that reads the error latch — not a
   classification.) A station water-pump complaint and a stuck-on-carpet robot are
   treated identically. This is the root: the other two only bite because of it.
2. **ERROR "TIME" IS A SPAN, NOT MEASURED LOSS.** 455 s ~= first-seen (72 s) to
   last-seen (525 s). Five discrete observations become 453 s of assumed-lost time.
   Even for a genuine robot fault this over-counts whenever errors recur rather than
   persist.
3. **NO FLOOR GUARD ON THE SUBTRACTION.** Subtracting more error-seconds than the
   run contains yields 0 and is written as fact. A result that says "cleaned 4 m² in
   0 s" is self-evidently impossible and should REFUSE — record the raw value and a
   blocker, not a zero. Compare RP-006/RP-042: a computed impossibility must not be
   reported as a confident value.

## Why it matters more than it looks

- `used_for_learning: true` with no `learning_blockers`, so it feeds the model.
- Any dock that develops an intermittent fault silently zeroes EVERY subsequent
  run's cleaning time — the more the dock complains, the less the system believes
  the robot cleaned.
- It masquerades as an RP-013f failure. The earlier Alfred run
  (`job_2026-08-01T22-54-51`) also showed `cleaning_time_seconds: 0`; that was
  read as the counter reset, and this cause was not considered.

## Shape of the fix (NOT authored)

Sibling to RP-013f — same file, same derivation. Classify the error source first
(the error-mining work already captured the full ErrorCode proto, so the
vocabulary to do it may already exist — see project_eufy_error_mining); subtract
only robot-blocking time; and refuse rather than clamp when the arithmetic goes
negative.

Needs a packet before execution. Do NOT let an executor "fix" it by clamping
differently — the clamp is defect 3 of 3, and the cheapest wrong fix.
