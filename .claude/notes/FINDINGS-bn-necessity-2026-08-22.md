# BN necessity — does this file need break notation at all?

**Assessed 2026-08-22. 42 files over 800 lines with no BN boundary. Answer: 41 are ONE IDEA,**
**one needs a boundary.** Written down so it is never re-derived — the per-file verdict is
exactly what was missing when the managers were assessed and only the framing survived.

---

## The correction that produced this pass

The BN placement pass reported 42 large files as a backlog *needing sections designed*. That
framing was wrong and Chris named it:

> *"each file gets looked at for if it even needs BN. 800 lines is not impossible to be a
> single idea."*

Using line count as a proxy for *has multiple subjects* is the same error as counting findings
instead of scopes: it measures something adjacent to the question and reads as if it answered
it. **Length is not evidence of structure.** A style sheet, a string table, one renderer, one
state machine can each be thousands of lines and still be one subject.

## The test

A BN boundary is an ADDRESS. It earns its place only if a document would need to point at that
region SEPARATELY. Sections invented to break up length are worse than nothing: they add false
structure and make the notation say something untrue about the code.

- **To answer ONE_IDEA** — name the idea in one sentence. If it needs an *and* joining unrelated
  things, it is not one idea.
- **To answer NEEDS_BN** — name at least two SUBJECTS (not two functions) that a reader would
  come looking for independently and that do not share the file's core state or vocabulary.
- *"It has 72 functions"* is not an argument. Many methods serving one lifecycle is one lifecycle.
- A proposed section that can only be named **"helpers"** or **"utilities"** is the tell that no
  separate subject was found.

## ⚠ THE ASYMMETRY RUNS THE OPPOSITE WAY FROM A NORMAL REVIEW

On the defect ledger the dangerous direction is a wrongly-CLOSED row: known work is dropped and
nobody looks again. **Here it is the reverse.** A file wrongly left whole costs one reader one
extra look. A file wrongly CARVED UP bakes false structure into the anchor registry permanently,
and documents get written against sections that were never real subjects. So the adversarial
pass attacked only the SPLIT verdicts, and was told to default to overturning.

**That is what the numbers say happened: 18 splits proposed, 17 overturned, 1 survived.** Trusting
the first pass would have carved up 18 files and been wrong about 17 of them.

### Why the overturns kept succeeding — the three recurring arguments

1. **It is a MODE, not a sibling.** `styles/map.js` and `renderers/map.js` were both proposed as
   "live map + config editor". Both overturned on the same evidence: the config view emits the
   SAME container (`evcc-map-container--config`), and `render-cycle.js` says in its own words that
   MAP_CONFIG *"is rendered without a tab"*. One surface in two modes.
2. **The cut orphans the thing that joins the halves.** `styles/setup.js`'s proposed boundary sat
   below `.evcc-setup-subtabs` — the strip that switches between the two regions would have
   belonged to neither. A boundary that strands the joiner is the wrong boundary.
3. **One data structure is one idea by construction.** Eight `src/styles/*.js` files and
   `adapters/config_schema.py` are a single exported literal with zero functions. There is nothing
   to be two of.

## The one that survived

**`src/renderers/setup.js`** — two sub-tabs, and the refuter said *"I tried to argue this one down
and could not."* The code had already conceded it: at `:999` the file captures the original
800-line renderer and wraps it, with the comment *"wrap rather than edit it so a 700-line renderer
stays untouched by the addition of a **sibling view**"*. Two boundaries placed:

| token | section | at |
|---|---|---|
| `BN00X12B` | Setup steps wizard | `proto.renderSetupView` |
| `BN2P065F` | System entity bindings | `proto._renderSystemSubtab` |

No third boundary for the ~30 lines of sub-tab routing — that would be the over-sectioning this
pass exists to prevent.

## ⚠ It agrees with the manager finding already on record

`DESIGN-core-manager-gravity-rule.md` §3d measured the managers and concluded **"topologically
they already are post offices — this axis is FINE, do not spend on it"**. That predicts exactly
this result: a manager that is topologically a post office is ONE idea by construction, because
180 delegators averaging five lines are all doing the single job of routing. Every manager in
this pass came back ONE_IDEA, including `learning/manager.py` (3,069 lines) and
`battery/manager.py` (1,692). §4 of that same doc explains why two of them are large at all:
`phase_runner.py` and `active_job.py` RECEIVED extractions from core — history, not structure.

