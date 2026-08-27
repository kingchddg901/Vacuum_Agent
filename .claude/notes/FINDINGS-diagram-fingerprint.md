# Diagram-fingerprint clustering — evidence report

**Status: STOPPED at Step 5, deliberately.** The handoff's Section 5 says to report a
contradiction with its premise rather than reconcile it silently. There is one, and
this is it.

**Premise under test:** manufacturers reuse illustration assets, so two manuals sharing
component drawings document the same procedure. The handoff states the expectation
plainly: *"Since the corpus appears to come from a single documentation house, asset
reuse is expected to be high and exact."*

**Finding: asset reuse is neither high nor exact.** The signal that does exist is weak
and does not survive a loosened threshold.

---

## What the corpus actually contains

Four structural facts, each of which produced a confident, uniform, WRONG answer before
being measured. On this corpus a uniform answer is broken, not informative.

1. **There are no raster images.** A 220-page Aqua10 manual contains exactly ONE
   `/Image` in the entire file. The handoff's Step 1 asset class 1 — "embedded raster
   images … SHA-256 of the raw stream" — yields essentially nothing here.
2. **Form XObjects are background boxes.** The same manual holds 26 distinct `/Form`
   XObjects; the ones inspected are a single filled rectangle (153 bytes, one `re` +
   `f`). An early probe hashing only Form streams reported **42% overlap between the
   Track and Roller manuals.** That number was measuring background boxes. It is not
   illustration lineage and was nearly reported as such.
3. **The artwork is inline vector paths, one segment per `q…Q` block.** Page 12 of the
   Track manual carries 174 moveto / 173 lineto / 172 stroke operators inside 177
   balanced `q…Q` pairs. Treating `q…Q` as figure granularity returns zero assets
   corpus-wide.
4. **`page.get_contents()` returns `None` on this corpus** for pages carrying a 16.8 KB
   stream. `page["/Contents"].get_object().get_data()` returns it. Every zero in the
   chain above ultimately traced to this one accessor.

## Step 0 — single-house test

Not run corpus-wide. Spot evidence supports it: the manuals inspected are Adobe
InDesign 20.0 / Adobe PDF Library 17.0, PDF/X-3:2002, and the InDesign source filename
survives in `/Title` (e.g. `R9528A-<EU edition>-<manual>-Aqua10 Ultra Track Series.indd`).

## Step 1 — exact tier

Implemented as `scripts/dreame_diagram_fingerprint.py`. Because the unit of reuse is a
figure but the unit of storage is a 2-point segment, the fingerprint is a **shingle**: a
run of k consecutive path points normalised to the run's own first point, which is
translation-invariant.

**Whole-document, first 40 content pages, k=8:**

| pair | Jaccard |
|---|---|
| track x roller | 0.439 |
| track x protrack | 0.551 |
| roller x protrack | 0.442 |
| track x x40 | **0.003** |
| roller x x40 | **0.003** |
| protrack x x40 | **0.003** |

Two orders of magnitude. **But this measures document-template lineage, not procedure
identity** — it separates "same manual family" from "different manual family", which is
a weaker claim than the one being tested.

⚠ Jaccard is size-sensitive here: the X40 manual yields 691,771 path points in 40 pages
against the Aqua10's 4,768, a 145x asymmetry. Report percent-of-smaller alongside it.

## Step 1 applied to the mop SECTION — negative

Restricting to the mop-maintenance pages (located per document from page-delimited
text), exact shingles do **not** separate mechanism:

```
spin within      median 0.139
spin x assembly  median 0.114
spin x roller    median 0.126
```

Within-class overlap is indistinguishable from cross-class.

## Step 2 — perceptual tier

**An earlier conclusion in this effort that Step 2 was impossible was wrong**, and the
correction matters: those tools rasterise a PDF *page*, but this artwork is already
vector segments, so the segments can be drawn directly into a numpy array. Self-
rasterising the paths IS the edge map Step 2 asks for, and it skips decode-then-edge-
detect entirely because line art has no fill to discard. No PDF renderer is required.

Implemented in `scratchpad/figure_shape.py`: segments → spatial connectivity grouping →
normalise each figure to its own bbox (aspect preserved, letterboxed) → 48x48 occupancy
grid → Hamming distance.

## Step 3 — document frequency

DF weighting is **not optional**. Raw best-match Hamming between any two documents is
ZERO, cross-mechanism included: every manual contains a figure that normalises to the
same bitmap, because a rectangle outline in a unit square is a rectangle outline.

Histogram over 49 documents (identical figure bitmaps):

```
appears in  1 doc  : 769 distinct figures     <- the rare tail
appears in  2      :  68
appears in  3      :  28
appears in  4-12   :  ~40
appears in 13-26   :  ~18                     <- template mass
```

Bimodal as the handoff predicted.

## Step 5 — validation, on a PROXY set

Chris's twenty hand-diffed manuals were not available, so the set was derived from the
corpus instead: documents whose maintenance text names mop pads / mop pad holders
(spin, 41 docs / 26 distinct reg codes, spanning D20, E30, E40, E50, L10s, L40, L50,
L60, P20, P50, V50, V70, X40, X50, Matrix10, MOBIUS), against controls naming a
fluffing roller (3) or a mop assembly (5).

