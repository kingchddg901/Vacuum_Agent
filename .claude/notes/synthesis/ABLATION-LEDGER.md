# Ablation closed-invariant ledger (protocol rule 9)

Each CLOSED round records the earned invariant AND the misreading it prevents.
Reopening a ledgered invariant requires NEW evidence; re-proving one pays nothing.
Escrow states live beside this file in `_ablation_scores.json` (rule 12b: every
score is provisional until chain-close + audit-window expiry). The economy is
bookkept by the coordinator's script, never by agents.

| # | doc §  | invariant (the meaning that proved load-bearing) | the misreading it prevents | closure evidence | round |
|---|--------|--------------------------------------------------|----------------------------|------------------|-------|
| 1 | 23 §4.3 | `error_label_key` returns a declared label only when the adapter's label map stores a non-empty string for that code; any other stored value (number, empty string, nested structure) resolves to `None`, exactly as an absent entry does — a label is never manufactured from a non-conforming entry. | §4.3's bare `dict` typing + `-> str | None` signature reads `str(value)` as conformance; the build brief's no-defensive-padding rule then forbids guessing stricter. | PROVISIONAL (escrow) — pends round-2 2-of-2 fresh-builder green | CAL-23 R1, provenance NEVER-PRESENT (original doc equally silent; survived two truth passes) |

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

#### CAL-23 round-1 ADJUDICATION (Opus, 2026-08-07) — precedents

- Verdicts: RED-1 C (flag read by nothing repo-wide — pin asserts non-contract; honest
  fallback recorded: if overruled -> D/NEVER-PRESENT), RED-2 C (defensive floor's side
  effect, not a semantic), RED-3 **D / NEVER-PRESENT** -> earned invariant #1, RED-4 C
  (verbatim pin asserts an absence with no consumer).
- PRECEDENT (C-class): a mutation-certified pin proves DETECTION, not CONTRACT; reds pay
  only on a consumer / invariant / stated design. PIN-11 flagged as the farmable shape
  (pins an undocumented absence; survives on consequence only).
- APPARATUS after adjudication: 8 behavioral legacy + 9 surviving certified pins (3
  C-verdict pins retired; the RED-3 pin STAYS as invariant #1's pin).
- TRIM-FIDELITY: (a) the trim ADDED §3.1's `acknowledged` row unlogged — the addition
  likely INDUCED RED-1; manifest blind spot -> protocol amended (additions logged);
  (b) trimmer's §7.2 correction beat the repo fix but overshot ("fully supported" vs
  source's DEPRECATED) -> round-2 fix.
- SCORE STATE (escrow): trim burned ZERO confirmed meaning in 66 removed lines; builder
  recovered peek/commit, identity-gated commit, deep-copy, re-arm guard,
  replaces-not-merges, explicit-0, limit=0, listener arity, thread-safe save from prose
  alone. All balances PROVISIONAL pending round-2 closure.
- ROUND 2 (surgical, trim submission 2/3): add invariant #1 to §4.3; restore §6.2
  harvest DEPRECATED status; manifest gains an ADDITIONS section. Then 2-of-2 fresh
  blind builders per the discovery rule.
