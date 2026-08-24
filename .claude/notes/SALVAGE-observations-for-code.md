# Salvaged observations owed to the code

Facts recovered from retired documents that **exist nowhere in source** and belong as comments
at the site they explain. Each one was verified absent before being listed — the grep is
recorded so the check can be repeated rather than trusted.

This file grows as the doc rewrite proceeds. Each new document's salvage read appends here;
nothing is applied during a doc pass, so a documentation commit never carries a code change.

**Why these are worth the trouble.** They are physical-world premises — facts about hardware
that no amount of reading the code recovers. The lifecycle salvage examined 23 candidates and
found ZERO, because every one was already carried by a comment that was *richer* than the doc.
Mapping is different: it is the subsystem that touches physical reality, so the observations
that calibrated its constants were never expressible in code.

---

## From `11-mapping-system.md` (retired 2026-08-22)

### 1. Eufy raw position scale — 1 unit ≈ 1 mm, INFERRED

**Site:** `mapping/tracker.py` — extend the existing comment above `MOVEMENT_DELTA_THRESHOLD`.

> The scale is approximately 1 unit ≈ 1 mm for Eufy devices (not verified across all models).

This is what makes `MOVEMENT_DELTA_THRESHOLD = 10.0` readable as *about a centimetre of robot
travel*. Without it the constant is an unscaled number.

⚠ **The trap is that the tree already contains a mm-per-unit statement, and it is Roborock's.**
`mapping/map_source_runtime.py` carries *"coords are vacuum units (1 unit = 1 mm)"* as a
documented Roborock convention, and `adapters/roborock/adapter.py` says `app_zoned_clean` wants
world millimetres. A reader who finds those and generalises them treats the Eufy scale as
guaranteed when it is an unverified approximation. **The Eufy caveat is load-bearing precisely
because the Roborock certainty is nearby.**

*Verified absent:* grep for `1 ?mm|mm/unit|millimet|per unit|vacuum unit` across
`custom_components/`, `src/` and the live docs returns only the three Roborock statements.

### 2. What the Eufy room-mask thresholds are rejecting

**Site:** `adapters/eufy/segmentor.py::_build_room_mask_from_hsv`, at the
`room_mask = (value >= 68) & (saturation >= 18)` line.

> Pixels must be both bright enough (value ≥ 68/255 ≈ 27% brightness) and colourful enough
> (saturation ≥ 18/255 ≈ 7%) to be treated as room pixels. This excludes near-black walls,
> near-white backgrounds, and the off-white dock area.

The threshold *values* are in code. The imagery observation that calibrated them is not — so a
porting brand, or anyone re-tuning, has no statement of what the mask is meant to reject and no
way to tell a mis-tune from a change in how the vendor renders its maps.

*Verified absent:* the function's docstring says only *"Return a binary room-pixel mask derived
from HSV saturation and value thresholds"*; the module says *"tuned for Eufy map colour
palettes"* and *"calibrated on Eufy map images"* — never what they exclude.

### 3. Eufy position frame — axis direction is robot-specific

**Site:** a note is the honest home; if it goes in code, `mapping/tracker.py` near the constants.

> The origin and axis directions are robot-specific. On Eufy map_6 the Y axis increases upward
> in the robot's reference frame but this is not guaranteed by the protocol.

**Low live value, kept for one reason.** The only current consumers of vacuum-space position are
the tracker's Euclidean delta — which is axis-direction agnostic — and the passive dock-drift
log. But `adapters/eufy/adapter.py` deliberately retains `position_lock_reliable` *"against a
possible trace-bounds revival"*, and a revival would need this.

*Verified absent:* the Y-flip comments in `map_source` and `roborock_raw_map` concern the
provider's rendered-image space (0–1, top-left origin), not the raw robot position sensors.

---

## From `26-eufy-segmentor.md`, `17-map-manager.md`, `31-map-source-coordinator.md` (retired 2026-08-22)

