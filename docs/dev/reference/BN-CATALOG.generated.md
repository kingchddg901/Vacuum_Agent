<!-- GENERATED FILE — DO NOT EDIT BY HAND. Regenerate: python scripts/gen_bn_catalog.py -->

# BN catalog — every break-notation anchor, by file

A `BN` anchors a **place**, not a claim — a region of a file that prose can address without the file being split. This is the card catalog of them: the name on the line beneath each one, and which documents cite it. There are deliberately no line numbers here — the citation form is `path#TOKEN` so that prose survives the code moving, and a column of line numbers would make this file drift every time any anchored file gained a line. The rule for when a divider earns one is in [design/shipped/notation-anchors.md](../design/shipped/notation-anchors.md) § `BN`.

**177 anchors in 38 files · 5 cited by at least one document · 0 with no name line.**

The tokens below are *data* — this file is excluded from the citation scan so listing an anchor here does not count as citing it. Cite from prose as `path#TOKEN` in backticks; the catalog deliberately never uses that form.

## `custom_components/eufy_vacuum/__init__.py` · 2

| token | section | cited by |
|---|---|---|
| BNACE45Q | Domain setup | — |
| BNMENBE8 | Config entry lifecycle | — |

## `custom_components/eufy_vacuum/adapters/eufy/constants.py` · 6

| token | section | cited by |
|---|---|---|
| BNRD9B1V | Mop wash debounce | — |
| BNWC83XR | Post-job water amendment timeout | — |
| BNM86HVH | Battery | — |
| BNGEQ16P | Water flow rates | — |
| BNKGEF7P | Physical tank measurements | — |
| BNZEYNKY | Wash frequency interval bounds | — |

## `custom_components/eufy_vacuum/adapters/eufy/vocabulary.py` · 1

| token | section | cited by |
|---|---|---|
| BNZZZXW7 | Fault policy (RF-DOCK) -- SOURCE, and whether the fault invalidates cleaning evidence | — |

## `custom_components/eufy_vacuum/battery/job_metrics.py` · 1

| token | section | cited by |
|---|---|---|
| BNWM5EZD | Helpers | — |

## `custom_components/eufy_vacuum/const.py` · 9

| token | section | cited by |
|---|---|---|
| BNPD8J3V | Service names | — |
| BNKPHT1G | Adapter config services | — |
| BNQKGHGD | Learning services | — |
| BNTFXJ1X | Setup services (panel-driven) | — |
| BNV2NJ50 | Mapping services | — |
| BN0JNMVV | Theme services | — |
| BN6DJDXS | Internal data keys | — |
| BN1ENC2F | Events | — |
| BNTM6TEN | Supported / tested | — |

## `custom_components/eufy_vacuum/core/capabilities.py` · 3

| token | section | cited by |
|---|---|---|
| BNSAZE8S | Entity lookup helpers | — |
| BN7SHBDE | Maintenance source detection | — |
| BNWETS61 | Public API | — |

## `custom_components/eufy_vacuum/core/manager.py` · 21

| token | section | cited by |
|---|---|---|
| BN9Y5WHJ | Callback registration / notification | — |
| BNHF6TXT | Vacuum / capability management | — |
| BN52YB62 | Water model helpers + estimation -- delegates to RunPlanManager | — |
| BNAQ6QDN | Active job tracking — delegates to ActiveJobTracker | — |
| BNNH89X5 | Dock actions — delegates to DockManager | — |
| BNTXYKSY | Room profiles — delegates to ProfileManager | — |
| BN13R22S | Queue / payload building | — |
| BNXJC33C | Run profiles — delegates to ProfileManager | — |
| BNKAQANF | Access graph — delegates to AccessGraphManager | — |
| BN078651 | Run planning -- delegates to RunPlanManager | — |
| BNASDHS6 | Room history cache and accessors | — |
| BNPN12E3 | Lifecycle / start status | — |
| BNA9T0JJ | Singleton-ownership helpers | — |
| BN990V7G | Job progress / control | — |
| BN5W62XG | Bounds-exit polling signal | — |
| BNR8RZFQ | Run anomalies: stall (hard) + running_long (soft) + skipped | — |
| BNT7JDBC | Upkeep / maintenance | — |
| BNCRE9Z8 | Onboarding — delegates to OnboardingManager | — |
| BN9KGAAA | Theme management - delegated to self.themes (ThemeManager) | — |
| BN40D32F | Dock events — delegates to DockManager | — |
| BN8XKZWY | Job start / run-profile start | — |

