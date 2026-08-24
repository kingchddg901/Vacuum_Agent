# 25 — The Eufy Segmentor

**Scope.** The 1,606-line HSV pipeline in `adapters/eufy/segmentor.py`: the question it was built
to answer, the two-image trick at its centre, and how you tell which stage is mis-tuned. The
pluggable engine contract it plugs into is [13 — How Rooms Are Found](13-segmentation.md).

**This document does not list thresholds.** Every numeric constant here was fitted to one brand's
map imagery on one person's floor plan, and reproducing them in prose would create a second copy
that drifts. What is worth writing down is the *premise* — which stays true — and the *retuning
surface*, which is how you find the constant that is wrong without being told what it currently is.

---

## 1. It answers a question that has since been answered

The vacuum knows its own rooms. `segments` on the vacuum entity carries them, and the map source
subsystem reads the vendor's own segmentation directly. So a computer-vision pipeline that infers
rooms from a screenshot looks, today, like a solution to a solved problem.

It was not solved when this was written. This module is the surviving fragment of a much larger
spatial-CV branch — map transform, alignment, live position tracking, path-trace capture — that was
built and then amputated, on the reasoning that the backend should depend on room truth, run truth,
queue truth and learned timing rather than on spatial inference. The segmenter is what was kept,
and it was kept quarantined inside the brand package rather than promoted to core.

**Read it as a system built before there was ground truth.** That framing explains its two
otherwise-odd properties: it never claims to be right, and it is designed to hand its output to a
person.

---

## 2. It is not trying to be correct — it is trying to be editable

The engine contract's third output type is `EditReadiness`, alongside quality and state. The
pipeline's job is not to produce rooms; it is to produce **a starting position a human can finish**
in the card's editor. Three separate classifiers exist for this and they answer different
questions:

| classifier | question |
|---|---|
| `adapters/eufy/segmentor.py::_issue_quality` | how much do we trust this segment |
| `adapters/eufy/segmentor.py::_structural_role` | is this shaped like a room, a corridor, or an artefact |
| `adapters/eufy/segmentor.py::_segmentation_state` | is this clean, worth review, or genuinely ambiguous |

A pipeline optimising for accuracy would collapse these into one score. Keeping them apart is what
lets the card say *which kind* of wrong a segment is, and a segment that is confidently a corridor
is a different editing task from one that is ambiguous.

The result carries a `good_or_better_count` beside the raw segment count for the same reason. The
number that matters to a user is not how many shapes were found.

---

## 3. The two-image trick

Most of the module's length is here.

A single screenshot of a Eufy map is hard to segment because adjacent rooms are filled with similar
colours and the wall between them is thin. Hue clustering alone merges neighbours.

So the pipeline takes **two renders of the same map** — the app's dark theme and its light theme.
`mapping/mapping_services.py::_CV_SOURCE_VARIANTS` fixes the set: dark, then default, is the
primary source; light is the assist. Room fills and wall strokes respond differently to the theme
change, so the pair separates what one image cannot.

Three consequences follow, and each accounts for a chunk of the file:

1. **The two images are not aligned.** They are separate screenshots, possibly at different zoom or
   crop, so `mapping/segment_primitives.py::estimate_alignment` recovers a scale and offset and
   every assist layer is transformed into the primary's pixel space before use.
2. **Walls become a first-class mask.** `adapters/eufy/segmentor.py::_build_light_wall_mask` exists
   only because the light variant exposes wall strokes the dark one buries, and those strokes are
   what the highest-priority split strategy cuts along.
3. **Everything degrades if the assist is missing.** The assist is optional throughout; without it
   the pipeline still runs, and the result's message says which mode it ran in.

`mapping/mapping_services.py::_image_variant` also accepts `custom` and `custom_<id>` variants, and
the segmenter deliberately never probes those — a custom backdrop is a manual-authoring surface, so
a custom-only map is never auto-segmented.

> This is also the reason the vision-model route was rejected. The pipeline's whole signal is small
> differences between two full-resolution PNGs; the model path received a downscaled image, and the
> difference the method depends on does not survive the downscale.

---

## 4. The split cascade is ordered by evidence quality

When a component looks like more than one room,
`adapters/eufy/segmentor.py::_split_suspicious_component` tries seven strategies **and returns the
first that succeeds.** The order is the argument:

| # | strategy | evidence it uses |
|---|---|---|
| 1 | wall cuts | an actual wall stroke from the assist variant |
| 2 | localized bins | only for very large components |
| 3 | colour distance | primary/assist colour separation |
| 4 | local support | saturation and value support masks |
| 5 | assist hue | assist hue alone |
| 6 | erosion seeds | shape only |
| 7 | opening split | shape only |

