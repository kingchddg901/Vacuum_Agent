# Dreame guide families — the scope, and why a family is a MANUAL PAGE

*(Retitled 2026-08-25. This file was called "why it is r-codes and not names" while it
argued for the r-code rule; that rule is retired below and the title outlived it by a
few hours — which is exactly how a dead premise keeps reading as authority.)*

**Decision (Chris, 2026-08-25): the target is Dreame's CURRENT-ISH lineup**, i.e. what
their own comparison page still lists — `dreametech.com/pages/robot-vacuum-and-mop-comparison`.
Not the 587 models the integration declares, and not the 228 historical platforms.

**26 platforms. 4 have manuals; 3 of those are authored (X50 Ultra, X60 Ultra, L10s
Ultra Gen 2 — L50 Ultra is downloaded but not written). 22 platforms have neither.**

⚠ Three counts live in this file and they are NOT interchangeable: *platforms in the
current-ish lineup*, *model keys the integration declares* (587), and *keys an authored
family actually reaches* (49). Say which one you mean.

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

| family | page covers | keys | authored |
|---|---|---|---|
| `x50` | X50 Ultra + X50 Ultra Complete | **41** | ✓ |
| `x60_ultra` | X60 Ultra | 4 | ✓ |
| `x60_pro_ultra_complete` | X60 Pro Ultra Complete | 1 | ✓ |
| `l10s_gen2` | L10s Ultra Gen 2 | 3 | ✓ |
| `l20` | L20 Ultra + L20 Ultra Complete | 15 | manual in hand |
| `x40` | X40 Ultra + X40 Ultra Complete | 9 | manual in hand |
| `l50` | L50 Ultra | 2 | manual in hand |

**Authored: 49 of 587 — 8.3%. Manuals in hand: 75 — 12.8%.**

⚠ **Those are two different numbers and this note previously ran them together.** It
reported "75 of 587 — 13%" as coverage when only `x60` and `l10s_gen2` were written:
8 keys, 1.4%. A downloaded PDF is not a guide. Quote the AUTHORED figure unless the
sentence is explicitly about what is left to transcribe.

The three remaining manuals are worth 26 keys and would take authored coverage to
12.8%. `l20` is the largest single one left.

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
rule it is **13%, 75 of 587**.

Re-run it whenever a family lands. "We wrote two families" is not a coverage statement.

## Status

Authored, all in `custom_components/eufy_vacuum/adapters/dreame/dreame_upkeep_guides.py`:
`x50` (R2489A), `x60_ultra` (R5089B), `x60_pro_ultra_complete` (R6001), `l10s_gen2`
(R2469X). 13 components each; the Pro Ultra Complete has 14.

**Guarded by `tests/adapters/dreame/test_dreame_upkeep_guides.py`** — before it, nothing
in the tree could go red on any of this. DUG-1 fails if a `BRAND_REGISTRARS` row for
Dreame ever appears (the release switch). DUG-4 fails if any of the seven measured X50
vs X60 divergences collapses — the regression guard for the shared-`_BASE` defect. All
14 mutations were ablated and all 14 went red; the switch guard was ablated separately,
including against an empty registrar table so it cannot pass vacuously.

⚠ There is still **no `BRAND_REGISTRARS` row**, and adding one is the release. The
adapter is gated on a released upstream build carrying Tasshack #1707.