### 4. ⭐ Why hue is the clustering space — the Eufy renderer paints each room a distinct hue

**Site:** `adapters/eufy/segmentor.py`, one line above the median-filter / 16-wide binning pair.

> Hue clustering. Median-filter the hue plane, bin into 16-wide buckets; iterate the active
> bins (**Eufy renders each room in a distinct hue**).

**The highest-value item found so far, and the only one rated high.** It is not a detail about a
constant — it is the world fact the entire CV segmentation rests on. A maintainer can read the
binning and see *what* it does; nothing in source says why a hue bin corresponds to a room.

Without it the choice of hue as the clustering space reads as a generic computer-vision
decision. It is not: **the algorithm is keyed to a rendering property of the vendor's map
image.** Anyone porting to another brand, or re-tuning after Eufy changes its palette, needs to
know that the premise is the vendor's renderer rather than anything about rooms.

*Verified absent:* the only room-adjacent `hue` hits in `custom_components/` are the two binning
lines themselves, both bare code with no rationale. `distinct hue|own hue|hue per room` returns
zero across source and notes.

---

## How to apply these

They are comments at a constant, not prose. Each states a **premise** the number rests on, which
is the one thing a reader cannot recover by reading the number. Keep the hedges — *inferred*,
*not verified across models*, *not guaranteed by the protocol* — because the hedge is the fact:
a reader who needs certainty here needs to go and measure, and the comment's job is to tell them
that no one has.

---

## 5. The room-RULES editor hardcodes clean_passes to [1, 2] — an Eufy limit on a brand-neutral surface

Salvaged 2026-08-22 from `docs/retired/dev/09-room-rules-system.md`, which is being deleted.
**FRONTEND — queued behind the frontend pass, not applied.**

Eufy caps 2 passes; Roborock declares 3 (`dispatch.passes_max`). The room SETTINGS editor was
already migrated to the capability-gated `max_clean_passes`. The room RULES editor was not, at
three sites:

    src/renderers/room-rules.js:565      `${[1, 2].map((count) => ...)}` — the chips
    src/bindings/room-rules.js:291-295   `if (normalizedPasses === 1 || normalizedPasses === 2)`
    src/state/room-rules.js:401          validity requires Number(value) === 1 || === 2

So a Roborock user can set 3 passes per room and cannot express a 3-pass modifier RULE. The
binding **silently drops** the value rather than refusing it.

⚠ **The same file states the contract it breaks.** `src/renderers/room-rules.js:15-19`: *"Each
adapter declares what its hardware supports … The card renders whatever the adapter says is valid
for this brand."* `_renderModifierChanges` honours it for clean_mode / fan_speed / water_level /
clean_intensity through the `chipRow(label, field, options)` helper — which returns `""` when the
adapter declared no options — and then the very next block uses a literal.

This is `f/eufy_is_not_the_default` and `f/eufy_ism_leak_layers` together: the brand port fixed
the settings editor and missed the rules editor.

**The backend does not clamp on the way in.** `protected_room_config` copies whatever
`clean_passes` it receives, so a value injected server-side through the service reaches the
effective room unclamped; only the dispatch wire clamps to `[1, passes_max]`
(`queue/dispatch_engines.py:226-230`). The frontend limit is therefore the only thing enforcing
it on the UI path, and it enforces the wrong brand's number.

Absence proven: `max_clean_passes` appears in exactly two frontend files (`src/cards/dashboard-card.js`,
`src/state/room-editor.js`) plus its backend producer. Zero hits in any of the three room-rules
files, and no passes-capability reference in them at all.

---

## 6. ⭐ Why the segmenter is CV and not a vision model — the LLM path never saw the real image

**Site:** `adapters/eufy/segmentor.py`, module docstring, beside the existing "Porting a new
brand" section.

**Provenance: Chris, 2026-08-23, in conversation — but only the REASON is new.**

