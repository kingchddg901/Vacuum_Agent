# Executive Synthesis, Registers, and Questions for Chris (Gate 3 package)

**Session:** Fable synthesis pass (claude-fable-5), 2026-07-31→08-01. Corpus: 516 records
/ 484 open at freeze `5be0931`, source at `c61b3eb`.

## Executive synthesis

The 484 open findings resolve into **33 accepted repair families + 3 batch groups
(small-correctness, dead-code, doc-only) + 5 deferrals**, with **zero unassigned
findings** (machine-checked: `synthesis/closure-matrix.json`). Six candidate families
were **rejected** after §G attack and are recorded so they are not re-proposed — most
importantly, no global "absent-vs-empty" helper and no vocabulary-constants module:
four distinct invariants and the question-not-vocabulary rule forbid them.

The campaign's center of gravity is not 484 independent bugs. It is **eight structural
invariants** violated repeatedly:
1. **Protected windows that don't cover their gate** (finalize claim — the
   hardware-proven CRITICAL that reopens the campaign CRIT).
2. **Absence of evidence consumed as evidence of absence** (empty discovery wipes
   stores; failed reads erase history; unavailable entities satisfy negating rules).
3. **Ownership by string prefix over a non-injective join** (proven cross-vacuum
   registry deletion).
4. **Refusals invisible to callers** (result dicts dropped at service/entity
   boundaries — the backend twin of audit #6's card finding).
5. **Identity carried by unstable keys** (numeric ids through re-segments; slugs
   without uniqueness; segment ids recycled under user overlays).
6. **Stale data served as live** (stored segment ids on total resolution miss;
   sticky-hold pose with an unread stale flag; caches with no freshness identity).
7. **Vocabulary owned by literals instead of the declared catalog** (the Eufy-ism
   seam, ~80% applied, now completable — bounded by four killed lookalikes).
8. **Setup without teardown** (loop-lifetime work orphaned across reloads, including
   the stale-manager store clobber).

**Packet tranche 1 (RP-001..RP-009) is authored to full §K rigor** and covers: the
finalize window + its refusal consumers, the manager shutdown seam, flight-recorder
redaction, all five room-store wipe CRITICALs, RMW read-conflation, the two
wrong-room dispatch CRITICALs + source freshness, the blocker-dropout CRITICAL, and
the entity-ownership family. That is **every CRITICAL that is closable without
product decisions**, plus the two instrument fixes hardware validation depends on.
Remaining CRITICALs land in named later packets: A1-ID-1/A2-REC-2 (RP-015, slug
uniqueness), A3-CRUD-4 (RP-016, remove_map completeness), A4-PP-RP-2 (RP-021,
overwrite steps), LC-1/EXT-1/EXT-2 (RP-026, mapping identity), INIT-1 (RP-003 ✔).
**Tranche 2 packets (RP-010..RP-040) are specified at design level in the catalogue
and graph; full §K authoring follows Gate 3 review** — authoring 31 more packets
before Chris re-shapes families would spend the expensive window on text he may
redirect.

## Severity re-grade policy (the 84 conflicts)

Per frozen plan §5, conflicts were resolved by **consequence class**, not averaged:
the corpus's `severity_effective` stands except where the catalogue notes a regrade.
Explicit regrades made during adjudication:
- **A5-AG-2 MEDIUM→HIGH** (one unconfigured room blocks every run on the map — broad
  inability to perform primary function).
- **DQ-ACT-5 confirmed HIGH** (wet-mop on dry rooms = destructive actuation; the
  "best-effort" framing does not reduce consequence).
- **DR-ONB-3's earlier LOW→MEDIUM upgrade** (sibling-guard evidence) retained.
- All `!C` findings inherit their family's consequence tier in the closure matrix;
  no finding was down-graded on trigger rarity (rubric forbids it).

## Compatibility & migration register

| Change | Risk class | Mitigation |
|---|---|---|
| RP-005 schema refusals (null/[] enabled_room_ids) | automation-visible | loud vol.Invalid text; release notes |
| RP-007 total-miss dispatch refusal | behaviour change after re-segment | user-facing reason; was wrong-room clean before |
| RP-031/RF-14 refusals raise | automations see errors that were silent | convention table reviewed at Gate 4; release notes |
| RP-018 slug-led carry (RF-25b) | changes carry-over on renumber | staged, Chris-flagged; identical when ids stable |
| RP-024 precedence clamp reframe | product semantics | both variants authored; Chris picks |
| RP-015 slug disambiguation suffix | learning keys for COLLIDED rooms only | collided history was already misattributed |
| RF-17 core-theme tombstones | new persisted list | additive; seeder consults it |
| RP-013 record additions (allocated flags, cumulative set) | additive schema | rebuilder tolerates absent keys |
| NO entity-registry migration anywhere | — | RF-04 §G decision eliminates the campaign's only registry-migration risk |
| Directory re-key for learning archive (IO-6) | real migration | DEFERRED (DEF-5, MIGRATION_INSPECTION_GATE) |

## Hardware validation register

| Checkpoint | Device path | Needs | Baseline state |
|---|---|---|---|
| HC-0 | lifecycle/finalize (Ivy + Alfred) | cancel-and-dock ×2 on Ivy | ✔ ivy-run-BEFORE.log / alfred-run-BEFORE.log |
| HC-1 | tier 1 | reload ×2, entity list, panel | n/a |
| HC-2 | dispatch + lifecycle (both) | **NEW BEFORE-CAPTURE REQUIRED: Alfred STEPPED run (charge_wait + 2-room group) before RP-013 lands** — the only decaying item this synthesis adds. Also: Alfred cancel-during-dispatch, app-started run; Ivy wake + stepped/cancel runs | partial (single-room Alfred; 2 cancelled Ivy jobs) |
| HC-3 | zone + profiles (both) | Alfred zone clean; Ivy profile apply + stored-room inspect | none needed beforehand (source-decidable fixes) |
| HC-4 | mapping (both) | (CORRECTED per GATE4 Q13: **no Omni E28 exists in the fleet** — inventory error.) RF-09 multi-Eufy closure = source verification + single-device regression; multi-device proof stays OPEN (gate recorded unsatisfied, future hardware/tester) | none |
| HC-5 | tier 1 card walk + ride-alongs | mop-wash cycle (RF-30), ETA observation (RF-21) | rides HC-2/HC-3 captures |
| Expensive outlier | mid-job recharge (A4-AJ-1/TRK-2) | staged low-battery run — OR simulated charging transitions in tests + source gate | Chris decides if the run is worth it |

Every capture: flight recorder **Everything (unfiltered)**, started via
`eufy_vacuum.debug_capture_start` (the switch cannot set target/ring).

## Unresolved questions for Chris (numbered — answers unblock Gate 4)

1. **RP-001 `_stored_job is None`:** refuse (recommended: return
   `{"finalized": False, "reason": "no_active_job_record"}`) or keep proceeding
   claim-less with a warning? (Packet ships the warning; refusal is one line more.)
2. **RF-19 precedence:** is floor-default-over-profile for water DELIBERATE? Pick:
   (a) uniform precedence + carpet-as-safety-clamp (recommended), or (b) keep
   override, fix only the custom-snap in the match candidate.
3. **granite/concrete water default value** (recommended: the brand's tile/marble
   value).
4. **RF-24 slug collision suffix** `_r{room_id}` — approve the scheme (product-visible
   in entity names for collided rooms only).
5. **RF-25 enable semantics:** first-import enables all; incremental discovery adds
   rooms DISABLED + unconfirmed — confirm.
6. **STATE-5 reopens your 3d decision:** trouble_rooms' denominator only advances
   while queued (it does NOT self-heal for unqueued rooms). Rebuilder now, or accept
   with the map-scoping fix only?
7. **RF-17 overwrite_theme semantics:** minimal fix (refuse with no active theme,
   document active-as-source) or full fix (draft-over-target)?
8. **INF-6 repairs.py:** delete the unreachable repair flow (recommended) or wire a
   first issue?
9. **RF-14 convention table** (raise vs response per service class) — review at
   Gate 4 before RP-031.
10. **setup_reject_rooms:** confirm map-scoping + un-reject service surface (RP-040/
    A4-SETUP-6).
11. **CF-9 edge-mopping control removal:** the carried note is reconstructed — confirm
    intent before the card packet.
12. **Eufy zone repeat ceiling** (RF-23): is 2 the device truth for zones as for rooms?
13. **HC-4 two-Eufy run:** will you run Alfred + Omni together for RF-09 proof?
14. **Mid-job recharge capture** (register's expensive outlier): run it, or accept
    test-simulation closure?

## Where NO abstraction should be introduced (explicit statement)

- No `common/` module, anywhere (doc-32 §M1 hard rule).
- No global absent-vs-empty helper; no shared "destructive write guard" across
  RF-02/03/13/15 (four incompatible refusal behaviours).
- No vocabulary-constants module; no merged status-set constants. The in-flight
  predicates, BLANK_STATE_VALUES, and step_types already own their questions —
  adoption, not addition.
- No unique_id scheme change, no parser for it, no entity-registry migration (RF-04).
- No shared version-hash helper across map sources (RF-09: same rule, different
  fields per source — a field-list parameter would be a bare vocabulary).
- No reset-detection logic in phase timing (killed A3-REC-7's premise stays dead).
- No synthetic per-room timings inside Eufy group phases (allocation flags instead —
  fabricated exactness is worse than honest allocation).
- No re-tuning of empirical constants (breakpoints, penalties, CV thresholds) —
  structure-only repairs in RF-21; DEF-3 guards the segmentor.

## Deliverables index

| File | Content |
|---|---|
| SYNTH-01a/01b | family catalogue (accepted/rejected/deferred/batches) + addendum |
| SYNTH-02 | dependency graph, waves, hardware checkpoints, frontend consumer nodes |
| SYNTH-03 | packets RP-001..RP-004 (Wave 0, full §K) |
| SYNTH-04 | packets RP-005..RP-009 (Wave 1, full §K) |
| closure-matrix.json | all 484 open findings → families (machine-generated, 0 unassigned) |
| this file | executive synthesis, regrade policy, registers, Chris questions |

**Role compliance:** no repository source was modified; reproducers are specified
inside packets for the main agent to materialize (`_proof_finalize_window.py`,
`_proof_manager_reload.py`, `_proof_rmw_conflation.py`, `_proof_stale_dispatch.py`,
`_proof_blocker_unavailable.py`; existing `_proof_setup.py` attached, not recreated).
Sonnet packets never reference the corpus.
