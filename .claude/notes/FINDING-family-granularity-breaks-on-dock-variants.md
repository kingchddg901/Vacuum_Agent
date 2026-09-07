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


## "Master" as a second cut-out flag — Chris: *"master was the flag for some plumbed editions"*

Right, but narrower than the word. Tested the same way as the embedded rule:

```
MASTER-named models with manual evidence: 14
   have a clean tank            10
   plumbed, no clean tank        4
```

Of the 4 plumbed, **two are already explained by "embedded"** (`Clean Master X60 Pro Steam
(Ultra-Thin embedded)`, `X60 Master (Ultimate Ultra-Thin embedded)`). The two that Master
genuinely flags are **`Master Pro` (r2310)** and **`Master One` (r2310a)** — where Master is the
PRODUCT NAME, not a suffix.

Every `<Model> Master` — X30/X40/X50/X60 Master, X50 Pro Master, X50s Pro Master — **has a clean
tank**. So the flag is not the word.

### What it actually is: the r2310 series

```
r2310   Master Pro                          c=0 d=0 p=2
r2310a  Master One                          c=0 d=0 p=2
r2310b  S10 Pro Ultra (Ultra-Thin embedded) c=0 d=0 p=2
r2310d  S30 Pro Ultra (Ultra-Thin embedded) c=0 d=0 p=3
r2310e  X40 Pro (Ultra-Thin embedded)       c=0 d=0 p=3
r2310f  S20 Pro (Ultra-Thin embedded)       c=0 d=0 p=3
r2310g  X30 Pro (Ultra-Thin embedded)       c=0 d=0 p=3

7 of 7 have manual evidence; 7 of 7 have clean_tank == 0
```

**The r2310 series IS the plumbed / ultra-thin platform.** Five of its members say so in their
name; `Master Pro` and `Master One` are the two flagship names where the marketing name replaced
the descriptor. That is precisely Chris's point, and it makes them cut-outs the name rule alone
would miss.

The contrast set confirms it is the platform and not the name: outside r2310, the same products
(`S30 Pro Ultra`, `X40 Pro`, `X30 Pro`) show `p=0` unless they carry "Ultra-Thin embedded".

### Cut-out flags, consolidated

```
name contains "Ultra-Thin"/"embedded"   -> PLUMBED   40/41, 0 counterexamples
model id in the r2310 series            -> PLUMBED   7/7   (catches Master Pro / Master One)
name is "<Model> Master"                -> NOT a flag; 10 of them have clean tanks
plain name                              -> nothing;  17 plain-named models are plumbed
```

## ⚠ Two cautions on the index itself

**1. It reads 10 pages, not the whole document.** `build_content_index.py` takes HEAD 5 + TAIL 5 —
enough for cover, parts list and spec table, which is where identity and plumbing markers live.
Its signal counts are therefore MUCH lower than `walk_manuals.py`'s full-document counts and the
two are **not comparable**. The index finds the right DOCUMENTS; the walk counts the signals.

**2. Junk from the mass API pulls.** Chris: *"some junk from mass api strips."* The corpus carries
other Dreame product lines — espresso machines, pool cleaners, shavers, hair tools, dishwashers,
a dehumidifier. 77 files, now excluded. They mattered because the PRODUCT-NAME join pulled them
into real families: six `MISFILED-dreame-ecceluxe-ESPRESSO-MACHINE-not-vacuum__s20-pro_*` files
extract "S20 Pro", a genuine catalog product, and landed in `wash_station`; pool cleaners did the
same to `x10` (14 files).

⚠ The model-id join was **never** exposed — 0 junk files token-match a catalog id, because ids
match on a token boundary. The same fix that stopped `r2228` matching the `r2228d` manual also
stopped the shaver `pr2501a` matching `r2501`.

⚠ And my first exclusion attempt SILENTLY DID NOTHING: it purged the cache in memory, then hit
`if not todo: return` and exited before writing, while printing "purged 77 junk rows". 20 MISFILED
rows were still on disk. Always persist before an early return — and check the artefact, not the
log line.