⚠ **I originally wrote "recorded NOWHERE else" here and that was FALSE.**
[`project_eufy_origin_lineage.md`](project_eufy_origin_lineage.md) stage 5 already describes the
CV branch as *"a deterministic **no-LLM** room-segmentation engine"*. The decision is on record;
what is NOT on record anywhere is **why** — the low-grade-image reason below.

**How I got it wrong, because the method matters more than the slip.** My absence-proof grep
returned **40 matches and I read `head -12`**. The lineage note ranked **19th**. I truncated my own
evidence and then asserted absence in bold, which is the same failure this whole campaign keeps
finding in other people's comments: an unaudited scope returns zero and reads identically to a
clean one.

**RULE: never prove absence through a truncated result set.** For an absence claim, count first
(`| wc -l`), then read all of it, or narrow the pattern until the full set is readable. `head` on
a grep whose entire purpose is to prove nothing exists is a self-inflicted false negative.

**The fact that is genuinely unrecorded.** The lineage note says the engine is deliberately
no-LLM. It does not say why. The reason was not model capability — it was that **the LLM pipeline
received a low-grade image rather than the full-quality PNG.** The model was being asked to
segment a degraded copy of the map, so the comparison was never against the real input.

Note that the lineage note gives *different* reasons for amputating the whole spatial branch
(stage 5): the backend should rest on "room truth, run truth, queue truth, and learned timing
rather than spatial/map inference"; mapping added runtime coupling; the HA box has no cv2; trace
capture was unreliable (last trace `sample_count 0`). Those are reasons for dropping SPATIAL
INFERENCE. They are not the reason for choosing CV over a vision model, which is what this entry
records.

**Why this matters more than an ordinary rejected alternative:**

⚠ **It is a NOT-YET wearing the clothes of a NEVER.** The blocker is INPUT PLUMBING — what image
reached the model — not "a model cannot do this". Anyone re-reading the current pipeline sees
1,606 lines of hand-tuned HSV clustering and reasonably infers someone judged CV the better
technique. That is not what happened. If the full-quality PNG can be delivered to a model, the
comparison has never actually been run.

⚠ **It reframes the tuning.** The hand-tuned thresholds are not evidence that the problem needs
hand tuning. They are what you build when the alternative was evaluated on bad input.

**What I do NOT know and must not invent:** where the degradation happened (HA camera proxy? a
resize on the way out? the capture path itself?), when this was decided, or whether the
full-quality PNG is reachable today. The comment should state the reason and stop there — the
mechanism of the degradation is not recoverable and guessing it would turn a true fact into a
false one.

**Suggested comment shape** — states the reason, needs no attribution to stand up:

    A vision-model approach was considered and rejected: the pipeline available to it
    delivered a downgraded image rather than the full-quality PNG, so the comparison was
    never against the real input. The blocker is what the model can be SHOWN, not what it
    can do — if the full-quality PNG becomes deliverable, this is worth re-running.

---

## 7. ⭐⭐ The CV segmenter was built BEFORE the map gave us truth, and its accuracy bar is "correctable", not "correct"

**Site:** `adapters/eufy/segmentor.py` module docstring. This is the frame the whole file needs,
and without it a reader cannot tell why 1,606 lines of hand-tuned CV sit next to a source that
simply reports where the rooms are.

**Provenance: Chris, 2026-08-23 — but read
[`project_eufy_origin_lineage.md`](project_eufy_origin_lineage.md) FIRST.** That note already
carries the pre-integration history in seven stages and states the through-line directly:
*"spatial approach rejected for timing/battery learning."* What it does NOT carry is the ordering
against `map_source` or the correctable-not-correct accuracy bar, which is what this entry adds.

⚠ **It also records something that has since CHANGED and needs reconciling:** stage 5 says the CV
segmentor "survived only quarantined to `tests/adapters/eufy`". It is in production today at
`adapters/eufy/segmentor.py`, imported at module level by `mapping/segmenter_engines.py`. So the
CV path came BACK out of quarantine at some point, and neither the note nor any comment says when
or why. That bears directly on the open question at the bottom of this entry.