## `custom_components/eufy_vacuum/dock/manager.py` · 4

| token | section | cited by |
|---|---|---|
| BN77YS6F | Private helpers | — |
| BNVV5A75 | Dock action status | — |
| BN1T5E99 | Dock action dispatch | — |
| BNYMF7A6 | Dock event recording | — |

## `custom_components/eufy_vacuum/learning/estimator.py` · 17

| token | section | cited by |
|---|---|---|
| BNPZ4HQP | Tunable constants | — |
| BNKNJ83W | Helpers | — |
| BNTDS01E | Learning velocity | — |
| BNNKMW2Y | Confidence scoring | — |
| BNM44SMY | Overhead modeling | — |
| BNFGHYVM | Room stat lookup | — |
| BNZFXXB3 | Main estimator class | — |
| BNX0VKNC | Stale detection | — |
| BNZ7NT64 | Accuracy stats | — |
| BNEYFJA0 | Core estimate | — |
| BN8A2JMG | Per-room estimation | — |
| BNV5916D | Overhead | — |
| BN04S802 | Job-level confidence — min of all room scores (hard rule) | — |
| BNBCR902 | Job ETA | — |
| BNGPJPM7 | Battery readiness | — |
| BNB7HKSE | Next room shortcut | — |
| BNGCS4JP | Timeline reanchoring | — |

## `custom_components/eufy_vacuum/learning/history_store.py` · 2

| token | section | cited by |
|---|---|---|
| BNDGR3XF | Incomplete run log | — |
| BNWM3ZGR | Trouble rooms log | — |

## `custom_components/eufy_vacuum/learning/job_segmenter_engines.py` · 5

| token | section | cited by |
|---|---|---|
| BN55BATD | Canonical cross-engine contract. | — |
| BN0PA3DC | Protocol. | — |
| BNT4BNT4 | Eufy engine — counter-plateau, delegates verbatim. | — |
| BNJ4K8X5 | Noop fallback — for a future brand with no segmentable signal. | — |
| BN95SS8Y | Registry. | — |

## `custom_components/eufy_vacuum/learning/room_attribution_engines.py` · 5

| token | section | cited by |
|---|---|---|
| BNBYP2TY | Canonical cross-engine contracts. | — |
| BN8DV7XK | Protocol. | — |
| BN5KJ83S | Eufy engine — anchor + winding + swept-area; ports the validated prototype. | — |
| BNS27NK6 | Noop fallback — for a future brand with no usable pose stream. | — |
| BNKAY1T5 | Registry. | — |

## `custom_components/eufy_vacuum/learning/services.py` · 2

| token | section | cited by |
|---|---|---|
| BNMXS80A | Load incomplete run log (file I/O → executor). | — |
| BNGE63K1 | Start cleaning. | — |

## `custom_components/eufy_vacuum/maintenance/manager.py` · 6

| token | section | cited by |
|---|---|---|
| BNBFVSBR | Module-level pure helpers | — |
| BNXFRB65 | Pure-function status helpers | — |
| BN6QNPKK | MaintenanceManager | — |
| BN6NQY5J | Upkeep model metadata + guide helpers | — |
| BNNYPRQB | Upkeep snapshot | — |
| BNF7YZZ4 | Maintenance state / reset / remaining | — |

## `custom_components/eufy_vacuum/mapping/map_source_runtime.py` · 3

| token | section | cited by |
|---|---|---|
| BNBK5XRF | Shared: device identity from the public registry. | — |
| BNNK54NP | Eufy storage backend. | — |
| BN47Z0PR | Dreame RASTER backend — consume the base integration's decoded MapData object | — |

## `custom_components/eufy_vacuum/mapping/mapping_services.py` · 11

