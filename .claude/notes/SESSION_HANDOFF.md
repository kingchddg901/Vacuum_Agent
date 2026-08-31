# SESSION HANDOFF — 2026-08-31 — Dreame go-to + zone LIVE-PROVEN; zone global-precall DEPLOYED (untested); OVERNIGHT: 7 guide families + full 18-lang i18n DONE — NOW COMMITTED (local, size decision still pending)

**Read this first on resume.** Index = durable facts, this = current state.

---

## 🟢 2026-08-31 — THIS SESSION (NEWEST — go-to, zone, global pre-call, settings-gating spec)

**Branch `dreame-tier-override-guides`. THE PILE DESCRIBED BELOW IS NOW COMMITTED LOCALLY,
NOT PUSHED** (9 commits `0fc1d501..` this session: guides flat-model+provenance, i18n,
spatial go-to/zone backend, external-run/fault/current-room attribution, card frontend,
adapter vocab+wiring test, corpus tooling, docs+NOTICE, these notes). `brands.py`'s
DO-NOT-COMMIT dreame BRAND_REGISTRARS switch is deliberately STILL UNSTAGED. Everything is
also deployed to `Z:` (a full HA restart loads the Python; the card bundle is built +
deployed). Re-check `git status` / `git log` — do not trust this line. STILL OPEN (not a
commit): the guide-translations.js SIZE decision (§B) and the live zone-precall test (§NEXT).

### 🌙 OVERNIGHT BATCH 2026-08-31 (guide families + FULL 18-lang i18n) — DONE, UNCOMMITTED
Chris's overnight task ("the rest of the maintenance guides made for Dreame / linked to
devices / i18n / OCR the image-only ones"). Autonomy he set: build all, leave uncommitted
for review, full 18 languages now, AI-translate (text-first, OCR where tooling exists).

**A. 7 new guide families authored + integrated** (matrix10, l60_ultra, l60_ultra_pe,
l40s_ultra, d30_ultra, d20_pro_plus, d20_plus) — measured off their own api-fetch manuals by
a 7-agent workflow, spliced into `dreame_upkeep_guides.py` (now 22 families / 16 authored),
`SOURCES` added to the provenance verifier, and **32 real models remapped tier→authored** in
`upkeep_catalog.py` (one hallucinated key `RPL51FE0` dropped; the two real L60 Ultra models
were already present). **Provenance: 639 strings, 0 defects.**
  - **OCR fallback added to `verify_dreame_guide_provenance.py`** — `d20_pro_plus`'s manual
    (`r2566a`) has a non-extractable CID font (mojibake text layer); its care pages RENDER
    fine, so the verifier now renders+OCRs (pymupdf + the tesseract binary Chris installed)
    any page whose text is garbled, and FAILS loudly if OCR is unavailable rather than
    emitting false defects. Reusable for the rest of the image-only corpus. Content proven:
    35/35 d20_pro_plus strings ≥40% vs both the OCR of its own manual AND its clean sibling
    `r2564b` (D20 Plus). `r5057a` carries a STALE catalog name "L40 Ultra A" but its own
    manual is a D30 Ultra manual, so the `d30_ultra` family link is right — the NAME is the
    stale field (flagged, not renamed).
  - **CONSISTENCY AUDIT (Chris asked — bulk authoring held up).** Within-family: the 7 bulk
    families are **100% authored verbatim from their own manual** (88/88 components, up from
    98% after closing 2 filters — `matrix10.filter`/`d20_pro_plus.filter` recast from each
    manual's own "Dust Box and Filter" section, matching their dustbin override; 0 new i18n
    strings, all already translated). The hand-authored old-9 are 67% verbatim (lean on the
    tier base more). Cross-family: 73% of authored step-slots are byte-identical reuse; the
    variation is genuine per-manual wording (e.g. "provided tool" vs "proper tool", a real
    X50/X60 manual difference) and real hardware deltas (D20 Pro Plus lists more sensors than
    D20 Plus) — NOT transcription drift. Sibling pairs from near-identical manuals converged
    19/23 and 24/26 identical. No semantic/contradictory inconsistency anywhere.
  - **REMAINING COVERAGE (diff-measured):** of the current-ish lineup, 12/19 models now have
    a family, 2 aren't driveable. The 5 uncovered need **0 new families**: L60 Pro Ultra =
    LINK (catalog row → `l60_ultra`); Aqua10 Roller / L40s Ultra AE / L40s Ultra CE / L40
    Ultra Gen 2 = VARIANT (existing family + measured delta; the L40 variants all lack
    `l40s_ultra`'s climbing-wheel `main_wheel`, a real hardware split). NOT yet built.

**B. Full 17-language i18n** (the 18th is English source). NEW dir
`adapters/dreame/upkeep_guides_i18n/` (17 `<lang>.py` packs + `__init__` →
`DREAME_UPKEEP_GUIDE_TRANSLATIONS`, exported from the package). 147 unique step/note strings
+ 9 frequency phrases (16% of 940 slots — heavy reuse) were AI-translated by a 17-agent
workflow (156/156 per lang, 0 missing, ①②/"IN" markers preserved), then a generator
assembled the packs to FULL parity (17 langs × 22 families, component-deduped into `_cNNN`
vars). Marked AI-DRAFTS (refine in place; manual-transcription via `dreame_i18n_segment.py`
is the Phase-2 upgrade). New parity+no-English-fallback test `test_dreame_upkeep_guides_i18n.py`
(5 tests, ablation-proven to bite). `sync-guide-translations.py` + `guide-translations.js`
regenerated; `guide-frequency-translations.json` gained the 5 missing interval phrases.
  - **⚠ COLLISION HANDLED:** Roborock AND Dreame both key generic tiers `standard`/
    `auto_empty`/`wash_station`; the card looks a family up by bare key with no brand. The
    sync merge now adds Dreame COLLISION-SAFE (never overwrites an earlier brand) — verified
    **0 eufy/roborock entries changed**. Dreame's unique authored families localize; its 3
    bare-tier families fall back to English on the card until keys are brand-namespaced (the
    proper fix, deferred — a cross-brand card change).
  - **⚠ SIZE DECISION FOR CHRIS:** guide-translations.js 340KB→2.0MB; the minified card
    bundle would grow ~+3MB (command-center 2.2→5.4MB, and the map bundle too — both import
    it). It's 61% redundant (identical component prose repeated across families); deduping via
    shared JS-object references in the sync output would ~halve it and is transparent to the
    card lookup, but changes the shared serialization for ALL brands → **your call, not made
    unilaterally.** NOT deployed (dist build only, proved it compiles). Tests: 67 passed, 1
    expected-red (below). JS maintenance units 50/50.
  - **LOADING DIRECTION (Chris, this convo):** don't bundle all guides in the card. The globe
    ALREADY fetches its UI text on-demand per-language (`src/i18n/index.js loadLocale`, same-
    origin fetch of `frontend/locales/<lang>.json`) — `guide-translations.js` is the lone
    thing bundled all-langs. Fix = bring guides in line: split per-language served files (card
    fetches the globe lang like a locale; ~17× smaller, no backend, works for Dreame unwired),
    or per-model/WS pull from the adapter snapshot for the big catalog (the backend overlay in
    `maintenance/manager.py:258` is already `guide_translations[lang][family][component]`; only
    `lang` is hardwired to the instance — parameterize it). Sequencing: **flat model → on-
    demand loading → scale authoring.** NOT built yet (the flat model IS, below).

**C. FLAT-MODEL correction (Chris, this convo — DONE, before scaling authoring).** The audit
found the family system barely held up under a verbatim standard: authored families override
~100% of steps/notes (base contributes nothing) AND the only thing the base still supplied —
FREQUENCIES — was un-verbatim (a normalised cadence) and UNVERIFIED (the provenance verifier
never scored frequencies). Fixed the data model:
  - `dreame_upkeep_guides.py` rewritten: **authored families are now FLAT per-manual tables**
    (steps/notes only, no base+override/drop); frequencies lifted into ONE owned map
    `COMPONENT_FREQUENCIES` (21 component-types, proven consistent across all 22 families),
    injected by `_with_cadence`. Tier profiles stay COMPOSED (`_profile`) as the unauthored
    fallback (nesting preserved). **Proven BYTE-IDENTICAL library output** before/after (no-op
    for the data; `guide-translations.js` unchanged after re-sync).
  - Frequencies are now GUARDED: DUG-9 (cadence single-sourced, no family carries its own),
    DUG-10 (values from a controlled `KNOWN_INTERVALS` vocab — a typo/new interval fails
    instead of rendering untranslated), both ablation-proven; the provenance verifier now also
    asserts every component resolves a cadence. Tests: **69 passed**, 1 expected-red.
  - Why it matters for the catalog: a flat table can't silently inherit generic prose (the two
    `filter` gaps this convo existed ONLY because the base was there to inherit from) and can't
    hide a missing component behind a fallback — the failure modes that scale badly at 700.