**Cutoff × radius sweep** (score = fraction of A's rare figures with a near match in B):

| cutoff | radius | spin-within | spin×other | margin |
|---|---|---|---|---|
| 3 | 120 | 0.117 | 0.017 | 0.100 |
| 3 | 200 | 0.730 | 0.500 | 0.230 |
| 3 | 300 | 1.000 | 1.000 | 0.000 |

The usable window is narrow and collapses. At radius 120 the ratio is ~7x but recall is
12%. At radius 200 half of the CROSS-class pairs match too. At 300 everything matches
everything.

**And the matches are the wrong figures.** Characterising matched vs unmatched rare
figures on spin-within pairs at radius 120:

```
MATCHED    n= 2080  segments median=324   ink median=0.0556
unmatched  n=12003  segments median= 50   ink median=0.0642

CONTROL (spin x roller|assembly):
MATCHED    n=  550  segments median=784   ink median=0.0560
```

Matches are driven by LARGE figures, and the cross-class matches are larger still. The
connectivity grouping is merging page artwork into composites, and at 48x48 one dense
composite resembles another regardless of content. That is the "near-identical generic
drawings across genuinely different mechanisms" false positive of Section 6, and it
accounts for most of the apparent signal.

## Conclusion

**The premise does not hold on this corpus at the strength it was stated.** The most
likely reason is straightforward: a maintenance figure shows the SPECIFIC ROBOT, so it
is redrawn per model even when the procedure is identical. That is consistent with
Chris's own hand-diff, which found the mop procedure TEXT identical across twenty
manuals spanning five model years — the words were reused; the pictures were not.

**Recommendation.** Treat text-section clustering as the primary signal and the diagram
stream as confirmatory on close-up COMPONENT drawings only, not as a clustering axis in
its own right. The one diagram result that is solid — whole-document template lineage
at J=0.44 vs 0.003 — answers "same manual family", which the reg code already answers
more cheaply and more directly.

## What would change this conclusion

- Chris's actual twenty, in place of the proxy set.
- Better figure segmentation. The composite-merging above is a real defect, and a
  tighter connectivity tolerance or a size cap per figure might expose a genuine
  component-level signal the current grouping is burying.
- Higher render resolution than 48x48.

None of these were pursued, because tuning until the ground truth passes without
confirming the controls still fail is the process failure named in Section 6.

---

# ⛔ RETRACTED, 2026-08-27 — THE EXTRACTOR WAS BROKEN

**Everything above the line is measured on page furniture, not artwork. Do not cite
any number in it.** The conclusion "the premise does not hold" is withdrawn; it was an
artefact of the extractor, not a property of the corpus.

Chris asked to SEE two mop-maintenance pages, to judge whether the similarity was
computationally hard or visually absent. Rendering them is what exposed it: the first
render was **a page of empty rectangles** — illustration frames and rules, with a dense
blob in one corner and no drawings anywhere.

Two bugs, both silent, both yielding confident numbers:

1. **Every Bezier curve was discarded.** `segments()` handled `m`/`l`/`re`/`h` and not
   `c`/`v`/`y`. On a figure page curves outnumber lines roughly 5:1 —
   `l10s-pro-ultra` p4 carries **11,770 `c` against 2,443 `l`** — so about 17% of the
   geometry was extracted, and the surviving 17% was the straight-line page furniture.

2. **The transformation matrix was ignored.** Each figure is drawn in its own local
   coordinate space and placed by `cm`; that same page carries **4,046 `cm`
   operators**. Without a CTM stack every figure lands on the origin. That is the
   corner blob, and it also explains the "large composite figures" artefact reported
   above as a false-positive mechanism: connectivity grouping was merging art that
   had all been stacked on top of itself.

Both fixed in `scripts/dreame_figure_shape.py` (Bezier flattening + q/Q CTM stack).
Segment counts on one page went 2,998 -> 97,350, and the renders now show the
illustrations plainly.

## What survives the retraction

* The four STRUCTURAL facts about the corpus (no raster images; Form XObjects are
  background boxes; artwork is inline vector paths; `page.get_contents()` returns
  None). Those were measured independently and still hold.
* The correction that Step 2 needs no PDF rasteriser. It is in fact stronger now:
  self-rasterising the paths produces legible full-page renders.
* The DF-weighting requirement. It was derived from a real observation (every document
  shares some figure that normalises identically) and is unaffected.

## What must be re-run before anything is concluded

Every similarity measurement: the whole-document exact tier, the mop-section exact
tier, the perceptual tier, the cutoff sweep, and the matched-figure characterisation.
The numbers in the sections above are void.

## The lesson, which this file already stated and I did not apply

The report above opens by saying a uniform answer on this corpus is broken, not
informative — and lists four cases where that held. The fifth case was the report's own
conclusion. **A NEGATIVE RESULT IS A UNIFORM ANSWER TOO.** "No separation anywhere"
should have been treated with the same suspicion as "zero assets everywhere", and the
cheapest possible check — render it and look — was not run until Chris asked for it.
