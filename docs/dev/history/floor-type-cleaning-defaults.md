# ⚠ RETIRED — kept as HISTORY, not as guidance

> **Decided and LANDED 2026-08-17.** The hard-floor water rows are gone from both shipped
> adapters and from the synthetic test brand; the hidden resolution arm is removed;
> `FLOOR_TYPE_FAN_DEFAULTS` is deliberately KEPT (see below). Full suite green.
> This file is the record of why.

Per-surface cleaning defaults: a room's `floor_type` selected a water level and, on carpet,
a fan speed. Retired because **it hid a default from users who did not know it existed.**

## What it was

Each adapter declared a table keyed by floor type:

```python
FLOOR_TYPE_WATER_DEFAULTS = {
    "hardwood": "Low", "laminate": "Low", "tile": "Medium", "marble": "Low",
    "carpet_low_pile": "Off", "carpet_high_pile": "Off",
}
FLOOR_TYPE_FAN_DEFAULTS = {"carpet_low_pile": "Max", "carpet_high_pile": "Standard"}
```

A room with no explicitly-set water level inherited the value for its floor. An explicit
value always won ([RP-8]), so this only ever affected users who had not set one — which is
to say, users who did not know there was one to set.

## Why it was retired

**The consequence was never surfaced.** `floor_type` is collected during setup and its
visible purposes are the map render and the onboarding gate — *"Some enabled rooms still
need a floor type confirmed before cleaning can start."* Not one user-facing string in the
card or the integration says that answering "what is the floor in this room?" will also
choose how wet to mop it. The picker was surfaced; the effect never was.

**It substituted the author's judgement for the user's, invisibly.** `tile: "Medium"` is a
preference. It is not a fact about the machine or the surface, and it was applied to every
room the user had not explicitly configured, with no way to see it had happened.

**A table of preferences has no failure mode.** `hardwood: "Low"` cannot be wrong. No test
could fail, no user could complain about a setting they could not see, and nothing in the
system ever contradicted it. That is why it survived months of active development and a
463-finding audit campaign untouched — and it is the part worth remembering, because the
next plausible-looking table will be invisible for exactly the same reason.

**The audit could not have caught it.** The campaign found `DQ-PAY-2` — that a mop room on
`granite` or `concrete` resolves `water_level` to `""` and shipped that empty string to the
device — because that is a defect *against the table's own intent*. An audit measures code
against what it is trying to do; it structurally cannot ask whether the thing is worth
doing. Two floor types were offered in the picker (`entity_helpers.py`) and appeared in
**neither** brand's table, and the only symptom was a bad wire value.

## What is KEPT, and why

**Carpet keeps both its rules.** Water off, and the fan boost — for two different
reasons, and the difference is the point of this whole note.

**Carpet is water-off, and that stays.** It is the one entry in the table that was never a
preference: it prevents the machine wetting a carpet, which is physical harm and not
recoverable by changing a setting afterwards. The framework already treats it as its single
guarantee — `profiles/room_profiles.py::no_water_value` reads a brand's carpet entry as
*"its no-water word"* — and [[IN40W49E]] keeps that word the brand's, not the framework's.

**`floor_type` itself stays.** It earns its place through the floor-texture map view
(shipped 1.6.0) and the onboarding gate. Only its effect on cleaning settings is retired.

**Carpet fan boost stays too, on a different argument.** Not safety — nothing breaks if a
carpet gets normal suction — but convergence: most vacuums boost on carpet in firmware, so
the framework doing it is meeting an expectation rather than imposing a choice. A rule that
matches what the user would have picked is not the same as a rule they never knew was there.

**No default replaces the table — and the attempt to add one is instructive.** The intent
was "default to low": under-mopping is a re-run, over-mopping is a wet floor. It was written
and then backed out the same day, for two reasons worth keeping.

First, `low` turned out to be a **framework** word, not a brand one — `config_schema.py`
declares the canonical water keys as `low` / `medium` / `high` and brands map their display
strings onto them (`water_level_aliases`: Eufy `"quiet" -> "low"`, `"strong" -> "high"`).
So the framework may say `low`. But that vocabulary is translated **inbound only**, for
learning and water-rate estimation. There is no canonical → brand direction, and Roborock
declares no aliases at all because its words already are the canonical spelling.

