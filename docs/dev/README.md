# Developer Docs — Reading Order

32 numbered files covering the integration's architecture, subsystems, and porting contract.
Read them in this order if you are new to the codebase; jump in anywhere if you know what you're looking for.

---

## Foundation

Start here. These four files give you the mental model you need before reading anything else.

| # | File | What it covers |
|---|---|---|
| 01 | [architecture-overview](01-architecture-overview.md) | The big picture: adapter pattern, data flow, concurrency rules, subsystem map |
| 02 | [ha-integration](02-ha-integration.md) | Config entry lifecycle, platform setup, entity registration, coordinator pattern |
| 03 | [data-model](03-data-model.md) | The persistent store schema — every top-level key and what lives under it |
| 04 | [listeners](04-listeners.md) | Event bus wiring — what the integration listens to and how state changes propagate |

---

## Core Orchestration

The manager and the job pipeline.

| # | File | What it covers |
|---|---|---|
| 05 | [core-manager](05-core-manager.md) | The central manager class: runtime state, method surface, subsystem wiring |
| 06 | [job-lifecycle](06-job-lifecycle.md) | Full job flow from queue to finalization, including pause/resume and cancellation |
| 07 | [queue-engine](07-queue-engine.md) | The queue data structure, room ordering, dispatch payload construction |
| 30 | [phase-runner](30-phase-runner.md) | Strict-order (sequenced) per-room phase execution: the settle/dispatch/verify/retry watchdog + per-phase timing capture (`PhaseRunner`, `jobs/`) |

---

## Subsystems

Domain subsystems in dependency order (rooms first, everything else builds on them).

| # | File | What it covers |
|---|---|---|
| 08 | [rooms-system](08-rooms-system.md) | Room data model, room fields, effective-settings resolution |
| 09 | [room-rules-system](09-room-rules-system.md) | Per-room rules: blockers, modifiers, rule evaluation at job build time |
| 10 | [learning-system](10-learning-system.md) | Timing learning: recording runs, ETA estimation, confidence model |
| 11 | [mapping-system](11-mapping-system.md) | Coordinate tracking, map bounds learning, segmenter engine seam |
| 31 | [map-source-coordinator](31-map-source-coordinator.md) | Provider-authoritative map-source reader: storage/memory/introspect backends, the four async readers, live-pose overlay (`MapSourceCoordinator`, `mapping/`) |
| 12 | [battery-system](12-battery-system.md) | Battery health: cycle counting, zone-aware charge rate tracking, job drain metrics |
| 13 | [maintenance-manager](13-maintenance-manager.md) | Maintenance tracking: interval overrides, reset snapshots, upkeep snapshot |
| 14 | [dock-manager](14-dock-manager.md) | Dock state, gated dock actions, dock event recording |
| 15 | [setup-system](15-setup-system.md) | Setup wizard, room drift detection, phantom room suppression |

---

## Domain Managers

Higher-level managers that sit above the subsystems.

| # | File | What it covers |
|---|---|---|
| 16 | [profile-manager](16-profile-manager.md) | Run profiles and room profiles: schema, apply, rename, overwrite, delete |
| 17 | [map-manager](17-map-manager.md) | Map import, storage, deletion, protection levels |
| 18 | [onboarding-manager](18-onboarding-manager.md) | First-run onboarding state and step tracking |

---

## UI Contract

The Lovelace panel card and everything the card reads from integration state.

| # | File | What it covers |
|---|---|---|
| 19 | [card-architecture](19-card-architecture.md) | Panel card structure, renderer/binding pattern, service call protocol |
| 20 | [theme-system](20-theme-system.md) | Theme editor: token hierarchy, palette → token derivation, import/export |
| 21 | [adapter-system](21-adapter-system.md) | Adapter registration, registry, runtime lookup, adapter API contract |
| 22 | [adapter-config-reference](22-adapter-config-reference.md) | Complete schema reference for per-vacuum adapter config dicts |
| 25 | [eufy-adapter](25-eufy-adapter.md) | The Eufy adapter as a worked example + pattern guide for a full-feature adapter |
| 26 | [eufy-segmentor](26-eufy-segmentor.md) | The Eufy CV room segmentor and the segmenter-engine pattern for a new brand |
| 29 | [roborock-adapter](29-roborock-adapter.md) | The **second-brand** worked example — Roborock (native `get_maps`, path-optimized order, live map image, strict-order); the foil to the Eufy adapter |

---

## Auxiliary

| # | File | What it covers |
|---|---|---|
| 23 | [error-tracker](23-error-tracker.md) | Error classification, per-vacuum error state, repair-issue patterns |
| 24 | [animal-svg](24-animal-svg.md) | Map-view animal companions: SVG structure, state→pose mapping, battery-state eye color, theme tokens, memorial animals, authoring rules |

---

## Frontend Quality & Tooling

Headless rendering of the real card for regression, accessibility, and sharing.

| # | File | What it covers |
|---|---|---|
| 27 | [render-harness](27-render-harness.md) | Headless render harness: the pure-renderer mount, all-states galleries, visual regression, CVD/colorblind validation + the Colorblind Safe theme, badge shape marks, theme-export intake, and the theme **gallery + issue→PR submission** pipeline. Test/run companion: [testing/07](../testing/07-render-harness.md) |

---

## Feature deep-dives

Cross-cutting features that span several subsystems.

| # | File | What it covers |
|---|---|---|
| 28 | [external-run-ingestion](28-external-run-ingestion.md) | App-started (external) runs: detection, capture, blind segmentation, the review card + confirm wizard, the tier-1 identity gate, and graduating into the learned baselines |
| 32 | [furnished-render](32-furnished-render.md) | Furnished custom render: overlay a to-scale home render over the live map (no georeference — the light path), the per-layout data model, the three services, `resolve_furnished_render`, and the frontend art layer / render modes |

---

## Contributing docs

Not numbered — separate audience.

- [porting-guide](../contributing/porting-guide.md) — end-to-end workflow for adding a new vacuum brand
- [mascot-authoring](../contributing/mascot-authoring.md) — visual standards for adding or improving animal companions

## Testing docs

How the test suite is structured, how to run it (Docker-based), the available
fixtures and seeding helpers, and copy-paste templates for new tests.

- [testing/README](../testing/README.md) — index and reading order