### LIVE-PROVEN on Robin (cross-render tested — our render vs the Dreame app matched)
- **Go-to (cruise-to-point).** Tap the map → robot drives there. Card `⌖` button (gated on
  `supports_goto` + a co-registered frame). `eufy_vacuum.goto` → `dispatch_goto` →
  `dreame_vacuum.vacuum_goto`. Offset `[30,290]` validated (the target sat where the Dreame
  app drew it).
- **Zone clean — COORDINATES.** Draw a box → robot cleans exactly it (cross-render overlay
  proof). Dedicated top-level `zone` block → `dreame_vacuum.vacuum_clean_zone` (4-tuple
  `zone` + `repeats`). `zone_max: 10`.

### DEPLOYED but NOT YET RUN ON HARDWARE (the one unproven piece)
- **Zone settings via GLOBAL PRE-CALL** — `dispatch/manager.py::_dispatch_zone_with_global_precall`:
  snapshot → flip `switch.robin_customized_cleaning` **OFF** (ungates the globals) → bulk-set
  the global selects (`cleaning_mode`/`cleaning_route`/`suction_level`) + `number.wetness_level`
  → **READBACK, refuse on mismatch** → execute the bare zone → **restore-at-completion** (a
  vacuum-state listener: after `cleaning`/`returning`, a return to `docked`/`idle` fires the
  restore + flips the gate back ON). Water = the FINE `wetness_level` 1-32 (3 card states →
  8/16/27). Harness-tested only — the flip/readback/restore has never moved the robot.

### KEY ARCHITECTURE FINDINGS (read from the dreame integration on `Z:`)
- **`customized_cleaning` is the device's MODE SELECTOR** — ON = per-segment settings (the
  STORE, `vacuum_set_custom_cleaning`); OFF = global. It gates the global selects (they read
  `unavailable` when ON).
- **`clean_segment` IS a param call** — ships per-segment `[seg,repeat,suction,water,index]`
  as `CLEANING_PROPERTIES` via `start_custom`; suction/water/repeats are LISTS in the service.
  So the old **"params are decorative" ruling is UN-RE-TESTED against the list path** — an A/B
  (`suction_level:[0,3]` on 2 rooms, store set differently) is the one measurement that settles
  whether inline per-room suction/water are honored. **Route/mode are NOT in `clean_segment`'s
  5-field row** — they ride the STORE (`set_custom_cleaning` DOES accept `cleaning_route`
  despite `services.yaml` omitting the field — its `fields:` list is just incomplete) or the
  globals. Per-room route/mode/suction SELECT entities exist (`select.robin_room_N_*`, 10 each).
- **`clean_zone` sets suction/water GLOBALLY via `_update_*`** — so the precall's suction/water
  may be redundant; the flip is load-bearing only for mode/route + fine wetness.
- Robin = `r2469a`, L10s Ultra Gen 2, fw 1636. `customized_cleaning=True` → `clean_segment`
  sends `index=1` (safe regardless of `capability.gen5`, which we never resolved — it's a
  device-reported cap, in the diagnostics download only).

### DECISION (Chris): global-flip is UNIVERSAL; phased dispatch uses it
Global pre-call flip extends to ROOMS + PHASED DISPATCH (phased uses the GLOBAL version);
per-room customized stays available "if someone wants it." Full write-up + the
**settings-per-mode GATING SPEC** (both tables, read off the app): →
`.claude/notes/DESIGN-dreame-cleaning-mode-toggle.md`.

### CAPABILITY / REPLICA PLUMBING (this session)
`supports_goto` (opt-in capability: `capabilities.py` KNOWN_CAPABILITY_HINTS + `_hint_wins` +
return dict; adapter hint + config block; snapshot). `supports_zone_clean` → True (L10s
profile). `zone_settings` snapshot field (card renders the setting selects from it).
Anchors: **RNQ433CB** (capability config-block↔snapshot replica), **RN0Y49XS** (Dreame render
`_n` ↔ `dreame_correspondences_from_mapdata` replica), **BN47Z0PR** (fixed a malformed
`BNDREAMEMD` anchor). Entries in `docs/dev/00c-replicas.md`. NEW MEMORY:
`f/anchor_replica_at_the_fix` (notice + anchor a replica set AT THE FIX).

### OPEN / NEXT (in priority order)
1. **DECIDE the guide-translations.js SIZE** (overnight §B) — ship flat (+3MB/bundle), dedup
   via shared JS refs (~halves it, shared-serialization change), or trim scope. Then `npm run
   build:deploy` to actually ship the card (dist build only so far).
2. **LIVE-TEST the zone precall** — draw a zone + pick Mop/Wet/Deep, watch
   `customized_cleaning` flip off → clean → flip back on. The one unproven piece.
3. **COMMIT the pile** — all of the above is uncommitted on `dreame-tier-override-guides`.
   Guides+i18n are review-ready; do NOT stage `brands.py`'s DO-NOT-COMMIT dreame registrar.
