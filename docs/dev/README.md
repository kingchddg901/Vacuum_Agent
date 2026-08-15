# Developer Docs — Reading Order

These are the **Disaster-Recovery baseline** docs — they answer **"this is how it works."**
The other three questions live elsewhere: **why** → [design/](design/map-state-source.md) ·
**what I'm changing right now** → [deltas/](deltas/README.md) · **what happened and what it
cost to learn** → the audit record. If a passage answers a different question than the
document it lives in, it belongs somewhere else — that's the whole routing rule.

**Reading rule:** read the DR section first, then check [deltas/](deltas/README.md) for a
matching delta. No delta file for a subsystem means the DR baseline is authoritative,
full stop.

Under the availability contract ([00 §0](00-disaster-recovery-standard.md)) the corpus
rebuilds a functionally identical integration from total source loss — **two-phase**:
every doc-stated interface first as skeletons, then each section implemented against
them. The reading order below is the COMPREHENSION order, not a dependency order (the
subsystem graph is mutually recursive; no topological order exists) — read top-down,
rebuild by interfaces.

The backend integration's architecture, subsystems, and porting contract, in reading order.
The **frontend / Lovelace-card** docs are their own set — see **[frontend/](frontend/architecture-overview.md)**.
Read them in this order if you are new to the codebase; jump in anywhere if you know what you're looking for.

---

## Foundation

Start here. The standard first — the bar every subsystem doc is held to — then the four
files that give you the mental model you need before reading anything else.

| # | File | What it covers |
|---|---|---|
| 00 | [disaster-recovery-standard](00-disaster-recovery-standard.md) | The disaster-recovery doc standard: the availability contract (§0 — total source loss, functional identity, self-hosting corpus), the DR-grade rubric, meta-rules, and the per-subsystem audit-status table |
| 00a | [documentation-epoch-lifecycle](00a-documentation-epoch-lifecycle.md) | The documentation model itself: DR baseline / dev deltas / audit record, epoch open-and-close, the plain-language key, epoch-edge fix rules |
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
| 30 | [phase-runner](30-phase-runner.md) | Strict-order (sequenced) per-room phase execution: the settle/dispatch/verify/retry watchdog + per-phase timing capture, plus the `charge_wait`/`wait` stop phases (`_run_charge_wait_phase` / `_run_wait_phase`) that a stepped run docks on between room groups (`PhaseRunner`, `jobs/`) |

---

## Subsystems

Domain subsystems in dependency order (rooms first, everything else builds on them).

| # | File | What it covers |
|---|---|---|
| 08 | [rooms-system](08-rooms-system.md) | Room data model, room fields, effective-settings resolution |
| 09 | [room-rules-system](09-room-rules-system.md) | Per-room rules: blockers, modifiers, rule evaluation at job build time |
| 10 | [learning-system](10-learning-system.md) | Timing learning: recording runs, ETA estimation, confidence model |
| 11 | [mapping-system](11-mapping-system.md) | Image segment analysis, coordinate system, segment adjustments, custom layouts, the segmenter-engine seam, and the provider map source. §3 and §7 preserve the **retired** trace→bounds design verbatim as a DR reference — the code is gone |
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

## Adapters

The adapter layer — how a vacuum brand plugs into the core.

| # | File | What it covers |
|---|---|---|
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

---

## Feature deep-dives

Cross-cutting features that span several subsystems.

| # | File | What it covers |
|---|---|---|
| 28 | [external-run-ingestion](28-external-run-ingestion.md) | App-started (external) runs: detection, capture, blind segmentation, the review card + confirm wizard, the tier-1 identity gate, and graduating into the learned baselines |

---

## Design references

Not in the numbered reading order — design rationale the subsystem docs point to.

- **[design/](design/map-state-source.md)** — design/proposal references: `map-state-source` (the provider-map-source seam rationale, paired with [31](31-map-source-coordinator.md)), `eufy-native-transition` (native current-room detection design + validation; its pose/attribution track shipped in 1.8.0), `voice-assist-wizard` (design-only, not yet implemented).
- **[32-core-minimality-and-deconstruction](32-core-minimality-and-deconstruction.md)** — the irreducible-core map (analysis, not a changelog).

*(The battery-accounting and external-run-robustness follow-up trackers were folded into their subsystem docs — [12 §9](12-battery-system.md) and [28 §11](28-external-run-ingestion.md) — and removed 2026-07-29 once their items were closed.)*

---

## Frontend

The Lovelace panel card — the render cycle, event binding, styles, state, the frontend↔backend
contract, theming, i18n, the standalone cards, and every card feature — is documented as its own
set in **[frontend/](frontend/architecture-overview.md)**. Start with the **architecture overview**
(the hub), which maps the whole set.

---

## Reference & maintenance

Not in the numbered reading order.

- **[reference/](reference/ai-theme-authoring.md)** — theme-token references:
  [THEME_TOKEN_MAP](reference/THEME_TOKEN_MAP.md) + [THEME_TOKEN_USAGE](reference/THEME_TOKEN_USAGE.md)
  (both **generated** — regenerate with `node scripts/gen-theme-token-docs.mjs`, never hand-edit) and
  [ai-theme-authoring](reference/ai-theme-authoring.md) (theming the card with an AI assistant).
- **`dev/maintenance/`** — the hostile-audit working ledger
  (`highly-aggressive-audit.md`): what each subsystem audit found, what is fixed, what is still open.
  **Repo-only** — excluded from the published docs site (`exclude_docs` in `mkdocs.yml`), so it is
  NAMED here in backticks rather than linked. A link would still render on the site, as an `<a href>`
  pointing at a page that was never built — and `mkdocs build --strict` reports that at INFO, not as a
  warning, so the build stays green while every reader of the public site gets a 404.

---

## Contributing docs

Not numbered — separate audience.

- [porting-guide](../contributing/porting-guide.md) — end-to-end workflow for adding a new vacuum brand
- [animal-authoring](../contributing/animal-authoring.md) — public path: submit a declarative animal **descriptor** (sanitised + codegen'd) — the safe way to share a companion
- [mascot-authoring](../contributing/mascot-authoring.md) — maintainer / runtime path: hand-written `animals/<id>.js` (`register()`, `type:'custom'`) plus the craft standards that apply to both paths
- [theme-authoring](../contributing/theme-authoring.md) — making a card theme (editor / AI-assisted / hand-written JSON) and sharing it in the gallery
- [translating](../contributing/translating.md) — contributing a card translation (a JSON locale file — data, not code)
- [translation-review](../contributing/translation-review.md) — AI-drafted-translation review notes awaiting native-speaker confirmation

## Testing docs

How the test suite is structured, how to run it (Docker-based), the available
fixtures and seeding helpers, and copy-paste templates for new tests.

- [testing/README](../testing/README.md) — index and reading order
