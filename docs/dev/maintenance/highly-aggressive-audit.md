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

**95 changes shipped**, all with tests, all deployed.

| | |
|---|---|
| Audits fully applied | #1 lifecycle · #2 learning · #3 external ingestion · #4 adapters · #5 error tracker |
| Partly applied | #6 card (root cause + top of the repair order) |
| #7 onward | **105** of 484 findings applied via 12 landed packets (RP-001, RP-002, RP-003, RP-004, RP-005, RP-006, RP-007, RP-008, RP-009, RP-010, RP-011, RP-012); rest open — see [Open](#open) |

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

---

## Open

**379 findings** — 338 across 12 audits plus 41 from direct reads. **105 more applied** via 12 landed packets (see [Applied](#applied)). 19 open clusters (10 fully applied) + 338 singles.

CRITICAL 7 · HIGH 57 · MEDIUM 141 · LOW 174

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

#### C4. A multi-room phase is recorded as ONE room

- **Seam:** `jobs/phase_runner.py:301`
- **Closes:** A3-REC-1, A3-REC-2, A3-REC-3, DQ-PH-3
- **Defect:** A room_group phase attributes the group's entire cleaning time, area and battery to queue_room_ids[0]. A phased job also never records a completed room, so live progress freezes on the group.
- **Fix:** Attribute per-phase metrics across the phase's rooms, or record the phase as a phase rather than as room[0].

#### C5. The repudiated `started_at and not ended_at` predicate is still live — **verified by hand**

- **Seam:** `jobs/active_job.py:1676,1709`
- **Closes:** A3-REC-4, A4-AJ-2
- **Defect:** SELF-INFLICTED. 0f1e2a6 moved this question onto status because nothing ever writes ended_at, so a finalized job matched forever. Two sample recorders were left behind, and the docstring written in that same commit names both BY NAME as needing the external-inclusive predicate. record_pose_sample:1776 is NOT affected (it has its own status check) -- the finding over-reached on that third site.
- **Fix:** Point record_active_job_sensor_value and record_counter_sample at run_is_in_flight. Roughly 2 lines.

#### C6. Profile round-trip is broken: applying a preset re-labels the room 'custom'

- **Seam:** `profiles/room_profiles.py:435`
- **Closes:** A1-PP-RES-2, A3-PP-CRUD-2, A6-PP-EST-DSP-1
- **Defect:** water_level (and carpet fan_speed) use a DIFFERENT precedence than every sibling field: the floor-type default OVERRIDES the profile. Candidate dicts omit the key so they take the floor default, while real rooms carry it -- so mop profiles fail to match on every floor except tile.
- **Fix:** Make the floor-type default lose to an explicit profile value, or resolve the candidate exactly the way the room is resolved.

#### C7. Slug identity has no uniqueness guarantee, and the docstring claims it does — **verified by hand**

- **Seam:** `rooms/utils.py:35 + rooms/room_discovery.py:254`
- **Closes:** A1-ID-1, A2-REC-2, A1-ID-3
- **Defect:** EXECUTED: 'Bed & Bath'/'Bed and Bath', 'Kids Room'/'Kids_Room', "Cat's Room"/'Cats Room', '"Guest" Room'/'Guest Room' each collapse to ONE slug -- and utils.py:16-18 explicitly claims 'distinct names must yield distinct slugs'. Discovery dedupes on numeric room_id only. On Roborock, slug_to_live_id is first-wins, so the second room's target resolves to the FIRST room's segment id and the robot cleans the wrong physical room WITH NO LOG LINE (the dropped-warning path is not reached because the lookup succeeds). plan_migration's existing_by_slug.setdefault is also first-wins, so the second room's stored settings, grants and rules are overwritten and never reported as dropped.
- **Fix:** Enforce slug uniqueness at discovery with deterministic disambiguation (append the device room_id on collision), and make the collision observable. Reconcile the docstring with whatever the code actually guarantees.

#### C8. Reconciliation never runs -- the divergence detector is never invoked

- **Seam:** `rooms/reconciliation.py`
- **Closes:** A2-REC-1
- **Defect:** compute_reconciliation/plan_migration exist and work, but nothing triggers them: no schedule, no event hook, no UI entry point. This is the ROOT of audit #7's CRITICAL (DQ-DE-1): stored ids and live ids diverge because nothing ever checks that they agree.
- **Fix:** Decide the trigger -- on map-source refresh, on job start, or a periodic check -- and surface the result. The machinery is already built.

#### C9. Destructive room writes with no confirmation or preservation — **1/2 applied**

- **Seam:** `rooms/room_crud.py`
- **Closes:** ~~A3-CRUD-1~~ ✅ RP-005 (`4217c3c`), A3-CRUD-4
- **Defect:** save_managed_rooms unconditionally replaces map_bucket['rooms'], so an empty selection wipes the map's stored rooms. remove_map leaves the map's saved run-profile library, queue state and onboarding orphaned rather than removing or migrating them.
- **Fix:** Guard the wholesale replace against an empty/degenerate discovery, and make remove_map account for every structure keyed on that map_id.

#### C10. async_refresh_room_source returns None on success AND on every failure path — **1/1 applied**

- **Seam:** `rooms/source_refresh.py`
- **Closes:** ~~A4-SRC-1~~ ✅ RP-007 (`4c42482`)
- **Defect:** Callers cannot distinguish 'refreshed successfully' from 'refresh failed, you are looking at stale cache'. dispatch/manager.py calls this immediately before resolving live segment ids, so a silent failure means stale ids go to the wire -- the same wrong-room outcome as C1, by a different route.
- **Fix:** Return a discriminable result and have dispatch refuse (or warn loudly) when the refresh did not actually succeed.

#### C11. The Eufy in-memory map source has NO vacuum identity — **verified by hand**

- **Seam:** `mapping/map_source_runtime.py:839 (eufy_inmem_candidates)`
- **Closes:** A1-LC-1, A3-EXT-1, A4-RB-2
- **Defect:** VERIFIED: eufy_inmem_candidates(hass, source_cfg) takes no vacuum_entity_id, no serial, no device_id, and appends the WHOLE hass.data['robovac_mqtt'] bucket first. The bounded BFS matches on attribute presence only, so coordinators[0] wins for EVERY vacuum. Six coordinator call sites inherit it (361/397/461/550/645/689): static rooms, live pose, the render raster the card draws, and the raster zone_membership consumes. The per-vacuum _mem_rooms_cache does not help -- its version is a hash of that same wrong raster, so it is self-consistently wrong. Only bites a MULTI-Eufy install; this install has one robot today.
- **Fix:** Pass vacuum_entity_id through and select the coordinator by serial/device_id. The pattern is already there on the other brand: roborock_candidates accepts image_entity_id and puts the per-vacuum entity object FIRST. Forgotten override sibling, fourth instance. The storage fallback is correctly per-serial, which proves per-device identity was the intent.

#### C12. Live pose is projected through the WRONG coordinate frame

- **Seam:** `mapping/map_source_coordinator.py (_load_live_pose_geom / _apply_inmem_pose_to_result)`
- **Closes:** A2-GEO-1, A5-POSE-1
- **Defect:** A memory-frame robot pixel is normalized and room-looked-up against .storage-frame geometry. The two frames are not guaranteed equal, so the robot dot and the derived current_room can both be wrong while reporting present:True.
- **Fix:** Normalize the pose against the frame it came from, or refuse to derive current_room when the frames disagree.

#### C13. The sticky-hold `stale` flag is written and never read

- **Seam:** `mapping/map_source_coordinator.py:126`
- **Closes:** A1-LC-2, A5-POSE-2
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

#### C16. dock_events records a NEW cycle on first sighting or on an availability blip

- **Seam:** `listeners/dock_events.py:74`
- **Closes:** A1-REG-1, A6-GUARD-3
- **Defect:** The only dedupe is new_val == old_val, with old_val = '' when old_state is None. So an entity first appearing (HA restart mid-cycle), unknown->drying, and unavailable->washing all read as a new cycle. record_dock_event overwrites the last-* timestamp BEFORE the debounce check, and the Eufy adapter declares debounce_seconds for last_mop_wash ONLY -- so dry-start and dust-empty have no suppression at all. An X10 dry cycle runs 2-4 hours, so the window is large and daily. The sibling listener discovery.py:127 DOES filter exactly this class; dock_events is the one of eight that writes durable counters from a raw state arrival and has no such filter.
- **Fix:** Require the previous value to be a real non-trigger dock state before recording a cycle. Move the timestamp write inside the debounce guard.

#### C17. Reactive listeners spawn unbounded concurrent work with no in-flight guard — **3/4 applied**

- **Seam:** `listeners/path_blockers.py + pause_timeout.py + lifecycle.py + pose_sampler.py`
- **Closes:** A6-GUARD-2, ~~A6-GUARD-4~~ ✅ RP-011 (`365f90b`), ~~A2-LIFE-2~~ ✅ RP-003 (`76d92fc`), ~~A4-POSE-2~~ ✅ RP-012 (`7269020`)
- **Defect:** path_blockers spawns a _process task per event with no coalescing, so a bouncing sensor stacks them; the 1-minute reap ticker has no in-flight guard while each reap blocks; the pose timer is fire-and-forget so a slow tick overlaps the next; and _process tasks are untracked, so remove() drops the subscription but not the work already in flight.
- **Fix:** One in-flight guard / coalescing pattern, applied to all four. This is the same question four times.

#### C18. The listener layer is a THIRD answer to 'is a job active' — **1/3 applied**

- **Seam:** `listeners/_common.py:110 (is_job_active)`
- **Closes:** ~~A3-COMMON-1~~ ✅ RP-008 (`8d244dc`), A3-COMMON-6, A5-METRICS-1
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

#### C23. The confidence tier system is INVERTED at the top, and green is unreachable — **verified by hand**

- **Seam:** `learning/estimator.py:117 (_BREAKPOINTS) + :165 (_breakpoint_for_score)`
- **Closes:** A1-EST-1, A1-EST-5
- **Defect:** VERIFIED BY EXECUTION. _LEARNED_BASE (0.55) + _SAMPLE_BONUS_MAX (0.25) = 0.80, which is EXACTLY high.min_score -- so HIGH/green requires a perfect score, i.e. minutes_stddev exactly 0, which real timing data never has. And medium.max_score is 0.79 while high.min_score is 0.80, so the band (0.79, 0.80) matches no bucket; _breakpoint_for_score falls through to _BREAKPOINTS[-1], which is LOW/error -- the BOTTOM of the table, not the nearest tier. Sweep at 12 samples / avg 10 min: stddev 0.05 -> 0.7975 -> RED; stddev 0.15 -> 0.7925 -> RED; stddev 0.20 -> 0.7900 -> AMBER. A room consistent to 3 seconds shows red while a room consistent to 12 seconds shows amber. ui_variant reaches the card verbatim (src/renderers/learning.js:534, rooms.js:742/1196) and job confidence is min(room scores), so one such room drags the whole job estimate red.
- **Fix:** Close the band (make the tiers contiguous, or use a one-sided descending test), and make the fall-through return the nearest tier rather than the last entry. Separately decide whether HIGH should be reachable at all -- as written it needs zero variance.

#### C24. External runs contribute battery=0.0 and the estimator consumes it as a real measurement

- **Seam:** `learning/estimator.py:844 + learning/external_ingest.py:1056`
- **Closes:** A1-EST-2
- **Defect:** THE HYPOTHESIS THIS AUDIT WAS BUILT ON, CONFIRMED. build_graduated_job constructs the completed-job record with NO battery block at all (grep for 'battery' in external_ingest.py returns zero hits), yet outcome.status is 'completed' and used_for_learning is True, so is_learning_job admits it. The rebuilder reads job.get('battery',{}).get('used') -> 0.0 and accumulates that into the SAME room_stats bucket as dispatched runs. _safe_float only substitutes a default for None/''/unknown/unavailable -- 0.0 is a valid float and passes straight through. There is no battery_sample_count and no source marker, so 'learned 0%' is indistinguishable from 'no battery data'. With an all-external archive avg_battery_used is exactly 0.0: the card asserts the job costs ZERO battery and battery_warning is False at ANY charge level. And confidence_score is computed from TIMING samples only, so the number carries no warning.
- **Fix:** Either exclude records with no battery block from the battery aggregate, or carry a battery_sample_count so a zero-sample bucket is distinguishable from a measured zero.

#### C25. The incomplete-run log misreports which rooms were missed

- **Seam:** `learning/history_store.py (incomplete-run family)`
- **Closes:** A4-STATE-1, A4-STATE-2, A4-STATE-4, A2-ACC-4
- **Defect:** The final room of EVERY non-completed run is recorded as missed; clear_incomplete_run's docstring claims '(full clean)' but ANY completion clears it; missed_room_ids survive a re-segment and a map switch, so they can name rooms that no longer exist or now mean something else; and a skipped room holds 'current' for the rest of the run so it can never be resolved.
- **Fix:** One pass over the incomplete-run lifecycle: who writes it, what clears it, and whether its room ids are still valid at read time.

#### C26. Learning services destroy or misreport, and say success either way — **2/4 applied**

- **Seam:** `learning/services.py`
- **Closes:** A5-SVC-1, ~~A5-SVC-2~~ ✅ RP-001 (`3ddcc1c`), A5-SVC-3, ~~A5-SVC-6~~ ✅ RP-006 (`e598e3e`)
- **Defect:** The 22 registrations here were NOT covered by audit #13's services sweep, and they have the same shape: exclude/restore_learning_job report 'stats rebuilt' without rebuilding; finalize_learning_job fires the job-finished event with a FABRICATED payload; retry_missed_rooms permanently destroys the map's room-enable selection; rebuild_learning_stats blanks accuracy_stats before replaying, so a failure partway leaves it empty.
- **Fix:** Same treatment as C19/C26's siblings: make the destructive ones confirm or be reversible, and make every response honest about what actually happened.

#### C27. overwrite_theme resolves against the ACTIVE theme, never the target it names — **verified by hand**

- **Seam:** `themes/manager.py:303`
- **Closes:** A1-CRUD-1, A1-CRUD-2, A1-CRUD-4
- **Defect:** VERIFIED at source and REPRODUCED by executing the module. overwrite_theme builds `resolved` from vac['active_theme_id'] + the working draft; `existing = library[theme_id]` is fetched but used ONLY to preserve name/source/tags/author. So calling it on any theme that is not the active one replaces that theme's palette with a CLONE of the active one, and line 326 then silently repoints the vacuum onto it. With no active theme the target's palette becomes {} outright. Both return ok:True and services.py persists. The metadata-preservation loop is what makes it silent -- the entry keeps its name and author, so it looks intact. The docstring claims it writes 'the vacuum's working draft'; it writes active+draft and works with an empty draft. The CARD masks it (bindings/theme.js only calls overwriteTheme inside `if (state.activeThemeId)` and passes that same id), so it is service-only reachable -- which is why the verifiers held it at MEDIUM. Also lets a BUNDLED theme's palette be permanently replaced (CRUD-4).
- **Fix:** Resolve against the TARGET entry, or refuse when theme_id != active_theme_id. Decide which the docstring meant and make the code and the doc agree.

#### C28. Bundled themes are protected from neither delete nor overwrite — **verified by hand**

- **Seam:** `themes/manager.py delete_theme/overwrite_theme + preloaded.ensure_preloaded_theme_library`
- **Closes:** A1-CRUD-3, A1-CRUD-4
- **Defect:** delete_theme has no source=='core' guard, so a bundled theme can be deleted -- and audit #14's A1-INIT-3 showed the startup re-seed resurrects it, so the deletion is neither prevented nor durable ('gone until restart'). overwrite_theme can replace a bundled theme's palette PERMANENTLY, because the re-seed only restores absent entries, not modified ones. The discriminator already exists and is trustworthy: preloaded.py stamps source='core', _import_scoped allowlists {community,generated,manual} so an import cannot claim it, and save_theme_as_new hardcodes 'manual'.
- **Fix:** Refuse both operations for source=='core'. Chris's spec: bundled themes are system inventory, not ordinary library entries -- protecting them removes the 'deleted until restart' behaviour rather than trying to make deletion durable.

#### C29. delete_theme leaves the working draft orphaned on a base that no longer exists — **verified by hand**

- **Seam:** `themes/manager.py:394`
- **Closes:** A1-CRUD-5, A2-DRAFT-1
- **Defect:** delete_theme nulls active_theme_id for every affected vacuum (that guard DOES exist) but line 394 only RE-NORMALIZES the working draft -- it does not empty it, and leaves draft_dirty untouched. set_active_theme twenty lines later does exactly the right thing (_empty_theme_draft + draft_dirty=False). So deleting the theme you are editing leaves a live draft of overrides authored against a base that is gone. Sibling divergence: two adjacent methods, one clears the draft, one does not.
- **Fix:** Per Chris's spec: treat deletion as an atomic destructive transition -- resolve the fallback target FIRST (default_theme_id is nulled at :388 before the vacuum walk at :391, so the chain must run before that), clear working_draft, set draft_dirty=False, set active_theme_id, persist once, notify once. Note delete_theme currently does not persist at all.

### Singles

<details><summary><strong>CRITICAL</strong> (2)</summary>

- **A3-EXT-2** `mapping/map_source_runtime.py:966` · eufy  
  Content version hashes ONLY the room raster, but the cache it gates holds the grid geometry the fork mutates independently  
  During and after any run in which the map grows, or across any session where Eufy re-localizes its coordinate origin (a documented behaviour of this device), the robot dot lands metres from where the robot is, the room b
- **A4-PP-RP-2** `profiles/manager.py:1086` · both  
  overwrite_run_profile unconditionally destroys a saved profile's step sequence; save_run_profile preserves it — same "snapshot the current run" contract, opposite behaviour  
  A saved run "Downstairs, wait 30 min for the floor to dry, then Upstairs" (or any rooms->zone / multi-group run) loses its entire sequence the first time the user opens its editor and saves — e.g. just to fix a typo in t

</details>

<details><summary><strong>HIGH</strong> (38)</summary>

- **A4-START-1** `core/manager.py:2863` · both  
  get_start_status validates PHASE 0's room count as if it were the whole job — a stepped run whose first phase is a zone is refused with a false "invalid payload" error  
  A run profile like "clean the entryway zone, then the kitchen", or any rooms+zone queue whose first room happens to be blocked by a room rule that moment, refuses to start and reports "Room-clean payload is missing or in
- **DQ-ZONE-1** `dispatch/manager.py:234` · eufy  
  Zone-clean pass count is never clamped on the Eufy branch — the clamp lives inside the device_mm branch Eufy never enters  
  An automation / YAML / script call `eufy_vacuum.start_zone_clean` (or `clean_saved_zone`/`clean_saved_zones`) with clean_times above the device ceiling reaches the robot unmodified: the value lands in the SelectZonesClea
- **A6-VAC-1** `dock/manager.py:154` · eufy  
  Dock-action gate is blind to app-started (external) runs — every dock action reports "Ready" and fires while the robot is mid-run at the dock  
  The user starts a clean from the Eufy app. The robot returns to the dock to recharge ("Charging (Resume)") or wash the pad mid-run. The card's Base Station tab shows Wash Mop / Dry Mop / Empty Dust as Ready. Tapping Dry
- **A2-CAN-2** `jobs/active_job.py:2255` · both  
  Cancelling a sequenced run reports the WRONG missed rooms — per-phase reset of queue_room_ids/completed_room_ids feeds the incomplete-run log and trouble-rooms counters  
  After cancelling a stepped run the card's incomplete-run banner and the EVENT_RUN_INCOMPLETE automation payload name the wrong rooms — under-reporting (rooms silently never retried by a `retry_missed_rooms` automation) o
- **A2-ACC-2** `learning/estimator.py:1122` · both  
  reanchor_timeline ignores its own reanchor_at parameter — every ETA is anchored to job start plus the sum of room durations, so all wall-clock dead time is invisible and "Done at" times slide into the past  
  Concrete: 3 rooms at 10 min each, overhead 7.02, started 12:00. R1 completes at 12:10 with actual_duration 10.0. The user pauses the vacuum at 12:10 and resumes at 12:40. At 12:45 the card refreshes and reanchors with co
- **A3-IO-1** `learning/history_store.py:989` · both  
  An empty room_timing on a charge/wait/zone phase is read as "capture failed", so every stepped run with a break or a zone is stripped of its accurate per-room timings and learns an even split instead  
  Using the flagship charge-break step (vac -> charge to X% -> mop) or queueing a saved zone alongside rooms silently downgrades that run's learning from exact per-room capture to an even time split, and contributes zero a
- **DQ-PH-1** `learning/history_store.py:996` · both  
  Every break/zone phase flips transit_capture_valid to False, so a stepped run's per-room learning silently degrades to an even split of the run's wall time — charge/wait dock time included  
  Every run that uses the charge_wait / wait / zone step feature writes corrupted per-room baselines: the exact per-room area and wall-minutes that were captured are thrown away, and each room instead learns an even share
- **A4-RB-1** `mapping/map_source_runtime.py:373` · roborock _(finder said CRITICAL; verifier corrected)_  
  Roborock MapData lookup never binds the found map to the requested map_id — a multi-map (multi-floor) device converts drawn zones in the wrong floor's coordinate frame  
  On a Roborock with more than one saved map (a two-storey home — the exact case the adapter's `active_map = select.{id}_selected_map` block exists for), the user draws a zone box on the upstairs map and the robot vacuums
- **A1-SERVIC-1** `mapping/mapping_services.py:450` · Both, but the rename trigger is Roborock-specific (map_id = user-editable map NAME from the select entity state). Eufy's numeric map ids make the accidental rename case unlikely; the empty/sentinel map_id case affects both.  
  No mapping write service can tell "this map exists" from "this map does not" — every schema takes a free-form map_id and every handler mints the bucket, so an edit against a non-existent map is persisted to a phantom bucket and reported as saved  
  Every geometry edit the user makes after a vendor-side map rename silently lands on a different bucket than the one holding their previous work, and the previous work becomes permanently unreachable — the write reports s
- **A2-POLYGO-3** `mapping/mapping_services.py:762` · Both (get_map_segments serves CV and custom scopes identically; on Roborock it bites in custom mode via the active layout's stores)  
  `_apply_segment_adjustments` returns the PERSISTED segment dicts by reference, and its caller writes `room_id` into them - baking a cleared/moved room link permanently into .storage and breaking the documented 1:1 invariant  
  src/state/map.js:1690-1698 `roomIdForSegment` reads `seg.room_id` from the backend payload and comments 'Backend payload is canonical when present' - so the stale value fully drives the card. After clearing a link the ca
- **A3-IMAGE--1** `mapping/mapping_services.py:1174` · Both. Eufy (eufy_cv_v1) is where re-analysis actually reshuffles ids; Roborock inherits the same read-time enrichment for any image_segments it holds.  
  Re-analysis rebinds the user's room links and manual segment adjustments onto positionally-reassigned segment ids  
  The map overlay silently mislabels rooms after any re-analysis in which blob ordering shifts, and the mislabel is actuating, not cosmetic: tapping a segment polygon calls toggleRoomEnabled for the LINKED room (src/bindin
- **A4-CUSTOM-1** `mapping/mapping_services.py:1667` · Both (Eufy + Roborock) — custom layouts are brand-independent map-bucket state.  
  set_custom_segments is a REPLACE-ALL write that cannot name its target layout — it lands on whatever layout is active at call time, destroying another layout's authored geometry  
  Silent, unrecoverable loss of hand-authored map geometry plus its room links. The layout the user was editing is left untouched and the one they were not looking at is destroyed; the service returns {'saved': True, 'segm
- **A6-ZONE-C-3** `mapping/mapping_services.py:2490` · Both.  
  The `map_version` re-map invalidation the design doc specifies as the zone's safety key does not exist anywhere in the codebase  
  Every saved zone on a re-mapped floor silently points at the wrong physical spot, and the design's own stated defence against exactly this was never built. This is the direct failure of "survives a re-import": the edit d
- **A6-ZONE-C-1** `mapping/mapping_services.py:2608` · Both. Roborock is more exposed: map_id is the vendor map NAME read off a select entity that goes `unavailable` whenever the upstream integration reloads, and the wrong-map projection can land on a different FLOOR.  
  Saved-zone clean dispatches to the device when the active-map signal is blank — the "active map only" guard is permissive, not a refusal  
  The vacuum cleans a physically different area from the one the user named and tapped, with no error and no way to tell from the response (it returns {cleaned: true}). Requires the active-map entity to be blank (integrati
- **A2-POLYGO-2** `mapping/segment_primitives.py:267` · Both (custom layouts are brand-agnostic; worst for Roborock, whose segmenter_engine is 'noop_fallback' so custom layouts are its only segment store)  
  `rasterize_primitives` returns the same `[]` for 'numpy/Pillow missing' as for 'degenerate shape', so set_custom_segments silently wipes the layout and reports saved:true  
  Destructive, silent, unrecoverable loss of an entire authored map layout on exactly the installs the CV-availability gate exists to protect. The card's comment 'Live/custom/manual paths don't need it' is a CLAIM and it i
- **A2-POLYGO-1** `mapping/segment_primitives.py:277` · Both (custom layouts are brand-agnostic; Roborock declares segmenter_engine='noop_fallback' so the custom compose path is its ONLY segment source, making this its primary path)  
  Authored custom segments grow ~1 working-pixel toward +X/+Y on every save, and the growth compounds without bound across save/reload cycles  
  Every authored room polygon is stored 0.3% of the map larger than drawn from the very first save. `set_custom_segments` is REPLACE-ALL, so once the compose draft has been reloaded from storage (which happens on any map/l
- **A5-PP-RP-1** `planning/run_plan.py:1352` · both  
  A multi-room_group plan with no charge/wait/zone is silently flattened to ONE atomic dispatch — the card routes it as sequenced  
  The canonical two-pass profile — "vacuum every room, then mop the kitchen and bath" — is saved, displayed as a multi-step sequenced run in the card's stepped preview, and then executed as ONE flat clean: rooms that appea
- **A5-PP-RP-3** `planning/run_plan.py:1379` · roborock  
  _build_steps_phases can return an empty list; `phases[0]` then raises IndexError inside get_start_status, killing the whole dashboard snapshot (Roborock)  
  For a Roborock user, turning on a blocker (e.g. the sensor behind a "don't clean while the baby naps" rule) while a charge/wait break sits in the queue makes the integration's dashboard snapshot service raise instead of
- **A6-PP-EST-BLK-1** `planning/run_plan.py:1615` · both _(finder said CRITICAL; verifier corrected)_  
  Mid-job path-block report walks reachability over the QUEUE only, so any queued room whose access parent is not in the queue is reported blocked — and can cancel the job  
  Running a subset of rooms (the normal case) plus any door/motion blocker rule: the first time that blocker entity changes state mid-run, rooms that the start plan judged perfectly accessible are declared blocked. With ca
- **A5-AG-1** `planning/run_plan.py:1615` · both  
  Mid-run reachability is queue-scoped while preflight is graph-scoped — a run that omits the dock room reports EVERY remaining room as access_blocked and can cancel the job  
  A perfectly valid access graph plus a normal partial run (user cleans the bedroom, not the entryway the dock sits in) turns any watched blocker entity's state change into a spurious 'path blocked' verdict on every unfini
- **DQ-PAY-1** `profiles/manager.py:225` · roborock  
  Applying a built-in room profile to a Roborock room writes EUFY vocabulary onto the room; the fresh room_defaults fix covers creation only  
  On a Roborock, choosing any built-in room profile (e.g. "Vacuum Only Deep") for a room stores an unusable capitalized suction value. The room then cleans at whatever fan speed the device happened to be left on — the user
- **A3-PP-CRUD-3** `profiles/manager.py:587` · both  
  rename_room_profile changes the store key and silently orphans every room referencing it — no migration, no reference check, no warning  
  A user renames a custom room profile from "Kitchen Deep" to "Kitchen Deep Clean" and every OTHER room using it loses its profile association. Those rooms' chip rows show nothing selected (strict `===` against the library
- **A3-PP-CRUD-1** `profiles/manager.py:631` · roborock  
  apply_room_profile writes Eufy vocabulary onto Roborock rooms — the catalog it resolves is inert  
  On Roborock, selecting any room profile from the card silently poisons the room. `jobs/active_job.py:1385-1393` filters `per_room_live_settings` values against `fan_speed_options` = {gentle,quiet,balanced,turbo,max} with
- **A4-PP-RP-1** `profiles/manager.py:1232` · both  
  A stepped run profile silently discards the per-room settings it was saved with; apply falls back to whatever the rooms happen to be set to now  
  User composes "Nightly": Kitchen + Bath on mop/High water, charge to 90%, then Bedrooms on vacuum — and saves it. Days later they switch the Kitchen to vacuum-only for a quick pass. Pressing the "Run Nightly" button (or
- **A4-PP-RP-4** `profiles/manager.py:1244` · both  
  apply_run_profile leaves no backend record that the applied profile is stepped, so a plain Start runs it flat — or inherits the map's unrelated leftover breaks  
  User presses "Apply" on a stepped profile, walks away, comes back to a reloaded dashboard (or starts it from a second tab / a phone), presses Start — and the run silently loses its structure: the charge-to-90% break neve
- **A4-PP-RP-3** `profiles/manager.py:1283` · both  
  start_run_profile mutates and persists every room's selection and settings BEFORE the start is allowed, and never reverts when the start refuses  
  The user has a hand-built queue selected (say three rooms with tuned fan/water) and presses a saved-run-profile dashboard button while the vacuum is still finishing a job, or while enough rooms are path-blocked to trigge
- **A2-PP-CAP-1** `profiles/room_profiles.py:560` · roborock  
  apply_room_profile_to_config's `catalog` brand-safety parameter is structurally unreachable on every production call — the guard exists, the test passes, and the code path can never take it  
  On a Roborock, applying ANY room profile from the card writes Eufy suction vocabulary ("Standard"/"Max") into the room. At dispatch, jobs/active_job.py:1385-1393 filters the per-room live fan call against `fan_speed_opti
- **DQ-PAY-2** `queue/queue_engine.py:303` · both  
  A mop room on a granite or concrete floor resolves water_level to the empty string and that empty string is written verbatim to the wire  
  A room the user configured to mop, on a granite or concrete floor, is dispatched to the Eufy with an empty water-level string — the robot either rejects the room_clean payload (the whole run silently fails to start) or m
- **DQ-PH-2** `queue/queue_engine.py:467` · both  
  advance_active_job_phase resets completed_room_ids/completed_rooms and no code path ever refills them for a phased job, so an abnormally-ended sequenced run reports every room as missed  
  Cancel a vac→charge→mop run (or a strict-order Roborock run) after 4 of 5 rooms are done and the 'Incomplete run' banner claims all 5 rooms were missed. Worse, the chronic-trouble counter increments miss_count for the 4
- **A3-CRUD-3** `rooms/room_crud.py:279` · both  
  save_managed_rooms auto-confirms floor type for every room it writes, permanently satisfying the onboarding_required start gate with the guessed value "hardwood"  
  The gate whose entire purpose is to force the user to declare carpet vs hardwood before the first clean is satisfied by a guess, on the very first import, for rooms the user has not looked at. A carpeted room reads as us
- **A2-REC-8** `rooms/room_manager.py:64` · both  
  The reachable room writer (save_managed_rooms/build_managed_rooms) carries settings by numeric id only, so a renumber stamps one room's floor type and access grants onto a different physical room  
  After a re-segment the robot runs the wrong room's settings on the wrong physical room — carpet/mop decisions inverted (mopping a carpeted room) and reachability grants pointing at the wrong neighbours, with no error and
- **A3-CRUD-2** `rooms/room_manager.py:64` · both  
  build_managed_rooms matches stored rooms by numeric id while room identity is the slug — a re-save after a re-segment transplants the previous occupant's access grants, rules and dock flag onto a different physical room and erases the reconciliation evidence  
  After any re-segment followed by the ordinary rescan-and-save, rooms silently carry the wrong configuration: the wrong room is flagged as the dock room, access grants point through rooms that are no longer adjacent (so r
- **SN-1** `sensor/__init__.py:98` · both · `direct read`  
  A managed vacuum with no imported map gets ZERO per-vacuum sensors, and importing a map never creates them  
  VERIFIED AT SOURCE. The per-vacuum loop is `maps = manager.data.get('maps', {}); for vacuum_entity_id in maps.keys()`, and EVERY per-vacuum sensor is built inside it: onboarding, theme, dock events, profiles, map overlay
- **A4-SETUP-2** `services/adapter_config.py:67` · both _(finder said CRITICAL; verifier corrected)_  
  save_adapter_config accepts a two-key config and registers it OVER the live code adapter — every omitted block silently resolves to Eufy behaviour on a Roborock  
  A Roborock is driven with Eufy vocabulary and Eufy learning engines from the moment the call returns until the next reload: wrong fan/water strings sent to the robot, room boundaries learned from a counter signal Roboroc
- **A2-JOB-3** `services/job_control.py:238` · both  
  clear_active_job destroys a running job's record unconditionally and returns nothing — no status precondition, no supports_response, immediate persist  
  A user or automation clearing what they believe is a stale job while the robot is actually mid-run permanently loses that run's learning data — the run is never finalized, per-room durations are gone, and the incomplete-
- **A2-JOB-1** `services/job_control.py:322` · both  
  start_selected_rooms discards every refusal — no supports_response, no exception, DEBUG log only; docs promise a response it cannot return  
  An automation that calls `eufy_vacuum.start_selected_rooms` at 09:00 gets a green checkmark whether the robot started or was refused for any of eleven reasons. The house is not cleaned, no error, no notification, nothing
- **A6-DIAG-2** `services/maintenance.py:94` · both  
  set_maintenance_interval accepts ANY component string, persists it, and returns saved:true — its sibling reset_maintenance raises ServiceValidationError for exactly that input  
  An automation that copies a working Eufy call to a Roborock (or just typos the component) gets `{"saved": true, "component": "rolling_brush", "interval_hours": 240.0}` back, no error and no log warning, while the interva
- **A4-SETUP-6** `services/setup.py:243` · both  
  setup_reject_rooms permanently deletes rooms from EVERY map for the vacuum with no map scoping, no protection gate, no confirmation and no way back  
  A YAML/automation caller, or a user clicking Reject on a room the drift panel surfaced, silently loses that room's configuration on maps they were not looking at. Room entities disappear, run profiles and queues referenc

</details>

<details><summary><strong>MEDIUM</strong> (127)</summary>

- **EP-1** `button.py:200` · both · `direct read`  
  The maintenance reset button discards a documented failure result and reports success  
  VERIFIED. async_press calls reset_maintenance(), throws the return value away, and unconditionally awaits async_save(). reset_maintenance is a result-returning API with three documented failure exits -- {'reset': False,
- **A1-INIT-3** `core/manager.py:347` · both _(finder said HIGH; verifier corrected)_  
  Startup re-seed of the bundled theme library resurrects themes the user deleted, and re-points default_theme_id  
  A user who curates the theme library — deleting the bundled themes they do not want, with a confirm dialog implying it stuck — finds all of them back in the picker after the next HA restart, silently and with no error. I
- **A6-VAC-3** `core/manager.py:1126` · eufy  
  refresh_vacuum_capabilities does NOT reproduce startup's detect_capabilities inputs — it silently drops the dock-button entity candidates, contradicting the comment above it  
  On an Eufy model outside the x10/x8 hint families that nevertheless exposes wash/dry/empty dock buttons, running the `eufy_vacuum.get_vacuum_capabilities` service (schema default refresh=True, and it async_save()s the re
- **A6-AGX-2** `core/manager.py:1374` · both _(finder said HIGH; verifier corrected)_  
  The structural gate on every per-room edit is absolute, not a delta: one stored graph violation rejects unrelated edits (fan speed, enable, color) with "The requested access links would make the graph invalid."  
  After a Roborock re-segment + migrate, the user can no longer change ANY room setting on that map — changing a room's fan speed or disabling a room fails with an error claiming they requested illegal access links, which
- **A3-SNAP-2** `core/manager.py:3914` · both  
  get_dashboard_snapshot composes get_job_progress_snapshot TWICE, so job_progress and job_control in the same payload can describe different rooms — and every side effect in the progress composer fires twice per card poll  
  During a multi-room run the card can render a timeline that highlights room B as in-progress while the status line above it reads "Cleaning C" and C is also drawn as an upcoming room — a self-contradicting view with no e
- **DQ-ACT-6** `core/manager.py:5005` · roborock  
  A pre-call leaves the device in a modified state (and the stashed run steps consumed) when the clean then fails to start  
  A failed start silently reconfigures the robot's global mop intensity and leaves it there. On a mixed-batch start that means water is now OFF for whatever the user does next from the vendor app.
- **DQ-ZONE-2** `dispatch/manager.py:120` · both  
  supports_zone_clean is honored by the card but never consulted by the actuation path  
  A model catalog entry that declares supports_zone_clean: False — the exact 'a model that categorically cannot zone-clean had no way to say so' case the capability was added for — still gets a zone_clean/app_zoned_clean s
- **DQ-PAY-4** `dispatch/manager.py:182` · eufy  
  Zone-clean repeat cap defaults to 3 for Eufy while the framework's own room-clean cap for Eufy is 2, and the service schema has no upper bound  
  An Eufy zone clean called with clean_times=3 (or 10) dispatches that raw value to a device the framework itself documents as capping at 2 passes. The user draws a box, presses clean, and either gets a silently rejected c
- **DQ-ZONE-3** `dispatch/manager.py:203` · future_brand_only  
  Per-zone SIZE bounds are enforced by coordinate-space branch, not by which bound the adapter declared — the other combination is silently ignored  
  A brand/model that declares a bound on the axis its coordinate space does not match gets NO enforcement of a limit it explicitly declared: e.g. a device_mm brand (the natural shape for Dreame's vacuum_clean_segment sibli
- **DQ-ZONE-4** `dispatch/manager.py:216` · eufy  
  Eufy per-side bound check is skipped entirely when live-map dims are unreadable, while the mm branch REFUSES on the same missing input  
  An automation-fired or saved-zone clean issued before the map source is warm sends a zone whose side is outside the device's 0.5-10 m range to the robot. The provider builds and sends the quad regardless (it validates ne
- **A6-VAC-2** `dock/manager.py:93` · eufy  
  Dock action returns performed=True / "Dock action sent." when the resolved button entity exists only in the registry (disabled or not loaded) — a silent no-op reported as success  
  A user who has disabled the upstream wash/dry/empty button entity (or whose upstream integration is reloading) sees the dock control offered as Ready, taps it, gets a success response, and the dock does nothing. There is
- **DR-DOCK-1** `dock/manager.py:383` · eufy · `direct read`  
  The dock-event timestamp is written BEFORE the debounce, so a debounced event still corrupts last_*  
  CONFIRMS audit #12's A1-REG-1 from the receiving side. vacuum_events[event_type] = now runs unconditionally at :383; the debounce block at :388-424 gates only the COUNTER. So even where debounce is configured (Eufy decla
- **DR-DOCK-2** `dock/manager.py:383` · both · `direct read`  
  record_dock_event validates nothing; its sibling set_dock_event_count validates the same vocabulary  
  set_dock_event_count checks event_type against counter_map and returns {'updated': False, 'error': ...} for anything unknown. record_dock_event writes vacuum_events[event_type] = now for ANY string. Since event_type come
- **A3-REC-5** `jobs/active_job.py:1721` · both  
  Every counter sample carries battery=None — last_battery_percent is read but never written by anything, so per-room battery attribution is dead on both recording paths  
  Per-room battery drain is never observed on either brand: every completed_job record's room_timings[].battery_delta is null, so the only per-room battery figure available anywhere is the even split total_battery_used / r
- **A6-PRE-2** `jobs/job_monitor.py:268` · both _(finder said HIGH; verifier corrected)_  
  invalid_payload uses phase 0's room count as the whole run's room count — a saved run profile whose first step is a zone is accepted on save but can never start  
  A user saves a run profile like "clean the hallway zone first, then the bedrooms", presses its exposed button, and gets "Room-clean payload is missing or invalid." every time, with rooms visibly selected and a valid queu
- **A1-EST-3** `learning/estimator.py:476` · roborock _(finder said HIGH; verifier corrected)_  
  _find_room_match Pass 1 can NEVER match a Roborock room: it compares the raw "" intensity against the rebuilder's normalized "standard", so every Roborock room takes a permanent -0.15 intensity-mismatch penalty  
  Roborock users see their room and job estimates permanently badged one confidence tier lower — often red "Low" instead of amber "Medium" — no matter how many clean runs they accumulate, because the estimator believes it
- **A1-EST-6** `learning/estimator.py:484` · both  
  _find_room_match relaxed passes return the lexicographically-first bucket and ignore sample_count entirely — a 1-sample bucket beats a 30-sample one  
  Changing one room setting the user has not run before throws away every accumulated sample for that room and answers from whichever adjacent bucket happens to sort first, which is systematically the slowest bucket for in
- **A2-ACC-6** `learning/estimator.py:637` · both  
  The "exact vs allocated" quality flag is recorded and never used — job-average actuals are blended into the same drift mean, permanently capping affected rooms below HIGH confidence while the card promises they will get there  
  Concrete: a 5-room job whose real per-room times are Bathroom 3 / Kitchen 15 / Living 20 / Hall 4 / Den 18 (60 min total) grades every room against actual_per_room = 12.0. Bathroom (estimated 3) records pct_error = |12-3
- **A1-EST-4** `learning/estimator.py:843` · both _(finder said HIGH; verifier corrected)_  
  Estimate consumes avg_minutes with no outlier rejection and no band check, and a single poisoned sample scores MEDIUM confidence because stddev of one sample is 0 by construction  
  A single bad archived run — one multi-room phase that credited the group's whole time to room[0] — moves the displayed job ETA by an order of magnitude, and when it is the room's FIRST run it does so under an amber "Medi
- **A2-ACC-3** `learning/estimator.py:1178` · both _(finder said HIGH; verifier corrected)_  
  Reanchoring drops inter-room transit from remaining rooms while keeping it in overhead — remaining ETAs jump earlier then later (oscillation) and the job ETA inflates by one transit leg per completed room on a run that is exactly on estimate  
  Concrete: 3 rooms × 10 min estimated, learned transit 2.0 min per boundary, overhead 7.02 (startup 1 + transitions 4 + recharge 0.12 + dust 0.9 + return 1), started 12:00. Original timeline: R2 eta 12:22, R3 eta 12:34, j
- **A3-IO-6** `learning/history_store.py:138` · both  
  get_paths derives the archive directory from the entity_id's object_id, so renaming the vacuum entity silently orphans all learned history and the predictor restarts from cold with no notice  
  Renaming the vacuum entity throws away months of learned per-room timings, accuracy stats and trouble-room history from the user's point of view — estimates silently revert to cold-start guesses with no warning, no migra
- **A3-IO-4** `learning/history_store.py:148` · both  
  ensure_dirs runs inside every path getter, so the caches that exist to keep the loop-bound estimate off disk still issue ~32 blocking filesystem syscalls per dashboard snapshot  
  Sustained blocking filesystem I/O on the HA event loop whenever a card is open — measurable UI latency and HA's "Detected blocking call ... by custom integration 'eufy_vacuum'" warnings on a network-mounted config dir, d
- **A4-STATE-3** `learning/history_store.py:301` · both _(finder said HIGH; verifier corrected)_  
  trouble_rooms.json is keyed by raw room_id and scoped per-vacuum, so its counters silently reattach to the wrong physical room after a re-segment or on a second map — the one id-keyed store reconcile-migrate forgets  
  A room that has never been missed is permanently badged "chronically missed, 67%" on its card tile, while the room that actually is missed shows clean — and there is no rebuild, service or UI action that can correct it (
- **A4-STATE-5** `learning/history_store.py:306` · both  
  trouble_rooms is a raw-counter store with no rebuilder, no clear service and a denominator that only advances when the room is queued — the "decays on its own" justification for excluding it from repair does not hold  
  A permanent, unclearable "chronically missed" warning on a room tile, with the only remedy being manual deletion of trouble_rooms.json from the config share — which is exactly the repair path the design note declared unn
- **A3-IO-5** `learning/history_store.py:368` · both  
  get_completed_job_path interpolates an unvalidated job_id into a filesystem path, giving exclude/restore_learning_job an arbitrary *.json overwrite primitive — the exact hole the sibling module already hardened  
  An authenticated HA user or any automation/script/dashboard that can call eufy_vacuum.exclude_learning_job can overwrite or create JSON files anywhere the HA process can write, corrupting unrelated integration data; the
- **A4-STATE-6** `learning/history_store.py:1092` · both  
  build_completed_job_payload's `queue` block prefers the LIVE queue over the job's own — a room switch flipped mid-run makes both the missed-rooms banner and trouble_rooms name a room that was never in the run  
  The missed-rooms banner names a room that was never cleaned in that job — often as an unnamed "Room N" — and omits the room that actually was missed; the phantom room then accrues a permanent chronic-trouble badge.
- **A5-SVC-4** `learning/services.py:486` · both  
  record_estimate_accuracy's schema requires no keys at all; an entry missing map_id/slug writes a permanently unreadable durable record and returns a confident success payload  
  An automation written against the service (which the docs encourage: 03-services.md:1287 "Records estimated-vs-actual minutes per room after a job completes, feeding the estimator's accuracy tracking") but missing map_id
- **A5-SVC-5** `learning/services.py:492` · both  
  record_estimate_accuracy writes accuracy_stats to disk but never invalidates the manager's in-memory accuracy cache, so estimates keep serving the pre-write numbers  
  A caller records real accuracy data, receives a success payload with the new mean, and the card's per-room estimates and confidence scores do not change. Looks like the learning system ignored the data; the user is likel
- **A6-GUARD-5** `listeners/discovery.py:140` · both  
  A discovery pass on the active map is scored against configured rooms across ALL maps, so switching maps makes the other map's rooms accrue "removed" strikes  
  On a multi-floor/multi-map setup, switching maps makes the setup tab report rooms as removed from the vacuum and flips setup_complete out of sync (setup/status.py:193-218), prompting the user to delete room configuration
- **A5-METRICS-2** `listeners/job_metrics.py:172` · both  
  `last_battery_percent` has no writer anywhere in production, so every counter sample carries battery=None and per-room `battery_delta` is permanently null on both dispatch paths  
  Every archived run, on every brand, on both the atomic and strict-order dispatch paths, records `battery_delta: null` for every room. The per-room battery-consumption figure the run archive and diagnostics expose is perm
- **A2-LIFE-3** `listeners/lifecycle.py:169` · eufy  
  The inline mop-wash detector diverges from the dedicated dock_events listener: hard-coded Eufy wash vocabulary as a fallback, and no same-state guard against attribute-only re-triggers  
  `observed_mop_wash_count` on the active job is inflated. That value is written into the completed-job record as `actual_mop_wash_count` and is handed to register_post_job_water_amendment at lifecycle.py:398 as `mop_wash_
- **A3-EXT-4** `mapping/map_source.py:243` · eufy  
  Room-outline offset is the exact NEGATION of the fork renderer's — overlays desync from the live backdrop whenever the outline origin differs from the map origin  
  On any Eufy map whose room-outline origin differs from the map origin (VA's own notes record an X10 map at +105 cells), the card's room tap-regions, room labels, current-room highlight and robot dot sit displaced by twic
- **A1-LC-3** `mapping/map_source_coordinator.py:261` · eufy  
  The storage-path mtime cache early-return omits the `map_id` check its sibling `_commit_result` performs, so map A's geometry is returned as map B's answer with `present: True`  
  For the window between a map switch and the fork's next store write, the card's room bboxes, the map-tap room resolution (`deviceRoomIdAtContentPct`) and the map_overlays sensor all describe the PREVIOUS floor's rooms wh
- **A4-RB-4** `mapping/map_source_runtime.py:511` · roborock _(finder said HIGH; verifier corrected)_  
  rooms_from_mapdata publishes the live segment number as the room's only identity and synthesizes the name, so after a Roborock re-map a tap on room A selects room B  
  After the robot re-maps (an app-initiated re-scan, or the automatic re-map some models do after a large layout change), the live map's room labels and tap targets are shifted onto the wrong rooms with no visible error. T
- **A4-RB-3** `mapping/map_source_runtime.py:743` · roborock _(finder said HIGH; verifier corrected)_  
  roborock_result_from_candidates hard-returns on the first duck-typed MapData match, so one false positive permanently blanks the Roborock map source — and the stale-hold masks it for six hours  
  A change in the HA core roborock integration's in-memory shape (or any provider object that happens to expose `.rooms` and `.image`) silently kills the entire Roborock map source: rooms, current room, robot/dock anchors,
- **A1-SERVIC-4** `mapping/mapping_services.py:443` · Both — the geometry layer is brand-independent; only the final dispatch conversion differs.  
  `_saved_zone_coord`'s docstring claims it "mirrors the hidden-regions sanitizer" but omits that sanitizer's degenerate-drop — a zone that can be saved but can NEVER be cleaned, with no service able to repair its geometry  
  A saved zone can enter storage in a state where every attempt to clean it fails with a generic error toast, and the user's only recourse is to delete and redraw it — the named zone is not repairable. The card's own conve
- **A1-SERVIC-3** `mapping/mapping_services.py:493` · Eufy (unclamped). Roborock is protected by the device_mm-branch clamp.  
  `clean_times` has no upper bound, defended by a sibling comment claiming dispatch enforces the per-brand ceiling — dispatch clamps it only on the Roborock (`zone_coords: device_mm`) branch; the Eufy branch ships it verbatim  
  A user who types a pass count above the device's ceiling on a Eufy gets a success toast and a {"cleaned": true} response while the device either silently ignores the pass count or rejects the whole zone_clean command and
- **A1-SERVIC-5** `mapping/mapping_services.py:563` · Both.  
  services.yaml documents map_id as optional ("Leave blank to use the current active map") on 8 mapping services whose schemas make it `vol.Required`; the integration's shared resolver `resolved_call_data` is used 59 times elsewhere and zero times in this file  
  Eight documented service calls fail with a raw voluptuous error when used exactly as their own UI documentation instructs, and the same field passed as an empty/sentinel string silently writes to the wrong bucket instead
- **A2-POLYGO-5** `mapping/mapping_services.py:769` · Eufy only (adjust_map_segment writes against `image_segments`, populated only by the `eufy_cv_v1` engine; Roborock declares segmenter_engine='noop_fallback' at adapters/roborock/adapter.py:482 so it has no CV store to adjust)  
  Stale `image_segment_adjustments` survive a CV re-analysis and are re-applied by segment_id to whatever polygon now carries that id - moving a room the user never edited  
  Silently wrong overlay geometry after a re-analysis, attributed to a manual edit the user never made on that room. Reversible only by calling `adjust_map_segment` with the exact inverse deltas (the values ARE surfaced in
- **A3-IMAGE--5** `mapping/mapping_services.py:896` · Both; Roborock materially more exposed because get_active_map_id returns the user-authored map NAME verbatim.  
  Image filenames are built from an unsanitised free-form map_id, so one map's upload can silently overwrite another map's image  
  The user edits/uploads a backdrop for the map they named and it lands on a different map's file, with the storage records still claiming otherwise — a direct answer to 'does the edit land on the map it names?' being 'not
- **A3-IMAGE--7** `mapping/mapping_services.py:1012` · Both.  
  delete_map_image drops the storage record and reports deleted:True even when the file removal failed, and analyze's filesystem probe then re-uses the orphan  
  The user is told a bad upload was removed, the UI agrees it is gone, and the segmenter keeps using it — the delete is neither honest nor effective. Also leaves an undeletable orphan: with no image_variants record, a seco
- **A3-IMAGE--6** `mapping/mapping_services.py:1014` · Both.  
  delete_map_image calls itself the mirror of upload but has no layout_id/art_scope sibling and sweeps no back-references  
  A layout survives its backdrop and becomes uneditable with a misleading reason ('no custom backdrop') while continuing to advertise one; get_map_segments silently substitutes the CV dark/default/light image metadata for
- **A4-CUSTOM-3** `mapping/mapping_services.py:1449` · Eufy only — on Roborock async_get_map_data_dict returns None early (map_source_coordinator.py:683), so nothing is written. _(finder said HIGH; verifier corrected)_  
  _backfill_saved_zone_area fails OPEN on an indeterminate active map and permanently persists area_m2 / room_number computed from the WRONG map's raster — the poisoned value never self-heals  
  Permanently wrong zone size shown in the card, a zone filed under the wrong room in the browse list (grouped by room_number per docs/dev/frontend/saved-zones.md), and a wrong area feeding the learning/duration-estimate p
- **A4-CUSTOM-4** `mapping/mapping_services.py:1467` · Eufy only — zone_membership returns room_number=None on Roborock (no per-pixel raster), so the `membership.get('room_number') is not None` arm never fires there.  
  _backfill_saved_zone_area overwrites a user's explicit 'Unassigned' filing — room_number=None means both 'never computed' and 'user chose Unassigned', and the read path cannot tell them apart  
  A saved zone silently jumps out of the Unassigned section into a room section the user explicitly moved it out of. Filing only — docs are explicit that room_number never affects dispatch, so no wrong physical clean. Narr
- **A4-CUSTOM-2** `mapping/mapping_services.py:1550` · Both (Eufy + Roborock). The card path additionally needs a live map source present (mss.present) for the dock-mascot fallback, which is the normal Eufy fork configuration. _(finder said HIGH; verifier corrected)_  
  In custom mode with no resolvable layout, _resolve_active_scope hands writers THROWAWAY dicts — set_companion_anchor / set_segment_room_link mutate a garbage-collected object and report saved: True  
  The mascot visibly stays where the user parked it for the rest of the session (the card never refetches after an anchor write) and silently snaps back on the next page load — repeatedly, with no error and no way for the
- **A4-CUSTOM-6** `mapping/mapping_services.py:1752` · Eufy only in practice — image_segment_adjustments is written against the CV image_segments store, which only the Eufy CV segmentor populates.  
  adjust_map_segment persists a map-level record keyed by a segment id that CV re-analysis recycles — a nudge authored for one room silently re-attaches to whichever segment inherits that id  
  A displayed room outline is silently offset from its true position and falsely labelled as manually adjusted, and the correction the user made is lost from the room it belonged to. Display/linking only — segment polygons
- **A5-FURNIS-1** `mapping/mapping_services.py:2108` · both _(finder said HIGH; verifier corrected)_  
  map_id is documented as optional + auto-resolving on 6 presentation services but is vol.Required; a literal blank map_id silently mints and writes a phantom map bucket  
  The service reports success and the setting is permanently invisible — the classic silent-wrong-answer shape. It also leaves a ghost map in .storage that surfaces through get_vacuum_maps / diagnostics as an extra map wit
- **A6-ZONE-C-5** `mapping/mapping_services.py:2346` · Both.  
  create_custom_layout force-flips segmentation_mode to "custom" with no record of the prior mode; delete only restores "cv" when zero layouts remain, so create-then-delete strands the user on a layout they never chose  
  Creating and then cancelling a layout silently changes what the map card renders — a different room-to-segment mapping, different mascot anchors, possibly a furnished art layer. Presentation-level only (room CLEAN dispat
- **A6-ZONE-C-4** `mapping/mapping_services.py:2503` · Eufy only — async_get_map_data_dict is the Eufy-only coordinator accessor (degrades to None elsewhere per docs/dev/frontend/saved-zones.md Wave 2), so on Roborock both fields simply stay None.  
  create_saved_zone files area_m2 + room_number from whatever raster is live when the active map is indeterminate, and that wrong value can never be corrected  
  A zone shows the wrong m² in the card list, is filed under a room from another map, and every ETA derived from it is wrong — permanently, with no UI path to fix the size. Needs the active-map signal blank at authoring ti
- **A6-ZONE-C-6** `mapping/mapping_services.py:2545` · Both for the phantom-bucket mechanism. The rename trigger is Roborock-specific (map NAME as id); the Roborock select's state changing on an in-app rename is near-certain but is device behaviour I could not verify from source.  
  Every handler in the block mints a persisted map bucket for an unknown map_id — including on the pure not-found and read-only clean paths  
  All saved zones and custom layouts for a floor appear to vanish after a vendor-side map rename, with no error and no migration path — the data is intact in .storage under the old key but unreachable through any service.
- **A6-ZONE-C-2** `mapping/mapping_services.py:2552` · Both — the zone step and its resolver are brand-agnostic. _(finder said HIGH; verifier corrected)_  
  delete_saved_zone performs no reference check; run-profile and queue `zone` steps keep the dead id and are silently dropped at run time while the UI still lists them  
  A saved run silently stops doing part of what the user built, and the UI keeps advertising the step that no longer runs. There is no warning at delete time and no reason code — the divergence is only discoverable by watc
- **A7-ROBORO-1** `mapping/roborock_raw_map.py:158` · roborock  
  A raster containing ZERO rooms is published as present:True — decode's own room_ids signal is computed and discarded  
  The card's `isVaRenderActive()` (src/state/map.js:1201) only tests `mapRenderData()?.present`, so the VA (▦) backdrop switches on over a completely blank canvas, replacing the live Roborock map image the user was looking
- **A7-ROBORO-3** `mapping/roborock_raw_map.py:163` · roborock (the identical raster-only version hash exists for eufy in map_source.eufy_version_of, out of scope here)  
  `version` hashes the raster ONLY, while the payload also ships room_names — a room rename cannot invalidate a fetched render payload  
  Immediately after renaming a room, that room's custom fill colour and its floor-type material silently disappear from the rendered map and it reverts to the default palette fill — with no error and no way to tell why. It
- **A7-ROBORO-4** `mapping/roborock_raw_map.py:171` · roborock  
  ro_dx/ro_dy are hardcoded 0 and the decoded top/left are discarded — the payload cannot express any offset between the raw IMAGE-block frame and the parser's rendered frame  
  IF the frames differ: the card draws the raster full-bleed at 0..1 while every overlay it composites on top — room bboxes, robot/dock anchors, no-go and no-mop quads, saved zones — comes from map_state_source in the pars
- **A2-POLYGO-4** `mapping/segment_primitives.py:221` · Both (brand-agnostic custom-layout authoring)  
  `mask_to_polygon` keeps only the largest traced loop, so merging two non-touching shapes into one room silently discards every piece but the biggest  
  A user merging a room with a detached alcove, a galley across a doorway, or a split L-shape whose two rects do not quite touch loses the smaller piece permanently. There is no error and no `skipped` signal. Because the c
- **DQ-Q-5** `maps/map_manager.py:197` · both  
  A map rebuild silently auto-enables AND auto-approves rooms that never existed before, adding them to the clean queue unseen  
  After a Rebuild Map, any segment that appeared since the last rebuild — a room the user renamed into existence in the vendor app, or on Eufy a phantom segment the CV segmenter split off — is cleaned on the next Start wit
- **EP-3** `number.py:22` · both · `direct read`  
  Interval bounds are framework constants, and the ceiling is BELOW a shipped component's declared max  
  VERIFIED: MAINTENANCE_INTERVAL_MAX = 500.0 is applied to every component of every brand, while the adapter declares a per-component max_interval_hours that the schema marks REQUIRED -- and Eufy's `sensor` component decla
- **DR-ONB-4** `onboarding/manager.py:66` · both · `direct read`  
  The five-key default record is hand-duplicated between _get_map_onboarding and reset_onboarding  
  Lines 66-72 and 252-258 are two hand-maintained copies of one vocabulary -- the campaign's structural root cause, in a 263-line module. A sixth flag added to the lazy-create path silently produces reset records missing i
- **DR-ONB-1** `onboarding/manager.py:182` · both · `direct read`  
  remap_confirmed_floor_types mutates in place while iterating, losing confirmations whenever old and new id sets overlap  
  PROVEN by execution. The loop pops str(old_id) and writes str(new_id) into the SAME dict it is iterating over, so a new_id that is also a later old_id consumes the entry just written. Measured: id_remap={1:2, 2:3, 3:4} w
- **DR-ONB-2** `onboarding/manager.py:186` · both · `direct read`  
  check_for_new_rooms compares a PER-MAP stored count against a source with no map scoping  
  The stored side, room_count_at_last_check, is stamped by mark_rooms_discovered from data['maps'][vacuum][map_id]['rooms'] -- per map. The live side reads the vacuum entity's `segments` attribute, which carries only the A
- **INF-1** `panels.py:29` · both · `direct read`  
  panels.py claims to be the single registration seam; a fourth site hand-copies all three of its constants  
  VERIFIED AT SOURCE. The module docstring asserts it is 'the single source of truth for that registration so the three call sites all compute the title and register the panel identically'. There are FOUR sites, and the fo
- **A6-PP-EST-DSP-2** `planning/run_plan.py:125` · both _(finder said HIGH; verifier corrected)_  
  _settings_profile_display's "selected != resolved" custom-detection arm is dead for every name the resolver can rewrite — a carpet-downgraded mop room is still labelled "Vacuum + Mop Quick"  
  The run-plan / payload row for a carpeted room set to a vacuum+mop preset reads "Living Room Vacuum + Mop Quick" with is_custom_profile False, while the carpet constraint has already downgraded the run to vacuum-only. No
- **DQ-Q-3** `planning/run_plan.py:884` · both  
  A run profile whose first step is a zone is permanently unstartable and reports "Room-clean payload is missing or invalid"  
  A saved run profile that begins with a saved-zone step (e.g. "spot-clean under the table, then clean the downstairs") can never be started. The user gets "Room-clean payload is missing or invalid." — a message about a co
- **A5-PP-RP-5** `planning/run_plan.py:884` · both  
  A user-authored leading or trailing charge/wait step is silently deleted at dispatch while the card still shows it and stamps has_charge_steps  
  A profile the user built as "wait 30 minutes, then clean" or "charge to 95%, then clean" starts cleaning immediately, at whatever battery level the robot is sitting at; "clean, then charge to 100%" never charges. The ste
- **DQ-Q-1** `planning/run_plan.py:902` · both _(finder said HIGH; verifier corrected)_  
  Stepped run silently collapses to ONE atomic dispatch when every break phase is trimmed — per-group settings and group sequencing are discarded  
  A saved run profile such as "charge to 100%, then bedrooms on quiet, then kitchen on max" runs as a single batch. On Roborock the per-phase `global_pre_calls` (fan / mop-intensity select, adapters/roborock/adapter.py:132
- **A5-PP-RP-2** `planning/run_plan.py:1379` · both _(finder said HIGH; verifier corrected)_  
  Any plan whose FIRST surviving phase is a zone is refused with "Room-clean payload is missing or invalid" — and a live blocker rule can push a plan into that state  
  A saved run that worked yesterday becomes unstartable the moment a door/occupancy sensor blocks the rooms in its first group — with an error that blames a corrupt payload rather than naming the blocked room. The rest of
- **A3-PP-CRUD-6** `profiles/manager.py:47` · future_brand_only  
  Protected-profile-name set is frozen from the Eufy in-code catalog, so a brand's own built-ins are unprotected and can be shadowed by a user profile  
  For a future adapter with its own profile vocabulary, a user 'saving' a profile under one of the brand's built-in names would silently and permanently replace that built-in for dispatch while the card still labels it pro
- **DQ-Q-2** `profiles/manager.py:148` · roborock  
  _match_profile_from_fields is structurally brand-blind and rewrites every Roborock room's profile_name to "custom" on every start  
  A Roborock room the user set to "Vacuum Only Quick" is reported as a Custom profile everywhere the start plan feeds: `queue_state["queue_rooms"][].profile_name` (queue_engine.py:127), `resolved_rooms[].selected_profile_n
- **A3-PP-CRUD-4** `profiles/manager.py:257` · roborock  
  get_effective_room_details resolves with no catalog — Eufy floor defaults override a Roborock carpet room, and "Quick" is injected where the brand has no intensity axis  
  `get_effective_room_details` is what the room entity publishes as attributes (room_entities.py:178) and what `save_room_profile_from_room` persists (manager.py:430-464). So the divergence is not display-only: saving a Ro
- **A3-PP-CRUD-5** `profiles/manager.py:322` · both  
  save-a-room-as-a-profile is not a round trip: path_type is discarded and re-derived from clean_intensity  
  path_type is a real wire field on Eufy X10/X8 (`"path_type": {"field_name": "path_type"}`, adapters/eufy/adapter.py:581, gated by supports_path_control at :226). So on an X10: set a room to the Narrow cleaning path, save
- **A4-PP-RP-6** `profiles/manager.py:779` · both  
  normalize_run_profile_steps passes arbitrary per-room fields through untouched, and the run-plan overlay treats them as authoritative settings — the one dispatch path that skips _protected_room_config  
  A user captures a room group while a room is hardwood and set to mop, then later marks that room as carpet (rug moved in). Every other path in the system now refuses to mop it — the card shows Vacuum, and apply_run_profi
- **A4-PP-RP-7** `profiles/manager.py:1258` · both  
  Applying a profile whose rooms no longer exist silently deselects and persists every room on the map, and reports the failure as "profile_not_found"  
  After a map rebuild or re-segmentation renumbers rooms, pressing a saved run profile deselects every room on the map, saves that to disk, and either says nothing (apply service / card) or blames a missing profile (start)
- **A6-PP-EST-H2O-1** `profiles/room_profiles.py:140` · both  
  granite and concrete are user-selectable floor types but are absent from every floor_type_water_defaults table, so a mop room there resolves water_level "" and is estimated as if it were dry  
  The learning panel's "Job will use N ml" under-counts by the entire floor-application volume for those rooms, and `not_enough_clean_water` / `low_clean_water_margin` (run_plan.py:488-496) — the source of the "Not enough
- **A1-PP-RES-8** `profiles/room_profiles.py:165` · future_brand_only  
  resolve_profile_catalog's `or` fallbacks mean a brand cannot declare an intentionally EMPTY block — it silently inherits Eufy's  
  No shipped brand hits this today (both declare non-empty blocks), but it is a structural seam a third brand categorically cannot express — the framework's own extension point silently substitutes Eufy vocabulary for a de
- **A2-PP-CAP-7** `profiles/room_profiles.py:166` · future_brand_only _(finder said LOW; verifier corrected)_  
  resolve_profile_catalog uses `or` for every key, so a brand that explicitly declares an EMPTY block silently gets Eufy's  
  No shipped brand declares an empty sub-block, so nothing is broken today. A brand-3 author who writes `"floor_type_water_defaults": {}` meaning 'this device has no water, do not apply surface defaults' gets Eufy's Low/Me
- **A2-PP-CAP-2** `profiles/room_profiles.py:209` · roborock  
  normalize_room_profile's third-level literals are the one fallback a brand CANNOT override — the more deliberately a brand omits an axis, the more certainly it gets the Eufy literal for it  
  Two live effects. (1) Profile matching never converges on Roborock: `_match_profile_from_fields` (manager.py:157-171) resolves each candidate from a bare `{"profile_name": name}` — which has no `clean_intensity` key, so
- **A1-PP-RES-7** `profiles/room_profiles.py:284` · both  
  A room pointing at a deleted or renamed custom profile silently resolves to the default profile — the UI reports a profile the room is not running  
  After deleting or renaming a custom room profile, every room that used it shows "Vacuum Only Quick" in the room editor and the run plan while actually running the deleted profile's suction/water/passes. The room editor's
- **A1-PP-RES-5** `profiles/room_profiles.py:294` · both  
  get_available_profile_names hardcodes the four Eufy built-in keys, so get_available_profiles silently drops every user-saved custom profile and would return {} for a brand with different catalog keys  
  sensor/profile.py:63-70 passes the user's stored profiles in and publishes `profile_count` / `profiles` / `profile_labels` from the result, so the "available room profiles" sensor always reports 2 or 4 and never lists a
- **A2-PP-CAP-4** `profiles/room_profiles.py:294` · both  
  get_available_profile_names hardcodes the four Eufy catalog KEYS and takes no catalog — get_available_profiles merges every user-created profile in and then filters all of them back out  
  The 'Available cleaning profiles' diagnostic sensor (sensor/profile.py:63-70) reads its own custom-profile store, passes it in, and reports a count that can only ever be 2 or 4 — a user with five saved custom room profil
- **A1-PP-RES-3** `profiles/room_profiles.py:419` · eufy _(finder said HIGH; verifier corrected)_  
  path_type resolves to the literal string "None" for any room backfilled by the startup migration, and that string reaches the Eufy wire payload  
  An Eufy X10/X8 room-clean payload carries path_type:"None" instead of "wide"/"narrow" — an out-of-vocabulary enum the device did not ask for, on every run of any room that predates the path_type field. planning/run_plan.
- **A1-PP-RES-4** `profiles/room_profiles.py:448` · both  
  "granite" and "concrete" are user-selectable floor types with no entry in either brand's FLOOR_TYPE_WATER_DEFAULTS, so the mop-with-no-water correction corrects to empty string  
  A mop-mode room on a Granite or Concrete floor whose water_level is unset or "off" dispatches water_level="" — no water and no error, when the code's stated intent is to correct that exact combination. The same empty val
- **DQ-DE-2** `queue/dispatch_engines.py:110` · future_brand_only  
  _SinglePhaseMixin silently swallows strict_order and the seam cannot express refusal — while the caller hides the order advisory on the strength of the request alone  
  A brand that path-optimizes (honors_clean_order False) but whose payload shape is list-of-dicts or positional-arrays — i.e. anything on eufy_room_clean, dreame_room_clean, or a future engine built off _SinglePhaseMixin —
- **DQ-DE-4** `queue/dispatch_engines.py:422` · future_brand_only  
  An omitted dispatch.template silently resolves to the Eufy engine with no warning, and the claimed registration-time rejection does not exist  
  A future brand's clean command is built in the wrong structural shape and shipped to its service. The failure mode is either a hard service error at start (best case) or a partially-parsed command the device acts on. The
- **A6-AGX-4** `rooms/access_graph.py:364` · both  
  Every access-graph issue message is a hard-coded English literal and is rendered verbatim in the card on all 18 shipped locales  
  On any non-English install the room-access modal's issue list and its save-error banner are English, including for AR/HE where they are injected into an RTL layout. This is the one place in the access feature where the u
- **A6-AGX-1** `rooms/access_graph.py:651` · both _(finder said HIGH; verifier corrected)_  
  get_access_graph_health emits no verdict — the "runs are allowed" empty graph and the "every run is blocked" partial graph are indistinguishable, and the report's own remediation moves the user from the first into the second  
  The one service documented as the access-graph diagnostic cannot answer the only question that matters — "are my runs blocked right now?". Following its single actionable instruction on a fresh map (mark a dock room) sil
- **A5-AG-2** `rooms/access_graph.py:770` · both  
  A room with no inbound edge makes the whole graph 'partial', hard-blocking every run on the map, and no shipped surface names the offending room  
  After a map rebuild that discovers even one new room, every Start on that map is refused with 'Room access graph is partially configured. Complete it or clear all access settings to allow basic runs.' — a message that na
- **A2-REC-3** `rooms/reconciliation.py:125` · roborock _(finder said HIGH; verifier corrected)_  
  A room renamed AND renumbered in the same edit is invisible to reconciliation — and migrate then deletes its stored data as if it were a stranger  
  The single most common real re-segment on the shipping Roborock path produces no review at all, and the affected room silently loses its floor type, profile, cleaning settings, rules and access grants — the room then beh
- **A2-REC-6** `rooms/room_crud.py:99` · both  
  Applying a 'renamed' review orphans that room's learned baselines, while the code comment claims history follows the room regardless  
  Renaming a room in the vendor app and confirming the resulting review silently discards that room's accumulated duration and water learning; time and consumable estimates degrade with no error, and the docstring tells a
- **A2-REC-5** `rooms/room_crud.py:162` · both  
  migrate applies a plan the user never saw: it never re-checks the reviews, and rebuilds the map even when there are none  
  The confirmation is not bound to what was shown, so a migration can silently apply a different id remap (and a different set of dropped rooms) than the one the user approved.
- **A1-ID-2** `rooms/room_discovery.py:176` · roborock _(finder said HIGH; verifier corrected)_  
  discover_rooms_for_vacuum's single-map fallback serves ANOTHER map's room list and relabels it with the REQUESTED map_id, defeating the map_id filter at both room writers  
  On a multi-map (multi-floor) Roborock, importing or re-saving one floor writes the OTHER floor's rooms into that floor's bucket, destroying its stored per-room settings; and a live-id dispatch resolves 'bedroom' to the o
- **SN-4** `sensor/__init__.py:272` · both · `direct read`  
  Renaming a room never reaches the entity's friendly name - the rebuilt entity carrying the new name is discarded  
  VERIFIED: async_update_entity has ZERO occurrences anywhere in the integration. Both sync blocks construct a fresh entity per desired room and then discard it when the unique_id is already known, pushing only a state wri
- **DR-SENS-1** `sensor/lifecycle.py:203` · both · `direct read`  
  The active_job sensor reports 'none' during an app-started run the system itself considers in flight  
  native_value hand-enumerates started / paused / completed and defaults everything else to 'none'. But `external` is a first-class status in this codebase: jobs/active_job.py:136 puts it in _RUN_IN_FLIGHT_STATUSES so run_
- **SN-5** `sensor/map_overlays.py:50` · both · `direct read`  
  The overlays sensor serves a cache entry without checking its map_id or its stale flag  
  _result() reads cache[vac]['result'] and ignores cache[vac]['map_id'] -- a key the producer maintains precisely so consumers cannot mix maps: map_source_coordinator.py:117 guards the hold path with cached.get('map_id') =
- **DR-ONB-3** `sensor/onboarding.py:62` · both · `direct read`  
  The 'empty means complete' guard exists in setup/status.py and was never mirrored onto the onboarding summary — forgotten override sibling  
  UPGRADED from LOW after finding the sibling that HAS the guard. Both sites answer the same question with the same optimistic-accumulator shape: setup/status.py initialises all_steps_complete=True and all_in_sync=True and
- **A1-WIRE-2** `services/_common.py:57` · both _(finder said HIGH; verifier corrected)_  
  resolved_call_data's docstring claims an unresolvable map_id always raises; discover_rooms is the one consumer that silently falls through and persists the payload under an empty-string map key  
  Pressing "Discover rooms" — exactly what a user does when the active_map sensor is stale/unavailable — returns a clean success (the service is registered without supports_response, and the handler's `except Exception ->
- **A4-SETUP-5** `services/adapter_config.py:86` · both _(finder said HIGH; verifier corrected)_  
  save_adapter_config persists to storage BEFORE registering, so a config the registry flags as invalid is written to disk anyway and reloaded at every restart  
  A user building a custom adapter types a template name that does not exist. The call succeeds silently, the config is written to .storage, and every subsequent cleaning run is dispatched with the Eufy payload shape — on
- **A4-SETUP-3** `services/adapter_config.py:108` · both _(finder said HIGH; verifier corrected)_  
  delete_adapter_config unregisters the CURRENTLY REGISTERED adapter — after startup that is the code adapter — leaving the vacuum with no adapter at all  
  A Roborock user who once experimented with save_adapter_config, then later calls delete_adapter_config to clean up, silently converts their Roborock into a vacuum driven by the Eufy dispatch engine and Eufy defaults unti
- **A6-DIAG-1** `services/dock.py:83` · eufy _(finder said HIGH; verifier corrected)_  
  Dock actions return performed:true / "Dock action sent." when the resolved button entity has no state — the press is silently dropped by HA  
  User taps Wash Mop on the card (or calls eufy_vacuum.wash_mop from an automation), gets a success response and a success toast, and the mop is never washed. Nothing in the response or the raised-error path distinguishes
- **A6-DIAG-6** `services/dock.py:124` · both  
  set_dock_event_count overwrites and immediately saves a durable counter for any entity_id, with no managed-vacuum check and no way back except the response body  
  An automation aimed at the wrong entity id silently seeds a phantom dock_events branch that persists forever and reports success. Aimed at the RIGHT id with a wrong count, it destroys the mop-wash/dust-empty/dry-start li
- **A2-JOB-4** `services/job_control.py:130` · eufy _(finder said HIGH; verifier corrected)_  
  start_zone_clean clean_times has no upper bound; the schema comment claims a dispatch-side per-brand ceiling that exists only on the Roborock branch  
  On a Eufy, `service: eufy_vacuum.start_zone_clean` with `clean_times: 200` from YAML — or a template that produces a bad number — is forwarded verbatim to the device. The robot either repeats the zone far beyond what the
- **A1-WIRE-1** `services/job_control.py:156` · both _(finder said HIGH; verifier corrected)_  
  get_manager() is re-fetched after a device-length await, so a config-entry reload mid-dispatch loses the just-started job record (or raises a bare KeyError)  
  The robot is cleaning but the integration has no active-job record: the card shows no run in progress, no per-room progress or attribution, no learning sample, and no finalization. In path (b) nothing is logged at all —
- **A2-JOB-7** `services/job_control.py:156` · both  
  async_save() sits after the try/except in every job_control handler — a raise after dispatch leaves a running job in memory only  
  The robot is cleaning, the user sees a red "Failed to start cleaning: …" error, and the active job exists only in RAM. A restart or reload before the next unrelated save orphans the run: it is never finalized, never lear
- **A6-DIAG-3** `services/maintenance.py:46` · both  
  set_maintenance_interval bypasses the min/max its own docstring claims, and interval_hours: 0 silently turns off the consumable's alert  
  A YAML typo (`interval_hours: 0`, or hours vs. days confusion producing 10 instead of 240) permanently disables the replace-me alert for that filter/brush with a success response, or pushes the interval past the adapter'
- **A3-ROOMS-4** `services/room_profiles.py:43` · both _(finder said HIGH; verifier corrected)_  
  services.yaml advertises required fields that the voluptuous schemas reject — three services fail outright when the user fills the form HA renders  
  A user who opens Developer Tools -> Actions, picks 'Save user room profile', and fills in every field HA marks required gets a hard validation failure and cannot save a custom profile through the UI at all. The card has
- **A3-ROOMS-7** `services/room_profiles.py:52` · both  
  save_user_room_profile silently overwrites an existing custom profile and reports saved: true, while its sibling rename_room_profile refuses the identical collision  
  An automation that re-saves a profile under a name the user already uses replaces the user's saved settings with no warning and a success response. The card has no caller for this service (src/actions/room-profiles.js:26
- **A3-ROOMS-5** `services/room_profiles.py:168` · both _(finder said HIGH; verifier corrected)_  
  apply_room_profile silently no-ops on unknown room ids and returns a success-shaped response with no way to tell  
  An automation that applies a named profile to rooms after a re-segment renumbered them (Roborock does this routinely) reports success while changing nothing — the rooms clean at their old settings and the user has no sig
- **A3-ROOMS-3** `services/rooms.py:79` · both _(finder said HIGH; verifier corrected)_  
  save_managed_rooms stamps every room's floor type as user-confirmed while its schema makes it structurally impossible to supply one  
  A carpeted room created through this service is recorded as hardwood and confirmed, so the user is never asked. The carpet invariants in _protected_room_config (profiles/manager.py:98-105 — force water 'Off', edge_moppin
- **A3-ROOMS-6** `services/rooms.py:102` · both _(finder said HIGH; verifier corrected)_  
  update_room_fields accepts any clean_mode string; a casing/spelling variant keeps water in storage and in the UI but silently drops it from the wire payload  
  A hand-written automation that sets clean_mode to 'Vacuum_Mop' or 'Mop' (there is no enumeration anywhere for the user to copy the exact token from) produces a room the card shows as mopping at water 'Medium' with edge m
- **A3-ROOMS-9** `services/rooms.py:103` · both  
  update_room_fields accepts any fan_speed string; on Roborock an unrecognised value leaves the device's previous suction in place with no error  
  A room configured through the service with a slightly-off fan speed cleans at the wrong suction indefinitely. The card shows the value the user typed, get_payload_state echoes it back, and nothing anywhere reports that t
- **A5-RUNPROF-4** `services/run_profiles.py:85` · both  
  set_run_profile_steps accepts a bare `list` and silently drops or clamps every malformed step; only 'at least one room_group survived' is enforced  
  A YAML author who mistypes a step type or a percent field gets `saved: True` and a profile that has lost its charge stop — the robot then runs the whole sequence in one go and can strand mid-run instead of docking to cha
- **A5-RUNPROF-1** `services/run_profiles.py:97` · both _(finder said HIGH; verifier corrected)_  
  save_run_profile never inspects the manager's `saved` flag — a save that stored nothing returns a success-shaped response and raises nothing  
  An automation whose 'save my current selection as a profile' step runs when the queue is empty (e.g. after a run, where `_clear_room_selections_after_start` turns every room off on a successful start) reports success and
- **A5-RUNPROF-2** `services/run_profiles.py:114` · both _(finder said HIGH; verifier corrected)_  
  apply_run_profile persists a full room-selection wipe and reports no error when the profile's rooms no longer exist on the map  
  After room ids churn (map rebuild / factory reset — Eufy re-scan renumbers segments; a Roborock map re-save likewise), applying an older profile clears the user's entire current room selection, applies nothing, and neith
- **A5-RUNPROF-3** `services/run_profiles.py:146` · both _(finder said HIGH; verifier corrected)_  
  overwrite_run_profile exposes the step-sequence destruction with no warning, no confirmation, no response signal — and commits it with async_save  
  A user (or automation) that overwrites a stepped profile — vacuum group A, charge to 95%, mop group B, or a mop-dry `wait` — loses the charge/wait boundaries permanently and irrecoverably at the moment of the call. The n
- **A4-SETUP-10** `services/setup.py:100` · both  
  floor_types accepts any string; an unrecognised value is silently clamped to "hardwood" at read time, so a mistyped carpet becomes a wet-mopped carpet  
  A YAML caller sets a floor type with a typo or picks a documented-but-unmapped value; the service returns success and the stored value is silently discarded. In the carpet case the robot mops a carpet with water at the h
- **A4-SETUP-7** `services/setup.py:215` · both  
  Three setup handlers subscript data["map_id"] after resolved_call_data and raise a bare KeyError — the helper's docstring claims the manager raises a clear error instead  
  A YAML caller following docs/advanced/03-services.md (which documents map_id as optional on all three) gets an opaque `KeyError: 'map_id'` and an aborted automation whenever the vacuum is offline or HA has just restarted
- **A4-SETUP-11** `services/setup.py:229` · both  
  setup_delete_map auto-resolves an omitted map_id to whatever map happens to be active at call time  
  An automation written while the upstairs map was active later deletes the downstairs map, taking its rooms, queue, job records and learned history with it. docs/advanced/03-services.md:1498 flags the operation as irrever
- **DR-SETUP-2** `setup/drift.py:117` · both · `direct read`  
  auto_refresh_on still uses the bare or-coercion that code-flag CS-2 fixed for its three siblings  
  get_discovery_cadence reads list(disc.get(auto_refresh_on) or _DEFAULT_AUTO_REFRESH_TRIGGERS). The other three keys in the same dict literal were converted to an is-not-None guard precisely because or silently reverts a
- **A1-ID-4** `setup/drift.py:540` · both  
  Drift keys its history by bare device room_id across ALL maps but feeds it only the ACTIVE map's discovery, so a multi-map vacuum's inactive rooms decay toward 'removed' and colliding ids mask each other  
  A user with an upstairs and a downstairs map is repeatedly told that the rooms on whichever floor is not currently active have been removed from the vacuum, with the wrong floor's name attached; and a room genuinely dele
- **A6-AGX-6** `src/state/room-access.js:85` · both  
  The card's access modal renders an existing edge into the dock room as "Missing Room N" — an edge that exists is displayed as a stale reference to a room that does not  
  The editor misrepresents the stored graph: a live room is labelled missing/stale, inviting the user to delete a valid edge. Conversely they cannot re-create it, because the dock room is filtered out of the selectable lis
- **A2-DRAFT-3** `themes/manager.py:411` · both  
  set_active_theme's global-default branch is the only mutator that returns without firing _notify_updated, leaving the theme sensor's default_theme_id attribute stale  
  An automation or script that calls eufy_vacuum.set_active_theme with only theme_id (the documented 'set the global default' form, services.yaml:2086-2087) gets ok:true, but every theme-state sensor keeps reporting the pr
- **A3-PORT-4** `themes/manager.py:411` · both  
  set_active_theme with vacuum_entity_id=None returns without firing _notify_updated — the only mutation in the module that skips the callback fan-out, leaving default_theme_id stale in HA state  
  A user (or automation) sets the global default theme. The change is persisted, but the sensor.<vacuum>_theme_state attribute default_theme_id keeps reporting the OLD value until some unrelated theme mutation happens to f
- **SN-6** `themes/manager.py:412` · both · `direct read`  
  Setting the GLOBAL default theme returns without notifying, so the theme sensor is stale indefinitely  
  VERIFIED AT SOURCE. set_active_theme's `if vacuum_entity_id is None:` branch writes theme['default_theme_id'] and returns immediately; the per-vacuum branch two lines below ends with self._notify_updated(...). Every othe
- **A2-DRAFT-2** `themes/manager.py:417` · both _(finder said HIGH; verifier corrected)_  
  set_active_theme destroys the working draft unconditionally with no confirmation, no undo and no same-id short-circuit — clicking the already-active preset tile silently wipes every unsaved edit  
  A user spends time in the token editor tuning twenty colours and radii, switches to the Themes tab to compare against another preset — or just clicks the tile that is already highlighted as active, which looks like a no-
- **A3-PORT-1** `themes/manager.py:544` · both _(finder said HIGH; verifier corrected)_  
  import_theme performs no key validation; the card applies every imported key as a real CSS declaration on the card host, so one imported theme file can render the card permanently blank  
  A user uploads a community/shared theme JSON containing `"tokens": {"display": "none"}` (or position/visibility/opacity). Import succeeds with no error. When they activate it, the card element gets `display:none` inline
- **A3-PORT-3** `themes/manager.py:625` · both  
  A scoped import rewrites the ACTIVE library entry in place with no core/provenance check, permanently corrupting a bundled preloaded theme that the seeder will never repair  
  The user's bundled 'Follow HA' (or any core) theme is permanently altered — its floor namespace now holds an imported palette. The Source facet still labels it `core`, so the card presents it as the shipped theme it no l
- **A2-DRAFT-5** `themes/services.py:230` · both  
  Every update_working_draft triggers an immediate full Store.async_save of the entire integration data dict, and the card fires it on `input` — once per keystroke in text and number token fields  
  Typing a 25-character font stack into a theme token field issues 25 full-store writes back to back. On an HA Green / Raspberry Pi with SD or eMMC storage this is visible editor lag and real flash wear, and it scales with
- **INF-2** `timestamp_utils.py:8` · both · `direct read`  
  _LOCAL_TZ is a FIXED offset captured at import, so naive legacy timestamps get the wrong offset half the year  
  VERIFIED BY EXECUTION. `_LOCAL_TZ = datetime.now().astimezone().tzinfo` does not return a DST-aware zone -- it returns a datetime.timezone with a frozen offset. Ran it: repr is datetime.timezone(timedelta(-1, 61200), 'Pa

</details>

<details><summary><strong>LOW</strong> (171)</summary>

- **A1-ID-5** `adapters/eufy/discovery.py:47` · eufy  
  adapters/eufy/discovery.py is a dead, divergent second implementation of get_active_map_id / discover_rooms_for_vacuum with hand-copied sentinel and key literals  
  No user impact today (dead code), but it is a green-tested Eufy-flavoured copy of the identity functions sitting in the adapter package a future brand port would read first — reviving it re-introduces the 'null' sentinel
- **DR-BAT-2** `battery/manager.py:601` · both · `direct read`  
  An out-of-order sample is correctly skipped but still rewinds the last-sample anchor  
  Line 522 guards the delta block with `if elapsed_sec > 0`, so a sample whose timestamp is not newer contributes no drain/rate -- correct. But lines 601-603 then commit last_battery_level / last_sample_ts unconditionally,
- **DR-BAT-3** `battery/manager.py:653` · both · `direct read`  
  After a stale-session discard, charging stays untracked until the next charge cycle  
  _update_session discards a session older than SESSION_MAX_HOURS and sets session=None. Control then reaches `if session is None: return` (line 680) on every later sample, because prev_charging is already True so the open
- **EP-6** `binary_sensor.py:86` · both · `direct read`  
  _attr_suggested_object_id is not a Home Assistant attribute - four sites rely on a dead assignment  
  VERIFIED BY EXECUTION against the installed HA: Entity has NO _attr_suggested_object_id (hasattr False); suggested_object_id exists only as a READ-ONLY property derived from the entity's resolved name, and _async_derive_
- **EP-5** `button.py:256` · both · `direct read`  
  The saved-run-profile button name is hardcoded English, bypassing the translation mechanism  
  Every other entity class in scope declares _attr_translation_key and lets HA resolve the name from strings.json. EufyVacuumSavedRunProfileButton sets _attr_has_entity_name = True, declares NO translation key, and overrid
- **A3-FLOW-3** `config_flow.py:98` · both  
  The options flow rebuilds the options dict from the stale form snapshot, so a submit can resurrect a vacuum that was deleted while the dialog was open  
  A user who deletes a vacuum's device while the Configure dialog is open in another tab sees the vacuum reappear after saving the dialog — as an empty shell that has lost all its learning history and maps. No error is sho
- **A3-FLOW-2** `config_flow.py:103` · both _(finder said MEDIUM; verifier corrected)_  
  Changing the vacuum in the options flow ADDS a second managed vacuum instead of replacing the first — the old pick is never reconciled away  
  A user who picked the wrong entity at install (or renamed their vacuum entity and updated the option to match) ends up with TWO sidebar panels, both titled "Vacuum Agent" by default and therefore indistinguishable, two s
- **INF-7** `const.py:27` · both · `direct read`  
  Four constants are defined and never read - including three service names for services that do not exist  
  Scripted check across every .py excluding const.py, cross-checked against services.yaml and the frontend bundle: SERVICE_REFRESH_BACKEND ('refresh_backend'), SERVICE_REBUILD_ACTIVE_MAP ('rebuild_active_map') and SERVICE_
- **A1-INIT-5** `core/manager.py:429` · future_brand_only  
  The startup backfill and setup_progress migration hard-code Eufy vocabulary and structurally cannot consult the adapter  
  No divergence on the two shipped brands today. A third brand whose room_profiles.default_profile is not 'vacuum_quick' would have any legacy room missing profile_name stamped with another brand's profile key at startup (
- **A2-CB-3** `core/manager.py:579` · both  
  The manager's four own callback registries append without a duplicate check while the theme registry they delegate to dedupes, and unregister removes only one copy  
  Latent today. If any future caller registers a room-update callback twice — or if the path_blockers `remove()`/`register()` pairing is ever broken so its `remove` no-ops — that subscriber survives config-entry unload and
- **A2-CB-4** `core/manager.py:1035` · both  
  remove_vacuum_record wipes every bucket the five callback registries exist to mirror and fires none of them, dropping the notification obligation its narrower sibling remove_map documents  
  Contained today by HA's own device-deletion sweep, so no user-visible breakage on the shipped path. The residual is that the in-memory `entity_map` / `room_history_entities` / `room_rule_status_entities` dicts in switch.
- **A6-VAC-5** `core/manager.py:1084` · both  
  get_managed_vacuums reads data["capabilities"] raw and reports supports_* as None when no snapshot exists, unlike its sibling get_vacuum_capabilities which detects on demand  
  Latent today: the only consumer, setup/status.py:171, reads just `vacuum_entity_id` from the returned items. Any future consumer of the four supports_* fields (or a diagnostics dump) would read `null` and treat it as "un
- **A5-FACADE-4** `core/manager.py:1239` · both _(finder said MEDIUM; verifier corrected)_  
  save_user_room_profile facade silently overwrites the existing 'user_1' profile when profile_name is omitted, while its sibling mints a unique id  
  A user (or automation) that saves two custom room profiles without supplying profile_name ends up with one: the second silently replaces the first, and both calls report saved=True. Every room whose stored `profile_name`
- **A4-START-3** `core/manager.py:2943` · both _(finder said MEDIUM; verifier corrected)_  
  get_start_status can never surface a non-blocking lifecycle warning message — preflight's "ready" text shadows it, making dock-drying starts show warning=True with the message "Ready to start cleaning."  
  Every start attempt during the post-mop dock-drying window — which follows every mop run on both brands — returns a warning flag whose explanatory text says "Ready to start cleaning." and whose reason is "ready". The car
- **A3-SNAP-4** `core/manager.py:4017` · future_brand_only  
  zone_max invents Eufy's device limit (10) for any brand that declares none, while the dispatch gate enforces no cap at all when the key is absent  
  A future adapter that declares no `zone_max` gets a card that silently stops the zone draw at 10 boxes with no explanation, while the backend would happily have dispatched more — a limit the user is shown but that the de
- **DQ-ZONE-5** `core/manager.py:4030` · both _(finder said MEDIUM; verifier corrected)_  
  zone_bounds is computed and shipped in the dashboard snapshot but has no consumer anywhere — and the card replaces the precise refusal message with a generic toast  
  Roborock's declared ceiling is 3.05 m² (roborock/adapter.py:614) — about a 1.75 m square, smaller than many ordinary draws — so a user drawing a normal box gets a refusal on press, and the actionable text explaining WHY
- **A4-START-2** `core/manager.py:5021` · both _(finder said MEDIUM; verifier corrected)_  
  start_selected_rooms dispatches phase 0 with no phase_type branch, unlike its phase_runner sibling — and _build_steps_phases' docstring claims a guard that does not exist  
  Latent today: the only thing stopping a segment-clean command with an empty room list from reaching the robot is the accidental `payload_room_count <= 0` block described in START-1, which is a side effect of the zone pha
- **DR-DIAG-5** `diagnostics.py:53` · both · `direct read`  
  Dead `_SENTINELS` alias sits in the one file whose header explains why that set must not fork  
  _SENTINELS = BLANK_STATE_VALUES is assigned and never read; the live use is _ACTIVE_MAP_SENTINELS, which IS BLANK_STATE_VALUES (same object, correctly centralized). So the file carries a second, unused name for the same
- **DQ-ACT-7** `dispatch/manager.py:421` · future_brand_only  
  The OFF-fallback lowercases the select's options for the membership test but then sends the lowercased string as the option value  
  On a future brand whose select uses capitalized or numeric options, the mop-intensity pre-call silently no-ops and the run uses whatever water the device was last left on — the same physical outcome as DQ-ACT-5, reached
- **DR-DOCK-3** `dock/manager.py:446` · both · `direct read`  
  A manual counter reset leaves the debounce marker, suppressing the next genuine event  
  set_dock_event_count zeroes the counter but never clears {event_type}_last_counted_at. Reset inside the debounce window and the next real wash is silently not counted -- reset and debounce state are not kept coherent.
- **DR-BAT-1** `docs/dev/12-battery-system.md:88` · both · `direct read`  
  Doc §3 states the MAX_DELTA_PCT boundary one step off from the code and from its own §5.2  
  The tunable-constants table says 'Reject single-sample deltas this large OR LARGER' (>= 3.0). manager.py:524 is `if abs(raw_delta) <= MAX_DELTA_PCT`, so exactly 3.0 is ACCEPTED and only >3.0 is rejected -- which is what
- **DR-BAT-4** `docs/dev/12-battery-system.md:338` · both · `direct read`  
  Doc omits two live conditions present in the code  
  §6.4/§8 give the mid-job rate-stat gate as `kind == 'mid_job' and avg > 0`; manager.py:771 also requires `delta_pct > 0`. §5.2's _process_sample snippet omits the `elapsed_sec > 0` guard at line 522 entirely. Both are co
- **DR-ONB-6** `docs/dev/18-onboarding-manager.md:228` · both · `direct read`  
  Doc cites the start gate at core/manager.py:2776; it is at 2805  
  The CLAIM is correct -- the gate really does block on floor_types_complete alone and never consults rooms_discovered. Only the line reference drifted. Recorded because this doc's stated scope is that 'a developer should
- **INF-9** `entity_helpers.py:109` · both · `direct read`  
  get_floor_type_label emits hardcoded English into an 18-language product  
  Nine English literals plus an English-derived fallback (str(floor_type).replace('_',' ').title()), emitted as floor_type_label from three backend payloads (core/manager.py:280, planning/run_plan.py:174, profiles/manager.
- **A6-PRE-4** `jobs/job_monitor.py:32` · both  
  BlockedRoomEntry.source documents "access_graph" for graph-propagated blocks; the producer writes "access_dependency", and the wrong literal is hand-copied into an exposed sensor attribute's type  
  The blocked-room `source` is surfaced as the `last_block_source` attribute on a per-room HA sensor. A user (or a future card branch) writing an automation template against the documented `access_graph` value silently nev
- **A6-PRE-3** `jobs/job_monitor.py:58` · both  
  PreflightResult declares `available` with a documented contract the producer never honours, and omits two keys the producer writes  
  Latent trap rather than live misbehaviour: nothing reads `available` today (manager.get_start_status derives the all-blocked case from included_room_count instead, core/manager.py:2834). Any future consumer that trusts t
- **A1-EST-7** `learning/estimator.py:238` · future_brand_only _(finder said MEDIUM; verifier corrected)_  
  _load_mop_wash_config hard-codes Eufy's wash-frequency bounds (15/20/25) in the brand-agnostic estimator while the adapter already declares wash_frequency_bounds  
  On any brand whose wash cadence falls outside Eufy's 15-25 minute helper range, the ETA carries a wrong mop-wash overhead and the payload reports a wash interval the dock is not set to. Eufy itself is unaffected because
- **A2-ACC-7** `learning/estimator.py:592` · both _(finder said MEDIUM; verifier corrected)_  
  A non-dict `rooms` block crashes both accuracy readers — including estimate() on the event loop — while the sibling reader in the same subsystem explicitly tolerates it  
  A hand-edited or older accuracy_stats.json with a list-shaped `rooms` block takes down the entire job-progress snapshot on every card refresh (no estimate, no timeline, no live banner) rather than degrading to zero drift
- **A1-EST-9** `learning/estimator.py:766` · both  
  estimate() runs ensure_dirs (four mkdir syscalls) three times per call on the event loop, even on full cache hits  
  Recurring blocking filesystem I/O on the HA event loop on every dashboard snapshot. On a network-mounted config directory this can surface as HA's "blocking call inside the event loop" warning or as UI stutter, without a
- **A1-EST-8** `learning/estimator.py:829` · future_brand_only  
  is_mop raw-compares clean_mode against a hand-copied literal set while the very same function canonicalizes it for the stats lookup  
  Latent today: both shipped adapters put canonical tokens ("vacuum"/"mop"/"vacuum_mop") into resolved_rooms, so is_mop resolves correctly. A brand or a restored older payload carrying a display-string mode silently loses
- **A2-ACC-5** `learning/estimator.py:1130` · both _(finder said MEDIUM; verifier corrected)_  
  Completed-room slug matching is keyed on the literal string "none" — the documented slug fallback is dead, and a room with a null slug is marked complete before it is cleaned  
  Concrete: 3-room queue where R2's stored slug is null. R1 completes with actual 9.0, so completed_by_slug = {"none": 9.0}. On the next reanchor R2 is not in completed_by_id, but its slug normalizes to "none" and hits the
- **A3-IO-7** `learning/history_store.py:196` · both  
  write_json is rename-atomic but not durable — no fsync before os.replace, so a power loss can leave a zero-length learned file that read_json then reports as "no data"  
  A power cut during a stats write can leave the learned file empty; on the next run the integration reports no learned history rather than an error, and the trouble-rooms accumulator then overwrites what remains (IO-2).
- **A4-STATE-7** `learning/history_store.py:232` · both _(finder said MEDIUM; verifier corrected)_  
  load_live_snapshot performs 4 mkdir syscalls plus an open()/read() on the Home Assistant event loop at every cold finalize  
  The event loop stalls for the duration of a network filesystem mkdir×4 + read at the moment a job finishes, delaying every other entity update in Home Assistant, and HA logs a blocking-call warning.
- **A3-IO-8** `learning/history_store.py:599` · both  
  append_job_csv_row / append_room_csv_rows are dead, and each CSV header is a hand-copied literal duplicated between the dead append writer and the live rebuild writer  
  None today (the append path never runs). Latent: a future schema column added to one copy of a header and not the other, or a re-enabled append writer, silently produces a misaligned exports CSV that a user opens in a sp
- **A5-SVC-9** `learning/services.py:72` · both  
  Schemas mark map_id Required on three services the documentation marks optional, so an automation written from the docs fails validation  
  An automation authored from the published service reference fails at call time with a schema error on three services, two of which the docs specifically position for manual/edge-case use ("historical corrections").
- **A5-SVC-8** `learning/services.py:450` · both  
  invalidate-then-preload is a no-op when a preload is already in flight, letting a stale in-flight load repopulate the cache with pre-rebuild data  
  After an exclude, restore, or rebuild, the card can keep showing pre-rebuild estimates and confidence until some later event invalidates the cache — making a correct repair look like it did nothing.
- **A4-STATE-9** `learning/services.py:892` · both  
  Dismissing the incomplete-run banner is client-only and no clear service is exposed, so the banner returns on every card load  
  "Dismiss" does not dismiss — the missed-rooms alert reappears on every dashboard reload until the user either accepts the retry (which rewrites their room selection) or happens to complete another run.
- **A3-COMMON-5** `listeners/_common.py:52` · both  
  get_adapter_value() is a second, independent implementation of the identical lookup already shipped in adapters/registry.py  
  No behavioural difference today. A fix or semantic change applied to one implementation (e.g. distinguishing a declared null from an absent key, or adding a diagnostic when a declared block is the wrong type) would silen
- **A3-COMMON-4** `listeners/_common.py:178` · both  
  _common owns the completion QUESTION but not its vocabulary defaults — the clear-sentinel and completion-status fallbacks exist as two hand-copied literals in different modules  
  No wrong result today (the two literal sets are identical). Latent divergence: changing the generic completion fallback in one place silently leaves the completion gate and the stranded reaper judging the same run agains
- **A3-COMMON-2** `listeners/_common.py:198` · future_brand_only _(finder said MEDIUM; verifier corrected)_  
  completion_secondary_satisfied() returns True from a config FLAG without verifying the entity it delegates to exists; the "Invariant" asserted in the caller is never validated  
  For a brand-3 adapter written against Roborock's pattern, the completion gate silently degrades to "task_status equals one string" with no secondary confirmation at all — while has_observed_active_lifecycle never arms, s
- **A1-REG-4** `listeners/dock_events.py:91` · future_brand_only  
  dock_events.register() never reads the adapter's `dock_events.enabled` flag — a brand that declares enabled:False but inherits triggers still records dock events  
  A future adapter that copies the Eufy dock_events block and flips `enabled: False` to opt out gets the opposite of what it declared: dock events are recorded and counters incremented, while the Base Station UI tab is hid
- **A5-METRICS-3** `listeners/job_metrics.py:44` · future_brand_only  
  `_duration_state_to_seconds` silently treats any unrecognized unit as seconds, and re-resolves the unit per event with no mid-run consistency check  
  Latent. On the two shipped brands the resolved units are "s" (Eufy, absent → seconds) and the adapter hint "min" (Roborock, bare number), both handled correctly and test-covered, so no wrong value reaches a user today. T
- **A5-METRICS-4** `listeners/job_metrics.py:117` · future_brand_only  
  Station-water subscription guesses an entity key that exists nowhere, ignores the adapter's `supports_station_water` declaration, and swallows every lookup failure silently  
  No wrong value on either shipped brand today (Eufy's `sensor.<vac>_water_level` is the station tank and is correct; Roborock never subscribes). The exposure is for the next adapter: an entities key named `water_level` th
- **A5-METRICS-5** `listeners/job_metrics.py:165` · both  
  watch_map's type annotation and the `int` value_type branch are both stale — the annotation declares 3-tuples while all three writers store 4-tuples, and no entry ever uses `int`  
  None today — purely a maintenance hazard. The annotation actively misdescribes the structure a future contributor must match, and the dead branch implies an int-valued metric channel that does not exist.
- **A4-POSE-6** `listeners/pose_sampler.py:10` · both  
  Module docstring still declares the sampler 'Capture-only / inert — nothing consumes pose_samples yet', but the W5c consumption wire has landed  
  No runtime effect on its own, but it materially understates blast radius: every defect in this file is currently read by maintainers as affecting an inert capture buffer, when in fact the samples drive which rooms an ext
- **A4-POSE-4** `listeners/pose_sampler.py:242` · future_brand_only  
  A zero or negative interval_s survives adapter registration (warn-only) and then splits the sampler in two: register() drops it, _sample_vacuum_once does not  
  Single-vacuum case: room-attribution pose sampling is silently disabled for the whole install — external runs finalize with no pose_samples and fall back to counter-only attribution, with no error surfaced anywhere. Mult
- **A5-POSE-6** `mapping/map_source.py:139` · both _(finder said MEDIUM; verifier corrected)_  
  `resolve_furnished_render` passes a stored placement transform through with no map-geometry stamp, so a re-mapped floor plan silently misaligns the art  
  After the vacuum re-maps or expands its floor plan, the furnished digital-twin art keeps rendering at its old placement over a map that has moved and rescaled underneath it — off by metres — with nothing in the payload,
- **A2-GEO-3** `mapping/map_source.py:191` · eufy _(finder said MEDIUM; verifier corrected)_  
  normalize_rendered CLAMPS out-of-grid pixels onto the map border instead of rejecting them, so off-grid raster cells and bad poses fold onto an edge rather than disappearing — diverging from the card's own decoder, which drops them  
  A room whose segmentation extends past the main grid gets a tap-region and label box pinned to the map edge. A saved zone drawn against the right edge can be filed to the wrong room because off-grid cells were swept into
- **A2-GEO-5** `mapping/map_source.py:314` · both  
  A room's normalized bbox excludes its last pixel row/column while width_m/height_m on the same dict include it (+1) — the two size descriptors disagree by exactly one cell, and Roborock's equivalent omits the +1  
  resolve_furnished_render ships per-room art placement transforms while the card places art inside the room's bbox and sizes to width_m/height_m — furnished art is scaled ~2.5% too large in a 2 m room and ~10% too large i
- **A2-GEO-2** `mapping/map_source.py:381` · eufy _(finder said MEDIUM; verifier corrected)_  
  zone_membership scans the entire room_outline raster with a per-cell normalize_rendered before the bbox reject, synchronously on the event loop — measured ~0.10 s per zone, ~1.0 s per dashboard read  
  On the first card load after zones exist without a stored area_m2, the whole Home Assistant event loop stalls for roughly a second — every other integration's updates, websocket pushes and service calls freeze with it. D
- **A2-GEO-6** `mapping/map_source.py:387` · eufy  
  zone_membership's docstring says the dominance vote counts cells 'whose centre falls inside the zone polygon'; the code tests the cell's top-left corner  
  The >=90% floor-dominance filing of a saved zone is computed over a cell set biased by half a cell on each boundary. For the Eufy minimum 0.5 m zone (10 cells across) that is a ~5% shift in the counted set per edge, enou
- **A5-POSE-7** `mapping/map_source.py:582` · eufy  
  An off-grid robot pixel is clamped onto the map edge and reported as a confident anchor — "off the map" is indistinguishable from "at the edge"  
  A robot whose reported pixel falls outside the map grid is drawn pinned to the map border as if that were its real position, and the live trail accumulates that clamped point (src/state/map.js:1032 `accumulateTrail`), so
- **A3-EXT-3** `mapping/map_source.py:686` · eufy _(finder said MEDIUM; verifier corrected)_  
  A dropped/renamed upstream geometry field degrades to a confidently WRONG map, not a loud absent one  
  After an upstream fork schema change, room regions, current-room and the robot anchor are all displaced by a large fixed offset with no warning in the log and no `unavailable` state — the card looks live and is wrong. In
- **A3-EXT-5** `mapping/map_source.py:808` · future_brand_only  
  Two room extractors disagree on the input coordinate frame and the dead one is the one under test  
  No user impact today (dead code). The trap is for the next brand adapter: the extractor that LOOKS canonical (it lives in the pure module, it has the descriptive name, it is the one with unit tests) divides raw device co
- **A1-LC-5** `mapping/map_source_coordinator.py:136` · both  
  `_commit_result` is blind last-writer-wins across the storage path's two executor awaits — a refresh started before a map switch can commit after a newer one  
  Until the next tick (up to 60s, sooner if the card is polling), the snapshot and the map_overlays sensor serve the previous map's rooms/anchors under the new map — and since neither consumer compares `entry['map_id']` to
- **A1-LC-4** `mapping/map_source_coordinator.py:266` · eufy _(finder said MEDIUM; verifier corrected)_  
  The same mtime early-return skips `_apply_inmem_pose_to_result`, freezing the robot/dock/current_room/path overlays for as long as the store file is unchanged  
  The map_overlays sensor's state (current room) and its `robot_anchor`/`dock_anchor`/`robot_heading` attributes stop advancing while the robot is cleaning — they only step forward when the fork happens to flush its Store
- **A5-POSE-5** `mapping/map_source_coordinator.py:266` · eufy _(finder said MEDIUM; verifier corrected)_  
  `_refresh_storage_map_source`'s mtime early-return bypasses the live-pose override entirely, re-serving the frozen pose it exists to kill  
  On the storage backend the dashboard snapshot and the map-overlays sensor report the robot at a position and in a room it left minutes ago, with no error and no staleness marker — and the sensor's recorded room-over-time
- **A5-POSE-3** `mapping/map_source_coordinator.py:491` · eufy _(finder said MEDIUM; verifier corrected)_  
  The pose-geometry .storage read skips the `store_version` guard that every other reader of the same file applies  
  After a fork store-schema bump, the map keeps rendering correctly from memory while the robot dot, the live trail and the current-room highlight are computed from stale-schema geometry — and the one designed signal for t
- **A5-POSE-4** `mapping/map_source_coordinator.py:528` · eufy _(finder said MEDIUM; verifier corrected)_  
  The live pose carries no freshness stamp, so a frozen `_robot_pixel` is reported as `present: True` forever — and the fork's own `_last_robot_render` timestamp is ignored  
  When the fork's map/pose channel stalls while the state channel keeps flowing, the card shows a confident live robot dot parked at a position the robot left long ago, and the pose sampler records that same wrong room eve
- **A4-RB-7** `mapping/map_source_runtime.py:260` · roborock  
  _walk and _structure_tree can only descend objects exposing __dict__, so a slotted/C-extension node is both an undiscoverable dead end and an uninformative diagnostic  
  When a python-roborock or HA core release moves the map behind a slotted container, the Roborock map source goes absent with reason `no_parsed_map` and a diagnostics dump that gives the maintainer nothing to tune — the f
- **A4-RB-5** `mapping/map_source_runtime.py:427` · roborock _(finder said MEDIUM; verifier corrected)_  
  roborock_geometry_drift_from_candidates pairs a MapData and a MapContent found by two independent BFS walks with no check they are the same map, and reports present:True regardless of the verdict  
  The on-device decode validator — the tool the notes record as having turned Roborock calibration 'from eyeball to data' — can report a bogus systematic drift that sends the maintainer hunting a flip/trim bug that does no
- **A2-GEO-4** `mapping/map_source_runtime.py:466` · roborock  
  correspondences_from_mapdata's docstring claims clamped corners are skipped; _mapdata_projector silently clamps with no detection, leaving the affine round-trip check as the only guard  
  No live mis-dispatch today. The risk is that the docstring reads as an implemented safety guard, so a future change to the projector, the trim/rotate config, or the residual tolerance would remove the only real protectio
- **A4-RB-8** `mapping/map_source_runtime.py:534` · roborock  
  correspondences_from_mapdata's docstring claims clamped corners are skipped; the code feeds them into the least-squares fit, turning a rare edge case into an unexplained zone refusal  
  If any room bbox corner projects outside the rendered image (rotation/trim edge cases), zone cleaning refuses with 'map projection failed validation' for the whole vacuum and no diagnostic points at the single bad corner
- **A4-RB-6** `mapping/map_source_runtime.py:760` · roborock _(finder said MEDIUM; verifier corrected)_  
  image_entity_object silently drops the only per-vacuum candidate root on any HA-internals change, while the presence gate still reports the map as present  
  An HA core refactor of the entity-component registry (or an image platform load order change) turns the per-vacuum map lookup into an account-wide guess with no error, no warning log, and a presence gate that still says
- **A1-SERVIC-7** `mapping/mapping_services.py:115` · Both (no runtime effect).  
  19 schemas (lines 115-301) are dead — defined once, referenced nowhere — and two of them are near-duplicate twins of LIVE schemas whose defaults would be rejected by the live validators  
  No runtime impact today. The risk is maintenance: two of the dead schemas are indistinguishable at a glance from the live ones they shadow, and their defaults have already diverged from the live validators.
- **A1-SERVIC-6** `mapping/mapping_services.py:406` · Both.  
  `backdrop_source` is the only enum-shaped field in the file left as free-form `cv.string`, is absent from services.yaml, and a typo produces a custom layout that can never hold segments and cannot be repaired  
  A hand-written create_custom_layout call with a near-miss value produces a layout that looks created, cannot be authored against, and cannot be fixed — only deleted. Not reachable from the card, which always sends the li
- **A3-IMAGE--8** `mapping/mapping_services.py:910` · Both; depends on whether Pillow is importable on the host.  
  Upload persists width/height as None when Pillow is unavailable and still reports saved:True  
  On a Pillow-less install a successful upload is recorded in a state that makes custom-segment authoring report a missing backdrop, and the variant row displays null dimensions. Confined to installs without Pillow, and th
- **A3-IMAGE--4** `mapping/mapping_services.py:933` · Both. _(finder said MEDIUM; verifier corrected)_  
  Re-uploading a map image does not invalidate image_segments, so a default analyze returns the previous image's segments  
  An automation or script that uploads a refreshed map export and analyzes it gets the previous map's room geometry back with a success-shaped response and no staleness signal. The card path is immune (it always passes for
- **A3-IMAGE--9** `mapping/mapping_services.py:945` · Both.  
  Layout existence is validated before the executor write and re-checked afterwards only by a silent isinstance guard, so a concurrent layout delete orphans the upload  
  A leaked PNG plus a phantom image_variants entry, and an upload the user believes attached to their layout that attached to nothing. Requires two service calls to overlap across a single await, so it is rare in practice;
- **A3-IMAGE--10** `mapping/mapping_services.py:964` · Both.  
  Four of the five services in this block have no services.yaml description, including the destructive delete_map_image  
  No runtime behaviour change — this is documentation/UI surface only. The consequence is that the one destructive service in this area (delete_map_image, which removes a file from disk) is the least discoverable and least
- **A3-IMAGE--11** `mapping/mapping_services.py:1089` · Both; any adapter that tunes min_area_pixels away from 1200. _(finder said MEDIUM; verifier corrected)_  
  min_area_pixels silently overrides the adapter's configured tuning because absent is coerced to 1200 before the is-not-None check  
  An adapter-level segmentation tuning knob that the adapter-config reference documents as configurable is silently inert for the omit-the-field case, so small rooms vanish from the segmentation with no diagnostic. Masked
- **A4-CUSTOM-5** `mapping/mapping_services.py:1379` · Both — saved zones and queue zone steps exist for Eufy and Roborock alike. _(finder said MEDIUM; verifier corrected)_  
  _generate_saved_zone_id / _generate_custom_layout_id guarantee uniqueness only against LIVE ids, so an id is reused after a delete — and saved-zone ids are durably referenced by queue steps and run profiles  
  Wrong physical area cleaned by a saved queue step or run profile, with no warning — the failure class is the most serious in this subsystem, but the window is narrow (delete and create must land in the same wall-clock se
- **A4-CUSTOM-7** `mapping/mapping_services.py:1650` · Both.  
  set_custom_segments' user-facing description is two features stale — it claims map-level scope and an uploaded-backdrop requirement that the layout + live-dims paths superseded  
  Documentation precision only, but it is the load-bearing kind: the description is exactly what would have warned a caller about CUSTOM-1's implicit target, and it omits the two parameters that make the live-layout path u
- **A5-FURNIS-6** `mapping/mapping_services.py:1969` · both  
  Clearing a home-scope art placement setdefaults an empty home_art dict, flipping the 'no furnished data' sentinel from None to a confident empty payload  
  No visible effect today: the card's clear button only renders when hasArt is true (src/renderers/map.js:1581), so the empty-home_art state is unreachable from the UI, and the current consumers key off art_url/render_mode
- **A5-FURNIS-3** `mapping/mapping_services.py:2076` · both _(finder said MEDIUM; verifier corrected)_  
  _handle_set_room_viewport is the only furnished writer with no clamp and a corner-valued default — zoom:0 and cx/cy:0.0 persist verbatim  
  Latent today — say so plainly: docs/advanced/08-map-configuration.md line 270 records the per-room viewport as "service-only today, not yet a panel control", and the card reads no viewport (src/state/map.js: "Per-room ar
- **A5-FURNIS-5** `mapping/mapping_services.py:2130` · both — sharpest on Roborock, whose rendered image is trimmed to the occupied extent _(finder said MEDIUM; verifier corrected)_  
  hidden_regions are stored as normalized rects with no record of the frame they were authored against, so a re-map re-aims the masks onto different physical areas — and masks hide content by default  
  Map content silently disappears with no indication of why, on a map the user never edited — the mask looks like a rendering bug rather than stale state. Recovery exists but is undiscoverable unless the user remembers the
- **A5-FURNIS-4** `mapping/mapping_services.py:2162` · both _(finder said MEDIUM; verifier corrected)_  
  area_label_anchors are keyed by device room id and nothing prunes them on a room rebuild, so a re-import silently re-aims one room's dragged label onto a different room  
  This is the direct answer to 'does the edit survive a re-import?': the bytes survive, their meaning does not, and nothing detects it. Cosmetic in consequence (a mis-placed m² chip, not a mis-cleaned room) but silently wr
- **A6-ZONE-C-8** `mapping/mapping_services.py:2482` · Both (Eufy 0.5-10 m per side, Roborock 1 ft²-3.05 m²), per the caps quoted in the _handle_clean_saved_zones docstring at 2641-2642.  
  Zone size limits are not enforced at author time, contradicting the doc — an un-cleanable zone can be saved and only fails when the user taps clean  
  A zone that can never be cleaned is savable and looks valid in the list. The failure is loud (an error toast) rather than silent, hence LOW — but it is discovered at the wrong moment, and in a batch it blocks the other z
- **A6-ZONE-C-7** `mapping/mapping_services.py:2614` · Both.  
  Both clean handlers ignore the zone's `kind`, so a zone saved with any non-"clean" kind is still dispatched as a clean  
  Latent today: no UI produces a non-"clean" kind, so only a direct service call reaches this. It matters because the field is publicly accepted, publicly documented as extensible, and the failure mode when someone uses it
- **A7-ROBORO-7** `mapping/roborock_raw_map.py:96` · roborock  
  The IMAGE-block dimension guard is `header_len >= 16`, but the four dims occupy the LAST 16 bytes of a header whose first 8 are the fixed type/len fields — anything under 24 reads dims out of the header's own metadata  
  Not reachable on a well-formed v1 blob (roborock uses >= 24-byte IMAGE headers). It matters as the module's stated defence posture: the docstring at lines 14-16 says the byte walk is 'mirrored from vacuum-map-parser-robo
- **A7-ROBORO-5** `mapping/roborock_raw_map.py:198` · roborock  
  Two functions in this module read the same `flip_y` key with OPPOSITE defaults, so a decoded dict missing the key renders flipped but drift-checks unflipped  
  Latent today: decode_roborock_v1_segments unconditionally sets flip_y True (line 126), so no shipped path produces a dict without the key. It bites the first time anything else builds a decoded dict — a b01/Qrevo decoder
- **A7-ROBORO-2** `mapping/roborock_raw_map.py:200` · roborock _(finder said MEDIUM; verifier corrected)_  
  raster_room_bboxes runs an O(width*height) pure-Python per-pixel loop directly on the Home Assistant event loop  
  Downloading diagnostics stalls the entire HA event loop — every integration, every automation trigger, the frontend websocket — for the duration of the scan. On x86 that is roughly 0.1-0.3 s for a mid-size map; on a Pi-c
- **A7-ROBORO-6** `mapping/roborock_raw_map.py:284` · roborock  
  geometry_drift reports max_center_delta: 0.0 when there are no common rooms — an optimistic accumulator that survives an empty loop  
  Diagnostics-readability only. The drift block is the tool a maintainer reads to decide whether the Roborock decode is correct on a real device; 'max_center_delta: 0.0' next to 'aligned: false' invites reading the geometr
- **A2-POLYGO-8** `mapping/segment_primitives.py:305` · Both (brand-agnostic custom-layout authoring)  
  A malformed primitive is silently skipped mid-segment, so a partially-drawn room saves as a success with no signal in the response  
  A card-side serialisation regression (a renamed field, a missing key on one shape type) degrades silently to a partial room rather than failing loudly, and the replace-all save makes the partial version canonical. `skipp
- **A2-POLYGO-6** `mapping/segment_primitives.py:342` · Neither at runtime (Eufy CV thresholds are empirically tuned); affects future adapter authors, which is exactly this module's advertised audience  
  `compactness` docstring claims 'Range 0-1; 1 = circle' - the attainable maximum is pi/4 and a circle scores LOWER than a square  
  No runtime defect - segmentor.py's thresholds (e.g. `compactness < 0.08` for `fragmented_candidate`) were tuned empirically against the actual function. The harm is to the stated purpose of this module: its header calls
- **A2-POLYGO-7** `mapping/segment_primitives.py:526` · Neither at runtime (Eufy CV only, thresholds empirically tuned); affects future adapter authors  
  `normalized_color_features`' luminance normalisation provably cancels out - the Rec.709 weights are dead arithmetic and tuning them changes nothing  
  No behavioural defect - the output is correct chromaticity and segmentor.py's hue clustering is tuned against it. The trap is for maintenance: the docstring says 'illumination-normalized chromaticity features' and the co
- **A6-TRK-5** `mapping/tracker.py:47` · both _(finder said MEDIUM; verifier corrected)_  
  _norm_room_name normalises differently from slugify_room_name — it merges room identities that rooms/ keeps distinct, and lacks the NFC canonicalisation slugify was given specifically to prevent this  
  Case (a): live dwell is attributed to the wrong room id whenever two rooms' names differ only in a separator character, and the card's reanchored timeline marks the wrong room complete. Case (b): for non-ASCII room names
- **A6-TRK-6** `mapping/tracker.py:196` · both  
  Dock-drift append rewrites the entire log file on every reading, and a failed write silently forfeits that drift event via the already-committed _last_dock_pos  
  On an SD-card or eMMC HA install the rewrite amplification is real flash wear for a purely diagnostic log; the cost scales with how often the reported docked position jitters, which is exactly what the log exists to meas
- **A6-TRK-7** `mapping/tracker.py:286` · both  
  start_job/end_job are dispatched to an executor thread on the strength of a comment describing disk I/O that start_job does not perform  
  No user-visible failure proven: the individual dict operations are GIL-atomic and the interleaving window is a handful of bytecodes, so at worst one position sample is misrouted at job start. The real cost is that a fals
- **DR-MAP-1** `maps/map_manager.py:62` · both · `direct read`  
  get_map_bucket returns a DETACHED dict on a miss and live storage on a hit  
  Mutation through the getter persists or silently vanishes depending on whether the map already exists -- the shape audit #1 found (a claim written to a copy). Sibling ensure_map_bucket uses setdefault and always returns
- **DR-MAP-2** `maps/map_manager.py:95` · both · `direct read`  
  get_vacuum_maps_summary mixes a live room_count with CACHED enabled/disabled counts  
  room_count is live len(rooms); enabled_room_count/disabled_room_count come from the stored summary block. Anything writing rooms without recomputing summary makes them disagree in one payload.
- **A3-CRUD-6** `maps/map_manager.py:181` · both _(finder said MEDIUM; verifier corrected)_  
  Both room writers auto-enable and auto-approve rooms the user has never seen (DQ-Q-5 extension: the live instance is save_managed_rooms, not rebuild_map)  
  A segment that appeared since the last save — a re-segment splitting one room in two, or a stray CV artefact — is added to the map already enabled, already approved and already floor-type-confirmed by the next `save_mana
- **A1-ID-6** `models/models.py:162` · both  
  RoomRecord documents grants_access_to as 'list[str] — room slugs' but every producer and consumer stores integer room ids  
  No current runtime defect; it is a loaded trap on the only place a developer looks up the field's namespace, in the exact subsystem where mixing the id and slug namespaces produces wrong-room behaviour.
- **INF-3** `models/models.py:257` · both · `direct read`  
  VacuumCapabilities is a never-constructed dataclass whose field names do not exist in the real capability payload  
  The live capability map is built by core/capabilities.py:353-400. Five of VacuumCapabilities' fields do not exist in it: supports_map_selection (real key supports_active_map), supports_dock_empty (real key supports_empty
- **EP-4** `number.py:7` · both · `direct read`  
  Module comment asserts 'no polling'; the one class that polls is the one relying on it  
  The comment `# All number entities write directly to manager storage; no polling.` sits above PARALLEL_UPDATES = 0. Verified as a claim: NumberEntity, unlike ButtonEntity, does NOT set _attr_should_poll = False, and Eufy
- **A5-PP-RP-7** `planning/run_plan.py:125` · future_brand_only _(finder said MEDIUM; verifier corrected)_  
  _settings_profile_display hardcodes the Eufy-era built-in profile-name set and takes no vacuum_entity_id, so a brand with its own profile keys renders every room as "Custom"  
  A future adapter that declares its own `room_profiles.builtins` keys (the block is adapter-owned and free-form) gets `is_custom = True` for every room whose profile resolves cleanly, so the pre-run plan, the water-estima
- **A5-PP-RP-8** `planning/run_plan.py:142` · future_brand_only  
  The water-off suppression in _settings_profile_display compares against the literal "off" instead of the brand's no-water value  
  A brand whose no-water label is "None", "Closed" or a localized string gets "Water: None" appended to every vacuum-only room's profile subtitle in the pre-run plan — cosmetic, but it is the same hand-copied-literal famil
- **A6-PP-EST-H2O-2** `planning/run_plan.py:237` · future_brand_only _(finder said MEDIUM; verifier corrected)_  
  A declared water_rates table REPLACES the core table wholesale, so an adapter that omits "off" bills 4.0 ml/min for water-off mop rooms — contradicting the comment that asserts the invariant  
  For the next adapter that declares measured rates, every mop-mode room with water turned off is billed as if it were mopping at a mid-range flow rate, inflating the job total and firing spurious "Not enough clean water"
- **A6-PP-EST-GUESS-1** `planning/run_plan.py:378` · eufy _(finder said MEDIUM; verifier corrected)_  
  estimate_job_water_usage drops the timeline's source/sample_count provenance, so default-guess room timings are presented as a measured "Job will use N ml"  
  On a fresh map, or any room whose settings combination has never been run (the learned key includes clean_mode, passes, carpet, intensity and edge_mopping), the entire water figure is derived from a constant guess yet is
- **A6-PP-EST-LBL-1** `planning/run_plan.py:436` · both  
  _room_surface_labels is fed a key that resolved_rooms never carries, so floor_type_label is always None at both display sites  
  Every consumer that reads `floor_type_label` off a resolved-room row gets null (src/renderers/rooms.js:1607, src/state/rooms.js:696). The room list happens to survive because it reads the label from the room ENTITY attri
- **A6-PP-EST-CLAMP-1** `planning/run_plan.py:476` · eufy  
  Tank-remaining ml is unclamped while its own percent is clamped to [0,100], and robot_internal_tank_ml is reported but never used in any calculation  
  A shortfall renders as a self-contradictory "-450 ml (0%)". And an adapter author is required by the schema to measure `robot_internal_tank_ml` on real hardware for a value the estimator never consults.
- **INF-8** `planning/run_plan.py:883` · both · `direct read`  
  The one call site step_types' docstring reasons about by name hand-copies the tuple instead of importing it  
  step_types.py's docstring says 'The leading/trailing break-trim in planning.run_plan is deliberately the second set too' and closes with 'a caller that reaches for the set is one `and` clause away from re-creating the dr
- **A5-PP-RP-4** `planning/run_plan.py:902` · both _(finder said MEDIUM; verifier corrected)_  
  The collapse fallback's `all_ids` is provably always [] — and the unit test manufactures the very key the real engines never emit  
  A stepped plan whose breaks are all trimmed (leading and/or trailing) runs as one flat clean using each room's GLOBAL stored settings instead of the per-group settings the card wrote into the step — e.g. `[room_group(kit
- **A5-PP-RP-6** `planning/run_plan.py:1458` · roborock _(finder said MEDIUM; verifier corrected)_  
  A stepped Roborock run enforces clean order but still tells the user the order is advisory  
  Every stepped Roborock run with two or more rooms displays "Cleaning order shown here is advisory: this vacuum cleans rooms in the order saved in its own app (set a cleaning Sequence there to enforce it) or optimizes the
- **A3-PP-CRUD-8** `profiles/manager.py:73` · both  
  Generated profile ids are local-time second-resolution and saves have no exists check, so two saves in one second silently destroy the first  
  A user's saved room profile or run profile is destroyed with no error and no way to recover it. Reachable from an automation or script that saves several profiles in a loop; not reachable from the card's own save flow, w
- **A4-PP-RP-5** `profiles/manager.py:77` · both _(finder said MEDIUM; verifier corrected)_  
  Run-profile ids are generated at one-second resolution and assigned without a collision check, so two saves in the same second silently overwrite each other  
  A script or automation that saves two run profiles back to back ("Quick" then "Deep" for the same map) ends up with one — the first is destroyed with no error, and the response even hands back the colliding id as if it w
- **A3-PP-CRUD-7** `profiles/manager.py:104` · both  
  _protected_room_config is the only writer in the finalize pipeline and it stamps the Eufy literal "Off" onto every non-mop room, on both brands  
  On Roborock every vacuum-mode room's stored water_level is 'Off' where the brand's declared value is 'off'. Dispatch is safe (dispatch/manager.py:390 lowercases before rank lookup) and profile matching is safe (`_normali
- **DQ-PAY-6** `profiles/manager.py:108` · roborock _(finder said MEDIUM; verifier corrected)_  
  _protected_room_config stamps the Eufy literal "Off" into every non-mop room's water_level regardless of brand, on the path into the payload builder  
  On a mop-settable Roborock the room editor's water chip row (strict `===` against the lowercase option values) renders nothing as selected for any vacuum-mode room, so the room reads as unconfigured. The value survives o
- **A6-PP-EST-TD-1** `profiles/room_profiles.py:14` · both  
  TypedDict drift: ProfileRecord's "all always present" claim is false for the shipped Roborock catalog, and capability_gated is declared bool but written as a dict  
  No runtime crash today — every consumer routes through `normalize_room_profile`, which `.get()`s with defaults (and re-injects "Quick", the known DQ-Q-4 leak). The impact is that the TypedDicts no longer describe the dat
- **DQ-Q-4** `profiles/room_profiles.py:209` · roborock _(finder said MEDIUM; verifier corrected)_  
  normalize_room_profile re-injects the Eufy literal "Quick" for clean_intensity, defeating Roborock's deliberate omission of the axis  
  Applying a room profile to a Roborock room stamps `clean_intensity="Quick"` — a value from a brand whose intensity option list (`clean_intensity_options`) is deliberately absent (adapters/roborock/adapter.py:241). The ca
- **A1-PP-RES-6** `profiles/room_profiles.py:209` · roborock _(finder said MEDIUM; verifier corrected)_  
  normalize_room_profile injects the Eufy literal "Quick" whenever the brand's normalize_defaults omits clean_intensity, and apply_room_profile_to_config PERSISTS it into Roborock room storage  
  A Roborock user applies any room profile and the room permanently acquires clean_intensity="Quick" — a capitalized value for an axis the Roborock adapter declares no options for (clean_intensity_options deliberately abse
- **A1-PP-RES-9** `profiles/room_profiles.py:366` · both  
  Dead branch in resolve_profile_name_for_constraints, and the carpet downgrade only knows the four framework built-in names  
  Dead code that reads as a live guard (a future edit to the alias table would silently change which branch fires). The custom-profile gap is display-only inconsistency today, because clean_mode is taken from the room rega
- **A2-PP-CAP-3** `profiles/room_profiles.py:496` · eufy _(finder said MEDIUM; verifier corrected)_  
  clean_intensity has no capability flag and reaches the Eufy wire on devices whose capability detection just concluded the intensity axis is absent  
  On a Eufy model outside the x10/x8 families (adapters/eufy/adapter.py:226, `"supports_path_control": model_family in {"x10", "x8"}`) with no cleaning-intensity entity, the framework has determined the device has no inten
- **A2-PP-CAP-6** `profiles/room_profiles.py:509` · roborock  
  apply_capability_gate hardcodes the Eufy literal "Off" in three places for the framework's own 'no water' concept  
  Contained today. `dispatch/manager.py:409` ranks with `str(room.get(field) or "").strip().lower()`, so the mop-intensity pre-call on a settable-mop Roborock still resolves "Off"→"off" correctly; and queue_engine.py:303 s
- **DQ-Q-6** `profiles/room_profiles.py:519` · future_brand_only  
  apply_capability_gate and _protected_room_config hardcode Eufy display literals for the framework's 'no water' / 'default path' concepts  
  No wrong physical action on either shipped brand. Structural: the framework's "no water" concept is expressed as the string `"Off"` in the one function every brand's payload must pass through, so a brand whose no-water v
- **DQ-DE-5** `queue/dispatch_engines.py:211` · both  
  Engine phase envelopes omit queue_room_ids/queue_rooms, making the run-plan group-union computation dead code and emptying queue_rooms on every phase advance  
  No user-visible wrong result today, but both are unearned rescues rather than correct code. (a) is masked only because `included_room_ids` currently happens to equal the union of the groups' rooms — `apply_run_profile` d
- **DQ-DE-3** `queue/dispatch_engines.py:316` · future_brand_only _(finder said MEDIUM; verifier corrected)_  
  DreameSegmentEngine's documented 'direct envelope (no command)' is unreachable — an omitted command defaults to Eufy's room_clean  
  Whoever enables the shipped-but-unused dreame_room_clean template and follows the engine's own documentation produces a service call the device cannot execute — the clean never starts, and because `_dispatch_clean_payloa
- **DQ-PH-5** `queue/queue_engine.py:62` · both  
  QueueEntry / PayloadItem / ActiveJobSnapshot describe a shape the module has never emitted, and disagree with build_active_job_state on the fields it does write  
  No runtime effect — these are documentation only. But they are the first thing a reader (or a future brand adapter author) opens to learn the snapshot contract, and they describe a different system. The module comment at
- **DQ-PAY-5** `queue/queue_engine.py:182` · future_brand_only _(finder said MEDIUM; verifier corrected)_  
  _write_room_field's value_map is fail-open: an unmapped canonical value is emitted raw, and the framework itself injects Eufy literals no adapter can declare a mapping for  
  Any brand whose wire vocabulary differs from the canonical one gets un-translatable framework literals on the wire for capability-gated fields — a malformed payload the device rejects, or a wrong setting applied — and th
- **DQ-Q-7** `queue/queue_engine.py:242` · both  
  build_room_clean_payload treats an empty queue_room_ids as "no filter" rather than "no rooms", so a cleared queue yields a payload containing every enabled room  
  No physical wrong action today: the DISPATCHED payload comes from `_build_effective_start_plan` -> `_build_dispatch_phases`, whose `queue_room_ids` is derived fresh from `effective_rooms` in the same call (run_plan.py:13
- **DQ-PAY-7** `queue/queue_engine.py:294` · future_brand_only  
  clean_passes_field: null omits passes in two engines but produces a None dict key in build_room_clean_payload  
  A brand whose room-clean command carries no per-room pass count cannot express that on the `eufy_room_clean` template: instead of omitting the field it gets a `{None: 1}` entry, which fails JSON serialisation or reaches
- **INF-6** `repairs.py:1` · both · `direct read`  
  The repair flow is unreachable - nothing ever raises an issue - and the doc asserts the opposite  
  VERIFIED: a repo-wide grep for async_create_issue / ir.create_issue across custom_components returns ZERO hits, so async_create_fix_flow is never invoked. doc 02 §10 states 'Currently raised by the setup workflow when st
- **EP-7** `room_entities.py:87` · both · `direct read`  
  _async_update_room silently drops non-managed keys from a mixed update  
  Branch 2 filters `updates` to a hand-maintained managed_field_names set and, if ANY managed key is present, routes only that subset to update_room_fields and RETURNS -- so every non-managed key in the same call is discar
- **EP-8** `room_entities.py:217` · both · `direct read`  
  Hand-copied room defaults, including two that disagree about the same missing key  
  extra_state_attributes re-declares defaults by hand rather than deriving them: profile_name defaults to the literal 'vacuum_quick' where the canonical DEFAULT_ROOM_PROFILE_NAME is imported properly by three other modules
- **A6-AGX-3** `rooms/access_graph.py:559` · both _(finder said MEDIUM; verifier corrected)_  
  get_room_access_editor marks every unselected target unselectable when the graph is already broken elsewhere, with the contentless reason "Not selectable due to graph legality."  
  A consumer of the documented editor service sees every link greyed out with a message that explains nothing and blames the edge being offered rather than the pre-existing violation. The user cannot tell what to fix; the
- **A6-AGX-5** `rooms/access_graph.py:613` · both _(finder said MEDIUM; verifier corrected)_  
  The per-room editor's issue list drops graph-scoped issues, so it reports a room as problem-free on a map whose graph is invalid and blocking runs  
  The per-room diagnostic reports a clean bill of health for a room on a map where cleaning is blocked, and never surfaces the one issue ("no dock room") that is causing it. The user auditing rooms one at a time will find
- **A2-REC-7** `rooms/room_crud.py:118` · both  
  action='ignore' writes reconciliation_dismissed_at that no code ever reads — dismissed reviews resurface on every discovery  
  Dismissal is a no-op: identical reviews are recomputed on every discovery forever, including the permanent phantom review from REC-2. A maintainer reading the docstring believes suppression exists.
- **A3-CRUD-7** `rooms/room_crud.py:318` · both  
  get_managed_rooms returns the live stored rule dicts and metadata sub-objects by reference despite copying the outer containers  
  Any consumer that treats this response as a detached snapshot and mutates a rule entry writes straight through into persisted storage, so a change that was never meant to be saved is persisted by the next async_save. Lat
- **A3-CRUD-5** `rooms/room_manager.py:57` · both _(finder said MEDIUM; verifier corrected)_  
  A re-save resurrects a room the user explicitly rejected as a phantom — build_managed_rooms never consults rejected_rooms  
  A phantom segment the user deliberately banished comes back as a fully approved, enabled room with entities and a place in the clean queue, and the robot is sent to clean it on the next run. The user is never told; drift
- **SN-8** `sensor/__init__.py:91` · both · `direct read`  
  active_job_entities and its explanatory comment are dead  
  The dict is documented as keyed by (vacuum, map) 'so the job-finished handler can refresh the right sensor directly', and is populated, but never read; _handle_job_finished refreshes only room-history sensors. Behaviour
- **SN-9** `sensor/map_overlays.py:76` · both · `direct read`  
  native_value returns the literal string 'unavailable', colliding with HA's reserved state  
  VERIFIED AT SOURCE: `if not res.get('present'): return 'unavailable'`. That is indistinguishable in hass.states, templates, is_state() and the frontend from an entity that is genuinely unavailable, while the real diagnos
- **DR-ONB-5** `sensor/onboarding.py:55` · both · `direct read`  
  The sensor recomputes the entire onboarding summary twice per update  
  native_value and extra_state_attributes each call _get_summary() independently, and each call iterates every map building a full get_onboarding_state dict. A polling diagnostic entity does the whole aggregation twice per
- **SN-10b** `sensor/theme.py:75` · both · `direct read`  
  A raw stored null theme name renders as the string 'None' — valid, but not reachable in normal operation  
  Split half B of the original SN-10, and the half both lenses agreed on. `str(entry.get('name', 'none'))` returns Python's str(None) == 'None' for a stored null rather than the intended 'none', and an empty string yields
- **A5-FACADE-5** `services.yaml:1179` · both  
  services.yaml declares a REQUIRED 'carpet' field on save_user_room_profile and overwrite_room_profile that the voluptuous schema rejects  
  Calling either service exactly as the HA Developer Tools > Actions form renders it — the form marks Carpet required, so a user filling it in will include it — fails validation with an opaque 'extra keys not allowed' erro
- **A2-JOB-9** `services/_common.py:58` · both  
  resolved_call_data's docstring claims a "clear error" on unresolvable map_id; the actual failure is a bare TypeError, and no service in either module raises ServiceValidationError  
  A user on an adapter that declares no `active_map` entity (scalar/Tuya Eufy, or any brand-3 adapter) who omits `map_id` — which every schema marks Optional and every services.yaml field describes as "Leave blank to use t
- **A4-SETUP-4** `services/adapter_config.py:57` · both _(finder said HIGH; verifier corrected)_  
  save_adapter_config / delete_adapter_config declare no supports_response and return None on every rejection path — a rejected write is indistinguishable from a successful one  
  An automation or script calling save_adapter_config with a config missing adapter_id gets a clean successful service call and continues to the next step; nothing was written. The only evidence is a log line the user is n
- **A4-SETUP-14** `services/adapter_config.py:198` · both  
  get_vacuum_capabilities uses the raising get_manager() while its siblings in the same module use the tolerant .get() form, and it writes storage on a read-shaped service  
  Calling the capability service during a reload produces an unhandled KeyError instead of a clean error, and a read-only-looking call touches .storage on every invocation.
- **A6-DIAG-8** `services/dock.py:51` · future_brand_only  
  Dock event-type vocabulary is hand-copied into three places, none derived from the adapter that declares it  
  No user-visible defect on either shipped brand today. A third adapter that names its dock events differently gets `set_dock_event_count` rejecting every one of its own declared event types at the schema, with the fix req
- **A6-DIAG-7** `services/dock.py:59` · both _(finder said MEDIUM; verifier corrected)_  
  get_dock_action_status raises a raw TypeError when map_id cannot be auto-resolved — the only unwrapped handler in the three modules, and _common's docstring claims the opposite  
  Both brands hit this in the restart window and whenever the active-map entity reads unknown/unavailable (Eufy's `sensor.<id>_active_map` before the first map sync; Roborock's `select.<id>_selected_map` while the coordina
- **A1-WIRE-3** `services/dock.py:174` · both  
  Sixteen registered services documented as public API have no services.yaml descriptor, including set_dock_event_count whose five dock siblings all have one  
  A YAML author who follows docs/advanced/03-services.md to `set_dock_event_count` or any setup_* service finds it in Developer Tools -> Actions with no name, no description, and no field UI — just a bare data editor with
- **A6-DIAG-4** `services/errors.py:71` · both _(finder said MEDIUM; verifier corrected)_  
  acknowledge_error returns the same {"acknowledged": true} whether the latch was deleted, merely MARKED, or was never there — and both docstrings still describe the pre-audit delete semantics  
  A caller (card or automation) that wants to confirm the alert was cleared cannot: `acknowledged: true` is returned for a vacuum with no error at all, and the mid-run case reports the same success while the latch is delib
- **A6-DIAG-5** `services/errors.py:93` · both _(finder said MEDIUM; verifier corrected)_  
  get_recent_errors — a read-only service — creates and persists a durable error_tracker record for any entity_id the caller names  
  A mistyped or foreign `vacuum_entity_id` in an automation looks like a healthy vacuum with a clean error history — the user concludes there are no errors when in fact they queried nothing. The storage file accumulates pe
- **A6-DIAG-9** `services/maintenance.py:95` · both  
  Mutate-then-save is not atomic in all three write services: a save failure surfaces an error while the change has already taken effect in memory  
  On a storage write failure the user sees "Failed to save maintenance interval" (or, for the dock/reset services, an unhandled traceback) and reasonably re-checks or re-enters the value — but the change is already live an
- **A2-JOB-5** `services/queue.py:40` · both _(finder said MEDIUM; verifier corrected)_  
  Break schemas do not enforce the break_type→parameter dependency, and the two sibling schemas disagree on which break types exist  
  A YAML user builds a stepped queue with `add_queue_break: {break_type: wait, after_index: 2}`, gets a successful service call, and the break is never added. Their next run is a flat clean with no pause — the robot cleans
- **A2-JOB-6** `services/queue.py:51` · both _(finder said MEDIUM; verifier corrected)_  
  get_queue_steps returns `breaks` in a shape set_queue_breaks rejects — the documented read-modify-write round trip fails validation  
  The obvious automation pattern — call get_queue_steps into a response_variable, edit one break's minutes, send the list back through set_queue_breaks — fails with a voluptuous error the user has to reverse-engineer, beca
- **A2-JOB-8** `services/queue.py:151` · both  
  Queue mutators create and persist a storage bucket for any syntactically-valid entity id, including one that is not a vacuum this integration manages  
  A typo in an automation permanently accumulates junk vacuum/map entries in the integration's store, with no error and a response that says only "needs_two_rooms" rather than "unknown vacuum". Storage junk rather than a f
- **A3-ROOMS-8** `services/room_profiles.py:97` · both _(finder said MEDIUM; verifier corrected)_  
  delete_room_profile / rename_room_profile leave dangling profile_name references on rooms, which then silently resolve to a built-in preset  
  After deleting or renaming a custom profile, every room that used it reports selected_profile_name/'selected_profile_label' as 'vacuum_quick'/'Vacuum Only Quick' in the room editor and in get_effective_room_details, whil
- **A3-ROOMS-11** `services/room_profiles.py:122` · both  
  Error-surfacing is inconsistent across the area: rooms.py wraps 4 of 5 handlers, room_profiles.py wraps 0 of 8, access_graph.py wraps 0 of 2  
  The same root cause produces a readable error from one service and an unhandled-exception traceback plus a generic 'Unknown error' toast from its sibling. For the supports_response services the websocket call is rejected
- **A1-WIRE-4** `services/room_profiles.py:203` · both  
  get_room_profiles is the only one of the 79 registrations with no schema, so caller-supplied scoping arguments are accepted and silently ignored  
  A caller who passes `vacuum_entity_id` or `map_id` — a reasonable assumption given that every neighbouring room-profile service requires `vacuum_entity_id` — gets the global profile library back with no indication the ar
- **A3-ROOMS-10** `services/rooms.py:251` · both _(finder said MEDIUM; verifier corrected)_  
  save_managed_rooms is the most destructive service in the area and the only mutation registered without supports_response  
  The one service in this area that can replace a map's entire room set wholesale gives the caller nothing to check — not room_count, not the resulting room list. An automation cannot detect ROOMS-1 or ROOMS-2 even defensi
- **A5-RUNPROF-5** `services/run_profiles.py:71` · both _(finder said MEDIUM; verifier corrected)_  
  rename_run_profile accepts a blank name and silently relabels the profile 'Untitled', returning renamed:True — the sibling save rejects the same input  
  An automation renaming a profile from a template that renders empty (`name: "{{ states('input_text.profile_name') }}"` while the helper is empty/unknown/unavailable) destroys the profile's label — the user's named run be
- **A5-RUNPROF-7** `services/run_profiles.py:90` · both  
  get_saved_run_profiles and get_dashboard_snapshot lack the package's try/except wrap; an unresolvable map_id surfaces as a raw TypeError, contradicting resolved_call_data's docstring  
  During an HA restart or while the vacuum's active_map entity is unavailable, the card's primary read (get_dashboard_snapshot) and the run-profile library read fail with an unactionable internal error instead of a message
- **A5-RUNPROF-6** `services/run_profiles.py:152` · both _(finder said MEDIUM; verifier corrected)_  
  overwrite_run_profile with no rooms enabled returns overwritten:False as a success — the raise gate matches one literal reason, not the failure flag  
  An automation that refreshes a stored profile after a run — the common 'clean these rooms, then remember what I just did' shape — silently no-ops when the selection has already been cleared, and the user believes the pro
- **A4-SETUP-9** `services/setup.py:131` · both _(finder said MEDIUM; verifier corrected)_  
  adapter `setup.steps` is never validated at registration despite two docstrings and the schema claiming it is; two declared step IDs have no completion writer and strand the wizard permanently  
  Either the wizard silently skips a mandatory step and declares setup complete, or it pins next_step to a step no service can ever mark done and the user is stranded with a permanently incomplete onboarding panel and setu
- **A4-SETUP-12** `services/setup.py:184` · both _(finder said MEDIUM; verifier corrected)_  
  setup_get_map_rooms returns a success-shaped empty room list when the runtime manager is missing — the caller cannot tell "integration not loaded" from "map has no rooms"  
  During the reload window that setup_add_vacuum itself schedules (services/setup.py:165), the room editor opens with zero rooms and no error. If the user then clicks Save, the card sends `enabled_room_ids: []` (src/bindin
- **A4-SETUP-8** `services/setup.py:222` · both _(finder said MEDIUM; verifier corrected)_  
  setup_save_rooms stamps the setup step complete unconditionally, unlike both of its sibling step-advancing handlers  
  The setup panel reports the wizard complete and `setup_complete: true` for a vacuum whose map now has zero configured rooms. The user is told onboarding finished; the queue has nothing to build from.
- **A4-SETUP-13** `services/setup.py:336` · both  
  setup_set_map_camera stores an unvalidated entity_id and reports success even when the entity does not exist  
  A typo in the camera entity id is confirmed as set. The Map view then shows no live backdrop and the user has no signal connecting the two — the stored value looks correct in setup_get_status (status.py:207) because that
- **A4-SETUP-15** `services/setup.py:353` · both  
  None of the 10 setup_* services and 5 of the 6 adapter-config services have services.yaml or translation entries  
  In Developer Tools → Actions these 15 services appear with the raw slug and no field editors, so the only way to call them correctly is to hand-write YAML from the prose docs — for services including the two most destruc
- **A5-RUNPROF-8** `services/snapshots.py:78` · both  
  No service here checks that vacuum_entity_id is a vacuum this integration manages; unknown ids create durable storage buckets, and a read service writes  
  A typo'd entity id in an automation gets a plausible-looking response (`{"vacuum_entity_id": "vacuum.typo", "pause_timeout_minutes_default": 0}`) instead of an error, so the user's real setting change appears to have wor
- **DR-SETUP-3** `setup/drift.py:336` · both · `direct read`  
  Two unguarded int(key) coercions on drift-history keys, in a module that guards every other one  
  The stale-entry prune and the history-only new-room branch both coerce a storage key with no try/except, while _room_lookup and _list_configured_room_ids in the same file wrap identical coercions in except (TypeError, Va
- **DR-SETUP-4** `setup/protection.py:44` · both · `direct read`  
  Protection evaluation calls .get() on map buckets and room records without isinstance guards  
  The imported-map comprehension and the has_rules / has_access_graph scans assume dicts, where drift.py consistently checks isinstance(bucket, dict) first. A malformed record raises AttributeError out of evaluate_map_prot
- **A3-PORT-7** `themes/manager.py:42` · both  
  _clean_theme_tags coerces non-string items with str(), reachable only through the unvalidated import payload, and silently drops rather than truncates over-long and over-count tags  
  An imported theme arrives with junk tags like `{'a': 1}` or `none` shown in the card's tag/filter UI, which the user then has to notice and clean up by hand. Separately, a theme legitimately tagged with a 40-character ph
- **A2-DRAFT-4** `themes/manager.py:111` · both _(finder said MEDIUM; verifier corrected)_  
  _get_vacuum_theme creates per-vacuum draft state for ANY well-formed entity id, so update_working_draft / revert_draft / set_active_theme return ok:true for a vacuum that does not exist and persist a record nothing can reach  
  A user writing a theme automation, or copying a call between two vacuums and mistyping the entity id, gets back {"ok": true, "draft_dirty": true} — a success response describing edits that landed nowhere. The card for th
- **A3-PORT-8** `themes/manager.py:172` · both  
  The _get_theme_library_entries docstring claims write-time normalization that does not exist — _normalize_theme_entry is called from two sites and both are read paths  
  No direct user-visible symptom on its own — this is the enabling condition for PORT-1 and PORT-2. Its cost is that a maintainer reading this docstring reasonably concludes stored theme entries are already sanitised and a
- **A2-DRAFT-7** `themes/manager.py:224` · both  
  _minimal_theme_mutation_response cannot express 'there is now no active theme' — a None active_theme_id is dropped from the payload rather than sent as null  
  A card whose cached activeThemeId is stale — for example after another browser tab or an automation deleted the active theme — keeps showing that dead theme as selected through any number of draft updates or reverts, bec
- **A1-CRUD-8** `themes/manager.py:350` · both  
  rename_theme accepts a blank/whitespace name and silently stores "Untitled"; no duplicate-name check on rename or save_theme_as_new  
  A rename with an accidentally blank value silently renames the theme to 'Untitled' rather than being rejected; repeated saves/renames can produce several identically named presets that the grid renders indistinguishably
- **A1-CRUD-6** `themes/manager.py:351` · both  
  rename_theme writes into the raw stored entry with no isinstance-dict guard, unlike set_theme_tags — a corrupt entry raises TypeError out of the service  
  An unhandled TypeError surfaces from the rename_theme service instead of a clean ServiceValidationError, if storage is ever corrupted or hand-edited. Latent — no in-tree path writes a non-dict library entry.
- **A1-CRUD-7** `themes/manager.py:370` · both  
  set_theme_tags silently discards tags past 16 or longer than 32 chars and still returns ok:True  
  A user adding a 17th vibe tag, or importing a theme whose tags are long, watches tags vanish after the round-trip with no explanation of the limit. Cosmetic; nothing else is lost.
- **A3-PORT-5** `themes/manager.py:554` · both  
  Import name de-duplication appends '(imported)' at most once, so repeated imports of the same theme produce multiple indistinguishable library entries  
  After importing the same theme file three or more times (a normal thing to do while iterating on a shared theme, or after a failed-looking import), the library lists two or more entries all named 'Ocean (imported)'. The
- **A3-PORT-2** `themes/manager.py:643` · both _(finder said HIGH; verifier corrected)_  
  _import_scoped clears a floor namespace in all three buckets but only re-applies the buckets the payload happens to contain, silently destroying per-layer opacity settings while reporting success  
  A user who has tuned their wood-floor layer opacities imports a colors-only 'oak palette' file — hand-authored, shared by another user, or exported by an older build from before the layer-opacity tokens shipped in v1.6.0
- **A2-DRAFT-6** `themes/manager.py:654` · both  
  _import_scoped strips matching keys out of the working draft but never recomputes draft_dirty, so the draft can be left empty with the dirty flag stuck True  
  After a scoped floor-texture import the card's footer keeps 'Discard' and 'Save changes' enabled (src/renderers/theme.js:1042, 1120-1133 gate purely on draft_dirty) with an empty draft behind them. The user sees a persis

</details>

### Applied

**105 findings** closed by a landed packet. Not open work, but kept
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

### Examined and deliberately not fixed

Real behaviour, but reaching it requires using the feature against its own purpose.
Recorded so it is not re-reported as a new finding, and documented where it lives.

- **DR-DBG-5** `debug_capture.py:263` — The restore guard cannot distinguish its own DEBUG from a user's mid-capture `logger:` DEBUG  
  Reaching it requires starting the flight recorder — a tool whose entire purpose is to avoid enabling `logger:` debug — and then enabling `logger:` debug anyway, mid-capture. That is a user footgun, not a defect: the two actions contradict each other. Documented in the module and in the post rather than guarded against.
- **SN-10a** `sensor/theme.py:75` — KILLED: the claim that a hand-edited theme import can store a raw null name  
  KILLED — the reachability premise is fatal to the claim AS RECORDED. Stage B's reproducer executed it: import_theme does `name = str(source_theme.get('name','')).strip()` (themes/manager.py:537), so a JSON null becomes the STRING 'None', which is truthy and passes the `if not name` gate. The stated entry path — 'reachable via a hand-edited import' — cannot produce the defect. That sentence was mine and it was wrong. Split from the original SN-10 so Corpus C does not have to assert the LINE is correct; the line-level defect survives as SN-10b.

### Carried forward from before the audits

- **`active_boundaries` round-trip (SEG-1)** — Deferred deliberately: it changes a persisted record field and warrants separate scrutiny.
- **Pose sampler predicates** — Two call sites were deliberately not re-pointed at the shared in-flight helper, because doing so would silently add `paused` to what gets sampled. Wants its own change.
- **Roborock room migration** — Room *creation* now takes brand-correct defaults. Rooms created before that still carry the old values. Stored user data, so repairing it is a product decision.
- **Three card strings untranslated** — `common.service_failed`, `learning.room_skipped`, `learning.run_incomplete_toast` are English-only across the 17 non-English locales.
- **Card: the two failure-renders-as-success paths (FE-ERR-1 / MZ-2)** — Blocked on a backend `supports_response` change.
- **Card: the qualification gap (CC-5)** — Surface provenance, truncation and absent data honestly rather than as confident values.
- **Card: surface captured run errors (`run_errors`)** — The backend now carries app-started-run error evidence end to end. Nothing displays it.
- **OpenDyslexic font support** — Contract settled — English-only gate, one token override, glyph coverage proven per locale before offering another. No code written.
- **Roborock edge-mopping control removal** — RECONSTRUCTED — the original note was lost when the orchestrator replaced the generators' hand-maintained CARRIED lists before verifying the replacement; only the title survived, from a diff printed earlier in the same session. Reconstructed from current source: the Roborock adapter declares supports_edge_mopping False (adapters/roborock/adapter.py:177 and :580, plus three edge_mopping:False entries in vocabulary.py), while the card still renders edge-mopping controls (src/renderers/external-jobs.js:287-289, src/renderers/metrics.js:537/551). The obligation is to gate or remove that control on a brand whose adapter declares it unsupported. VERIFY THE INTENT WITH CHRIS before acting — the reconstruction is grounded in source, but it is not the original wording.

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

