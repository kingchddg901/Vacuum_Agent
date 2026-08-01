# REVIEW-05 — Risk register (Passes 8, 9, 10)

## Highest blast-radius repairs
1. **RP-018 slug-led carry (RF-25b)** — touches how every room edit persists.
   Now double-gated: D5's stored-slug dedupe migration (RP-015) + a REAL Ivy re-map
   capture required for closure. Rollback: revert restores id-led carry; the dedupe
   migration itself needs MIGRATION_INSPECTION_GATE (before/after dumps; suffixed
   slugs are additive and reversible by stripping — recorded algorithm required).
2. **RP-031 (RF-14/05) service contract pass** — public semantics; automations see
   new errors. Mitigation: convention table at Gate 4 (Q9); response-not-raise for
   automation-common services.
3. **RP-026 (RF-09) mapping identity** — medium confidence on the Eufy fork linkage;
   verify-first gate added; failure path returns to synthesis, does not improvise.
4. **RP-025/RP-024 (RF-18/19)** — brand vocabulary + precedence; product forks
   authored both ways; legacy stored literals explicitly out of scope (CF-3).
5. **RP-007 (RF-08)** — dispatch refusals; Q16 (wake-by-dispatch) must be answered
   or the packet risks breaking the sleeping-Roborock start path.

## Public contract changes (inventory)
Schema refusals (RP-005), dispatch refusals (RP-007), service raises/responses
(RP-031), graph issue codes replacing English messages (RP-023 — card consumer
named), zone author-time checks (RP-029/RP-022), reject_rooms scoping (RP-040).

## Migration risks
- D5 stored-slug dedupe (NEW — the review's structural catch).
- Learning-archive directory re-key: DEFERRED (DEF-5) — interim warn-only.
- Core-theme tombstones: additive list; seeder consult; reversible by list removal.
- Everything else verified migration-free (Pass 9 challenge applied to each "none").

## Hardware uncertainty
- HC rows lack the Pass-8 record template — **amendment (D11): every checkpoint run
  must record device, firmware, deployed SHA, map identity, starting state, action,
  expected observation, log/capture paths.** Template added to the hardware register.
- Roborock long-idle disconnect: HC-2/HC-4 Ivy legs already require wake+reload;
  Pass-8 rule 6 (upstream absence ≠ VA failure) noted for interpreters — HW-DIAG-1's
  settled analysis is the reference.
- Mid-job recharge capture: RESOLVED per GATE4 Q14 — simulation + production-listener
  parity verification; hardware optional only if parity cannot be established.
- Two-Eufy HC-4: RECLASSIFIED per GATE4 Q13 — **unsupported/implausible on current
  hardware (no Omni E28 exists; inventory error corrected)**. RF-09 multi-Eufy
  closure = source + single-device regression; multi-device proof left open.

## Source-only HIGHs — sufficiency decisions (Pass 7)
- A6-PRE-1, A4-STARTs, WD/CAN/STR members: source sufficient (branch logic; frozen
  rubric consequence-based) — reproducers specified in tranche-2 packets.
- A1-EST-2 (external battery dilution): needs one app-started-run capture (HC-2
  ride-along) — upgraded from source-only to capture-verified closure.
- A6-VAC-1 (dock mid-external): capture on the same run.
- DQ-PAY-2 ("" to wire): source sufficient (executed evidence exists in record).
- No HIGH retained on "sounds architectural" grounds; no downgrades for rarity.

## Reopened clean areas (Pass 10 obligations)
- RP-006 (read_json seam) touches EVERY learning reader → obligation: full learning
  suite + an estimator golden-output fixture pinned BEFORE the change (add to RP-006
  regression block).
- RP-009's shared sync helper reopens the sensor platform's clean areas → parity
  test present ✔; ADD: card-rendered room list smoke on HC-1.
- RP-013a..e reopen learning-ingest clean areas → the stepped-run BEFORE capture is
  the baseline; plus stats_rebuilder tolerance pre-check (REVIEW-02/RF-11).
- RP-021 reopens run-plan clean areas (the killed DQ-ACT-4/PH-4 guards): regression
  MUST include the killed findings' scenarios as pinned-behaviour tests (preflight
  still blocks zone-first until the whole-plan fix lands; after it, starts succeed).
- RP-025 catalog threading reopens profile resolution areas → golden resolution
  fixtures per brand pinned before edit.

## Unresolved Chris decisions (consolidated — now 17)
Q1..Q14 from SYNTH-05, plus:
- **Q15 (D3):** orphan registry entries — report-only cleanup policy.
- **Q16 (RF-08):** wake-by-dispatch with stored ids vs refuse-until-awake.
- **Q17 (D6):** leading charge_wait — non-clean phase-0 support vs keep-trim+card-honesty.