Second, the helper written to dodge that — take the first declared `water_level_option`
that is not the no-water word — was wrong twice over: it inferred an ordering no adapter
states, and it read `water_level_options` out of the `room_profiles` catalog, which does
not carry that key. It returned `""` for every brand and a test caught it.

**The ordinal scale this needed was designed and never built.** It exists in miniature at
`dispatch.global_pre_calls[].rank` — `["off", "low", "medium", "high"]`, ascending, index
as the ordinal — declared by Roborock only, because Roborock's settings are device-global
and therefore *had* to be comparable across rooms. Eufy never needed one, so it has none.
The general mechanism got built exactly where a failure forced it, which is the same
lesson as the table itself.

## The prerequisite that already landed

The value gate at `queue/queue_engine.py` — `if supports_water and is_mop and water_level:`
— went in on 2026-08-17 as the fix for `DQ-PAY-2`, matching the `path_type` sibling one line
below it. It is **required before the table can be removed**: strip the non-carpet rows
without it and every hardwood room ships `water_level: ""` to the device, because
`_write_room_field` passes values through unchanged. With it, an undeclared floor means *no
opinion* and the field is simply omitted, which is the behaviour a user-owns-this design
wants. Pinned by `[DE-W1]`/`[DE-W2]`/`[DE-W3]` in `tests/unit/test_dispatch_engines.py`:
`[DE-W1]` an explicitly-empty level is omitted from the wire, `[DE-W2]` carpet still sends
the brand's no-water word — it exists specifically to fail if the gate ever starts
swallowing the guarantee — and `[DE-W3]` an explicit level the user chose still ships.

## What landed

- `adapters/eufy/room_profiles.py` and `adapters/roborock/vocabulary.py` —
  `FLOOR_TYPE_WATER_DEFAULTS` trimmed to the two carpet rows, with a note at each literal.
- `tests/brand_catalogs.py` — the **synthetic** brand trimmed to match. It had its own
  `hardwood` / `tile` rows, so leaving it would have let a retired feature keep passing its
  own tests from a fixture.
- `profiles/room_profiles.py` — the hidden hard-floor arm removed, and the
  mop-with-no-water correction retired with its reasoning at the site.
- `tests/unit/test_profiles_room_profiles.py::[RP-10]` — inverted. It used to assert the
  room took its floor default; it now asserts the room **keeps what it was given**, plus a
  second assertion that fails if a hard-floor row is ever re-added.

## What this fixed that we did not expect

`DQ-PAY-2` was filed as "granite and concrete are missing from the table, so water resolves
to `""`". The deeper cause was the arm itself: it ran whenever neither the room nor the
profile carried a water level and **overwrote whatever the room → profile ladder had already
resolved** — the `Q2/RP-024` comment beside it says exactly that. So a mop room on granite
did not merely lack a default; it had a perfectly good profile value replaced by `""` and
shipped. Removing the arm closes that path completely, and the queue-engine value gate now
covers only the genuine residue: a room, a profile and a brand that all decline to say.

That is why `[DE-W1]` had to be rewritten to construct the empty case explicitly. Granite
had stopped manufacturing it.
- `FLOOR_TYPE_FAN_DEFAULTS` (both) — **KEPT, ruled 2026-08-17.** It looks like the same
  shape as the water table and is not. Boosting suction on carpet is what most vacuums do
  natively, so it matches what the machine and the user already expect rather than
  substituting one person's preference for theirs. That is the whole distinction: the
  hard-floor water rows were an opinion nobody else held, and carpet fan boost is the
  convergent default. Do not retire it by applying the water reasoning mechanically.
- The new single low-water default needs a home. It is framework-level policy rather than
  brand vocabulary, so it must not become a fifth literal in core — see [[IN40W49E]].
- **Existing users:** rooms with a stored `water_level` are untouched (explicit always won).
  A user who never set one and has been silently receiving `Low` on hardwood will stop.
  That is a change newly activating over existing data, so enumerate it before shipping
  rather than after — the shape that nearly cost a real room in `SETUP-REJ-2`.
