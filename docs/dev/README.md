# Developer documentation

> **This corpus is being rewritten.** The previous set of subsystem guides was retired wholesale
> to `docs/retired/dev/` — not because it was wrong, but because it was built to a standard that
> rewarded restating the code. What replaces it is written against the anchor system, so a
> document addresses a *region* or a *rule* rather than a file and a line.
>
> **Retired docs are still on disk and still readable.** They are as-of-their-date records, and
> several are the only written account of their subsystem until it is rewritten. Read them for
> orientation; do not treat them as current, and do not repair them.

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
| [05 — While a Run Is Live](05-run-live.md) | Queue derivation and the refusal ladder, dispatch, brand-conditional room advance, the two stuck detectors, and the mid-run observers. |
| [11 — Mapping Services](11-mapping-services.md) | The 29 services that write a map's stored representation — images and the segment cache, custom segmentation, layout lifecycle, display state, and saved zones. |
| [06 — How a Run Ends](06-run-end.md) | Every path by which a run ends, the exactly-once claim, finalization and its commit point, error-second deduction, and which derived stores never self-heal. |

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