## ⛔ CORRECTION — "10 Master models have a clean tank" was the boilerplate

Chris: *"do they have clean tanks in the manual where they are tagged master"*. He asked because
the claim smelled wrong, and it was. I had scored MASTER-tagged models from the CONTENT INDEX,
which reads 10 pages, and counted `clean_tank >= 1` as "has a clean tank". Full-document reads
show what those hits actually are:

> Only clean water and the officially-approved cleaning solution can be added to the clean water
> tank. Do not add any other liquid such as alcohol or disinfectant.

**A safety caution about what may be ADDED — the exact trap
[`FINDING-plumbed-variants-have-no-clean-tank.md`](FINDING-plumbed-variants-have-no-clean-tank.md)
records for the X50 Master:** *"presence of the phrase is not presence of the part."* That note is
where the warning lives, I cited it in this same session, and then re-made the error one section
later with a shallower instrument.

### Re-counted, boilerplate excluded

```
MASTER-tagged models with a manual                20
   only the safety boilerplate                    10   <- previously counted as "has a tank"
   no clean-water phrase at all                    4
   genuinely document a clean-water tank           6
```

**So 14 of 20 have NO clean-water tank.** Chris's "master was the flag for some plumbed editions"
is right, and much broader than the two I had allowed (`Master Pro`, `Master One`).

The 6 divide again, and only 3 are station tanks:

```
REAL STATION TANK, in the parts list, plumbing absent or minimal
   r6012  Clean Master X60 Pro Steam      clean=10  plumb=0
   r501w  X60 Master (Ultimate edition)   clean=11  plumb=0
   r2212  G20 Master                      clean=10  plumb=3   (has a fill procedure)

ONE real mention each, and it is the station AUTO-FILLING THE ROBOT's tank
   r2501l X50 Pro Master   r2501p X50s Pro Master   r5189u X60 Master
      "클린 스테이션은 로봇 청소기의 정수 탱크를 자동으로 채우고"
      "主機清水箱將透過基座進行自動補水"
```

Those three are robot tanks refilled by a plumbed station — not a station clean tank, and under
the robot-tank ruling not ours anyway.

### The usable rule

**Master + plumbing markers (plumb >= 5) => no station clean-water tank.** All three genuine
station tanks sit at plumb 0-3; every model at plumb >= 5 has none.

### The methodological lesson, which is the more valuable half

The content index reads **10 pages**; the walk reads the **whole document**. I wrote that caution
into this note myself and then treated an index count as a hardware fact in the very next
analysis. **Index counts locate documents. Only a full read counts a part** — and even then the
sentence decides, because a safety caution names the part without the machine having it.


## The Master rule is MARKET-conditioned — Chris: *"the ZH set use (embedded)"*

He spotted that the three exceptions to "Master => plumbed" are all Chinese documents, and that
the ZH set marks plumbing with the embedded descriptor instead. Cross-tabbing Master-tagged
models by the manual's dominant script against a full-document, boilerplate-filtered clean-tank
count:

```
script     HAS tank   no tank
CJK            4          4
Hangul         1          1
Latin          1          9
```

**Within CJK the DESCRIPTOR does the work.** All four CJK "no tank" models carry it explicitly:

```
r6112  Clean Master X60 Pro Steam (Ultra-Thin embedded)   plumb=11
r512g  X60 Master (Ultimate Ultra-Thin embedded)          plumb=11
r2310  Master Pro          r2310 series                   plumb=9
r2310a Master One          r2310 series                   plumb=9
```

so a plain `Master` name in a Chinese manual means the TANK version — which is why the three
strong station tanks (`r6012` clean=10, `r2212` clean=10, `r501w` clean=11) are all CJK.

**Within Latin the NAME does the work.** 9 of 10 have no tank, and the one exception (`r2501l`,
real=1) is the station auto-filling the ROBOT's tank, not a station tank. Export documents folded
the plumbed configuration into the Master name.

