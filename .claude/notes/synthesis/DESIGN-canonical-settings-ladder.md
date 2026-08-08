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

## CORRECTION (Chris, 2026-08-07): more of these are variables than I classified

I split the settings into ordinal / categorical and got two of them wrong by
reading the WORD instead of the mechanism — the exact error this whole campaign
is about.

**`clean_intensity` is ORDINAL.** Its axis is PATH SPACING, not a set of modes:
`Deep` = closest passes, `Narrow` = medium path, `Quick` = wide path. One ordered
axis, so it clamps meaningfully. "Narrow" merely SOUNDS like a different
dimension.

**`path_type` IS `clean_intensity` — the same concept under two canonical field
names.** Verified: Roborock declares `path_type: "wide" / "narrow"`
(`adapters/roborock/vocabulary.py`), Eufy declares
`clean_intensity: "Quick" / "Narrow" / "Deep"`. Same physical property — pass
density — split into two fields purely by which brand's word arrived first.
`"narrow"` appears in BOTH vocabularies. And `path_type` has no options list in
`config_schema.py` at all (only `fan_speed`, `water_level`, `clean_mode` and
`clean_intensity` have one), so it is undeclared free-form strings.

This is both brands hiding as function at once, and it means the canonicalization
MERGES two fields rather than re-encoding six. Six canonical per-room fields
become five.

**`clean_mode` can carry slot numbers too** (Chris: 0 mop, 1 vacuum, 2 vacuum+mop,
4 vacuum-after-mop — note the deliberately unused 3). So the slot mechanism is
universal: every setting with a variable gets numbered rungs, unoccupied ones
null. What is NOT universal is the fallback, below.

## Decision 1 — the fallback rule follows the setting's KIND

The ladder generalizes to every setting with a variable, but "nearest rung" only
means something for an ORDERED one. The six canonical per-room fields split three
ways:

## REFINEMENT — separate SLOT SPACE from RESOLUTION POLICY

My framing derived the fallback FROM the setting's kind, which forced two
different mechanisms. The cleaner cut (Chris + GPT, 2026-08-07) is that
**"represented as slots" and "semantically ordinal" are different properties**,
and each setting declares them independently:

1. **Slot space** — what canonical intents exist.
2. **Resolution policy** — what to do when the provider does not occupy the
   requested slot.

`clean_mode` shows why they must separate. It represents perfectly well as slots
(0 mop, 1 vacuum, 2 vacuum+mop, 4 vacuum-after-mop) — a provider-independent
choice space — but those numbers carry no magnitude: mode 2 is not "more" than
mode 1, and 4 is not "nearest" to 2. So it uses the same slot machinery as
everything else and simply declares a different resolver.

| concept | slot space | resolution |
|---|---|---|
| fan speed | ordered rungs | nearest supported |
| water level | ordered rungs | nearest supported |
| pass count | numeric / ordered | clamp to supported range |
| path density (`clean_intensity`) | ordered rungs | nearest supported |
| clean mode | enumerated slots | **exact, else the provider's declared default** |
| edge mopping | boolean | capability gate / off |

One constraint survives from the earlier "directional fallback" note, and it must
be stated rather than assumed: **the declared default for `clean_mode` must be a
DRY mode.** "Exact, else provider default" is only safe if that default cannot be
wet — otherwise an adapter declaring `mop` as its default resolves an
unsupported intent into water on carpet, which is a wrong physical ACTION rather
than an omitted one. The safety property moves from the resolver into a
constraint on the declaration, which is a better place for it.

## The third leak class — brands hiding as SCHEMA

`path_type` vs `clean_intensity` is not vocabulary leakage and not behavioural
fossilization. It is a third thing:

> **Eufy called the physical axis `clean_intensity`. Roborock called it
> `path_type`. VA preserved BOTH NAMES AS SEPARATE CONCEPTS.**

One physical property — distance between cleaning passes — became two canonical
fields because two brands named it differently and neither name was ever
reconciled. That is a first-brand accretion scar in the SCHEMA, and no amount of
value-mapping fixes it, because the duplication is at the concept level.

The slot/resolver design removes both classes at once: core owns the abstract
intent space, adapters declare which points they occupy and how those points
translate. Core stops needing to know whether the provider calls rung 2 "Quick",
"Wide", "Fast", or `17`.

**Sequencing, deliberately conservative:** do NOT rename 49 consumers. The
canonical model should carry ONE axis (`path_density` / `pass_spacing`, or keep
`clean_intensity` for compatibility), with `path_type` demoted to a
provider-facing representation rather than an independent concept. The rename is
optional; the reconciliation is not.

---

Every setting gets numbered rungs. The FALLBACK differs, and for one of them it
is a safety rule rather than a distance rule:

| setting | rungs | unmatched resolves to |
|---|---|---|
| `fan_speed` | ordinal (Quiet → Max) | nearest occupied rung |
| `water_level` | ordinal (Low → High) | nearest occupied rung |
| `clean_passes` / repeats | ordinal | clamped into range |
| `clean_intensity` **(absorbs `path_type`)** | ordinal — pass density: deep/closest → quick/wide | nearest occupied rung |
| `clean_mode` | slots: 0 mop · 1 vacuum · 2 vacuum+mop · 4 vacuum-after-mop | **nearest DRY rung — never toward wet** |
| `edge_mopping` | boolean | capability-gated off |

**`clean_mode`'s fallback is directional, not nearest.** The slots are orderable,
but the risk is not symmetric: falling from `vacuum` down to `mop` puts water on a
carpet — a wrong PHYSICAL ACTION. Falling from `mop` up to `vacuum` merely
under-cleans a hard floor. So unmatched must resolve toward the DRY end, and a
brand with no dry mode at all should refuse rather than substitute.

That asymmetry is why "declare the kind and derive the fallback" is not quite
enough on its own: `clean_mode` needs a stated safe direction, not just a
distance metric. It is the one place in this design where the correct answer is
about consequences rather than about representation.

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
