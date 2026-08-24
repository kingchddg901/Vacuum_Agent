# Highly Aggressive Audit

A deliberately hostile, multi-agent review of this integration, run subsystem by subsystem.
This page is the working ledger: **what it found, what has been fixed, and what has not.**

## What the campaign is

Each audit takes one subsystem and runs a fan-out of agents against it — discovery agents
split by area, then two adversarial verifiers over the pooled findings. One verifier is
scored on *false positives killed*; the other must reproduce each finding with concrete
inputs and correct the severity. A finding only survives if neither kills it.

The fan-out is **scaled to the target**, not fixed: six finders for a large subsystem, three
for a 668-line module. Cost tracks agent count far more than lines of code, and the verify
stage has a floor of roughly 200k tokens regardless of target size — so below a few hundred
lines the shape stops paying and a **direct read** by the orchestrator is better value. Some
entries below came that way; they are marked `direct read`.

Rules that earned their place across the runs:

- Every finding must list **the guards that were checked and did NOT rescue it**. A finding
  without that is unverifiable and gets dropped.
- Every agent must also report **areas it examined and found correct**, so "audited and
  sound" is distinguishable from "never looked at".
- Home Assistant runs a single event loop, so a claim needing two coroutines to interleave
  inside a synchronous block is a false positive by construction. A gap *across* an `await`
  is real, and the distinction is stated per subsystem.
- **A comment asserting a guard is a claim to verify, not evidence.** This has repeatedly
  been the finding itself.
- **Read the subsystem's doc before adjudicating a finding.** The doc states INTENT, so a
  code/doc divergence is the finding either way — but it stops a documented design choice
  being reported as a defect. This demonstrably narrowed a claim from three sites to one.

## Confidence

Findings below were reported by an agent and confirmed by two independent adversarial
verifiers. **A small number were additionally re-checked by hand against source; the rest
were not.** Treat an unverified entry as a strong lead, not an established defect, and
re-verify before acting on it — findings have gone stale within hours when other fixes
landed in between.

---

## Completed

**499 changes shipped**, all with tests, all deployed.

| | |
|---|---|
| Audits fully applied | #1 lifecycle · #2 learning · #3 external ingestion · #4 adapters · #5 error tracker |
| Partly applied | #6 card (root cause + top of the repair order) |
| #7 onward | **466** of 494 findings applied via 67 landed packets (CARD-1, CARD-2, CARD-3, CARD-4, CARD-5, CARD-6, CARD-7, CARD-8, CARD-9, RP-001, RP-002, RP-003, RP-004, RP-005, RP-006, RP-007, RP-008, RP-009, RP-010, RP-011, RP-012, RP-013a, RP-013b, RP-013c, RP-013d, RP-013e, RP-013f, RP-014, RP-015, RP-016, RP-018, RP-019, RP-020, RP-021a, RP-021b, RP-021c, RP-023a, RP-022, RP-024, RP-025, RP-026, RP-027, RP-028, RP-029, RP-030, RP-031, RP-032, RP-033, RP-034, RP-035, RP-036, RP-037, RP-038, RP-039, RP-040, RP-042, RP-043, RP-044, RP-045, RP-046, RP-048, RP-049, RP-050, RP-051, RP-052, RP-053, RP-054); rest open — see [Open](#open) |

### The recurring root cause

Six of the first audits converged on one pattern, which the campaign named the
**forgotten override sibling**: a variant is wired into some call sites but not others, and
a permissive default turns the omission into a silent wrong answer rather than an error.
It has since appeared three more times, including twice in fixes made *during* this
campaign. The structural cause is vocabulary propagated by hand-copied literals defended by
comments rather than by a shared helper.

### Shipped changes

