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

#### CAL-23 round-1 log (2026-08-07)

- TRIM 1/3 submitted: 475 -> 409 (~14%); manifest 23 entries (discard 13 / audit 5 / lore 7).
- COUPLING SCAN: PASS — 0 true leaks (2 substring false-positives adjudicated: both inside
  public names, `first_seen_job_elapsed_seconds` + `runtime_manager`).
- FIRST BLOOD (pre-build): the trim CAUGHT a confidently-wrong claim that SURVIVED the
  truth pass — doc 23 §7.2 documented deprecated `harvest_active_run` (zero callers) as
  the live finalizer wiring; real design is the peek/commit two-phase pair
  (learning/manager.py:460-484). Live doc corrected same-day per §13 (this commit).
- APPARATUS FINDING (blocks builders, awaiting Chris): the examination suite is 81%
  WHITE-BOX — 35/43 tests touch private names (`_record_rising_edge`,
  `_is_in_secondary_error`, `_grace_cancels`, ...). A coupling-compliant reconstruction
  CANNOT pass them regardless of doc quality: the tests use the implementation as their
  answer key — the inversion the protocol's three-proofs clause forbids. Production even
  keeps the deprecated method alive FOR these tests (its own docstring says so).
  PROPOSED RULING (a): examine reconstructions against the 8 behavioral tests + NEW
  tester-authored public-contract pins (biting-pin bounty's purpose); the 35 white-box
  tests are handed to the in-flight test-hardening effort as over-pinned findings — they
  reject any correct reimplementation, i.e. they assert the wrong contract (verdict-C at
  population scale). Alternatives: (b) run all 43 and drown review in C verdicts;
  (c) pause CAL-23 behind the hardening. Recommendation: (a).