The
ordering half is verifiable and I checked it:

    mapping/image_segments.py         2026-04-30   ALREADY 1,909 LINES at the git root
    mapping/trace_segmentation.py     2026-04-30   the other original approach — since DELETED
    -> split 2026-05-30 (5b87e4f2) into mapping/segment_primitives.py + adapters/eufy/segmentor.py
    mapping/map_source.py             2026-06-19   the truth source
    mapping/map_source_coordinator.py 2026-06-21

⚠⚠ **GIT CANNOT DATE THE ORIGIN OF ANYTHING IN THIS REPO, AND I GOT THIS WRONG TWICE.**

The root commit `eae291fa` is an orphan with **215 files and manifest version 0.9.0** — a mature
codebase imported into version control, not a first day of work. Everything in it, including the
1,909-line CV segmenter, was written BEFORE history begins. `--follow` faithfully reports
2026-04-30 and that is the IMPORT date.

So the honest statement is *"CV segmentation was already present when the repo was created"* —
never "it shipped on day one", which implies a project origin git has no view of. Chris's memory
is that it arrived during early integration; nothing here contradicts that, and nothing here can
confirm it either.

Two dating traps, both of which produced a confident wrong answer:
  1. `--diff-filter=A` alone dates the PATH — for a split-out file it returns the refactor commit.
     It reported `segmentor.py` as born 2026-05-30.
  2. `--follow` fixes that but still bottoms out at the IMPORT. A repo whose root is a v0.9.0
     release cannot answer "when was this written".

**For any origin question here, the answer is Chris, not git.** That is exactly why observations
#6 and #7 exist.

### The three facts

**(1) It predates the truth source, and it predates version control.** CV segmentation was
already present — 1,909 lines of it — in the commit that created this repo, when the only thing
available was the rendered PNG.
`mapping/map_source.py::rooms_from_room_pixels` — rooms derived from the device's OWN `room_pixels`
raster — arrived seven weeks later. The CV pipeline is not an alternative someone chose over the
vendor's segmentation; it is what you build when the vendor's segmentation is not reachable.

**And it was one of TWO original approaches.** `mapping/trace_segmentation.py` shipped in the same
first commit: derive a room polygon from the robot's driven trace. That one was deleted, and
`13-segmentation.md` documents what survives of it — `boundary.py`, 40 lines, `point_in_polygon`
and nothing else. So the shipped answer to "where are the rooms" has been through three regimes:
drive it, photograph it, or ask the device.

**(2) There are now three sources of room geometry, and this is the oldest:**

    room_pixels      the device's own segmentation      map_source.py       (Jun, the truth)
    image_segments   CV over the rendered PNG           segmentor.py        (predates the repo)
    custom_segments  hand-authored                      mapping_services.py
    (deleted)        polygon from the driven trace      trace_segmentation.py (Apr, gone)

**(3) The accuracy target is NOT correctness.** It is *good enough to be corrected in the card*.
The CV output is provisional by design — the user makes the final adjustments, and those land in
`image_segment_adjustments` (see `11-map-stored-state.md`) or in the authored `custom_segments`
path (see `13-segmentation.md`). Judged as a standalone segmenter it will look under-engineered;
judged as the first stage of a human-in-the-loop system it is sized correctly.

⚠ **"There are levels to the system that are not just in there."** The segmenter is one layer.
Quality scoring, the adjustment store and the authored path are the others, and they live in
different files. A doc that treats `segmentor.py` as the whole system will misjudge it.

### Why this belongs at the top of the file

