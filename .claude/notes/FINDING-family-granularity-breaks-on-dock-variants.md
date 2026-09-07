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


## ⛔ RETRACTION — "families hold multiple products" is NOT a defect

Chris: *"i have 123 manuals that match a naive search on windows in the corpus for the X50."*
Chasing that, I measured 19 families holding more than one base product name and was about to
file it as a structural defect, with `x50` (50 models, incl. **GoVac 800**), `l50` (L10s Ultra
Gen 3, L40 Ultra Gen 2) and `aqua10_ultra_track` (Aqua 10 Pro Track) as the worst offenders.

**All three are named in `upkeep_catalog.py`'s own docstring as PROVEN-CORRECT examples:**

> family is either one of the 16 AUTHORED families or a generic name-derived TIER for the long
> tail. An authored family is assigned on an exact authored-line name match, OR on a reg-code
> (PLATFORM) match proving the same certified machine as an authored line — verify_rebadge_claims.py's
> rule "two names sharing an r-code are the same hardware, proof not inference" (e.g. **GoVac 800
> == X50 on RLX85CE**, **L10s Ultra Gen 3 / L40 Ultra Gen 2 == the L50 machine on RLH41CE**,
> **Aqua 10 Pro Track == Aqua10 Ultra Track on RLR81CE**). Either way measured prose never lands
> on a differently-mopped variant.

And `wash_station`, `wash_station_roller`, `standard` are **deliberate generic TIERS** for the
long tail, explicitly provisional and flagged there for refinement from the DEVICE_INFO
capability table. Not buckets that leaked; buckets by design.

So multiple product NAMES in one family is the system working — reg-code proof collapsing
rebadges. I re-derived a documented design from the corpus and read it as a fault, which is
exactly what the standing rule about scanning the docs before scoping exists to stop. The answer
was in the first 12 lines of the file I had been querying all day.

## ✅ What survives the retraction

The **DOCK-variant** finding above is untouched and is a different axis:

* reg-code matching proves *the same certified machine*. It does **not** say which DOCK that
  machine shipped with, and the water cards depend entirely on the dock.
* `x50_pro` is the demonstration: one robot, one family, and four of its manuals read
  `clean=11 dirty=21 plumb=0` (Tracked, Exclusive) against `clean=0 dirty=0 plumb=11`
  (two Ultra-Thin embedded). Same machine, different plumbing, opposite card needs.
* 34 of 277 families pair a plumbed-named model with a plain one.

So the correct statement is narrow: **a family is a machine, and that is proven; but a family is
not a DOCK, and the water components are dock-level.** The retraction removes the sweeping claim
and leaves the specific one, which is the one that actually bit.


## ✅ RESOLVED with a content index — 8 families, not 34

Chris: *"i have 123 manuals that match a naive search on windows in the corpus for the X50"* and
then *"can you even search this way?"* — pointing at Explorer results containing `kr_2.pdf`,
`kr_3.pdf`, `kr_5.pdf`, `kr_6.pdf`. No model id, no "x50" in the name. **Windows indexes PDF
TEXT; every walk I had run matched FILENAMES.** That is the root cause of the sampling failures
in this note, not a detail.

`tools/build_content_index.py` now indexes all 3,111 PDFs by what the DOCUMENT says it is —
product names, reg codes, CCC numbers, script, and the water/dock signals. **58 seconds on 12
cores** (Chris: *"i have 12 cores use them"*), against two earlier whole-corpus attempts that
timed out at 600s single-threaded.

```
indexed 3111, unreadable 0
scripts   Latin 2236 · CJK 262 · none 186 (image-only) · Cyrillic 146 · Kana 95
          other 63 · Hangul 45 · Arabic 41 · Hebrew 37
join keys product name 1955 rows · reg code 882 · model id 0
```

⚠ **`model_ids` = 0. No manual prints its `dreame.vacuum.*` id** — those are MIoT identifiers,
not document text. The joins are PRODUCT NAME and REG CODE. Any future "find this model's manual"
must use those.

**Reach, measured honestly.** For X50 the content index finds 115 manuals against 43 by a naive
filename string, but my model-id matcher already reached 87 of them, so the true X50 blind spot is
only **5** — four of which are the Korean files Chris supplied by hand. Corpus-wide it is much
worse: **1,400 of 1,955 identifiable manuals (72%) carry no catalog model id in their filename.**

### The per-variant answer

Pulling every manual that NAMES each product, rather than one filename-matched sample:

```
family        manuals   w/ tanks   plumbed   ambiguous
x50_ultra          24          6         1           0    <- I had ruled on the ONE plumbed manual
x50_pro             7          2         3           2    <- matches Chris's five manuals exactly
x50                80         28         4           0
x40                41         24         1           2
s40                12          7         1           0
wash_station       10          1         1           0
x60_master          8          1         1           3
m50_ultra           7          1         2           0
```

**8 families of the 34 name-based candidates have manuals on BOTH sides.** Those are the ones
where one card cannot be right. The other 26 have evidence on one side only, or too few manuals to
say — they are not confirmed splits and should not be treated as such.

That is the actionable set, and it is a quarter the size of the number I gave before the index
existed.


## ✅ THE CUT-OUT RULE — Chris: *"that is why i always had model cut outs in mind"*

His instinct was right and the mechanism already exists: the catalog maps
`model_id -> (name, family)`, so a cut-out is just a different family value on a row.
`s60_pro_disc` and `x50s_pro_master` are cut-outs that were already made. What was missing was
evidence for WHICH models to cut. The content index supplies it.

### First, a methodological correction

Joining manuals by PRODUCT NAME does not resolve dock variants: **every parenthesised variant has
zero manuals.** Documents print the base name on the cover — "X50 Pro" — never
"(Enhanced Ultra-Thin embedded)". So:

> **Product name identifies the ROBOT. Only the model id identifies the SKU (robot x dock).**

That is why the r2580 / r9455 / r9513 / r2502 comparison worked — those were model-id filenames.
Any dock question must join on model id or reg code.

### The rule, tested against every model with manual evidence

```
EMBEDDED name -> PLUMBED    40
EMBEDDED name -> BOTH        1
EMBEDDED name -> TANKS       0     <- ZERO counterexamples
plain name    -> TANKS     122
plain name    -> PLUMBED    17     <- e.g. r9490 "S40", no descriptor, plumbed
plain name    -> BOTH       16
```

**A name carrying "Ultra-Thin" / "embedded" implies PLUMBED — 40 of 41, no counterexamples.**
The converse is FALSE: a plain name implies nothing, since 17 plain-named models are plumbed.
One-directional, and that is exactly how it must be used.

`s40` is the natural experiment — every embedded variant plumbed, every non-embedded one with
tanks, and one plain-named model (`r9490`) plumbed anyway:

```
r2553 S40                                TANKS     r2574 S40 (Platinum Ultra-thin embedded) PLUMBED
r2573 S40 (Platinum Edition)             TANKS     r2576 S40 (Premium Ultra-Thin embedded)  PLUMBED
r2575 S40 (Premium Edition)              TANKS     r9426 S40 (Enhanced Ultra-Thin embedded) PLUMBED
r9430 S40 (Enhanced Edition)             TANKS     r9490 S40                                PLUMBED
```

### What this makes possible

An embedded-named model can be cut out on the NAME alone, with no manual needed — it is plumbed,
so it wants no clean-water tank card and no station used-water tank card. Everything else still
needs per-model evidence.

That converts the dock problem from "read 3,111 manuals" into "cut out the embedded models, then
resolve the remainder", and it is the concrete form of the cut-out Chris has had in mind
throughout.
