# Dreame guide families — the scope, and why a family is a MANUAL PAGE

*(Retitled 2026-08-25. This file was called "why it is r-codes and not names" while it
argued for the r-code rule; that rule is retired below and the title outlived it by a
few hours — which is exactly how a dead premise keeps reading as authority.)*

**Decision (Chris, 2026-08-25): the target is Dreame's CURRENT-ISH lineup**, i.e. what
their own comparison page still lists — `dreametech.com/pages/robot-vacuum-and-mop-comparison`.
Not the 587 models the integration declares, and not the 228 historical platforms.

**26 platforms. 4 are covered by an authored family (X50 Ultra, X60 Ultra, L50 Ultra,
L10s Ultra Gen 2). 22 have no manual and no family.** The other three families —
`l20`, `x40`, `x60_pro_ultra_complete` — cover models Dreame no longer lists as
current, which is the point: older flagships become the common secondhand fleet.

⚠ Three counts live in this file and they are NOT interchangeable: *platforms in the
current-ish lineup* (26), *model keys the integration declares* (587), and *keys an
authored family actually reaches* (75). Say which one you mean — they answer different
questions and only the last one means "someone can read a guide".

---

## The rule — corrected 2026-08-25, second version

> **A guide family is a MANUAL PAGE. Its scope is every `dreame.vacuum.*` key whose
> marketing name appears on that page.**

Not the r-code, and not the marketing name. Both were tried and both are wrong:

* **r-code is too NARROW.** `X40 Ultra Complete` is `r2449`, not `r2416` — yet Dreame
  ships **one manual for X40 Ultra and X40 Ultra Complete together**. Keying on the
  manual's own r-code would leave `r2449` unguided while the manual plainly covers it.
  Same shape on X50: one page for Ultra + Ultra Complete, six platforms between them.
* **marketing name is too BROAD.** "X50" is 23 distinct names across ~20 codes.

**The manual page is the only boundary Dreame actually draws**, and it draws it by
printing one maintenance section for a set of models. That is vendor assertion, not our
inference — the strongest evidence available short of hardware.

⚠ **This supersedes the first version of this rule, which said "a family is an r-code
platform".** That was measured but under-scoped: it produced 7% coverage and would have
orphaned `r2449`, `r5020`, `r9515` and the four X50 Ultra Complete codes, all of which
sit on manual pages we already hold.

### One more correction: A MARKETING NAME CAN HAVE TWO MANUALS

"X60" had two, and they are two families, not one:

* **`R5089B-X60_Ultra`** — robot `RLX92DE`, dock `RCXE0910`. Marketing name **X60
  Ultra** → `r5089*`, `r9515*`, 4 keys.
* **`R6001-X60_Series`** — robots `RLX96DE`/`RLX98DE`, docks `RCXE0912`/`-1`.
  `r6001a` is **X60 Pro Ultra Complete**, 1 key.

Different regulatory hardware, different parts tables: R5089B lists **no baseboard
cleaning brush and no caster wheel**. An earlier cut put all three r-codes in one `x60`
family — backwards for two of the three, and it would have handed an X60 Ultra owner a
guide for a brush their robot has not got. The tell was in plain sight: **the manual
filenames carry the r-codes.**

Their care text, though, is 48 of 49 sentences identical — the baseboard brush is the
entire delta. So `x60_pro_ultra_complete` is built as `x60_ultra` **plus** that one
component. That is sharing on a **measured** diff, which is allowed; sharing because
component names line up is what is banned.

### And: THE APPLICABILITY STATEMENT IS ON THE SPECIFICATIONS PAGE

⚠ This note previously said *"the manuals do not resolve it either: no applicability
statement, no model list, checked on pp. 1-6 of each."* **Wrong** — that was front
matter, and absence there was read as absence everywhere. Every manual lists its
regulatory models under **Specifications** (X50: `RLX85CE` and `-1`,`-3`,`-4`,`-5`,`-6`
— six robots, three base stations), and the X50 goes further, naming its two marketing
variants outright on the what's-in-the-box pages: *"(Dreame X50 Ultra)"* p. 7 and
*"(Dreame X50 Ultra Complete)"* p. 8. So for the X50 the family scope is **Dreame's own
assertion**, not our inference.

