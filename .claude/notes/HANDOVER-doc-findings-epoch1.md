# HANDOVER — doc findings at the Epoch-1 close

**Written 2026-08-07 for hand-off. Scope: DOCUMENTATION findings only** — no code bugs
(those live in `DOC-PASS-TRIAGE.md`'s code queue). Context ruling (Chris, 2026-08-07):
**the audit and ALL its fixes are Epoch 1; Epoch 2 is currently EMPTY.** Every finding
below is what stands between the ledger and that ruling being true on paper.

Method note: coverage below is derived from `git show --stat`, never from file mtimes —
a checkout resets mtimes and several frontend docs carry 8/6 mtimes with zero commits.

---

## D-1. The epoch ledger itself is stale — `docs/dev/deltas/README.md`

The highest-priority finding, because the ledger is the epoch system's root document.

- **Epoch 2 row** lists two "first known delta candidates": the Phased Jobs rebuild and
  `live:FONT-1`'s unresolved remainder. Per the ruling, both are Epoch 1: the rebuild is
  campaign-derived work, and FONT-1 is RESOLVED, user-confirmed (`c093843`; mechanism
  finished `ec30b11`; drop-in fonts shipped `cefc688`). The row should read **empty**.
- **The "Epoch 1 coverage caveat"** states `docs/dev/frontend/` "was not in the
  reconciliation pass." That was true when written and is now substantially overtaken:
  three Opus-verified truth passes landed 2026-08-06 —
  `fcb0c4d` (fe-architecture: card-topology, module-reference, state-management) ·
  `b8b1a9d` (fe-visual: custom-segment-composer, dashboard-card, map-render-layers,
  saved-zones, themeable-map-palette) ·
  `c11954b` (fe-theme-i18n: event-binding-and-modal-host, i18n-system, render-harness,
  styles-system, theme-system) — plus `12e3b63` (styles-system §4b drop-in fonts +
  user-guide 14-accessibility) and `3531e02` (map-render-layers, R2-BUG-5 resolution).
  The caveat must be rewritten to the ACTUAL residual scope (D-2), or it commits the
  exact failure it warns about — an epoch row misstating its own coverage.

## D-2. Frontend residual — six docs no 8/6 pass touched

By git, these have had **no reconciliation commit** and are the true remaining
unreconciled frontend region:

| doc | last touched | note |
|---|---|---|
| `frontend/architecture-overview.md` | 7/29 | entry-point doc — highest staleness risk of the six given the 8/6 card work |
| `frontend/backend-contract-and-data-shapes.md` | pre-8/6 | carries fault/error_label content from an EARLIER era — verify against the shipped fault-label seam, it may be stale-vs-code (see D-3) |
| `frontend/render-cycle.md` | 7/11 | predates the state/renderers/bindings module split |
| `frontend/floor-texture-map-view.md` | 7/4 | feature-scoped; likely low drift |
| `frontend/furnished-render.md` | 7/29 | feature-scoped; likely low drift |
| `frontend/animal-svg.md` | 7/4 | decorative subsystem; lowest stakes |

Disposition per the epoch doctrine: either reconcile these six, or name them as the
(reduced) coverage exclusion in the rewritten caveat. Silence is the only wrong option.

## D-3. The two "absent DR sections" — verify closure, do not assume it

The caveat's two absent-section claims are now partially answered; each needs a
verify-and-close or an explicit carry:

- **Accessibility typeface**: `styles-system.md` now carries the mechanism (§4b drop-in
  fonts `12e3b63`, FONT_DEFS generation `ec30b11`, the shadow-vs-document registration
  rule from the FONT-1 chain `ecbe77f`) and `docs/user-guide/14-accessibility.md` has
  the user how-to. **Verify** the section covers the full shipped surface: @font-face
  document-level registration rule, the a11y token chain, form-control inheritance,
  `user_fonts.py` catalog flow (fontTools cmap → catalog.json), the
  `fonttools[woff2]` manifest requirement, and the 12-locale FONT_SUPPORT evidence rule
  (proof-not-coverage doctrine per the FS-3/FS-4/LCF-2 reconciliation `6b11fec`).
- **Fault-label seam** (`error_label_keys`, `ROBOROCK_ERROR_LABEL_KEYS`,
  `fault.<brand>.*`, fallback-to-raw-code): content matching these symbols exists today
  in `i18n-system.md` (truth-passed 8/6 — likely current) and in
  `backend-contract-and-data-shapes.md` (NOT passed — verify, D-2). Also note the seam
  itself changed on 8/7: `31edf3b` landed RB-ERR-2 (`error_tracking.message_is_code`,
  `_read_error_code_for_message()`) with backend docs 22/23/29 reconciled in the same
  commit — the frontend-side description must agree with that shipped shape.

## D-4. Job-lifecycle + phase-runner docs (06, 30) — inside Epoch 1, reconciliation unclaimed

Batch-1 re-verified backend docs 03/10/12/22/23/29 — **not 06 or 30**. With the Phased
Jobs rebuild ruled into Epoch 1, the DR baseline now claims to describe the REBUILT
lifecycle. Partial evidence exists — RP-047(b)'s revert-on-live-evidence put the
surviving design into 06, and `54707f8` fixed seven stale in-source claims feeding these
docs — but no pass has claimed full reconciliation of 06/30 against the rebuilt system.
Either run that pass or add 06/30 to the coverage exclusion by name.

Related Chris decision (open, from DOC-PASS-TRIAGE Q2): Phased-Jobs doc depth — the
parent/child finalize schema is documented only as hedged pointers. The Epoch-1 ruling
sharpens this: if the rebuild is Epoch 1, its schema is DR material now, not
next-epoch material.

## D-5. Advanced-docs GAPS — regenerated 2026-08-07, two open

`python .claude/notes/_check_advanced_doc_drift.py` at today's tree: exit 0,
**BREAKS: none** (nothing documented is missing or misnamed in code — no user can copy
a dead snippet). Two GAPS — real, undocumented, non-gating:

- `get_learning_history_snapshot` accepts `profile_name`; its section never mentions it.
- `get_metrics_snapshot` accepts `profile_name`; its section never mentions it.

(10 services remain exempt by design — maintainer tooling + the mid-rebuild queue-break
surface. With Phased Jobs ruled into Epoch 1, the queue-break half of that exempt list
is due a revisit: the script's own header says the list must be reconsidered when the
rebuild decision changes.)

## D-6. Intent questions blocking doc text (Chris's, not the doc-worker's)

From `DOC-PASS-TRIAGE.md`, still open; the dependent doc sections stay HELD until
answered:

1. **`discovery.py` trigger semantics** — doc said auto-discovery fires on "first
   non-idle state"; code fires on entering DOCKED (run-end) plus map-change/reload/
   timer. Which is intended? Either answer produces a doc change (rationale, or a
   regression note).
2. **Phased-Jobs doc depth** (see D-4) — stand pat with pointers, or document the
   parent/child finalize schema now that the rebuild is Epoch-1 material.

---

## What this handover deliberately excludes

- Code-defect tickets (DOC-PASS-TRIAGE code queue: R2-COV-1, R2-TEST-1, R2-DEAD-2,
  R2-BUG-2's semantics call, config-flow tested-model, `_background_tasks`, collapse
  path, dead SERVICE_* constants).
- `live:RB-ERR-2` — CLOSED 2026-08-07, folded into Epoch 1 with its docs in the same
  commit; nothing left doc-side.
- The old 10-item advanced-docs GAPS list — cleared by the doc pass; only the two in
  D-5 remain today.