### The tell

`X60 Master` sits on both sides:

```
r5189u  X60 Master   CJK     real=1   plumb=2    tank version
r5104h  X60 Master   Latin   real=0   plumb=5    plumbed
r5189j  X60 Master   Latin   real=0   plumb=5    plumbed
```

Same product name, different model ids, opposite docks. **The dock tracks the MARKET, and the
manual's language is a proxy for it** — domestic Chinese listings keep the basic water-tank dock;
export listings ship the plumbed one under the same Master name.

### Consequence for cut-outs

A cut-out decision cannot be made from the name alone once Master is involved — it needs the name
AND the document's market. Concretely:

```
embedded / r2310 in the name            -> PLUMBED, any market      (still 47/48, no counterexamples)
Master + Latin/Hangul manual            -> PLUMBED                  (9 of 10, the 10th is a robot tank)
Master + CJK manual, no descriptor      -> HAS a station tank       (3 of 4 strong; the 4th is real=1)
```

The embedded rule is market-independent and stays the primary cut-out signal. Master is a
secondary one that must be qualified by market, and this is exactly the noise Chris meant when he
said the names break down.


## ✅ FULL-DEPTH RESOLUTION — the eight, settled

Chris: *"read the other 7 i want to be done with this in one shot if possible."*
`tools/resolve_dock_splits.py` — every model in all eight families, whole document, boilerplate
filtered, 12 cores. Result cached to `tools/dock_resolution.json`.

```
CONFIRMED SPLIT at full depth   6   s40, x40, x50, x50_pro, x50_ultra, x60_master
NOT split                       2   m50_ultra, wash_station
```

`m50_ultra` and `wash_station` drop out: the 10-page index had over-read them, and at full depth
neither has models on both sides (`wash_station` has just 2 models with a manual at all, 5 without).

### Per-family, at depth

```
s40          TANKS 5   PLUMBED-both 4
x40          TANKS 14  PLUMBED-supply 1
x50          TANKS 41  PLUMBED-both 2
x50_pro      TANKS 8   PLUMBED-both 4
x50_ultra    TANKS 1   PLUMBED-both 1   no-station-water 1
x60_master   TANKS 1   PLUMBED-both 3   REVIEW 1
```

`PLUMBED-both` = neither station tank. `PLUMBED-supply` = mains in, used-water tank still present.
The distinction matters: a supply-plumbed machine still needs its dirty-tank card.

### ⚠ A THIRD EVIDENCE-FITNESS RULE: a line manual cannot resolve a SKU

The pass produced exactly ONE name-rule disagreement:

```
r25857  X50 Pro (Enhanced Ultra-Thin embedded)   rule=PLUMBED   manual=TANKS
```

Its manual is **305 pages**, and 19 model files share its byte-identical signature
(`c=7 b=2 d=13 p=5`) — one multi-language export manual reissued per model id. A line manual
describes every variant in the line, so it reads TANKS whenever ANY variant has them.

```
models resolved ONLY by a >=150-page manual   37   of which TANKS 35
embedded models on a SKU-scale manual (<150p) 14   PLUMBED 13, REVIEW 1, TANKS 0
```

**Excluding mega-manuals as unfit, the embedded rule has ZERO counterexamples.** The
disagreement was an evidence-fitness problem, not a rule problem — and it means those 35 "TANKS"
readings identify a product line, not a dock.

The three fitness rules now stand together, and all three were learned the same way — by a
shallow instrument confidently returning a wrong answer:

```
10-page index count   -> LOCATES a document. Counted the safety caution as a part.
line manual (>=150p)  -> IDENTIFIES a product. Cannot resolve a dock variant.
one manual per family -> SAMPLES one SKU. Read a plumbed variant as the whole family.
```

### What is safe to cut out

An **embedded-named model whose evidence is a SKU-scale manual** is plumbed, with no
counterexamples in 14. That is the cut-out set. Models resting only on a line manual are NOT
resolved and must not be cut on that evidence.