And those two pages say WHY one care section covers both: the Complete's entire
difference is an **"Extra Accessories Kit"** — 3 dust bags, 3 dust box filters, 12 side
brushes, spare main brushes and mop pads. Consumable spares, not different hardware.
"Complete" on an X50 buys a box of refills; on an X60 the suffix buys a robot. Do not
carry an assumption about what a suffix means across model lines.

Incidental confirmation from the same pages: a **Cleaning Tool** is listed in package
contents, which is why the X50's steps say "the provided cleaning tool" where the X60
manual says "a proper tool". That wording difference is real, not a transcription slip.

### Coverage

| family | page covers | keys | components |
|---|---|---|---|
| `x50` | X50 Ultra + X50 Ultra Complete | **41** | 13 |
| `l20` | L20 Ultra + L20 Ultra Complete | 15 | 14 |
| `x40` | X40 Ultra + X40 Ultra Complete | 9 | 13 |
| `x60_ultra` | X60 Ultra | 4 | 13 |
| `l10s_gen2` | L10s Ultra Gen 2 | 3 | 13 |
| `l50` | L50 Ultra | 2 | 13 |
| `x60_pro_ultra_complete` | X60 Pro Ultra Complete | 1 | 14 |

**Authored: 75 of 587 — 12.8%. Every manual in hand is now written**, so authored and
downloaded have converged and the next family costs a new PDF, not a new read.

⚠ **Those were two different numbers and this note once ran them together**, reporting
"75 of 587 — 13%" as coverage when only 8 keys were written (1.4%). They agree today by
work, not by definition — the moment a manual is downloaded they diverge again. A
downloaded PDF is not a guide.

**Four of the seven pages name both variants outright** — X50 pp. 7-8, L20 pp. 7-8, X40
pp. 7-8 — and in every case the "Complete" differs only by QUANTITIES of consumables
(L20 Complete: side brush ×3, dust bag ×5, mop pad ×14). Spares, not hardware. That is
what lets one care section cover two marketing names — and note it does NOT generalise:
"Complete" buys refills on an L20/X40/X50 and a different robot on an X60.

Routing keys on the **full model string** via a generated name→family table, built from
`supported_devices.md` so it tracks upstream rather than being hand-typed.

---

## Why names and codes cannot be the key (the underlying measurement)

Marketing names and r-codes are many-to-many **in both directions**, measured against
`Tasshack/dreame-vacuum` `docs/supported_devices.md`:

```
"X50 Ultra"            26 keys ->  r2489 AND r9538      one name, two platforms
"X50 Ultra Complete"   15 keys ->  r2532, r2538, r5048, r9446
r2518                          ->  "X50 Pro Ultra", "X50 Ultra (Enhanced Edition)",
                                   "X50s Pro Ultra"     one platform, three names
```

"X50" alone is **23 distinct names across ~20 r-codes**. So a name identifies neither
the hardware nor a manual, and mapping guides by name would hand one platform's
instructions to another's hardware — the defect already committed once in
`a2efcf46` and fixed in `d45e2ec4`.

**The COVERS do not resolve it** — "X50 Series" and "X60 Series" name only themselves.
The Specifications page does, and the X50's box pages do; see the correction above.
That is where to look in any manual pulled from here on.

⚠ **`r501` is a live collision inside the current lineup.** `L60 Pro Ultra` and
`L40 Ultra Gen 2` are both `r501`, as are `L10s Ultra Gen 3` and `X60 Master`. So the
three-digit codes need their suffix to be a key at all — `r501bt` is Aqua 10 Roller,
`r501h` is something else. Keys are `r` + **3 or 4** digits + a **variable-length**
suffix; a `r\d{4}` regex silently drops ~9% of Dreame robots.

---

## The 26 current-ish platforms

| model | platforms | manual |
|---|---|---|
| X60 Max Ultra Complete | *(not in the upstream list at all)* | |
| X60 Ultra | `r5089`, `r9515` | **r5089 ✓** |
| Matrix10 Ultra | `r2513`, `r502`, `r5062` | |
| Aqua10 Ultra Roller | `r9535` | |
| Aqua10 Roller | `r9533` | |
| X50 Ultra | `r2489`, `r9538` | **r2489 ✓** |
| L60 Pro Ultra | `r501` | |
| L60 Ultra | `r5090`, `r6015` | |
| L60 Ultra PE | `r5039` | |
| L60 Ultra FE | *(not in the upstream list)* | |
| L50 Ultra | `r9493` | **✓** |
| L40s Ultra | `r2551` | |
| L40s Ultra AE | `r2579`, `r500` | |
| L40s Ultra CE | `r2562`, `r5021` | |
| L40 Ultra Gen 2 | `r501` | |
| L10s Ultra Gen 2 | `r2469`, `r5020` | **r2469 ✓** |
| D30 Ultra | `r5057` | |
| D20 Pro Plus | `r2566`, `r9537` | |
| D20 Plus | `r2564`, `r5314` | |