## ⚠ Two method failures in this pass, both mine, both worth keeping

**The batch list was hand-transcribed from printed output and lost a file.**
`src/renderers/theme.js` (1,474 lines) was never judged by the fan-out. Caught only by diffing
the candidate list against the verdict list. Derive a work list, never retype one.

**The consolidator keyed attack verdicts by BASENAME.** `manager.py` is the basename of four
different files here, so verdicts merged across them and the single surviving split silently
disappeared into an overturn belonging to a different file — reporting 41/41 ONE_IDEA. The count
check ("1 upheld" but zero rows shown) is what exposed it. Key by path.

---

## Per-file verdicts

### NEEDS BN (1)

- **`src/renderers/setup.js`** — Nominally "the Setup tab" — but two sibling sub-tabs live here: the onboarding step wizard, and a diagnostic table of which HA entity got bound to each internal role.
  - `Setup steps` at `proto.renderSetupView`
  - `System entity bindings` at `proto._renderSystemSubtab`

### ONE IDEA — no BN (41)

`*` = an agent proposed a split and the adversarial pass overturned it.

| file | the single idea |
|---|---|
| `custom_components/eufy_vacuum/adapters/config_schema.py` | The contract for a per-vacuum adapter config — every block an adapter may declare, stated as data, together with the walk that checks a config against it. |
| `custom_components/eufy_vacuum/adapters/eufy/adapter.py` | Everything the framework needs to know about a Eufy vacuum, declared as one config dict and registered for one entity at startup. |
| `custom_components/eufy_vacuum/adapters/eufy/segmentor.py` | Turn one Eufy map image into room segments by HSV clustering and morphological analysis. |
| `custom_components/eufy_vacuum/adapters/roborock/adapter.py` | Everything the framework needs to know about a Roborock vacuum, declared as one config dict and registered for one entity at startup. |
| \* `custom_components/eufy_vacuum/battery/manager.py` | everything the integration derives about one vacuum's battery from percent-level observations, held in the single per-vacuum record defined by `_new_record()`. |
| \* `custom_components/eufy_vacuum/core/error_tracker.py` | latching a vacuum's upstream error signals into per-run and per-device records — but the file also carries a stateless error-code classification seam that the tracker itself never calls. |
| `custom_components/eufy_vacuum/diagnostics.py` | Build the integration's Download Diagnostics dump — one redacted, read-only document describing what each vacuum's install actually resolved to. |
| `custom_components/eufy_vacuum/jobs/active_job.py` | ActiveJobTracker owns the one active-job record per vacuum+map through its whole life — the record's shape, every live device observation written into it, the current-room pointer it advance |
| \* `custom_components/eufy_vacuum/jobs/phase_runner.py` | executing a strict-order (sequenced) job, where each phase dispatches one room and the run advances phase by phase. |
| \* `custom_components/eufy_vacuum/learning/external_ingest.py` | turning a captured app-started (external) run into a pending review record the card resolves — which is what the module docstring claims and what only about half the file does. |
| `custom_components/eufy_vacuum/learning/job_finalizer.py` | Everything that happens to one run's record between job start and the moment the finalized record is durable on disk. |
| \* `custom_components/eufy_vacuum/learning/manager.py` | the integration's single entry point to the optional learning system, coordinating the history store, the finalizer, the stats rebuilder and the estimator. |
| `custom_components/eufy_vacuum/learning/stats_rebuilder.py` | Reduce one vacuum's completed-job history into every derived, persisted artifact its consumers read — job stats, room stats/baselines/transit, the jobs index, and the flat CSV exports. |
| \* `custom_components/eufy_vacuum/mapping/map_source.py` | pure, HA-free readers that turn a provider's own map segmentation into normalized 0-1 rendered-image-space room data, anchors and overlay layers. |
| `custom_components/eufy_vacuum/mapping/map_source_coordinator.py` | Dispatch every read of a provider's own map — static segmentation, live pose, render raster, verify probe — to the backend the adapter's `map_state_source` block declares, and cache the norm |
| \* `custom_components/eufy_vacuum/profiles/room_profiles.py` | resolve a room's effective cleaning settings from the adapter-declared profile catalog, the room's own overrides, floor-type constraints and the device's capabilities. |
| \* `custom_components/eufy_vacuum/setup/drift.py` | keep the per-vacuum setup_progress record — which setup steps are done, which rooms have drifted, and which room ids the user has rejected. |
| `harness/fixtures/gallery.js` | A catalogue of stub-state fixtures, each one shaping a single real tab render so every coloured branch of that screen lands co-present on one screenshot. |
| \* `harness/mount-entry.js` | The browser-side harness API exposed as `window.__evcc`, which puts the card's UI on a headless Playwright page and reports what actually rendered. |
| `src/bindings/theme.js` | Wires every control in the theme editor to the card's theme state and the backend theme services. |
| \* `src/cards/dashboard-card.js` | The standalone Dashboard Mode card bundle: the compact multi-room control element, plus the separate Lovelace editor element that configures it. |
| `src/i18n/en.js` | The English source-of-truth string catalog: every user-facing key the card can render, in one object. |
| \* `src/main.js` | The card's registration module: it defines the root Command Center custom element and, separately, the Lovelace visual config editor element that authors it. |
| `src/renderers/learning.js` | What the card says about the time/water estimator across a run's lifecycle — before it starts, while it runs, and after it ends. |
| `src/renderers/maintenance.js` | The vacuum's consumables: how each upkeep and replacement item's wear state is summarised, listed, and inspected. |
| \* `src/renderers/map.js` | Nominally "the map" — but it is two screens: the live map the user watches and taps, and the separate configuration editor that authors the room shapes that map draws. |
| `src/renderers/metrics.js` | The Metrics view: one learning snapshot presented through a set of filtered tabs. |
| `src/renderers/rooms.js` | The Rooms view: how the clean queue and the rooms in it are presented — the same rooms rendered as action-bar chips, as live-queue steps, and as tiles. |
| `src/renderers/theme.js` | The Theme editor's render surface: the preset selector, the mode bar, and the grouped token editor, with one control shape per token type. |
| \* `src/state/learning.js` | Nominally the card's learning/estimate state; in practice it is also the card's entire dashboard-snapshot mirror and the capability gates read by every other subsystem. |
| \* `src/state/map.js` | Nominally "card-local state for the map view" — in practice it is the parking lot for every independent store any map surface happens to need. |
| \* `src/state/rooms.js` | Nominally "all room-related state reads for the Rooms view" — actually the room data model AND the run-control state machine, interleaved. |
| `src/state/theme.js` | The card's theme-editor state: one `_themeState` container holding the backend-mirrored theme plus the editor's own view state, and every selector that reads it. |
| `src/styles/learning.js` | The learning subsystem's surfaces — the estimate/progress panel and everything that expresses how confident the card is in what it predicted or observed. |
| \* `src/styles/map.js` | Nominally "the map" — but it is two sibling screens: the live map surface shown in the Rooms view, and the separate full-screen map configuration/calibration editor. |
| `src/styles/mobile.js` | The mobile branch: everything the card changes when the shell is in a phone/landscape viewport. |
| `src/styles/modal-host.js` | The document.body modal host: because it sits outside the card's shadow cascade it must re-derive the whole modal token family for itself, and everything rendered inside it is styled here fo |
| `src/styles/rooms.js` | The Rooms view: the room-card grid and the queue-chip language that runs through every state a room or a queued job can be in. |
| \* `src/styles/setup.js` | Nominally "the Setup view" — but the view carries two sub-tabs, and the file carries both: the onboarding/config wizard, and the System entity-binding table. |
| `src/styles/theme-preview.js` | The Theme editor's live preview pane and every specimen inside it, styled so a token edit shows up on a truthful sample of the real product. |
| `src/styles/theme.js` | The Theme editor view: everything from its layout shell down to the individual token controls a user edits a theme with. |

---

## If you are re-running this

Candidate filter was `>= 800 lines AND no existing BN boundary`. That is a filter for *asking*
the question, not an answer to it — do not let it become the proxy again. The 175 boundaries
placed earlier the same day were a different job entirely: those sections ALREADY existed as
named comment sandwiches, so tokenising them decided nothing.