| Commit | Change |
|---|---|
| `31da1fe` | fix(profiles): has_stops must count a zone step (forgotten sibling of the run_plan gate) |
| `4a8878b` | fix(learning): forward edge_mopping from both manager estimate paths |
| `afbc075` | fix(learning): a learning hold must suppress zone learning, not just stat rebuilds |
| `46f689a` | fix(rooms): preserve is_transition across a room re-save |
| `c9ee622` | fix(capabilities): let an adapter declare edge-mopping/passes unsupported |
| `f12a87c` | test(adapters): make an undeclared config block a red test; declare the 11 that shipped |
| `43b05c1` | test(adapters): extend the undeclared-key gate one level down; declare the 19 nested keys |
| `9e378a3` | fix(learning): derive job_id from the active job before synthesising a timestamp |
| `5b02547` | fix(lifecycle): claim finalize before the await — exactly-once finalization |
| `25d59ed` | fix(lifecycle): clear an orphaned finalize claim at startup |
| `e49987d` | fix(learning): defer the battery aggregate push past the durable write |
| `557ca17` | feat(learning): make learned_zones repairable from the completed-job archive |
| `30ad484` | feat(battery): make the drain aggregates repairable from the job archive |
| `4b1da8a` | fix(learning): a run excluded from learning must not feed accuracy_stats |
| `111cd90` | feat(learning): make "run a rebuild" actually repair the incremental accumulators |
| `71e089c` | fix(learning): move the exactly-once claim to the chokepoint — the service bypassed it |
| `0f1e2a6` | fix(errors,battery): decide "job in flight" by status, not by a field nothing writes |
| `9538b9a` | fix(errors): use the adapter sentinel set at grace expiry, and stop the re-arm loop |
| `ea302e0` | feat(errors): replace the destructive error harvest with peek + commit (Wave 2b) |
| `ef02c8a` | fix(card): surface service failures to the user instead of only the console |
| `ff4fce8` | fix(card): read the backend's Pause/Resume verdict, and stop the battery warning short-circuit |
| `7a3e730` | fix(card): a skipped room is not "currently cleaning", and 100% is not 1% |
| `1e1db6a` | fix(card): map segments must follow the active map, not be fetched once per element |
| `77d4741` | fix(card): a failed fetch must not be rendered as a confident empty result |
| `0d6593d` | fix(card): zone counts as a stop, early finishes keep their sign, incomplete-run toast is translated |
| `3c10e5d` | feat(snapshot): tell the card which per-room controls the brand honours, and the zone size bounds |
| `4e8414c` | feat(learning): make accuracy_stats repairable — the last unrecoverable accumulator |
| `9612dca` | refactor(steps): promote the step/phase vocabulary to helpers — and keep the two questions apart |
| `27aefb1` | refactor(state): one shared blank-state question, and each caller gets more robust for it |
| `6804d87` | refactor(rooms): one dataclass builds a room record, not two hand-maintained field lists |
| `e8537a4` | fix(external): an unresolved room blocks the graduate, and a pending id cannot escape its directory |
| `dc1de09` | fix(errors): don't clear the error latch when the finalize never wrote a record |
| `6a882b5` | fix(errors): acknowledging mid-run marks the latch instead of destroying it |
| `2065625` | docs(errors): make the advertised error_tracking contract true, and describe what the code writes |
| `6f37a68` | fix(errors): app-started runs latch their errors too, and carry them into the record |
| `12d7e5d` | fix(errors): the latch accessors hand out a copy, so history stops rewriting itself |
| `822eaca` | refactor(adapters): brand selection becomes a registrar table, not an if/else in core |
| `0e9f28c` | fix(rooms): a new room's settings come from its BRAND's default profile |
| `300dc1d` | test(adapters): give the contract test teeth — and it immediately found three real gaps |
| `8144e82` | feat(adapters): say out loud which Eufy default a brand just inherited |
| `fbf7d57` | docs(debug): the mid-capture `logger:` case is a footgun, not a bug — say so |
| `fe7edfd` | chore(audit): commit the frozen evidence snapshot — provenance was one temp sweep from gone |
| `45fdc8c` | chore(audit): stop git translating line endings in the frozen evidence |
| `b960ab3` | chore(audit): recover audit #18's per-finding verdicts and re-freeze |
| `59daba3` | chore(audit): canonical corpus — Gate 1 steps 2-4, and three defects the build surfaced |
| `61879f8` | chore(audit): evidence classes, historical-gap inventory, and the human report — Gate 1 complete bar hardware |
| `c7d2ed5` | audit: capture Eufy hardware baseline, close Gate 1 |
| `00a3dcb` | audit: Roborock hardware baseline + double-finalize observed on hardware |
| `91a777a` | audit: refute my own OBS-IVY-1 mechanism, narrow the question |
| `5be0931` | audit: OBS-IVY-1 CONFIRMED CRITICAL - exactly-once claim has a real race |
| `c61b3eb` | audit: land HW-FINAL-1 in the corpus as a first-class CRITICAL |
| `569d788` | audit: materialize the 5 tranche-1 reproducers - Sonnet precondition met |
| `3ddcc1c` | RP-001: write the finalize permanent gate inside the claimed window |
| `ca6dc75` | RP-002 (1/3): finalize_result_succeeded helper + lifecycle consumer |
| `c2569bf` | RP-002 (2/3): finalize_learning_job service raises on refusal |
| `3875f62` | RP-002 (3/3): stranded-job finalize branches on the refusal reason |
| `76d92fc` | RP-003: manager shutdown seam + unload ledger (INIT-1) |
| `27824be` | RP-004: flight recorder redacts + caps tracebacks (DR-DBG-1) |
| `6989031` | RP-005 (card half): setup editor refuses an empty room selection |
| `4217c3c` | RP-005: room-store wipe guard at the room_crud chokepoints |
| `e598e3e` | RP-006 (1/3): read tri-state + learning-store RMW refusals |
| `b0967eb` | RP-006 (2/3): cache write-back refusals (preload + room source) |
| `e35b961` | RP-006 (3/3): map-analysis store gates on available + regression tests |
| `4c42482` | RP-007 (1/3): room-source refresh — distinguishable exits, freshness, coalescing |
| `4bdd3f8` | RP-007 (2/3): dispatch refuses stale segment ids (DQ-ACT-1, DQ-DE-1) |
| `8d244dc` | RP-008: blocker rules — unavailable is indeterminate; edges dedup |
| `6ab1b20` | RP-009: entity ownership without prefix matching (DR-SETUP-1, EP-2) |
| `0ee7e07` | audit: freeze wave-1 reproducer evidence (_proof_wipe_guard + extended _proof_setup) |
| `2c00da8` | audit: HC-0..HC-2 hardware checkpoints SATISFIED (tranche 1 validated on hardware) |
| `1b32515` | docs(readme): HACS Default badges + accurate MIT statement |
| `e967450` | audit: tranche-2 proof harness + wave-2 reproducers RP-010/011/012 |
| `032d210` | audit: wave-2 reproducers RP-013a + RP-013c; MATERIALIZATION-02 |
| `3e9e969` | RP-010 (1/3): dispatch chokepoint re-check + advance-gate suppression |
| `de835ef` | RP-010 (2/3): cancel single-flight latch + lifecycle gate suppression |
| `d3e6139` | RP-010 (3/3): start_zone_clean refuses on an in-flight job (JOB-2) |
| `365f90b` | RP-011 (1/3): watchdog crash/exhaustion liveness marking |
| `4cdcf51` | RP-011 (2/3): reaper consumes watchdog liveness; per-slot isolation |
| `7f6b969` | RP-011 (3/3): room/zone phase re-arm; timing clamps; WD-3 has_native fix |
| `7269020` | RP-012(a): tracker release + flush on finalize (TRK-1/TRK-3/TRK-4) |
| `47f9a25` | RP-012(b): recharge-end resolved on a later listener tick (A4-AJ-1/TRK-2) |
| `a02fd19` | RP-012(c): pose sampler per-vacuum cadence + isolation (POSE-1/2/5, DQ-PH-6) |
| `532a774` | audit: RP-012 proof catches a regression in its own repair; stepped run HELD |
| `4450181` | audit: wave-2 reproducer RP-013b (allocated group timing) |
| `6598b0c` | RP-012(d): port the commanded-dock guard to resolve_mid_job_recharge_resumed |
| `8009189` | audit: wave 2 reproducers COMPLETE — RP-013e, RP-014, RP-013d extension |
| `623372a` | audit: RF-36 battery/charge packets + the coverage gap they expose |
| `ea3d157` | audit: stepped Run A captured — RP-013a/013e confirmed, RP-013d packet is wrong |
| `685a9d3` | audit: RP-013d corrected + RP-013f authored, both from stepped Run A |
| `2712e75` | audit: hostile review of the 9 wave-2 proofs — 1 critical, 4 fixed |
| `7346e84` | audit: coverage check — mapping/ IS covered; battery/+sensor/ are the real gaps |
| `0664eba` | audit: correct the battery coverage claim — it was REVIEWED, and cleared |
| `7d62c32` | audit: resolve SYNTH-11 collision — battery packets become SYNTH-12 |
| `457331a` | audit: materialization handoff for the executing window (waves 3-7) |
| `47a664f` | audit: staged Sonnet prompts to close out the campaign |
| `56901ad` | audit: make S0 executable — verified packet map + four traps pre-cleared |
| `b6b622f` | audit: derive ledger closure state from landed packets |
| `94d3ae5` | audit: wave-3 reproducers RP-015/017/018/019/020 |
| `267ce31` | audit: wave-3 reproducers batch 2 -- RP-038/016/021b/027/041 |
| `e756457` | audit: wave-3 reproducers batch 3 (M3) -- RP-022/023/028/029/033/036 |
| `d25af77` | audit: wave-3 reproducer (M4) -- RP-026 LC-3 only |
| `4a21fc7` | audit: wave-7 reproducers batch 1 (M5) -- CARD-1/3/4/8 |
| `b2e8edb` | audit: wave-7 reproducer (M5) -- CARD-5 missed-rooms retry map scope |
| `9e35d13` | audit: wave-7 reproducer (M5) -- CARD-9 theme preset selection safety |
| `ac7fd30` | audit: wave-6 reproducer (heavy tail) -- RP-031 RF-05a apply_run_profile |
| `3b35145` | audit: wave-6 reproducer (heavy tail) -- RP-034 Q7 overwrite_theme source |
| `95a070f` | audit: wave-4 reproducer (heavy tail) -- RP-021a clause 4 empty-phase crash |
| `99af207` | audit: wave-4 reproducer (heavy tail) -- RP-024 Q2 water precedence |
| `ea8bf6c` | audit: wave-4 reproducer (heavy tail) -- RP-025 clauses i+ii catalog vocab |
| `e679d6b` | audit: wave-5 reproducer (heavy tail) -- RP-030 ROBORO-5 flip_y disagreement |
| `b4dc2cc` | audit: wave-6 reproducer (heavy tail) -- RP-035 SN-9 overlays availability |
| `c98eda6` | audit: wave-6 reproducer (heavy tail) -- RP-039 DIAG-2/4 diagnostics redaction |
| `96e0047` | audit: wave-6 reproducer (heavy tail) -- RP-037 ensure_dirs memoization |
| `baa1068` | audit: wave-6 reproducer (heavy tail) -- RP-040 Q10 reject_rooms map scope |
| `67ceec2` | audit: RP-026 verify-first gate CLEARED — Eufy half proceeds, no fork PR |
| `f4c93d0` | audit: wave-7 reproducer (CARD-2) -- clause 2 allocated-estimate qualifier |
| `450e617` | audit: generate RP-040's per-file table; correct the sensor/battery coverage claim AGAIN |
| `d0be882` | audit: wave-7 reproducer (CARD-6) -- clause 1 leading charge_wait unsupported |
| `4486760` | audit: battery/ and sensor/ WERE covered — direct-read tier, by design |
| `b1d0900` | audit: Stage X — the execution release (5 packets, reproducers in hand) |
| `93888bc` | audit: pre-flight before releasing to Sonnet — paths made explicit, gate pinned |
| `cb0fdb7` | audit: RP-014 site table widened 5 -> 17 (+1) and adjudicated |
| `d5e8d44` | audit: RP-040 table was OVER-INCLUSIVE by 42 — cross-check added |
| `9099d1a` | audit: RP-032 reclassified, CARD-6 clause 2 resolved |
| `34a15b1` | audit: Stage G (RP-032) + Stage C (CARD clauses) handed off |
| `c075b12` | audit: four ownership calls adjudicated + Chris's scope decisions recorded |
| `f212c20` | RP-013b: allocated group timing — a multi-room group phase credits every room |
| `581e940` | audit: RP-013b landed — ledger closure regenerated |
| `ed1a953` | RP-013f (1/2): a stepped run's cleaning_time_seconds sums its phases (REC-A) |
| `3fcda23` | fix(ci): wave-7 CARD reproducers were committed RED and broke node-tests |
| `0ff1e9f` | RP-013f (2/2): wall-clock fallback subtracts commanded breaks (REC-B) |
| `d9ce30c` | audit: handoff gap that caused the red CI — frontend reproducers are CI-gated |
| `9978a03` | audit: RP-013f landed — ledger closure regenerated |
| `8606134` | audit: Stage E template — check CI conclusion after push, not just local |
| `4b0cda3` | RP-013e (1/2): recorder predicate/scope — no more fan-out to finished jobs |
| `dbbb348` | RP-013e (2/2): job_metrics watches the adapter-declared battery entity |
| `cc22c4a` | audit: RP-013e landed — ledger closure regenerated |
| `205ef7b` | RP-013a: phase-type-aware capture validity — break/zone empty timing is valid |
| `8b489c8` | audit: RP-013a landed — ledger closure regenerated |
| `8f4c5a8` | RP-013d: the queue block mirrors the resolved_rooms ladder (A4-STATE-6) |
| `5ad6b06` | audit: RP-013d landed — ledger closure regenerated — STAGE X COMPLETE |
| `7714931` | audit: RP-040 closing batch — delete dead Eufy discovery duplicate (#10:A1-ID-5) |
| `d37e501` | audit: RP-040 closing batch — battery/manager.py anchor + session fixes (DR-BAT-2, DR-BAT-3) |
| `d86e18e` | audit: RP-040 closing batch — delete 4 dead const.py entries (INF-7) |
| `59cdf66` | audit: RP-040 closing batch — core/manager.py callback + start-status fixes (CB-3, CB-4, START-3) |
| `f3387e3` | audit: RP-040 closing batch — dispatch/manager.py OFF-fallback sends real option string (DQ-ACT-7) |
| `cc9baba` | audit: RP-040 closing batch — fix battery doc drift (DR-BAT-1, DR-BAT-4) |
| `0e6b1e0` | audit: RP-040 closing batch — fix onboarding doc stale line reference (DR-ONB-6) |
| `faf2e89` | audit: RP-040 closing batch — learning/history_store.py path-safety, durability, dead code (IO-5, IO-7, IO-8) |
| `aa413d7` | audit: RP-040 closing batch — listeners/_common.py delegates get_adapter_value (COMMON-5) |
| `4405267` | audit: RP-040 closing batch — pose_sampler.py docstring understated its own blast radius (POSE-6) |
| `ecb47ef` | audit: RP-040 closing batch — delete dead Roborock room extractor with disputed coordinate frame (#11:A3-EXT-5) |
| `d242c51` | audit: RP-040 closing batch — maps/map_manager.py detached-copy + live counts (DR-MAP-1, DR-MAP-2) |
| `f7eae2d` | audit: RP-040 closing batch — models.py doc fix + dead VacuumCapabilities (ID-6, INF-3) |
| `0db5e11` | audit: RP-040 closing batch — onboarding/manager.py shares the default-record builder (DR-ONB-4) |
| `c2bff98` | audit: RP-040 closing batch — planning/run_plan.py water estimator fixes (EST-H2O-2, EST-GUESS-1, EST-CLAMP-1) |
| `bea97f9` | audit: RP-040 closing batch — queue_engine.py omits null clean_passes_field (PAY-7) |
| `21dce08` | audit: RP-040 closing batch — delete unreachable repairs.py (#14:INF-6, Q8) |
| `74a6ac6` | audit: RP-040 closing batch — rooms/room_crud.py CRUD-7 closed incidentally by DR-MAP-1, no code change |
| `93b83be` | audit: RP-040 closing batch — onboarding sensor no longer vacuously "complete" on zero maps (DR-ONB-3) |
| `41aedd6` | audit: RP-040 closing batch — setup/drift.py or-coercion + unguarded int(key) fixes (DR-SETUP-2, DR-SETUP-3) |
| `9c42f03` | audit: RP-040 closing batch — setup/protection.py isinstance guards (DR-SETUP-4) |
| `d54c432` | audit: RP-040 landed — ledger closure regenerated — STAGE M6 COMPLETE |
| `98a4bce` | audit: re-scope the Roborock edge-mopping carried item — the framing was backwards |
| `86191b1` | audit: RF-36 unparked; unreadable is null; Run B recipe corrected; CARD-7 re-shaped |
| `4fe48ab` | audit: RP-032 (a) — build the services.yaml <-> registration parity gate (RF-28) |
| `8deae74` | audit: RP-042 corrected — the phantom-cycle claim was fabricated, severity drops |
| `8b90c28` | audit: RP-032 (b) — SVC-9 group: map_id required-vs-docs-optional (4 learning services) |
| `bf75b22` | audit: RP-032 (b) — WIRE-4 + carpet/floor_type group |
| `2c461dd` | audit: RP-032 (b) — delete 19 dead schema constants (SERVIC-7) |
| `04adb30` | RP-032: document 11 schema-accepted-but-undocumented service fields |
| `78c8bd0` | RP-032: JOB-5 break_type cross-field validation, JOB-6 read/write round trip |
| `64f566d` | RP-032: ZONE-C-7 -- saved-zone kind restricted to what dispatch honors |
| `c9c4cba` | RP-032: SERVIC-4 -- reject degenerate saved-zone geometry at create time |
| `a293ad8` | RP-032: IMAGE--10 -- annotate delete_map_image as the priority no_yaml_entry item |
| `63c9a3f` | audit: NEW live finding — a DOCK fault zeroes a productive run's cleaning time |
| `27dbfe1` | notes(RP-032): adjudicate the no_yaml_entry set — 5 entries, 19 internal |
| `b4953b4` | ci: give node-tests the same concurrency guard as tests/validate |
| `1d52fa6` | RP-032: apply Chris's no_yaml_entry ruling -- 24 of 27 resolved |
| `7f1f462` | fix(card): route Cancel through cancel_active_job instead of a bare dock |
| `26ac44e` | notes(RP-032): rule the 3 external-run services in; walk beats grep |
| `f84617e` | capture(RP-013c): the before-picture, on hardware |
| `64e718b` | RP-032: no_yaml_entry FULLY resolved -- last 3 external-run services documented |
| `f9849f5` | audit: RP-032 landed -- ledger closure regenerated |
| `4d09cd8` | notes: derive hardware validation from the ledger, stop asserting "none" |
| `0ff4a8a` | RP-013c: job-cumulative completed evidence (RF-11 part 2) |
| `b0da875` | notes: pin RP-013c's commit and regenerate the checklist |
| `2a2fa97` | notes: derive reproducer coverage, drop the stale "26" from the handoff |
| `9644eea` | materialize RP-045: battery health unreportable on both live devices |
| `a3298f1` | CARD-2 clause 3: sample count in the room confidence chip's tooltip |
| `748917e` | materialize RP-043 + RP-044: what the charge ETA divides by |
| `3f0dce3` | CARD-2 clause 1: dim + "last seen" badge for a held/stale map |
| `b555d2c` | CARD-6 clause 2: zone-repeat control gated on a declared capability |
| `472af80` | CARD-6 clause 3 (zone_bounds live readout): drop per Chris's ruling |
| `50d8583` | build: rebuild card bundles + locale reference for CARD-2/CARD-6 work |
| `be7d950` | materialize RP-042: an unreadable battery reported as 0 % |
| `1501db0` | materialize RP-037: SNAP-2 -- the snapshot is neither pure nor composed once |
| `9a00349` | materialize RP-034: core deletes resurrect, imports are unvetted |
| `8b6ec8a` | materialize RP-035: sensor roster keyed off maps; timezone frozen at import |
| `2bb42d1` | materialize RP-030: off-grid clamping, zero-room raster reported present |
| `0a9479a` | materialize RP-021a: a leading charge_wait is saved, shown, and never runs |
| `cc3763e` | materialize RP-026: no per-device map selection; version blind to geometry |
| `77e0348` | materialize RP-031: mutation handlers whose refusal cannot reach the caller |
| `6419254` | RP-013c fix-up: centralize the completed-rooms question; credit the finished phase |
| `6185cf1` | notes: Sonnet handoff -- materialization done, 30 packets ready to execute |
| `8cdd3ef` | CARD-7: design signed off -- setup banner, one decision, three packet corrections |
| `6a8c965` | RP-031 (RF-14/Q9): queue.py -- 3 mutation handlers had no refusal channel |
| `87220b4` | RP-031 (RF-14/Q9): learning/services.py -- 2 mutation handlers had no channel |
| `4f5fa7a` | RP-031 (RF-14/Q9): adapter_config.py -- save/delete had no refusal channel |
| `d677cc9` | RP-031 (RF-05a): apply_run_profile wipes rooms before authorization |
| `a38cac4` | RP-046 groundwork: Eufy fault policy -- source AND evidence validity |
| `f48dee2` | RP-020 (RF-22, SVC-1): exclude/restore_learning_job rebuild accumulators |
| `8f9d5db` | RP-021a (RF-35, clause 1): leading/trailing charge_wait break is unsupported (Q17) |
| `5b21a1a` | RP-046 clause 2: only evidence-invalidating faults reduce cleaning time |
| `1f8c1c2` | CARD-4: translate the three keys missing from all 17 locale packs |
| `0e0369f` | RP-019 (RF-25c): reconciliation becomes reachable and reviewable |
| `a923109` | CARD-3 draft: plain-language rewrites for the 96 jargon fault strings |
| `c005ad6` | RP-034 (RF-17, Q7): overwrite source, core-delete tombstone, import allowlist |
| `9edda4a` | CARD-3 draft: disambiguate the two water systems; fix a depth-sensor slip |
| `e434813` | RP-026 (RF-09): per-device map selection, geometry-aware version, map_id cache key |
| `816665b` | CARD-3: fault rewrites SIGNED OFF -- all 96 English strings approved |
| `382d3d5` | RP-027 (RF-10, blocked_by RP-026): held/cached map results stop freezing the pose |
| `065e389` | CARD-3: land the English fault vocabulary -- 199 codes, 189 keys |
| `9abcb69` | RP-024 (RF-19, Q2 clause 1): water_level is no longer floor-over-profile |
| `71cc479` | RP-025 (RF-18, blocked_by RP-024): catalog is the vocabulary for 2 mechanisms |
| `b8d6ca2` | RP-028 (RF-15): no phantom map buckets, addressed custom-segment writes |
| `63b7e3b` | RP-029 (zone-safety batch, blocked_by RP-028): indeterminate map + aliased reads |
| `6726b19` | RP-015 (RF-24): slug uniqueness at the admission boundary + tracker parity |
| `5af0fa2` | RP-018 (RF-25b, blocked_by RP-015): slug-led carry + Q5 enablement semantics |
| `f0ff25a` | notes: reopen A3-REC-3 -- RP-013c was credited with a fix that does not hold |
| `a193eae` | RP-047: live progress must show the PHASE, not room[0] |
| `1d652dc` | arch: phased jobs -- a concept/execution mismatch, not a bug |
| `64a34e7` | arch: fold gpt review -- withdraw "six packets unnecessary", parent is an aggregate |
| `462b31a` | plan: Option B in six waves -- awaiting approval, no code yet |
| `4f6cb2c` | design: Phased Jobs -- full design, awaiting sign-off |
| `1eedb3a` | design: close the four open items -- Phased Jobs design is complete |
| `00284f1` | design: the phase key -- DTG anchor + ordinal, presence is the phased signal |
| `2650671` | CARD-4: flip the reproducer -- translations landed in 1f8c1c2 |
| `f859a56` | CARD-8 (carried CF-9, Q11): edge-mopping visibility is capability-driven |
| `1ca6e17` | notes: regenerate REPRODUCER-STATUS.md -- surfaces RP-047's missing proof |
| `3e1e2c9` | design: fold the hostile audit -- eight findings, two of them mine to correct |
| `ed46bc6` | Phased Jobs wave 0: the DTG anchor -- written, read by nothing |
| `2feb9e0` | RP-016 (RF-20): per-map store registry + rename/delete referential integrity |
| `3e7a36c` | Phased Jobs: the parent record -- opened at start, closed with boundaries |
| `b75d81a` | Phased Jobs: the parent carries the PLAN as well as the outcome |
| `a3d3e61` | Phased Jobs: hostile audit of the parent store -- six probes, six repairs |
| `1288b65` | RP-022 (RF-23): declared caps on every branch; Q12 zone repeats |
| `74ce10c` | feat(learning): wire the Phased Job parent into the run (wave 1) |
| `7afd39f` | fix(learning): repair six defects a hostile probe found in the wave-1 wiring |
| `66f32c9` | fix(jobs): null-guard the charge-wait battery reads ahead of RP-042 |
| `b49818d` | feat(learning): wave 2 — each clean phase finalizes as its own child |
| `0089613` | RP-042 (RF-36 part 1): an unreadable battery must not be reported as 0% |
| `6790952` | fix(learning): wave 2 wrote no children on the first live run |
| `3610b09` | fix(jobs): the live queue froze inside a multi-room phase |
| `5d2ac9e` | fix(learning): a cancelled run must say WHICH phase was running |
| `c7ae85c` | fix(jobs): a cancelled job could still advance and DISPATCH another phase |
| `e7c12db` | fix(learning): a child must not inherit earlier phases' completed rooms |
| `dc44fb9` | audit-2: charter -- readiness gates, differential scope, method deltas; awaiting sign-off |
| `4db652a` | audit-2: Q2 decided -- mixed-tier fleet; S1 doubles as its calibration |
| `f88b53a` | refactor(learning): retire RP-013c's accumulator — derive it from the phase index |
| `76539c3` | audit-2: reframe the tier rule -- a reasoning premium, not a memory premium |
| `4adcac9` | fix(learning): the child finalize never ran — two bugs a permissive stub hid |
| `bda1bae` | fix(core): a cancel during a wait stranded the countdown on the card |
| `de7ee65` | fix(learning): a user cancel must not mark rooms as chronic trouble |
| `47488b5` | CARD-1, CARD-6(1), CARD-9(1), CARD-2(2): four wave-7 frontend fixes |
| `393e0f7` | CARD-6: VISUAL=1 Playwright baseline for the unsupported-position break |
| `7bd1bb0` | fix(learning): the wave-2 metric scope never applied — children inherited earlier phases |
| `1eb1d86` | CARD-5: missed-rooms retry is map-scoped |
| `0c2ce0e` | feat(learning): wave 3 — an allocated timing never teaches a room duration |
| `4792799` | fix(learning): an unlearned room must not estimate ZERO minutes |
| `9961211` | fix(learning): the SIBLING estimate path also read a zero duration as real |
| `1c8da5a` | RP-038 (RF-30) part 1/2: dock event edge semantics + validation |
| `b474581` | RP-038 (RF-30) part 2/2: dock_events.enabled flag + lifecycle delegation |
| `322a49d` | CARD-9(2)/(3): overwrite confirm dialog + import rejected-keys surfacing |
| `06ffc73` | RP-033 (RF-32): adapter-config seam hardened |
| `8a3bada` | fix(learning): children belong in the general pool — revert b49818d's exclusion |
| `6c44ee5` | feat(learning): a phased job with an excluded child is excluded by default |
| `dd4d8c5` | fix(learning): a phased run counted every room TWICE |
| `d5f9b2d` | finding: issue #46 -- Roborock import blocked by capability-gated map selector |
| `9fc20dc` | notes: close RP-038's checklist rows + flag the RP-033/RP-038 attribution nit |
| `a27c03b` | build: rebuild card bundles for CARD-9(2)/(3) and other landed source changes |
| `782c17c` | fix(learning): room_baselines still learned allocated timings — wave 3's own sibling |
| `671a5c9` | audit-2: correction -- RP-047 was never executed; a193eae is spec-only |
| `53f903c` | fix(jobs): a cleaning phase declared no type, so the capture gate failed open |
| `9693864` | handoff: RP-047 -- the group phase has nothing to advance; execute the spec |
| `6831ccd` | feat(core): RP-047 (a) — the snapshot presents the PHASE, not room[0] |
| `46e8f35` | fix(jobs): a grouped phase would have fired a FALSE STALL on every run |
| `40cbaac` | fix(jobs): rooms must advance inside a group — move the phases guard to the native path |
| `05e75b3` | RP-030 (mapping batch, map_source family): GEO-3/5/6, GEO-4/RB-8, EXT-3, RB-7 |
| `466f8f3` | RP-030 (mapping batch, roborock_raw_map family): ROBORO-1/5/6/7 |
| `83bfa91` | RP-032 (8 map_id-requiredness rows) + RP-030 mapping_services/tracker family |
| `42a51f0` | CARD-7 followup: State A/refresh-fail ordering fix + i18n completion |
| `5ec6893` | fix(jobs): stop charging dock trips to the room the robot is not in |
| `def78af` | feat(jobs): a group phase's rooms get MEASURED timings, not an even split |
| `a6079d8` | notes: phased jobs — steps 1 and 2 landed, step 3 (card) is next |
| `e665db7` | test: autospec the manager stand-ins so a wrong signature fails the suite |
| `075e6cf` | test(battery): pin RF-36's charge-ETA precedence, including the branch nothing covered |
| `a3ea685` | feat(card): the estimate panel shows the plan FROZEN at dispatch while a run is live |
| `1c2d8b1` | RP-035 (sensor/entity platform batch, RF-34) |
| `c9c8f70` | i18n: translate the fault catalogue — de/fr/es/it/nl/pt (6 of 17) |
| `9427890` | i18n: translate the fault catalogue — pl/cs/tr/id (10 of 17) |
| `e19006f` | i18n: translate the fault catalogue — ru/ja/ko/zh-Hans/zh-Hant (15 of 17) |
| `45aa65f` | test(RP-035): assert the room-rename swap actually changes room_name |
| `272955f` | i18n: finish the fault catalogue (ar/he) + gate locale completeness |
| `64b3c57` | fix(eufy): 5014 is a ROBOT battery shutdown, not station power — it invalidates |
| `97689a6` | RP-036 (a/3, RF-21): estimator correctness batch — EST group |
| `ebcea69` | RP-036 (b/3, RF-21): estimator correctness batch — ACC/reanchor group |
| `715f841` | RP-036 (c/3, RF-21): estimator correctness batch — ingest/rebuilder half |
| `1893055` | audit: the ledger was 33 packets stale and kept silently reverting closures |
| `f208788` | fix(profiles): RP-021b #8:A4-PP-RP-2 (CRITICAL) — overwrite re-snapshots steps, not blank |
| `34f9685` | test: a named regression gate for today's phased-run work, before touching run_plan |
| `4c93fb5` | fix(run_plan): RP-021b #8:A4-PP-RP-6 — re-protect the per-group overlay before dispatch |
| `a00ee36` | RP-037 (a/3, RF-29): fs/loop hygiene — mkdir memo, diagnostics executor dispatch, zone bbox pre-reject, dead executor hop removed |
| `7b53ed4` | RP-037 (b/3, RF-29): SNAP-2 — get_job_progress_snapshot becomes a pure read; anomaly emission hoists to the explicit tick |
| `4d7912d` | RP-037 (c/3, RF-29): draft-save debounce + ONB-5 onboarding-summary cache + extended loop-hygiene proof |
| `0fa6cd9` | fix(profiles): RP-021b #8:A4-PP-RP-1 — a stepped apply restores the SAVED settings |
| `4a0afb9` | RP-039 (1/4, RF-16): panel-ledger orphans + async_setup_entry mid-setup unwind |
| `1981640` | RP-039 (2/4, RF-16): services table + ledger joins + per-vacuum teardown |
| `56fb7be` | RP-039 (3/4, RF-16+RF-33): debug_capture.py — shared auto-stop ledger + honesty fixes |
| `498a285` | RP-039 (4/4, RF-33): diagnostics honesty — inert capabilities, redaction, live checks |
| `4b07de2` | test(RP-039): a dedicated entry-unload-ledger proof for the debug auto-stop join |
| `dc25e0a` | audit: resync the ledger after the concurrent session's run — and refuse to over-close |
| `e2a424c` | fix(profiles): RP-021b #13:A5-RUNPROF-4 — the WRITE path refuses; READS stay tolerant |
| `5c4c0f0` | fix(RP-014, RF-12): the three askers that could not see an app-started run |
| `81c1834` | audit-2: fold the reproducer-staleness findings into the charter |
| `408d562` | refactor(capabilities): ONE honors_clean_order predicate — the snapshot copy disagreed with all four gates |
| `9095968` | test(RP-014, RF-12): the three in-flight sites were proof-only evidence |
| `b5d7ddb` | design: trace_route -- route evidence over outcome evidence; charter delta 7 |
| `5692611` | audit: two ledger lines that cited state which has since moved |
| `e2e59b8` | audit: absorb today's landings — RP-014 recorded, RP-021b hold corrected to 4 of 5 |
| `3409a27` | audit-2: delta 8 -- mock-failure ledger with pre-registered decision rule |
| `d84151e` | handoff: the group-phase segmentation fallback is SILENT — a capture run today would record nothing |
| `fabddc9` | feat(observability): decision log — phase_runner and lifecycle stop deciding in silence |
| `52c7d79` | handoff: the silent-segmentation blocker is RESOLVED — decision_log names the gate |
| `7debd37` | probe: replay a real counter stream through the real segmenter — and the root cause it found |
| `3ffd10c` | probe: record the confirmed root cause in the probe's own docstring |
| `e2db2f1` | fix(segmentation): read the area signal BOTH ways — a boundary flushes at the blip as often as after it |
| `67809d9` | fix(segmentation): a wash_plateau must prove the robot left the floor |
| `a97f0d6` | docs(segmentation): the tuning constants are "one unit plus margin", not measurements |
| `ac530c4` | docs(segmentation): fix two comment claims that were wrong, not merely vague |
| `d76d110` | fix(planning): mid-run reachability walks the ACCESS GRAPH, not the queue |
| `333c3db` | test(planning): replace a VACUOUS reachability test with the invariant it missed |
| `53d5a3b` | audit-2: gate 9 gains the ledger's KNOWN uncertainty band, in both directions |
| `f042cf9` | audit: adjudicate #18:A3-IMAGE--1 as OVERSTATED, and render the wontfix list at all |
| `48ae966` | audit: A3-IMAGE--1 — the trigger is not merely rare, it is UNREACHABLE from the UI |
| `1437bc2` | audit-2: delta 9 — the campaign never read the user guide, and severity is a claim about USE |
| `e557f99` | audit-2: mechanical drift checker for docs/advanced/ — 0 breaks, 10 gaps logged for the doc pass |
| `d77e763` | audit: #13:A4-SETUP-6 HIGH -> LOW — mechanism confirmed, harm misdescribed |
| `b0ce9f3` | fix(setup): import a single-map vacuum with no map-selector entity (#46) |
| `03424a2` | fix(maintenance): overdue consumable crashed the upkeep snapshot |
| `174fa9a` | fix(diagnostics): get_upkeep_snapshot was a second non-inert capabilities path |
| `025031b` | feat(#46): observation trace for a missing job-active binary |
| `2d13c4e` | tools(#46): score candidate job-active rules against real history |
| `17f4dc0` | fix(debug): the decision log was not selectable in the flight recorder |
| `972ca42` | fix(maintenance): overdue consumable crashed the upkeep snapshot (for real) |
| `1a99c6b` | audit: close RP-021b for the 4 it landed; split the parked 5th to RP-021c |
| `689125b` | audit-2: section 2b -- partial completion is first-class (OPEN, x of y) |
| `92e24b6` | audit-2: 2b -- blockers are TYPED, not just named |
| `176c73e` | fix(profiles): RP-021c #8:A4-PP-RP-4 — apply the profile's STRUCTURE, not just its rooms |
| `d44496f` | audit: RP-021c landed — the last parked finding is closed |
| `94b5a2d` | audit: credit RP-023a — the two reachability findings d76d110 actually fixed |
| `5141223` | audit-2: restore the section 5 heading my delta-8 edit swallowed |
| `14a4f43` | fix(RP-046, RF-DOCK): report WHOSE hardware raised the error seconds |
| `da6b213` | audit: RP-046 landed — the uncreditable packet is closed |
| `03dba08` | audit-2: SIGNED OFF -- Q1 in scope (S4 confirmed), Q3 docs first, Q4 manual |
| `7d43a75` | fix(mapping,onboarding): B1+B2 — A2-POLYGO-6, A2-POLYGO-7, DR-ONB-1 |
| `ddfb981` | audit: A2-POLYGO-5 + A4-CUSTOM-6 OVERSTATED — the trigger does not fire |
| `8e27bd7` | audit-2: deltas 10+11 -- premise ledger and answerability routing |
| `25b27b8` | audit-2: delta 12 -- recorder-replay corpus as test fodder |
| `3cd755e` | corpus: bank recorder-replay exports -- 57 Alfred + 11 Ivy runs, inventoried |
| `9dab25e` | fix(mapping): B3 — A4-CUSTOM-2 silent data loss, A3-IMAGE--8 null dimensions |
| `e8d380a` | corpus: cross-match inventory to the learned dataset -- 68/68 matched |
| `f43213b` | audit-2: concordance baseline -- a standing lifecycle destabilization detector |
| `52339f5` | fix(mapping): A3-IMAGE--4 — a cached segmentation goes stale with its source image |
| `819eb58` | corpus: kitchen clustering is usage skew, not a signature -- Chris-settled |
| `d101c1a` | corpus: characterize the kitchen skew precisely -- fixed-geometry, varied-settings |
| `ed08643` | fix(mapping): A5-FURNIS-4 — the dragged area label lives ON the room record |
| `84ce7e8` | notes: storage-migration design — the wire-shape rule and the restart-scoped hatch |
| `784e79e` | fix(access-graph): B5 — A6-AGX-2 Half A (delta gate) + A6-AGX-5 (graph-scoped issues) |
| `cc67618` | fix(card): A6-AGX-2 Half B — a refused room edit no longer looks like a save |
| `d1f9b22` | fix(access-graph): A6-AGX-1 + A6-AGX-3 — say WHY, and stop punishing old damage |
| `9ce51af` | fix(#48): Edge Mopping was zeroed on every read — two predicates disagreed |
| `2dd1369` | fix(#48): the duplicate "Vacuum and mop" chip — same root, card side |
| `c613b6b` | fix(card): "Off" is not offered as a water level while mopping |
| `6176c63` | audit: bank ENT-1 + DIAG-1 as release-gate findings (from issue #48) |
| `6b8427c` | fix(access-graph): A6-AGX-4 — access-graph issues can finally be translated |
| `212c62e` | i18n: English-identical ratchet (section D) + strict coverage + 2 fixes |
| `3ff894c` | i18n: nl samples -> metingen -- ruled translate, pending list now empty |
| `9b00a42` | fix(room-access): A6-AGX-6 — a saved edge into the dock room no longer becomes an unrecoverable ghost |
| `81b392d` | audit-2: completeness sweep -- gate 14 field families, strict i18n, setup scope |
| `423fad8` | fix(start): A5-AG-2 — the access-graph refusal names its rooms, and stops being English-only |
| `e348636` | chore(audit): bank live:I18N-1 — the tRaw docstring contradicts translate() |
| `dd78d90` | test(replay): the recorder-save run harness -- real streams drive real listeners |
| `c575aa1` | audit-2: delta 12 status -- run harness BUILT, dispatched-oracle mode open |
| `0a609ba` | chore(audit): A5-AG-2 semantics REJECTED by design owner; bank live:AGX-CLEAR-1 |
| `2715da4` | docs(design): access graph builder — one click-driven modal over a deduped seam |
| `376f644` | refactor(access-graph): Wave A — one pure model owns every graph question |
| `7a9c493` | feat(access-graph): Wave B — set_room_access_graph, one atomic replace-all write |
| `2f1e74f` | docs(design): record what the access graph MEANS, in Chris's terms |
| `14f496a` | feat(access-graph): A5-DOCK-1 — the dock gate Chris believed he had, and the second-dock guard |
| `a9b0089` | docs(handover): the access graph design session, decisions and refusals |
| `f42a7b7` | fix(rooms): INF-9 — the floor_type code travels with its English label |
| `16289e5` | chore(audit): reconcile OPEN-FIX-CHECKLIST against the code — 17 of 27 already landed |
| `c84e502` | fix(button): EP-5 — the saved-run button name goes through the translation mechanism |
| `1e6fd9f` | chore(audit): correct the reconciliation — 19 of 27 landed, and the marker test was wrong |
| `28cc857` | audit-2: seed the premise ledger -- 8 premises, 4 retired with evidence |
| `f6eb0e6` | tools: trace_route -- route capture, fallback census, route diff |
| `9898833` | fix(start): A5-PP-RP-2 — a zone-first plan is runnable, not a corrupt payload |
| `208a884` | harness v2: patch tracking, quarantine rendering, contract versions |
| `4fbb530` | fix(audit): DR-ONB-2, A7-ROBORO-4, DQ-ACT-6 — the last three findings, two narrower than filed |
| `70770a1` | docs(handover): verify the access-graph handover against the code, post-audit |
| `d22acb9` | fix(card): tier-3 — the last untranslated string, and the refusal shape only one call site inspected |
| `1c813a0` | feat(review): surface captured run errors — the evidence reached storage and stopped there |
| `162e391` | fix(roborock): the adapter stops requesting a capability it declares absent |
| `9d6d0dc` | docs(audit): AUDIT-1 closeout write-up — the campaign, written up |
| `6c21647` | fix(review): REV-6 — an absent battery reading stops rendering as "Battery 0" |
| `5b1afb6` | docs(design): the postmortem compiler — audit history as a verified causal graph |
| `6dbda38` | fix(review): REV-5 — the run list states its own truncation |
| `b2ad9da` | fix(review): CC-5 — the matcher's clean-mode chip compares canonically |
| `f6d40cc` | fix(maintenance): CENSUS-6 — server-baked English stops winning over the card's own translation |
| `dddc82c` | docs(postmortem): PM-3 instrument shop + compiler design decisions |
| `a93d428` | docs(design): the time rule -- duration from timestamps, never from volume |
| `ad80b82` | docs(design): name the human-pacing bias behind the time rule |
| `dfff15f` | feat(a11y): OpenDyslexic P1+P2 — the font asset, the token override, the preference |
| `818ad37` | feat(a11y): OpenDyslexic P3 — the picker, wired end to end |
| `dd2ec11` | feat(a11y): OpenDyslexic P4 — harness support, gallery case, user-guide |
| `ec83cd7` | chore(audit): refresh the ledger — OpenDyslexic shipped, DOCK-1 closed, CC-5 cluster down to two |
| `20c0ab1` | fix(diagnostics): live:DIAG-1 — a failed resolution is now distinguishable from an absent capability |
| `367180a` | docs(i18n): live:I18N-1 — the tRaw docstring said the opposite of what tRaw does |
| `de495a1` | fix(access-graph): live:AGX-CLEAR-1 — the refusal now says WHERE the second exit is |
| `9a37ad6` | fix(capabilities): live:ENT-1 — companions resolve by DEVICE as well as by derived name |
| `3fa8d5f` | fix(progress): RP-047(b) — a group phase marks ALL its rooms current, not room[0] |
| `c81c8a3` | fix(external): REV-2 — the wizard suggests the room, it no longer pre-picks it |
| `45c18e7` | Revert "fix(progress): RP-047(b) — a group phase marks ALL its rooms current, not room[0]" |
| `f5b6315` | test(replay): capture the PHASE-ATTR-1 counter series as a replay bundle |
| `00b380e` | fix(phases): PHASE-ATTR-1 — a phase's counters are progress since THAT phase |
| `1c37bde` | Revert "test(replay): capture the PHASE-ATTR-1 counter series as a replay bundle" |
| `3d0a1fd` | test(replay): harvest every retained run into ground-truth bundles |
| `a5e03b9` | test(replay): detect counter units per run, and flag what a delta cannot mean |
| `5e7ce8a` | fix(phases): PHASE-ATTR-2 — rounding jitter is not a counter reset |
| `3f73d7d` | test(replay): eject an arbitrary recorder window, no job record needed |
| `c263ba3` | test(replay): drop *_rule_status from bundles, with an escape hatch |
| `318400d` | test(replay): dedupe repeated-state rows, which makes the noisy filter cheap |
| `1803ca6` | test(replay): cut focused recordings from the general harvest |
| `ce936ef` | docs(phases): the ft² is a per-entity override, not an imperial install |
| `ddd6bf1` | fix(learning): transit_seconds counted cleaning as travel — 83% over |
| `7048f3f` | feat(pose): a 24-hour rolling pose ring, so transit can be decomposed |
| `8267ff6` | fix(card): show where the run has got to, not "queue rooms first" |
| `1f07d36` | fix(learning): a mid-job recharge no longer corrupts room attribution |
| `c14e741` | fix(battery): guard the regime-speed ratio against impossible values |
| `fa96460` | notes: bank BATT-ZONE-1 — the high-zone charge rate is backwards from taper physics |
| `8b7c3ee` | fix(battery): reject an impossible charge rate by value, not by interval |
| `0ee3611` | notes: a staleness check for the ledger, so it reads like a report again |
| `afaedf5` | notes: A3-REC-3 does not reproduce — and the ledger has 32 unbacked hand-ticks |
| `d28b7c0` | notes: inventory the 26 ledger ticks that have no JSON backing |
| `9c52d65` | charter: findings surfaced DURING the audit are tracked, not carried |
| `6cf30ff` | notes: verify all 26 unbacked ticks at source — 23 real, 3 were optimism |
| `cf38d84` | notes: fix 9 backfills that silently missed — the open list is 7, not 16 |
| `56af6b1` | fix(audit): A4-SETUP-6 — room rejection is per-MAP, reversible, and refuses ambiguity |
| `6801fbf` | notes: close the audit ledger — 7 open singles resolve to 1, C17 reaches 4/4 |
| `b78fd81` | notes: restore indent=1 in the four ledger JSONs (formatting only) |
| `2a283eb` | fix(audit): SETUP-REJ-2 — wire the rejection exclusion at the write boundary, map-scoped |
| `321799d` | notes: RP-051 closes SETUP-REJ-2 — open singles now 0 |
| `6f76e59` | fix: a rejection must never DELETE a room — regression from wiring SETUP-REJ-2 |
| `35d2fd8` | fix: a stored map bucket is not a map — centralize the predicate (MAP-GHOST-1) |
| `c7a0900` | fix: deleting a map takes its rejections with it (live-observed orphan) |
| `6e28e78` | test(replay): re-judge harvested runs with current code, and reclassify a tape |
| `1ab8f63` | fix(services): plan_token rendered as a toggle — duplicate `selector:` key |
| `31b3e5b` | notes: reopen A7-ROBORO-4 and DQ-ACT-6 — RP-049 credited two half-fixes as whole (charter 2b) |
| `c0b7ff9` | fix(deploy): /PURGE — deleted files were still running on the live box (DEPLOY-PURGE-1) |
| `148bcc8` | notes: file RB-PROJ-1 — a dead projector empties every Roborock overlay silently |
| `3441978` | docs(roborock): A7-ROBORO-4 closed by verification — ro_dx/dy 0 is the measurement |
| `d4a40b6` | chore(repo): stop tracking generated + bulk telemetry under .claude/ |
| `168b26c` | fix(roborock): count what the overlay projector drops, and say so (RB-PROJ-1) |
| `75fe676` | notes: RP-054 closes RB-PROJ-1 |
| `259d277` | notes: MAP-GHOST-1 wontfix — will not delete stored state on other people's installs |
| `2ed9636` | charter(audit-2): gate 15 — every ledger item addressable, carried items included |
| `a14c08c` | notes: close CC-5 as NOT VERIFIABLE — no seam, no entry (charter gate 15) |
| `facf7a9` | fix(learning): SEG-1 — persist the boundaries the segmenter SELECTED, not just the survivors |
| `ca65835` | notes: close SEG-1 — selected_boundaries lands (facf7a9) |
| `fa8868e` | notes: close FE-ERR-1 / MZ-2 — one centralised refusal check, 10 pins green |
| `df0a2e6` | notes: render settled decisions apart from open work (charter gate 15) |
| `1b3155c` | fix(errors): core carries ENUM-STRING codes, and Roborock declares its tables (RB-ERR-1) |
| `96c1b31` | feat(card): say WHOSE hardware raised a run's faults (C7 / RF-DOCK clause 4) |
| `b1cd3b7` | notes: close C7 — the card now names which hardware raised a run's faults |
| `991a797` | docs(roborock): correct an unverified claim about how the card would translate enum states |
| `b4eb352` | refactor(roborock): move the error tables to vocabulary.py, and fix what the move exposed |
| `f349262` | feat(card): a warning triangle on the run-error badge, so a faulted run is scannable |
| `dda02c7` | build(locales): regenerate en.reference.jsonc for C7's three error-source keys |
| `64ea19a` | feat(roborock): name the fault, in all 18 languages -- 48 keys x 18 packs |
| `4eba1e6` | fix(i18n): use Roborock's OWN manual vocabulary for 14 fault strings in 8 locales |
| `6b47d38` | feat(learning): NAME the faults a run hit — the history snapshot carries run_errors |
| `aa69805` | test(faults): inject all 238 declared codes through the real seam, in 18 languages |
| `70059f6` | feat(learning): job-summary detail — a DERIVED recharge line and per-room rows |
| `bea6d3e` | feat(card): Job Summary modal — the run detail that only ever lived in the JSON |
| `88ac274` | fix(styles): drop three tokens I invented that nothing defines |
| `94bc18a` | build(check-styles): fail when a --evcc-* reference resolves to nothing |
| `8ee6fb9` | fix(styles): resolve all 11 dangling token references, and empty the debt list |
| `dd2a2f7` | fix(i18n): review.badge_errors_seconds needs plural forms in ar and he |
| `c465ba7` | fix(card): the accessibility typeface never applied — the token had no readers |

---

## Open

**28 findings** — 21 across 12 audits plus 7 from direct reads. **466 more applied** via 67 landed packets (see [Applied](#applied)). 0 open clusters (29 fully applied) + 28 singles.

CRITICAL 0 · HIGH 2 · MEDIUM 13 · LOW 13

The same audits recorded **673 areas examined and found correct**.

> **No fix from any audit has run on physical hardware.** That gate comes before a release tag.

### Clusters — several findings, one fix each. Start here.

#### C1. Live-id resolution falls back to STALE stored ids — **verified by hand** — **2/2 applied**

- **Seam:** `dispatch/manager.py:317`
- **Closes:** ~~DQ-DE-1~~ ✅ RP-007 (`4c42482`), ~~DQ-ACT-1~~ ✅ RP-007 (`4c42482`)
- **Defect:** A single-target strict-order phase makes `dropped` non-empty EQUIVALENT to new_segments==[], so the 'live source unavailable' fallback fires for a target that was resolved and REJECTED. The robot cleans a different physical room, and the watchdog re-dispatches the same stale id up to 3x.
- **Fix:** Distinguish 'live source unavailable' (keep stored ids) from 'targets resolved and rejected' (skip or abort). Also correct phase_runner.py:1029, whose comment describes behaviour the code does not have.

#### C2. Cancel is lost across the dispatch chain's awaits — **2/2 applied**

- **Seam:** `jobs/phase_runner.py:553`
- **Closes:** ~~A1-WD-1~~ ✅ RP-010 (`3e9e969`), ~~A2-CAN-1~~ ✅ RP-010 (`3e9e969`)
- **Defect:** _cancel_in_flight is read ONCE per attempt, then four sequential awaits follow (global pre-calls, per-room live settings, live map refresh, dispatch) with no re-read. The user cancels, the robot returns to base, then drives back out and cleans the phase's room.
- **Fix:** Re-read the job (or re-check the cancel flag) between each await inside _dispatch_active_phase.

#### C3. _phase_dispatch_pending left set makes a run un-reapable forever — **4/4 applied**

- **Seam:** `jobs/phase_runner.py:530`
- **Closes:** ~~A1-WD-2~~ ✅ RP-011 (`365f90b`), ~~A5-STR-3~~ ✅ RP-011 (`365f90b`), ~~A2-CAN-3~~ ✅ RP-010 (`3e9e969`), ~~A4-AJ-3~~ ✅ RP-010 (`3e9e969`)
- **Defect:** There is no try/except anywhere in _run_advanced_phase or _dispatch_active_phase. Any raise leaves the guard set, and is_stranded_started returns False while it is set, so the reaper is DISABLED. The job sits status='started' permanently and blocks every future start.
- **Fix:** try/finally so the guard always clears, plus a bounded age after which the reaper stops honouring it.

#### C4. A multi-room phase is recorded as ONE room — **4/4 applied**

- **Seam:** `jobs/phase_runner.py:301`
- **Closes:** ~~A3-REC-1~~ ✅ RP-013b (`f212c20`), ~~A3-REC-2~~ ✅ RP-013b (`f212c20`), ~~A3-REC-3~~ ✅ RP-013c (`0ff4a8a`), ~~DQ-PH-3~~ ✅ RP-013b (`f212c20`)
- **Defect:** A room_group phase attributes the group's entire cleaning time, area and battery to queue_room_ids[0]. A phased job also never records a completed room, so live progress freezes on the group.
- **Fix:** Attribute per-phase metrics across the phase's rooms, or record the phase as a phase rather than as room[0].

#### C5. The repudiated `started_at and not ended_at` predicate is still live — **verified by hand** — **2/2 applied**

- **Seam:** `jobs/active_job.py:1676,1709`
- **Closes:** ~~A3-REC-4~~ ✅ RP-013e (`4b0cda3`), ~~A4-AJ-2~~ ✅ RP-013e (`4b0cda3`)
- **Defect:** SELF-INFLICTED. 0f1e2a6 moved this question onto status because nothing ever writes ended_at, so a finalized job matched forever. Two sample recorders were left behind, and the docstring written in that same commit names both BY NAME as needing the external-inclusive predicate. record_pose_sample:1776 is NOT affected (it has its own status check) -- the finding over-reached on that third site.
- **Fix:** Point record_active_job_sensor_value and record_counter_sample at run_is_in_flight. Roughly 2 lines.

#### C6. Profile round-trip is broken: applying a preset re-labels the room 'custom' — **3/3 applied**

- **Seam:** `profiles/room_profiles.py:435`
- **Closes:** ~~A1-PP-RES-2~~ ✅ RP-024 (`9abcb69`), ~~A3-PP-CRUD-2~~ ✅ RP-024 (`9abcb69`), ~~A6-PP-EST-DSP-1~~ ✅ RP-024 (`9abcb69`)
- **Defect:** water_level (and carpet fan_speed) use a DIFFERENT precedence than every sibling field: the floor-type default OVERRIDES the profile. Candidate dicts omit the key so they take the floor default, while real rooms carry it -- so mop profiles fail to match on every floor except tile.
- **Fix:** Make the floor-type default lose to an explicit profile value, or resolve the candidate exactly the way the room is resolved.

#### C7. Slug identity has no uniqueness guarantee, and the docstring claims it does — **verified by hand** — **3/3 applied**

- **Seam:** `rooms/utils.py:35 + rooms/room_discovery.py:254`
- **Closes:** ~~A1-ID-1~~ ✅ RP-015 (`6726b19`), ~~A2-REC-2~~ ✅ RP-015 (`6726b19`), ~~A1-ID-3~~ ✅ RP-015 (`6726b19`)
- **Defect:** EXECUTED: 'Bed & Bath'/'Bed and Bath', 'Kids Room'/'Kids_Room', "Cat's Room"/'Cats Room', '"Guest" Room'/'Guest Room' each collapse to ONE slug -- and utils.py:16-18 explicitly claims 'distinct names must yield distinct slugs'. Discovery dedupes on numeric room_id only. On Roborock, slug_to_live_id is first-wins, so the second room's target resolves to the FIRST room's segment id and the robot cleans the wrong physical room WITH NO LOG LINE (the dropped-warning path is not reached because the lookup succeeds). plan_migration's existing_by_slug.setdefault is also first-wins, so the second room's stored settings, grants and rules are overwritten and never reported as dropped.
- **Fix:** Enforce slug uniqueness at discovery with deterministic disambiguation (append the device room_id on collision), and make the collision observable. Reconcile the docstring with whatever the code actually guarantees.

#### C8. Reconciliation never runs -- the divergence detector is never invoked — **1/1 applied**

- **Seam:** `rooms/reconciliation.py`
- **Closes:** ~~A2-REC-1~~ ✅ RP-019 (`0e0369f`)
- **Defect:** compute_reconciliation/plan_migration exist and work, but nothing triggers them: no schedule, no event hook, no UI entry point. This is the ROOT of audit #7's CRITICAL (DQ-DE-1): stored ids and live ids diverge because nothing ever checks that they agree.
- **Fix:** Decide the trigger -- on map-source refresh, on job start, or a periodic check -- and surface the result. The machinery is already built.

#### C9. Destructive room writes with no confirmation or preservation — **2/2 applied**

- **Seam:** `rooms/room_crud.py`
- **Closes:** ~~A3-CRUD-1~~ ✅ RP-005 (`4217c3c`), ~~A3-CRUD-4~~ ✅ RP-016 (`2feb9e0`)
- **Defect:** save_managed_rooms unconditionally replaces map_bucket['rooms'], so an empty selection wipes the map's stored rooms. remove_map leaves the map's saved run-profile library, queue state and onboarding orphaned rather than removing or migrating them.
- **Fix:** Guard the wholesale replace against an empty/degenerate discovery, and make remove_map account for every structure keyed on that map_id.

#### C10. async_refresh_room_source returns None on success AND on every failure path — **1/1 applied**

- **Seam:** `rooms/source_refresh.py`
- **Closes:** ~~A4-SRC-1~~ ✅ RP-007 (`4c42482`)
- **Defect:** Callers cannot distinguish 'refreshed successfully' from 'refresh failed, you are looking at stale cache'. dispatch/manager.py calls this immediately before resolving live segment ids, so a silent failure means stale ids go to the wire -- the same wrong-room outcome as C1, by a different route.
- **Fix:** Return a discriminable result and have dispatch refuse (or warn loudly) when the refresh did not actually succeed.

#### C11. The Eufy in-memory map source has NO vacuum identity — **verified by hand** — **3/3 applied**

- **Seam:** `mapping/map_source_runtime.py:839 (eufy_inmem_candidates)`
- **Closes:** ~~A1-LC-1~~ ✅ RP-026 (`e434813`), ~~A3-EXT-1~~ ✅ RP-026 (`e434813`), ~~A4-RB-2~~ ✅ RP-026 (`e434813`)
- **Defect:** VERIFIED: eufy_inmem_candidates(hass, source_cfg) takes no vacuum_entity_id, no serial, no device_id, and appends the WHOLE hass.data['robovac_mqtt'] bucket first. The bounded BFS matches on attribute presence only, so coordinators[0] wins for EVERY vacuum. Six coordinator call sites inherit it (361/397/461/550/645/689): static rooms, live pose, the render raster the card draws, and the raster zone_membership consumes. The per-vacuum _mem_rooms_cache does not help -- its version is a hash of that same wrong raster, so it is self-consistently wrong. Only bites a MULTI-Eufy install; this install has one robot today.
- **Fix:** Pass vacuum_entity_id through and select the coordinator by serial/device_id. The pattern is already there on the other brand: roborock_candidates accepts image_entity_id and puts the per-vacuum entity object FIRST. Forgotten override sibling, fourth instance. The storage fallback is correctly per-serial, which proves per-device identity was the intent.

#### C12. Live pose is projected through the WRONG coordinate frame — **2/2 applied**

- **Seam:** `mapping/map_source_coordinator.py (_load_live_pose_geom / _apply_inmem_pose_to_result)`
- **Closes:** ~~A2-GEO-1~~ ✅ RP-027 (`382d3d5`), ~~A5-POSE-1~~ ✅ RP-027 (`382d3d5`)
- **Defect:** A memory-frame robot pixel is normalized and room-looked-up against .storage-frame geometry. The two frames are not guaranteed equal, so the robot dot and the derived current_room can both be wrong while reporting present:True.
- **Fix:** Normalize the pose against the frame it came from, or refuse to derive current_room when the frames disagree.

#### C13. The sticky-hold `stale` flag is written and never read — **2/2 applied**

- **Seam:** `mapping/map_source_coordinator.py:126`
- **Closes:** ~~A1-LC-2~~ ✅ RP-027 (`382d3d5`), ~~A5-POSE-2~~ ✅ RP-027 (`382d3d5`)
- **Defect:** The last-known-good hold re-serves a frozen current_room/robot_anchor as present:True and sets stale/stale_since/stale_reason -- which have NO consumer anywhere. A docked Roborock therefore reports a phantom room for up to 6 hours, and nothing downstream can tell the difference.
- **Fix:** Either consume the stale flag at every presentation surface, or stop serving a frozen pose as present.

#### C14. The tracker's end_job runs only on a SUCCESSFUL finalize — **2/2 applied**

- **Seam:** `mapping/tracker.py`
- **Closes:** ~~A6-TRK-1~~ ✅ RP-012 (`7269020`), ~~A6-TRK-4~~ ✅ RP-012 (`7269020`)
- **Defect:** end_job has exactly one caller, so every cancel, abort and stranded-reap leaves tracker state live into the next run. The last room of every job also never fires room_completed, because end_job resets the state that would emit it.
- **Fix:** Call end_job from every terminal path, and flush the final room before the reset.

#### C15. `unavailable` satisfies every negating rule operator — a sensor dropout aborts a live run — **verified by hand** — **1/1 applied**

- **Seam:** `rooms/access_graph.py:907 (_room_rule_matches)`
- **Closes:** ~~A6-GUARD-1~~ ✅ RP-008 (`8d244dc`)
- **Defect:** VERIFIED: an unavailable entity still yields a State object, so state_value == 'unavailable' and there is NO availability check anywhere in the matcher. `not_equals` and `not_in` both return True; `missing` returns True the moment the entity is dropped. The rule matches, the room enters direct_blocked, and path_blockers applies path_block_action -- `cancel_and_event` calls async_cancel_active_job, which issues vacuum.return_to_base and finalizes the run as cancelled. `pause_and_event` ends the same way once pause_timeout reaps it. A battery-powered contact sensor dropping off a Zigbee mesh for one poll physically aborts a clean in progress, and the user sees a path-blocked event naming a door that never opened.
- **Fix:** Treat unavailable/unknown as 'no answer' rather than as a value: skip the rule (or hold the previous verdict) instead of letting a negating operator match. Decide the same question once for `missing` vs `unavailable` -- they are different facts.

#### C16. dock_events records a NEW cycle on first sighting or on an availability blip — **2/2 applied**

- **Seam:** `listeners/dock_events.py:74`
- **Closes:** ~~A1-REG-1~~ ✅ RP-038 (`1c8da5a`), ~~A6-GUARD-3~~ ✅ RP-038 (`1c8da5a`)
- **Defect:** The only dedupe is new_val == old_val, with old_val = '' when old_state is None. So an entity first appearing (HA restart mid-cycle), unknown->drying, and unavailable->washing all read as a new cycle. record_dock_event overwrites the last-* timestamp BEFORE the debounce check, and the Eufy adapter declares debounce_seconds for last_mop_wash ONLY -- so dry-start and dust-empty have no suppression at all. An X10 dry cycle runs 2-4 hours, so the window is large and daily. The sibling listener discovery.py:127 DOES filter exactly this class; dock_events is the one of eight that writes durable counters from a raw state arrival and has no such filter.
- **Fix:** Require the previous value to be a real non-trigger dock state before recording a cycle. Move the timestamp write inside the debounce guard.

#### C17. Reactive listeners spawn unbounded concurrent work with no in-flight guard — **4/4 applied**

- **Seam:** `listeners/path_blockers.py + pause_timeout.py + lifecycle.py + pose_sampler.py`
- **Closes:** ~~A6-GUARD-2~~ ✅ RP-050 (`8d244dc`), ~~A6-GUARD-4~~ ✅ RP-011 (`365f90b`), ~~A2-LIFE-2~~ ✅ RP-003 (`76d92fc`), ~~A4-POSE-2~~ ✅ RP-012 (`7269020`)
- **Defect:** path_blockers spawns a _process task per event with no coalescing, so a bouncing sensor stacks them; the 1-minute reap ticker has no in-flight guard while each reap blocks; the pose timer is fire-and-forget so a slow tick overlaps the next; and _process tasks are untracked, so remove() drops the subscription but not the work already in flight.
- **Fix:** One in-flight guard / coalescing pattern, applied to all four. This is the same question four times.

#### C18. The listener layer is a THIRD answer to 'is a job active' — **3/3 applied**

- **Seam:** `listeners/_common.py:110 (is_job_active)`
- **Closes:** ~~A3-COMMON-1~~ ✅ RP-008 (`8d244dc`), ~~A3-COMMON-6~~ ✅ RP-014 (`5c4c0f0`), ~~A5-METRICS-1~~ ✅ RP-014 (`5c4c0f0`)
- **Defect:** jobs/active_job.py owns two deliberate predicates (dispatched_job_is_in_flight, run_is_in_flight). The listener layer uses NEITHER -- _common.is_job_active is an independent third implementation, and job_progress gates on a hand-copied {'started','paused'} literal that is a fourth. On Roborock, is_job_active treats a not-yet-added job_active entity as 'not active'. Fifth instance of the campaign's forgotten-override-sibling pattern, and the first where the divergence is a whole LAYER.
- **Fix:** Route the listener layer at the canonical predicates, or state explicitly why the input layer needs a different question and derive it from the same constant.

#### C19. A public service call wipes a map's entire room configuration, silently — **verified by hand** — **5/5 applied**

- **Seam:** `rooms/room_crud.py:261 (map_bucket['rooms'] = managed_rooms)`
- **Closes:** ~~A3-ROOMS-1~~ ✅ RP-005 (`4217c3c`), ~~A3-ROOMS-2~~ ✅ RP-005 (`4217c3c`), ~~A4-SETUP-1~~ ✅ RP-005 (`4217c3c`), ~~A5-FACADE-1~~ ✅ RP-005 (`4217c3c`), ~~A5-FACADE-3~~ ✅ RP-005 (`4217c3c`)
- **Defect:** VERIFIED BY EXECUTION. Three routes to one unconditional replace. (1) save_managed_rooms against a map with no cached discovery: discovery.get('rooms',[]) is [], build_managed_rooms returns {}, and line 261 replaces wholesale. (2) `enabled_room_ids:` with a blank YAML value -- cv.ensure_list(None) returns [] (confirmed against installed HA core), so the schema turns null into [], which passes the manager's `is not None` check while _normalize_enabled_room_ids([]) yields an empty set, so every room hits `continue`. The None-vs-empty distinction the manager deliberately relies on is destroyed one layer up, at the schema boundary. (3) setup_save_rooms rebuilds from the stale/absent discovery cache and returns {'status':'success'}. Every per-room setting, rule, grant, colour and floor type is gone; none of the three services declares supports_response, so the caller gets no error and no room_count. Documented behaviour is the OPPOSITE: docs/advanced/03-services.md:255 says 'Omit to keep all rooms enabled'. AUDIT #14 CONFIRMS THE LAYER: the same unguarded total-wipe is reachable at the FACADE (A5-FACADE-1) and rebuild_map has it too (A5-FACADE-3) -- so the facade, not the service, is where the precondition belongs.
- **Fix:** Guard the wholesale replace: refuse to persist an empty room set when the previous bucket was non-empty and discovery is empty. Separately, stop the schema collapsing null into [] -- an explicit null must either be rejected or preserved as None. Give these three services a response so a caller can tell.

#### C20. A config-entry reload leaves the OLD manager alive; its orphaned timer then overwrites the store — **verified by hand** — **1/1 applied**

- **Seam:** `core/manager.py:473 + __init__.py:465 (async_unload_entry)`
- **Closes:** ~~A1-INIT-1~~ ✅ RP-003 (`76d92fc`)
- **Defect:** VERIFIED. async_initialize spawns loop-lifetime work -- the dock re-arm poller (hass.async_create_task) and external-run grace timers (async_call_later, 300s x up to 8 re-arms = ~45 min). There is NO manager teardown anywhere: grep for async_shutdown / def shutdown / EVENT_HOMEASSISTANT_STOP across manager.py, phase_runner.py and external_run.py returns nothing, and nothing is registered with entry.async_on_unload. async_unload_entry removes listeners/services/panels and pops DATA_RUNTIME but cancels none of it. A reload then builds a SECOND manager over the same STORAGE_KEY, while the orphaned callbacks still hold self._manager = the OLD one and end in external_run.py:213 async_save() / phase_runner.py:856 _async_save_logged() -- and async_save is a bare whole-root-dict write. So the pre-reload snapshot replaces everything persisted since. The orphaned dock poller can also still call maybe_advance_phase, so a dead manager and a live one can both dispatch to the same physical robot; _dock_poller_active is per-instance and cannot dedupe across two.
- **Fix:** Give the manager a teardown that cancels its spawned tasks and timers, and register it with entry.async_on_unload. Consider guarding async_save against a manager whose entry has been unloaded.

#### C21. Panels registered outside async_setup_entry are never tracked, so unload cannot remove them — **verified by hand** — **3/3 applied**

- **Seam:** `__init__.py:420 + setup/workflow.py:106`
- **Closes:** ~~A1-UP-1~~ ✅ RP-003 (`76d92fc`), ~~A2-DOWN-1~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-1~~ ✅ RP-003 (`76d92fc`)
- **Defect:** VERIFIED. Only __init__.py ever writes `_panels_<entry_id>`, and it appends only what its OWN loop registered. setup/workflow.py:106 (add_vacuum, reached from the panel's own onboarding flow) registers a per-vacuum panel and tracks nothing. panels.py swallows HA's duplicate-url ValueError at DEBUG and returns None, which `if panel_url:` then drops -- so on the next setup the panel is not re-tracked either. services/setup.py:161 schedules a reload immediately after add_vacuum, so the interleaving is automatic. Steady state from a BLANK install: two sidebar entries, one rendering the 'no vacuum configured' placeholder, self-perpetuating across reloads until a full HA restart clears hass.data[DATA_PANELS]. Found independently by THREE of four agents. The reproducer corrected an over-stated sub-claim: it does NOT affect 'every second and later vacuum unconditionally' -- it needs the blank-install path.
- **Fix:** Track every panel registration in the `_panels_` list regardless of where it happens, or give panels.py a register-and-track helper that is the only entry point.

#### C22. Setup starts several things unload never stops — the systemic version of C20 — **6/6 applied**

- **Seam:** `__init__.py async_setup_entry vs async_unload_entry`
- **Closes:** ~~A1-UP-3~~ ✅ RP-003 (`76d92fc`), ~~A2-DOWN-2~~ ✅ RP-003 (`76d92fc`), ~~A2-DOWN-3~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-2~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-3~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-4~~ ✅ RP-003 (`76d92fc`)
- **Defect:** This audit's assignment was to build the table -- everything setup starts, checked against what unload stops. C20 (the manager's spawned tasks/timers) was one known row; these are the others: async_unregister_learning_services removes 16 of the 21 services setup registers, so FIVE learning services survive an unload; the post-job water-amendment state listener and its 180s timer are never cancelled; the debug-capture auto-stop timer survives; and two hass.data[DOMAIN] keys are left behind. Individually LOW/MEDIUM; together they are the same shape as C20 and should be fixed as one pass over the setup/unload pair.
- **Fix:** Make unload the exact inverse of setup: register every unsub/timer/key with entry.async_on_unload at the point of creation, so the two cannot drift.

#### C23. The confidence tier system is INVERTED at the top, and green is unreachable — **verified by hand** — **2/2 applied**

- **Seam:** `learning/estimator.py:117 (_BREAKPOINTS) + :165 (_breakpoint_for_score)`
- **Closes:** ~~A1-EST-1~~ ✅ RP-036 (`97689a6`), ~~A1-EST-5~~ ✅ RP-036 (`97689a6`)
- **Defect:** VERIFIED BY EXECUTION. _LEARNED_BASE (0.55) + _SAMPLE_BONUS_MAX (0.25) = 0.80, which is EXACTLY high.min_score -- so HIGH/green requires a perfect score, i.e. minutes_stddev exactly 0, which real timing data never has. And medium.max_score is 0.79 while high.min_score is 0.80, so the band (0.79, 0.80) matches no bucket; _breakpoint_for_score falls through to _BREAKPOINTS[-1], which is LOW/error -- the BOTTOM of the table, not the nearest tier. Sweep at 12 samples / avg 10 min: stddev 0.05 -> 0.7975 -> RED; stddev 0.15 -> 0.7925 -> RED; stddev 0.20 -> 0.7900 -> AMBER. A room consistent to 3 seconds shows red while a room consistent to 12 seconds shows amber. ui_variant reaches the card verbatim (src/renderers/learning.js:534, rooms.js:742/1196) and job confidence is min(room scores), so one such room drags the whole job estimate red.
- **Fix:** Close the band (make the tiers contiguous, or use a one-sided descending test), and make the fall-through return the nearest tier rather than the last entry. Separately decide whether HIGH should be reachable at all -- as written it needs zero variance.

#### C24. External runs contribute battery=0.0 and the estimator consumes it as a real measurement — **1/1 applied**

- **Seam:** `learning/estimator.py:844 + learning/external_ingest.py:1056`
- **Closes:** ~~A1-EST-2~~ ✅ RP-036 (`97689a6`)
- **Defect:** THE HYPOTHESIS THIS AUDIT WAS BUILT ON, CONFIRMED. build_graduated_job constructs the completed-job record with NO battery block at all (grep for 'battery' in external_ingest.py returns zero hits), yet outcome.status is 'completed' and used_for_learning is True, so is_learning_job admits it. The rebuilder reads job.get('battery',{}).get('used') -> 0.0 and accumulates that into the SAME room_stats bucket as dispatched runs. _safe_float only substitutes a default for None/''/unknown/unavailable -- 0.0 is a valid float and passes straight through. There is no battery_sample_count and no source marker, so 'learned 0%' is indistinguishable from 'no battery data'. With an all-external archive avg_battery_used is exactly 0.0: the card asserts the job costs ZERO battery and battery_warning is False at ANY charge level. And confidence_score is computed from TIMING samples only, so the number carries no warning.
- **Fix:** Either exclude records with no battery block from the battery aggregate, or carry a battery_sample_count so a zero-sample bucket is distinguishable from a measured zero.

#### C25. The incomplete-run log misreports which rooms were missed — **4/4 applied**

- **Seam:** `learning/history_store.py (incomplete-run family)`
- **Closes:** ~~A4-STATE-1~~ ✅ RP-013c (`0ff4a8a`), ~~A4-STATE-2~~ ✅ RP-013c (`0ff4a8a`), ~~A4-STATE-4~~ ✅ RP-020 (`f48dee2`), ~~A2-ACC-4~~ ✅ RP-036 (`97689a6`)
- **Defect:** The final room of EVERY non-completed run is recorded as missed; clear_incomplete_run's docstring claims '(full clean)' but ANY completion clears it; missed_room_ids survive a re-segment and a map switch, so they can name rooms that no longer exist or now mean something else; and a skipped room holds 'current' for the rest of the run so it can never be resolved.
- **Fix:** One pass over the incomplete-run lifecycle: who writes it, what clears it, and whether its room ids are still valid at read time.

#### C26. Learning services destroy or misreport, and say success either way — **4/4 applied**

- **Seam:** `learning/services.py`
- **Closes:** ~~A5-SVC-1~~ ✅ RP-020 (`f48dee2`), ~~A5-SVC-2~~ ✅ RP-001 (`3ddcc1c`), ~~A5-SVC-3~~ ✅ RP-031 (`6a8c965`), ~~A5-SVC-6~~ ✅ RP-006 (`e598e3e`)
- **Defect:** The 22 registrations here were NOT covered by audit #13's services sweep, and they have the same shape: exclude/restore_learning_job report 'stats rebuilt' without rebuilding; finalize_learning_job fires the job-finished event with a FABRICATED payload; retry_missed_rooms permanently destroys the map's room-enable selection; rebuild_learning_stats blanks accuracy_stats before replaying, so a failure partway leaves it empty.
- **Fix:** Same treatment as C19/C26's siblings: make the destructive ones confirm or be reversible, and make every response honest about what actually happened.

#### C27. overwrite_theme resolves against the ACTIVE theme, never the target it names — **verified by hand** — **3/3 applied**

- **Seam:** `themes/manager.py:303`
- **Closes:** ~~A1-CRUD-1~~ ✅ RP-034 (`c005ad6`), ~~A1-CRUD-2~~ ✅ RP-034 (`c005ad6`), ~~A1-CRUD-4~~ ✅ RP-034 (`c005ad6`)
- **Defect:** VERIFIED at source and REPRODUCED by executing the module. overwrite_theme builds `resolved` from vac['active_theme_id'] + the working draft; `existing = library[theme_id]` is fetched but used ONLY to preserve name/source/tags/author. So calling it on any theme that is not the active one replaces that theme's palette with a CLONE of the active one, and line 326 then silently repoints the vacuum onto it. With no active theme the target's palette becomes {} outright. Both return ok:True and services.py persists. The metadata-preservation loop is what makes it silent -- the entry keeps its name and author, so it looks intact. The docstring claims it writes 'the vacuum's working draft'; it writes active+draft and works with an empty draft. The CARD masks it (bindings/theme.js only calls overwriteTheme inside `if (state.activeThemeId)` and passes that same id), so it is service-only reachable -- which is why the verifiers held it at MEDIUM. Also lets a BUNDLED theme's palette be permanently replaced (CRUD-4).
- **Fix:** Resolve against the TARGET entry, or refuse when theme_id != active_theme_id. Decide which the docstring meant and make the code and the doc agree.

#### C28. Bundled themes are protected from neither delete nor overwrite — **verified by hand** — **2/2 applied**

- **Seam:** `themes/manager.py delete_theme/overwrite_theme + preloaded.ensure_preloaded_theme_library`
- **Closes:** ~~A1-CRUD-3~~ ✅ RP-034 (`c005ad6`), ~~A1-CRUD-4~~ ✅ RP-034 (`c005ad6`)
- **Defect:** delete_theme has no source=='core' guard, so a bundled theme can be deleted -- and audit #14's A1-INIT-3 showed the startup re-seed resurrects it, so the deletion is neither prevented nor durable ('gone until restart'). overwrite_theme can replace a bundled theme's palette PERMANENTLY, because the re-seed only restores absent entries, not modified ones. The discriminator already exists and is trustworthy: preloaded.py stamps source='core', _import_scoped allowlists {community,generated,manual} so an import cannot claim it, and save_theme_as_new hardcodes 'manual'.
- **Fix:** Refuse both operations for source=='core'. Chris's spec: bundled themes are system inventory, not ordinary library entries -- protecting them removes the 'deleted until restart' behaviour rather than trying to make deletion durable.

#### C29. delete_theme leaves the working draft orphaned on a base that no longer exists — **verified by hand** — **2/2 applied**

- **Seam:** `themes/manager.py:394`
- **Closes:** ~~A1-CRUD-5~~ ✅ RP-034 (`c005ad6`), ~~A2-DRAFT-1~~ ✅ RP-034 (`c005ad6`)
- **Defect:** delete_theme nulls active_theme_id for every affected vacuum (that guard DOES exist) but line 394 only RE-NORMALIZES the working draft -- it does not empty it, and leaves draft_dirty untouched. set_active_theme twenty lines later does exactly the right thing (_empty_theme_draft + draft_dirty=False). So deleting the theme you are editing leaves a live draft of overrides authored against a base that is gone. Sibling divergence: two adjacent methods, one clears the draft, one does not.
- **Fix:** Per Chris's spec: treat deletion as an atomic destructive transition -- resolve the fallback target FIRST (default_theme_id is nulled at :388 before the vacuum walk at :391, so the chain must run before that), clear working_draft, set draft_dirty=False, set active_theme_id, persist once, notify once. Note delete_theme currently does not persist at all.

### Singles

<details><summary><strong>HIGH</strong> (2)</summary>

- **ENT-1** `adapters/eufy/entities.py:119` · eufy  
  Companion entities are resolved by deriving a name from the vacuum entity id, with no device-registry lookup and no fallback — a device whose entities are named differently reports EVERY capability as absent, silently  
  build_entity_id does string surgery: vacuum_entity_id.split('.')[-1] + suffix. There is no registry lookup, no fallback, and no signal when a derived name does not exist — the capability is simply reported absent. PROVEN
- **A3-IMAGE--1** `mapping/mapping_services.py:1174` · Both. Eufy (eufy_cv_v1) is where re-analysis actually reshuffles ids; Roborock inherits the same read-time enrichment for any image_segments it holds.  
  Re-analysis rebinds the user's room links and manual segment adjustments onto positionally-reassigned segment ids  
  The map overlay silently mislabels rooms after any re-analysis in which blob ordering shifts, and the mislabel is actuating, not cosmetic: tapping a segment polygon calls toggleRoomEnabled for the LINKED room (src/bindin

</details>

<details><summary><strong>MEDIUM</strong> (13)</summary>

- **A6-AGX-2** `core/manager.py:1374` · both _(finder said HIGH; verifier corrected)_  
  The structural gate on every per-room edit is absolute, not a delta: one stored graph violation rejects unrelated edits (fan speed, enable, color) with "The requested access links would make the graph invalid."  
  After a Roborock re-segment + migrate, the user can no longer change ANY room setting on that map — changing a room's fan speed or disabling a room fails with an error claiming they requested illegal access links, which
- **DIAG-1** `diagnostics.py:0` · both  
  entity_resolution reports only what the adapter DERIVED, so 'we looked in the wrong place' is indistinguishable from 'this device has no such entity'  
  The dump lists each declared companion with exists true/false. It never lists what the vacuum's DEVICE actually exposes, so a naming miss and a genuinely absent capability produce byte-identical output. Issue #48 is the
- **A2-POLYGO-5** `mapping/mapping_services.py:769` · Eufy only (adjust_map_segment writes against `image_segments`, populated only by the `eufy_cv_v1` engine; Roborock declares segmenter_engine='noop_fallback' at adapters/roborock/adapter.py:482 so it has no CV store to adjust)  
  Stale `image_segment_adjustments` survive a CV re-analysis and are re-applied by segment_id to whatever polygon now carries that id - moving a room the user never edited  
  Silently wrong overlay geometry after a re-analysis, attributed to a manual edit the user never made on that room. Reversible only by calling `adjust_map_segment` with the exact inverse deltas (the values ARE surfaced in
- **A4-CUSTOM-2** `mapping/mapping_services.py:1550` · Both (Eufy + Roborock). The card path additionally needs a live map source present (mss.present) for the dock-mascot fallback, which is the normal Eufy fork configuration. _(finder said HIGH; verifier corrected)_  
  In custom mode with no resolvable layout, _resolve_active_scope hands writers THROWAWAY dicts — set_companion_anchor / set_segment_room_link mutate a garbage-collected object and report saved: True  
  The mascot visibly stays where the user parked it for the rest of the session (the card never refetches after an anchor write) and silently snaps back on the next page load — repeatedly, with no error and no way for the
- **A4-CUSTOM-6** `mapping/mapping_services.py:1752` · Eufy only in practice — image_segment_adjustments is written against the CV image_segments store, which only the Eufy CV segmentor populates.  
  adjust_map_segment persists a map-level record keyed by a segment id that CV re-analysis recycles — a nudge authored for one room silently re-attaches to whichever segment inherits that id  
  A displayed room outline is silently offset from its true position and falsely labelled as manually adjusted, and the correction the user made is lost from the room it belonged to. Display/linking only — segment polygons
- **DR-ONB-1** `onboarding/manager.py:182` · both · `direct read`  
  remap_confirmed_floor_types mutates in place while iterating, losing confirmations whenever old and new id sets overlap  
  PROVEN by execution. The loop pops str(old_id) and writes str(new_id) into the SAME dict it is iterating over, so a new_id that is also a later old_id consumes the entry just written. Measured: id_remap={1:2, 2:3, 3:4} w
- **DR-ONB-2** `onboarding/manager.py:186` · both · `direct read`  
  check_for_new_rooms compares a PER-MAP stored count against a source with no map scoping  
  The stored side, room_count_at_last_check, is stamped by mark_rooms_discovered from data['maps'][vacuum][map_id]['rooms'] -- per map. The live side reads the vacuum entity's `segments` attribute, which carries only the A
- **A5-PP-RP-2** `planning/run_plan.py:1379` · both _(finder said HIGH; verifier corrected)_  
  Any plan whose FIRST surviving phase is a zone is refused with "Room-clean payload is missing or invalid" — and a live blocker rule can push a plan into that state  
  A saved run that worked yesterday becomes unstartable the moment a door/occupancy sensor blocks the rooms in its first group — with an error that blames a corrupt payload rather than naming the blocked room. The rest of
- **A6-AGX-4** `rooms/access_graph.py:364` · both  
  Every access-graph issue message is a hard-coded English literal and is rendered verbatim in the card on all 18 shipped locales  
  On any non-English install the room-access modal's issue list and its save-error banner are English, including for AR/HE where they are injected into an RTL layout. This is the one place in the access feature where the u
- **A6-AGX-1** `rooms/access_graph.py:651` · both _(finder said HIGH; verifier corrected)_  
  get_access_graph_health emits no verdict — the "runs are allowed" empty graph and the "every run is blocked" partial graph are indistinguishable, and the report's own remediation moves the user from the first into the second  
  The one service documented as the access-graph diagnostic cannot answer the only question that matters — "are my runs blocked right now?". Following its single actionable instruction on a fresh map (mark a dock room) sil
- **A5-AG-2** `rooms/access_graph.py:770` · both  
  A room with no inbound edge makes the whole graph 'partial', hard-blocking every run on the map, and no shipped surface names the offending room  
  After a map rebuild that discovers even one new room, every Start on that map is refused with 'Room access graph is partially configured. Complete it or clear all access settings to allow basic runs.' — a message that na
- **SN-4** `sensor/__init__.py:272` · both · `direct read`  
  Renaming a room never reaches the entity's friendly name - the rebuilt entity carrying the new name is discarded  
  VERIFIED: async_update_entity has ZERO occurrences anywhere in the integration. Both sync blocks construct a fresh entity per desired room and then discard it when the unique_id is already known, pushing only a state wri
- **A6-AGX-6** `src/state/room-access.js:85` · both  
  The card's access modal renders an existing edge into the dock room as "Missing Room N" — an edge that exists is displayed as a stale reference to a room that does not  
  The editor misrepresents the stored graph: a live room is labelled missing/stale, inviting the user to delete a valid edge. Conversely they cannot re-create it, because the dock room is filtered out of the selectable lis

</details>

<details><summary><strong>LOW</strong> (13)</summary>

- **EP-5** `button.py:256` · both · `direct read`  
  The saved-run-profile button name is hardcoded English, bypassing the translation mechanism  
  Every other entity class in scope declares _attr_translation_key and lets HA resolve the name from strings.json. EufyVacuumSavedRunProfileButton sets _attr_has_entity_name = True, declares NO translation key, and overrid
- **DEAD-ROLLOVER-1** `custom_components/eufy_vacuum/jobs/active_job.py:1371` · both  
  _pending_fast_rollover is READ but written nowhere - the fast-rollover branch of room advancement is dead code  
  FILED 2026-08-05 under the charter's new 2c rule, and it is the case that rule exists
for: found while chasing live:ROOM-FLICKER-1, not the thing being chased, and it
survived only because it reached a closing summary. A
- **A3-IMAGE--8** `mapping/mapping_services.py:910` · Both; depends on whether Pillow is importable on the host.  
  Upload persists width/height as None when Pillow is unavailable and still reports saved:True  
  On a Pillow-less install a successful upload is recorded in a state that makes custom-segment authoring report a missing backdrop, and the variant row displays null dimensions. Confined to installs without Pillow, and th
- **A3-IMAGE--4** `mapping/mapping_services.py:933` · Both. _(finder said MEDIUM; verifier corrected)_  
  Re-uploading a map image does not invalidate image_segments, so a default analyze returns the previous image's segments  
  An automation or script that uploads a refreshed map export and analyzes it gets the previous map's room geometry back with a success-shaped response and no staleness signal. The card path is immune (it always passes for
- **A5-FURNIS-4** `mapping/mapping_services.py:2162` · both _(finder said MEDIUM; verifier corrected)_  
  area_label_anchors are keyed by device room id and nothing prunes them on a room rebuild, so a re-import silently re-aims one room's dragged label onto a different room  
  This is the direct answer to 'does the edit survive a re-import?': the bytes survive, their meaning does not, and nothing detects it. Cosmetic in consequence (a mis-placed m² chip, not a mis-cleaned room) but silently wr
- **A2-POLYGO-6** `mapping/segment_primitives.py:342` · Neither at runtime (Eufy CV thresholds are empirically tuned); affects future adapter authors, which is exactly this module's advertised audience  
  `compactness` docstring claims 'Range 0-1; 1 = circle' - the attainable maximum is pi/4 and a circle scores LOWER than a square  
  No runtime defect - segmentor.py's thresholds (e.g. `compactness < 0.08` for `fragmented_candidate`) were tuned empirically against the actual function. The harm is to the stated purpose of this module: its header calls
- **A2-POLYGO-7** `mapping/segment_primitives.py:526` · Neither at runtime (Eufy CV only, thresholds empirically tuned); affects future adapter authors  
  `normalized_color_features`' luminance normalisation provably cancels out - the Rec.709 weights are dead arithmetic and tuning them changes nothing  
  No behavioural defect - the output is correct chromaticity and segmentor.py's hue clustering is tuned against it. The trap is for maintenance: the docstring says 'illumination-normalized chromaticity features' and the co
- **MAP-GHOST-1** `maps/map_manager.py:145` · eufy  
  Empty map buckets accumulate one per firmware re-map and surface in the card  
  Found on live storage 2026-08-05: alfred carries maps 7, 11 and 12 where only 12 is real. Eufy firmware only rolls the active map id FORWARD, so 7 and 11 cannot return. They are not delete residue -- remove_map does `del
- **EP-4** `number.py:7` · both · `direct read`  
  Module comment asserts 'no polling'; the one class that polls is the one relying on it  
  The comment `# All number entities write directly to manager storage; no polling.` sits above PARALLEL_UPDATES = 0. Verified as a claim: NumberEntity, unlike ButtonEntity, does NOT set _attr_should_poll = False, and Eufy
- **EP-7** `room_entities.py:87` · both · `direct read`  
  _async_update_room silently drops non-managed keys from a mixed update  
  Branch 2 filters `updates` to a hand-maintained managed_field_names set and, if ANY managed key is present, routes only that subset to update_room_fields and RETURNS -- so every non-managed key in the same call is discar
- **A6-AGX-3** `rooms/access_graph.py:559` · both _(finder said MEDIUM; verifier corrected)_  
  get_room_access_editor marks every unselected target unselectable when the graph is already broken elsewhere, with the contentless reason "Not selectable due to graph legality."  
  A consumer of the documented editor service sees every link greyed out with a message that explains nothing and blames the edge being offered rather than the pre-existing violation. The user cannot tell what to fix; the
- **A6-AGX-5** `rooms/access_graph.py:613` · both _(finder said MEDIUM; verifier corrected)_  
  The per-room editor's issue list drops graph-scoped issues, so it reports a room as problem-free on a map whose graph is invalid and blocking runs  
  The per-room diagnostic reports a clean bill of health for a room on a map where cleaning is blocked, and never surfaces the one issue ("no dock room") that is causing it. The user auditing rooms one at a time will find
- **SN-9** `sensor/map_overlays.py:76` · both · `direct read`  
  native_value returns the literal string 'unavailable', colliding with HA's reserved state  
  VERIFIED AT SOURCE: `if not res.get('present'): return 'unavailable'`. That is indistinguishable in hass.states, templates, is_state() and the frontend from an entity that is genuinely unavailable, while the real diagnos

</details>

### Applied

**466 findings** closed by a landed packet. Not open work, but kept
here rather than removed — a disappeared finding is indistinguishable from one never
found. `.claude/notes/_landed_packets.json` is the source of truth for what has
landed; see `_gen_packet_closure.py` for how a packet resolves to the ids below.

- [x] **A3-SNAP-3** `core/manager.py:3844` · both — **RP-001** (`3ddcc1c`, 2026-07-31)  
  The snapshot has no read of the exactly-once finalize claim, so across the finalize await it reports a finished run as actively cleaning and offers Pause / Cancel on it
- [x] **A5-STR-5** `jobs/active_job.py:2464` · both — **RP-001** (`3ddcc1c`, 2026-07-31)  
  async_finalize_stranded_job reports success regardless of the finalizer's answer — a refused finalize still marks the slot 'completed' and fires a bogus EVENT_JOB_FINISHED
- [x] **HW-FINAL-1** `learning/manager.py:737` · both — **RP-001** (`3ddcc1c`, 2026-07-31)  
  The exactly-once finalize claim releases BEFORE the permanent gate is written, and an await sits in the gap - the finalize body runs twice
- [x] **A5-SVC-2** `learning/services.py:409` · both — **RP-001** (`3ddcc1c`, 2026-07-31)  
  finalize_learning_job fires eufy_vacuum_job_finished with a FABRICATED status "completed" when the finalize was rejected, and (no supports_response) tells the caller nothing
- [x] **A2-LIFE-1** `listeners/lifecycle.py:354` · both — **RP-001** (`3ddcc1c`, 2026-07-31)  
  The exactly-once claim's REFUSAL dict is consumed as a successful finalize — the duplicate EVENT_JOB_FINISHED survived the fix and now carries an all-null payload
- [x] **A1-UP-1** `__init__.py:420` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Panels registered outside async_setup_entry are never tracked, so unload can't remove them and setup silently re-adds the "no vacuum configured" fallback panel
- [x] **A1-UP-2** `__init__.py:316` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  async_setup_entry has no failure unwind, and HA never calls async_unload_entry for an entry that failed setup — a mid-setup raise orphans every subsystem registered so far and the next reload builds a second live copy
- [x] **A2-DOWN-1** `__init__.py:420` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Panels registered outside async_setup_entry are never tracked, so unload cannot remove them — and setup then re-adds the "no vacuum configured" fallback panel next to the working one
- [x] **A4-RELOAD-1** `__init__.py:420` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Panels registered outside async_setup_entry are never tracked, so unload never removes them
- [x] **A4-RELOAD-3** `__init__.py:499` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Unload stops the debug capture but never cancels its auto-stop timer, which then kills a later capture
- [x] **A1-INIT-1** `core/manager.py:473` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  async_initialize spawns loop-lifetime work with no teardown — after a config-entry reload the PREVIOUS manager writes its stale self.data over the live store
- [x] **A6-VAC-4** `core/manager.py:1035` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  remove_vacuum_record drops data["room_history"][vacuum] but leaves the _room_history_cache_ready marker — three sibling call sites invalidate it, the one that DELETES the data does not
- [x] **A2-DOWN-3** `core/water_amendment.py:246` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Post-job water-amendment listener + 180s timer, and two hass.data[DOMAIN] cache keys, are created outside setup and never removed by unload
- [x] **A4-RELOAD-4** `core/water_amendment.py:246` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Post-job water-amendment state listener and 180s timeout are never cancelled by unload
- [x] **A1-WIRE-5** `debug_capture.py:510` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  The debug-capture auto-stop timer is not cancelled on unload, so an orphaned timer from before a reload kills a capture started after it
- [x] **DR-DBG-3** `debug_capture.py:483` · n/a (drop-in helper) — **RP-003** (`76d92fc`, 2026-07-31)  
  Reload orphans a pending auto-stop timer
- [x] **A1-UP-3** `learning/services.py:901` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Five learning services registered during setup are missing from async_unregister_learning_services, so they survive unload as ghost services
- [x] **A2-DOWN-2** `learning/services.py:901` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  async_unregister_learning_services removes 16 of the 21 services async_register_learning_services registers — 5 survive unload and 3 raise a bare KeyError when called
- [x] **A4-RELOAD-2** `learning/services.py:901` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Five learning services are registered on setup but missing from the unregister list, so they survive unload and entry removal
- [x] **A5-SVC-7** `learning/services.py:901` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Five registered services are never unregistered, surviving integration unload as phantom entries that fail with an unhandled KeyError
- [x] **A1-REG-3** `listeners/discovery.py:96` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Per-vacuum teardown never re-registers listeners, and the documented 'a subscription to a now-deleted entity is inert' invariant is false — discovery keeps running passes for the deleted vacuum and re-creates its setup_progress bucket
- [x] **A6-GUARD-6** `listeners/discovery.py:133` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  Discovery triggers survive per-vacuum deletion and re-create a setup_progress record for the deleted vacuum — the "subscription to a deleted entity is inert" comment is false
- [x] **A1-REG-2** `listeners/lifecycle.py:390` · eufy — **RP-003** (`76d92fc`, 2026-07-31)  
  lifecycle registers a state listener + timer (post-job water amendment) whose unsubs are function-local and unreachable from lifecycle.remove()/async_unload_entry — the only unsub leak among the eight modules
- [x] **A2-LIFE-2** `listeners/lifecycle.py:409` · both — **RP-003** (`76d92fc`, 2026-07-31)  
  _process tasks are untracked — remove() drops only the subscription, so a config-entry reload orphans an in-flight finalize bound to the dead manager
- [x] **DR-DBG-1** `debug_capture.py:173` · n/a (drop-in helper) — **RP-004** (`27824be`, 2026-07-31)  
  exc_info tracebacks are stored UNREDACTED and UNTRUNCATED — both published claims hold only for the message field
- [x] **DR-DBG-2** `debug_capture.py:605` · n/a (drop-in helper) — **RP-004** (`27824be`, 2026-07-31)  
  The switch bypasses the auto-stop bookkeeping the services maintain — forgotten override sibling at the entry-point layer
- [x] **DR-DBG-4** `debug_capture.py:374` · n/a (drop-in helper) — **RP-004** (`27824be`, 2026-07-31)  
  An unrecognised `areas` value silently produces a capture that records nothing
- [x] **DR-DBG-6** `debug_capture.py:286` · n/a (drop-in helper) — **RP-004** (`27824be`, 2026-07-31)  
  status() reports stale started_at / services / areas after a stop
- [x] **DR-DBG-7** `debug_capture.py:457` · n/a (drop-in helper) — **RP-004** (`27824be`, 2026-07-31)  
  Two dumps in the same second overwrite each other
- [x] **DR-DIAG-1** `diagnostics.py:570` · both — **RP-004** (`27824be`, 2026-07-31)  
  "Everything in _vacuum_diagnostics is read-only" is false — refresh=False does not make the capability call inert
- [x] **DR-DIAG-2** `diagnostics.py:326` · both — **RP-004** (`27824be`, 2026-07-31)  
  Nine repr(err) sinks bypass the key-based redaction the docstring promises unconditionally
- [x] **DR-DIAG-3** `diagnostics.py:286` · both — **RP-004** (`27824be`, 2026-07-31)  
  A failed health probe is silently absent from the warnings block designed to be read first
- [x] **DR-DIAG-4** `diagnostics.py:539` · both — **RP-004** (`27824be`, 2026-07-31)  
  entry.title is dumped unredacted while entry.data and entry.options are redacted
- [x] **HW-DIAG-1** `diagnostics.py:365` · both — **RP-004** (`27824be`, 2026-07-31)  
  The job-active warning asserts a run-time failure that is unreachable from the state triggering it — and computes presence from a stale snapshot
- [x] **DR-LR-1** `live_refresh/manager.py:170` · roborock — **RP-004** (`27824be`, 2026-07-31)  
  A misdeclared returns_response retries forever at DEBUG and never sticky-disables
- [x] **A5-FACADE-1** `core/manager.py:1434` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  save_managed_rooms facade wipes every stored room for a map when the discovery cache is empty — the precondition its sibling reconcile_room has
- [x] **A5-FACADE-2** `core/manager.py:1426` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  discover_rooms facade overwrites a good persisted discovery cache with an empty one whenever the room source is momentarily unreadable
- [x] **A5-FACADE-3** `core/manager.py:1450` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  rebuild_map facade has the same unguarded total-wipe as save_managed_rooms, with no in-repo caller to compensate
- [x] **A2-REC-4** `rooms/room_crud.py:173` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  migrate replaces the whole room map from one discovery snapshot — any room missing from that snapshot is permanently deleted, guarded only by 'the list wasn't empty'
- [x] **A3-CRUD-1** `rooms/room_crud.py:261` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  save_managed_rooms unconditionally replaces map_bucket["rooms"] — an empty selection or an empty discovery cache silently destroys every stored room on the map
- [x] **A3-ROOMS-1** `services/rooms.py:160` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  save_managed_rooms silently wipes a map's entire saved room configuration when the discovery cache for that map is empty
- [x] **A3-ROOMS-2** `services/rooms.py:83` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  enabled_room_ids: null coerces to [] and wipes every managed room — the exact opposite of omitting the key
- [x] **A4-SETUP-1** `services/setup.py:213` · both — **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  setup_save_rooms rebuilds the map from the stale/absent `data["discovery"]` cache and REPLACES the map's rooms wholesale — returns {"status": "success"}
- [x] **A1-INIT-2** `core/manager.py:2275` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  Room-history preload overwrites the persisted cache with {} whenever the rebuild throws, and marks the cache ready so it never retries
- [x] **A2-CB-2** `core/manager.py:2275` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  async_preload_room_history_cache replaces the whole per-vacuum room_history subtree AFTER an executor await, silently discarding any room-history written during that await
- [x] **A2-ACC-1** `learning/estimator.py:589` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  A single transient read failure makes record_estimate_accuracy silently overwrite the entire accuracy history with one job's rooms
- [x] **A3-IO-2** `learning/history_store.py:176` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  read_json turns a corrupt or unreadable file into None, and the trouble-rooms read-modify-write then overwrites the file with a one-job store — permanently destroying history that has no rebuilder by design
- [x] **A3-IO-3** `learning/history_store.py:536` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  A failed or absent read is cached as None for the life of the process, and load_*_stats has no bypass — so _reload_learning_stats_now's documented "guarantees the current on-disk stats" is false
- [x] **A4-STATE-8** `learning/history_store.py:327` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  The live snapshot has no clear: last_job_snapshot.json and _live_snapshot_cache are never invalidated after a run, and the stale snapshot's job_id outranks the active job's — a failed snapshot save makes the next finalize overwrite the previous job's record
- [x] **A5-SVC-6** `learning/services.py:447` · both — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  rebuild_learning_stats blanks accuracy_stats before replaying it; any failure after the blank leaves the store empty and the service reports nothing at all
- [x] **A3-IMAGE--2** `mapping/mapping_services.py:1174` · Both. Eufy via engine_exception / missing optional CV libs; Roborock and any adapter without a registered segmenter engine hits it on the very first analyze call via noop_fallback. — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  A failed or unavailable segmenter run overwrites the good cached segmentation with an empty available:False envelope and persists it
- [x] **A3-IMAGE--3** `mapping/mapping_services.py:1100` · Both. — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  The analyze cache-hit gate tests truthiness, so a cached FAILURE envelope is served as a valid cache forever
- [x] **A4-SRC-2** `rooms/source_refresh.py:280` · roborock — **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  set_cached_room_source is called unconditionally on every successful service call, so a response the flatten shim does not recognise (or an empty maps list) silently REPLACES a good cache with {} — logged at DEBUG only
- [x] **DQ-DE-1** `dispatch/manager.py:317` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  Strict-order per-room phases invert the live-id safety rule: an unresolvable slug dispatches the STALE stored segment id instead of being skipped
- [x] **DQ-ACT-1** `dispatch/manager.py:317` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  When NO target slug resolves live, dispatch falls back to the STALE stored ids — the exact wrong-room outcome the function exists to prevent
- [x] **DQ-ACT-5** `dispatch/manager.py:442` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  The mixed-batch water SAFETY pre-call is best-effort — if it fails the clean still dispatches and the robot wet-mops the vacuum-only rooms
- [x] **A4-SRC-1** `rooms/source_refresh.py:217` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  async_refresh_room_source returns None on success AND on every failure/skip path, and the cache carries no freshness stamp — dispatch cannot tell a fresh live snapshot from an arbitrarily old one, and rewrites the wire payload with stale segment ids while believing it re-resolved live
- [x] **A4-SRC-3** `rooms/source_refresh.py:205` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  flatten_maps_response keys the cache by map NAME with last-writer-wins and no collision detection; a collapsed cache chains into room_discovery's single-map fallback and serves one map's segment ids for a different map_id
- [x] **A4-SRC-4** `rooms/source_refresh.py:274` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  No in-flight coalescing or lock on the refresh: triggers spawn unbounded concurrent get_maps cloud calls, and an older response landing last becomes the resident cached snapshot — including one that started before a map switch and lands after it
- [x] **A4-SRC-5** `rooms/source_refresh.py:80` · roborock — **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  The room-source cache is never invalidated — not on config-entry unload/reload, not on map switch, not when a vacuum is unmanaged — and it keeps hass.data[DOMAIN] alive so the unload cleanup never fires
- [x] **A3-SNAP-1** `core/manager.py:3948` · roborock — **RP-008** (`8d244dc`, 2026-08-01)  
  mop_active collapses "tank sensor unreadable" into a definite False, so the card confidently reports "Vacuuming" and hides the water-level control on Roborock
- [x] **INF-4** `entity_helpers.py:14` · both — **RP-008** (`8d244dc`, 2026-08-01)  
  The BLANK_STATE_VALUES docstring asserts a consolidation that is roughly 20% applied
- [x] **A6-PRE-1** `jobs/job_monitor.py:217` · both — **RP-008** (`8d244dc`, 2026-08-01)  
  The vacuum-state busy branch is unreachable for every HA-standard vacuum state — an errored or externally-cleaning robot classifies as "ready" and Start dispatches at it
- [x] **A3-COMMON-1** `listeners/_common.py:138` · roborock — **RP-008** (`8d244dc`, 2026-08-01)  
  is_job_active() treats a NOT-YET-ADDED / removed job_active entity as "no job running", defeating the Roborock mid-recharge completion guard
- [x] **A3-COMMON-3** `listeners/_common.py:166` · future_brand_only — **RP-008** (`8d244dc`, 2026-08-01)  
  completed_finalize_signals() docstring claims it returns "" for unavailable entities; it actually returns the literal "unavailable"/"unknown"
- [x] **A6-GUARD-1** `listeners/path_blockers.py:116` · both — **RP-008** (`8d244dc`, 2026-08-01)  
  A blocker sensor going `unavailable` satisfies every negating rule operator, so a Zigbee/cloud dropout pauses or CANCELS a live run (return_to_base)
- [x] **A4-POSE-3** `listeners/pose_sampler.py:129` · roborock — **RP-008** (`8d244dc`, 2026-08-01)  
  _is_parked has no working fallback on the native_current_room path — when task_status is unreadable it returns 'not parked', the opposite of what its own docstring claims
- [x] **DR-MNT-1** `maintenance/manager.py:713` · both — **RP-008** (`8d244dc`, 2026-08-01)  
  source_available reports True for a MISSING usage_hours attribute, and reset_maintenance's invalid_usage_hours is unreachable for it
- [x] **SN-2** `sensor/maintenance.py:95` · both — **RP-008** (`8d244dc`, 2026-08-01)  
  The maintenance sensor's documented availability guard never fires; it publishes a fabricated full-life value
- [x] **INF-5** `entity_helpers.py:57` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  The unique-id scheme is a non-injective flat join with no parser, and its vacuum-key half is open-coded at four sites
- [x] **EP-2** `number.py:101` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  number.py's prefix sweep also destroys NON-room maintenance entities that its callback can never rebuild
- [x] **DR-SENS-2** `sensor/__init__.py:250` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  Two ~40-line dynamic-entity reconciliation blocks are hand-duplicated and must be edited in lockstep
- [x] **SN-3** `sensor/__init__.py:255` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  Two of the four sensor prefix sites are destructive - a room sync on one vacuum deletes a sibling's registry entries
- [x] **SN-7** `sensor/__init__.py:62` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  The stated thread-safety invariant is internally inconsistent, and copies 3 and 4 have already dropped it
- [x] **DR-SETUP-1** `setup/delete.py:136` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  Deleting map N from vacuum.X sweeps every entity of vacuum.X_N from the registry
- [x] **A2-CB-1** `switch.py:71` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  Room-update fan-out identifies "stale" entities by unique_id PREFIX, so a room edit on one vacuum permanently deletes a sibling vacuum's entities from the entity registry
- [x] **A2-CB-5** `switch.py:89` · both — **RP-009** (`6ab1b20`, 2026-08-01)  
  Three of the four fan-out subscribers call async_write_ha_state() unguarded while the fourth routes through a hass-is-None guard, so one bad entity aborts the rest of that subscriber's sync silently
- [x] **A2-CAN-3** `jobs/active_job.py:2205` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel OPENS the completion gate it is about to wait for — it clears _phase_dispatch_pending before return_to_base, and neither the gate nor maybe_advance_phase checks _cancel_in_flight
- [x] **A2-CAN-5** `jobs/active_job.py:2101` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Pause has NO in-flight flag at all — a dispatch already inside _dispatch_active_phase lands after vacuum.pause and the robot cleans while the record says 'paused'
- [x] **A2-CAN-6** `jobs/active_job.py:2189` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  async_cancel_active_job is re-entrant — a second cancel arriving inside the 30 s confirm window overwrites finalize_summary with all-None
- [x] **A4-AJ-3** `jobs/active_job.py:2205` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel clears `_phase_dispatch_pending` up front, so the return-to-base dock is read as phase completion and the job advances to the next phase during the 30 s cancel window
- [x] **DQ-ACT-2** `jobs/phase_runner.py:1025` · roborock — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel is defeated by the phase watchdog: _cancel_in_flight is checked once, before two multi-second awaits, then the clean is dispatched unconditionally
- [x] **A1-WD-1** `jobs/phase_runner.py:553` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel is defeated ACROSS _dispatch_active_phase's awaits — the watchdog re-sends a clean after return_to_base, then the run is finalized while the robot keeps cleaning
- [x] **A2-CAN-1** `jobs/phase_runner.py:553` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel is LOST across _dispatch_active_phase's awaits — the watchdog re-sends a clean AFTER return_to_base and the robot is left cleaning with no job record
- [x] **A2-JOB-2** `services/job_control.py:170` · both — **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  start_zone_clean is the only start service with zero preconditions — it dispatches to the robot mid-job and strands the tracked room job
- [x] **A2-CAN-4** `jobs/active_job.py:2155` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Pause+resume permanently kills the phase watchdog for room_group and zone phases — resume re-arms ONLY dock phases and never restores the dispatch guard
- [x] **A5-STR-1** `jobs/active_job.py:2378` · eufy — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Strand exclusion consults only task_status against a narrower vocabulary — an Eufy dock service cycle reaps a healthy mid-run job as `interrupted`
- [x] **A5-STR-2** `jobs/active_job.py:2447` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  async_finalize_stranded_job calls the finalizer unguarded — one raising finalize kills the entire reaper tick for every vacuum, every minute, forever
- [x] **A5-STR-4** `jobs/job_monitor.py:357` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  A dispatched run the device never started can never be reaped, then the NEXT run's completion signals finalize the stale slot with the wrong run's data
- [x] **DQ-ACT-3** `jobs/phase_runner.py:552` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  A raising dispatch kills the phase watchdog task and wedges the run in 'started' forever
- [x] **A1-WD-2** `jobs/phase_runner.py:530` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Every abnormal exit from the watchdog leaves _phase_dispatch_pending set, and that state is UN-REAPABLE BY DESIGN — the run wedges in 'started' forever and blocks all future starts
- [x] **A1-WD-3** `jobs/phase_runner.py:889` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  has_native gates on the DECLARED entity-id string (always truthy on both shipped brands), so the coarse fallback is dead code and Eufy verifies phases against a signal its own adapter declares unusable as a live current-room source
- [x] **A1-WD-4** `jobs/phase_runner.py:125` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  An HA restart during a room_group or zone phase's un-confirmed window strands the run — the re-arm covers ONLY dock phases and the comment's claimed recovery path cannot fire
- [x] **A1-WD-5** `jobs/phase_runner.py:891` · future_brand_only — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Adapter-declared phase_timing overrides are applied with no clamping — poll_seconds: 0 pins the event loop in a hot loop, max_attempts: 0 dispatches nothing and wedges the phase
- [x] **A5-STR-3** `jobs/phase_runner.py:572` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  _phase_dispatch_pending is a permanent strand exclusion — a watchdog that gives up wedges the run AND blinds the reaper that exists to recover it
- [x] **A6-GUARD-4** `listeners/pause_timeout.py:155` · both — **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  The 1-minute reap ticker has no in-flight guard while each reap blocks up to ~35s, so two reapable slots guarantee overlapping ticks and a duplicate cancel
- [x] **A4-AJ-1** `jobs/active_job.py:472` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  Mid-job recharge NEVER ends: the recharge-end branch is unreachable dead code, so recharge_seconds_accumulated is always 0 and every recharging run is silently held from learning
- [x] **A4-POSE-1** `listeners/pose_sampler.py:309` · roborock — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  Sampler cadence collapses to min() across all vacuums while the attribution engine multiplies tick counts by each vacuum's OWN declared interval_s — Roborock is sampled at 2.0s but its ticks are valued at 5.0s
- [x] **A4-POSE-2** `listeners/pose_sampler.py:315` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  The sampling timer is fire-and-forget: a tick slower than interval_s overlaps the next tick, double-recording samples and stamping stale pose content with a fresh timestamp
- [x] **A4-POSE-5** `listeners/pose_sampler.py:312` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  _handle_pose_tick has no per-vacuum exception guard, and only the live_pose read is wrapped — one vacuum raising drops every later vacuum from that tick
- [x] **A6-TRK-1** `mapping/tracker.py:320` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  end_job has only ONE caller (successful finalize) — every cancel/abort/strand path leaves the tracker permanently stuck on the finished job's map and rooms
- [x] **A6-TRK-2** `mapping/tracker.py:316` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  resume_sampling is provably unreachable — _sampling_paused is a one-way latch, so all room attribution stops permanently at the first mid-job recharge
- [x] **A6-TRK-3** `mapping/tracker.py:450` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  The HOLD path keeps ACCRUING dwell and movement for a room the robot has already left, inflating duration_seconds and forcing confidence to 1.0
- [x] **A6-TRK-4** `mapping/tracker.py:324` · both — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  The last room of every job never fires room_completed — end_job resets state without flushing the held room
- [x] **DQ-PH-6** `queue/queue_engine.py:466` · future_brand_only — **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  advance_active_job_phase resets every per-phase pointer except _native_current_room_id, leaving a latent cross-phase carry-over that only the phases-gate currently hides
- [x] **DQ-PH-1** `learning/history_store.py:996` · both — **RP-013a** (`205ef7b`, 2026-08-02)  
  Every break/zone phase flips transit_capture_valid to False, so a stepped run's per-room learning silently degrades to an even split of the run's wall time — charge/wait dock time included
- [x] **A3-IO-1** `learning/history_store.py:989` · both — **RP-013a** (`205ef7b`, 2026-08-02)  
  An empty room_timing on a charge/wait/zone phase is read as "capture failed", so every stepped run with a break or a zone is stripped of its accurate per-room timings and learns an even split instead
- [x] **INF-8** `planning/run_plan.py:883` · both — **RP-013a** (`205ef7b`, 2026-08-02)  
  The one call site step_types' docstring reasons about by name hand-copies the tuple instead of importing it
- [x] **DQ-PH-3** `jobs/phase_runner.py:301` · eufy — **RP-013b** (`f212c20`, 2026-08-02)  
  A multi-room room_group phase is recorded as ONE room — the group's whole cleaning time, area and battery are attributed to its first room and every other room in the group vanishes from the record
- [x] **A3-REC-1** `jobs/phase_runner.py:301` · eufy — **RP-013b** (`f212c20`, 2026-08-02)  
  A multi-room room_group phase records ONLY queue_room_ids[0] — the group's whole time/area lands on one room, the other N-1 rooms produce no timing at all, and the run is still flagged high-confidence
- [x] **A3-REC-2** `jobs/phase_runner.py:297` · eufy — **RP-013b** (`f212c20`, 2026-08-02)  
  Phase 0's timing is attributed to the whole-run queue's first room, which need not be a room of phase 0 at all
- [x] **A2-CAN-2** `jobs/active_job.py:2255` · both — **RP-013c** (`0ff4a8a`, 2026-08-02)  
  Cancelling a sequenced run reports the WRONG missed rooms — per-phase reset of queue_room_ids/completed_room_ids feeds the incomplete-run log and trouble-rooms counters
- [x] **A3-REC-3** `jobs/active_job.py:937` · eufy — **RP-013c** (`0ff4a8a`, 2026-08-02)  
  A phased job never records a completed room, so live progress freezes on the group's first room and the stall detector fires a false 'stuck' event mid-run
- [x] **A4-STATE-2** `learning/history_store.py:273` · both — **RP-013c** (`0ff4a8a`, 2026-08-02)  
  clear_incomplete_run's docstring claim "(full clean)" is false — ANY completed run erases the missed-room record, and it is unrecoverable because completed_room_ids is never persisted in the job archive
- [x] **A4-STATE-1** `learning/services.py:689` · both — **RP-013c** (`0ff4a8a`, 2026-08-02)  
  The final room of EVERY non-completed run is recorded as "missed"; on a stranded run the documented retry automation re-dispatches the robot in an unbounded loop
- [x] **DQ-PH-2** `queue/queue_engine.py:467` · both — **RP-013c** (`0ff4a8a`, 2026-08-02)  
  advance_active_job_phase resets completed_room_ids/completed_rooms and no code path ever refills them for a phased job, so an abnormally-ended sequenced run reports every room as missed
- [x] **A4-STATE-6** `learning/history_store.py:1092` · both — **RP-013d** (`8f4c5a8`, 2026-08-02)  
  build_completed_job_payload's `queue` block prefers the LIVE queue over the job's own — a room switch flipped mid-run makes both the missed-rooms banner and trouble_rooms name a room that was never in the run
- [x] **A3-REC-4** `jobs/active_job.py:1709` · both — **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  Both sample recorders still use the `started_at and not ended_at` predicate the module itself documents as permanently true after finalize, and fan the write out to every map bucket
- [x] **A3-REC-5** `jobs/active_job.py:1721` · both — **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  Every counter sample carries battery=None — last_battery_percent is read but never written by anything, so per-room battery attribution is dead on both recording paths
- [x] **A4-AJ-2** `jobs/active_job.py:1676` · both — **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  The two sample recorders still use the repudiated `started_at and not ended_at` predicate and write into EVERY map bucket, so a finished or stranded job silently absorbs another run's counters
- [x] **A5-METRICS-2** `listeners/job_metrics.py:172` · both — **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  `last_battery_percent` has no writer anywhere in production, so every counter sample carries battery=None and per-room `battery_delta` is permanently null on both dispatch paths
- [x] **A6-VAC-1** `dock/manager.py:154` · eufy — **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  Dock-action gate is blind to app-started (external) runs — every dock action reports "Ready" and fires while the robot is mid-run at the dock
- [x] **A3-COMMON-4** `listeners/_common.py:178` · both — **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  _common owns the completion QUESTION but not its vocabulary defaults — the clear-sentinel and completion-status fallbacks exist as two hand-copied literals in different modules
- [x] **A3-COMMON-6** `listeners/_common.py:110` · both — **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  The listener layer never uses either canonical in-flight predicate — it hand-inlines the status set that dispatched_job_is_in_flight declares itself "THE single answer" to
- [x] **A5-METRICS-1** `listeners/job_progress.py:74` · roborock — **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  job_progress ticker gates on a hand-copied {"started","paused"} literal, so app-started (external) runs never get the Lever B live current-room refresh or a progress tick
- [x] **DR-SENS-1** `sensor/lifecycle.py:203` · both — **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  The active_job sensor reports 'none' during an app-started run the system itself considers in flight
- [x] **A6-TRK-5** `mapping/tracker.py:47` · both — **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  _norm_room_name normalises differently from slugify_room_name — it merges room identities that rooms/ keeps distinct, and lacks the NFC canonicalisation slugify was given specifically to prevent this
- [x] **A2-REC-2** `rooms/reconciliation.py:84` · both — **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  Two rooms with the same name collapse into one identity: phantom id_changed on an unchanged map, and migrate overwrites one room's settings with the other's
- [x] **A1-ID-1** `rooms/room_discovery.py:254` · both — **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  slugify_room_name has no uniqueness guarantee and nothing enforces one — two rooms can share a slug, and on Roborock the second one dispatches to the FIRST one's segment id
- [x] **A1-ID-3** `rooms/room_discovery.py:247` · both — **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  A room name that slugifies to empty passes discovery's only validation and is then silently deleted by plan_migration and silently un-cleanable by dispatch
- [x] **A3-IO-6** `learning/history_store.py:138` · both — **RP-016** (`2feb9e0`, 2026-08-02)  
  get_paths derives the archive directory from the entity_id's object_id, so renaming the vacuum entity silently orphans all learned history and the predictor restarts from cold with no notice
- [x] **A3-IMAGE--6** `mapping/mapping_services.py:1014` · Both. — **RP-016** (`2feb9e0`, 2026-08-02)  
  delete_map_image calls itself the mirror of upload but has no layout_id/art_scope sibling and sweeps no back-references
- [x] **A4-CUSTOM-5** `mapping/mapping_services.py:1379` · Both — saved zones and queue zone steps exist for Eufy and Roborock alike. — **RP-016** (`2feb9e0`, 2026-08-02)  
  _generate_saved_zone_id / _generate_custom_layout_id guarantee uniqueness only against LIVE ids, so an id is reused after a delete — and saved-zone ids are durably referenced by queue steps and run profiles
- [x] **A6-ZONE-C-2** `mapping/mapping_services.py:2552` · Both — the zone step and its resolver are brand-agnostic. — **RP-016** (`2feb9e0`, 2026-08-02)  
  delete_saved_zone performs no reference check; run-profile and queue `zone` steps keep the dead id and are silently dropped at run time while the UI still lists them
- [x] **A6-ZONE-C-5** `mapping/mapping_services.py:2346` · Both. — **RP-016** (`2feb9e0`, 2026-08-02)  
  create_custom_layout force-flips segmentation_mode to "custom" with no record of the prior mode; delete only restores "cv" when zero layouts remain, so create-then-delete strands the user on a layout they never chose
- [x] **A3-PP-CRUD-3** `profiles/manager.py:587` · both — **RP-016** (`2feb9e0`, 2026-08-02)  
  rename_room_profile changes the store key and silently orphans every room referencing it — no migration, no reference check, no warning
- [x] **A3-CRUD-4** `rooms/room_crud.py:336` · both — **RP-016** (`2feb9e0`, 2026-08-02)  
  remove_map leaves the map's saved run-profile library, queue state and onboarding state behind; re-importing the same map_id resurrects run profiles holding room ids from the deleted segmentation
- [x] **A3-ROOMS-8** `services/room_profiles.py:97` · both — **RP-016** (`2feb9e0`, 2026-08-02)  
  delete_room_profile / rename_room_profile leave dangling profile_name references on rooms, which then silently resolve to a built-in preset
- [x] **DQ-Q-5** `maps/map_manager.py:197` · both — **RP-018** (`5af0fa2`, 2026-08-02)  
  A map rebuild silently auto-enables AND auto-approves rooms that never existed before, adding them to the clean queue unseen
- [x] **A3-CRUD-6** `maps/map_manager.py:181` · both — **RP-018** (`5af0fa2`, 2026-08-02); the `save_managed_rooms` half closed 2026-08-24 (R14/C60)  
  Both room writers auto-enable and auto-approve rooms the user has never seen (DQ-Q-5 extension: the live instance is save_managed_rooms, not rebuild_map)  
  ⚠ **THIS ROW WAS CHECKED OFF WITH ITS OWN NAMED LIVE INSTANCE STILL OPEN, FOR 22 DAYS.** RP-018 landed the auto-ENABLE half in both writers, and the auto-APPROVE half in `rebuild_map_bucket` and — in `build_managed_rooms` — only on the branch that receives `enabled_room_ids` (CRUD-3). The `None` branch, on the writer this row explicitly calls *"the live instance"*, was never touched until 2026-08-24. A closed row is exactly what stops anyone re-checking, which is why this note lives here and not only in the ledger.
- [x] **A3-CRUD-3** `rooms/room_crud.py:279` · both — **RP-018** (`5af0fa2`, 2026-08-02)  
  save_managed_rooms auto-confirms floor type for every room it writes, permanently satisfying the onboarding_required start gate with the guessed value "hardwood"
- [x] **A2-REC-8** `rooms/room_manager.py:64` · both — **RP-018** (`5af0fa2`, 2026-08-02)  
  The reachable room writer (save_managed_rooms/build_managed_rooms) carries settings by numeric id only, so a renumber stamps one room's floor type and access grants onto a different physical room
- [x] **A3-CRUD-2** `rooms/room_manager.py:64` · both — **RP-018** (`5af0fa2`, 2026-08-02)  
  build_managed_rooms matches stored rooms by numeric id while room identity is the slug — a re-save after a re-segment transplants the previous occupant's access grants, rules and dock flag onto a different physical room and erases the reconciliation evidence
- [x] **A3-CRUD-5** `rooms/room_manager.py:57` · both — **RP-018** (`5af0fa2`, 2026-08-02)  
  A re-save resurrects a room the user explicitly rejected as a phantom — build_managed_rooms never consults rejected_rooms
- [x] **A6-GUARD-5** `listeners/discovery.py:140` · both — **RP-019** (`0e0369f`, 2026-08-02)  
  A discovery pass on the active map is scored against configured rooms across ALL maps, so switching maps makes the other map's rooms accrue "removed" strikes
- [x] **A2-REC-3** `rooms/reconciliation.py:125` · roborock — **RP-019** (`0e0369f`, 2026-08-02)  
  A room renamed AND renumbered in the same edit is invisible to reconciliation — and migrate then deletes its stored data as if it were a stranger
- [x] **A2-REC-1** `rooms/room_crud.py:68` · both — **RP-019** (`0e0369f`, 2026-08-02)  
  Reconciliation never runs in production: no trigger, no schedule, no UI — the reviews are computed into a payload nothing reads
- [x] **A2-REC-5** `rooms/room_crud.py:162` · both — **RP-019** (`0e0369f`, 2026-08-02)  
  migrate applies a plan the user never saw: it never re-checks the reviews, and rebuilds the map even when there are none
- [x] **A2-REC-6** `rooms/room_crud.py:99` · both — **RP-019** (`0e0369f`, 2026-08-02)  
  Applying a 'renamed' review orphans that room's learned baselines, while the code comment claims history follows the room regardless
- [x] **A2-REC-7** `rooms/room_crud.py:118` · both — **RP-019** (`0e0369f`, 2026-08-02)  
  action='ignore' writes reconciliation_dismissed_at that no code ever reads — dismissed reviews resurface on every discovery
- [x] **A1-ID-2** `rooms/room_discovery.py:176` · roborock — **RP-019** (`0e0369f`, 2026-08-02)  
  discover_rooms_for_vacuum's single-map fallback serves ANOTHER map's room list and relabels it with the REQUESTED map_id, defeating the map_id filter at both room writers
- [x] **A1-ID-4** `setup/drift.py:540` · both — **RP-019** (`0e0369f`, 2026-08-02)  
  Drift keys its history by bare device room_id across ALL maps but feeds it only the ACTIVE map's discovery, so a multi-map vacuum's inactive rooms decay toward 'removed' and colliding ids mask each other
- [x] **A4-STATE-3** `learning/history_store.py:301` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  trouble_rooms.json is keyed by raw room_id and scoped per-vacuum, so its counters silently reattach to the wrong physical room after a re-segment or on a second map — the one id-keyed store reconcile-migrate forgets
- [x] **A4-STATE-4** `learning/history_store.py:247` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  incomplete_run.json's missed_room_ids survive a re-segment and a map switch, and the card applies them to whatever map is active — wiping the user's selection and enabling the wrong rooms
- [x] **A4-STATE-5** `learning/history_store.py:306` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  trouble_rooms is a raw-counter store with no rebuilder, no clear service and a denominator that only advances when the room is queued — the "decays on its own" justification for excluding it from repair does not hold
- [x] **A4-STATE-9** `learning/services.py:892` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  Dismissing the incomplete-run banner is client-only and no clear service is exposed, so the banner returns on every card load
- [x] **A5-SVC-1** `learning/services.py:555` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  exclude_learning_job / restore_learning_job report "stats rebuilt" but never rebuild the three incremental accumulators — the excluded run's poison stays in accuracy_stats, learned_zones and battery aggregates
- [x] **A5-SVC-5** `learning/services.py:492` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  record_estimate_accuracy writes accuracy_stats to disk but never invalidates the manager's in-memory accuracy cache, so estimates keep serving the pre-write numbers
- [x] **A5-SVC-8** `learning/services.py:450` · both — **RP-020** (`f48dee2`, 2026-08-02)  
  invalidate-then-preload is a no-op when a preload is already in flight, letting a stale in-flight load repopulate the cache with pre-rebuild data
- [x] **A4-START-1** `core/manager.py:2863` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  get_start_status validates PHASE 0's room count as if it were the whole job — a stepped run whose first phase is a zone is refused with a false "invalid payload" error
- [x] **A4-START-2** `core/manager.py:5021` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  start_selected_rooms dispatches phase 0 with no phase_type branch, unlike its phase_runner sibling — and _build_steps_phases' docstring claims a guard that does not exist
- [x] **A6-PRE-2** `jobs/job_monitor.py:268` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  invalid_payload uses phase 0's room count as the whole run's room count — a saved run profile whose first step is a zone is accepted on save but can never start
- [x] **DQ-Q-1** `planning/run_plan.py:902` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  Stepped run silently collapses to ONE atomic dispatch when every break phase is trimmed — per-group settings and group sequencing are discarded
- [x] **DQ-Q-3** `planning/run_plan.py:884` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  A run profile whose first step is a zone is permanently unstartable and reports "Room-clean payload is missing or invalid"
- [x] **A5-PP-RP-1** `planning/run_plan.py:1352` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  A multi-room_group plan with no charge/wait/zone is silently flattened to ONE atomic dispatch — the card routes it as sequenced
- [x] **A5-PP-RP-3** `planning/run_plan.py:1379` · roborock — **RP-021a** (`8f9d5db`, 2026-08-02)  
  _build_steps_phases can return an empty list; `phases[0]` then raises IndexError inside get_start_status, killing the whole dashboard snapshot (Roborock)
- [x] **A5-PP-RP-4** `planning/run_plan.py:902` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  The collapse fallback's `all_ids` is provably always [] — and the unit test manufactures the very key the real engines never emit
- [x] **A5-PP-RP-5** `planning/run_plan.py:884` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  A user-authored leading or trailing charge/wait step is silently deleted at dispatch while the card still shows it and stamps has_charge_steps
- [x] **A5-PP-RP-6** `planning/run_plan.py:1458` · roborock — **RP-021a** (`8f9d5db`, 2026-08-02)  
  A stepped Roborock run enforces clean order but still tells the user the order is advisory
- [x] **A6-PP-EST-LBL-1** `planning/run_plan.py:436` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  _room_surface_labels is fed a key that resolved_rooms never carries, so floor_type_label is always None at both display sites
- [x] **DQ-DE-2** `queue/dispatch_engines.py:110` · future_brand_only — **RP-021a** (`8f9d5db`, 2026-08-02)  
  _SinglePhaseMixin silently swallows strict_order and the seam cannot express refusal — while the caller hides the order advisory on the strength of the request alone
- [x] **DQ-DE-5** `queue/dispatch_engines.py:211` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  Engine phase envelopes omit queue_room_ids/queue_rooms, making the run-plan group-union computation dead code and emptying queue_rooms on every phase advance
- [x] **DQ-Q-7** `queue/queue_engine.py:242` · both — **RP-021a** (`8f9d5db`, 2026-08-02)  
  build_room_clean_payload treats an empty queue_room_ids as "no filter" rather than "no rooms", so a cleared queue yields a payload containing every enabled room
- [x] **A4-PP-RP-2** `profiles/manager.py:1086` · both — **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  overwrite_run_profile unconditionally destroys a saved profile's step sequence; save_run_profile preserves it — same "snapshot the current run" contract, opposite behaviour
- [x] **A4-PP-RP-1** `profiles/manager.py:1232` · both — **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  A stepped run profile silently discards the per-room settings it was saved with; apply falls back to whatever the rooms happen to be set to now
- [x] **A4-PP-RP-6** `profiles/manager.py:779` · both — **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  normalize_run_profile_steps passes arbitrary per-room fields through untouched, and the run-plan overlay treats them as authoritative settings — the one dispatch path that skips _protected_room_config
- [x] **A5-RUNPROF-4** `services/run_profiles.py:85` · both — **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  set_run_profile_steps accepts a bare `list` and silently drops or clamps every malformed step; only 'at least one room_group survived' is enforced
- [x] **A4-PP-RP-4** `profiles/manager.py:1244` · both — **RP-021c** (`176c73e`, 2026-08-04)  
  apply_run_profile leaves no backend record that the applied profile is stepped, so a plain Start runs it flat — or inherits the map's unrelated leftover breaks
- [x] **DQ-ZONE-5** `core/manager.py:4030` · both — **RP-022** (`1288b65`, 2026-08-02)  
  zone_bounds is computed and shipped in the dashboard snapshot but has no consumer anywhere — and the card replaces the precise refusal message with a generic toast
- [x] **A3-SNAP-4** `core/manager.py:4017` · future_brand_only — **RP-022** (`1288b65`, 2026-08-02)  
  zone_max invents Eufy's device limit (10) for any brand that declares none, while the dispatch gate enforces no cap at all when the key is absent
- [x] **DQ-PAY-4** `dispatch/manager.py:182` · eufy — **RP-022** (`1288b65`, 2026-08-02)  
  Zone-clean repeat cap defaults to 3 for Eufy while the framework's own room-clean cap for Eufy is 2, and the service schema has no upper bound
- [x] **DQ-ZONE-1** `dispatch/manager.py:234` · eufy — **RP-022** (`1288b65`, 2026-08-02)  
  Zone-clean pass count is never clamped on the Eufy branch — the clamp lives inside the device_mm branch Eufy never enters
- [x] **DQ-ZONE-2** `dispatch/manager.py:120` · both — **RP-022** (`1288b65`, 2026-08-02)  
  supports_zone_clean is honored by the card but never consulted by the actuation path
- [x] **DQ-ZONE-3** `dispatch/manager.py:203` · future_brand_only — **RP-022** (`1288b65`, 2026-08-02)  
  Per-zone SIZE bounds are enforced by coordinate-space branch, not by which bound the adapter declared — the other combination is silently ignored
- [x] **DQ-ZONE-4** `dispatch/manager.py:216` · eufy — **RP-022** (`1288b65`, 2026-08-02)  
  Eufy per-side bound check is skipped entirely when live-map dims are unreadable, while the mm branch REFUSES on the same missing input
- [x] **A1-SERVIC-3** `mapping/mapping_services.py:493` · Eufy (unclamped). Roborock is protected by the device_mm-branch clamp. — **RP-022** (`1288b65`, 2026-08-02)  
  `clean_times` has no upper bound, defended by a sibling comment claiming dispatch enforces the per-brand ceiling — dispatch clamps it only on the Roborock (`zone_coords: device_mm`) branch; the Eufy branch ships it verbatim
- [x] **A6-ZONE-C-8** `mapping/mapping_services.py:2482` · Both (Eufy 0.5-10 m per side, Roborock 1 ft²-3.05 m²), per the caps quoted in the _handle_clean_saved_zones docstring at 2641-2642. — **RP-022** (`1288b65`, 2026-08-02)  
  Zone size limits are not enforced at author time, contradicting the doc — an un-cleanable zone can be saved and only fails when the user taps clean
- [x] **A2-JOB-4** `services/job_control.py:130` · eufy — **RP-022** (`1288b65`, 2026-08-02)  
  start_zone_clean clean_times has no upper bound; the schema comment claims a dispatch-side per-brand ceiling that exists only on the Roborock branch
- [x] **A6-PP-EST-BLK-1** `planning/run_plan.py:1615` · both — **RP-023a** (`d76d110`, `333c3db`, 2026-08-03)  
  Mid-job path-block report walks reachability over the QUEUE only, so any queued room whose access parent is not in the queue is reported blocked — and can cancel the job
- [x] **A5-AG-1** `planning/run_plan.py:1615` · both — **RP-023a** (`d76d110`, `333c3db`, 2026-08-03)  
  Mid-run reachability is queue-scoped while preflight is graph-scoped — a run that omits the dock room reports EVERY remaining room as access_blocked and can cancel the job
- [x] **A5-FACADE-4** `core/manager.py:1239` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  save_user_room_profile facade silently overwrites the existing 'user_1' profile when profile_name is omitted, while its sibling mints a unique id
- [x] **A6-PP-EST-DSP-1** `planning/run_plan.py:125` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  A room stamped profile_name="custom" is re-labelled as the brand's DEFAULT preset ("Vacuum Quick") with is_custom_profile=False — proven for any mop room on hardwood
- [x] **A6-PP-EST-DSP-2** `planning/run_plan.py:125` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  _settings_profile_display's "selected != resolved" custom-detection arm is dead for every name the resolver can rewrite — a carpet-downgraded mop room is still labelled "Vacuum + Mop Quick"
- [x] **A3-PP-CRUD-2** `profiles/manager.py:157` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  Applying a mop room profile instantly rewrites the room's profile_name to "custom" — the profile the user just picked does not stay selected
- [x] **A3-PP-CRUD-5** `profiles/manager.py:322` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  save-a-room-as-a-profile is not a round trip: path_type is discarded and re-derived from clean_intensity
- [x] **A3-PP-CRUD-8** `profiles/manager.py:73` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  Generated profile ids are local-time second-resolution and saves have no exists check, so two saves in one second silently destroy the first
- [x] **A4-PP-RP-5** `profiles/manager.py:77` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  Run-profile ids are generated at one-second resolution and assigned without a collision check, so two saves in the same second silently overwrite each other
- [x] **A1-PP-RES-2** `profiles/room_profiles.py:435` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  water_level and carpet fan_speed use a DIFFERENT precedence than every sibling field (floor default OVERRIDES the profile), so applying a built-in mop profile immediately re-labels the room "custom"
- [x] **A1-PP-RES-3** `profiles/room_profiles.py:419` · eufy — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  path_type resolves to the literal string "None" for any room backfilled by the startup migration, and that string reaches the Eufy wire payload
- [x] **A1-PP-RES-4** `profiles/room_profiles.py:448` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  "granite" and "concrete" are user-selectable floor types with no entry in either brand's FLOOR_TYPE_WATER_DEFAULTS, so the mop-with-no-water correction corrects to empty string
- [x] **A1-PP-RES-7** `profiles/room_profiles.py:284` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  A room pointing at a deleted or renamed custom profile silently resolves to the default profile — the UI reports a profile the room is not running
- [x] **A6-PP-EST-H2O-1** `profiles/room_profiles.py:140` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  granite and concrete are user-selectable floor types but are absent from every floor_type_water_defaults table, so a mop room there resolves water_level "" and is estimated as if it were dry
- [x] **DQ-PAY-2** `queue/queue_engine.py:303` · both — **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  A mop room on a granite or concrete floor resolves water_level to the empty string and that empty string is written verbatim to the wire
- [x] **A1-INIT-5** `core/manager.py:429` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  The startup backfill and setup_progress migration hard-code Eufy vocabulary and structurally cannot consult the adapter
- [x] **A1-EST-7** `learning/estimator.py:238` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  _load_mop_wash_config hard-codes Eufy's wash-frequency bounds (15/20/25) in the brand-agnostic estimator while the adapter already declares wash_frequency_bounds
- [x] **A1-EST-8** `learning/estimator.py:829` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  is_mop raw-compares clean_mode against a hand-copied literal set while the very same function canonicalizes it for the stats lookup
- [x] **A2-LIFE-3** `listeners/lifecycle.py:169` · eufy — **RP-025** (`71cc479`, 2026-08-02)  
  The inline mop-wash detector diverges from the dedicated dock_events listener: hard-coded Eufy wash vocabulary as a fallback, and no same-state guard against attribute-only re-triggers
- [x] **A5-PP-RP-7** `planning/run_plan.py:125` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  _settings_profile_display hardcodes the Eufy-era built-in profile-name set and takes no vacuum_entity_id, so a brand with its own profile keys renders every room as "Custom"
- [x] **A5-PP-RP-8** `planning/run_plan.py:142` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  The water-off suppression in _settings_profile_display compares against the literal "off" instead of the brand's no-water value
- [x] **DQ-Q-2** `profiles/manager.py:148` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  _match_profile_from_fields is structurally brand-blind and rewrites every Roborock room's profile_name to "custom" on every start
- [x] **DQ-PAY-1** `profiles/manager.py:225` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  Applying a built-in room profile to a Roborock room writes EUFY vocabulary onto the room; the fresh room_defaults fix covers creation only
- [x] **DQ-PAY-6** `profiles/manager.py:108` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  _protected_room_config stamps the Eufy literal "Off" into every non-mop room's water_level regardless of brand, on the path into the payload builder
> **Closure caveat (recorded 2026-08-08).** Three findings below name `profiles/manager.py`
> and were all marked closed against `71cc479` — a commit that never touched that file. One
> (CRUD-1) was genuinely fixed elsewhere; two (CRUD-4, CRUD-7) were still live six days later
> and were rediscovered independently while removing the framework profile catalog. A `[x]`
> in this ledger records that someone believed a finding was addressed, not that the named
> commit demonstrably addressed it. Where a finding names a FILE, the closing commit should
> touch that file — a cheap check that would have caught both.

- [x] **A3-PP-CRUD-1** `profiles/manager.py:631` · roborock — **RP-025** (`71cc479`, 2026-08-02) → *fix landed in `0b9c375`, not the commit cited*  
  apply_room_profile writes Eufy vocabulary onto Roborock rooms — the catalog it resolves is inert
- [x] **A3-PP-CRUD-4** `profiles/manager.py:257` · roborock — **RP-025** (`71cc479`, 2026-08-02) → **REOPENED, actually fixed `ad8c074`, 2026-08-08**  
  get_effective_room_details resolves with no catalog — Eufy floor defaults override a Roborock carpet room, and "Quick" is injected where the brand has no intensity axis  
  *Closure was wrong: `71cc479` touched `room_profiles.py` and two test files, never `profiles/manager.py`. The call site still passed no catalog and was rediscovered independently six days later.*
- [x] **A3-PP-CRUD-6** `profiles/manager.py:47` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  Protected-profile-name set is frozen from the Eufy in-code catalog, so a brand's own built-ins are unprotected and can be shadowed by a user profile
- [x] **A3-PP-CRUD-7** `profiles/manager.py:104` · both — **RP-025** (`71cc479`, 2026-08-02) → **REOPENED, actually fixed `ad8c074`, 2026-08-08**  
  _protected_room_config is the only writer in the finalize pipeline and it stamps the Eufy literal "Off" onto every non-mop room, on both brands  
  *Closure was wrong, same cause as CRUD-4. This was the THIRD copy of one predicate: the literal was removed from `resolve_room_profile_for_room`, then later from `apply_capability_gate`, and this sibling was marked closed by association both times. A guard that EXISTS reads as
  complete; diff a predicate against its copies, because the shorter copy is the bug.*
- [x] **DQ-Q-4** `profiles/room_profiles.py:209` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  normalize_room_profile re-injects the Eufy literal "Quick" for clean_intensity, defeating Roborock's deliberate omission of the axis
- [x] **DQ-Q-6** `profiles/room_profiles.py:519` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  apply_capability_gate and _protected_room_config hardcode Eufy display literals for the framework's 'no water' / 'default path' concepts
- [x] **A1-PP-RES-5** `profiles/room_profiles.py:294` · both — **RP-025** (`71cc479`, 2026-08-02)  
  get_available_profile_names hardcodes the four Eufy built-in keys, so get_available_profiles silently drops every user-saved custom profile and would return {} for a brand with different catalog keys
- [x] **A1-PP-RES-6** `profiles/room_profiles.py:209` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  normalize_room_profile injects the Eufy literal "Quick" whenever the brand's normalize_defaults omits clean_intensity, and apply_room_profile_to_config PERSISTS it into Roborock room storage
- [x] **A1-PP-RES-8** `profiles/room_profiles.py:165` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  resolve_profile_catalog's `or` fallbacks mean a brand cannot declare an intentionally EMPTY block — it silently inherits Eufy's
- [x] **A1-PP-RES-9** `profiles/room_profiles.py:366` · both — **RP-025** (`71cc479`, 2026-08-02)  
  Dead branch in resolve_profile_name_for_constraints, and the carpet downgrade only knows the four framework built-in names
- [x] **A2-PP-CAP-1** `profiles/room_profiles.py:560` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  apply_room_profile_to_config's `catalog` brand-safety parameter is structurally unreachable on every production call — the guard exists, the test passes, and the code path can never take it
- [x] **A2-PP-CAP-2** `profiles/room_profiles.py:209` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  normalize_room_profile's third-level literals are the one fallback a brand CANNOT override — the more deliberately a brand omits an axis, the more certainly it gets the Eufy literal for it
- [x] **A2-PP-CAP-3** `profiles/room_profiles.py:496` · eufy — **RP-025** (`71cc479`, 2026-08-02)  
  clean_intensity has no capability flag and reaches the Eufy wire on devices whose capability detection just concluded the intensity axis is absent
- [x] **A2-PP-CAP-4** `profiles/room_profiles.py:294` · both — **RP-025** (`71cc479`, 2026-08-02)  
  get_available_profile_names hardcodes the four Eufy catalog KEYS and takes no catalog — get_available_profiles merges every user-created profile in and then filters all of them back out
- [x] **A2-PP-CAP-6** `profiles/room_profiles.py:509` · roborock — **RP-025** (`71cc479`, 2026-08-02)  
  apply_capability_gate hardcodes the Eufy literal "Off" in three places for the framework's own 'no water' concept
- [x] **A2-PP-CAP-7** `profiles/room_profiles.py:166` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  resolve_profile_catalog uses `or` for every key, so a brand that explicitly declares an EMPTY block silently gets Eufy's
- [x] **A6-PP-EST-TD-1** `profiles/room_profiles.py:14` · both — **RP-025** (`71cc479`, 2026-08-02)  
  TypedDict drift: ProfileRecord's "all always present" claim is false for the shipped Roborock catalog, and capability_gated is declared bool but written as a dict
- [x] **DQ-PAY-5** `queue/queue_engine.py:182` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  _write_room_field's value_map is fail-open: an unmapped canonical value is emitted raw, and the framework itself injects Eufy literals no adapter can declare a mapping for
- [x] **EP-8** `room_entities.py:217` · both — **RP-025** (`71cc479`, 2026-08-02)  
  Hand-copied room defaults, including two that disagree about the same missing key
- [x] **A6-DIAG-8** `services/dock.py:51` · future_brand_only — **RP-025** (`71cc479`, 2026-08-02)  
  Dock event-type vocabulary is hand-copied into three places, none derived from the adapter that declares it
- [x] **A3-ROOMS-6** `services/rooms.py:102` · both — **RP-025** (`71cc479`, 2026-08-02)  
  update_room_fields accepts any clean_mode string; a casing/spelling variant keeps water in storage and in the UI but silently drops it from the wire payload
- [x] **A3-ROOMS-9** `services/rooms.py:103` · both — **RP-025** (`71cc479`, 2026-08-02)  
  update_room_fields accepts any fan_speed string; on Roborock an unrecognised value leaves the device's previous suction in place with no error
- [x] **A1-LC-1** `mapping/map_source_coordinator.py:397` · eufy — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Eufy in-memory map/pose source has NO vacuum identity — a second Eufy robot is served the FIRST robot's map, rooms, pose and render raster
- [x] **A1-LC-3** `mapping/map_source_coordinator.py:261` · eufy — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  The storage-path mtime cache early-return omits the `map_id` check its sibling `_commit_result` performs, so map A's geometry is returned as map B's answer with `present: True`
- [x] **A1-LC-5** `mapping/map_source_coordinator.py:136` · both — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  `_commit_result` is blind last-writer-wins across the storage path's two executor awaits — a refresh started before a map switch can commit after a newer one
- [x] **A3-EXT-1** `mapping/map_source_runtime.py:839` · eufy — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Eufy in-memory map/pose source has NO device selection — every vacuum gets coordinators[0]'s map
- [x] **A3-EXT-2** `mapping/map_source_runtime.py:966` · eufy — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Content version hashes ONLY the room raster, but the cache it gates holds the grid geometry the fork mutates independently
- [x] **A4-RB-1** `mapping/map_source_runtime.py:373` · roborock — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Roborock MapData lookup never binds the found map to the requested map_id — a multi-map (multi-floor) device converts drawn zones in the wrong floor's coordinate frame
- [x] **A4-RB-2** `mapping/map_source_runtime.py:1005` · roborock — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  No device scoping anywhere in the Roborock candidate walk — on a two-vacuum Roborock account the card's rendered raster and the diagnostics drift report come from an arbitrary robot
- [x] **A4-RB-3** `mapping/map_source_runtime.py:743` · roborock — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  roborock_result_from_candidates hard-returns on the first duck-typed MapData match, so one false positive permanently blanks the Roborock map source — and the stale-hold masks it for six hours
- [x] **A4-RB-4** `mapping/map_source_runtime.py:511` · roborock — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  rooms_from_mapdata publishes the live segment number as the room's only identity and synthesizes the name, so after a Roborock re-map a tap on room A selects room B
- [x] **A4-RB-5** `mapping/map_source_runtime.py:427` · roborock — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  roborock_geometry_drift_from_candidates pairs a MapData and a MapContent found by two independent BFS walks with no check they are the same map, and reports present:True regardless of the verdict
- [x] **A4-RB-6** `mapping/map_source_runtime.py:760` · roborock — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  image_entity_object silently drops the only per-vacuum candidate root on any HA-internals change, while the presence gate still reports the map as present
- [x] **A7-ROBORO-3** `mapping/roborock_raw_map.py:163` · roborock (the identical raster-only version hash exists for eufy in map_source.eufy_version_of, out of scope here) — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  `version` hashes the raster ONLY, while the payload also ships room_names — a room rename cannot invalidate a fetched render payload
- [x] **SN-5** `sensor/map_overlays.py:50` · both — **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  The overlays sensor serves a cache entry without checking its map_id or its stale flag
- [x] **A1-LC-2** `mapping/map_source_coordinator.py:126` · both — **RP-027** (`382d3d5`, 2026-08-02)  
  Sticky last-known-good hold re-serves a frozen current_room/robot_anchor as `present: True`; the `stale` flag it sets has NO consumer, so a docked Roborock reports a phantom room for up to 6 hours
- [x] **A1-LC-4** `mapping/map_source_coordinator.py:266` · eufy — **RP-027** (`382d3d5`, 2026-08-02)  
  The same mtime early-return skips `_apply_inmem_pose_to_result`, freezing the robot/dock/current_room/path overlays for as long as the store file is unchanged
- [x] **A2-GEO-1** `mapping/map_source_coordinator.py:520` · eufy — **RP-027** (`382d3d5`, 2026-08-02)  
  Live-pose room lookup projects a MEMORY-frame robot pixel through STORAGE-frame geometry (no memory fallback, no store_version guard) — feeds room attribution at 2 s
- [x] **A5-POSE-1** `mapping/map_source_coordinator.py:489` · eufy — **RP-027** (`382d3d5`, 2026-08-02)  
  Live pose is normalized and room-looked-up against .storage geometry while the map it is drawn on is memory-PRIMARY — the one reader never repointed
- [x] **A5-POSE-2** `mapping/map_source_coordinator.py:127` · both — **RP-027** (`382d3d5`, 2026-08-02)  
  `stale` / `stale_since` / `stale_reason` are written by the hold path and read by nothing — the docstring's "the card dims/badges it" is false
- [x] **A5-POSE-3** `mapping/map_source_coordinator.py:491` · eufy — **RP-027** (`382d3d5`, 2026-08-02)  
  The pose-geometry .storage read skips the `store_version` guard that every other reader of the same file applies
- [x] **A5-POSE-4** `mapping/map_source_coordinator.py:528` · eufy — **RP-027** (`382d3d5`, 2026-08-02)  
  The live pose carries no freshness stamp, so a frozen `_robot_pixel` is reported as `present: True` forever — and the fork's own `_last_robot_render` timestamp is ignored
- [x] **A5-POSE-5** `mapping/map_source_coordinator.py:266` · eufy — **RP-027** (`382d3d5`, 2026-08-02)  
  `_refresh_storage_map_source`'s mtime early-return bypasses the live-pose override entirely, re-serving the frozen pose it exists to kill
- [x] **A1-SERVIC-1** `mapping/mapping_services.py:450` · Both, but the rename trigger is Roborock-specific (map_id = user-editable map NAME from the select entity state). Eufy's numeric map ids make the accidental rename case unlikely; the empty/sentinel map_id case affects both. — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  No mapping write service can tell "this map exists" from "this map does not" — every schema takes a free-form map_id and every handler mints the bucket, so an edit against a non-existent map is persisted to a phantom bucket and reported as saved
- [x] **A1-SERVIC-5** `mapping/mapping_services.py:563` · Both. — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  services.yaml documents map_id as optional ("Leave blank to use the current active map") on 8 mapping services whose schemas make it `vol.Required`; the integration's shared resolver `resolved_call_data` is used 59 times elsewhere and zero times in this file
- [x] **A3-IMAGE--5** `mapping/mapping_services.py:896` · Both; Roborock materially more exposed because get_active_map_id returns the user-authored map NAME verbatim. — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  Image filenames are built from an unsanitised free-form map_id, so one map's upload can silently overwrite another map's image
- [x] **A4-CUSTOM-1** `mapping/mapping_services.py:1667` · Both (Eufy + Roborock) — custom layouts are brand-independent map-bucket state. — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  set_custom_segments is a REPLACE-ALL write that cannot name its target layout — it lands on whatever layout is active at call time, destroying another layout's authored geometry
- [x] **A5-FURNIS-1** `mapping/mapping_services.py:2108` · both — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  map_id is documented as optional + auto-resolving on 6 presentation services but is vol.Required; a literal blank map_id silently mints and writes a phantom map bucket
- [x] **A6-ZONE-C-6** `mapping/mapping_services.py:2545` · Both for the phantom-bucket mechanism. The rename trigger is Roborock-specific (map NAME as id); the Roborock select's state changing on an in-app rename is near-certain but is device behaviour I could not verify from source. — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  Every handler in the block mints a persisted map bucket for an unknown map_id — including on the pure not-found and read-only clean paths
- [x] **A6-DIAG-6** `services/dock.py:124` · both — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  set_dock_event_count overwrites and immediately saves a durable counter for any entity_id, with no managed-vacuum check and no way back except the response body
- [x] **A6-DIAG-5** `services/errors.py:93` · both — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  get_recent_errors — a read-only service — creates and persists a durable error_tracker record for any entity_id the caller names
- [x] **A2-JOB-8** `services/queue.py:151` · both — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  Queue mutators create and persist a storage bucket for any syntactically-valid entity id, including one that is not a vacuum this integration manages
- [x] **A5-RUNPROF-8** `services/snapshots.py:78` · both — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  No service here checks that vacuum_entity_id is a vacuum this integration manages; unknown ids create durable storage buckets, and a read service writes
- [x] **A2-DRAFT-4** `themes/manager.py:111` · both — **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  _get_vacuum_theme creates per-vacuum draft state for ANY well-formed entity id, so update_working_draft / revert_draft / set_active_theme return ok:true for a vacuum that does not exist and persist a record nothing can reach
- [x] **A2-POLYGO-3** `mapping/mapping_services.py:762` · Both (get_map_segments serves CV and custom scopes identically; on Roborock it bites in custom mode via the active layout's stores) — **RP-029** (`63b7e3b`, 2026-08-02)  
  `_apply_segment_adjustments` returns the PERSISTED segment dicts by reference, and its caller writes `room_id` into them - baking a cleared/moved room link permanently into .storage and breaking the documented 1:1 invariant
- [x] **A3-IMAGE--7** `mapping/mapping_services.py:1012` · Both. — **RP-029** (`63b7e3b`, 2026-08-02)  
  delete_map_image drops the storage record and reports deleted:True even when the file removal failed, and analyze's filesystem probe then re-uses the orphan
- [x] **A4-CUSTOM-3** `mapping/mapping_services.py:1449` · Eufy only — on Roborock async_get_map_data_dict returns None early (map_source_coordinator.py:683), so nothing is written. — **RP-029** (`63b7e3b`, 2026-08-02)  
  _backfill_saved_zone_area fails OPEN on an indeterminate active map and permanently persists area_m2 / room_number computed from the WRONG map's raster — the poisoned value never self-heals
- [x] **A4-CUSTOM-4** `mapping/mapping_services.py:1467` · Eufy only — zone_membership returns room_number=None on Roborock (no per-pixel raster), so the `membership.get('room_number') is not None` arm never fires there. — **RP-029** (`63b7e3b`, 2026-08-02)  
  _backfill_saved_zone_area overwrites a user's explicit 'Unassigned' filing — room_number=None means both 'never computed' and 'user chose Unassigned', and the read path cannot tell them apart
- [x] **A6-ZONE-C-1** `mapping/mapping_services.py:2608` · Both. Roborock is more exposed: map_id is the vendor map NAME read off a select entity that goes `unavailable` whenever the upstream integration reloads, and the wrong-map projection can land on a different FLOOR. — **RP-029** (`63b7e3b`, 2026-08-02)  
  Saved-zone clean dispatches to the device when the active-map signal is blank — the "active map only" guard is permissive, not a refusal
- [x] **A6-ZONE-C-3** `mapping/mapping_services.py:2490` · Both. — **RP-029** (`63b7e3b`, 2026-08-02)  
  The `map_version` re-map invalidation the design doc specifies as the zone's safety key does not exist anywhere in the codebase
- [x] **A6-ZONE-C-4** `mapping/mapping_services.py:2503` · Eufy only — async_get_map_data_dict is the Eufy-only coordinator accessor (degrades to None elsewhere per docs/dev/frontend/saved-zones.md Wave 2), so on Roborock both fields simply stay None. — **RP-029** (`63b7e3b`, 2026-08-02)  
  create_saved_zone files area_m2 + room_number from whatever raster is live when the active map is indeterminate, and that wrong value can never be corrected
- [x] **A6-ZONE-C-7** `mapping/mapping_services.py:2614` · Both. — **RP-029** (`63b7e3b`, 2026-08-02)  
  Both clean handlers ignore the zone's `kind`, so a zone saved with any non-"clean" kind is still dispatched as a clean
- [x] **A2-POLYGO-1** `mapping/segment_primitives.py:277` · Both (custom layouts are brand-agnostic; Roborock declares segmenter_engine='noop_fallback' so the custom compose path is its ONLY segment source, making this its primary path) — **RP-029** (`63b7e3b`, 2026-08-02)  
  Authored custom segments grow ~1 working-pixel toward +X/+Y on every save, and the growth compounds without bound across save/reload cycles
- [x] **A2-POLYGO-2** `mapping/segment_primitives.py:267` · Both (custom layouts are brand-agnostic; worst for Roborock, whose segmenter_engine is 'noop_fallback' so custom layouts are its only segment store) — **RP-029** (`63b7e3b`, 2026-08-02)  
  `rasterize_primitives` returns the same `[]` for 'numpy/Pillow missing' as for 'degenerate shape', so set_custom_segments silently wipes the layout and reports saved:true
- [x] **A2-POLYGO-4** `mapping/segment_primitives.py:221` · Both (brand-agnostic custom-layout authoring) — **RP-029** (`63b7e3b`, 2026-08-02)  
  `mask_to_polygon` keeps only the largest traced loop, so merging two non-touching shapes into one room silently discards every piece but the biggest
- [x] **A2-POLYGO-8** `mapping/segment_primitives.py:305` · Both (brand-agnostic custom-layout authoring) — **RP-029** (`63b7e3b`, 2026-08-02)  
  A malformed primitive is silently skipped mid-segment, so a partially-drawn room saves as a success with no signal in the response
- [x] **A2-GEO-3** `mapping/map_source.py:191` · eufy — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  normalize_rendered CLAMPS out-of-grid pixels onto the map border instead of rejecting them, so off-grid raster cells and bad poses fold onto an edge rather than disappearing — diverging from the card's own decoder, which drops them
- [x] **A2-GEO-5** `mapping/map_source.py:314` · both — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  A room's normalized bbox excludes its last pixel row/column while width_m/height_m on the same dict include it (+1) — the two size descriptors disagree by exactly one cell, and Roborock's equivalent omits the +1
- [x] **A2-GEO-6** `mapping/map_source.py:387` · eufy — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  zone_membership's docstring says the dominance vote counts cells 'whose centre falls inside the zone polygon'; the code tests the cell's top-left corner
- [x] **A3-EXT-3** `mapping/map_source.py:686` · eufy — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  A dropped/renamed upstream geometry field degrades to a confidently WRONG map, not a loud absent one
- [x] **A3-EXT-4** `mapping/map_source.py:243` · eufy — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Room-outline offset is the exact NEGATION of the fork renderer's — overlays desync from the live backdrop whenever the outline origin differs from the map origin
- [x] **A5-POSE-6** `mapping/map_source.py:139` · both — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  `resolve_furnished_render` passes a stored placement transform through with no map-geometry stamp, so a re-mapped floor plan silently misaligns the art
- [x] **A5-POSE-7** `mapping/map_source.py:582` · eufy — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  An off-grid robot pixel is clamped onto the map edge and reported as a confident anchor — "off the map" is indistinguishable from "at the edge"
- [x] **A2-GEO-4** `mapping/map_source_runtime.py:466` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  correspondences_from_mapdata's docstring claims clamped corners are skipped; _mapdata_projector silently clamps with no detection, leaving the affine round-trip check as the only guard
- [x] **A4-RB-7** `mapping/map_source_runtime.py:260` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  _walk and _structure_tree can only descend objects exposing __dict__, so a slotted/C-extension node is both an undiscoverable dead end and an uninformative diagnostic
- [x] **A4-RB-8** `mapping/map_source_runtime.py:534` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  correspondences_from_mapdata's docstring claims clamped corners are skipped; the code feeds them into the least-squares fit, turning a rare edge case into an unexplained zone refusal
- [x] **A1-SERVIC-6** `mapping/mapping_services.py:406` · Both. — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  `backdrop_source` is the only enum-shaped field in the file left as free-form `cv.string`, is absent from services.yaml, and a typo produces a custom layout that can never hold segments and cannot be repaired
- [x] **A3-IMAGE--11** `mapping/mapping_services.py:1089` · Both; any adapter that tunes min_area_pixels away from 1200. — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  min_area_pixels silently overrides the adapter's configured tuning because absent is coerced to 1200 before the is-not-None check
- [x] **A3-IMAGE--9** `mapping/mapping_services.py:945` · Both. — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Layout existence is validated before the executor write and re-checked afterwards only by a silent isinstance guard, so a concurrent layout delete orphans the upload
- [x] **A5-FURNIS-3** `mapping/mapping_services.py:2076` · both — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  _handle_set_room_viewport is the only furnished writer with no clamp and a corner-valued default — zoom:0 and cx/cy:0.0 persist verbatim
- [x] **A5-FURNIS-5** `mapping/mapping_services.py:2130` · both — sharpest on Roborock, whose rendered image is trimmed to the occupied extent — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  hidden_regions are stored as normalized rects with no record of the frame they were authored against, so a re-map re-aims the masks onto different physical areas — and masks hide content by default
- [x] **A5-FURNIS-6** `mapping/mapping_services.py:1969` · both — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Clearing a home-scope art placement setdefaults an empty home_art dict, flipping the 'no furnished data' sentinel from None to a confident empty payload
- [x] **A7-ROBORO-1** `mapping/roborock_raw_map.py:158` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  A raster containing ZERO rooms is published as present:True — decode's own room_ids signal is computed and discarded
- [x] **A7-ROBORO-5** `mapping/roborock_raw_map.py:198` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Two functions in this module read the same `flip_y` key with OPPOSITE defaults, so a decoded dict missing the key renders flipped but drift-checks unflipped
- [x] **A7-ROBORO-6** `mapping/roborock_raw_map.py:284` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  geometry_drift reports max_center_delta: 0.0 when there are no common rooms — an optimistic accumulator that survives an empty loop
- [x] **A7-ROBORO-7** `mapping/roborock_raw_map.py:96` · roborock — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  The IMAGE-block dimension guard is `header_len >= 16`, but the four dims occupy the LAST 16 bytes of a header whose first 8 are the fixed type/len fields — anything under 24 reads dims out of the header's own metadata
- [x] **A6-TRK-6** `mapping/tracker.py:196` · both — **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Dock-drift append rewrites the entire log file on every reading, and a failed write silently forfeits that drift event via the already-committed _last_dock_pos
- [x] **EP-1** `button.py:200` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  The maintenance reset button discards a documented failure result and reports success
- [x] **A6-VAC-2** `dock/manager.py:93` · eufy — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Dock action returns performed=True / "Dock action sent." when the resolved button entity exists only in the registry (disabled or not loaded) — a silent no-op reported as success
- [x] **A5-SVC-3** `learning/services.py:735` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  retry_missed_rooms permanently destroys the map's room-enable selection and persists it to disk even when the start was BLOCKED and nothing ran
- [x] **A5-SVC-4** `learning/services.py:486` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  record_estimate_accuracy's schema requires no keys at all; an entry missing map_id/slug writes a permanently unreadable durable record and returns a confident success payload
- [x] **A4-PP-RP-3** `profiles/manager.py:1283` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  start_run_profile mutates and persists every room's selection and settings BEFORE the start is allowed, and never reverts when the start refuses
- [x] **A4-PP-RP-7** `profiles/manager.py:1258` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Applying a profile whose rooms no longer exist silently deselects and persists every room on the map, and reports the failure as "profile_not_found"
- [x] **A1-WIRE-2** `services/_common.py:57` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  resolved_call_data's docstring claims an unresolvable map_id always raises; discover_rooms is the one consumer that silently falls through and persists the payload under an empty-string map key
- [x] **A2-JOB-9** `services/_common.py:58` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  resolved_call_data's docstring claims a "clear error" on unresolvable map_id; the actual failure is a bare TypeError, and no service in either module raises ServiceValidationError
- [x] **A4-SETUP-4** `services/adapter_config.py:57` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_adapter_config / delete_adapter_config declare no supports_response and return None on every rejection path — a rejected write is indistinguishable from a successful one
- [x] **A4-SETUP-14** `services/adapter_config.py:198` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_vacuum_capabilities uses the raising get_manager() while its siblings in the same module use the tolerant .get() form, and it writes storage on a read-shaped service
- [x] **A6-DIAG-1** `services/dock.py:83` · eufy — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Dock actions return performed:true / "Dock action sent." when the resolved button entity has no state — the press is silently dropped by HA
- [x] **A6-DIAG-7** `services/dock.py:59` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_dock_action_status raises a raw TypeError when map_id cannot be auto-resolved — the only unwrapped handler in the three modules, and _common's docstring claims the opposite
- [x] **A6-DIAG-4** `services/errors.py:71` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  acknowledge_error returns the same {"acknowledged": true} whether the latch was deleted, merely MARKED, or was never there — and both docstrings still describe the pre-audit delete semantics
- [x] **A1-WIRE-1** `services/job_control.py:156` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_manager() is re-fetched after a device-length await, so a config-entry reload mid-dispatch loses the just-started job record (or raises a bare KeyError)
- [x] **A2-JOB-1** `services/job_control.py:322` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  start_selected_rooms discards every refusal — no supports_response, no exception, DEBUG log only; docs promise a response it cannot return
- [x] **A2-JOB-3** `services/job_control.py:238` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  clear_active_job destroys a running job's record unconditionally and returns nothing — no status precondition, no supports_response, immediate persist
- [x] **A2-JOB-7** `services/job_control.py:156` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  async_save() sits after the try/except in every job_control handler — a raise after dispatch leaves a running job in memory only
- [x] **A6-DIAG-2** `services/maintenance.py:94` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  set_maintenance_interval accepts ANY component string, persists it, and returns saved:true — its sibling reset_maintenance raises ServiceValidationError for exactly that input
- [x] **A6-DIAG-3** `services/maintenance.py:46` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  set_maintenance_interval bypasses the min/max its own docstring claims, and interval_hours: 0 silently turns off the consumable's alert
- [x] **A6-DIAG-9** `services/maintenance.py:95` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Mutate-then-save is not atomic in all three write services: a save failure surfaces an error while the change has already taken effect in memory
- [x] **A2-JOB-5** `services/queue.py:40` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Break schemas do not enforce the break_type→parameter dependency, and the two sibling schemas disagree on which break types exist
- [x] **A2-JOB-6** `services/queue.py:51` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_queue_steps returns `breaks` in a shape set_queue_breaks rejects — the documented read-modify-write round trip fails validation
- [x] **A3-ROOMS-5** `services/room_profiles.py:168` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  apply_room_profile silently no-ops on unknown room ids and returns a success-shaped response with no way to tell
- [x] **A3-ROOMS-7** `services/room_profiles.py:52` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_user_room_profile silently overwrites an existing custom profile and reports saved: true, while its sibling rename_room_profile refuses the identical collision
- [x] **A3-ROOMS-11** `services/room_profiles.py:122` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Error-surfacing is inconsistent across the area: rooms.py wraps 4 of 5 handlers, room_profiles.py wraps 0 of 8, access_graph.py wraps 0 of 2
- [x] **A3-ROOMS-10** `services/rooms.py:251` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_managed_rooms is the most destructive service in the area and the only mutation registered without supports_response
- [x] **A5-RUNPROF-1** `services/run_profiles.py:97` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_run_profile never inspects the manager's `saved` flag — a save that stored nothing returns a success-shaped response and raises nothing
- [x] **A5-RUNPROF-2** `services/run_profiles.py:114` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  apply_run_profile persists a full room-selection wipe and reports no error when the profile's rooms no longer exist on the map
- [x] **A5-RUNPROF-3** `services/run_profiles.py:146` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  overwrite_run_profile exposes the step-sequence destruction with no warning, no confirmation, no response signal — and commits it with async_save
- [x] **A5-RUNPROF-5** `services/run_profiles.py:71` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  rename_run_profile accepts a blank name and silently relabels the profile 'Untitled', returning renamed:True — the sibling save rejects the same input
- [x] **A5-RUNPROF-6** `services/run_profiles.py:152` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  overwrite_run_profile with no rooms enabled returns overwritten:False as a success — the raise gate matches one literal reason, not the failure flag
- [x] **A5-RUNPROF-7** `services/run_profiles.py:90` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_saved_run_profiles and get_dashboard_snapshot lack the package's try/except wrap; an unresolvable map_id surfaces as a raw TypeError, contradicting resolved_call_data's docstring
- [x] **A4-SETUP-7** `services/setup.py:215` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Three setup handlers subscript data["map_id"] after resolved_call_data and raise a bare KeyError — the helper's docstring claims the manager raises a clear error instead
- [x] **A4-SETUP-8** `services/setup.py:222` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_save_rooms stamps the setup step complete unconditionally, unlike both of its sibling step-advancing handlers
- [x] **A4-SETUP-10** `services/setup.py:100` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  floor_types accepts any string; an unrecognised value is silently clamped to "hardwood" at read time, so a mistyped carpet becomes a wet-mopped carpet
- [x] **A4-SETUP-11** `services/setup.py:229` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_delete_map auto-resolves an omitted map_id to whatever map happens to be active at call time
- [x] **A4-SETUP-12** `services/setup.py:184` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_get_map_rooms returns a success-shaped empty room list when the runtime manager is missing — the caller cannot tell "integration not loaded" from "map has no rooms"
- [x] **A4-SETUP-13** `services/setup.py:336` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_set_map_camera stores an unvalidated entity_id and reports success even when the entity does not exist
- [x] **A1-CRUD-7** `themes/manager.py:370` · both — **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  set_theme_tags silently discards tags past 16 or longer than 32 chars and still returns ok:True
- [x] **A5-SVC-9** `learning/services.py:72` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  Schemas mark map_id Required on three services the documentation marks optional, so an automation written from the docs fails validation
- [x] **A1-SERVIC-4** `mapping/mapping_services.py:443` · Both — the geometry layer is brand-independent; only the final dispatch conversion differs. — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  `_saved_zone_coord`'s docstring claims it "mirrors the hidden-regions sanitizer" but omits that sanitizer's degenerate-drop — a zone that can be saved but can NEVER be cleaned, with no service able to repair its geometry
- [x] **A1-SERVIC-7** `mapping/mapping_services.py:115` · Both (no runtime effect). — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  19 schemas (lines 115-301) are dead — defined once, referenced nowhere — and two of them are near-duplicate twins of LIVE schemas whose defaults would be rejected by the live validators
- [x] **A3-IMAGE--10** `mapping/mapping_services.py:964` · Both. — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  Four of the five services in this block have no services.yaml description, including the destructive delete_map_image
- [x] **A4-CUSTOM-7** `mapping/mapping_services.py:1650` · Both. — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  set_custom_segments' user-facing description is two features stale — it claims map-level scope and an uploaded-backdrop requirement that the layout + live-dims paths superseded
- [x] **A5-FACADE-5** `services.yaml:1179` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  services.yaml declares a REQUIRED 'carpet' field on save_user_room_profile and overwrite_room_profile that the voluptuous schema rejects
- [x] **A1-WIRE-3** `services/dock.py:174` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  Sixteen registered services documented as public API have no services.yaml descriptor, including set_dock_event_count whose five dock siblings all have one
- [x] **A1-WIRE-4** `services/room_profiles.py:203` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  get_room_profiles is the only one of the 79 registrations with no schema, so caller-supplied scoping arguments are accepted and silently ignored
- [x] **A3-ROOMS-4** `services/room_profiles.py:43` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  services.yaml advertises required fields that the voluptuous schemas reject — three services fail outright when the user fills the form HA renders
- [x] **A3-ROOMS-3** `services/rooms.py:79` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  save_managed_rooms stamps every room's floor type as user-confirmed while its schema makes it structurally impossible to supply one
- [x] **A4-SETUP-15** `services/setup.py:353` · both — **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  None of the 10 setup_* services and 5 of the 6 adapter-config services have services.yaml or translation entries
- [x] **A6-VAC-3** `core/manager.py:1126` · eufy — **RP-033** (`06ffc73`, 2026-08-02)  
  refresh_vacuum_capabilities does NOT reproduce startup's detect_capabilities inputs — it silently drops the dock-button entity candidates, contradicting the comment above it
- [x] **A3-COMMON-2** `listeners/_common.py:198` · future_brand_only — **RP-033** (`06ffc73`, 2026-08-02)  
  completion_secondary_satisfied() returns True from a config FLAG without verifying the entity it delegates to exists; the "Invariant" asserted in the caller is never validated
- [x] **A4-POSE-4** `listeners/pose_sampler.py:242` · future_brand_only — **RP-033** (`06ffc73`, 2026-08-02)  
  A zero or negative interval_s survives adapter registration (warn-only) and then splits the sampler in two: register() drops it, _sample_vacuum_once does not
- [x] **DQ-DE-3** `queue/dispatch_engines.py:316` · future_brand_only — **RP-033** (`06ffc73`, 2026-08-02)  
  DreameSegmentEngine's documented 'direct envelope (no command)' is unreachable — an omitted command defaults to Eufy's room_clean
- [x] **DQ-DE-4** `queue/dispatch_engines.py:422` · future_brand_only — **RP-033** (`06ffc73`, 2026-08-02)  
  An omitted dispatch.template silently resolves to the Eufy engine with no warning, and the claimed registration-time rejection does not exist
- [x] **A4-SETUP-2** `services/adapter_config.py:67` · both — **RP-033** (`06ffc73`, 2026-08-02)  
  save_adapter_config accepts a two-key config and registers it OVER the live code adapter — every omitted block silently resolves to Eufy behaviour on a Roborock
- [x] **A4-SETUP-3** `services/adapter_config.py:108` · both — **RP-033** (`06ffc73`, 2026-08-02)  
  delete_adapter_config unregisters the CURRENTLY REGISTERED adapter — after startup that is the code adapter — leaving the vacuum with no adapter at all
- [x] **A4-SETUP-5** `services/adapter_config.py:86` · both — **RP-033** (`06ffc73`, 2026-08-02)  
  save_adapter_config persists to storage BEFORE registering, so a config the registry flags as invalid is written to disk anyway and reloaded at every restart
- [x] **A4-SETUP-9** `services/setup.py:131` · both — **RP-033** (`06ffc73`, 2026-08-02)  
  adapter `setup.steps` is never validated at registration despite two docstrings and the schema claiming it is; two declared step IDs have no completion writer and strand the wizard permanently
- [x] **A1-INIT-3** `core/manager.py:347` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  Startup re-seed of the bundled theme library resurrects themes the user deleted, and re-points default_theme_id
- [x] **A1-CRUD-1** `themes/manager.py:305` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  overwrite_theme WIPES the target theme's entire palette when the vacuum has no active theme — ok:True, persisted, no undo
- [x] **A1-CRUD-2** `themes/manager.py:303` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  overwrite_theme replaces the target with a copy of a DIFFERENT theme (the vacuum's active one), and silently repoints the vacuum at the target
- [x] **A1-CRUD-3** `themes/manager.py:386` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  delete_theme of a bundled/core theme is silently undone at the next HA restart — the seeder re-adds it
- [x] **A1-CRUD-4** `themes/manager.py:321` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  overwrite_theme can permanently replace a bundled theme's palette while preserving source:"core", so user content keeps claiming to be shipped
- [x] **A1-CRUD-5** `themes/manager.py:391` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  delete_theme nulls the active pointer but leaves the vacuum's dirty working draft orphaned; the next save writes a theme containing only the deltas
- [x] **A1-CRUD-6** `themes/manager.py:351` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  rename_theme writes into the raw stored entry with no isinstance-dict guard, unlike set_theme_tags — a corrupt entry raises TypeError out of the service
- [x] **A1-CRUD-8** `themes/manager.py:350` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  rename_theme accepts a blank/whitespace name and silently stores "Untitled"; no duplicate-name check on rename or save_theme_as_new
- [x] **A2-DRAFT-1** `themes/manager.py:391` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  delete_theme clears active_theme_id but leaves the deleted theme's working draft and draft_dirty in place — the orphan draft bleeds over the card's default look forever and survives restart
- [x] **A2-DRAFT-2** `themes/manager.py:417` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  set_active_theme destroys the working draft unconditionally with no confirmation, no undo and no same-id short-circuit — clicking the already-active preset tile silently wipes every unsaved edit
- [x] **A2-DRAFT-3** `themes/manager.py:411` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  set_active_theme's global-default branch is the only mutator that returns without firing _notify_updated, leaving the theme sensor's default_theme_id attribute stale
- [x] **A2-DRAFT-6** `themes/manager.py:654` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  _import_scoped strips matching keys out of the working draft but never recomputes draft_dirty, so the draft can be left empty with the dirty flag stuck True
- [x] **A2-DRAFT-7** `themes/manager.py:224` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  _minimal_theme_mutation_response cannot express 'there is now no active theme' — a None active_theme_id is dropped from the payload rather than sent as null
- [x] **A3-PORT-1** `themes/manager.py:544` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  import_theme performs no key validation; the card applies every imported key as a real CSS declaration on the card host, so one imported theme file can render the card permanently blank
- [x] **A3-PORT-2** `themes/manager.py:643` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  _import_scoped clears a floor namespace in all three buckets but only re-applies the buckets the payload happens to contain, silently destroying per-layer opacity settings while reporting success
- [x] **A3-PORT-3** `themes/manager.py:625` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  A scoped import rewrites the ACTIVE library entry in place with no core/provenance check, permanently corrupting a bundled preloaded theme that the seeder will never repair
- [x] **A3-PORT-4** `themes/manager.py:411` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  set_active_theme with vacuum_entity_id=None returns without firing _notify_updated — the only mutation in the module that skips the callback fan-out, leaving default_theme_id stale in HA state
- [x] **A3-PORT-5** `themes/manager.py:554` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  Import name de-duplication appends '(imported)' at most once, so repeated imports of the same theme produce multiple indistinguishable library entries
- [x] **A3-PORT-7** `themes/manager.py:42` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  _clean_theme_tags coerces non-string items with str(), reachable only through the unvalidated import payload, and silently drops rather than truncates over-long and over-count tags
- [x] **A3-PORT-8** `themes/manager.py:172` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  The _get_theme_library_entries docstring claims write-time normalization that does not exist — _normalize_theme_entry is called from two sites and both are read paths
- [x] **SN-6** `themes/manager.py:412` · both — **RP-034** (`c005ad6`, 2026-08-02)  
  Setting the GLOBAL default theme returns without notifying, so the theme sensor is stale indefinitely
- [x] **EP-6** `binary_sensor.py:86` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  _attr_suggested_object_id is not a Home Assistant attribute - four sites rely on a dead assignment
- [x] **A3-FLOW-2** `config_flow.py:103` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  Changing the vacuum in the options flow ADDS a second managed vacuum instead of replacing the first — the old pick is never reconciled away
- [x] **A3-FLOW-3** `config_flow.py:98` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  The options flow rebuilds the options dict from the stale form snapshot, so a submit can resurrect a vacuum that was deleted while the dialog was open
- [x] **A6-VAC-5** `core/manager.py:1084` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  get_managed_vacuums reads data["capabilities"] raw and reports supports_* as None when no snapshot exists, unlike its sibling get_vacuum_capabilities which detects on demand
- [x] **A6-PRE-3** `jobs/job_monitor.py:58` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  PreflightResult declares `available` with a documented contract the producer never honours, and omits two keys the producer writes
- [x] **A6-PRE-4** `jobs/job_monitor.py:32` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  BlockedRoomEntry.source documents "access_graph" for graph-propagated blocks; the producer writes "access_dependency", and the wrong literal is hand-copied into an exposed sensor attribute's type
- [x] **A5-METRICS-3** `listeners/job_metrics.py:44` · future_brand_only — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  `_duration_state_to_seconds` silently treats any unrecognized unit as seconds, and re-resolves the unit per event with no mid-run consistency check
- [x] **A5-METRICS-4** `listeners/job_metrics.py:117` · future_brand_only — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  Station-water subscription guesses an entity key that exists nowhere, ignores the adapter's `supports_station_water` declaration, and swallows every lookup failure silently
- [x] **A5-METRICS-5** `listeners/job_metrics.py:165` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  watch_map's type annotation and the `int` value_type branch are both stale — the annotation declares 3-tuples while all three writers store 4-tuples, and no entry ever uses `int`
- [x] **EP-3** `number.py:22` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  Interval bounds are framework constants, and the ceiling is BELOW a shipped component's declared max
- [x] **INF-1** `panels.py:29` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  panels.py claims to be the single registration seam; a fourth site hand-copies all three of its constants
- [x] **DQ-PH-5** `queue/queue_engine.py:62` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  QueueEntry / PayloadItem / ActiveJobSnapshot describe a shape the module has never emitted, and disagree with build_active_job_state on the fields it does write
- [x] **SN-1** `sensor/__init__.py:98` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  A managed vacuum with no imported map gets ZERO per-vacuum sensors, and importing a map never creates them
- [x] **SN-8** `sensor/__init__.py:91` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  active_job_entities and its explanatory comment are dead
- [x] **SN-10b** `sensor/theme.py:75` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  A raw stored null theme name renders as the string 'None' — valid, but not reachable in normal operation
- [x] **INF-2** `timestamp_utils.py:8` · both — **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  _LOCAL_TZ is a FIXED offset captured at import, so naive legacy timestamps get the wrong offset half the year
- [x] **A1-EST-1** `learning/estimator.py:167` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Confidence breakpoint table has a dead band at 0.79–0.80; the best-learned rooms fall through it and render as LOW / red "error"
- [x] **A1-EST-2** `learning/estimator.py:844` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  App-started (external) runs contribute battery=0.0 samples; the estimator consumes a learned 0.0 as a real number and derives battery_warning / mid_job_recharge_risk = False from it
- [x] **A1-EST-3** `learning/estimator.py:476` · roborock — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  _find_room_match Pass 1 can NEVER match a Roborock room: it compares the raw "" intensity against the rebuilder's normalized "standard", so every Roborock room takes a permanent -0.15 intensity-mismatch penalty
- [x] **A1-EST-4** `learning/estimator.py:843` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Estimate consumes avg_minutes with no outlier rejection and no band check, and a single poisoned sample scores MEDIUM confidence because stddev of one sample is 0 by construction
- [x] **A1-EST-5** `learning/estimator.py:148` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  HIGH confidence is mathematically unreachable for any real room, yet _learning_velocity reports runs_to_high=0 at 10 samples and runs_to_medium=0 always
- [x] **A1-EST-6** `learning/estimator.py:484` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  _find_room_match relaxed passes return the lexicographically-first bucket and ignore sample_count entirely — a 1-sample bucket beats a 30-sample one
- [x] **A2-ACC-2** `learning/estimator.py:1122` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  reanchor_timeline ignores its own reanchor_at parameter — every ETA is anchored to job start plus the sum of room durations, so all wall-clock dead time is invisible and "Done at" times slide into the past
- [x] **A2-ACC-3** `learning/estimator.py:1178` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Reanchoring drops inter-room transit from remaining rooms while keeping it in overhead — remaining ETAs jump earlier then later (oscillation) and the job ETA inflates by one transit leg per completed room on a run that is exactly on estimate
- [x] **A2-ACC-4** `learning/estimator.py:1189` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  A skipped room can never be resolved: it holds "current" for the rest of the run, adds its full estimate to every later room's ETA, and permanently blocks all_completed
- [x] **A2-ACC-5** `learning/estimator.py:1130` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Completed-room slug matching is keyed on the literal string "none" — the documented slug fallback is dead, and a room with a null slug is marked complete before it is cleaned
- [x] **A2-ACC-6** `learning/estimator.py:637` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  The "exact vs allocated" quality flag is recorded and never used — job-average actuals are blended into the same drift mean, permanently capping affected rooms below HIGH confidence while the card promises they will get there
- [x] **A2-ACC-7** `learning/estimator.py:592` · both — **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  A non-dict `rooms` block crashes both accuracy readers — including estimate() on the event loop — while the sibling reader in the same subsystem explicitly tolerates it
- [x] **A3-SNAP-2** `core/manager.py:3914` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  get_dashboard_snapshot composes get_job_progress_snapshot TWICE, so job_progress and job_control in the same payload can describe different rooms — and every side effect in the progress composer fires twice per card poll
- [x] **A1-EST-9** `learning/estimator.py:766` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  estimate() runs ensure_dirs (four mkdir syscalls) three times per call on the event loop, even on full cache hits
- [x] **A3-IO-4** `learning/history_store.py:148` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  ensure_dirs runs inside every path getter, so the caches that exist to keep the loop-bound estimate off disk still issue ~32 blocking filesystem syscalls per dashboard snapshot
- [x] **A4-STATE-7** `learning/history_store.py:232` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  load_live_snapshot performs 4 mkdir syscalls plus an open()/read() on the Home Assistant event loop at every cold finalize
- [x] **A2-GEO-2** `mapping/map_source.py:381` · eufy — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  zone_membership scans the entire room_outline raster with a per-cell normalize_rendered before the bbox reject, synchronously on the event loop — measured ~0.10 s per zone, ~1.0 s per dashboard read
- [x] **A7-ROBORO-2** `mapping/roborock_raw_map.py:200` · roborock — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  raster_room_bboxes runs an O(width*height) pure-Python per-pixel loop directly on the Home Assistant event loop
- [x] **A6-TRK-7** `mapping/tracker.py:286` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  start_job/end_job are dispatched to an executor thread on the strength of a comment describing disk I/O that start_job does not perform
- [x] **DR-ONB-5** `sensor/onboarding.py:55` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  The sensor recomputes the entire onboarding summary twice per update
- [x] **A2-DRAFT-5** `themes/services.py:230` · both — **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  Every update_working_draft triggers an immediate full Store.async_save of the entire integration data dict, and the card fires it on `input` — once per keystroke in text and number token fields
- [x] **DR-DOCK-1** `dock/manager.py:383` · eufy — **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  The dock-event timestamp is written BEFORE the debounce, so a debounced event still corrupts last_*
- [x] **DR-DOCK-2** `dock/manager.py:383` · both — **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  record_dock_event validates nothing; its sibling set_dock_event_count validates the same vocabulary
- [x] **DR-DOCK-3** `dock/manager.py:446` · both — **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  A manual counter reset leaves the debounce marker, suppressing the next genuine event
- [x] **A1-REG-1** `listeners/dock_events.py:74` · eufy — **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  dock_events treats any arrival at a trigger value as a NEW dock cycle — a startup, an entity re-add, or an `unavailable` blip mid-cycle re-records the event and increments the durable counter
- [x] **A1-REG-4** `listeners/dock_events.py:91` · future_brand_only — **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  dock_events.register() never reads the adapter's `dock_events.enabled` flag — a brand that declares enabled:False but inherits triggers still records dock events
- [x] **A6-GUARD-3** `listeners/dock_events.py:72` · eufy — **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  dock_events treats a first-sighting (old_state=None) and an unavailable-recovery as a fresh dock cycle, inflating maintenance counters and resetting last_dry_start
- [x] **DR-DIAG-5** `diagnostics.py:53` · both — **RP-039** (`4a0afb9`, `1981640`, `56fb7be`, `498a285`, `4b07de2`, 2026-08-03)  
  Dead `_SENTINELS` alias sits in the one file whose header explains why that set must not fork
- [x] **A1-ID-5** `adapters/eufy/discovery.py:47` · eufy — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  adapters/eufy/discovery.py is a dead, divergent second implementation of get_active_map_id / discover_rooms_for_vacuum with hand-copied sentinel and key literals
- [x] **DR-BAT-2** `battery/manager.py:601` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  An out-of-order sample is correctly skipped but still rewinds the last-sample anchor
- [x] **DR-BAT-3** `battery/manager.py:653` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  After a stale-session discard, charging stays untracked until the next charge cycle
- [x] **INF-7** `const.py:27` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Four constants are defined and never read - including three service names for services that do not exist
- [x] **A2-CB-3** `core/manager.py:579` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The manager's four own callback registries append without a duplicate check while the theme registry they delegate to dedupes, and unregister removes only one copy
- [x] **A2-CB-4** `core/manager.py:1035` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  remove_vacuum_record wipes every bucket the five callback registries exist to mirror and fires none of them, dropping the notification obligation its narrower sibling remove_map documents
- [x] **A4-START-3** `core/manager.py:2943` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_start_status can never surface a non-blocking lifecycle warning message — preflight's "ready" text shadows it, making dock-drying starts show warning=True with the message "Ready to start cleaning."
- [x] **DQ-ACT-7** `dispatch/manager.py:421` · future_brand_only — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The OFF-fallback lowercases the select's options for the membership test but then sends the lowercased string as the option value
- [x] **DR-BAT-1** `docs/dev/12-battery-system.md:88` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Doc §3 states the MAX_DELTA_PCT boundary one step off from the code and from its own §5.2
- [x] **DR-BAT-4** `docs/dev/12-battery-system.md:338` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Doc omits two live conditions present in the code
- [x] **DR-ONB-6** `docs/dev/18-onboarding-manager.md:228` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Doc cites the start gate at core/manager.py:2776; it is at 2805
- [x] **A3-IO-5** `learning/history_store.py:368` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_completed_job_path interpolates an unvalidated job_id into a filesystem path, giving exclude/restore_learning_job an arbitrary *.json overwrite primitive — the exact hole the sibling module already hardened
- [x] **A3-IO-7** `learning/history_store.py:196` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  write_json is rename-atomic but not durable — no fsync before os.replace, so a power loss can leave a zero-length learned file that read_json then reports as "no data"
- [x] **A3-IO-8** `learning/history_store.py:599` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  append_job_csv_row / append_room_csv_rows are dead, and each CSV header is a hand-copied literal duplicated between the dead append writer and the live rebuild writer
- [x] **A3-COMMON-5** `listeners/_common.py:52` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_adapter_value() is a second, independent implementation of the identical lookup already shipped in adapters/registry.py
- [x] **A4-POSE-6** `listeners/pose_sampler.py:10` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Module docstring still declares the sampler 'Capture-only / inert — nothing consumes pose_samples yet', but the W5c consumption wire has landed
- [x] **A3-EXT-5** `mapping/map_source.py:808` · future_brand_only — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Two room extractors disagree on the input coordinate frame and the dead one is the one under test
- [x] **DR-MAP-1** `maps/map_manager.py:62` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_map_bucket returns a DETACHED dict on a miss and live storage on a hit
- [x] **DR-MAP-2** `maps/map_manager.py:95` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_vacuum_maps_summary mixes a live room_count with CACHED enabled/disabled counts
- [x] **A1-ID-6** `models/models.py:162` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  RoomRecord documents grants_access_to as 'list[str] — room slugs' but every producer and consumer stores integer room ids
- [x] **INF-3** `models/models.py:257` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  VacuumCapabilities is a never-constructed dataclass whose field names do not exist in the real capability payload
- [x] **DR-ONB-4** `onboarding/manager.py:66` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The five-key default record is hand-duplicated between _get_map_onboarding and reset_onboarding
- [x] **A6-PP-EST-H2O-2** `planning/run_plan.py:237` · future_brand_only — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  A declared water_rates table REPLACES the core table wholesale, so an adapter that omits "off" bills 4.0 ml/min for water-off mop rooms — contradicting the comment that asserts the invariant
- [x] **A6-PP-EST-GUESS-1** `planning/run_plan.py:378` · eufy — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  estimate_job_water_usage drops the timeline's source/sample_count provenance, so default-guess room timings are presented as a measured "Job will use N ml"
- [x] **A6-PP-EST-CLAMP-1** `planning/run_plan.py:476` · eufy — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Tank-remaining ml is unclamped while its own percent is clamped to [0,100], and robot_internal_tank_ml is reported but never used in any calculation
- [x] **DQ-PAY-7** `queue/queue_engine.py:294` · future_brand_only — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  clean_passes_field: null omits passes in two engines but produces a None dict key in build_room_clean_payload
- [x] **INF-6** `repairs.py:1` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The repair flow is unreachable - nothing ever raises an issue - and the doc asserts the opposite
- [x] **A3-CRUD-7** `rooms/room_crud.py:318` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_managed_rooms returns the live stored rule dicts and metadata sub-objects by reference despite copying the outer containers
- [x] **DR-ONB-3** `sensor/onboarding.py:62` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The 'empty means complete' guard exists in setup/status.py and was never mirrored onto the onboarding summary — forgotten override sibling
- [x] **DR-SETUP-2** `setup/drift.py:117` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  auto_refresh_on still uses the bare or-coercion that code-flag CS-2 fixed for its three siblings
- [x] **DR-SETUP-3** `setup/drift.py:336` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Two unguarded int(key) coercions on drift-history keys, in a module that guards every other one
- [x] **DR-SETUP-4** `setup/protection.py:44` · both — **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Protection evaluation calls .get() on map buckets and room records without isinstance guards
- [x] **DOCK-1** `learning/job_finalizer.py:939` · eufy (Roborock declares no code tables, so it degrades to 'trust the run') — **RP-046** (`5b21a1a`, `14a4f43`, 2026-08-04)  
  total_error_seconds is subtracted from cleaning_time_seconds with no notion of WHOSE fault it was, so a station fault raised while the robot cleaned normally is charged against the robot's cleaning time
- [x] **A4-SETUP-6** `services/setup.py:243` · both — **RP-048** (`56af6b1`, 2026-08-05)  
  setup_reject_rooms permanently deletes rooms from EVERY map for the vacuum with no map scoping, no protection gate, no confirmation and no way back
- [x] **DQ-ACT-6** `core/manager.py:5005` · roborock — **RP-049** (`4fbb530`, 2026-08-05)  
  A pre-call leaves the device in a modified state (and the stashed run steps consumed) when the clean then fails to start
- [x] **AGX-CLEAR-1** `custom_components/eufy_vacuum/services.yaml:0` · both — **RP-049** (`4fbb530`, 2026-08-05)  
  The graph refusal offers two exits and only one is reachable — there is no clear-the-access-graph action or service
- [x] **INF-9** `entity_helpers.py:109` · both — **RP-049** (`4fbb530`, 2026-08-05)  
  get_floor_type_label emits hardcoded English into an 18-language product
- [x] **A7-ROBORO-4** `mapping/roborock_raw_map.py:171` · roborock — **RP-049** (`4fbb530`, 2026-08-05)  
  ro_dx/ro_dy are hardcoded 0 and the decoded top/left are discarded — the payload cannot express any offset between the raw IMAGE-block frame and the parser's rendered frame
- [x] **I18N-1** `src/renderers/shared.js:0` · both — **RP-049** (`4fbb530`, 2026-08-05)  
  The tRaw docstring claims it escapes interpolated values; it does not — neither t() nor tRaw() escapes vars
- [x] **A6-GUARD-2** `listeners/path_blockers.py:194` · both — **RP-050** (`8d244dc`, 2026-08-05)  
  path_blockers spawns unbounded concurrent `_process` tasks; a second blocker event inside the 30s cancel-confirm window double-cancels and the loser deterministically nulls the run's finalize_summary
- [x] **SETUP-REJ-2** `rooms/room_manager.py:51` · both — **RP-051** (`2a283eb`, 2026-08-05)  
  build_managed_rooms' rejected_rooms= exclusion (CRUD-5) has no production caller
- [x] **DEPLOY-PURGE-1** `scripts/deploy-live.ps1:61` · both — **RP-052** (`93953fa`, 2026-08-05)  
  deploy-live.ps1 never purges — every file the audit ever DELETED is still running live
- [x] **RB-PROJ-1** `mapping/map_source_runtime.py:509` · roborock — **RP-054** (`168b26c`, 2026-08-05)  
  A dead projector empties EVERY Roborock overlay silently — nothing counts the drops, nothing logs

### Examined and deliberately not fixed

Real behaviour, but reaching it requires using the feature against its own purpose.
Recorded so it is not re-reported as a new finding, and documented where it lives.

- **DR-DBG-5** `debug_capture.py:263` — The restore guard cannot distinguish its own DEBUG from a user's mid-capture `logger:` DEBUG  
  Reaching it requires starting the flight recorder — a tool whose entire purpose is to avoid enabling `logger:` debug — and then enabling `logger:` debug anyway, mid-capture. That is a user footgun, not a defect: the two actions contradict each other. Documented in the module and in the post rather than guarded against.
- **SN-10a** `sensor/theme.py:75` — KILLED: the claim that a hand-edited theme import can store a raw null name  
  KILLED — the reachability premise is fatal to the claim AS RECORDED. Stage B's reproducer executed it: import_theme does `name = str(source_theme.get('name','')).strip()` (themes/manager.py:537), so a JSON null becomes the STRING 'None', which is truthy and passes the `if not name` gate. The stated entry path — 'reachable via a hand-edited import' — cannot produce the defect. That sentence was mine and it was wrong. Split from the original SN-10 so Corpus C does not have to assert the LINE is correct; the line-level defect survives as SN-10b.

### Carried forward from before the audits

_None open._

**Closed (7)** — kept visible with evidence, not dropped.

- ~~**`active_boundaries` round-trip (SEG-1)**~~ — CLOSED 2026-08-05 — Closed by facf7a9 as the ADDITIVE second field Chris chose -- his words, 'the least change and the safest change'. `selected_boundaries` records what the segmenter SELECTED, captured PRE-drop, alongside the two sets the record already had: `candidates` (every boundary detected) and `active_boundaries` (the survivors of the trailing-drop). The gap was the middle set: `active_ids` was built inside the keep-loop past its break, so a dropped trailing segment's boundary was erased and the record could not reproduce its own input.
  Nothing is reinterpreted, no schema bump, no migration -- a record written earlier simply has no key, which reads as UNKNOWN rather than empty. Changing the meaning of a field under records already on disk is the class of problem that bit twice today; the second-field shape sidesteps it entirely.
  Mattered more than when filed: tests/replay/reverdict.py now re-judges old records with current code (four fixes validated that way today, no vacuum), and a record that cannot restate its inputs bounds what replay can prove. Pin verified to bite -- pre-fix the fixture gives selected == active == [2], the erasure reproduced.
- ~~**Three card strings untranslated**~~ — CLOSED 2026-08-05 — The translation pass landed; `[CARD4-1]` (src/i18n/card4-untranslated-strings.test.mjs) asserts all three keys are present in every one of the 17 shipped packs and PASSES. Verified by running the test, not by grep -- two of my greps were wrong first (the packs are de-bundled to frontend/locales/, and that JSON is NESTED, so a flat "common.service_failed" pattern can never match).
- ~~**Card: the two failure-renders-as-success paths (FE-ERR-1 / MZ-2)**~~ — CLOSED 2026-08-05 — VERIFIED AT SOURCE AND BY TEST 2026-08-05. Both failure-renders-as-success paths are closed by ONE centralised check in src/actions/core.js:89-95 -- inside the shared service caller, so it is asked once rather than at each call site:
    if (returnResponse && result && typeof result === 'object') {
      const refused = result.success === false
        || (result.started === false && result.reason !== 'confirmation_required');
      if (refused) this.showServiceRefusalToast(result.reason);
    }
  It handles BOTH backend refusal shapes -- {success:false, reason} (RP-031, most services) and {started:false, reason} (job_control's start_*) -- either of which was previously handed back identically to a genuine success: no toast, nothing. MZ-2 specifically was {started:false} handled per call site where only ONE of three ever did it: startCleaning toasted, cleanZone and startRunProfile did not, so a refused ad-hoc zone clean was completely silent while the user believed the robot was going. confirmation_required is deliberately EXEMPT -- it is a prompt, not a refusal, and toasting it would put an error beside a question the user is being asked.
  10 regression tests pass: [CSF-1..6] core-service-failure.test.mjs (error toast names the service, failed call still returns null so existing null-checks keep working, success raises no toast, response payload untouched, no-toast-host does not throw, message routes through i18n not a literal) and [MZT-1..4] map-zone-clean-refusal-toast.test.mjs (job_in_progress refusal toasts with its reason, cleanZone passes returnResponse=true, a genuine dispatch raises no toast as control, no vacuum entity means no call and no toast).
  The carried entry's blocked_by, 'backend supports_response change', is STALE: the code reads returnResponse and the structured result throughout. Nothing was waiting on the backend.
- ~~**Card: the qualification gap (CC-5)**~~ — CLOSED 2026-08-05 — CLOSED AS NOT VERIFIABLE (Chris, 2026-08-05). The note — 'surface provenance, truncation and absent data honestly rather than as confident values' — names no file, no seam, no symptom. Searched: the only CC-5 corpus row is A2-ACC-5, an unrelated learning/estimator.py slug-matching bug; the src/renderers/review.js:360 CC-5 is a DIFFERENT concern (a clean-mode chip comparison) and is already fixed; and ec83cd7, which claimed 'CC-5 cluster down to two', touched only ledger files, no code. Nothing in the tree corresponds to this entry. It is unverifiable and unactionable by anyone, including whoever wrote it. This is the cautionary case now named in charter gate 15: an item that names no seam does not enter the ledger — a finding that does not name its seam is a note about a feeling.
  THE UNDERLYING IDEA MAY STILL BE GOOD, and is preserved here rather than lost with the box: the card presents derived values (estimates, confidence, coverage) without always saying where they came from, whether they were truncated, or that the data was absent rather than zero. Chris: 'It may mean we need a new feature.' If pursued it is a FEATURE with its own scoping — pick the surfaces, decide what provenance means per value, decide how absent renders differently from zero — NOT a defect to re-file. Do not resurrect this as a finding without a named seam.
- ~~**Card: surface captured run errors (`run_errors`)**~~ — CLOSED 2026-08-05 — Closed across 1b3155c (core carries enum-string codes; Roborock declares its tables) and this commit (the card reads error_seconds_by_source). The field was ALREADY persisted by the finalizer and nothing read it, so the fix was plumbing, not enrichment. Badge tooltip now names each source with seconds; unattributed is named explicitly rather than omitted, because silence would imply attribution we do not have. Three new keys translated into all 17 packs at creation. [REB-7..10] pin it, and [REB-6] drift guard extended to the source split.
- ~~**OpenDyslexic font support**~~ — CLOSED 2026-08-05 — Shipped across dfff15f (P1+P2: font asset, token override, preference), 818ad37 (P3: the picker, wired end to end), dd2ec11 (P4: harness, gallery, user guide). ec83cd7 even refreshed the ledger saying so -- and this hand-maintained Tier-3 line still read 'No code written'.
- ~~**Roborock edge-mopping: the adapter contradicts itself (was: control removal)**~~ — CLOSED 2026-08-05 — Closed by 162e391 exactly as re-scoped: the declaration stays False and the REQUEST goes away. vocabulary.py:164 now has vacuum_mop_deep edge_mopping False; all five profiles + CUSTOM_ROOM_PROFILE agree. Card gating was deliberately NOT done (it would hide the control on every Roborock including models that can edge mop -- a per-model fact frozen at brand level). Chris re-approved this same shape 2026-08-05 before it was found already done.

**Decisions (2)** — settled calls, not open work (gate 15). Each carries its revisit trigger; an untriggered deferment is how a carried item rots into an invisible wontfix.

- **Pose sampler predicates** — Two call sites were deliberately not re-pointed at the shared in-flight helper, because doing so would silently add `paused` to what gets sampled. Wants its own change.  
  _Revisit when:_ If pose sampling is ever intentionally widened to cover paused time — then route both call sites through the shared helper IN THE SAME CHANGE, so the widening is the visible decision rather than a side effect.
- **Roborock room migration** — Room *creation* now takes brand-correct defaults. Rooms created before that still carry the old values. Stored user data, so repairing it is a product decision.  
  _Revisit when:_ A user report where the old defaults cause a real symptom. Then the fix is to SURFACE the mismatch (show that a room's settings predate the brand defaults, offer a one-click reset), never to rewrite silently.

---

## Suggested repair order

Ordered by (verified) × (blast radius) × (cost), not by severity label.

1. **C5** — 2 lines, verified, and it closes a gap introduced by an earlier fix in this campaign. Cheapest real win.
2. **C20** — verified CRITICAL, and the most dangerous shape found: silent data loss with a DELAYED fuse. A reload (which `setup_add_vacuum` schedules itself) leaves the old manager's timers alive; minutes later one fires and reverts the store wholesale. The UI keeps showing the lost data until the next restart.
3. **C23** — verified by execution, and cheap. The confidence chip is inverted at the top: your best-learned rooms render RED and the green tier needs literally zero variance. Two constants and a fall-through.
4. **C19** — verified CRITICAL. A blank `enabled_room_ids:` in an automation destroys a map's entire room configuration, silently, and the docs promise the opposite. Public API, trivially reachable, no undo.
5. **C15** — verified CRITICAL, and the cheapest of the criticals. A blocker sensor going `unavailable` currently aborts a live run. One availability check in `_room_rule_matches`.
6. **C7** — verified CRITICAL. Slug uniqueness at discovery: wrong physical room, plus silent replacement of the second room's stored settings. Correct the docstring's false claim at the same time.
7. **C1** — verified CRITICAL seam. The other wrong-physical-room path.
8. **C11** — verified CRITICAL. Give the Eufy in-memory source a vacuum identity. Latent on a single-robot install, but a second Eufy robot gets the first one's map, rooms, pose and render raster — so a room tap cleans the wrong room. The fix pattern already exists on the Roborock side.
9. **C10** — small, and a third route to the same wrong-room outcome: a failed refresh is indistinguishable from a successful one, so stale ids reach the wire.
10. **C9** — destructive writes. An empty selection wiping a map's stored rooms is one bad call away.
11. **C3** — a `try/finally` so one transient failure stops bricking every subsequent run.
12. **C8** — decide reconciliation's trigger. The machinery is built and nothing calls it. This is the *root* of C1 and C7 rather than another instance of them.
13. **C13** — the sticky-hold `stale` flag has no consumer, so a frozen pose is served as present. Cheap, and it makes a whole class of phantom-room report visible.
14. **C14** — call the tracker's `end_job` from every terminal path, not only a successful finalize.
15. **C12** — pose frame mismatch. Needs the memory-vs-storage frame question settled first.
16. **C2** — cancel correctness. Needs care around the await boundaries.
17. **C6** — user-visible on every mop room, but it changes resolution precedence, so test hard.
18. **C4** — per-phase attribution. Touches the shape of learning data.
19. Remaining HIGHs, then MEDIUMs. LOWs only when the file is already open for another reason.

## Calibration

Measured cost per audit, for scoping future runs. **Complete** — every run in the campaign,
plus the cheap methods. Audits #1-#6 were scoped by CONTRACT ("the exactly-once finalize
lifecycle") rather than by file list, so LOC is not meaningful for them; #7 onward were
file-scoped. All measured on `claude-opus-5[1m]` — rescale for a different model.

| Audit | Subsystem | LOC | Tokens | Wall |
|---|---|---|---|---|
| #1 | active-job lifecycle + exactly-once finalize *(calibration pass)* | — | 1.86M | 41 min |
| #2 | learning persistence | — | 1.77M | 32.6 min |
| #3 | external-run ingestion | — | 1.82M | 31.9 min |
| #4 | adapter contract | — | 1.84M | 37.8 min |
| #5 | error tracker | — | 1.53M | 30.2 min |
| #6 | card / frontend (6 by feature vertical) | — | 2.01M | 36.5 min |
| *sweep* | forgotten-sibling sweep (**4 agents**; orchestrator did the mechanical discovery) | — | **0.76M** | 23.5 min |
| #7 | dispatch + queue | 1,515 | 1.58M | 23 min |
| #8 | profiles + planning | 3,677 | 1.95M *(includes a re-verify forced by a harness bug)* | 40 min |
| #9 | jobs / run execution | 3,914 | 1.50M | 23 min |
| #10 | rooms / identity | 2,531 | 1.07M | 21 min |
| #11 | map source + tracker (scoped) | 3,126 | 1.39M | 27 min |
| #12 | listeners (input layer) | 2,000 | 1.22M | 22 min |
| #13 | services (public API, dual mode) | 2,938 | 1.35M | 23 min |
| #14 | core/manager.py (the hub) | 5,155 | 1.51M | 25 min |
| #15 | integration script (**4+2 agents**) | 853 | **0.76M** | 20 min |
| #16 | learning consumers (5+2 agents) | 3,308 | 1.23M | 24 min |
| #17 | themes/manager.py (**3+2 agents**) | 668 | **0.53M** | 16 min |
| *1 agent* | entity platforms (button/number/switch/select/binary_sensor/room_entities) | 1,075 | **0.18M** | 16 min |
| *1 agent* | sensor leftovers (platform setup + 4 entity modules) | 887 | **0.17M** | 13 min |
| *1 agent* | infrastructure (const/models/entity_helpers/config_flow/…) | 1,169 | **0.19M** | 14 min |
| *direct read ×11* | live_refresh · maps · dock · maintenance · counter_segmentation · debug_capture · diagnostics · onboarding · battery · sensor · setup | 8,709 | **~0.55M total (~50K each)** | — |
| #18 | mapping services (**7+2+1 agents**, incl. meta-verifier) | 3,690 | 1.87M | 37 min |
| *stage B* | verify the 27 targeted-agent findings (**2 agents, no finders**) | — | **0.37M** | 16.5 min |

Cost tracks the **agent shape far more than subsystem size** — one audit covered 2,531 lines
for 1.07M tokens while another covered 1,515 lines for 1.58M. Scope by agent count, not by LOC.

**Finder false-positive rate, from the six runs that recorded it** (candidates -> survived):
57->52, 52->45, 59->49, 44->39, 52->51. So the finder stage runs roughly 5-15% speculative,
and the verifiers earn their ~22% of spend on that alone — before the severity corrections,
which are the larger effect. Audit #6 (frontend) is the instructive outlier: only ONE finding
killed, but 2 CRITICAL->HIGH and 10 HIGH->MEDIUM. A rendered string is easier to prove than a
race, so frontend findings were less speculative but their user impact was more often
overstated. Expect verifiers to shift from killing to re-grading on presentation layers.

**The ladder, measured.** Roughly an order of magnitude separates each rung:

| Method | Shape | Typical cost |
|---|---|---|
| Full audit | 6 finders + 2 verifiers | 1.1–1.6M |
| Scaled audit | 3–5 finders + 2 verifiers | 0.53–1.23M |
| Targeted agent | 1 agent, no verifiers | ~0.18M |
| Direct read | orchestrator, no agents | ~0.05M |

Verify has a **~200k floor that does not shrink with the target**, so an audit has a cost
floor regardless of size — which is why below a few hundred lines a direct read wins. Measured
here: 11 direct reads covered 8,709 lines for ~0.55M, against ~2.5M for equivalent audits.

Caveats: direct-read figures are **upper bounds** — each stretch also carried ledger updates
and commits. Audits #1-#6 predate this table (their findings were applied and left the ledger).
The targeted-agent rows had NO adversarial verification, which is a coverage difference, not
just a cost difference.