**Most current models are TWO platforms** — X60 Ultra is `r5089`+`r9515`, X50 Ultra is
`r2489`+`r9538`, L10s Ultra Gen 2 is `r2469`+`r5020`.

⚠ An earlier version of this note called those "half-covered". **That was wrong**, and
it was the r-code rule causing it: both codes of each pair sit on the SAME manual page,
so one family legitimately covers both. Robin's guides do apply to an `r5020` L10s
Ultra Gen 2, because Dreame prints one maintenance section for the model name they
share. Two platforms is not two hardware sets.

⚠ **`X60 Max Ultra Complete` — the current flagship — is not in the upstream device
list.** It cannot be driven at all by the installed build, let alone guided.

---

## What authoring one family costs

1. **Automate the finding.** `Routine Maintenance` locates the care section reliably:
   `l20` pp20-26 · `x40` 19-26 · `l10s_gen2` 18-25 · `x50` 22-30 · `l50` 23-30.
2. **Read the pages in VISUAL order.** `pypdf.extract_text()` emits content-stream
   order, which interleaves adjacent columns — a collapsed extract of the Gen 2 "Main
   Brush" block arrives with used-water-tank sentences inside it, and that produced a
   false "the dust bag differs" finding once. **`scripts/pdf_layout_dump.py` fixes this
   properly**: it reconstructs reading order from the text matrices (cluster by *y*
   into rows, sort by *x*, mark column gaps with `|`), so a three-column care page like
   R6001 p15 comes out legible. No rasteriser is installed — no poppler, no PyMuPDF —
   so this, not page images, is how these get read.
3. **Author the family whole**, from that platform's own manual.

**Do not factor a shared base out of two families because their component names match —
only because you diffed them.** Measured between `x60` and `l10s_gen2`: of the **11
component keys in common, exactly ONE (`caster_wheel`) has identical steps**. Ten
differ, six while having the same step COUNT, so nothing shape-based catches it. Between
`x50` and `x60_ultra`: 29 of 46 sentences shared, 5 of 12 common keys identical. But
between the two X60 manuals it is 48 of 49 — so those two *do* share a body, and the
difference between that and the original defect is entirely that the diff was run first.

Cheap way to run it: strip `Fig. E-\d+` and page furniture, split on sentence
boundaries, and set-difference the two care sections. It takes seconds and it is the
only thing standing between "these look the same" and "these are the same".

Manual pages needed: ~13 for the 22 platforms, since siblings share a page
(`L40s Ultra`/`AE`/`CE`, `D20 Plus`/`Pro Plus`, the Aqua10 pair).

---

## Coverage is measured against the LINEUP, not against downloads

The check that produced this file: after two families were written, coverage against
the full model list came out **26% by name and 7% by r-code**. The GAP was the finding
— two keys disagreeing by a factor of four proved neither resolved what a family
covers, which is what sent us to the manual page as the boundary. Under the corrected
rule, and with all seven families authored, it is **75 of 587 — 12.8%**.

Re-run it whenever a family lands. "We wrote two families" is not a coverage statement,
and neither is "we downloaded seven manuals" — this file has made BOTH of those mistakes
and each time the number moved by more than the work did.

The recount is cheap and worth repeating rather than remembering: parse
`supported_devices.md` into `name -> [keys]`, sum the keys for the marketing names on
each authored page, divide by the 587 total.

## Language coverage — EVERYTHING AUTHORED IS ENGLISH ONLY

All 264 authored strings come from EN sections, and there is **no
`upkeep_guides_i18n/` for Dreame at all** while Eufy and Roborock each carry 17 packs
plus the EN base. Chris was told (2026-08-25) and said **record, do not start** — the
i18n rollout is LOCKED at 18 languages, so Dreame packs are a decision, not cleanup.

The manufacturer text for most of those languages is ALREADY in the PDFs we hold, and
it is unevenly spread. Per authored family, measured from page footers:

| language | families with manual text | note |
|---|---|---|
| EN | 7/7 | |
| DE, FR | 6/7 | |
| IT | 5/7 | |
| ES, NL, PL | 3/7 | |
| HE, PT | 2/7 | |
| AR, ID, JA, TR, ZH-Hant | 1/7 | `l10s_gen2` only |
| KO | 2/7 | `x50`, `x60_ultra` — separate Korean-edition PDFs |
| CS, ZH-Hans | 0/7 | |

⚠ **THE PROBE THAT PRODUCED THIS WAS WRONG TWICE, AND BOTH FAILURES LOOKED LIKE DATA.**
Recorded because the next person will reach for the same shortcut:

1. First version returned **zero languages for every manual** — it read only the tail of
   the extracted text, and footers are not last in content-stream order. A probe that
   answers uniformly is broken, not informative.
2. Fixed, it still under-reported: **single-language regional editions carry no ASCII
   footer code at all.** RU, JA and ZH-Hant were nearly reported absent with the
   Cyrillic, Kana and Han plainly in the file. Sniff the SCRIPT, not just the footer.

It is trustworthy only because it was ablated against something independently known —
it recovers exactly what each filename claims (`R2489A-X50_Series-EN_DE_FR` → EN/DE/FR).
And per `MANUAL-INVENTORY.md`'s own standing warning, **the filename is not a manifest**:
it is a floor to check the probe against, never the answer.

⚠ **`ko` is the live correction.** `MANUAL-INVENTORY.md` records Korean as absent with
good evidence — that finding is about the **L10s Gen 2** and stands. But
`korean-vocabulary-source/` holds `R2489F` (X50 Ultra) and `R5089F` (X60 Ultra), so
Korean is in hand for two authored families. That file has been annotated in place.

---

## Status

**Seven families, all authored from their own manual**, all in
`custom_components/eufy_vacuum/adapters/dreame/dreame_upkeep_guides.py`: `x50` (R2489A),
`l20` (R2394A), `x40` (R2416A), `x60_ultra` (R5089B), `x60_pro_ultra_complete` (R6001),
`l50` (R9493), `l10s_gen2` (R2469X). 13 components each; the L20 and the Pro Ultra
Complete have 14. **264 authored strings**, all scored against their source manual.

Cross-family identical-component counts, measured (out of ~12-13 keys in common):

```
x60_ultra / x60_pro_ultra_complete  13/13   shared body BY CONSTRUCTION, diffed first
l50       / x50                     11/13   two families -- see below
x40       / l10s_gen2                8/13
x50       / x40   6/12    l20 / x40   6/13    x40 / l50   6/12
x50       / x60_ultra                5/12
l20       / x60_ultra                1/11    the most distinct pair here
```

⚠ **`l50` and `x50` are 11 of 13 identical and are still two families.** The whole
delta sits INSIDE two shared components, not in an extra one: the L50 says *open* the
robot cover where the X50 says *remove* it, and the L50 carries a laser distance sensor
with no VersaLift while the X50 carries a VersaLift with no LDS. Merging them would tell
an L50 owner to wipe a sensor their robot has not got. This is the case the X60 pair is
NOT, and the difference is where the delta lives — which only a read finds, never a
headline overlap number.

**Guarded by `tests/adapters/dreame/test_dreame_upkeep_guides.py`** (37 tests) — before
it, nothing in the tree could go red on any of this. DUG-1 fails if a
`BRAND_REGISTRARS` row for Dreame ever appears (the release switch). DUG-4 and DUG-6
fail if a measured divergence collapses — the regression guards for the shared-`_BASE`
defect. DUG-6 pins BOTH halves of the l50/x50 relationship, the 2 that must differ and
the 11 that must stay the same, because a difference-guard alone goes green on a corpus
that has simply rotted.

25 mutations ablated, 25 went red. The switch guard was ablated separately, including
against an EMPTY registrar table so it cannot pass vacuously.

`scripts/verify_dreame_guide_provenance.py` scores all 264 strings against their source
manual: 0 defects, 15 known recasts. Its exemption for recast entries carries its own
FLOOR (40%) — waving a component/kind pair through unconditionally would have hidden an
invented sensor step behind the same label that excuses a legitimate rewrite, and that
hole was ablated shut. Note the L50 manual sets "filter" with an fi LIGATURE, which a
naive tokenizer turns into "lter" and reports as a defect in every filter sentence.

⚠ There is still **no `BRAND_REGISTRARS` row**, and adding one is the release. The
adapter is gated on a released upstream build carrying Tasshack #1707.
