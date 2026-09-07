# A family is not one machine: 34 families mix dock configurations

**Status:** MEASURED 2026-09-07. **This is a constraint on the gap work, not a task in itself.**
Chris caught it with five manuals and one sentence: *"remember how we have lots of X50s — they
differ."*

## The catch

I had just told him three families' dirty-water cards should be deleted because their manuals
document no station tank of either kind. Two of the three were wrong, and wrong the same way.

`x50_pro` holds **twelve** models. Scanned side by side:

```
r2580  X50 Pro (Tracked Version)              clean=11  dirty=21  plumb=0     BOTH TANKS
r9455  X50 Pro (Exclusive Edition)            clean=10  dirty=22  plumb=3     BOTH TANKS
r9513  X50 Pro (Enhanced Ultra-Thin embedded) clean=0   dirty=0   plumb=11    PLUMBED
r2502  X50 Pro (Enhanced Ultra-Thin embedded) clean=0   dirty=0   plumb=11    PLUMBED
```

The walk had picked **r2502** — a plumbed variant — as *the* manual for the family, and I read its
zeros as a description of `x50_pro`. Deleting that dirty card would have stripped a card that is
correct for the Tracked and Exclusive editions.

Same for `x50_ultra`, sampled on `r2501` (Enhanced Ultra-Thin embedded).

⚠ I wrote *"a family can span hardware states, so a per-family signature is a SAMPLE not a
description"* into
[`FINDING-the-58-robot-tank-families-walked.md`](FINDING-the-58-robot-tank-families-walked.md)
earlier the same day, then ignored it when the sample said what I expected.

## The scale

```
families in the catalog                                   277
families mixing a plumbed-named model with a plain one     34
```

Plumbed-named = the name carries *Ultra-Thin* / *embedded* / *Automatic Water Supply* /
*Drainage*. This is the three-dock rule from `STATE-dreame-manual-corpus.md` showing through:
一款机型三种配置 — basic water tank, plumbed, ultra-thin plumbed — and **the parenthesised
descriptor is the DOCK, not the robot.** Where a family holds more than one dock, no single card
can be right for all of its models.

Worst offenders: `x50_pro` (5+7), `s30_pro_ultra` (4+6), `s40` (3+6), `s60_pro` (4+1),
`p60` (3+3), `s50` (3+3).

## What it invalidates in the gap worklist

The 2026-09-07 gap walk over the 144 dirty-only families:

| band | n | status |
|---|---|---|
| clean tank mentioned ≥5 → **needs a card** | 122 | **holds.** 10 are mixed-dock, but a plain variant having a tank is exactly why the card is needed |
| clean tank = 0 → "correctly no card, plumbed" | 11 | ⛔ **UNSUPPORTED at family level.** 7 are mixed-dock AND were scanned on a plumbed variant; **0 of the 11 have an all-plumbed model list** |
| dirty card to delete | 3 | `x50_pro`, `x50_ultra` **RETRACTED**. Only `s10` survives |

The 7 suspect: `s10_pro_ultra` `s30_pro_ultra` `wash_station` `x30_pro` `x40_pro` `x50_pro`
`x50_ultra` — every one scanned on an `r2310*` / `r2502` / `r2501` plumbed variant.

`s10` still stands: no dock at all, one hardware state, and independently reconfirmed from a
second pass ([`FINDING-s10-spliced-dirty-tank-and-tiering.md`](FINDING-s10-spliced-dirty-tank-and-tiering.md)).

## ⚠ What this does NOT invalidate

[`FINDING-plumbed-variants-have-no-clean-tank.md`](FINDING-plumbed-variants-have-no-clean-tank.md)
is **correct as written**: a plumbed variant genuinely has no clean-water tank, and the r2310
evidence is sound. The error is entirely in applying a *variant* fact at *family* scope. Do not
retire that note; it is the reason we know what the plumbed variants are.

## The rule that follows

**Before ruling on a family from one manual, check whether its model names span dock
configurations.** If they do, the signature describes one variant and the family needs either
per-variant evidence or a card that is true across all of them. A card can only be family-level
where the family is one dock.

This is the same shape as the `s10` tiering (one product name, three hardware states) and
`s60_pro` (one robot, three docks). It is not a special case; it is the default for 34 families.

## Korean vocabulary, derived while checking this

The two X50s manuals Chris supplied are Korean, which the walker's en+zh patterns score as zero —
the language fault again. Terms extracted from the documents themselves, not guessed:

```
정수 탱크   clean-water tank        오수 탱크   used-water tank
먼지 탱크   dust bin                먼지 봉투   dust bag
스테이션    base station            급배수 / 자동 급수 / 배수구   plumbed supply & drainage
```

Measured with them: **X50s Pro Ultra** clean=12 dirty=13 plumb=2 (both tanks); **X50s Pro Master**
clean=4 dirty=2 plumb=13 (plumbed). Those two are already separate families
(`x50s_pro_master` = r2501p), so the split there is correct. Fold these into `SIGNALS` before the
next walk.