| token | section | cited by |
|---|---|---|
| BNPJAKN9 | Service names | — |
| BNEDRAMZ | Schemas | — |
| BN131WEZ | Helpers | — |
| BN3EPB5V | Polygon math helpers | — |
| BN6NPMKA | Image analysis handlers | `docs/dev/11-map-stored-state.md` |
| BNC3PSH3 | Custom layouts — named collection of no-CV segmentations per map | `docs/dev/11-map-stored-state.md` |
| BN436BDT | Furnished custom render (Wave 0) — per-layout furnished-art overlay state | `docs/dev/11-map-stored-state.md` |
| BNS7MCWP | Custom layout CRUD | `docs/dev/11-map-stored-state.md` |
| BNWZH4DA | Saved-zone CRUD (Wave 1 — storage only; filing + dispatch are later waves) | `docs/dev/11-map-stored-state.md` |
| BNCBE0NT | Registration | — |
| BNB7AGJH | Image analysis services | — |

## `custom_components/eufy_vacuum/mapping/segmenter_engines.py` · 7

| token | section | cited by |
|---|---|---|
| BN5Z6F7W | Type definitions — the canonical SegmentationResult contract. | — |
| BN3XPZM4 | Protocol — what the framework registers in _SEGMENTER_ENGINES. | — |
| BNHJ5AKM | Eufy CV engine — wraps the existing detect_room_segments pipeline. | — |
| BNH7N8GP | Internal | — |
| BN4X66AM | Noop fallback — for adapters that yield no segmentation at all. | — |
| BN5HEHJ2 | Registry | — |
| BNTWD4V0 | Internal helpers | — |

## `custom_components/eufy_vacuum/mapping/tracker.py` · 7

| token | section | cited by |
|---|---|---|
| BNX0V0H3 | Constants | — |
| BNJYEYJG | Per-vacuum tracker state | — |
| BN5D4RKA | Tracker | — |
| BNFQRJDY | Dock-coordinate drift log (diagnostic) | — |
| BN7N3R5Z | Listener registration | — |
| BNEKTDZR | Job lifecycle | — |
| BNRTVX2S | Position handling | — |

## `custom_components/eufy_vacuum/models/models.py` · 2

| token | section | cited by |
|---|---|---|
| BNVAM19F | Rule models | — |
| BNDTA35W | Theme models | — |

## `custom_components/eufy_vacuum/onboarding/manager.py` · 2

| token | section | cited by |
|---|---|---|
| BN3BEJTH | Private helpers | — |
| BNW9AAN5 | Public API | — |

## `custom_components/eufy_vacuum/planning/run_plan.py` · 5

| token | section | cited by |
|---|---|---|
| BN3WEMRE | Module-level pure helpers (duplicated from core/manager.py where also used) | — |
| BN31DWVA | RunPlanManager | — |
| BNFFVWNW | Water model helpers | — |
| BNS19G4Z | Water usage estimation | — |
| BN6EGRMT | Run planning helpers | — |

## `custom_components/eufy_vacuum/profiles/manager.py` · 3

| token | section | cited by |
|---|---|---|
| BN9M1MVS | ID generators | — |
| BNW696N6 | Room profile CRUD | — |
| BNP8V5FN | Run profile CRUD | — |

## `custom_components/eufy_vacuum/queue/dispatch_engines.py` · 1

| token | section | cited by |
|---|---|---|
| BNBPG3M5 | Registry | — |

## `custom_components/eufy_vacuum/rooms/access_graph.py` · 9

| token | section | cited by |
|---|---|---|
| BN9HSWTX | Internal ID generator | — |
| BNQHVRGC | Normalization | — |
| BNB031V0 | Managed rooms with automation metadata | — |
| BNX8KSJR | Access graph views | — |
| BNYV5NW7 | Issue formatting | — |
| BNDK0JMV | Room access context (internal aggregate) | — |
| BNS70XJJ | Public API — access graph editor / health | — |
| BNRYWGGQ | Validation | — |
| BNX4QZGD | Rule evaluation | — |

## `custom_components/eufy_vacuum/rooms/source_refresh.py` · 3

