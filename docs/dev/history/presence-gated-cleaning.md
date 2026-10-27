# Presence-Gated Cleaning — proposed, specified, ruled out

**2026-09-15.** Proposed as a feature, specified in full, and **ruled out the same day.**
Dated and left alone.

This is here because the standard says it should be: *a retired approach with no recorded
reason gets proposed again in six months, confidently.* It was proposed this time from a
survey of [botts7/dreame-scheduler](https://github.com/botts7/dreame-scheduler), whose
presence gating is its headline feature — so the next survey of a neighbouring project
will surface it again. Read this before re-scoping it.

---

## 1. What was proposed

Gate cleaning on presence: do not start while anyone is home, stop if someone arrives, and
resume once the house is empty again — with a dwell so the robot does not launch the moment
the door closes.

## 2. What the investigation actually found

Two things, both of which shrank the proposal before it was rejected.

**The mid-run half already ships.** `listeners/path_blockers.py` re-evaluates blocker rules
against live entity state during a run and supports three escalation levels via
`path_block_action`: `event_only`, `pause_and_event`, and `cancel_and_event` — the last
re-checking that the rule still matches against a *known* state before the irreversible
action. [06-room-rules](../../advanced/06-room-rules.md) uses "someone comes home" as its
own worked example. Point a blocker rule at a presence entity and the stopping half exists
today.

**The starting half is already documented, and already names this case.**
[04-automation-examples §9 — Pre-Run Conditions](../../advanced/04-automation-examples.md)
is the standing doctrine: *"Home Assistant owns whether and when a job starts … they're
conditions on your start automation."* Its customization points list **"a 'nobody home'
presence check"** as a swap-in condition, beside an energy-price sensor and a `sun`
condition.

So the feature was never the gap it appeared to be. What remained was only the handling of
unreliable geofence data.

## 3. The model that was specified

Recorded because the thinking is sound and should not be redone from scratch if the
constraints ever change. It is **not** a plan.

> A weak state transition requires persistence. Stronger evidence can settle the transition
> immediately.

- All **required** people outside the geofence before an away timer starts.
- Away dwell: user-configurable.
- Geofence re-entry is **weak evidence and resets nothing.** It starts a second, separately
  configurable *return* dwell. Leave again before it expires and it is GPS wiggle — the
  original away timer is **preserved**. Stay the full dwell and the return is confirmed.
- A **strong signal** — a garage door, an exterior door sensor, any entity the user deems
  definitive — bypasses the return dwell. **Combinatory, never standalone: presence AND
  signal.** It corroborates a re-entry; it cannot manufacture one.
- **Restarts may kill an in-flight timer and that is accepted.** Elapsed time is not
  persisted; at best an incomplete timer restarts from zero if its conditions still hold.

## 4. Why it was ruled out

**It is nine decisions for one outcome.** Required-people set · away dwell · return dwell ·
which entities are strong signals · which state of each · the signal's arming window ·
what an `unavailable` tracker means · `path_block_action` level · per-room rules. Several
have no defensible default, and the failures are silent in both directions: a wrong dwell
either never cleans or cleans while someone is home.

Delivering that means either **making those decisions for people** or **walking them
through a wizard** — for the single outcome *don't clean while I'm home*.

**And every one of those nine decisions is a Home Assistant problem.** Timers, template
sensors, `for:` on any condition, trigger-based sensors, automations: HA has all of it, the
user already knows it, and it does it better. Building it here means **writing Home
Assistant inside Vacuum Agent**, and then owning the support load for geofence flakiness
that was never ours.

⚠ **An intermediate position was floated and is also rejected:** adding a `for:` duration
to blocker rules, as a small general capability with presence as one consumer. It is
rejected for the same reason and a sharper one — a rule points at an *entity*, and an
entity can already carry its own dwell. Make the sensor smart in HA; the rule stays one
question, *does this entity match this state*. Adding dwell to the rule engine duplicates
a primitive that already exists one layer up.

## 5. What the answer is instead

[04-automation-examples §9](../../advanced/04-automation-examples.md). An HA automation
with whatever presence logic the user wants, calling `eufy_vacuum.start_run_profile`, with
`path_block_action` on the room rules if they also want mid-run stopping.

**The one thing §9 does not say**, and the only residue of this whole investigation worth
carrying forward: a bare `person` state check flaps at the geofence boundary, and the
debounce for it is one property — `delay_off` on a template `binary_sensor`. That is a
sentence in §9's customization points if anyone wants it, not a feature.

## 6. What would have to change to reopen this

Not "a user asked for it" — §5 already serves that user. It would take evidence that the
**HA-side recipe cannot express** something people actually need, which the model in §3 is
not evidence of: every clause in it is buildable in HA today by someone willing to write
five automations and two timer helpers. The question is whether *we* should own it, and
that was answered no.
