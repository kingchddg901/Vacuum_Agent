# Development deltas — the current epoch's diff against the DR baseline

Per [00a — Documentation Epoch and Reconciliation Model](../00a-documentation-epoch-lifecycle.md):
the numbered docs in `docs/dev/` are the **Disaster-Recovery baseline** — the reconciled,
present-tense rebuild truth as of the last epoch close. Files in THIS directory are the
current epoch's **deltas** against that baseline.

Reading rule: read the relevant DR section first, then the matching delta here. A delta
overrides the baseline only where it explicitly says it differs. **No delta file for a
subsystem means the DR baseline is authoritative, full stop.**

Deltas may be painfully honest — hypotheses, competing interpretations, unadjudicated
evidence, known gaps. Their job is to preserve active engineering reasoning accurately
enough for the next epoch-closing audit to adjudicate it.

---

## Epoch ledger

| epoch | closed | closing operation |
|---|---|---|
| **Epoch 1** | **2026-08-06** | The hostile-audit campaign (464 findings / 67 packets, cleared) + the DR reconciliation pass that established this baseline. Provenance: the audit record (`.claude/notes/synthesis/`, closure ledgers, the postmortem corpus). |
| Epoch 2 | open | Accumulating. First known delta candidates: the Phased Jobs rebuild; `live:FONT-1`'s unresolved remainder. |

### Epoch 2 delta candidates — detail

**`live:RB-ERR-2` — CLOSED 2026-08-07, folded into Epoch 1 instead.** Chris pulled it into
the epoch-closing release: shipping "clean" meant shipping the capture, not documenting it
as a known gap while 48 keys and 816 translated strings sat unreachable for every Roborock
user. `error_tracking.message_is_code` + `_read_error_code_for_message()`; docs 22/23/29
reconciled in the same change, so DR describes the shipped system rather than carrying a
delta. The note below is kept as the reasoning that predicted its shape.

**Original entry —** Chain and fix shape:
`.claude/notes/synthesis/FINDING-roborock-error-code-carrier.md`; queued as
`DOC-PASS-TRIAGE.md` open item 2.

Note carefully what kind of item this is. It is **not** a current divergence — doc 23
was reconciled to describe what capture writes *today* (`code` is `int | None`), which
is accurate. The delta arrives when the fix lands: once the message-channel rising edge
carries the brand's error enum into `code`, doc 23's field type, the classification-seam
reachability statements, and 22/29's five Roborock `error_tracking` blocks all change
meaning at once. Until then DR is authoritative and correct, and the five declared
Roborock tables are correctly documented as declared-but-unreachable.

The fix is gated on an adapter declaration (Eufy's `error_message` carries prose — "Robot
is stuck" must never become a pseudo-code), so it is an adapter-contract change, not a
local patch. That makes it delta-shaped rather than hotfix-shaped.

---

## Epoch 1 coverage caveat — `docs/dev/frontend/` was not in the reconciliation pass

Recorded rather than carried silently. The batch-1 pass re-verified six backend docs
(03, 10, 12, 22, 23, 29) plus the dev-reference / design / contributing clusters. It did
**not** cover `docs/dev/frontend/`. That region is therefore **unreconciled baseline, not
reconciled truth**, and the Epoch 1 row above should be read with this exclusion.

Known-stale against the 2026-08-06 card work:

| doc | what changed under it |
|---|---|
| `frontend/module-reference` | four new modules — `state/`, `renderers/`, `bindings/`, `styles/job-summary.js` (`bea6d3e`) |
| `frontend/styles-system` | the token build gate — every `var(--evcc-*)` must resolve, `KNOWN_DANGLING` may only shrink (`94bc18a`, `8ee6fb9`) |
| `frontend/event-binding-and-modal-host` | the job card is now a `role="button"` launch surface, with in-card controls guarded against double-firing (`bea6d3e`) |

Absent entirely — no DR section exists for either:

- **The accessibility typeface.** Nothing under `docs/dev/frontend/` mentions `@font-face`,
  `OpenDyslexic`, or the shadow-vs-document registration rule, though `styles-system.md`
  documents the shadow/body split meticulously elsewhere. That omission is what let the
  feature ship inert for two days: no prose said a font token is subject to the split, and
  `live:FONT-1` is still open.
- **The fault-label seam.** `error_label_keys`, `ROBOROCK_ERROR_LABEL_KEYS`,
  `fault.<brand>.*` and the card's fallback-to-raw-code rule appear in zero docs.

Why this is logged in the ledger and not just a TODO: per
[00a §9](../00a-documentation-epoch-lifecycle.md), the documentation is part of the
measurement apparatus. An epoch row that overstates its own coverage tells the next
auditor that a stale region is trustworthy prose — which is the same failure class as a
confidently-wrong DR statement, one level up. The exclusion is the honest baseline.
