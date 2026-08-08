# DESIGN — canonical settings ladder (kills the vocabulary fossil at the root)

**Status: DESIGNED, NOT STARTED.** Chris's design, worked out 2026-08-07 in
conversation. Belongs to the adapter-boundary sweep's FINDING BATCH — it is the
repair for the seeded `profiles.room_profiles` fossil, generalized. Nothing is
built; this records the shape and the two decisions that were made along the way.

## The defect

Each brand declares its own `fan_speed_options`, so there is no universal
canonical set — but `BUILT_IN_ROOM_PROFILES` has to put SOMETHING in the default
profile, and what it puts there is **Eufy's words** (`Boost`, `Max`). Eufy was
first, so the framework catalog is Eufy's catalog.

A brand that omits its own block inherits them, and the failure is not cosmetic:
a room stores `fan_speed: "Max"`, the brand's declared options never contain it,
the card's chip rows match nothing, and `per_room_live_settings` filters the value
out — so **no suction is applied at all**. That is the Roborock incident recorded
in dev doc 21 §7, and it is predicted to recur for Dreame.

## The fix — a VARIABLE, not a literal

Core stops storing a brand word. It stores an INTENT that each adapter resolves
against its own ordered options:

- a fixed **ladder** of canonical rungs in core;
- each adapter declares **which rungs it occupies** and what each resolves to;
- **unoccupied rungs are `null`** — the brand does not have that level;
- a stored room holds the **rung**, not the resolved value.

Storing the rung is what makes a brand switch survive: a room set to "the top
rung" stays on the top rung and re-resolves, instead of becoming a stale `"Max"`
that the new brand's options do not contain.

**`null` for "this brand lacks it" is an existing idiom, not a new invention.**
`DreameSegmentEngine` already sets `field_name: null` for fields Dreame does not
accept. This extends the same mechanism from FIELDS down to LEVELS.

## Decision 1 — the fallback rule follows the setting's KIND

The ladder generalizes to every setting with a variable, but "nearest rung" only
means something for an ORDERED one. The six canonical per-room fields split three
ways:

| setting | kind | unmatched resolves to |
|---|---|---|
| `fan_speed` | ordinal | nearest occupied rung |
| `water_level` | ordinal | nearest occupied rung |
| `clean_passes` / repeats | ordinal | clamped into range |
| `clean_mode` (vacuum / mop / vacuum_mop) | categorical | the brand's declared default |
| `clean_intensity` (Quick / Narrow / Deep) | categorical — `Narrow` is path WIDTH, not a level | the brand's declared default |
| `path_type` | categorical | the brand's declared default |
| `edge_mopping` | boolean | capability-gated off |

**Clamping a categorical is worse than the bug being fixed.** Clamp `mop` to its
"nearest" neighbour and a mop job dry-runs on carpet — a physical wrong action,
where the current defect is merely an omitted one. So each setting declares its
kind, and the fallback follows from the kind rather than from one global rule.

## Decision 2 — unmatched CLAMPS, it never DROPS

Today an unmatched value is silently dropped, and that drop IS the incident.
`rooms/room_defaults.py:15` documents the behaviour and line 17 states outright
that the filter exists **as a workaround for this exact default**.

Two consequences:

1. `null` must mean *this brand lacks this level*, never *send nothing*.
2. **The workaround retires with the fossil.** That filter's only reason to exist
   is one brand's vocabulary being the default. Leave it in place after the root
   is fixed and it becomes an orphan that silently swallows legitimately
   unmatched values forever — so the NEXT occurrence would be invisible for
   exactly the reason the last one was. It is also itself a small instance of
   Eufy-hiding-as-function: core carrying a filter that exists only because the
   default is Eufy's.

## Open — learning keys must RESOLVE, not store the rung

`learning/utils.py:157` folds `fan_speed` into the settings signature and
`learning/manager.py:170` lists it among the estimate keys. If a room stores the
rung and learning keys on the rung, a 4-rung brand's top and a 6-rung brand's top
share an estimate bucket — and they are not the same suction, so the runtime
prediction is wrong.

**Symbolic for stored intent; resolved for estimate keys and for the wire.**

## Scope note

Deliberately NOT the same thing as canonicalizing the wire representation
everywhere. That would touch 25 python + 24 frontend files and migrate persisted
learning history. This changes the DEFAULT CATALOG, the resolution point, and the
readers of defaults. Much smaller, and it removes the fossil CLASS rather than
the one instance.