| token | section | cited by |
|---|---|---|
| BN9RY7DZ | Cache accessors | — |
| BNAJ69WK | Flatten shim (pure — no hass) | — |
| BN2YZGWK | Async refresher | — |

## `custom_components/eufy_vacuum/sensor/lifecycle.py` · 3

| token | section | cited by |
|---|---|---|
| BN93905S | HA lifecycle | — |
| BNK3GSCT | Update callbacks | — |
| BNCDV51F | State | — |

## `custom_components/eufy_vacuum/setup/workflow.py` · 3

| token | section | cited by |
|---|---|---|
| BN47ST30 | Internal helpers | — |
| BN3WR8AM | add_vacuum | — |
| BNR06W9B | import_active_map | — |

## `custom_components/eufy_vacuum/themes/manager.py` · 3

| token | section | cited by |
|---|---|---|
| BNQWR9SP | Callback management | — |
| BNDN4WKD | Private helpers | — |
| BNCXHCJ9 | Public API | — |

## `custom_components/eufy_vacuum/themes/preloaded.py` · 3

| token | section | cited by |
|---|---|---|
| BNFMJ978 | Build helpers | — |
| BN1AX4KE | Base spec and preloaded theme list | — |
| BN2DJBKT | Library seeder | — |

## `custom_components/eufy_vacuum/themes/services.py` · 3

| token | section | cited by |
|---|---|---|
| BNRSG97G | Schemas | — |
| BNEA5RRB | Helpers | — |
| BND8DXX9 | Registration | — |

## `scripts/gen_event_docs.py` · 7

| token | section | cited by |
|---|---|---|
| BNB5542G | blind-spot ledger | — |
| BNC874K2 | 1. parse the package | — |
| BNWXRS80 | 2. module-level string constants — INCLUDING f-strings | — |
| BNQYEQND | 3. function/method index — for resolving builder calls | — |
| BNTYV3XR | 4. every async_fire call site | — |
| BNF6JNDQ | 5. the model | — |
| BNGXW9T3 | 6. emit the reference | — |

## `src/actions/rooms.js` · 4

| token | section | cited by |
|---|---|---|
| BNB9BKM3 | 1) Confirm start status against backend truth | — |
| BNAXGMHJ | 2) Start selected rooms | — |
| BNYCFWAT | 3) Run learning estimate and store the full payload | — |
| BN7WZN6Q | 4) Enter active learning-job mode | — |

## `src/bindings/map.js` · 2

| token | section | cited by |
|---|---|---|
| BN3KGZJ9 | Double-click on map background → reset transform | — |
| BNVMC3YY | Touch pinch zoom | — |

## `src/controllers/learning-controller-progress.test.mjs` · 3

| token | section | cited by |
|---|---|---|
| BNGAA1QF | getRoomProgressSnapshot — BACKEND path | — |
| BNNZFY5R | getRoomProgressSnapshot — LOCAL timeline path | — |
| BNADC9QG | computeProgressPercent | — |

## `src/renderers/setup.js` · 2

| token | section | cited by |
|---|---|---|
| BN00X12B | Setup steps wizard | — |
| BN2P065F | System entity bindings | — |

## `src/state/clean-mode-options.test.mjs` · 1

| token | section | cited by |
|---|---|---|
| BNSW5H06 | Water level: "Off" is not offered while mopping | — |

## `src/state/maintenance-logic.test.mjs` · 2

| token | section | cited by |
|---|---|---|
| BNPM3VTK | findUpkeepItem | — |
| BNP0PFCA | canInvokeMaintenanceReset | — |

## `src/theme-tokens/floor-scope.test.mjs` · 4

| token | section | cited by |
|---|---|---|
| BN9E1X7P | floorTypeNames / prefixes / keyInType (whole-name, never dash-split) | — |
| BNP10789 | detectFloorScope — known/unknown partition | — |
| BNGVX4JV | sliceThemeByTypes — keep only wanted types across the 3 sections | — |
| BN2CB85J | clampThemeScalars — clamp bounded scalars, pass colors/rangeless through | — |
