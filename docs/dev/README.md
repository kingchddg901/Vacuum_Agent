# Developer documentation

> **The rewrite is complete.** Every backend line has an owning document, and the three
> cross-cutting documents that line coverage cannot see — [01](01-architecture-overview.md),
> [02](02-ha-integration.md), [03](03-data-model.md) — are written. The previous set of subsystem
> guides was retired wholesale to `docs/retired/dev/`, not because it was wrong but because it was
> built to a standard that rewarded restating the code. What replaced it is written against the
> anchor system, so a document addresses a *region* or a *rule* rather than a file and a line.
>
> **Retired docs are still on disk and still readable — in the repo, not on the site.**
> `docs/retired/` is excluded from the published build (see `mkdocs.yml`): it is an archive, it was
> never in the nav, and building it only surfaced relative links that broke when the files were
> *moved* there. They are as-of-their-date records, and several are the only written account of a
> subsystem's *history*. Read them for that; do not treat them as current, and **do not repair
> them** — that instruction is why the fix was a build exclusion and not eighty-three edits.
>
> ⚠ **If you scope another campaign, read this before you start.** The instruction that stood here
> was *"scope the remaining work from the tree, not from the retired file list."* It exists because
> the retired list has holes — nine live modules, 2,780 lines, had no owning document in it, and
> `clean_order/` was the trap: the string appears 23 times across seven retired docs, every one of
> them the capability flag `honors_clean_order`, which is a different subject from the package that
> reads the device's clean sequence.
>
> **That instruction is correct and it is not sufficient.** Scoping from the tree finds every
> *package* — and a document about the *system* owns no lines, so it cannot be found that way. Three
> were dropped exactly like that and were only noticed when someone asked. The tell was in the link
> graph the whole time: the two most-cited missing targets were the two missing documents, because
> orienting docs are cited most. **Scope from the tree AND from what the corpus is cited for.**
>
> ```bash
> python scripts/docs_coverage.py            # line coverage, plus the declared cross-cutting list
> python -m mkdocs build --strict            # what the corpus is cited for, and what no longer resolves
> ```

---

## Start here

| doc | what it is for |
|---|---|
| [00 — How These Docs Work](00-documentation-standard.md) | The standard. Shelves, the acceptance test, citation rules, the release gate. Read before writing anything here. |

## The registries — rules with a durable identity

These are the addressing layer. Declarations live in **source**; these files index them.

| doc | holds |
|---|---|
| [00b — Invariants](00b-invariants.md) | `IN` — a rule the program must preserve, each with the consequence of breaking it. Also `EN` — a rule that binds a person, where no test can ever go red. |
| [00c — Replicas](00c-replicas.md) | `RN` — one rule deliberately implemented in more than one place. A green suite cannot see a missing copy. |
| [00b-h — Invariant harvest](00b-h-invariant-harvest.md) | Working table for rules found but not yet ruled on. |
| [00c-h — Replica harvest](00c-h-replica-harvest.md) | The same, for replica sets. |
| [00d — Audit crosswalk](00d-audit-crosswalk.md) | Maps audit findings to where they landed. |

The notation itself — every class, what each is for, and how to mint one — is specified in
[design/shipped/notation-anchors.md](design/shipped/notation-anchors.md).

## NOW — what the system does today

Code is authoritative. A NOW doc that disagrees with the code is stale, and the fix is the doc.