4. **BUILD settings mode-gating** (both tables per the design note) + the room/phased
   global-flip (reuse `_dispatch_zone_with_global_precall`'s primitive).
5. Deferred/small: brand-namespace guide family keys (unblocks Dreame bare-tier card i18n);
   fix `r5057a`'s stale "L40 Ultra A" catalog name → D30 Ultra; the suction/water inline A/B;
   the HA-restart-mid-run restore-persistence edge; add the "Mop after Vac" mode (4th, global).

### TEST BASELINE (known-red, all pre-existing/expected)
3 brand-registrar (the `brands.py` Dreame switch, `DO-NOT-COMMIT`) + 17 locale
(`vocab.dreame.fan_speed.turbo` + the 2 new English-only `map.goto_*` keys, within the
fallback ratchet). Suite otherwise green (~4300+ passed).

---

## 🟢 2026-08-29/30 — THIS SESSION (newest; read before the corpus sections below)

**Branch `dreame-tier-override-guides`, 10 new commits, NOT pushed** (re-check
`git log --oneline -12`; do not trust this line). Working tree after them: clean
EXCEPT `brands.py` (the live-test registrar switch — carries its own
`⚠ DO-NOT-COMMIT` marker, correctly excluded) and the untracked
`scripts/dreame_corpus_*` / `dreame_doc_*` corpus tooling (prior work) + these notes.
NOTE: the live `Z:` deploy still has a leftover `_dreame_probe.py` + `dreame_clean_probe.jsonl`
(harmless, deduped) — the next deploy's `/PURGE` clears them; the repo tree is already clean.

### What landed (10 commits)
```
ac761c4e fix(dreame): robot/dock anchor from the camera's live pose, not the {0,0} sentinel
ba02b385 feat(dreame): VA raster render — room_pixels_v1 from the decoded map
5d8b1a3a feat(dreame): map raster decoder — true per-room area, furniture, pose
7b225e09 docs(testing): document the settings_write dispatch test
c413ec71 fix(jobs): normalize map-id comparison in the start blocker
e69c8282 fix(cards): brand-scoped vocab labels + water-level chip layout
2ed8729b feat(dreame): completion secondary-clear gate + settings_write dispatch
989a82da refactor(core): drop brand names from 4 brand-agnostic core keys
```
(Plus 2 earlier this branch.) Decoder+render+pose all VALIDATED LIVE on robin: areas match
ground-truth pixel counts exactly, VA raster renders our floor plan in the correct orientation
(matches the Dreame app), robot/dock anchors sit on the dock. Render ~4-5px vs the Dreame PNG
frame = PARKED (our render is self-consistent; the gap only shows on the old PNG-backdrop
fallback, which the VA render replaces).
343 touched tests green; the full suite's only reds are PRE-EXISTING (locale packs
missing the English-only `vocab.dreame.fan_speed.turbo`; the `brands.py` registrar
switch tripping 2 brand-selection tests). Sequencing needed hunk-splitting the rename
out of `manager.py`/`registry.py`/`dreame/adapter.py`/`test_adapters.py`
(blob-injection + `git apply --cached`); `manager.py`'s `_run_settings_write` wrapper
was correctly moved into commit 2, not the cards commit.

### Commit 1 — brand names dropped from core, DUAL-ACCEPTED  [[feedback_drop_brand_names_in_core]]
Chris's standing rule: "every time it's this cheap we drop brand names in core." Four
core selector keys renamed:
- `eufy_room_pixels_v1` → `room_pixels_v1` (card render-data format)
- `dreame_camera_attrs` → `camera_attrs` (map-source backend id)
- `eufy_anchor_winding_v1` → `swept_area_winding_v1` (+ class `EufyAnchorWindingAttributor`
  → `SweptAreaWindingAttributor`)
- `eufy_cv_v1` → `cv_image_v1` (map-segmenter engine key)
Persisted adapter-config selectors → core gates/registries **dual-accept the legacy key
for ONE RELEASE** (legacy-key bite tests pin it; REMOVE the aliases next release).
Server-side only (card decodes by payload fields, not the format string; zero `src/`
refs). A workflow sweep confirmed these 4 and cleared 3 — `roborock_raw_map_v1` (names
its own input format), `eufy_counter_v1`, `eufy_room_clean`. The last two exposed a
SEPARATE, UN-FIXED `eufy_is_not_the_default` tension: core dispatch/job-segmenter
FALLBACKS (`_FALLBACK_TEMPLATE`, `_FALLBACK_JOB_ENGINE`) default to the Eufy engine — a
behaviour/design change (documented compat for legacy all-Eufy installs), not a rename.

### Proven live on vacuum.robin (committed as features 2-3, or recorded not-built)
- **Completion**: `completion.secondary_clear_entity:"task_type"` (not the Eufy
  `active_cleaning_target`, which reverts to the dock room) — finalized a multi-room
  Kitchen→Dining run cleanly.
- **settings_write**: parked/pre-launch bulk `vacuum_set_custom_cleaning`, index-aligned
  INT arrays over queued rooms, read-modify-write. Locks at launch. Card's Dreame per-room
  write path.
- **Live suction beats the vendor app** (NOT YET BUILT): per-room suction select stays
  writable mid-run (route/mode/water go `unavailable` at launch). Build dynamic-suction on
  the blocker loop, gate `live_mutable_settings:["fan_speed"]`.
- **Route is mop-only** (objective, NOT YET BUILT): gate card CLEANING PATH on
  `route_honored_modes:["mop"]`.

