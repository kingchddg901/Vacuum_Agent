# FREEZE — repair synthesis snapshot

**SHA:** `7108519b57d8adcf032c23aa5a133354c2d662ec`
**Taken:** 2026-07-31T19:12:41
**Size:** 3.32 MB · 12 audit artifacts + 63 non-audit records

## Why this exists

**11 of the 12 audit artifacts lived in `AppData/Local/Temp/` at freeze time** — session-scoped
and subject to cleanup. The ledger is GENERATED from them, so the evidence base for 482 findings
was one temp sweep away from unrecoverable. This snapshot copies them out.

`_frozen/_audit_runs.json` is rewritten to point at the frozen copies, so the snapshot is
self-contained and regenerable without the temp directory.

## Reconciliation (computed from the frozen copies)

| | |
|---|---|
| audit survivors | 421 |
| open non-audit (direct reads + targeted agents) | 61 |
| **open total** | **482** |
| killed records (Corpus C) | 21 |
| clean areas | 673 |

Matches the committed ledger at this SHA.

## Contents

- `audits/` — the 12 structured audit outputs (#7–#18)
- `reproducers/` — `_proof_onboarding.py`, `_proof_setup.py`, `_proof_battery.py`,
  `_proof_debug.py`, `_stageA_repro.py`
- `_direct_reads.json`, `_clusters.json`, `_order.json`, `_calibration.json`
- `_stageB_result.json`, `_mapping_result.json`
- `highly-aggressive-audit.md` — the generated ledger as of this SHA
- `FREEZE.json` — SHA-256 digests for every artifact

## Known gap

`.claude/notes/` is git-ignored, so this snapshot is **machine-local**. The generated ledger is
committed and survives; the evidence it was generated FROM does not. Committing `_frozen/`
(3.32 MB) would close that.