| doc | covers |
|---|---|
| [01 — Architecture Overview](01-architecture-overview.md) | The map: five layers and which way they point, where a run travels, and the four boundaries that carry the design. **Start here.** |
| [02 — The Home Assistant Surface](02-ha-integration.md) | What the integration exposes to HA and takes from it — and the eleven outbound events, which have no other owning document. |
| [03 — The Data Model](03-data-model.md) | Everything persisted, in one place: two stores with different write shapes, the schema that is mostly undeclared, and the two identifiers that are names. |
| [05 — While a Run Is Live](05-run-live.md) | Queue derivation and the refusal ladder, dispatch, brand-conditional room advance, the two stuck detectors, and the mid-run observers. |
| [06 — How a Run Ends](06-run-end.md) | Every path by which a run ends, the exactly-once claim, finalization and its commit point, error-second deduction, and which derived stores never self-heal. |
| [11 — A Map's Stored State](11-map-stored-state.md) | The 29 services that write a map's stored representation — images and the segment cache, custom segmentation, layout lifecycle, display state, and saved zones. |
| [12 — Where the Map Comes From](12-map-source.md) | The provider's own segmentation and pose, normalized into one brand-neutral shape. Backends are declared, never inferred. |
| [13 — How Rooms Are Found](13-segmentation.md) | The segmenter contract, the shape every engine must return, the shared geometry toolkit, and what survives of boundary derivation. |
| [14 — Live Room Tracking](14-live-tracking.md) | Room identity from the device's own signal; position survives only as a movement delta. Plus the dock-drift log. |
| [15 — The Stall Capture Image](15-stall-capture-image.md) | The pure renderer behind a stall notification, and why every behaviour in it is an absence behaviour. |
| [16 — The Battery Record](16-battery-record.md) | Two evidence streams meeting in one record: the sampling guards and their asymmetric reach, charge sessions, the two-regime health proxy, per-job drain, and the twelve sensors. |
| [17 — A Room's Identity](17-room-identity.md) | What a room is, where identity is minted, how it survives the device renumbering its segments, and the guards on the write path. |
| [18 — The Access Graph](18-access-graph.md) | Reachability and live-entity rules over the room store: the delta-scoped edit gate, tri-state rule evaluation, and what reaches a user. |
| [19 — The Event Ingress Layer](19-event-ingress.md) | The ten listeners: three subscription models, why nothing is serialized at ingress, and where deduplication actually lives. |
| [20 — Room Profiles](20-room-profiles.md) | The global profile library and the contract that keeps one brand's vocabulary out of another brand's rooms: core owns the keys, the adapter owns every value. |
| [21 — Run Profiles](21-run-profiles.md) | The per-map saved-run library: what a save captures, the four-rung apply ladder, and why applying one writes the queue and not just the rooms. |
| [22 — The Adapter Contract](22-adapter-contract.md) | What a brand must declare, what each omission falls back to, and which of those rules actually run for a code adapter. |
| [23 — The Eufy Adapter](23-eufy-adapter.md) | How the reference brand answers the contract: the five things it computes, the declarations that look like mistakes and are not, and the surfaces that no longer do what they say. |
| [24 — The Roborock Adapter](24-roborock-adapter.md) | What it cost to be the second brand: the live dock resolution and the three probes it rejects, where the reverse port forced a new name or a change to core, and the two model tables that disagree. |
| [25 — The Eufy Segmentor](25-eufy-segmentor.md) | The HSV pipeline that infers rooms from map screenshots: why it exists after the vendor gave us rooms, the two-theme image trick at its centre, and how to find the mis-tuned stage without memorising a threshold. |
| [26 — The Learning Record Store](26-learning-record-store.md) | Where learning keeps what it knows: six directories per vacuum, three record kinds, and the tri-state read that stops a torn file becoming a wrong statistic. |
| [27 — What Counts As Learnable](27-learning-eligibility.md) | The two vocabularies that record the verdict, the three places that can veto a run, and why a cancelled run is not evidence about a room in either direction. |
| [28 — From Records To Statistics](28-learning-statistics.md) | The key that decides what counts as the same clean, what a partial clean loses and keeps, and why a renamed room starts from zero. |
| [29 — Prediction and Accuracy](29-learning-prediction.md) | The five-pass lookup and why it relaxes cheapest-first, what a relaxed match costs, and the loop that feeds a prediction error back into its next confidence. |
| [30 — External Runs](30-external-runs.md) | Runs started from the vendor app: capture without identity, the dock grace window, and why one finishes into a pending review rather than a job. |
| [31 — The Setup Layer](31-setup-layer.md) | The declared step machine, the asymmetric drift signal that reopens a finished step, and why a rejected phantom room belongs to one map. |
| [32 — The Store](32-the-store.md) | The one persistent document everything writes to: two write paths, a schema that is mostly undeclared, and the guard that stops a failed setup writing an empty dict over everything. |
| [33 — The Orchestrator](33-the-orchestrator.md) | Fifteen subsystems and the three that do not need the manager, what a restart loses, and the migration loop that must never write a brand word. |
| [34 — Capability Detection](34-capability-detection.md) | The two kinds of adapter hint and why confusing them shipped a defect, and the vocabulary that records how a role was resolved rather than only what won. |
| [35 — The Fault Tracker](35-the-fault-tracker.md) | Three latches with three lifetimes, the two-phase handoff that survives a failed save, and where Home Assistant stops speaking and the brand starts. |
| [36 — The Service Layer](36-the-service-layer.md) | Eighty services across sixteen domains: why a write refuses where a read answers, and why service names are never translated but their failures are. |
| [37 — The Entity Surface](37-the-entity-surface.md) | What works without the card: six platforms, a unique id that may never be parsed, and why cleanup is the complement of what was built. |
| [38 — The Theme Library](38-the-theme-library.md) | One subtree owned outright, why deleting a built-in theme needs a tombstone, and which tags are stored versus derived from the palette. |
| [39 — The Integration Entry Point](39-the-entry-point.md) | The four functions HA calls, the cold-start race that makes setup run twice, and the ruling that removing the integration keeps your learning tree. |
| [40 — Diagnostics and Evidence](40-diagnostics-and-evidence.md) | Four layered ways to ask what actually happened: the read-only support dump, the silent log ring, the record that makes invisible branches visible, and the receipt protocol where both ends assert the edge. |
| [41 — Maintenance and the Dock](41-maintenance-and-the-dock.md) | Why the framework keeps a bookmark rather than a counter, what each of the two clamps defends against, and the gate that asked the dispatched question about the floor. |
| [42 — The Send Side](42-the-send-side.md) | The last mile: ids re-resolved at dispatch, why a mixed batch takes the safest water, and the safety abort that could never fire. |
| [43 — Observing a Run Without Geometry](43-observing-a-run.md) | Counter plateaus instead of coordinates, the pose ring that outlives the job, and a module that deliberately decides nothing because a wrong rule is worse than the bug. |
| [44 — Onboarding and First Run](44-onboarding-and-first-run.md) | Installed to usable, where nothing blocks: an optional vacuum picker, completeness computed rather than stepped, and a sidebar title the user owns. |
| [45 — The Shared Layer](45-the-shared-layer.md) | The four modules everything imports: a constants file that re-exports a brand, ensure-versus-require arrived at four times, and how much of the first data model is still here. |

> The rest of the NOW shelf is unwritten. Until a subsystem is rewritten here, its retired guide
> in `docs/retired/dev/` is the only account there is.

## DESIGN — how we want it to work

Either side may be wrong; when a design doc and the code disagree, **adjudicate** rather than
assuming the doc is stale.

- [design/shipped/notation-anchors.md](design/shipped/notation-anchors.md) — the anchor classes
- [design/shipped/map-state-source.md](design/shipped/map-state-source.md)
- [design/shipped/eufy-native-transition.md](design/shipped/eufy-native-transition.md)
- [design/planning/entity-resolution-reliability.md](design/planning/entity-resolution-reliability.md)
- [design/planning/voice-assist-wizard.md](design/planning/voice-assist-wizard.md)
- [design/core-minimality.md](design/core-minimality.md) — a dated *measurement*, not a plan and
  not history; it sits at the `design/` root because neither sub-shelf fits it

## HISTORY — what we stopped doing

Never wrong: a record of what was true then.

- [history/disaster-recovery-standard.md](history/disaster-recovery-standard.md)
- [history/documentation-epoch-lifecycle.md](history/documentation-epoch-lifecycle.md)
- [history/floor-type-cleaning-defaults.md](history/floor-type-cleaning-defaults.md)
- [history/room-bounds-from-traces.md](history/room-bounds-from-traces.md)

## Outside the shelves

- **[frontend/](frontend/architecture-overview.md)** — the card. Its own hub, its own index.
- **`reference/`** — generated. Never hand-edit; regenerate with
  `python scripts/check_generated_docs.py --fix`.
  [EVENTS](reference/EVENTS.md) ·
  [THEME_TOKEN_MAP](reference/THEME_TOKEN_MAP.md) ·
  [THEME_TOKEN_USAGE](reference/THEME_TOKEN_USAGE.md) ·
  [ai-theme-authoring](reference/ai-theme-authoring.md)
- **`deltas/`** — [open deltas](deltas/README.md), tracked against live behaviour.
- **`maintenance/`** — dated audit records, excluded from the citation and index gates by rule.

---

## Gates

Documentation is a **release** gate, not a per-push one.

| command | checks |
|---|---|
| `python scripts/check_doc_citations.py` | every `::symbol` resolves; flags surviving line citations |
| `python scripts/check_generated_docs.py` | generated docs match their generator |
| `python scripts/check_docs_index.py` | every doc is reachable from an index |
| `python scripts/doc_anchor.py --check` | anchor identity: duplicate, broken, moved, malformed |
| `mkdocs build --strict` | **links only** — it has passed clean through eleven false sentences and can never be the freshness gate |

Naming a file in backticks does **not** make it reachable. That is how the whole of `design/`
once went missing from the corpus.
