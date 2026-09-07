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

## What the card contains — RULED 2026-09-06, and applied

Chris's rule, with his worked example:

> The parts are a module. The steps to get to both are the same. **But we can ignore the
> bin except where access is needed.**
>
> ```
> open top / remove dust bin / remove filter from dust bin /
> wash filter with clean water / allow to completely dry /
> reinstall filter to dust bin / reinstall dust bin / close top cover
> ```

So the test per step is not which part it **names**, it is what it **does**:

| step does | verdict |
|---|---|
| on the path to the filter (open the box, take the filter out, refit, close) | **KEEP**, even though it says "dust box" |
| services the box itself (empty, rinse the box, dry the box, clean the intake) | **DROP** |
| both in one sentence | **REWORD** down to the filter half |

Note his example has no "tip the debris out" step: emptying the bin is use, not filter
maintenance, so the button-press-to-empty keys go too even though they read like access.

**Applied 2026-09-06 across 463 blocks** — 645 placements dropped over 14 keys
(`bin.empty` 333, `bin.tip_out` 94, `bin.box_dry_fully` 88, `bin.rinse_box_only` 80, …)
and 666 reworded over 8 (`bin.rinse` 332 → `filter.rinse_only`, `bin.dry_fully` 317 →
`filter.dry_fully`, …). Only two new phrases were needed — `filter.holder_rinse_only` and
`filter.holder_dry_gate` — because the reword targets already existed and were already
translated.

### ⚠ I argued this could NOT be split. That was wrong.

I wrote that `bin.rinse` ("Rinse the dust box **and** filter with clean water", 209 users)
was the clincher for keeping the two together — *"the vocabulary itself refuses to
separate them"*. Chris: **"the hell we cant split it. bin.rinse dies becomes filter rinse
with the dustbin section gone."** He is right. A welded sentence is not evidence that two
facts are inseparable; it is an **undecomposed key**, which is the whole point of
[`DESIGN-key-decomposition.md`](DESIGN-key-decomposition.md). `bin.rinse` maps straight
onto `filter.rinse_only`, which already existed with 52 users. The reword cost zero new
keys and zero translation for the two biggest cases.

The lesson generalises: **"these keys are welded" is a statement about the phrase table,
never about the hardware.** Do not use it as an argument for a scope or modelling
decision.

### One family the rule cannot cover: `e5` — EXEMPT

`e5`'s packet has **no filter component at all** (dustbin, clean_water_tank, mop_cloth,
side_brush, sensor, charging_contacts). Its "filter" card was built entirely from
dust-box steps, so the strip leaves nothing. It is the **only** family of 279 in that
state, and it is exempt and untouched pending a decision: either e5 gets no filter card,
or its dust-box procedure stands in for one. 56 other blocks also went empty under the
strip, but all 56 are shadow `dustbin` blocks whose family has its own filter block — they
do not ship, so they do not matter.

## Open question this raises (not a defect, a labelling call)

The card is keyed `filter` and titled accordingly. After the strip its body is filter work
plus the shared access path, so the mismatch is much smaller than it was — but the card
still opens by taking the dust box out. Whether the heading should say so is a
**labelling** decision, and it lands on the same surface as
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
