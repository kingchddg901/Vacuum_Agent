# The dust box is folded into `filter` — read this before "fixing" an empty filter block

**Status:** settled, and now written into `compose/scope.json`. Chris, 2026-09-06:
*"the filter dustbin is a module."*

## The fact

On these machines the dust box and its filter are **one module** — you cannot service
either without the other. So they get **one card**, and `filter` is the half that has a
purchasable replacement and a counter. `dustbin` is not a shipped component.

The mechanism is one line in `emit_composed.py`:

```python
DONOR = {"filter": "dustbin"}   # a survivor inherits the cadence of the block it absorbed
```

Where a family's `filter` block is empty, its `dustbin` block is emitted **as** the filter
card and inherits its cadence.

## The trap this note exists to stop

```
families whose filter block is EMPTY and whose dustbin block is FULL      81 of 280
emitted blocks with zero steps                                             0 of 1,880
```

Counting empty `filter` blocks in the fixture makes it look like **81 families ship no
filter guide**. They ship the full procedure. Verified 2026-09-06 by loading the emitted
artifact: c9 emits 11 steps, d10s 12, e30_aqua 10 — all sourced from their dustbin block.
I made exactly this wrong call before checking, and reported it to Chris as a defect.

## How much dust-box work is really in the filter card

Not just "take the dust box out". Of 3,282 key placements across the 279 shipped filter
cards:

| what the step does | placements | share |
|---|---|---|
| filter work | 1,222 | 37% |
| other | 800 | 24% |
| reach / refit access | 733 | 22% |
| **dust-box cleaning** | **527** | **16%** |

14 distinct dust-box-cleaning keys, touching **274 of 280 families** — `bin.empty` (198),
`bin.tip_out` (53), `bin.rinse_box_only` (42), `bin.intake_clean`, the fill-and-shake
routine, and others.

The clincher for the module framing is the biggest key of all:

```
bin.rinse   209 users   "Rinse the dust box and filter with clean water."
```

One welded sentence doing both parts. The vocabulary itself refuses to separate them, so
splitting the component would mean splitting 209 sentences that the vendors wrote as one.

## Open question this raises (not a defect, a labelling call)

The card is keyed `filter` and will be titled accordingly, while 16% of its body is
dust-box work and its largest single step names both parts. Whether the user-visible
heading should say something like "Dust box and filter" is a **labelling** decision, and
it lands on the same surface as
[`FINDING-maintenance-heading-not-localized.md`](FINDING-maintenance-heading-not-localized.md)
and [`DECISION-canonical-component-vocab.md`](DECISION-canonical-component-vocab.md).
Not decided here.

## What was wrong in `scope.json`, and is now fixed

`scope.json` calls itself the single source. It had drifted three ways:

1. **`dustbin` was in neither `keep` nor `out`.** Dropped but never recorded as dropped —
   invisible to the file that governs scope, while feeding 81 families' filter cards.
   Now documented in `out` with the DONOR mechanism spelled out.
2. **`mop_cloth` likewise.** Chris's 2026-09-05 ruling is recorded in
   `_changed_2026_09_05.DROPPED`, but it was never added to `out`, so the file did not
   actually say it was cut. Now in `out`.
3. **Three components sat in `keep` AND `out` at once** — `base_station_filter`,
   `fluffing_roller`, `mop_compartment`. All three were cut and then **re-added on
   evidence** the same week (`_changed_2026_09_05.ADDED`); the original cut rationale was
   never swept. Moved to `_out_superseded_2026_09_05`, which keeps the history without
   leaving it live.

**Consequence, and why it mattered:** `emit_composed.py`, `lint_compose.py` and
`vocab_scan.py` all read `keep` only, so **shipping was always correct**. But
`build_domain.py:75` iterates `out` to generate documentation — so the generated doc has
been publishing three shipped components as cut. Retirement is not done until the old
entry is swept; this is that pattern inside a JSON file rather than a markdown one.

`_keep_note` was also stale from the 11-component era: it named `dustbin` as kept and
omitted five components that are (`base_station_filter`, `clean_water_tank`,
`main_brush_anti_tangle`, `washboard`, `washboard_filter`). Rewritten.

## Checks worth re-running

```
keep ∩ out                    must be empty
emitted blocks with 0 steps   must be 0
dustbin + mop_cloth           must appear in out with a reason
```