### ✅ Dreame map decoder (Stage 4) — DATA LAYER BUILT + VALIDATED + COMMITTED `5d8b1a3a`
`map_source_runtime.dreame_coordinator` / `dreame_mapdata_candidates` / `dreame_render_from_mapdata`
(+ wired as the Dreame backend in map_source_coordinator, MapData preferred / camera-attr bboxes
fallback). Reads the base MapData via the PUBLIC `coordinator.device` (resolved through the physical
DEVICE — the `vacuum.*` entity is our wrapper). Produces TRUE per-room `area_m2` (pixel_type,
`{id,100+id,200+id}` × grid_size², frame-robust), pose (robot/dock anchors), and user-placed
furniture (neutral slug + room + size). 6 unit tests `DMD-*` (`test_dreame_mapdata_decode.py`,
doc'd in 07-mapping). **Validated live on robin: areas match ground-truth pixel counts EXACTLY**
(Living Room 16.59 m² = 6634 px × 0.0025; grid_size **50 mm** confirmed). The ground-truth probe is
REMOVED (`_dreame_probe.py` deleted; the decoder is the real reader).

DONE: (2) raster render `ba02b385`, (pose) `ac761c4e`. REMAINING roadmap:

(3) **"Not reached" — via the PHASE-RUNNER, NOT a bypass. NEXT.** SCOPED this session:
  - `record_completed_room` does NOT fire for Dreame — `active_jobs.vacuum.robin.Main` after a
    completed Kitchen run had `queue_room_ids=[3]`, `status=completed`, `finalized=true` but
    `completed_room_ids=[]`. So per-room attribution must be WIRED; existing job tracking is empty.
  - The map's per-run cleaned overlay is NOT on `selected_map` (proven: no CLEAN_AREA pixels /
    `cleaning_map_data` / `cleaned_segments` across a whole run). It's on the camera attrs
    (`active_segments=[3]` = the run's rooms) + the cleaning HISTORY (`_cleaning_history[0]`,
    `cleaning_history_picture` flags Completed/Interrupted). So the "map cleaned-overlay" approach
    (A) needs the history map, not the live one.
  - **CHRIS'S STEER (2026-08-30): do NOT make Dreame's `job_segmenter` a true noop.** Keep the
    phase-runner engaged — it's needed for (a) WAIT tracking (mop-wash/prep bounces) and (b) the
    foundation for **deeper per-phase settings control from the app settings**. So build a REAL
    Dreame job-segmenter (segment the run by `current_room` transitions + counters, like Eufy's
    `eufy_counter_v1` on Dreame's signals) feeding the phase-runner → per-room `cleaning_seconds`
    + waits; the decoder's `area_m2` is the surface value. `current_room` tracks correctly
    (Dining→Kitchen→Dining this run). This supersedes the `active_segments`-bypass idea.
(3b) **DEEPER GLOBAL SETTINGS (the phase-runner payoff, per Chris's app tour 2026-08-30).**
  The app's Custom (global/run-level) tier, per cleaning mode — distinct from the per-room
  `settings_write` we built. Already modelled: Suction (Quiet/Standard/Intense/Max = our
  fan_speed quiet/standard/strong/turbo — app "Intense"=strong, "Max"=turbo), Mop Wetness (1–32
  = wetness_level), Route (Quick/Standard/Intensive/Deep — count is MODE-DEPENDENT: 4 in
  Mop/Mop-after-Vac, 2 Quick/Standard in Vacuum & Vac+Mop, confirming our route finding),
  Cleaning Mode (vacuum/mop/vacuum_mop). NEW to add: **CleanGenius (auto mode)**, **"Mop after
  Vac" mode**, **Max Suction Power (one-time boost toggle)**, and **Mop-Washing Frequency —
  a WASH SETTING with options By Area / By Time / By Room** (Chris 2026-08-30: NOT part of the
  phase-runner; a global device config to surface). Likely driven via Dreame global
  selects/switches/numbers (same as the per-room writes). SEPARATELY, the phase-runner (kept
  non-noop) tracks the run's ACTUAL per-phase timings + waits — the job_segmenter reason,
  distinct from the wash-frequency setting.
(4) command palette — `vacuum_goto`/`vacuum_clean_spot`/`vacuum_clean_zone`/ "furniture clean"
  (= clean_zone at a furniture bbox) + `vacuum_set_furniture` write, all on the decoder's transform.
(5) **Heading** — we don't emit `robot_heading`, so the dot's arrow defaults NORTH; real facing is
  south (Dreame renders a "cone of vision"). Fix = emit `vacuum_position.a`, but the a→`rotate(deg)`
  convention (card: `renderers/map.js:504`, CSS-CW, 0=north) is UNKNOWN — needs a run with the angle
  capture armed BEFORE start (my capture missed the moving data, only got docked a=0). Cone-of-vision
  is a nicer card render style than the triangle.
(6) bespoke furniture RENDERER (view work, `.claude/notes/DESIGN-bespoke-furniture-renderer.md`) —
  furniture data now flows to it; Dreame furniture is read+write (`vacuum_set_furniture`).

--- RECON (below) is now HISTORY; the decoder above supersedes it. ---
Chris: "map attribution now, then we should have the room rasters to render it our way."
Drives the **"Not reached" bug**: `renderers/job-summary.js:200-224` prints "Not reached"
when a room has NO per-room metrics; Dreame declares noop attribution → `area_m2=0` → every
cleaned room reads "Not reached" (a conflation, not a miss). Fix = a real per-room area
source = the decoder.

**The decoder reads ONE structure → raster + rooms + pose together**
(`Z:\custom_components\dreame_vacuum\dreame\`, class `MapData` in `types.py:4459`):
- RASTER = `MapData.pixel_type` — dense numpy uint8 (width×height) grid, per-pixel segment
  id. Built by the bitmap unpacker `map.py:3962-4050` (`segment_id = pixel & 0x1F`). The
  `room_pixels` analog.
- ROOMS = `MapData.segments {id: Segment}` — bbox/name/center/area. ⚠ `Segment.outline` is
  ONLY the bbox rectangle and `.area = abs(x1-x0)*abs(y1-y0)` — rectangles, WRONG for
  L-shaped rooms. The decoder MUST use `pixel_type`, not outlines.
- GEOMETRY = `MapData.dimensions` (grid_size = pixel→metre scale → resolves the deferred
  `map_pixel_size: None`).
- POSE = `MapData.robot_position`/`charger_position` — FREE (same `camera.robin_map`
  `vacuum_position` sampled all session). The `camera_attrs` backend ALREADY turns these
  into robot/dock anchors, so the deferred live-pose reader (POSE_BACKEND, phase 4a.2) is
  poll-SPEED only, not correctness.

**Access fork RESOLVED but needs Chris's OK**: `pixel_type` is a numpy grid on the decoded
MapData OBJECT, NOT usable in HA state attrs (`as_dict()=asdict(self)` includes it, but the
compact `map_data_json` state carries only bboxes/pose). So the reader must reach the base
integration's DEVICE/COORDINATOR object (same object model our `set_cleanset` writes touch),
not the camera entity — a real coupling decision. I flagged it; **he has not yet ruled — get
his go before building.**

Scope + all proven findings: `.claude/notes/synthesis/dreame-port/SCOPE-per-room-attribution.md`.
Backend contract: `docs/dev/12-map-source.md` (a third brand stays a DECLARATION, never a
branch). Current declared backend = `camera_attrs` (renamed), Phase 4a: `supports_va_render`
False, card uses the device PNG.

### Release gate — #1707 now DOCUMENT-HANDLED (was: blocked on an upstream release)
NO `BRAND_REGISTRARS` row yet (brands.py holds the local-only switch for live testing) — but
#1707 is **no longer the gate.** LIVE-TESTED 2026-08-30 (details below): a device with a saved
map never bites; only an unmapped first-setup does, and the remedy is a reload. It ships as a
user-guide **WARNING** (landed: `docs/user-guide/11-setup.md` Step 1), not a code gate.
Remaining pre-ship items (Chris): maintenance guides in 18 languages, goto/zone/spot clean,
polish. The `BRAND_REGISTRARS` row is still the switch, and still Chris's call.

**Branch: `master`, commits ahead of `origin/master`, NOT pushed** (re-check `git log
origin/master..HEAD` — do not trust this line). `do-not-push` still exists; we are not on it.

⚠ Handoffs rot ONE WAY — written at the pause, never at the resume. Re-read the git log AND
`du -sh` the corpus before trusting any status line here. This file's own corpus number has
been stale twice now.

## ⭐ READ FIRST — the newest record supersedes older arithmetic

1. `.claude/notes/STATE-dreame-acquisition-channels.md` — **the current durable record**;
   its 2026-08-28 append covers the MOVA share-QR method, the self-audit, and the
   byte-audited count. Supersedes the corpus arithmetic everywhere it disagrees.
2. `.claude/notes/STATE-dreame-manual-corpus.md` / `-corpus-extraction.md` — older, still
   useful for the identity apparatus; distrust their numbers.

## ⭐ THE ONE RULE FROM THIS CAMPAIGN

**Trust the bytes; distrust every label.** Every "not-reached / dead-404 / absent /
non-robot" we produced was wrong at least once (see the wrong-label tally in the
acquisition note). Before believing any "absent", re-resolve it and SHA-match on disk
(`scratchpad/self_audit.py` is the tool). Never announce a "floor" without a byte audit —
we called one five+ times and were wrong five+ times.

**Corpus: 3,009 PDFs, byte-verified 717/741 models covered (96.8%) — CLOSED 2026-08-28.**
That is **100% of everything publicly reachable**. Per-key ledger:
`derived/coverage_final.json` (also `honest_final.json`, `coverage_scout.json`). Lives
OUTSIDE the repo at `C:/Users/CKing/Documents/durable/dreame-port-fixture/manuals/`.
Chris's ruling: **"those pdfs are not going to the repo."**

Remaining **24 = a phone-gate floor, NOT an effort gap**: 22 CN-only MOVA special editions
(上下水 / 精选·甄选 / 洁净世界·净界 / 水箱版) + 2 Mijia M30 (`xiaomi.vacuum.d102`/`d102cn`).
All 24 are gated by a mainland app (MOVA / Mijia) that requires **phone registration**. The
manuals are public OSS objects (`oss.iot.dreame.tech/pub/faq/…`, no auth) but the only handle
to their un-enumerable content-hash is the phone-gated app — so a VPN/CN-IP alone cannot
reach them (confirmed: the `:13267` API returns `Missing token` from a CN IP; auth ≠ geo).
The two live paths left are the phone-gated app (real-SIM registration) or a human in China
who owns one sharing a QR. See the acquisition note's **CAMPAIGN-CLOSED 2026-08-28** append
for the four closing techniques and every dead-end already ruled out — do not re-run them.

⚠ **NEVER RENDER A VERDICT ON AN EMPTY SAMPLE.** A check that measured nothing printed a
confident pass in a previous session (`0 <= 0 * 0.25`). Guard every summary with "did I
measure anything at all?"

---

## ⚠ THE GIT REPAIR — READ BEFORE ANY COMMIT

**HEAD's tree contained exactly ONE file this morning.** The five unpushed
`notes(dreame)` commits had each written a tree containing only
`STATE-dreame-manual-corpus.md`; every other file was recorded as deleted. `origin/master`
was intact; the working tree was intact; only the commits were wrong.

Repaired by replaying all five with `commit-tree` onto `496a57d6`'s tree, preserving
messages, authors and dates:

```
9a735705 -> 905cf190    2c0a33ab -> a2aad2ca    5096d3f2 -> d267d59c
e08944cb -> 460a4c0d    9b8c77d7 -> 19740ffb
```

Verified after: note blob identical (`2a0ca784`), all five messages preserved, 1345 files,
0 PDFs, clean tree. Old tip `9b8c77d7` is recoverable via reflog. Nothing on disk changed.

⚠ **THE LIKELY CAUSE, AND IT IS STILL LIVE.** `git add` on a TRACKED file under
`.claude/` **succeeds but exits 1** — `.gitignore:83` carries `.claude/` and git prints
ignored-path advice regardless of the file already being tracked. Any `git add ... && git
commit ...` chain therefore stages the file and then SILENTLY SKIPS THE COMMIT. That is
almost certainly how the `read-tree HEAD` seeding step got skipped five times in a row.

**Do not chain add and commit with `&&` for anything under `.claude/`.** Run them as
separate statements and check `git ls-tree -r HEAD --name-only | wc -l` (expect 1346)
after every commit.

---

## WHERE THIS STOPPED

Paused cleanly. Working tree clean except six untracked `scripts/dreame_*.py`. Suite not
re-run this session — no Python behaviour changed until the last commit, and that commit
is inert data with no importer.

```
38ede994  feat(dreame): room-profile vocabulary, captured from a live device
a6bb183e  notes(dreame): correct the -1 rule - it is a (robot, dock) pairing
de8d7129  notes(dreame): the 51% caveat was pointed the wrong way - it is a floor
5b7ceb11  notes(dreame): the document is the unit - one code, up to six SKUs
80b2ffa2  notes(dreame): coverage vs the supported surface, and where the wandering was
```

plus the five replayed commits beneath them. Tree: **1346 files, 0 PDFs.**

---

## THE FRAMING CHRIS GAVE, WHICH REFRAMES EVERYTHING ABOVE

> "this was a pre stage i was trying to have it all ready for when upstream lands the fix
> for all others to be able to use VA"

**VA = the integration itself** (`docs/dev/design/shipped/map-state-source.md`: "VA-owned
reader", "the VA owns the frame"). NOT Voice Assist — the `VA:` in
`voice-assist-wizard.md` is only a speaker label in a transcript. Do not confuse them.

So the whole Dreame campaign is the **gate-independent half**, exactly as
`adapters/dreame/__init__.py` already says: *"upkeep guides, and later the model/family
metadata"*. #1707 was the gate; it is now **DOCUMENT-HANDLED** (below).

**#1707** (upstream Tasshack/dreame-vacuum, still OPEN): `_init_data()` clears `_capability`
and `_aes_iv`, breaking map decode after an empty map. **RESOLVED to document-handled via a
live test 2026-08-30** (transcript: `scratchpad/dreame_1707_test_transcript.md` — session-local,
re-export). The un-patched reproducer was confirmed LOADED (`.pyc` carried the marker string),
then every map op was swept on Robin WITH a saved map — startup, phased clean, new-map
create/save/segment/rename, map switch, entity reload — and **none bit** (marker never fired,
decode never broke through frame 128). The upstream issue states the exact trigger: **a
freshly-added device with NO saved map**, whose empty 2×2 first frame wipes iv/capability →
decode broken until an **integration reload**. So it is scoped to unmapped-first-setup ONLY — a
mapped device never reaches it. It is a **WARNING, not a VA blocker**, shipped as a user-guide
setup note (`docs/user-guide/11-setup.md` Step 1: map-first + reload-to-recover). (The `str+None`
crash seen mid-test was unrelated `samsungtv_smart._get_source`, not dreame — a red herring.)

⚠ **Chris still has the local patch** — `Z:\custom_components\dreame_vacuum\dreame\map.py`,
restored byte-identical after the test (backup: `C:\Users\CKing\Documents\_dreame_map_1707test_bak_20260830\`);
loads on his next restart. It is now a convenience, not a release requirement. **Dreame adapter
DEV DOC deferred** until the adapter settles (goto/zone/spot + guide i18n + polish land first).

---

## WHAT LANDED TODAY: `adapters/dreame/vocabulary.py`

`room_profiles` is the ONE adapter block where registration HARD-FAILS if absent
(`docs/contributing/porting-guide.md` §10) and Dreame had none. It now exists, DATA ONLY,
still no `adapter.py` and still no registrar row. `BRAND_REGISTRARS` is still
`['roborock', 'eufy']` — verified after the commit.

**Every value was read off the live device**, not a manual — `vacuum.robin`, via
`Z:\.storage\core.entity_registry`. The manuals do NOT carry these enums; the Aqua10
manual defers to "Cleaning Mode settings in the app". Captured vocabulary is kept at
`scratchpad/dreame_live_vocabulary.json` (scratchpad is session-local — re-capture rather
than trust a copy).

Three traps found in the capture, all documented in the file:

1. **The vacuum entity disagrees with the select.** `fan_speed_list` says `Silent`;
   `select.*_suction_level` takes `quiet`. A different WORD, not casing.
2. **Per-room lists are not the global lists.** `cleaning_mode` is 4 globally / 3 per
   room; `cleaning_route` is `quick|standard` globally / `standard|intensive|deep` per
   room.
3. **Dreame has NO no-water word.** `mop_pad_humidity` is three wet states;
   `wetness_level` bottoms out at **1**, not 0.

`FLOOR_TYPE_WATER_DEFAULTS` is therefore **declared EMPTY** rather than inventing an
`"off"` the dispatch `options_key` filter would silently drop (the Roborock capital-O
"Off" defect). The carpet-water-off guarantee still holds via the MODE DOWNGRADE in
`profiles/manager.py` — a carpet room's `clean_mode` is rewritten to `"vacuum"`, which
maps to Dreame's `sweeping`; after that `is_mop` is False so `queue_engine` never writes
water either. Two gates, neither needing a no-water value.

⚠ **DO NOT "FIX" THIS WITH VERSALIFT.** Chris's ruling: *"versa lift is pretty good but
not every vacuum has it."* Mop lift is a PER-MODEL fact; leaning on it moves a framework
safety property onto firmware that may be absent. Same reasoning as the Roborock
`edge_mopping` ruling. The mode downgrade works on every Dreame ever made.

---

## COVERAGE, MEASURED AGAINST CHRIS'S SCOPE RULING

Scope: *"we will support in general what they have listed"* — Tasshack's
`supported_devices.md`, held locally at `durable/dreame-port-fixture/catalogue/`.
**741 models / 386 names.** (A WebFetch of the same page returned 344 models and asserted
a total of 511. Both wrong. The local copy is authoritative.)

| | models | of 741 |
|---|---|---|
| guide authored (7 families) | 202 | 27% |
| manual held | 383 | 51% |
| **held but NOT authored** | **261** | **35%** |
| no manual, no guide | 278 | 38% |

**The 261 is the cheapest work left** — 98 names, no sourcing needed, and not fringe
hardware: `matrix10ultra` (13 models), `p70proultra` (8), `s70ultraroller` (7).

Every authored guide is `dreame.*`; all 154 non-Dreame IDs (mova 102, xiaomi 25,
trouver 13, ijai 11, deerma 2, szkj 1) are uncovered — but 85 of them are authorable from
manuals already on disk.

---

## THE DOCUMENT IS THE UNIT

A manual is scoped to a SERIES and declares one base regulatory code plus N numbered SKU
variants. **N reaches 6.** `RLX85CE` covers X50 / X50 Ultra / X50 Ultra Complete /
GoVac 800 in one document. So ~202 open names is ~100 documents, not 202.

**Track vs Roller costs exactly ONE part.** 27 maintenance rows shared with identical
intervals; the delta is `Fluffing roller` (Roller only), a washboard-filter interval, and
a relabel. A Track manual is ~96% of the upkeep content for the whole Aqua family.

**The code collapses rebadges** — the census payoff:
`RLX95CE` = Matrix10 Ultra = X50 Ultra MatriX · `RLX63CE` = X40 Ultra = GoVac 508 ·
`RLX85CE` = X50 = GoVac 800 · `RLM83HE` = mova lr10 prime / nutripal10 / pf10 / lb10.

⚠ **`-N` IS A (ROBOT, DOCK) PAIRING, NOT A BUNDLE.** An earlier commit today
(`5b7ceb11`) generalised "one robot, one dock" from the Aqua10 case; an adversarial pass
refuted it and `a6bb183e` corrected it. `doc_facts.json` measures 5 families with
DIFFERENT docks vs 3 sharing one. **The S-series rule is the norm; Aqua10 Track is the
exception.**

X-series shape, for reference: X20 predates the `RL*` scheme entirely (no code);
X30 Ultra `RLX56CE` (1); X40 Ultra `RLX63CE` (4); X40 Master `RLX73CE` (separate machine);
X50 `RLX85CE` (6). And **`RLX` does not mean "X-series"** — it also carries L20 Ultra
(`RLX41CE`) and L40 Ultra (`RLX53SE`). Weak hint, not identity.

---

## ⚠ THE MAPPING ALREADY EXISTS — DO NOT RE-DERIVE IT

This session wasted effort regex-scanning `manual_text_cache.json` to build a 64-code map.
The background jobs had already written better:

* `derived/corpus-manifest.json` — 2,015 entries; 365 with `reg_codes`, 326 with
  `names_printed`, 251 with BOTH; 96 distinct codes; yields **84 code→names groups**.
* `derived/doc_facts.json` — **351 Declaration-of-Conformity certificates** →
  `{model, base, product}`; 156 distinct models, 170 distinct base stations. This is the
  AUTHORITATIVE model→dock source.

These ARE the "model/family metadata" the adapter docstring names as the next
gate-independent deliverable. **Read the manifest; do not re-derive from text.**

---

## CORRECTIONS MADE TODAY — DO NOT RE-BREAK THEM

1. **The 51% is a FLOOR, not an inflated figure.** Resolved by READING
   `scripts/dreame_corpus_name.py` rather than inferring: `--devices` is required and the
   matcher is built from `supported_devices.md`, so the namer cannot emit a name outside
   the catalogue. That makes "0 corpus names outside their list" a TAUTOLOGY, not evidence
   of circularity. The 51% counts only COVERED (manual TEXT names the model), excludes
   ATTESTED (filename-only claims), and can only MISS. Earlier guidance not to spend it
   was wrong in DIRECTION.
2. **`matrix10ultra` was ALWAYS in the held-but-not-authored bucket**, never "uncovered".
   A restatement in conversation said otherwise; that was a slip.
3. **"Aqua 10 Pro Roller" is NOT corpus-attested.** No document prints it. The held Roller
   manual prints "Aqua10 Ultra Roller" (`RLH71DE` / `RLH71DE-1`). The only "Pro Roller"
   anywhere in the corpus is S70 Pro Roller (`RLZ11HE`), a different machine. The
   Pro/Ultra-share-a-code pattern IS evidenced on the TRACK side (R2527 vs R2527B) but not
   for Roller. Chris's find stands alone — needs a second source.
4. **A code merge CANNOT expand coverage** — tested, +0 models, +0 names. Codes are
   observable only through manuals already held, whose names are already counted. Only the
   registry can grow the number beyond the corpus.

---

## SCOPE-CREEP VERDICT (Chris: "my god we had some massive creep")

**The hunting list never wandered.** All 202 open names on the Dreame Hunting List
artifact are on the supported list — 202/202, zero off-list, 287 models behind them. The
fence held exactly.

What grew past its brief was the identity apparatus around it (CCC census, registry walks,
code taxonomy, the 2,133-article support-site walk). **The corpus and the open hunting list
overlap by SIX names** — 20 GB answered the easy half; the hard tail was never going to
come from PDFs, which is what the notes' own "reg codes matter more than manuals" already
said.

---

## STANDING LESSONS FROM THIS SESSION

⚠ **A probe that answers uniformly is broken, not informative.** Three times:

1. Provenance check v1 used `difflib` longest-contiguous-match and flagged **all 156**
   strings including verbatim ones — PDF extraction interleaves columns, so no long
   contiguous run survives. Bigrams survive it.
2. The language probe returned **zero languages for every manual**. It sliced only the
   tail of the extracted text; footers are not last in content-stream order.
3. Its fixed version still under-reported, because **single-language regional editions
   carry no ASCII footer code at all**. RU / JA / ZH-Hant were nearly reported absent
   with the Cyrillic, Kana and Han plainly in the file.

**The fix that generalises: ablate the probe against something independently known.**
The language probe is trustworthy only because it recovers exactly what each filename
claims (`R2489A-X50_Series-EN_DE_FR` → EN, DE, FR).

⚠ **An exemption needs its own floor.** The provenance checker waved through any
component/kind pair on the recast list — a wholly invented sensor step would have been
labelled "recast" and passed. Now floored at 40%; fabricated text scores 0%.

⚠ **Exit codes lied repeatedly in the previous session too** (`tail`'s status, a
background wrapper's last command, a PowerShell `Select-Object` pipeline). Read the
COUNT LINE (`4720 passed`), never the exit code.

---

## THE ISSUE #55 ARC, IN ONE PLACE

A support report turned into three defects of the same family — **naming a cause we
could not see** — and one architectural gap.

1. **`ServiceNotSupported` folded into "failed"** (`b39b7395`). A permanent refusal was
   dressed as a transient fault with a bug report attached. He filed the report.
2. **The diagnostic could not see WHY** (`52ba1c4b`). The room-source cache recorded
   only SUCCESSES, so a refusal left no trace and the self-check inferred the reason
   from the shape of the entity list. Now the outcome is recorded at the single point
   every service-source exit funnels through, and read rather than deduced.
3. **A fallback that yielded a BRAND'S WORD.** The self-check's `else` branches named
   the Eufy app and the eufy-clean fork unconditionally — issue #46's defect, fixed in
   the import message and left alive in the sibling path. De-branded WITHOUT deleting
   the advice: a Eufy owner on the reduced transport genuinely needs that fork, and the
   honest discriminator is `has_segments` (the transport signature), not the label.
4. **Two causes, one signature.** The job-active warning asserted capability-gating
   (#173282) as fact. For a B01 device that is simply wrong. It now names both and
   asserts neither.

⚠ **BOTH OF MY OWN DEFECTS HERE WERE CAUGHT BY EXISTING TESTS, NOT BY REVIEW** —
`brand.lower()` on an Optional[str] (which would have made the whole self-check vanish
silently, because its caller catches everything into `{"error": ...}`), and de-branding
that dropped real advice for brandless Eufy installs. Both were invisible on a read.

---

## TOOLING BUILT (both durable, both in `scripts/`)

* **`pdf_layout_dump.py`** — reconstructs visual reading order from PDF text matrices.
  **There is no rasteriser in this environment** (no poppler, no PyMuPDF), so the
  `Read` tool cannot render PDF pages; this is how manuals get read. Makes a
  three-column care page legible.
  `python scripts/pdf_layout_dump.py MANUAL.pdf 22-30`
* **`verify_dreame_guide_provenance.py`** — scores every authored string against its
  source manual. 264 strings, 0 defects, 15 known recasts. **Cannot be a CI gate** —
  the manuals are vendor copyright and stay out of the repo.

---

## WHAT IS NOT DONE

* **261 supported models (98 names) have a manual on disk and NO guide written.**
  This supersedes the old "22 of 26 platforms" line — that count predated the 741-model
  supported surface. No sourcing needed for any of them; see COVERAGE above. Two of the
  98 are ready to author right now from manuals Chris hand-delivered today:
  `aqua10_ultra_track` (R9528A, RLR81CE/-1) and `aqua10_ultra_roller` (R9535,
  RLH71DE/-1). Costs ~15 components, of which FOUR are new to the library:
  `fluffing_roller` (Roller only), `omnidirectional_wheel`, `retractable_legs`,
  `clean_water_tank`.
* **`BRAND_REGISTRARS` row — still the release switch, still Chris's call.** #1707 no longer
  gates it (DOCUMENT-HANDLED 2026-08-30 — see THE FRAMING above). Remaining pre-ship: guide
  i18n (18 langs), goto/zone/spot clean, polish.
* **Dreame i18n** — see above. Recorded, not started, needs Chris's go.
* **`ADAPTER-CONFIG.generated.md` is committed but NOT freshness-gated** — see
  `POST-2.1.0-deferred.md` entry 5. Not in `GENERATORS`, generator still untracked,
  measured decay 364 lines in ~2 days. Fix is one `Generator(...)` entry plus a
  force-add. Held out of 2.1.0 deliberately.
* **Issue [#55](https://github.com/kingchddg901/Vacuum_Agent/issues/55)** — DIAGNOSED
  AND FIXED (`b39b7395`, `52ba1c4b`), **REPLIED AND CLOSED 2026-08-26** as
  `NOT_PLANNED` (comment `5418743449`). Nothing outstanding. The text sent is kept at
  `.claude/notes/ISSUE-55-reply-draft.md`, marked POSTED — do not send it again.

  Root cause: a Roborock Q7 M5 is a **B01-protocol** device. HA routes it to
  `RoborockQ7Vacuum`, whose `get_maps()` is a stub raising `ServiceNotSupported`
  unconditionally (`components/roborock/vacuum.py`, 2026.8); the Q10 class is identical
  and only V1 implements it. B01 devices also get no `selected_map` select and no binary
  sensors at all. Our reading of his device was CORRECT; what was wrong was the cause we
  named and what we told him to do about it.

  ⚠ **THE FIX DOES NOT MAKE HIS VACUUM WORK** — it changes what he is TOLD. Chris's
  point, and the draft says it outright: "we fixed it" reading as "your problem is
  solved" would have him update, watch the import stop again, and conclude we lied.
* Background chip pending: split `dreame_upkeep_guides.py` (1099 lines) into a package.
  "Not yet, revisit at N families" is a legitimate answer to record.

* ⚠ **FOR CHRIS — 209 OF 223 NOTES ARE UNTRACKED, AND THE TRACKED INDEX CITES THEM.**
  Measured 2026-08-25, not acted on. `.claude/` is gitignored by design and the 15
  tracked notes were force-added one at a time as they became load-bearing, so this
  may be entirely deliberate. But the shape is worth a decision:

  - `INDEX.md` IS tracked and links to **93** notes. All 93 resolve on disk — the
    corpus is intact and the index is accurate **locally**.
  - **81 of those 93 point at files that do not exist in the repo.** To a fresh clone,
    or after a `git clean -fdx`, the index is 87% dangling pointers.
  - Same class as the `.claude/generated-docs/` finding recorded below, which cost a
    red CI gate on the release tip — a `.gitignore` on `.claude/` silently excluding
    something the tree depends on.

  **Not fixed here, deliberately** — force-adding 209 notes is a decision about what
  becomes public, not a cleanup, and some of it is unfiltered working thinking. Only
  `synthesis/dreame-port/MANUAL-INVENTORY.md` was force-added this pass, because it was
  corrected today and the tracked index now cites it as authority on a live question.
  The options are: leave as is (notes are local memory), track the ones INDEX cites, or
  stop citing untracked notes from a tracked index.

---

## RECIPES FOR RESUME

**Tests only in Docker** (Windows `python -m pytest` dies at `import fcntl`; piped to
`tail` reports exit 0 for a suite that never ran). Use **PowerShell** — Git Bash mangles
`-w`:

```
docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/w" -w /w eufy-vacuum-test:latest python -m pytest tests --no-cov -p no:cacheprovider
```

The `tests` argument is load-bearing; bare `pytest` skips `tests/adapters`.

**Bundle rebuild** after any `src/**` change: `npm run build:deploy`.

**Commit protocol**: private `GIT_INDEX_FILE`, `read-tree HEAD`, add + commit, then
`git reset -q HEAD -- <SPECIFIC PATHS>`. NEVER `-- .` (broadcasts a false-delete across
the tree; recover with `git reset --mixed HEAD`). `.claude/` is gitignored, so notes
need `git add -f`.

⚠ **AND `git add` EXITS 1 ON A TRACKED `.claude/` FILE EVEN THOUGH IT SUCCEEDS.**
`.gitignore:83` carries `.claude/`, so git prints ignored-path advice and returns
non-zero regardless of the file already being tracked. `git add X && git commit ...`
therefore stages the file and SILENTLY SKIPS THE COMMIT. This is the most likely cause
of the tree corruption described at the top of this file. Run add and commit as
SEPARATE statements, and verify with:

```
git ls-tree -r HEAD --name-only | wc -l     # expect 1346
git ls-tree -r HEAD --name-only | grep -c '\.pdf$'   # expect 0
```

**Three ratchets live**:
- New test file → a row in `docs/testing/subsystems/*.md` required.
- Bare `MagicMock()` for a handler dependency → `create_autospec(spec_set=True, instance=True)`.
- Docs are a release gate after 2.1 (Chris's ruling) — not per-push.

---

## RELEASE STATE — 2.1.0 SHIPPED 2026-08-25

Tag `v2.1.0` → `2b03c140`, marked latest, not a pre-release, so it reached every HACS
default-store user. Deployed full-tree to `Z:\`, clean load.

**The two things only the first push could find** (63 commits had accumulated with
nothing pushed, so two gates went red on the release tip that five audits and every
local run had passed):

1. `check_generated_docs.py` — `THEME_TOKEN_USAGE.md` stale from the banner fix's line
   shifts. Fixed `87942de6`.
2. `test_adapter_config_parity.py` — FileNotFoundError on CI ONLY. `.gitignore` carries
   `.claude/` and the file never got its `git add -f`. **All 54 files under
   `.claude/generated-docs/` were untracked — that gate had never run in CI once.**
   Fixed `b101030f`; the on-disk copy was 364 lines stale and was regenerated rather
   than frozen.

⚠ A local visual run without `VISUAL=1` reports `31 skipped, 1 passed` and reads
exactly like a pass. `card-visual.yml` runs `visual device-theme` — BOTH.

Earlier release-session detail (the 17-task list, the three frontend i18n/RTL defects
in `1f153481`, the sequence-toggle row in `89195039`) is in those commit messages and
in `POST-2.1.0-deferred.md`; it is not repeated here now that 2.1.0 has shipped.

---

# 2026-08-27 — SECOND PAUSE (restart). Read this before the older sections.

**Branch `master`, 25 commits ahead of origin, still unpushed. Tree 1352 files, 0 PDFs.**
Working tree clean except the same six untracked `scripts/dreame_*.py`.

## What landed today

1. **`feat(dreame)`: the two Aqua10 families** (`258b69f2`). Nine families now. They are
   NOT one family with a spare part - three procedures differ (washboard, mop assembly,
   mop compartment). Provenance gate: 93 strings, 0 defects.
   ⚠ The provenance verifier is broken for the ORIGINAL SEVEN families - the corpus
   rename moved every source file, so all seven read "missing manual".

2. **`feat(dreame)`: document -> supported-models cross-table** (`a4714332`).
   `derived/doc_model_crosstable.{json,tsv}`. 2015 docs, 639 with an identity signal,
   422 resolving to a model. Found 17 robots misfiled in `unclassified`.

3. **Diagram fingerprinting: TESTED, RETRACTED, CLOSED.** See
   `.claude/notes/FINDINGS-diagram-fingerprint.md` - read the CLOSED section at the
   bottom, not the numbers above it. Chris's verdict on corrected renders:
   *"dead easy to eyeball, almost impossible to automate."* The first conclusion was
   right and its evidence was worthless - three independent extractor bugs.

4. **Clone detection from DECLARED asset identity** (`dde6ca96`, `5b672614`,
   `27dc5236`). Adobe stamps every placed illustration with `xmpMM:DocumentID`. Verified:
   92% of repeatedly-placed assets have a constant path-operator count. 31-37x lift over
   a 2.17% base rate. Full corpus: `derived/clone_pointers.json`, 232 pairs.

5. **Procedure shape** (`3144fab8`) - and ⚠ the first version measured the WRONG THING.
   It read the service-interval table; Chris: *"I don't care about the interval. I care
   about the steps."* Replaced by ACTION SEQUENCE, which calibrates far better
   (same-machine median 0.794 vs different 0.390, against intervals' 1.000 vs 0.667).

## The one cross-name pair that survives all three signals

    S70 Pro Roller (RLZ11HE) x S70 Ultra Roller (RLZ52EE)
    artwork 4 (the WEAKEST link measured) | action shape p99.8 | text 1.000 IDENTICAL

Contradicted, and they were the LOUDEST artwork pointers: `M40 x X20+` (35 shared assets,
action shape p3.2) and `L10s Pro x M40` (p4.2). **Artwork proposes, procedure disposes.**

Still undecided, with the text blocks already sent to Chris:
`D20 Pro (RLD43SA) x E30 Pro Plus (RLE31SD)` - artwork 21, action p70.6, text 82%.

## The composition model (design, not yet built)

Everything decomposes into small key spaces, which makes i18n mostly LIFTING rather than
translating - the manuals already carry 6-34 language editions of the same content at
computable offsets, with the language code printed on the page.

    interval:  [action] + [frequency] + [numeral] + [unit]
               ~6 actions, ~4 frequencies, integers (not keys), 4 units
               `repetition` is a TOKEN not a number, so "each_use" and "6-12" are
               ordinary values, not special cases
    procedure: a sequence of [action][object] pairs

⚠ MAKE THE KEY THE WHOLE PATTERN, not the word "every". Japanese puts it as a SUFFIX
(`6 ～ 12 カ月ごと`, `2 週間に一度`) so concatenating a prefix produces broken Japanese.

Validated against the nine authored families: `main_brush` reduces to ONE skeleton with
one node of difference (Group B has brush end-covers). `dustbin`'s six variants are one
skeleton plus two booleans (`has_robot_cover`, `has_dust_box_cover`). `washboard` looked
like it resisted composition and does NOT - Chris called that correctly; all four share
`exit station -> remove washboard -> [CLEAN] -> reinstall -> return robot` and only the
`[CLEAN]` sub-procedure varies, by hardware.

⚠ `retractable legs`, `side brush extension` and `MopExtend` have NO maintenance
procedure anywhere in the corpus - labels and one table row (`Clean it as needed`) only.

## App API investigation

See `.claude/notes/STATE-dreame-app-api.md`. Headline: **the HA model string IS the
document code** (`dreame.vacuum.r2469a` -> R2469A), so HA model -> R-code -> document
works with no network call at all. The API was never reached; a Wireshark SNI capture was
in flight at the restart.

