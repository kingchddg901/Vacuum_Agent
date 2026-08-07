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
| **Epoch 1** | **2026-08-06** | The hostile-audit campaign (464 findings / 67 packets, cleared) + the DR reconciliation passes that established this baseline: batch 1 (`5940830` + siblings) and the 17-cluster adversarially-verified workflow pass (runs `wf_c3085752-b7b` + `wf_16fa0e1a-3f3`, applied 2026-08-06). Includes the rebuilt Phased Jobs (docs 06/30 reconciled + Opus-verified in `6a87c13`, per the §13 epoch-edge ruling) and the full `live:FONT-1` resolution (fix `ecbe77f`/`d3f81e6`, user-confirmed; typeface mechanism + drop-in fonts documented same-commit, styles-system §4/§4b). Provenance: the audit record (`.claude/notes/synthesis/`, closure ledgers, the postmortem corpus). |
| Epoch 2 | open | Accumulating. **No known code-vs-DR deltas at open** — every epoch-edge change landed with its DR statement in the same commit (§13). What remains open is *reconciliation residue*, listed below, not divergence. |

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

## Epoch 1 reconciliation residue — the honest remainder (rewritten 2026-08-07)

The original caveat here ("`docs/dev/frontend/` was not in the reconciliation pass") was
overtaken by events and has been replaced by the evidence-derived state below. The
workflow pass covered all three frontend clusters: 13 frontend docs were diffed and
Opus-verified (`fcb0c4d`, `b8b1a9d`, `c11954b`), and the font-era fixes updated their DR
sections same-commit (`ecbe77f`, `d3f81e6`, `cefc688`, `12e3b63`). Both previously
"absent" DR sections now exist and were verified in place: the **typeface mechanism**
(styles-system §4 chain + §4b drop-ins, TF-1..13 pinned) and the **fault-label seam**
(23-error-tracker §4.5 read-time tables incl. the `None`→raw-code rule, i18n-system
`faultLabel`, and the 22/25/29 adapter blocks — reconciled post-`RB-ERR-2`).

Coverage is claimed from evidence, not diffs — a clean doc produces no diff. The
remaining classes:

**Reconciled without a diff, verification recorded** (audit `clean[]` entries, Opus
spot-checked): `frontend/animal-svg` (no drift found, left untouched);
`frontend/floor-texture-map-view` (named sections verified; remainder below).

**Verified since the pass:** `frontend/render-cycle` — read in full during the FONT-1
work, its cache-bust section exercised against `build-card.mjs`, and its one recorded
unverifiable claim (VIEW_ORDER-mismatch frame reset) since confirmed at `main.js:1602`.

**The real residual — unreconciled, named as the exclusion:**

| doc | evidence state |
|---|---|
| `frontend/architecture-overview` | no recorded verification in any pass |
| `frontend/furnished-render` | auditor's own record: "read in full but not line-by-line cross-checked" |
| `frontend/floor-texture-map-view` (remainder) | sections beyond the verified toggle/render chain unchecked |

**Open questions that hold dependent sections** (need Chris, tracked in
`DOC-PASS-TRIAGE.md`): `discovery.py` trigger semantics; Phased-Jobs doc depth — the §13
ruling makes the phased-job record schema DR material, which also decides whether the
drift-checker's queue-break exempt list gets retired by documenting those services.

Why this is logged in the ledger and not just a TODO: per
[00a §9](../00a-documentation-epoch-lifecycle.md), the documentation is part of the
measurement apparatus. An epoch row that overstates its own coverage tells the next
auditor that a stale region is trustworthy prose — which is the same failure class as a
confidently-wrong DR statement, one level up. The named residual is the honest baseline.
