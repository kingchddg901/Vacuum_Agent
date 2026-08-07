# Ablation closed-invariant ledger (protocol rule 9)

Each CLOSED round records the earned invariant AND the misreading it prevents.
Reopening a ledgered invariant requires NEW evidence; re-proving one pays nothing.
Escrow states live beside this file in `_ablation_scores.json` (rule 12b: every
score is provisional until chain-close + audit-window expiry). The economy is
bookkept by the coordinator's script, never by agents.

| # | doc §  | invariant (the meaning that proved load-bearing) | the misreading it prevents | closure evidence | round |
|---|--------|--------------------------------------------------|----------------------------|------------------|-------|
| — | (none yet — calibration on doc 23 in progress) | | | | |

## Round log

### CAL-23 — calibration, doc 23 (error tracker) — OPEN 2026-08-07

- Target: `custom_components/eufy_vacuum/core/error_tracker.py` (1,269 lines)
- Examination: `tests/integration/test_core_error_tracker.py` (43 tests) — run by the
  TEST role against the reconstruction; never present in the builder's sandbox.
- Staffing: trim/build/test = Sonnet, review = Opus(high), coordinator = Fable (this
  round only — the calibration measures whether that tier is needed at all later).
- Trim budget: 3. B-repair cap: 2. Discovery rounds need 2-of-2 fresh builders.