It runs strongest-evidence-first and falls back toward pure morphology. A wall cut is a real
observation about the map; an erosion seed is a guess about shape. Reordering these to put the
cheap morphological operations first would make the pipeline faster and its splits less defensible.

✅ **CORRECTED 2026-08-23.** The module header listed these in a different order — erosion and opening first, wall
cuts third. That was *source-definition* order, not priority, and close to the reverse of the
real cascade, in the one place a reader looks to find out what is tried first. The header now
lists the cascade in run order and says so explicitly.

---

## 5. How you tell which stage is mis-tuned

This is the retuning surface, and it is the reason not to memorise constants.

The result's `segmentation.stages` block reports **six named stages**, each publishing its own
counters, so a bad result localises to a stage before anyone touches a threshold:

| stage | what its counters tell you |
|---|---|
| `base_mask_generation` | room pixels found at all — if this is low, the HSV room thresholds miss this palette and nothing downstream can recover |
| `variant_reconciliation` | assist agreement, wall pixels, and how many pixels the wall cuts removed — a large removal here with few segments later means the wall mask is eating rooms |
| `connected_components` | clusters and components seen — the raw material count |
| `candidate_scoring` | kept, dropped, deduped — a high drop count with a low segment count means the keep thresholds are too strict for this map |
| `suspicious_region_split_pass` | split candidates, regions generated, and a per-method debug list |
| `recovery_pass` | regions recovered, and the deficit still outstanding against the expected count |

Several stages also report **left/right pixel counts** rather than a single total. That is not
decoration: a mask defect that is symmetric is usually a threshold problem, and one that is
lopsided is usually an alignment problem. The split localises the cause.

`recovery_pass.count_deficit_after_recovery` is the one number to read first when a map comes back
short. `expected_room_count` biases scoring rather than forcing an outcome, so a non-zero deficit
means the pipeline knows it fell short — which is a different failure from returning confident
nonsense.

---

## 6. A CV pipeline with no CV library

There is no OpenCV here. The stack is NumPy, Pillow and SciPy's `ndimage`, and the Home Assistant
install has no cv2 — which is one of the reasons the wider spatial branch was cut rather than
finished.

All three are **optional and undeclared**. The integration's requirements do not list them, so on a
box without them the pipeline returns a fully-shaped result with `available: False` and a machine-
readable reason rather than raising. `mapping/segment_primitives.py::image_runtime_capabilities`
reports each library's availability and version into every result, including the failures, so a
diagnostic taken from a box that cannot segment still says why.

The readiness check gates the whole pipeline at its first line, and the image read is separately
guarded — an unreadable file is a different reason code from a missing library.

---

## 7. Surfaces that do not do what they say

**The cascade's return type is wrong.** `adapters/eufy/segmentor.py::_split_suspicious_component`
is annotated as returning a two-tuple. Every `return` in it produces three values, its docstring
describes three, and its single caller unpacks three. The code and the prose agree; the annotation
is a leftover from a two-value version. Harmless at runtime, and it would be caught the moment this
file is type-checked.

**The first-tried strategy used to be the one whose failure was not recorded.** Every other
strategy appends an entry to the debug list whether it succeeds or fails. The wall-cut attempt
appended only on success — when it failed, the per-method debug list simply had no wall-cut row. So
the strategy with the strongest evidence, tried first, was invisible in diagnostics exactly when it
did not fire, and a reader inspecting the debug list would reasonably conclude it was never
attempted.

It records its declines now, and it records WHICH decline, because the four are four different
problems for whoever is reading:

| reason | what it means |
|---|---|
| `no_wall_hint` | the second image variant was never available — a user/upload question |
| `wall_hint_shape_mismatch` | two images arrived at different sizes — a pipeline bug |
| `no_local_wall` | the hint does not touch this component |
| `no_split` | walls found, no clean cut separated it — a tuning question |

The reason is produced inside `_split_component_via_wall_cuts` rather than inferred by the caller:
the caller would have to re-test the function's own preconditions to guess it, and a second copy of
a predicate is how the two drift apart. The debug sink is an optional parameter, so the eight
existing call sites that only want the masks are untouched.

**The tuning block restates two defaults.** The adapter's `segmenter_tuning` declares a minimum
area equal to the function's own default and an epsilon of `None`, which is the auto-derive
behaviour the parameter already has. Both are documented in place and neither is wrong; they are
worth knowing about only so that a reader counting "what Eufy had to tune" does not overcount.

**Its own porting instructions are optimistic.** The module tells a new brand to copy the HSV mask
builder and the scoring heuristics and retune the thresholds. That is right as far as it goes, but
the two-image premise is not portable in the same way: it depends on the vendor's app offering two
themes that render walls and fills differently, and on a user being willing to upload both. A brand
whose app has one theme does not have a weaker version of this pipeline — it has a different
problem, and `noop_fallback` is the honest declaration.

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