Every other observation about this module is downstream of it. The hand-tuning (salvage #4), the
rejected vision-model comparison (salvage #6) and the module's own five repetitions of "tuned for
Eufy map colour palettes" all read differently once you know the pipeline was built against a PNG
because a PNG was all there was, and that its job is to get close enough for a human to finish.

⚠ **A question this raises and does NOT answer:** whether the CV path is still load-bearing now
that `room_pixels` exists, or whether it survives mainly for the authored/adjustment flow and for
maps where the device's own segmentation is unavailable. That is Chris's call and needs measuring
on real installs — do not infer it from the code.

---

## 8-11. From the adapter-contract salvage (2026-08-23)

Four observations, the highest yield of any pass so far (previous: 0, 4, 1, 0, 0).
`21-adapter-system.md` and `22-adapter-config-reference.md` carried porting lessons that the
schema encodes without explaining.

### 8. [medium] The scope of the localized-entity-id problem, and the fact that non-Latin-script installs escape it by accident rather than by design. HA localizes en

**Absence proven:** grep -rIn for '41 language', 'NATIVE_ENTITY_IDS', '48 translation|48
packs|ships 48', 'blast radius', 'languages\.py', 'entity ids? for [0-9]+', 'how niche|is this
niche|affected installs' across custom_components/eufy_vacuum, src/, tests/, .claude/notes/ —
zero hits for every pattern except 'blast radius', whose only hits are unrelated
(src/bindings/floor-opacity-resolve.test.mjs, two audit notes

> "Blast radius, for anyone weighing whether this is niche: HA localizes entity ids for **41**
languages (`generated/languages.py` `NATIVE_ENTITY_IDS`); Roborock ships **48** translation
packs, **32** of them in that set. Non-Latin scripts are unaffected only because they are absent
from the native set, not by design."

### 9. [medium] An entity id is a permanent fossil of the language active when the entity was first created, and the affected user cannot self-heal. async_get_or_crea

**Absence proven:** adapters/entity_resolve.py:378 and :577 and
tests/unit/test_entity_resolve.py:341 all state 'HA slugs an entity id from the TRANSLATED name
at creation time' — the creation half only. grep -rIn for 'never revisits', 'renames nothing',
'switch(ing)? (the )?language', 'changing the HA language', 'does not rename|never renamed',
'frozen at creation', 'self-heal' across custom_components/eufy_vacuum,

> "HA slugs an entity id from the **translated** name at creation and then never revisits it
(`async_get_or_create` looks the entity up by `unique_id` and takes the update path) … Switching
HA's language afterwards renames **nothing** — which also means an affected user cannot self-
heal."

### 10. [medium] A deliberately reserved fourth clean_mode slot: 'mop AFTER vacuum' as two sequential passes, distinct from vacuum_mop (one simultaneous pass). Neither

**Absence proven:** config_schema.py:474-489 declares clean_mode_options with exactly three
canonical values ('vacuum', 'mop', 'vacuum_mop') and no mention of a reserved fourth. grep -oE
'mop_after_vacuum|vacuum_then_mop|mop_then_vacuum|sweep_then_mop|vacuum_and_then_mop' across all
four trees — zero hits. grep -i 'reserved slot|slot 3' — the only hit is
.claude/notes/_dr_findings_wave3_adapters.json finding D22-ROUT

> "**Slot 3 is reserved and currently unoccupied.** Neither shipped brand does a sequential
sweep-then-mop, but several vacuums do, and a brand that supports it needs a slot that means
*that* rather than being forced into `vacuum_mop`, which is a different physical behaviour. …
Declaring the reserved slot now costs nothing and prevents the alternative: the first brand to
need it inventing a fourth v

### 11. [low] What removal_confirmation_passes=3 actually buys in wall-clock: the knob is calibrated against the auto_refresh_on TRIGGER cadence (dock events, rough

**Absence proven:** config_schema.py:1026-1038 states the purpose ('Prevents transient API
glitches from producing spurious removal notifications. Set higher for noisy integrations, lower
for stable ones. Default: 3.') but gives no time conversion and never names the trigger cadence
it is calibrated against. setup/drift.py:1-40 module docstring repeats the same purpose sentence
with no arithmetic. grep -i '3 passes',

> "A genuinely-removed room shows up in the setup tab within ~one day at typical clean cadence
(3 passes × 6-12h between events). A 5-minute API glitch never surfaces."

