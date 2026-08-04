# OPEN FIX CHECKLIST -- hostile audit campaign

> **RECONCILED 2026-08-04.** The unchecked list had drifted badly: of 27 entries,
> **19 were already landed** and simply never ticked — most inside RP-035 (the
> sensor/entity platform batch) and the RP-023 access-graph work. Verified by
> in-code fix markers whose comments describe the change in the past tense, not
> the problem. Ticked above.
>
> The count over-reported open work by ~2.5x, which is the inverse of the usual
> failure: an unaudited scope yields no findings and reads clean, but a stale
> LEDGER yields phantom findings and reads busy. Both are answered the same way —
> check the code, not the count.
>
> **CORRECTION, same day.** The first pass of this sweep used "does the code cite
> the finding id?" as the test and put **A2-POLYGO-6/-7** in the open column. Both
> were already fixed — the compactness docstring now derives the π/4 maximum and
> states that a digital disc scores π²/16, BELOW a square, and
> `normalized_color_features` had the dead Rec.709 arithmetic removed outright.
> Neither fix cites its finding id. **Absence of a marker proved nothing, exactly
> as flagged.** Read the code; the marker is a shortcut, not the test. 19, not 17.
>
> **AUDIT CLEARED 2026-08-04.** All five remaining findings worked: EP-5
> (c84e502), A5-PP-RP-2 (9898833), and DR-ONB-2 / A7-ROBORO-4 / DQ-ACT-6 in the
> closing commit. Nothing is left unchecked here except:
>
> - **A4-SETUP-6** — deferred by decision; map-scoped rejection, fix shape in the
>   adjudication, do it with the multi-map work.
> - **ENT-1** / **DIAG-1** — banked for the next release, DIAG-1 first.
>
> Two of the five turned out to be narrower than filed and are recorded as such
> rather than as clean fixes: **A7-ROBORO-4**'s offset is preserved but NOT
> applied (applying it is pose registration, which needs an S6 on the bench), and
> **DR-ONB-2**'s method has no production callers at all — fixed because the
> mechanism is real, but it should be deleted rather than left as a correct
> answer nobody asks for.


Durable ledger of every finding NOT yet applied. Generated from the audit JSON, not from
recollection. **This file lives in git-ignored `.claude/notes/` -- it does not survive a
machine loss.** Copy it somewhere backed up if that matters to you.

## Standing

| | |
|---|---|
| Fixes SHIPPED | audits #1-#6 + the adapter remainder, all deployed |
| Fixes APPLIED (landed packets) | **455** findings via 60 packets (CARD-1, CARD-2, CARD-3, CARD-4, CARD-5, CARD-6, CARD-7, CARD-8, CARD-9, RP-001, RP-002, RP-003, RP-004, RP-005, RP-006, RP-007, RP-008, RP-009, RP-010, RP-011, RP-012, RP-013a, RP-013b, RP-013c, RP-013d, RP-013e, RP-013f, RP-014, RP-015, RP-016, RP-018, RP-019, RP-020, RP-021a, RP-021b, RP-021c, RP-023a, RP-022, RP-024, RP-025, RP-026, RP-027, RP-028, RP-029, RP-030, RP-031, RP-032, RP-033, RP-034, RP-035, RP-036, RP-037, RP-038, RP-039, RP-040, RP-042, RP-043, RP-044, RP-045, RP-046) |
| Audits covered here | #7 dispatch+queue, #8 profiles+planning, #9 jobs execution, #10 rooms identity, #11 map source lifecycle, #12 listeners input, #13 services (public API), #14 core/manager hub, #15 integration script, #16 learning consumers, #17 themes manager, #18 mapping services |
| Open findings | **29** -- 2 open clusters (27 fully applied) + 27 singles |
| By severity | CRITICAL 0 / HIGH 3 / MEDIUM 13 / LOW 13 |
| Hardware validation | **5 packets** validated on hardware (RP-013a, RP-013b, RP-013d, RP-013e, RP-013f) across 2 brand(s): eufy (alfred, T2351); roborock (ivy, S6). Evidence in `_frozen/baseline/` |


> ### 1 REOPENED finding(s) — a landed packet was credited with a fix that
> does not hold. Closure is binary; findings are not.
>
> **#9:A3-REC-3** — credited to RP-013c, reopened 2026-08-02
> - **Evidence:** alfred job_2026-08-02T11-15-51 — a [kitchen] -> [entryway + hallway] run. The card showed Entryway for the whole 13m40s group phase and never advanced to Hallway.
> - **Why:** A3-REC-3 has TWO halves and RP-013c closed one. It made the FINALIZED record correct (completed_room_ids_cumulative carried at advance time, the finalizer's three-source union). MECHANISM NOTE 2026-08-03: that accumulated field has since been RETIRED — the same facts are now derived from the phase index (queue_engine.py:497 and learning/utils.py:322 both carry the tombstone comment). The closure still holds; only its mechanism changed. Do not read the original wording as a claim about live code. The LIVE path is untouched: _derive_active_job_current_room_id returns the first resolved_room not in the PER-PHASE completed_room_ids, and record_completed_room never fires inside a group dispatch, so current_room_id pins to queue_room_ids[0] for the phase's duration. C4's own stated fix — 'record the phase as a phase rather than as room[0]' — is the half still open. STATUS 2026-08-03: RP-047 (a) landed (6831ccd, core/manager.py +51 with tests in test_manager_progress.py) and the snapshot now presents the phase. This finding stays REOPEN until a fresh group-phase hardware run confirms the card no longer pins to room[0] — (a) is the mechanism, the run is the evidence.
> - **NOT fixable by:** Advancing 8 -> 4 partway through. The record's own allocated:true / allocation_group_size:2 means the split was NOT observed; inventing a boundary is the same synthesis RP-013c's REVIEW pin forbids.

`verified` = I personally opened the file and confirmed the mechanism at source. Everything
else was reported by a finder and confirmed by both adversarial verifiers, but not
independently re-checked by me.

**Re-verify before scoping.** Audit #4 taught this the expensive way: RC-3 and RC-7 were both
substantially stale by the time they were worked, because fixes had landed in between. An
audit is a snapshot, not a ledger.

---

## TIER 1 -- clusters. Several findings, ONE fix each. Do these first.

### C1. Live-id resolution falls back to STALE stored ids **[VERIFIED AT SOURCE]** — **2/2 applied**

- **Seam:** `dispatch/manager.py:317`
- **Closes:** ~~DQ-DE-1~~ ✅ RP-007 (`4c42482`), ~~DQ-ACT-1~~ ✅ RP-007 (`4c42482`)
- **What breaks:** A single-target strict-order phase makes `dropped` non-empty EQUIVALENT to new_segments==[], so the 'live source unavailable' fallback fires for a target that was resolved and REJECTED. The robot cleans a different physical room, and the watchdog re-dispatches the same stale id up to 3x.
- **Fix:** Distinguish 'live source unavailable' (keep stored ids) from 'targets resolved and rejected' (skip or abort). Also correct phase_runner.py:1029, whose comment describes behaviour the code does not have.
- [x] applied  [ ] tested  [ ] hardware-checked

### C2. Cancel is lost across the dispatch chain's awaits *(not independently verified)* — **2/2 applied**

- **Seam:** `jobs/phase_runner.py:553`
- **Closes:** ~~A1-WD-1~~ ✅ RP-010 (`3e9e969`), ~~A2-CAN-1~~ ✅ RP-010 (`3e9e969`)
- **What breaks:** _cancel_in_flight is read ONCE per attempt, then four sequential awaits follow (global pre-calls, per-room live settings, live map refresh, dispatch) with no re-read. The user cancels, the robot returns to base, then drives back out and cleans the phase's room.
- **Fix:** Re-read the job (or re-check the cancel flag) between each await inside _dispatch_active_phase.
- [x] applied  [ ] tested  [ ] hardware-checked

### C3. _phase_dispatch_pending left set makes a run un-reapable forever *(not independently verified)* — **4/4 applied**

- **Seam:** `jobs/phase_runner.py:530`
- **Closes:** ~~A1-WD-2~~ ✅ RP-011 (`365f90b`), ~~A5-STR-3~~ ✅ RP-011 (`365f90b`), ~~A2-CAN-3~~ ✅ RP-010 (`3e9e969`), ~~A4-AJ-3~~ ✅ RP-010 (`3e9e969`)
- **What breaks:** There is no try/except anywhere in _run_advanced_phase or _dispatch_active_phase. Any raise leaves the guard set, and is_stranded_started returns False while it is set, so the reaper is DISABLED. The job sits status='started' permanently and blocks every future start.
- **Fix:** try/finally so the guard always clears, plus a bounded age after which the reaper stops honouring it.
- [x] applied  [ ] tested  [ ] hardware-checked

### C4. A multi-room phase is recorded as ONE room *(not independently verified)* — **3/4 applied**

- **Seam:** `jobs/phase_runner.py:301`
- **Closes:** ~~A3-REC-1~~ ✅ RP-013b (`f212c20`), ~~A3-REC-2~~ ✅ RP-013b (`f212c20`), A3-REC-3, ~~DQ-PH-3~~ ✅ RP-013b (`f212c20`)
- **What breaks:** A room_group phase attributes the group's entire cleaning time, area and battery to queue_room_ids[0]. A phased job also never records a completed room, so live progress freezes on the group.
- **Fix:** Attribute per-phase metrics across the phase's rooms, or record the phase as a phase rather than as room[0].
- [ ] applied  [ ] tested  [ ] hardware-checked

### C5. The repudiated `started_at and not ended_at` predicate is still live **[VERIFIED AT SOURCE]** — **2/2 applied**

- **Seam:** `jobs/active_job.py:1676,1709`
- **Closes:** ~~A3-REC-4~~ ✅ RP-013e (`4b0cda3`), ~~A4-AJ-2~~ ✅ RP-013e (`4b0cda3`)
- **What breaks:** SELF-INFLICTED. 0f1e2a6 moved this question onto status because nothing ever writes ended_at, so a finalized job matched forever. Two sample recorders were left behind, and the docstring written in that same commit names both BY NAME as needing the external-inclusive predicate. record_pose_sample:1776 is NOT affected (it has its own status check) -- the finding over-reached on that third site.
- **Fix:** Point record_active_job_sensor_value and record_counter_sample at run_is_in_flight. Roughly 2 lines.
- [x] applied  [ ] tested  [x] hardware-checked

### C6. Profile round-trip is broken: applying a preset re-labels the room 'custom' *(not independently verified)* — **3/3 applied**

- **Seam:** `profiles/room_profiles.py:435`
- **Closes:** ~~A1-PP-RES-2~~ ✅ RP-024 (`9abcb69`), ~~A3-PP-CRUD-2~~ ✅ RP-024 (`9abcb69`), ~~A6-PP-EST-DSP-1~~ ✅ RP-024 (`9abcb69`)
- **What breaks:** water_level (and carpet fan_speed) use a DIFFERENT precedence than every sibling field: the floor-type default OVERRIDES the profile. Candidate dicts omit the key so they take the floor default, while real rooms carry it -- so mop profiles fail to match on every floor except tile.
- **Fix:** Make the floor-type default lose to an explicit profile value, or resolve the candidate exactly the way the room is resolved.
- [x] applied  [ ] tested  [ ] hardware-checked

### C7. Slug identity has no uniqueness guarantee, and the docstring claims it does **[VERIFIED AT SOURCE]** — **3/3 applied**

- **Seam:** `rooms/utils.py:35 + rooms/room_discovery.py:254`
- **Closes:** ~~A1-ID-1~~ ✅ RP-015 (`6726b19`), ~~A2-REC-2~~ ✅ RP-015 (`6726b19`), ~~A1-ID-3~~ ✅ RP-015 (`6726b19`)
- **What breaks:** EXECUTED: 'Bed & Bath'/'Bed and Bath', 'Kids Room'/'Kids_Room', "Cat's Room"/'Cats Room', '"Guest" Room'/'Guest Room' each collapse to ONE slug -- and utils.py:16-18 explicitly claims 'distinct names must yield distinct slugs'. Discovery dedupes on numeric room_id only. On Roborock, slug_to_live_id is first-wins, so the second room's target resolves to the FIRST room's segment id and the robot cleans the wrong physical room WITH NO LOG LINE (the dropped-warning path is not reached because the lookup succeeds). plan_migration's existing_by_slug.setdefault is also first-wins, so the second room's stored settings, grants and rules are overwritten and never reported as dropped.
- **Fix:** Enforce slug uniqueness at discovery with deterministic disambiguation (append the device room_id on collision), and make the collision observable. Reconcile the docstring with whatever the code actually guarantees.
- [x] applied  [ ] tested  [ ] hardware-checked

### C8. Reconciliation never runs -- the divergence detector is never invoked *(not independently verified)* — **1/1 applied**

- **Seam:** `rooms/reconciliation.py`
- **Closes:** ~~A2-REC-1~~ ✅ RP-019 (`0e0369f`)
- **What breaks:** compute_reconciliation/plan_migration exist and work, but nothing triggers them: no schedule, no event hook, no UI entry point. This is the ROOT of audit #7's CRITICAL (DQ-DE-1): stored ids and live ids diverge because nothing ever checks that they agree.
- **Fix:** Decide the trigger -- on map-source refresh, on job start, or a periodic check -- and surface the result. The machinery is already built.
- [x] applied  [ ] tested  [ ] hardware-checked

### C9. Destructive room writes with no confirmation or preservation *(not independently verified)* — **2/2 applied**

- **Seam:** `rooms/room_crud.py`
- **Closes:** ~~A3-CRUD-1~~ ✅ RP-005 (`4217c3c`), ~~A3-CRUD-4~~ ✅ RP-016 (`2feb9e0`)
- **What breaks:** save_managed_rooms unconditionally replaces map_bucket['rooms'], so an empty selection wipes the map's stored rooms. remove_map leaves the map's saved run-profile library, queue state and onboarding orphaned rather than removing or migrating them.
- **Fix:** Guard the wholesale replace against an empty/degenerate discovery, and make remove_map account for every structure keyed on that map_id.
- [x] applied  [ ] tested  [ ] hardware-checked

### C10. async_refresh_room_source returns None on success AND on every failure path *(not independently verified)* — **1/1 applied**

- **Seam:** `rooms/source_refresh.py`
- **Closes:** ~~A4-SRC-1~~ ✅ RP-007 (`4c42482`)
- **What breaks:** Callers cannot distinguish 'refreshed successfully' from 'refresh failed, you are looking at stale cache'. dispatch/manager.py calls this immediately before resolving live segment ids, so a silent failure means stale ids go to the wire -- the same wrong-room outcome as C1, by a different route.
- **Fix:** Return a discriminable result and have dispatch refuse (or warn loudly) when the refresh did not actually succeed.
- [x] applied  [ ] tested  [ ] hardware-checked

### C11. The Eufy in-memory map source has NO vacuum identity **[VERIFIED AT SOURCE]** — **3/3 applied**

- **Seam:** `mapping/map_source_runtime.py:839 (eufy_inmem_candidates)`
- **Closes:** ~~A1-LC-1~~ ✅ RP-026 (`e434813`), ~~A3-EXT-1~~ ✅ RP-026 (`e434813`), ~~A4-RB-2~~ ✅ RP-026 (`e434813`)
- **What breaks:** VERIFIED: eufy_inmem_candidates(hass, source_cfg) takes no vacuum_entity_id, no serial, no device_id, and appends the WHOLE hass.data['robovac_mqtt'] bucket first. The bounded BFS matches on attribute presence only, so coordinators[0] wins for EVERY vacuum. Six coordinator call sites inherit it (361/397/461/550/645/689): static rooms, live pose, the render raster the card draws, and the raster zone_membership consumes. The per-vacuum _mem_rooms_cache does not help -- its version is a hash of that same wrong raster, so it is self-consistently wrong. Only bites a MULTI-Eufy install; this install has one robot today.
- **Fix:** Pass vacuum_entity_id through and select the coordinator by serial/device_id. The pattern is already there on the other brand: roborock_candidates accepts image_entity_id and puts the per-vacuum entity object FIRST. Forgotten override sibling, fourth instance. The storage fallback is correctly per-serial, which proves per-device identity was the intent.
- [x] applied  [ ] tested  [ ] hardware-checked

### C12. Live pose is projected through the WRONG coordinate frame *(not independently verified)* — **2/2 applied**

- **Seam:** `mapping/map_source_coordinator.py (_load_live_pose_geom / _apply_inmem_pose_to_result)`
- **Closes:** ~~A2-GEO-1~~ ✅ RP-027 (`382d3d5`), ~~A5-POSE-1~~ ✅ RP-027 (`382d3d5`)
- **What breaks:** A memory-frame robot pixel is normalized and room-looked-up against .storage-frame geometry. The two frames are not guaranteed equal, so the robot dot and the derived current_room can both be wrong while reporting present:True.
- **Fix:** Normalize the pose against the frame it came from, or refuse to derive current_room when the frames disagree.
- [x] applied  [ ] tested  [ ] hardware-checked

### C13. The sticky-hold `stale` flag is written and never read *(not independently verified)* — **2/2 applied**

- **Seam:** `mapping/map_source_coordinator.py:126`
- **Closes:** ~~A1-LC-2~~ ✅ RP-027 (`382d3d5`), ~~A5-POSE-2~~ ✅ RP-027 (`382d3d5`)
- **What breaks:** The last-known-good hold re-serves a frozen current_room/robot_anchor as present:True and sets stale/stale_since/stale_reason -- which have NO consumer anywhere. A docked Roborock therefore reports a phantom room for up to 6 hours, and nothing downstream can tell the difference.
- **Fix:** Either consume the stale flag at every presentation surface, or stop serving a frozen pose as present.
- [x] applied  [ ] tested  [ ] hardware-checked

### C14. The tracker's end_job runs only on a SUCCESSFUL finalize *(not independently verified)* — **2/2 applied**

- **Seam:** `mapping/tracker.py`
- **Closes:** ~~A6-TRK-1~~ ✅ RP-012 (`7269020`), ~~A6-TRK-4~~ ✅ RP-012 (`7269020`)
- **What breaks:** end_job has exactly one caller, so every cancel, abort and stranded-reap leaves tracker state live into the next run. The last room of every job also never fires room_completed, because end_job resets the state that would emit it.
- **Fix:** Call end_job from every terminal path, and flush the final room before the reset.
- [x] applied  [ ] tested  [ ] hardware-checked

### C15. `unavailable` satisfies every negating rule operator — a sensor dropout aborts a live run **[VERIFIED AT SOURCE]** — **1/1 applied**

- **Seam:** `rooms/access_graph.py:907 (_room_rule_matches)`
- **Closes:** ~~A6-GUARD-1~~ ✅ RP-008 (`8d244dc`)
- **What breaks:** VERIFIED: an unavailable entity still yields a State object, so state_value == 'unavailable' and there is NO availability check anywhere in the matcher. `not_equals` and `not_in` both return True; `missing` returns True the moment the entity is dropped. The rule matches, the room enters direct_blocked, and path_blockers applies path_block_action -- `cancel_and_event` calls async_cancel_active_job, which issues vacuum.return_to_base and finalizes the run as cancelled. `pause_and_event` ends the same way once pause_timeout reaps it. A battery-powered contact sensor dropping off a Zigbee mesh for one poll physically aborts a clean in progress, and the user sees a path-blocked event naming a door that never opened.
- **Fix:** Treat unavailable/unknown as 'no answer' rather than as a value: skip the rule (or hold the previous verdict) instead of letting a negating operator match. Decide the same question once for `missing` vs `unavailable` -- they are different facts.
- [x] applied  [ ] tested  [ ] hardware-checked

### C16. dock_events records a NEW cycle on first sighting or on an availability blip *(not independently verified)* — **2/2 applied**

- **Seam:** `listeners/dock_events.py:74`
- **Closes:** ~~A1-REG-1~~ ✅ RP-038 (`1c8da5a`), ~~A6-GUARD-3~~ ✅ RP-038 (`1c8da5a`)
- **What breaks:** The only dedupe is new_val == old_val, with old_val = '' when old_state is None. So an entity first appearing (HA restart mid-cycle), unknown->drying, and unavailable->washing all read as a new cycle. record_dock_event overwrites the last-* timestamp BEFORE the debounce check, and the Eufy adapter declares debounce_seconds for last_mop_wash ONLY -- so dry-start and dust-empty have no suppression at all. An X10 dry cycle runs 2-4 hours, so the window is large and daily. The sibling listener discovery.py:127 DOES filter exactly this class; dock_events is the one of eight that writes durable counters from a raw state arrival and has no such filter.
- **Fix:** Require the previous value to be a real non-trigger dock state before recording a cycle. Move the timestamp write inside the debounce guard.
- [x] applied  [ ] tested  [ ] hardware-checked

### C17. Reactive listeners spawn unbounded concurrent work with no in-flight guard *(not independently verified)* — **3/4 applied**

- **Seam:** `listeners/path_blockers.py + pause_timeout.py + lifecycle.py + pose_sampler.py`
- **Closes:** A6-GUARD-2, ~~A6-GUARD-4~~ ✅ RP-011 (`365f90b`), ~~A2-LIFE-2~~ ✅ RP-003 (`76d92fc`), ~~A4-POSE-2~~ ✅ RP-012 (`7269020`)
- **What breaks:** path_blockers spawns a _process task per event with no coalescing, so a bouncing sensor stacks them; the 1-minute reap ticker has no in-flight guard while each reap blocks; the pose timer is fire-and-forget so a slow tick overlaps the next; and _process tasks are untracked, so remove() drops the subscription but not the work already in flight.
- **Fix:** One in-flight guard / coalescing pattern, applied to all four. This is the same question four times.
- [ ] applied  [ ] tested  [ ] hardware-checked

### C18. The listener layer is a THIRD answer to 'is a job active' *(not independently verified)* — **3/3 applied**

- **Seam:** `listeners/_common.py:110 (is_job_active)`
- **Closes:** ~~A3-COMMON-1~~ ✅ RP-008 (`8d244dc`), ~~A3-COMMON-6~~ ✅ RP-014 (`5c4c0f0`), ~~A5-METRICS-1~~ ✅ RP-014 (`5c4c0f0`)
- **What breaks:** jobs/active_job.py owns two deliberate predicates (dispatched_job_is_in_flight, run_is_in_flight). The listener layer uses NEITHER -- _common.is_job_active is an independent third implementation, and job_progress gates on a hand-copied {'started','paused'} literal that is a fourth. On Roborock, is_job_active treats a not-yet-added job_active entity as 'not active'. Fifth instance of the campaign's forgotten-override-sibling pattern, and the first where the divergence is a whole LAYER.
- **Fix:** Route the listener layer at the canonical predicates, or state explicitly why the input layer needs a different question and derive it from the same constant.
- [x] applied  [ ] tested  [ ] hardware-checked

### C19. A public service call wipes a map's entire room configuration, silently **[VERIFIED AT SOURCE]** — **5/5 applied**

- **Seam:** `rooms/room_crud.py:261 (map_bucket['rooms'] = managed_rooms)`
- **Closes:** ~~A3-ROOMS-1~~ ✅ RP-005 (`4217c3c`), ~~A3-ROOMS-2~~ ✅ RP-005 (`4217c3c`), ~~A4-SETUP-1~~ ✅ RP-005 (`4217c3c`), ~~A5-FACADE-1~~ ✅ RP-005 (`4217c3c`), ~~A5-FACADE-3~~ ✅ RP-005 (`4217c3c`)
- **What breaks:** VERIFIED BY EXECUTION. Three routes to one unconditional replace. (1) save_managed_rooms against a map with no cached discovery: discovery.get('rooms',[]) is [], build_managed_rooms returns {}, and line 261 replaces wholesale. (2) `enabled_room_ids:` with a blank YAML value -- cv.ensure_list(None) returns [] (confirmed against installed HA core), so the schema turns null into [], which passes the manager's `is not None` check while _normalize_enabled_room_ids([]) yields an empty set, so every room hits `continue`. The None-vs-empty distinction the manager deliberately relies on is destroyed one layer up, at the schema boundary. (3) setup_save_rooms rebuilds from the stale/absent discovery cache and returns {'status':'success'}. Every per-room setting, rule, grant, colour and floor type is gone; none of the three services declares supports_response, so the caller gets no error and no room_count. Documented behaviour is the OPPOSITE: docs/advanced/03-services.md:255 says 'Omit to keep all rooms enabled'. AUDIT #14 CONFIRMS THE LAYER: the same unguarded total-wipe is reachable at the FACADE (A5-FACADE-1) and rebuild_map has it too (A5-FACADE-3) -- so the facade, not the service, is where the precondition belongs.
- **Fix:** Guard the wholesale replace: refuse to persist an empty room set when the previous bucket was non-empty and discovery is empty. Separately, stop the schema collapsing null into [] -- an explicit null must either be rejected or preserved as None. Give these three services a response so a caller can tell.
- [x] applied  [ ] tested  [ ] hardware-checked

### C20. A config-entry reload leaves the OLD manager alive; its orphaned timer then overwrites the store **[VERIFIED AT SOURCE]** — **1/1 applied**

- **Seam:** `core/manager.py:473 + __init__.py:465 (async_unload_entry)`
- **Closes:** ~~A1-INIT-1~~ ✅ RP-003 (`76d92fc`)
- **What breaks:** VERIFIED. async_initialize spawns loop-lifetime work -- the dock re-arm poller (hass.async_create_task) and external-run grace timers (async_call_later, 300s x up to 8 re-arms = ~45 min). There is NO manager teardown anywhere: grep for async_shutdown / def shutdown / EVENT_HOMEASSISTANT_STOP across manager.py, phase_runner.py and external_run.py returns nothing, and nothing is registered with entry.async_on_unload. async_unload_entry removes listeners/services/panels and pops DATA_RUNTIME but cancels none of it. A reload then builds a SECOND manager over the same STORAGE_KEY, while the orphaned callbacks still hold self._manager = the OLD one and end in external_run.py:213 async_save() / phase_runner.py:856 _async_save_logged() -- and async_save is a bare whole-root-dict write. So the pre-reload snapshot replaces everything persisted since. The orphaned dock poller can also still call maybe_advance_phase, so a dead manager and a live one can both dispatch to the same physical robot; _dock_poller_active is per-instance and cannot dedupe across two.
- **Fix:** Give the manager a teardown that cancels its spawned tasks and timers, and register it with entry.async_on_unload. Consider guarding async_save against a manager whose entry has been unloaded.
- [x] applied  [ ] tested  [ ] hardware-checked

### C21. Panels registered outside async_setup_entry are never tracked, so unload cannot remove them **[VERIFIED AT SOURCE]** — **3/3 applied**

- **Seam:** `__init__.py:420 + setup/workflow.py:106`
- **Closes:** ~~A1-UP-1~~ ✅ RP-003 (`76d92fc`), ~~A2-DOWN-1~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-1~~ ✅ RP-003 (`76d92fc`)
- **What breaks:** VERIFIED. Only __init__.py ever writes `_panels_<entry_id>`, and it appends only what its OWN loop registered. setup/workflow.py:106 (add_vacuum, reached from the panel's own onboarding flow) registers a per-vacuum panel and tracks nothing. panels.py swallows HA's duplicate-url ValueError at DEBUG and returns None, which `if panel_url:` then drops -- so on the next setup the panel is not re-tracked either. services/setup.py:161 schedules a reload immediately after add_vacuum, so the interleaving is automatic. Steady state from a BLANK install: two sidebar entries, one rendering the 'no vacuum configured' placeholder, self-perpetuating across reloads until a full HA restart clears hass.data[DATA_PANELS]. Found independently by THREE of four agents. The reproducer corrected an over-stated sub-claim: it does NOT affect 'every second and later vacuum unconditionally' -- it needs the blank-install path.
- **Fix:** Track every panel registration in the `_panels_` list regardless of where it happens, or give panels.py a register-and-track helper that is the only entry point.
- [x] applied  [ ] tested  [ ] hardware-checked

### C22. Setup starts several things unload never stops — the systemic version of C20 *(not independently verified)* — **6/6 applied**

- **Seam:** `__init__.py async_setup_entry vs async_unload_entry`
- **Closes:** ~~A1-UP-3~~ ✅ RP-003 (`76d92fc`), ~~A2-DOWN-2~~ ✅ RP-003 (`76d92fc`), ~~A2-DOWN-3~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-2~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-3~~ ✅ RP-003 (`76d92fc`), ~~A4-RELOAD-4~~ ✅ RP-003 (`76d92fc`)
- **What breaks:** This audit's assignment was to build the table -- everything setup starts, checked against what unload stops. C20 (the manager's spawned tasks/timers) was one known row; these are the others: async_unregister_learning_services removes 16 of the 21 services setup registers, so FIVE learning services survive an unload; the post-job water-amendment state listener and its 180s timer are never cancelled; the debug-capture auto-stop timer survives; and two hass.data[DOMAIN] keys are left behind. Individually LOW/MEDIUM; together they are the same shape as C20 and should be fixed as one pass over the setup/unload pair.
- **Fix:** Make unload the exact inverse of setup: register every unsub/timer/key with entry.async_on_unload at the point of creation, so the two cannot drift.
- [x] applied  [ ] tested  [ ] hardware-checked

### C23. The confidence tier system is INVERTED at the top, and green is unreachable **[VERIFIED AT SOURCE]** — **2/2 applied**

- **Seam:** `learning/estimator.py:117 (_BREAKPOINTS) + :165 (_breakpoint_for_score)`
- **Closes:** ~~A1-EST-1~~ ✅ RP-036 (`97689a6`), ~~A1-EST-5~~ ✅ RP-036 (`97689a6`)
- **What breaks:** VERIFIED BY EXECUTION. _LEARNED_BASE (0.55) + _SAMPLE_BONUS_MAX (0.25) = 0.80, which is EXACTLY high.min_score -- so HIGH/green requires a perfect score, i.e. minutes_stddev exactly 0, which real timing data never has. And medium.max_score is 0.79 while high.min_score is 0.80, so the band (0.79, 0.80) matches no bucket; _breakpoint_for_score falls through to _BREAKPOINTS[-1], which is LOW/error -- the BOTTOM of the table, not the nearest tier. Sweep at 12 samples / avg 10 min: stddev 0.05 -> 0.7975 -> RED; stddev 0.15 -> 0.7925 -> RED; stddev 0.20 -> 0.7900 -> AMBER. A room consistent to 3 seconds shows red while a room consistent to 12 seconds shows amber. ui_variant reaches the card verbatim (src/renderers/learning.js:534, rooms.js:742/1196) and job confidence is min(room scores), so one such room drags the whole job estimate red.
- **Fix:** Close the band (make the tiers contiguous, or use a one-sided descending test), and make the fall-through return the nearest tier rather than the last entry. Separately decide whether HIGH should be reachable at all -- as written it needs zero variance.
- [x] applied  [ ] tested  [ ] hardware-checked

### C24. External runs contribute battery=0.0 and the estimator consumes it as a real measurement *(not independently verified)* — **1/1 applied**

- **Seam:** `learning/estimator.py:844 + learning/external_ingest.py:1056`
- **Closes:** ~~A1-EST-2~~ ✅ RP-036 (`97689a6`)
- **What breaks:** THE HYPOTHESIS THIS AUDIT WAS BUILT ON, CONFIRMED. build_graduated_job constructs the completed-job record with NO battery block at all (grep for 'battery' in external_ingest.py returns zero hits), yet outcome.status is 'completed' and used_for_learning is True, so is_learning_job admits it. The rebuilder reads job.get('battery',{}).get('used') -> 0.0 and accumulates that into the SAME room_stats bucket as dispatched runs. _safe_float only substitutes a default for None/''/unknown/unavailable -- 0.0 is a valid float and passes straight through. There is no battery_sample_count and no source marker, so 'learned 0%' is indistinguishable from 'no battery data'. With an all-external archive avg_battery_used is exactly 0.0: the card asserts the job costs ZERO battery and battery_warning is False at ANY charge level. And confidence_score is computed from TIMING samples only, so the number carries no warning.
- **Fix:** Either exclude records with no battery block from the battery aggregate, or carry a battery_sample_count so a zero-sample bucket is distinguishable from a measured zero.
- [x] applied  [ ] tested  [ ] hardware-checked

### C25. The incomplete-run log misreports which rooms were missed *(not independently verified)* — **4/4 applied**

- **Seam:** `learning/history_store.py (incomplete-run family)`
- **Closes:** ~~A4-STATE-1~~ ✅ RP-013c (`0ff4a8a`), ~~A4-STATE-2~~ ✅ RP-013c (`0ff4a8a`), ~~A4-STATE-4~~ ✅ RP-020 (`f48dee2`), ~~A2-ACC-4~~ ✅ RP-036 (`97689a6`)
- **What breaks:** The final room of EVERY non-completed run is recorded as missed; clear_incomplete_run's docstring claims '(full clean)' but ANY completion clears it; missed_room_ids survive a re-segment and a map switch, so they can name rooms that no longer exist or now mean something else; and a skipped room holds 'current' for the rest of the run so it can never be resolved.
- **Fix:** One pass over the incomplete-run lifecycle: who writes it, what clears it, and whether its room ids are still valid at read time.
- [x] applied  [ ] tested  [ ] hardware-checked

### C26. Learning services destroy or misreport, and say success either way *(not independently verified)* — **4/4 applied**

- **Seam:** `learning/services.py`
- **Closes:** ~~A5-SVC-1~~ ✅ RP-020 (`f48dee2`), ~~A5-SVC-2~~ ✅ RP-001 (`3ddcc1c`), ~~A5-SVC-3~~ ✅ RP-031 (`6a8c965`), ~~A5-SVC-6~~ ✅ RP-006 (`e598e3e`)
- **What breaks:** The 22 registrations here were NOT covered by audit #13's services sweep, and they have the same shape: exclude/restore_learning_job report 'stats rebuilt' without rebuilding; finalize_learning_job fires the job-finished event with a FABRICATED payload; retry_missed_rooms permanently destroys the map's room-enable selection; rebuild_learning_stats blanks accuracy_stats before replaying, so a failure partway leaves it empty.
- **Fix:** Same treatment as C19/C26's siblings: make the destructive ones confirm or be reversible, and make every response honest about what actually happened.
- [x] applied  [ ] tested  [ ] hardware-checked

### C27. overwrite_theme resolves against the ACTIVE theme, never the target it names **[VERIFIED AT SOURCE]** — **3/3 applied**

- **Seam:** `themes/manager.py:303`
- **Closes:** ~~A1-CRUD-1~~ ✅ RP-034 (`c005ad6`), ~~A1-CRUD-2~~ ✅ RP-034 (`c005ad6`), ~~A1-CRUD-4~~ ✅ RP-034 (`c005ad6`)
- **What breaks:** VERIFIED at source and REPRODUCED by executing the module. overwrite_theme builds `resolved` from vac['active_theme_id'] + the working draft; `existing = library[theme_id]` is fetched but used ONLY to preserve name/source/tags/author. So calling it on any theme that is not the active one replaces that theme's palette with a CLONE of the active one, and line 326 then silently repoints the vacuum onto it. With no active theme the target's palette becomes {} outright. Both return ok:True and services.py persists. The metadata-preservation loop is what makes it silent -- the entry keeps its name and author, so it looks intact. The docstring claims it writes 'the vacuum's working draft'; it writes active+draft and works with an empty draft. The CARD masks it (bindings/theme.js only calls overwriteTheme inside `if (state.activeThemeId)` and passes that same id), so it is service-only reachable -- which is why the verifiers held it at MEDIUM. Also lets a BUNDLED theme's palette be permanently replaced (CRUD-4).
- **Fix:** Resolve against the TARGET entry, or refuse when theme_id != active_theme_id. Decide which the docstring meant and make the code and the doc agree.
- [x] applied  [ ] tested  [ ] hardware-checked

### C28. Bundled themes are protected from neither delete nor overwrite **[VERIFIED AT SOURCE]** — **2/2 applied**

- **Seam:** `themes/manager.py delete_theme/overwrite_theme + preloaded.ensure_preloaded_theme_library`
- **Closes:** ~~A1-CRUD-3~~ ✅ RP-034 (`c005ad6`), ~~A1-CRUD-4~~ ✅ RP-034 (`c005ad6`)
- **What breaks:** delete_theme has no source=='core' guard, so a bundled theme can be deleted -- and audit #14's A1-INIT-3 showed the startup re-seed resurrects it, so the deletion is neither prevented nor durable ('gone until restart'). overwrite_theme can replace a bundled theme's palette PERMANENTLY, because the re-seed only restores absent entries, not modified ones. The discriminator already exists and is trustworthy: preloaded.py stamps source='core', _import_scoped allowlists {community,generated,manual} so an import cannot claim it, and save_theme_as_new hardcodes 'manual'.
- **Fix:** Refuse both operations for source=='core'. Chris's spec: bundled themes are system inventory, not ordinary library entries -- protecting them removes the 'deleted until restart' behaviour rather than trying to make deletion durable.
- [x] applied  [ ] tested  [ ] hardware-checked

### C29. delete_theme leaves the working draft orphaned on a base that no longer exists **[VERIFIED AT SOURCE]** — **2/2 applied**

- **Seam:** `themes/manager.py:394`
- **Closes:** ~~A1-CRUD-5~~ ✅ RP-034 (`c005ad6`), ~~A2-DRAFT-1~~ ✅ RP-034 (`c005ad6`)
- **What breaks:** delete_theme nulls active_theme_id for every affected vacuum (that guard DOES exist) but line 394 only RE-NORMALIZES the working draft -- it does not empty it, and leaves draft_dirty untouched. set_active_theme twenty lines later does exactly the right thing (_empty_theme_draft + draft_dirty=False). So deleting the theme you are editing leaves a live draft of overrides authored against a base that is gone. Sibling divergence: two adjacent methods, one clears the draft, one does not.
- **Fix:** Per Chris's spec: treat deletion as an atomic destructive transition -- resolve the fallback target FIRST (default_theme_id is nulled at :388 before the vacuum walk at :391, so the chain must run before that), clear working_draft, set draft_dirty=False, set active_theme_id, persist once, notify once. Note delete_theme currently does not persist at all.
- [x] applied  [ ] tested  [ ] hardware-checked

---

## TIER 2 -- singles, by corrected severity

### HIGH (1)

- [ ] **ENT-1** `adapters/eufy/entities.py:119` [eufy]  
  Companion entities are resolved by deriving a name from the vacuum entity id, with no device-registry lookup and no fallback — a device whose entities are named differently reports EVERY capability as absent, silently  
  -> build_entity_id does string surgery: vacuum_entity_id.split('.')[-1] + suffix. There is no registry lookup, no fallback, and no signal when a derived name does not exist — the capability is simply reported absent. PROVEN

### MEDIUM (13)

- [x] **A6-AGX-2** `core/manager.py:1374` [both] _(finder said HIGH)_  
  The structural gate on every per-room edit is absolute, not a delta: one stored graph violation rejects unrelated edits (fan speed, enable, color) with "The requested access links would make the graph invalid."  
  -> After a Roborock re-segment + migrate, the user can no longer change ANY room setting on that map — changing a room's fan speed or disabling a room fails with an error claiming they requested illegal access links, which
- [x] **DQ-ACT-6** `core/manager.py:5005` [roborock]  
  A pre-call leaves the device in a modified state (and the stashed run steps consumed) when the clean then fails to start  
  -> A failed start silently reconfigures the robot's global mop intensity and leaves it there. On a mixed-batch start that means water is now OFF for whatever the user does next from the vendor app.
- [ ] **DIAG-1** `diagnostics.py:0` [both]  
  entity_resolution reports only what the adapter DERIVED, so 'we looked in the wrong place' is indistinguishable from 'this device has no such entity'  
  -> The dump lists each declared companion with exists true/false. It never lists what the vacuum's DEVICE actually exposes, so a naming miss and a genuinely absent capability produce byte-identical output. Issue #48 is the
- [x] **A4-CUSTOM-2** `mapping/mapping_services.py:1550` [Both (Eufy + Roborock). The card path additionally needs a live map source present (mss.present) for the dock-mascot fallback, which is the normal Eufy fork configuration.] _(finder said HIGH)_  
  In custom mode with no resolvable layout, _resolve_active_scope hands writers THROWAWAY dicts — set_companion_anchor / set_segment_room_link mutate a garbage-collected object and report saved: True  
  -> The mascot visibly stays where the user parked it for the rest of the session (the card never refetches after an anchor write) and silently snaps back on the next page load — repeatedly, with no error and no way for the
- [x] **A7-ROBORO-4** `mapping/roborock_raw_map.py:171` [roborock]  
  ro_dx/ro_dy are hardcoded 0 and the decoded top/left are discarded — the payload cannot express any offset between the raw IMAGE-block frame and the parser's rendered frame  
  -> IF the frames differ: the card draws the raster full-bleed at 0..1 while every overlay it composites on top — room bboxes, robot/dock anchors, no-go and no-mop quads, saved zones — comes from map_state_source in the pars
- [x] **DR-ONB-1** `onboarding/manager.py:182` [both]  
  remap_confirmed_floor_types mutates in place while iterating, losing confirmations whenever old and new id sets overlap  
  -> PROVEN by execution. The loop pops str(old_id) and writes str(new_id) into the SAME dict it is iterating over, so a new_id that is also a later old_id consumes the entry just written. Measured: id_remap={1:2, 2:3, 3:4} w
- [x] **DR-ONB-2** `onboarding/manager.py:186` [both]  
  check_for_new_rooms compares a PER-MAP stored count against a source with no map scoping  
  -> The stored side, room_count_at_last_check, is stamped by mark_rooms_discovered from data['maps'][vacuum][map_id]['rooms'] -- per map. The live side reads the vacuum entity's `segments` attribute, which carries only the A
- [x] **A5-PP-RP-2** `planning/run_plan.py:1379` [both] _(finder said HIGH)_  
  Any plan whose FIRST surviving phase is a zone is refused with "Room-clean payload is missing or invalid" — and a live blocker rule can push a plan into that state  
  -> A saved run that worked yesterday becomes unstartable the moment a door/occupancy sensor blocks the rooms in its first group — with an error that blames a corrupt payload rather than naming the blocked room. The rest of
- [x] **A6-AGX-4** `rooms/access_graph.py:364` [both]  
  Every access-graph issue message is a hard-coded English literal and is rendered verbatim in the card on all 18 shipped locales  
  -> On any non-English install the room-access modal's issue list and its save-error banner are English, including for AR/HE where they are injected into an RTL layout. This is the one place in the access feature where the u
- [x] **A6-AGX-1** `rooms/access_graph.py:651` [both] _(finder said HIGH)_  
  get_access_graph_health emits no verdict — the "runs are allowed" empty graph and the "every run is blocked" partial graph are indistinguishable, and the report's own remediation moves the user from the first into the second  
  -> The one service documented as the access-graph diagnostic cannot answer the only question that matters — "are my runs blocked right now?". Following its single actionable instruction on a fresh map (mark a dock room) sil
- [x] **A5-AG-2** `rooms/access_graph.py:770` [both]  
  A room with no inbound edge makes the whole graph 'partial', hard-blocking every run on the map, and no shipped surface names the offending room  
  -> After a map rebuild that discovers even one new room, every Start on that map is refused with 'Room access graph is partially configured. Complete it or clear all access settings to allow basic runs.' — a message that na
- [x] **SN-4** `sensor/__init__.py:272` [both]  
  Renaming a room never reaches the entity's friendly name - the rebuilt entity carrying the new name is discarded  
  -> VERIFIED: async_update_entity has ZERO occurrences anywhere in the integration. Both sync blocks construct a fresh entity per desired room and then discard it when the unique_id is already known, pushing only a state wri
- [x] **A6-AGX-6** `src/state/room-access.js:85` [both]  
  The card's access modal renders an existing edge into the dock room as "Missing Room N" — an edge that exists is displayed as a stale reference to a room that does not  
  -> The editor misrepresents the stored graph: a live room is labelled missing/stale, inviting the user to delete a valid edge. Conversely they cannot re-create it, because the dock room is filtered out of the selectable lis

### LOW (13)

- [x] **EP-5** `button.py:256` [both]  
  The saved-run-profile button name is hardcoded English, bypassing the translation mechanism  
  -> Every other entity class in scope declares _attr_translation_key and lets HA resolve the name from strings.json. EufyVacuumSavedRunProfileButton sets _attr_has_entity_name = True, declares NO translation key, and overrid
- [x] **INF-9** `entity_helpers.py:109` [both]  
  get_floor_type_label emits hardcoded English into an 18-language product  
  -> Nine English literals plus an English-derived fallback (str(floor_type).replace('_',' ').title()), emitted as floor_type_label from three backend payloads (core/manager.py:280, planning/run_plan.py:174, profiles/manager.
- [x] **A3-IMAGE--8** `mapping/mapping_services.py:910` [Both; depends on whether Pillow is importable on the host.]  
  Upload persists width/height as None when Pillow is unavailable and still reports saved:True  
  -> On a Pillow-less install a successful upload is recorded in a state that makes custom-segment authoring report a missing backdrop, and the variant row displays null dimensions. Confined to installs without Pillow, and th
- [x] **A3-IMAGE--4** `mapping/mapping_services.py:933` [Both.] _(finder said MEDIUM)_  
  Re-uploading a map image does not invalidate image_segments, so a default analyze returns the previous image's segments  
  -> An automation or script that uploads a refreshed map export and analyzes it gets the previous map's room geometry back with a success-shaped response and no staleness signal. The card path is immune (it always passes for
- [x] **A5-FURNIS-4** `mapping/mapping_services.py:2162` [both] _(finder said MEDIUM)_  
  area_label_anchors are keyed by device room id and nothing prunes them on a room rebuild, so a re-import silently re-aims one room's dragged label onto a different room  
  -> This is the direct answer to 'does the edit survive a re-import?': the bytes survive, their meaning does not, and nothing detects it. Cosmetic in consequence (a mis-placed m² chip, not a mis-cleaned room) but silently wr
- [x] **A2-POLYGO-6** `mapping/segment_primitives.py:342` [Neither at runtime (Eufy CV thresholds are empirically tuned); affects future adapter authors, which is exactly this module's advertised audience]  
  `compactness` docstring claims 'Range 0-1; 1 = circle' - the attainable maximum is pi/4 and a circle scores LOWER than a square  
  -> No runtime defect - segmentor.py's thresholds (e.g. `compactness < 0.08` for `fragmented_candidate`) were tuned empirically against the actual function. The harm is to the stated purpose of this module: its header calls
- [x] **A2-POLYGO-7** `mapping/segment_primitives.py:526` [Neither at runtime (Eufy CV only, thresholds empirically tuned); affects future adapter authors]  
  `normalized_color_features`' luminance normalisation provably cancels out - the Rec.709 weights are dead arithmetic and tuning them changes nothing  
  -> No behavioural defect - the output is correct chromaticity and segmentor.py's hue clustering is tuned against it. The trap is for maintenance: the docstring says 'illumination-normalized chromaticity features' and the co
- [x] **EP-4** `number.py:7` [both]  
  Module comment asserts 'no polling'; the one class that polls is the one relying on it  
  -> The comment `# All number entities write directly to manager storage; no polling.` sits above PARALLEL_UPDATES = 0. Verified as a claim: NumberEntity, unlike ButtonEntity, does NOT set _attr_should_poll = False, and Eufy
- [x] **EP-7** `room_entities.py:87` [both]  
  _async_update_room silently drops non-managed keys from a mixed update  
  -> Branch 2 filters `updates` to a hand-maintained managed_field_names set and, if ANY managed key is present, routes only that subset to update_room_fields and RETURNS -- so every non-managed key in the same call is discar
- [x] **A6-AGX-3** `rooms/access_graph.py:559` [both] _(finder said MEDIUM)_  
  get_room_access_editor marks every unselected target unselectable when the graph is already broken elsewhere, with the contentless reason "Not selectable due to graph legality."  
  -> A consumer of the documented editor service sees every link greyed out with a message that explains nothing and blames the edge being offered rather than the pre-existing violation. The user cannot tell what to fix; the
- [x] **A6-AGX-5** `rooms/access_graph.py:613` [both] _(finder said MEDIUM)_  
  The per-room editor's issue list drops graph-scoped issues, so it reports a room as problem-free on a map whose graph is invalid and blocking runs  
  -> The per-room diagnostic reports a clean bill of health for a room on a map where cleaning is blocked, and never surfaces the one issue ("no dock room") that is causing it. The user auditing rooms one at a time will find
- [x] **SN-9** `sensor/map_overlays.py:76` [both]  
  native_value returns the literal string 'unavailable', colliding with HA's reserved state  
  -> VERIFIED AT SOURCE: `if not res.get('present'): return 'unavailable'`. That is indistinguishable in hass.states, templates, is_state() and the frontend from an entity that is genuinely unavailable, while the real diagnos
- [ ] **A4-SETUP-6** `services/setup.py:243` [both] _(finder said HIGH)_  
  setup_reject_rooms permanently deletes rooms from EVERY map for the vacuum with no map scoping, no protection gate, no confirmation and no way back  
  -> A YAML/automation caller, or a user clicking Reject on a room the drift panel surfaced, silently loses that room's configuration on maps they were not looking at. Room entities disappear, run profiles and queues referenc
  -> **ADJUDICATED:** SEVERITY CORRECTED HIGH -> LOW (LATENT) (2026-08-03) -- MECHANISM CONFIRMED, HARM MISDESCRIBED. The scoping claim is correct and worth keeping: rejection is NOT map-scoped. `rejected_rooms` is a flat list[int] on setup_progress[vacuum_entity_id] with no map dimension, _get_progress_record is keyed by vacuum only, the suppression is a flat set subtraction applied identically to every map, and reject_rooms iterates manager.data['maps'][veid] with no filter -- while discovery IS map-capable (discover_rooms_for_vacuum takes map_id), each drift row carries a map_id, and the card renders it beside the button. The UI presents a per-map decision that the backend applies per-vacuum. But the finding's HARM -- 'silently loses that room's configuration on maps they were not looking at' -- is unreachable. new_candidate_ids = discovered - configured_ids - rejected, and _list_configured_room_ids collects across ALL maps for the vacuum, so a room configured anywhere is never offered for rejection anywhere. The rooms.pop therefore removes a discovery-created stub, not user data. And the user guide (docs/user-guide/11-setup.md, applying charter delta 9) shows the other two 'harms' are the FEATURE: phantom rooms 'need to be rejected here so they don't become managed entities', and Reject as phantom 'permanently suppresses the room... never appears in this list again... Use this for ghost rooms the firmware occasionally invents.' Permanence is the point, and a typed-token gate on dismissing a firmware ghost would be absurd friction. Chris: it refuses the room's CREATION, it does not delete a room. The card offers it only inside Setup; anything else needs a hand-written service call. WHAT SURVIVES, and why it stays OPEN at LOW rather than being retired: rejection is vacuum-scoped while phantoms are per-map, and Eufy reuses ids 1-11 per map. A genuine phantom id on one floor therefore permanently blocks configuring a REAL room with the same id on another, and there is no un-reject path (grep: the only writers are drift.py and core/manager.py:559 record-init). That is the inverse of the finding's harm -- not losing existing configuration, but losing the ABILITY to configure. Latent today because only one map per vacuum carries rooms in this fleet; that is current state, NOT a limit (Chris), so it becomes live the day a second floor is configured. Minor second residual: reject_rooms never checks is_configured, so a direct service call can pop a configured room. Not reachable from the card. FIX SHAPE when it is worth doing: carry the map the rejection was made on rather than adding a confirmation gate or a protection level -- neither of those addresses the actual defect. Reads stay tolerant of the legacy flat list (treat as all-maps, preserving today's behaviour for existing records); writes become map-keyed; the service takes an optional map_id and the card passes the map_id it already renders.

---

## APPLIED -- 455 findings closed by a landed packet

Not open work. Kept here (rather than removed) so the audit trail stays intact --
a disappeared finding is indistinguishable from one never found.
`.claude/notes/_landed_packets.json` is the source of truth for what has landed; see
`_gen_packet_closure.py` for how a packet resolves to the finding ids below.

- [x] **A3-SNAP-3** `core/manager.py:3844` [both] -- **RP-001** (`3ddcc1c`, 2026-07-31)  
  The snapshot has no read of the exactly-once finalize claim, so across the finalize await it reports a finished run as actively cleaning and offers Pause / Cancel on it
- [x] **A5-STR-5** `jobs/active_job.py:2464` [both] -- **RP-001** (`3ddcc1c`, 2026-07-31)  
  async_finalize_stranded_job reports success regardless of the finalizer's answer — a refused finalize still marks the slot 'completed' and fires a bogus EVENT_JOB_FINISHED
- [x] **HW-FINAL-1** `learning/manager.py:737` [both] -- **RP-001** (`3ddcc1c`, 2026-07-31)  
  The exactly-once finalize claim releases BEFORE the permanent gate is written, and an await sits in the gap - the finalize body runs twice
- [x] **A5-SVC-2** `learning/services.py:409` [both] -- **RP-001** (`3ddcc1c`, 2026-07-31)  
  finalize_learning_job fires eufy_vacuum_job_finished with a FABRICATED status "completed" when the finalize was rejected, and (no supports_response) tells the caller nothing
- [x] **A2-LIFE-1** `listeners/lifecycle.py:354` [both] -- **RP-001** (`3ddcc1c`, 2026-07-31)  
  The exactly-once claim's REFUSAL dict is consumed as a successful finalize — the duplicate EVENT_JOB_FINISHED survived the fix and now carries an all-null payload
- [x] **A1-UP-1** `__init__.py:420` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Panels registered outside async_setup_entry are never tracked, so unload can't remove them and setup silently re-adds the "no vacuum configured" fallback panel
- [x] **A1-UP-2** `__init__.py:316` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  async_setup_entry has no failure unwind, and HA never calls async_unload_entry for an entry that failed setup — a mid-setup raise orphans every subsystem registered so far and the next reload builds a second live copy
- [x] **A2-DOWN-1** `__init__.py:420` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Panels registered outside async_setup_entry are never tracked, so unload cannot remove them — and setup then re-adds the "no vacuum configured" fallback panel next to the working one
- [x] **A4-RELOAD-1** `__init__.py:420` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Panels registered outside async_setup_entry are never tracked, so unload never removes them
- [x] **A4-RELOAD-3** `__init__.py:499` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Unload stops the debug capture but never cancels its auto-stop timer, which then kills a later capture
- [x] **A1-INIT-1** `core/manager.py:473` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  async_initialize spawns loop-lifetime work with no teardown — after a config-entry reload the PREVIOUS manager writes its stale self.data over the live store
- [x] **A6-VAC-4** `core/manager.py:1035` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  remove_vacuum_record drops data["room_history"][vacuum] but leaves the _room_history_cache_ready marker — three sibling call sites invalidate it, the one that DELETES the data does not
- [x] **A2-DOWN-3** `core/water_amendment.py:246` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Post-job water-amendment listener + 180s timer, and two hass.data[DOMAIN] cache keys, are created outside setup and never removed by unload
- [x] **A4-RELOAD-4** `core/water_amendment.py:246` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Post-job water-amendment state listener and 180s timeout are never cancelled by unload
- [x] **A1-WIRE-5** `debug_capture.py:510` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  The debug-capture auto-stop timer is not cancelled on unload, so an orphaned timer from before a reload kills a capture started after it
- [x] **DR-DBG-3** `debug_capture.py:483` [n/a (drop-in helper)] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Reload orphans a pending auto-stop timer
- [x] **A1-UP-3** `learning/services.py:901` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Five learning services registered during setup are missing from async_unregister_learning_services, so they survive unload as ghost services
- [x] **A2-DOWN-2** `learning/services.py:901` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  async_unregister_learning_services removes 16 of the 21 services async_register_learning_services registers — 5 survive unload and 3 raise a bare KeyError when called
- [x] **A4-RELOAD-2** `learning/services.py:901` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Five learning services are registered on setup but missing from the unregister list, so they survive unload and entry removal
- [x] **A5-SVC-7** `learning/services.py:901` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Five registered services are never unregistered, surviving integration unload as phantom entries that fail with an unhandled KeyError
- [x] **A1-REG-3** `listeners/discovery.py:96` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Per-vacuum teardown never re-registers listeners, and the documented 'a subscription to a now-deleted entity is inert' invariant is false — discovery keeps running passes for the deleted vacuum and re-creates its setup_progress bucket
- [x] **A6-GUARD-6** `listeners/discovery.py:133` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  Discovery triggers survive per-vacuum deletion and re-create a setup_progress record for the deleted vacuum — the "subscription to a deleted entity is inert" comment is false
- [x] **A1-REG-2** `listeners/lifecycle.py:390` [eufy] -- **RP-003** (`76d92fc`, 2026-07-31)  
  lifecycle registers a state listener + timer (post-job water amendment) whose unsubs are function-local and unreachable from lifecycle.remove()/async_unload_entry — the only unsub leak among the eight modules
- [x] **A2-LIFE-2** `listeners/lifecycle.py:409` [both] -- **RP-003** (`76d92fc`, 2026-07-31)  
  _process tasks are untracked — remove() drops only the subscription, so a config-entry reload orphans an in-flight finalize bound to the dead manager
- [x] **DR-DBG-1** `debug_capture.py:173` [n/a (drop-in helper)] -- **RP-004** (`27824be`, 2026-07-31)  
  exc_info tracebacks are stored UNREDACTED and UNTRUNCATED — both published claims hold only for the message field
- [x] **DR-DBG-2** `debug_capture.py:605` [n/a (drop-in helper)] -- **RP-004** (`27824be`, 2026-07-31)  
  The switch bypasses the auto-stop bookkeeping the services maintain — forgotten override sibling at the entry-point layer
- [x] **DR-DBG-4** `debug_capture.py:374` [n/a (drop-in helper)] -- **RP-004** (`27824be`, 2026-07-31)  
  An unrecognised `areas` value silently produces a capture that records nothing
- [x] **DR-DBG-6** `debug_capture.py:286` [n/a (drop-in helper)] -- **RP-004** (`27824be`, 2026-07-31)  
  status() reports stale started_at / services / areas after a stop
- [x] **DR-DBG-7** `debug_capture.py:457` [n/a (drop-in helper)] -- **RP-004** (`27824be`, 2026-07-31)  
  Two dumps in the same second overwrite each other
- [x] **DR-DIAG-1** `diagnostics.py:570` [both] -- **RP-004** (`27824be`, 2026-07-31)  
  "Everything in _vacuum_diagnostics is read-only" is false — refresh=False does not make the capability call inert
- [x] **DR-DIAG-2** `diagnostics.py:326` [both] -- **RP-004** (`27824be`, 2026-07-31)  
  Nine repr(err) sinks bypass the key-based redaction the docstring promises unconditionally
- [x] **DR-DIAG-3** `diagnostics.py:286` [both] -- **RP-004** (`27824be`, 2026-07-31)  
  A failed health probe is silently absent from the warnings block designed to be read first
- [x] **DR-DIAG-4** `diagnostics.py:539` [both] -- **RP-004** (`27824be`, 2026-07-31)  
  entry.title is dumped unredacted while entry.data and entry.options are redacted
- [x] **HW-DIAG-1** `diagnostics.py:365` [both] -- **RP-004** (`27824be`, 2026-07-31)  
  The job-active warning asserts a run-time failure that is unreachable from the state triggering it — and computes presence from a stale snapshot
- [x] **DR-LR-1** `live_refresh/manager.py:170` [roborock] -- **RP-004** (`27824be`, 2026-07-31)  
  A misdeclared returns_response retries forever at DEBUG and never sticky-disables
- [x] **A5-FACADE-1** `core/manager.py:1434` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  save_managed_rooms facade wipes every stored room for a map when the discovery cache is empty — the precondition its sibling reconcile_room has
- [x] **A5-FACADE-2** `core/manager.py:1426` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  discover_rooms facade overwrites a good persisted discovery cache with an empty one whenever the room source is momentarily unreadable
- [x] **A5-FACADE-3** `core/manager.py:1450` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  rebuild_map facade has the same unguarded total-wipe as save_managed_rooms, with no in-repo caller to compensate
- [x] **A2-REC-4** `rooms/room_crud.py:173` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  migrate replaces the whole room map from one discovery snapshot — any room missing from that snapshot is permanently deleted, guarded only by 'the list wasn't empty'
- [x] **A3-CRUD-1** `rooms/room_crud.py:261` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  save_managed_rooms unconditionally replaces map_bucket["rooms"] — an empty selection or an empty discovery cache silently destroys every stored room on the map
- [x] **A3-ROOMS-1** `services/rooms.py:160` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  save_managed_rooms silently wipes a map's entire saved room configuration when the discovery cache for that map is empty
- [x] **A3-ROOMS-2** `services/rooms.py:83` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  enabled_room_ids: null coerces to [] and wipes every managed room — the exact opposite of omitting the key
- [x] **A4-SETUP-1** `services/setup.py:213` [both] -- **RP-005** (`4217c3c`, `6989031`, 2026-08-01)  
  setup_save_rooms rebuilds the map from the stale/absent `data["discovery"]` cache and REPLACES the map's rooms wholesale — returns {"status": "success"}
- [x] **A1-INIT-2** `core/manager.py:2275` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  Room-history preload overwrites the persisted cache with {} whenever the rebuild throws, and marks the cache ready so it never retries
- [x] **A2-CB-2** `core/manager.py:2275` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  async_preload_room_history_cache replaces the whole per-vacuum room_history subtree AFTER an executor await, silently discarding any room-history written during that await
- [x] **A2-ACC-1** `learning/estimator.py:589` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  A single transient read failure makes record_estimate_accuracy silently overwrite the entire accuracy history with one job's rooms
- [x] **A3-IO-2** `learning/history_store.py:176` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  read_json turns a corrupt or unreadable file into None, and the trouble-rooms read-modify-write then overwrites the file with a one-job store — permanently destroying history that has no rebuilder by design
- [x] **A3-IO-3** `learning/history_store.py:536` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  A failed or absent read is cached as None for the life of the process, and load_*_stats has no bypass — so _reload_learning_stats_now's documented "guarantees the current on-disk stats" is false
- [x] **A4-STATE-8** `learning/history_store.py:327` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  The live snapshot has no clear: last_job_snapshot.json and _live_snapshot_cache are never invalidated after a run, and the stale snapshot's job_id outranks the active job's — a failed snapshot save makes the next finalize overwrite the previous job's record
- [x] **A5-SVC-6** `learning/services.py:447` [both] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  rebuild_learning_stats blanks accuracy_stats before replaying it; any failure after the blank leaves the store empty and the service reports nothing at all
- [x] **A3-IMAGE--2** `mapping/mapping_services.py:1174` [Both. Eufy via engine_exception / missing optional CV libs; Roborock and any adapter without a registered segmenter engine hits it on the very first analyze call via noop_fallback.] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  A failed or unavailable segmenter run overwrites the good cached segmentation with an empty available:False envelope and persists it
- [x] **A3-IMAGE--3** `mapping/mapping_services.py:1100` [Both.] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  The analyze cache-hit gate tests truthiness, so a cached FAILURE envelope is served as a valid cache forever
- [x] **A4-SRC-2** `rooms/source_refresh.py:280` [roborock] -- **RP-006** (`e598e3e`, `b0967eb`, `e35b961`, 2026-08-01)  
  set_cached_room_source is called unconditionally on every successful service call, so a response the flatten shim does not recognise (or an empty maps list) silently REPLACES a good cache with {} — logged at DEBUG only
- [x] **DQ-DE-1** `dispatch/manager.py:317` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  Strict-order per-room phases invert the live-id safety rule: an unresolvable slug dispatches the STALE stored segment id instead of being skipped
- [x] **DQ-ACT-1** `dispatch/manager.py:317` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  When NO target slug resolves live, dispatch falls back to the STALE stored ids — the exact wrong-room outcome the function exists to prevent
- [x] **DQ-ACT-5** `dispatch/manager.py:442` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  The mixed-batch water SAFETY pre-call is best-effort — if it fails the clean still dispatches and the robot wet-mops the vacuum-only rooms
- [x] **A4-SRC-1** `rooms/source_refresh.py:217` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  async_refresh_room_source returns None on success AND on every failure/skip path, and the cache carries no freshness stamp — dispatch cannot tell a fresh live snapshot from an arbitrarily old one, and rewrites the wire payload with stale segment ids while believing it re-resolved live
- [x] **A4-SRC-3** `rooms/source_refresh.py:205` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  flatten_maps_response keys the cache by map NAME with last-writer-wins and no collision detection; a collapsed cache chains into room_discovery's single-map fallback and serves one map's segment ids for a different map_id
- [x] **A4-SRC-4** `rooms/source_refresh.py:274` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  No in-flight coalescing or lock on the refresh: triggers spawn unbounded concurrent get_maps cloud calls, and an older response landing last becomes the resident cached snapshot — including one that started before a map switch and lands after it
- [x] **A4-SRC-5** `rooms/source_refresh.py:80` [roborock] -- **RP-007** (`4c42482`, `4bdd3f8`, 2026-08-01)  
  The room-source cache is never invalidated — not on config-entry unload/reload, not on map switch, not when a vacuum is unmanaged — and it keeps hass.data[DOMAIN] alive so the unload cleanup never fires
- [x] **A3-SNAP-1** `core/manager.py:3948` [roborock] -- **RP-008** (`8d244dc`, 2026-08-01)  
  mop_active collapses "tank sensor unreadable" into a definite False, so the card confidently reports "Vacuuming" and hides the water-level control on Roborock
- [x] **INF-4** `entity_helpers.py:14` [both] -- **RP-008** (`8d244dc`, 2026-08-01)  
  The BLANK_STATE_VALUES docstring asserts a consolidation that is roughly 20% applied
- [x] **A6-PRE-1** `jobs/job_monitor.py:217` [both] -- **RP-008** (`8d244dc`, 2026-08-01)  
  The vacuum-state busy branch is unreachable for every HA-standard vacuum state — an errored or externally-cleaning robot classifies as "ready" and Start dispatches at it
- [x] **A3-COMMON-1** `listeners/_common.py:138` [roborock] -- **RP-008** (`8d244dc`, 2026-08-01)  
  is_job_active() treats a NOT-YET-ADDED / removed job_active entity as "no job running", defeating the Roborock mid-recharge completion guard
- [x] **A3-COMMON-3** `listeners/_common.py:166` [future_brand_only] -- **RP-008** (`8d244dc`, 2026-08-01)  
  completed_finalize_signals() docstring claims it returns "" for unavailable entities; it actually returns the literal "unavailable"/"unknown"
- [x] **A6-GUARD-1** `listeners/path_blockers.py:116` [both] -- **RP-008** (`8d244dc`, 2026-08-01)  
  A blocker sensor going `unavailable` satisfies every negating rule operator, so a Zigbee/cloud dropout pauses or CANCELS a live run (return_to_base)
- [x] **A4-POSE-3** `listeners/pose_sampler.py:129` [roborock] -- **RP-008** (`8d244dc`, 2026-08-01)  
  _is_parked has no working fallback on the native_current_room path — when task_status is unreadable it returns 'not parked', the opposite of what its own docstring claims
- [x] **DR-MNT-1** `maintenance/manager.py:713` [both] -- **RP-008** (`8d244dc`, 2026-08-01)  
  source_available reports True for a MISSING usage_hours attribute, and reset_maintenance's invalid_usage_hours is unreachable for it
- [x] **SN-2** `sensor/maintenance.py:95` [both] -- **RP-008** (`8d244dc`, 2026-08-01)  
  The maintenance sensor's documented availability guard never fires; it publishes a fabricated full-life value
- [x] **INF-5** `entity_helpers.py:57` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  The unique-id scheme is a non-injective flat join with no parser, and its vacuum-key half is open-coded at four sites
- [x] **EP-2** `number.py:101` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  number.py's prefix sweep also destroys NON-room maintenance entities that its callback can never rebuild
- [x] **DR-SENS-2** `sensor/__init__.py:250` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  Two ~40-line dynamic-entity reconciliation blocks are hand-duplicated and must be edited in lockstep
- [x] **SN-3** `sensor/__init__.py:255` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  Two of the four sensor prefix sites are destructive - a room sync on one vacuum deletes a sibling's registry entries
- [x] **SN-7** `sensor/__init__.py:62` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  The stated thread-safety invariant is internally inconsistent, and copies 3 and 4 have already dropped it
- [x] **DR-SETUP-1** `setup/delete.py:136` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  Deleting map N from vacuum.X sweeps every entity of vacuum.X_N from the registry
- [x] **A2-CB-1** `switch.py:71` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  Room-update fan-out identifies "stale" entities by unique_id PREFIX, so a room edit on one vacuum permanently deletes a sibling vacuum's entities from the entity registry
- [x] **A2-CB-5** `switch.py:89` [both] -- **RP-009** (`6ab1b20`, 2026-08-01)  
  Three of the four fan-out subscribers call async_write_ha_state() unguarded while the fourth routes through a hass-is-None guard, so one bad entity aborts the rest of that subscriber's sync silently
- [x] **A2-CAN-3** `jobs/active_job.py:2205` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel OPENS the completion gate it is about to wait for — it clears _phase_dispatch_pending before return_to_base, and neither the gate nor maybe_advance_phase checks _cancel_in_flight
- [x] **A2-CAN-5** `jobs/active_job.py:2101` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Pause has NO in-flight flag at all — a dispatch already inside _dispatch_active_phase lands after vacuum.pause and the robot cleans while the record says 'paused'
- [x] **A2-CAN-6** `jobs/active_job.py:2189` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  async_cancel_active_job is re-entrant — a second cancel arriving inside the 30 s confirm window overwrites finalize_summary with all-None
- [x] **A4-AJ-3** `jobs/active_job.py:2205` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel clears `_phase_dispatch_pending` up front, so the return-to-base dock is read as phase completion and the job advances to the next phase during the 30 s cancel window
- [x] **DQ-ACT-2** `jobs/phase_runner.py:1025` [roborock] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel is defeated by the phase watchdog: _cancel_in_flight is checked once, before two multi-second awaits, then the clean is dispatched unconditionally
- [x] **A1-WD-1** `jobs/phase_runner.py:553` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel is defeated ACROSS _dispatch_active_phase's awaits — the watchdog re-sends a clean after return_to_base, then the run is finalized while the robot keeps cleaning
- [x] **A2-CAN-1** `jobs/phase_runner.py:553` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  Cancel is LOST across _dispatch_active_phase's awaits — the watchdog re-sends a clean AFTER return_to_base and the robot is left cleaning with no job record
- [x] **A2-JOB-2** `services/job_control.py:170` [both] -- **RP-010** (`3e9e969`, `de835ef`, `d3e6139`, 2026-08-01)  
  start_zone_clean is the only start service with zero preconditions — it dispatches to the robot mid-job and strands the tracked room job
- [x] **A2-CAN-4** `jobs/active_job.py:2155` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Pause+resume permanently kills the phase watchdog for room_group and zone phases — resume re-arms ONLY dock phases and never restores the dispatch guard
- [x] **A5-STR-1** `jobs/active_job.py:2378` [eufy] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Strand exclusion consults only task_status against a narrower vocabulary — an Eufy dock service cycle reaps a healthy mid-run job as `interrupted`
- [x] **A5-STR-2** `jobs/active_job.py:2447` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  async_finalize_stranded_job calls the finalizer unguarded — one raising finalize kills the entire reaper tick for every vacuum, every minute, forever
- [x] **A5-STR-4** `jobs/job_monitor.py:357` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  A dispatched run the device never started can never be reaped, then the NEXT run's completion signals finalize the stale slot with the wrong run's data
- [x] **DQ-ACT-3** `jobs/phase_runner.py:552` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  A raising dispatch kills the phase watchdog task and wedges the run in 'started' forever
- [x] **A1-WD-2** `jobs/phase_runner.py:530` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Every abnormal exit from the watchdog leaves _phase_dispatch_pending set, and that state is UN-REAPABLE BY DESIGN — the run wedges in 'started' forever and blocks all future starts
- [x] **A1-WD-3** `jobs/phase_runner.py:889` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  has_native gates on the DECLARED entity-id string (always truthy on both shipped brands), so the coarse fallback is dead code and Eufy verifies phases against a signal its own adapter declares unusable as a live current-room source
- [x] **A1-WD-4** `jobs/phase_runner.py:125` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  An HA restart during a room_group or zone phase's un-confirmed window strands the run — the re-arm covers ONLY dock phases and the comment's claimed recovery path cannot fire
- [x] **A1-WD-5** `jobs/phase_runner.py:891` [future_brand_only] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  Adapter-declared phase_timing overrides are applied with no clamping — poll_seconds: 0 pins the event loop in a hot loop, max_attempts: 0 dispatches nothing and wedges the phase
- [x] **A5-STR-3** `jobs/phase_runner.py:572` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  _phase_dispatch_pending is a permanent strand exclusion — a watchdog that gives up wedges the run AND blinds the reaper that exists to recover it
- [x] **A6-GUARD-4** `listeners/pause_timeout.py:155` [both] -- **RP-011** (`365f90b`, `4cdcf51`, `7f6b969`, 2026-08-01)  
  The 1-minute reap ticker has no in-flight guard while each reap blocks up to ~35s, so two reapable slots guarantee overlapping ticks and a duplicate cancel
- [x] **A4-AJ-1** `jobs/active_job.py:472` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  Mid-job recharge NEVER ends: the recharge-end branch is unreachable dead code, so recharge_seconds_accumulated is always 0 and every recharging run is silently held from learning
- [x] **A4-POSE-1** `listeners/pose_sampler.py:309` [roborock] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  Sampler cadence collapses to min() across all vacuums while the attribution engine multiplies tick counts by each vacuum's OWN declared interval_s — Roborock is sampled at 2.0s but its ticks are valued at 5.0s
- [x] **A4-POSE-2** `listeners/pose_sampler.py:315` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  The sampling timer is fire-and-forget: a tick slower than interval_s overlaps the next tick, double-recording samples and stamping stale pose content with a fresh timestamp
- [x] **A4-POSE-5** `listeners/pose_sampler.py:312` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  _handle_pose_tick has no per-vacuum exception guard, and only the live_pose read is wrapped — one vacuum raising drops every later vacuum from that tick
- [x] **A6-TRK-1** `mapping/tracker.py:320` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  end_job has only ONE caller (successful finalize) — every cancel/abort/strand path leaves the tracker permanently stuck on the finished job's map and rooms
- [x] **A6-TRK-2** `mapping/tracker.py:316` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  resume_sampling is provably unreachable — _sampling_paused is a one-way latch, so all room attribution stops permanently at the first mid-job recharge
- [x] **A6-TRK-3** `mapping/tracker.py:450` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  The HOLD path keeps ACCRUING dwell and movement for a room the robot has already left, inflating duration_seconds and forcing confidence to 1.0
- [x] **A6-TRK-4** `mapping/tracker.py:324` [both] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  The last room of every job never fires room_completed — end_job resets state without flushing the held room
- [x] **DQ-PH-6** `queue/queue_engine.py:466` [future_brand_only] -- **RP-012** (`7269020`, `47f9a25`, `a02fd19`, `6598b0c`, 2026-08-01)  
  advance_active_job_phase resets every per-phase pointer except _native_current_room_id, leaving a latent cross-phase carry-over that only the phases-gate currently hides
- [x] **DQ-PH-1** `learning/history_store.py:996` [both] -- **RP-013a** (`205ef7b`, 2026-08-02)  
  Every break/zone phase flips transit_capture_valid to False, so a stepped run's per-room learning silently degrades to an even split of the run's wall time — charge/wait dock time included
- [x] **A3-IO-1** `learning/history_store.py:989` [both] -- **RP-013a** (`205ef7b`, 2026-08-02)  
  An empty room_timing on a charge/wait/zone phase is read as "capture failed", so every stepped run with a break or a zone is stripped of its accurate per-room timings and learns an even split instead
- [x] **INF-8** `planning/run_plan.py:883` [both] -- **RP-013a** (`205ef7b`, 2026-08-02)  
  The one call site step_types' docstring reasons about by name hand-copies the tuple instead of importing it
- [x] **DQ-PH-3** `jobs/phase_runner.py:301` [eufy] -- **RP-013b** (`f212c20`, 2026-08-02)  
  A multi-room room_group phase is recorded as ONE room — the group's whole cleaning time, area and battery are attributed to its first room and every other room in the group vanishes from the record
- [x] **A3-REC-1** `jobs/phase_runner.py:301` [eufy] -- **RP-013b** (`f212c20`, 2026-08-02)  
  A multi-room room_group phase records ONLY queue_room_ids[0] — the group's whole time/area lands on one room, the other N-1 rooms produce no timing at all, and the run is still flagged high-confidence
- [x] **A3-REC-2** `jobs/phase_runner.py:297` [eufy] -- **RP-013b** (`f212c20`, 2026-08-02)  
  Phase 0's timing is attributed to the whole-run queue's first room, which need not be a room of phase 0 at all
- [x] **A2-CAN-2** `jobs/active_job.py:2255` [both] -- **RP-013c** (`0ff4a8a`, 2026-08-02)  
  Cancelling a sequenced run reports the WRONG missed rooms — per-phase reset of queue_room_ids/completed_room_ids feeds the incomplete-run log and trouble-rooms counters
- [x] **A4-STATE-2** `learning/history_store.py:273` [both] -- **RP-013c** (`0ff4a8a`, 2026-08-02)  
  clear_incomplete_run's docstring claim "(full clean)" is false — ANY completed run erases the missed-room record, and it is unrecoverable because completed_room_ids is never persisted in the job archive
- [x] **A4-STATE-1** `learning/services.py:689` [both] -- **RP-013c** (`0ff4a8a`, 2026-08-02)  
  The final room of EVERY non-completed run is recorded as "missed"; on a stranded run the documented retry automation re-dispatches the robot in an unbounded loop
- [x] **DQ-PH-2** `queue/queue_engine.py:467` [both] -- **RP-013c** (`0ff4a8a`, 2026-08-02)  
  advance_active_job_phase resets completed_room_ids/completed_rooms and no code path ever refills them for a phased job, so an abnormally-ended sequenced run reports every room as missed
- [x] **A4-STATE-6** `learning/history_store.py:1092` [both] -- **RP-013d** (`8f4c5a8`, 2026-08-02)  
  build_completed_job_payload's `queue` block prefers the LIVE queue over the job's own — a room switch flipped mid-run makes both the missed-rooms banner and trouble_rooms name a room that was never in the run
- [x] **A3-REC-4** `jobs/active_job.py:1709` [both] -- **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  Both sample recorders still use the `started_at and not ended_at` predicate the module itself documents as permanently true after finalize, and fan the write out to every map bucket
- [x] **A3-REC-5** `jobs/active_job.py:1721` [both] -- **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  Every counter sample carries battery=None — last_battery_percent is read but never written by anything, so per-room battery attribution is dead on both recording paths
- [x] **A4-AJ-2** `jobs/active_job.py:1676` [both] -- **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  The two sample recorders still use the repudiated `started_at and not ended_at` predicate and write into EVERY map bucket, so a finished or stranded job silently absorbs another run's counters
- [x] **A5-METRICS-2** `listeners/job_metrics.py:172` [both] -- **RP-013e** (`4b0cda3`, `dbbb348`, 2026-08-02)  
  `last_battery_percent` has no writer anywhere in production, so every counter sample carries battery=None and per-room `battery_delta` is permanently null on both dispatch paths
- [x] **A6-VAC-1** `dock/manager.py:154` [eufy] -- **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  Dock-action gate is blind to app-started (external) runs — every dock action reports "Ready" and fires while the robot is mid-run at the dock
- [x] **A3-COMMON-4** `listeners/_common.py:178` [both] -- **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  _common owns the completion QUESTION but not its vocabulary defaults — the clear-sentinel and completion-status fallbacks exist as two hand-copied literals in different modules
- [x] **A3-COMMON-6** `listeners/_common.py:110` [both] -- **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  The listener layer never uses either canonical in-flight predicate — it hand-inlines the status set that dispatched_job_is_in_flight declares itself "THE single answer" to
- [x] **A5-METRICS-1** `listeners/job_progress.py:74` [roborock] -- **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  job_progress ticker gates on a hand-copied {"started","paused"} literal, so app-started (external) runs never get the Lever B live current-room refresh or a progress tick
- [x] **DR-SENS-1** `sensor/lifecycle.py:203` [both] -- **RP-014** (`5c4c0f0`, `9095968`, 2026-08-03)  
  The active_job sensor reports 'none' during an app-started run the system itself considers in flight
- [x] **A6-TRK-5** `mapping/tracker.py:47` [both] -- **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  _norm_room_name normalises differently from slugify_room_name — it merges room identities that rooms/ keeps distinct, and lacks the NFC canonicalisation slugify was given specifically to prevent this
- [x] **A2-REC-2** `rooms/reconciliation.py:84` [both] -- **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  Two rooms with the same name collapse into one identity: phantom id_changed on an unchanged map, and migrate overwrites one room's settings with the other's
- [x] **A1-ID-1** `rooms/room_discovery.py:254` [both] -- **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  slugify_room_name has no uniqueness guarantee and nothing enforces one — two rooms can share a slug, and on Roborock the second one dispatches to the FIRST one's segment id
- [x] **A1-ID-3** `rooms/room_discovery.py:247` [both] -- **RP-015** (`6726b19`, `5af0fa2`, 2026-08-02)  
  A room name that slugifies to empty passes discovery's only validation and is then silently deleted by plan_migration and silently un-cleanable by dispatch
- [x] **A3-IO-6** `learning/history_store.py:138` [both] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  get_paths derives the archive directory from the entity_id's object_id, so renaming the vacuum entity silently orphans all learned history and the predictor restarts from cold with no notice
- [x] **A3-IMAGE--6** `mapping/mapping_services.py:1014` [Both.] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  delete_map_image calls itself the mirror of upload but has no layout_id/art_scope sibling and sweeps no back-references
- [x] **A4-CUSTOM-5** `mapping/mapping_services.py:1379` [Both — saved zones and queue zone steps exist for Eufy and Roborock alike.] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  _generate_saved_zone_id / _generate_custom_layout_id guarantee uniqueness only against LIVE ids, so an id is reused after a delete — and saved-zone ids are durably referenced by queue steps and run profiles
- [x] **A6-ZONE-C-2** `mapping/mapping_services.py:2552` [Both — the zone step and its resolver are brand-agnostic.] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  delete_saved_zone performs no reference check; run-profile and queue `zone` steps keep the dead id and are silently dropped at run time while the UI still lists them
- [x] **A6-ZONE-C-5** `mapping/mapping_services.py:2346` [Both.] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  create_custom_layout force-flips segmentation_mode to "custom" with no record of the prior mode; delete only restores "cv" when zero layouts remain, so create-then-delete strands the user on a layout they never chose
- [x] **A3-PP-CRUD-3** `profiles/manager.py:587` [both] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  rename_room_profile changes the store key and silently orphans every room referencing it — no migration, no reference check, no warning
- [x] **A3-CRUD-4** `rooms/room_crud.py:336` [both] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  remove_map leaves the map's saved run-profile library, queue state and onboarding state behind; re-importing the same map_id resurrects run profiles holding room ids from the deleted segmentation
- [x] **A3-ROOMS-8** `services/room_profiles.py:97` [both] -- **RP-016** (`2feb9e0`, 2026-08-02)  
  delete_room_profile / rename_room_profile leave dangling profile_name references on rooms, which then silently resolve to a built-in preset
- [x] **DQ-Q-5** `maps/map_manager.py:197` [both] -- **RP-018** (`5af0fa2`, 2026-08-02)  
  A map rebuild silently auto-enables AND auto-approves rooms that never existed before, adding them to the clean queue unseen
- [x] **A3-CRUD-6** `maps/map_manager.py:181` [both] -- **RP-018** (`5af0fa2`, 2026-08-02)  
  Both room writers auto-enable and auto-approve rooms the user has never seen (DQ-Q-5 extension: the live instance is save_managed_rooms, not rebuild_map)
- [x] **A3-CRUD-3** `rooms/room_crud.py:279` [both] -- **RP-018** (`5af0fa2`, 2026-08-02)  
  save_managed_rooms auto-confirms floor type for every room it writes, permanently satisfying the onboarding_required start gate with the guessed value "hardwood"
- [x] **A2-REC-8** `rooms/room_manager.py:64` [both] -- **RP-018** (`5af0fa2`, 2026-08-02)  
  The reachable room writer (save_managed_rooms/build_managed_rooms) carries settings by numeric id only, so a renumber stamps one room's floor type and access grants onto a different physical room
- [x] **A3-CRUD-2** `rooms/room_manager.py:64` [both] -- **RP-018** (`5af0fa2`, 2026-08-02)  
  build_managed_rooms matches stored rooms by numeric id while room identity is the slug — a re-save after a re-segment transplants the previous occupant's access grants, rules and dock flag onto a different physical room and erases the reconciliation evidence
- [x] **A3-CRUD-5** `rooms/room_manager.py:57` [both] -- **RP-018** (`5af0fa2`, 2026-08-02)  
  A re-save resurrects a room the user explicitly rejected as a phantom — build_managed_rooms never consults rejected_rooms
- [x] **A6-GUARD-5** `listeners/discovery.py:140` [both] -- **RP-019** (`0e0369f`, 2026-08-02)  
  A discovery pass on the active map is scored against configured rooms across ALL maps, so switching maps makes the other map's rooms accrue "removed" strikes
- [x] **A2-REC-3** `rooms/reconciliation.py:125` [roborock] -- **RP-019** (`0e0369f`, 2026-08-02)  
  A room renamed AND renumbered in the same edit is invisible to reconciliation — and migrate then deletes its stored data as if it were a stranger
- [x] **A2-REC-1** `rooms/room_crud.py:68` [both] -- **RP-019** (`0e0369f`, 2026-08-02)  
  Reconciliation never runs in production: no trigger, no schedule, no UI — the reviews are computed into a payload nothing reads
- [x] **A2-REC-5** `rooms/room_crud.py:162` [both] -- **RP-019** (`0e0369f`, 2026-08-02)  
  migrate applies a plan the user never saw: it never re-checks the reviews, and rebuilds the map even when there are none
- [x] **A2-REC-6** `rooms/room_crud.py:99` [both] -- **RP-019** (`0e0369f`, 2026-08-02)  
  Applying a 'renamed' review orphans that room's learned baselines, while the code comment claims history follows the room regardless
- [x] **A2-REC-7** `rooms/room_crud.py:118` [both] -- **RP-019** (`0e0369f`, 2026-08-02)  
  action='ignore' writes reconciliation_dismissed_at that no code ever reads — dismissed reviews resurface on every discovery
- [x] **A1-ID-2** `rooms/room_discovery.py:176` [roborock] -- **RP-019** (`0e0369f`, 2026-08-02)  
  discover_rooms_for_vacuum's single-map fallback serves ANOTHER map's room list and relabels it with the REQUESTED map_id, defeating the map_id filter at both room writers
- [x] **A1-ID-4** `setup/drift.py:540` [both] -- **RP-019** (`0e0369f`, 2026-08-02)  
  Drift keys its history by bare device room_id across ALL maps but feeds it only the ACTIVE map's discovery, so a multi-map vacuum's inactive rooms decay toward 'removed' and colliding ids mask each other
- [x] **A4-STATE-3** `learning/history_store.py:301` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  trouble_rooms.json is keyed by raw room_id and scoped per-vacuum, so its counters silently reattach to the wrong physical room after a re-segment or on a second map — the one id-keyed store reconcile-migrate forgets
- [x] **A4-STATE-4** `learning/history_store.py:247` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  incomplete_run.json's missed_room_ids survive a re-segment and a map switch, and the card applies them to whatever map is active — wiping the user's selection and enabling the wrong rooms
- [x] **A4-STATE-5** `learning/history_store.py:306` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  trouble_rooms is a raw-counter store with no rebuilder, no clear service and a denominator that only advances when the room is queued — the "decays on its own" justification for excluding it from repair does not hold
- [x] **A4-STATE-9** `learning/services.py:892` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  Dismissing the incomplete-run banner is client-only and no clear service is exposed, so the banner returns on every card load
- [x] **A5-SVC-1** `learning/services.py:555` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  exclude_learning_job / restore_learning_job report "stats rebuilt" but never rebuild the three incremental accumulators — the excluded run's poison stays in accuracy_stats, learned_zones and battery aggregates
- [x] **A5-SVC-5** `learning/services.py:492` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  record_estimate_accuracy writes accuracy_stats to disk but never invalidates the manager's in-memory accuracy cache, so estimates keep serving the pre-write numbers
- [x] **A5-SVC-8** `learning/services.py:450` [both] -- **RP-020** (`f48dee2`, 2026-08-02)  
  invalidate-then-preload is a no-op when a preload is already in flight, letting a stale in-flight load repopulate the cache with pre-rebuild data
- [x] **A4-START-1** `core/manager.py:2863` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  get_start_status validates PHASE 0's room count as if it were the whole job — a stepped run whose first phase is a zone is refused with a false "invalid payload" error
- [x] **A4-START-2** `core/manager.py:5021` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  start_selected_rooms dispatches phase 0 with no phase_type branch, unlike its phase_runner sibling — and _build_steps_phases' docstring claims a guard that does not exist
- [x] **A6-PRE-2** `jobs/job_monitor.py:268` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  invalid_payload uses phase 0's room count as the whole run's room count — a saved run profile whose first step is a zone is accepted on save but can never start
- [x] **DQ-Q-1** `planning/run_plan.py:902` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  Stepped run silently collapses to ONE atomic dispatch when every break phase is trimmed — per-group settings and group sequencing are discarded
- [x] **DQ-Q-3** `planning/run_plan.py:884` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  A run profile whose first step is a zone is permanently unstartable and reports "Room-clean payload is missing or invalid"
- [x] **A5-PP-RP-1** `planning/run_plan.py:1352` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  A multi-room_group plan with no charge/wait/zone is silently flattened to ONE atomic dispatch — the card routes it as sequenced
- [x] **A5-PP-RP-3** `planning/run_plan.py:1379` [roborock] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  _build_steps_phases can return an empty list; `phases[0]` then raises IndexError inside get_start_status, killing the whole dashboard snapshot (Roborock)
- [x] **A5-PP-RP-4** `planning/run_plan.py:902` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  The collapse fallback's `all_ids` is provably always [] — and the unit test manufactures the very key the real engines never emit
- [x] **A5-PP-RP-5** `planning/run_plan.py:884` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  A user-authored leading or trailing charge/wait step is silently deleted at dispatch while the card still shows it and stamps has_charge_steps
- [x] **A5-PP-RP-6** `planning/run_plan.py:1458` [roborock] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  A stepped Roborock run enforces clean order but still tells the user the order is advisory
- [x] **A6-PP-EST-LBL-1** `planning/run_plan.py:436` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  _room_surface_labels is fed a key that resolved_rooms never carries, so floor_type_label is always None at both display sites
- [x] **DQ-DE-2** `queue/dispatch_engines.py:110` [future_brand_only] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  _SinglePhaseMixin silently swallows strict_order and the seam cannot express refusal — while the caller hides the order advisory on the strength of the request alone
- [x] **DQ-DE-5** `queue/dispatch_engines.py:211` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  Engine phase envelopes omit queue_room_ids/queue_rooms, making the run-plan group-union computation dead code and emptying queue_rooms on every phase advance
- [x] **DQ-Q-7** `queue/queue_engine.py:242` [both] -- **RP-021a** (`8f9d5db`, 2026-08-02)  
  build_room_clean_payload treats an empty queue_room_ids as "no filter" rather than "no rooms", so a cleared queue yields a payload containing every enabled room
- [x] **A4-PP-RP-2** `profiles/manager.py:1086` [both] -- **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  overwrite_run_profile unconditionally destroys a saved profile's step sequence; save_run_profile preserves it — same "snapshot the current run" contract, opposite behaviour
- [x] **A4-PP-RP-1** `profiles/manager.py:1232` [both] -- **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  A stepped run profile silently discards the per-room settings it was saved with; apply falls back to whatever the rooms happen to be set to now
- [x] **A4-PP-RP-6** `profiles/manager.py:779` [both] -- **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  normalize_run_profile_steps passes arbitrary per-room fields through untouched, and the run-plan overlay treats them as authoritative settings — the one dispatch path that skips _protected_room_config
- [x] **A5-RUNPROF-4** `services/run_profiles.py:85` [both] -- **RP-021b** (`f208788`, `0fa6cd9`, `4c93fb5`, `e2a424c`, 2026-08-03)  
  set_run_profile_steps accepts a bare `list` and silently drops or clamps every malformed step; only 'at least one room_group survived' is enforced
- [x] **A4-PP-RP-4** `profiles/manager.py:1244` [both] -- **RP-021c** (`176c73e`, 2026-08-04)  
  apply_run_profile leaves no backend record that the applied profile is stepped, so a plain Start runs it flat — or inherits the map's unrelated leftover breaks
- [x] **DQ-ZONE-5** `core/manager.py:4030` [both] -- **RP-022** (`1288b65`, 2026-08-02)  
  zone_bounds is computed and shipped in the dashboard snapshot but has no consumer anywhere — and the card replaces the precise refusal message with a generic toast
- [x] **A3-SNAP-4** `core/manager.py:4017` [future_brand_only] -- **RP-022** (`1288b65`, 2026-08-02)  
  zone_max invents Eufy's device limit (10) for any brand that declares none, while the dispatch gate enforces no cap at all when the key is absent
- [x] **DQ-PAY-4** `dispatch/manager.py:182` [eufy] -- **RP-022** (`1288b65`, 2026-08-02)  
  Zone-clean repeat cap defaults to 3 for Eufy while the framework's own room-clean cap for Eufy is 2, and the service schema has no upper bound
- [x] **DQ-ZONE-1** `dispatch/manager.py:234` [eufy] -- **RP-022** (`1288b65`, 2026-08-02)  
  Zone-clean pass count is never clamped on the Eufy branch — the clamp lives inside the device_mm branch Eufy never enters
- [x] **DQ-ZONE-2** `dispatch/manager.py:120` [both] -- **RP-022** (`1288b65`, 2026-08-02)  
  supports_zone_clean is honored by the card but never consulted by the actuation path
- [x] **DQ-ZONE-3** `dispatch/manager.py:203` [future_brand_only] -- **RP-022** (`1288b65`, 2026-08-02)  
  Per-zone SIZE bounds are enforced by coordinate-space branch, not by which bound the adapter declared — the other combination is silently ignored
- [x] **DQ-ZONE-4** `dispatch/manager.py:216` [eufy] -- **RP-022** (`1288b65`, 2026-08-02)  
  Eufy per-side bound check is skipped entirely when live-map dims are unreadable, while the mm branch REFUSES on the same missing input
- [x] **A1-SERVIC-3** `mapping/mapping_services.py:493` [Eufy (unclamped). Roborock is protected by the device_mm-branch clamp.] -- **RP-022** (`1288b65`, 2026-08-02)  
  `clean_times` has no upper bound, defended by a sibling comment claiming dispatch enforces the per-brand ceiling — dispatch clamps it only on the Roborock (`zone_coords: device_mm`) branch; the Eufy branch ships it verbatim
- [x] **A6-ZONE-C-8** `mapping/mapping_services.py:2482` [Both (Eufy 0.5-10 m per side, Roborock 1 ft²-3.05 m²), per the caps quoted in the _handle_clean_saved_zones docstring at 2641-2642.] -- **RP-022** (`1288b65`, 2026-08-02)  
  Zone size limits are not enforced at author time, contradicting the doc — an un-cleanable zone can be saved and only fails when the user taps clean
- [x] **A2-JOB-4** `services/job_control.py:130` [eufy] -- **RP-022** (`1288b65`, 2026-08-02)  
  start_zone_clean clean_times has no upper bound; the schema comment claims a dispatch-side per-brand ceiling that exists only on the Roborock branch
- [x] **A6-PP-EST-BLK-1** `planning/run_plan.py:1615` [both] -- **RP-023a** (`d76d110`, `333c3db`, 2026-08-03)  
  Mid-job path-block report walks reachability over the QUEUE only, so any queued room whose access parent is not in the queue is reported blocked — and can cancel the job
- [x] **A5-AG-1** `planning/run_plan.py:1615` [both] -- **RP-023a** (`d76d110`, `333c3db`, 2026-08-03)  
  Mid-run reachability is queue-scoped while preflight is graph-scoped — a run that omits the dock room reports EVERY remaining room as access_blocked and can cancel the job
- [x] **A5-FACADE-4** `core/manager.py:1239` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  save_user_room_profile facade silently overwrites the existing 'user_1' profile when profile_name is omitted, while its sibling mints a unique id
- [x] **A6-PP-EST-DSP-1** `planning/run_plan.py:125` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  A room stamped profile_name="custom" is re-labelled as the brand's DEFAULT preset ("Vacuum Quick") with is_custom_profile=False — proven for any mop room on hardwood
- [x] **A6-PP-EST-DSP-2** `planning/run_plan.py:125` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  _settings_profile_display's "selected != resolved" custom-detection arm is dead for every name the resolver can rewrite — a carpet-downgraded mop room is still labelled "Vacuum + Mop Quick"
- [x] **A3-PP-CRUD-2** `profiles/manager.py:157` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  Applying a mop room profile instantly rewrites the room's profile_name to "custom" — the profile the user just picked does not stay selected
- [x] **A3-PP-CRUD-5** `profiles/manager.py:322` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  save-a-room-as-a-profile is not a round trip: path_type is discarded and re-derived from clean_intensity
- [x] **A3-PP-CRUD-8** `profiles/manager.py:73` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  Generated profile ids are local-time second-resolution and saves have no exists check, so two saves in one second silently destroy the first
- [x] **A4-PP-RP-5** `profiles/manager.py:77` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  Run-profile ids are generated at one-second resolution and assigned without a collision check, so two saves in the same second silently overwrite each other
- [x] **A1-PP-RES-2** `profiles/room_profiles.py:435` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  water_level and carpet fan_speed use a DIFFERENT precedence than every sibling field (floor default OVERRIDES the profile), so applying a built-in mop profile immediately re-labels the room "custom"
- [x] **A1-PP-RES-3** `profiles/room_profiles.py:419` [eufy] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  path_type resolves to the literal string "None" for any room backfilled by the startup migration, and that string reaches the Eufy wire payload
- [x] **A1-PP-RES-4** `profiles/room_profiles.py:448` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  "granite" and "concrete" are user-selectable floor types with no entry in either brand's FLOOR_TYPE_WATER_DEFAULTS, so the mop-with-no-water correction corrects to empty string
- [x] **A1-PP-RES-7** `profiles/room_profiles.py:284` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  A room pointing at a deleted or renamed custom profile silently resolves to the default profile — the UI reports a profile the room is not running
- [x] **A6-PP-EST-H2O-1** `profiles/room_profiles.py:140` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  granite and concrete are user-selectable floor types but are absent from every floor_type_water_defaults table, so a mop room there resolves water_level "" and is estimated as if it were dry
- [x] **DQ-PAY-2** `queue/queue_engine.py:303` [both] -- **RP-024** (`9abcb69`, `71cc479`, 2026-08-02)  
  A mop room on a granite or concrete floor resolves water_level to the empty string and that empty string is written verbatim to the wire
- [x] **A1-INIT-5** `core/manager.py:429` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  The startup backfill and setup_progress migration hard-code Eufy vocabulary and structurally cannot consult the adapter
- [x] **A1-EST-7** `learning/estimator.py:238` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  _load_mop_wash_config hard-codes Eufy's wash-frequency bounds (15/20/25) in the brand-agnostic estimator while the adapter already declares wash_frequency_bounds
- [x] **A1-EST-8** `learning/estimator.py:829` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  is_mop raw-compares clean_mode against a hand-copied literal set while the very same function canonicalizes it for the stats lookup
- [x] **A2-LIFE-3** `listeners/lifecycle.py:169` [eufy] -- **RP-025** (`71cc479`, 2026-08-02)  
  The inline mop-wash detector diverges from the dedicated dock_events listener: hard-coded Eufy wash vocabulary as a fallback, and no same-state guard against attribute-only re-triggers
- [x] **A5-PP-RP-7** `planning/run_plan.py:125` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  _settings_profile_display hardcodes the Eufy-era built-in profile-name set and takes no vacuum_entity_id, so a brand with its own profile keys renders every room as "Custom"
- [x] **A5-PP-RP-8** `planning/run_plan.py:142` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  The water-off suppression in _settings_profile_display compares against the literal "off" instead of the brand's no-water value
- [x] **DQ-Q-2** `profiles/manager.py:148` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  _match_profile_from_fields is structurally brand-blind and rewrites every Roborock room's profile_name to "custom" on every start
- [x] **DQ-PAY-1** `profiles/manager.py:225` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  Applying a built-in room profile to a Roborock room writes EUFY vocabulary onto the room; the fresh room_defaults fix covers creation only
- [x] **DQ-PAY-6** `profiles/manager.py:108` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  _protected_room_config stamps the Eufy literal "Off" into every non-mop room's water_level regardless of brand, on the path into the payload builder
- [x] **A3-PP-CRUD-1** `profiles/manager.py:631` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  apply_room_profile writes Eufy vocabulary onto Roborock rooms — the catalog it resolves is inert
- [x] **A3-PP-CRUD-4** `profiles/manager.py:257` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  get_effective_room_details resolves with no catalog — Eufy floor defaults override a Roborock carpet room, and "Quick" is injected where the brand has no intensity axis
- [x] **A3-PP-CRUD-6** `profiles/manager.py:47` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  Protected-profile-name set is frozen from the Eufy in-code catalog, so a brand's own built-ins are unprotected and can be shadowed by a user profile
- [x] **A3-PP-CRUD-7** `profiles/manager.py:104` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  _protected_room_config is the only writer in the finalize pipeline and it stamps the Eufy literal "Off" onto every non-mop room, on both brands
- [x] **DQ-Q-4** `profiles/room_profiles.py:209` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  normalize_room_profile re-injects the Eufy literal "Quick" for clean_intensity, defeating Roborock's deliberate omission of the axis
- [x] **DQ-Q-6** `profiles/room_profiles.py:519` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  apply_capability_gate and _protected_room_config hardcode Eufy display literals for the framework's 'no water' / 'default path' concepts
- [x] **A1-PP-RES-5** `profiles/room_profiles.py:294` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  get_available_profile_names hardcodes the four Eufy built-in keys, so get_available_profiles silently drops every user-saved custom profile and would return {} for a brand with different catalog keys
- [x] **A1-PP-RES-6** `profiles/room_profiles.py:209` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  normalize_room_profile injects the Eufy literal "Quick" whenever the brand's normalize_defaults omits clean_intensity, and apply_room_profile_to_config PERSISTS it into Roborock room storage
- [x] **A1-PP-RES-8** `profiles/room_profiles.py:165` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  resolve_profile_catalog's `or` fallbacks mean a brand cannot declare an intentionally EMPTY block — it silently inherits Eufy's
- [x] **A1-PP-RES-9** `profiles/room_profiles.py:366` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  Dead branch in resolve_profile_name_for_constraints, and the carpet downgrade only knows the four framework built-in names
- [x] **A2-PP-CAP-1** `profiles/room_profiles.py:560` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  apply_room_profile_to_config's `catalog` brand-safety parameter is structurally unreachable on every production call — the guard exists, the test passes, and the code path can never take it
- [x] **A2-PP-CAP-2** `profiles/room_profiles.py:209` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  normalize_room_profile's third-level literals are the one fallback a brand CANNOT override — the more deliberately a brand omits an axis, the more certainly it gets the Eufy literal for it
- [x] **A2-PP-CAP-3** `profiles/room_profiles.py:496` [eufy] -- **RP-025** (`71cc479`, 2026-08-02)  
  clean_intensity has no capability flag and reaches the Eufy wire on devices whose capability detection just concluded the intensity axis is absent
- [x] **A2-PP-CAP-4** `profiles/room_profiles.py:294` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  get_available_profile_names hardcodes the four Eufy catalog KEYS and takes no catalog — get_available_profiles merges every user-created profile in and then filters all of them back out
- [x] **A2-PP-CAP-6** `profiles/room_profiles.py:509` [roborock] -- **RP-025** (`71cc479`, 2026-08-02)  
  apply_capability_gate hardcodes the Eufy literal "Off" in three places for the framework's own 'no water' concept
- [x] **A2-PP-CAP-7** `profiles/room_profiles.py:166` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  resolve_profile_catalog uses `or` for every key, so a brand that explicitly declares an EMPTY block silently gets Eufy's
- [x] **A6-PP-EST-TD-1** `profiles/room_profiles.py:14` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  TypedDict drift: ProfileRecord's "all always present" claim is false for the shipped Roborock catalog, and capability_gated is declared bool but written as a dict
- [x] **DQ-PAY-5** `queue/queue_engine.py:182` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  _write_room_field's value_map is fail-open: an unmapped canonical value is emitted raw, and the framework itself injects Eufy literals no adapter can declare a mapping for
- [x] **EP-8** `room_entities.py:217` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  Hand-copied room defaults, including two that disagree about the same missing key
- [x] **A6-DIAG-8** `services/dock.py:51` [future_brand_only] -- **RP-025** (`71cc479`, 2026-08-02)  
  Dock event-type vocabulary is hand-copied into three places, none derived from the adapter that declares it
- [x] **A3-ROOMS-6** `services/rooms.py:102` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  update_room_fields accepts any clean_mode string; a casing/spelling variant keeps water in storage and in the UI but silently drops it from the wire payload
- [x] **A3-ROOMS-9** `services/rooms.py:103` [both] -- **RP-025** (`71cc479`, 2026-08-02)  
  update_room_fields accepts any fan_speed string; on Roborock an unrecognised value leaves the device's previous suction in place with no error
- [x] **A1-LC-1** `mapping/map_source_coordinator.py:397` [eufy] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Eufy in-memory map/pose source has NO vacuum identity — a second Eufy robot is served the FIRST robot's map, rooms, pose and render raster
- [x] **A1-LC-3** `mapping/map_source_coordinator.py:261` [eufy] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  The storage-path mtime cache early-return omits the `map_id` check its sibling `_commit_result` performs, so map A's geometry is returned as map B's answer with `present: True`
- [x] **A1-LC-5** `mapping/map_source_coordinator.py:136` [both] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  `_commit_result` is blind last-writer-wins across the storage path's two executor awaits — a refresh started before a map switch can commit after a newer one
- [x] **A3-EXT-1** `mapping/map_source_runtime.py:839` [eufy] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Eufy in-memory map/pose source has NO device selection — every vacuum gets coordinators[0]'s map
- [x] **A3-EXT-2** `mapping/map_source_runtime.py:966` [eufy] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Content version hashes ONLY the room raster, but the cache it gates holds the grid geometry the fork mutates independently
- [x] **A4-RB-1** `mapping/map_source_runtime.py:373` [roborock] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  Roborock MapData lookup never binds the found map to the requested map_id — a multi-map (multi-floor) device converts drawn zones in the wrong floor's coordinate frame
- [x] **A4-RB-2** `mapping/map_source_runtime.py:1005` [roborock] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  No device scoping anywhere in the Roborock candidate walk — on a two-vacuum Roborock account the card's rendered raster and the diagnostics drift report come from an arbitrary robot
- [x] **A4-RB-3** `mapping/map_source_runtime.py:743` [roborock] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  roborock_result_from_candidates hard-returns on the first duck-typed MapData match, so one false positive permanently blanks the Roborock map source — and the stale-hold masks it for six hours
- [x] **A4-RB-4** `mapping/map_source_runtime.py:511` [roborock] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  rooms_from_mapdata publishes the live segment number as the room's only identity and synthesizes the name, so after a Roborock re-map a tap on room A selects room B
- [x] **A4-RB-5** `mapping/map_source_runtime.py:427` [roborock] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  roborock_geometry_drift_from_candidates pairs a MapData and a MapContent found by two independent BFS walks with no check they are the same map, and reports present:True regardless of the verdict
- [x] **A4-RB-6** `mapping/map_source_runtime.py:760` [roborock] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  image_entity_object silently drops the only per-vacuum candidate root on any HA-internals change, while the presence gate still reports the map as present
- [x] **A7-ROBORO-3** `mapping/roborock_raw_map.py:163` [roborock (the identical raster-only version hash exists for eufy in map_source.eufy_version_of, out of scope here)] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  `version` hashes the raster ONLY, while the payload also ships room_names — a room rename cannot invalidate a fetched render payload
- [x] **SN-5** `sensor/map_overlays.py:50` [both] -- **RP-026** (`e434813`, `382d3d5`, 2026-08-02)  
  The overlays sensor serves a cache entry without checking its map_id or its stale flag
- [x] **A1-LC-2** `mapping/map_source_coordinator.py:126` [both] -- **RP-027** (`382d3d5`, 2026-08-02)  
  Sticky last-known-good hold re-serves a frozen current_room/robot_anchor as `present: True`; the `stale` flag it sets has NO consumer, so a docked Roborock reports a phantom room for up to 6 hours
- [x] **A1-LC-4** `mapping/map_source_coordinator.py:266` [eufy] -- **RP-027** (`382d3d5`, 2026-08-02)  
  The same mtime early-return skips `_apply_inmem_pose_to_result`, freezing the robot/dock/current_room/path overlays for as long as the store file is unchanged
- [x] **A2-GEO-1** `mapping/map_source_coordinator.py:520` [eufy] -- **RP-027** (`382d3d5`, 2026-08-02)  
  Live-pose room lookup projects a MEMORY-frame robot pixel through STORAGE-frame geometry (no memory fallback, no store_version guard) — feeds room attribution at 2 s
- [x] **A5-POSE-1** `mapping/map_source_coordinator.py:489` [eufy] -- **RP-027** (`382d3d5`, 2026-08-02)  
  Live pose is normalized and room-looked-up against .storage geometry while the map it is drawn on is memory-PRIMARY — the one reader never repointed
- [x] **A5-POSE-2** `mapping/map_source_coordinator.py:127` [both] -- **RP-027** (`382d3d5`, 2026-08-02)  
  `stale` / `stale_since` / `stale_reason` are written by the hold path and read by nothing — the docstring's "the card dims/badges it" is false
- [x] **A5-POSE-3** `mapping/map_source_coordinator.py:491` [eufy] -- **RP-027** (`382d3d5`, 2026-08-02)  
  The pose-geometry .storage read skips the `store_version` guard that every other reader of the same file applies
- [x] **A5-POSE-4** `mapping/map_source_coordinator.py:528` [eufy] -- **RP-027** (`382d3d5`, 2026-08-02)  
  The live pose carries no freshness stamp, so a frozen `_robot_pixel` is reported as `present: True` forever — and the fork's own `_last_robot_render` timestamp is ignored
- [x] **A5-POSE-5** `mapping/map_source_coordinator.py:266` [eufy] -- **RP-027** (`382d3d5`, 2026-08-02)  
  `_refresh_storage_map_source`'s mtime early-return bypasses the live-pose override entirely, re-serving the frozen pose it exists to kill
- [x] **A1-SERVIC-1** `mapping/mapping_services.py:450` [Both, but the rename trigger is Roborock-specific (map_id = user-editable map NAME from the select entity state). Eufy's numeric map ids make the accidental rename case unlikely; the empty/sentinel map_id case affects both.] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  No mapping write service can tell "this map exists" from "this map does not" — every schema takes a free-form map_id and every handler mints the bucket, so an edit against a non-existent map is persisted to a phantom bucket and reported as saved
- [x] **A1-SERVIC-5** `mapping/mapping_services.py:563` [Both.] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  services.yaml documents map_id as optional ("Leave blank to use the current active map") on 8 mapping services whose schemas make it `vol.Required`; the integration's shared resolver `resolved_call_data` is used 59 times elsewhere and zero times in this file
- [x] **A3-IMAGE--5** `mapping/mapping_services.py:896` [Both; Roborock materially more exposed because get_active_map_id returns the user-authored map NAME verbatim.] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  Image filenames are built from an unsanitised free-form map_id, so one map's upload can silently overwrite another map's image
- [x] **A4-CUSTOM-1** `mapping/mapping_services.py:1667` [Both (Eufy + Roborock) — custom layouts are brand-independent map-bucket state.] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  set_custom_segments is a REPLACE-ALL write that cannot name its target layout — it lands on whatever layout is active at call time, destroying another layout's authored geometry
- [x] **A5-FURNIS-1** `mapping/mapping_services.py:2108` [both] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  map_id is documented as optional + auto-resolving on 6 presentation services but is vol.Required; a literal blank map_id silently mints and writes a phantom map bucket
- [x] **A6-ZONE-C-6** `mapping/mapping_services.py:2545` [Both for the phantom-bucket mechanism. The rename trigger is Roborock-specific (map NAME as id); the Roborock select's state changing on an in-app rename is near-certain but is device behaviour I could not verify from source.] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  Every handler in the block mints a persisted map bucket for an unknown map_id — including on the pure not-found and read-only clean paths
- [x] **A6-DIAG-6** `services/dock.py:124` [both] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  set_dock_event_count overwrites and immediately saves a durable counter for any entity_id, with no managed-vacuum check and no way back except the response body
- [x] **A6-DIAG-5** `services/errors.py:93` [both] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  get_recent_errors — a read-only service — creates and persists a durable error_tracker record for any entity_id the caller names
- [x] **A2-JOB-8** `services/queue.py:151` [both] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  Queue mutators create and persist a storage bucket for any syntactically-valid entity id, including one that is not a vacuum this integration manages
- [x] **A5-RUNPROF-8** `services/snapshots.py:78` [both] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  No service here checks that vacuum_entity_id is a vacuum this integration manages; unknown ids create durable storage buckets, and a read service writes
- [x] **A2-DRAFT-4** `themes/manager.py:111` [both] -- **RP-028** (`b8d6ca2`, `63b7e3b`, 2026-08-02)  
  _get_vacuum_theme creates per-vacuum draft state for ANY well-formed entity id, so update_working_draft / revert_draft / set_active_theme return ok:true for a vacuum that does not exist and persist a record nothing can reach
- [x] **A2-POLYGO-3** `mapping/mapping_services.py:762` [Both (get_map_segments serves CV and custom scopes identically; on Roborock it bites in custom mode via the active layout's stores)] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  `_apply_segment_adjustments` returns the PERSISTED segment dicts by reference, and its caller writes `room_id` into them - baking a cleared/moved room link permanently into .storage and breaking the documented 1:1 invariant
- [x] **A3-IMAGE--7** `mapping/mapping_services.py:1012` [Both.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  delete_map_image drops the storage record and reports deleted:True even when the file removal failed, and analyze's filesystem probe then re-uses the orphan
- [x] **A4-CUSTOM-3** `mapping/mapping_services.py:1449` [Eufy only — on Roborock async_get_map_data_dict returns None early (map_source_coordinator.py:683), so nothing is written.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  _backfill_saved_zone_area fails OPEN on an indeterminate active map and permanently persists area_m2 / room_number computed from the WRONG map's raster — the poisoned value never self-heals
- [x] **A4-CUSTOM-4** `mapping/mapping_services.py:1467` [Eufy only — zone_membership returns room_number=None on Roborock (no per-pixel raster), so the `membership.get('room_number') is not None` arm never fires there.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  _backfill_saved_zone_area overwrites a user's explicit 'Unassigned' filing — room_number=None means both 'never computed' and 'user chose Unassigned', and the read path cannot tell them apart
- [x] **A6-ZONE-C-1** `mapping/mapping_services.py:2608` [Both. Roborock is more exposed: map_id is the vendor map NAME read off a select entity that goes `unavailable` whenever the upstream integration reloads, and the wrong-map projection can land on a different FLOOR.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  Saved-zone clean dispatches to the device when the active-map signal is blank — the "active map only" guard is permissive, not a refusal
- [x] **A6-ZONE-C-3** `mapping/mapping_services.py:2490` [Both.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  The `map_version` re-map invalidation the design doc specifies as the zone's safety key does not exist anywhere in the codebase
- [x] **A6-ZONE-C-4** `mapping/mapping_services.py:2503` [Eufy only — async_get_map_data_dict is the Eufy-only coordinator accessor (degrades to None elsewhere per docs/dev/frontend/saved-zones.md Wave 2), so on Roborock both fields simply stay None.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  create_saved_zone files area_m2 + room_number from whatever raster is live when the active map is indeterminate, and that wrong value can never be corrected
- [x] **A6-ZONE-C-7** `mapping/mapping_services.py:2614` [Both.] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  Both clean handlers ignore the zone's `kind`, so a zone saved with any non-"clean" kind is still dispatched as a clean
- [x] **A2-POLYGO-1** `mapping/segment_primitives.py:277` [Both (custom layouts are brand-agnostic; Roborock declares segmenter_engine='noop_fallback' so the custom compose path is its ONLY segment source, making this its primary path)] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  Authored custom segments grow ~1 working-pixel toward +X/+Y on every save, and the growth compounds without bound across save/reload cycles
- [x] **A2-POLYGO-2** `mapping/segment_primitives.py:267` [Both (custom layouts are brand-agnostic; worst for Roborock, whose segmenter_engine is 'noop_fallback' so custom layouts are its only segment store)] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  `rasterize_primitives` returns the same `[]` for 'numpy/Pillow missing' as for 'degenerate shape', so set_custom_segments silently wipes the layout and reports saved:true
- [x] **A2-POLYGO-4** `mapping/segment_primitives.py:221` [Both (brand-agnostic custom-layout authoring)] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  `mask_to_polygon` keeps only the largest traced loop, so merging two non-touching shapes into one room silently discards every piece but the biggest
- [x] **A2-POLYGO-8** `mapping/segment_primitives.py:305` [Both (brand-agnostic custom-layout authoring)] -- **RP-029** (`63b7e3b`, 2026-08-02)  
  A malformed primitive is silently skipped mid-segment, so a partially-drawn room saves as a success with no signal in the response
- [x] **A2-GEO-3** `mapping/map_source.py:191` [eufy] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  normalize_rendered CLAMPS out-of-grid pixels onto the map border instead of rejecting them, so off-grid raster cells and bad poses fold onto an edge rather than disappearing — diverging from the card's own decoder, which drops them
- [x] **A2-GEO-5** `mapping/map_source.py:314` [both] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  A room's normalized bbox excludes its last pixel row/column while width_m/height_m on the same dict include it (+1) — the two size descriptors disagree by exactly one cell, and Roborock's equivalent omits the +1
- [x] **A2-GEO-6** `mapping/map_source.py:387` [eufy] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  zone_membership's docstring says the dominance vote counts cells 'whose centre falls inside the zone polygon'; the code tests the cell's top-left corner
- [x] **A3-EXT-3** `mapping/map_source.py:686` [eufy] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  A dropped/renamed upstream geometry field degrades to a confidently WRONG map, not a loud absent one
- [x] **A3-EXT-4** `mapping/map_source.py:243` [eufy] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Room-outline offset is the exact NEGATION of the fork renderer's — overlays desync from the live backdrop whenever the outline origin differs from the map origin
- [x] **A5-POSE-6** `mapping/map_source.py:139` [both] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  `resolve_furnished_render` passes a stored placement transform through with no map-geometry stamp, so a re-mapped floor plan silently misaligns the art
- [x] **A5-POSE-7** `mapping/map_source.py:582` [eufy] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  An off-grid robot pixel is clamped onto the map edge and reported as a confident anchor — "off the map" is indistinguishable from "at the edge"
- [x] **A2-GEO-4** `mapping/map_source_runtime.py:466` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  correspondences_from_mapdata's docstring claims clamped corners are skipped; _mapdata_projector silently clamps with no detection, leaving the affine round-trip check as the only guard
- [x] **A4-RB-7** `mapping/map_source_runtime.py:260` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  _walk and _structure_tree can only descend objects exposing __dict__, so a slotted/C-extension node is both an undiscoverable dead end and an uninformative diagnostic
- [x] **A4-RB-8** `mapping/map_source_runtime.py:534` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  correspondences_from_mapdata's docstring claims clamped corners are skipped; the code feeds them into the least-squares fit, turning a rare edge case into an unexplained zone refusal
- [x] **A1-SERVIC-6** `mapping/mapping_services.py:406` [Both.] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  `backdrop_source` is the only enum-shaped field in the file left as free-form `cv.string`, is absent from services.yaml, and a typo produces a custom layout that can never hold segments and cannot be repaired
- [x] **A3-IMAGE--11** `mapping/mapping_services.py:1089` [Both; any adapter that tunes min_area_pixels away from 1200.] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  min_area_pixels silently overrides the adapter's configured tuning because absent is coerced to 1200 before the is-not-None check
- [x] **A3-IMAGE--9** `mapping/mapping_services.py:945` [Both.] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Layout existence is validated before the executor write and re-checked afterwards only by a silent isinstance guard, so a concurrent layout delete orphans the upload
- [x] **A5-FURNIS-3** `mapping/mapping_services.py:2076` [both] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  _handle_set_room_viewport is the only furnished writer with no clamp and a corner-valued default — zoom:0 and cx/cy:0.0 persist verbatim
- [x] **A5-FURNIS-5** `mapping/mapping_services.py:2130` [both — sharpest on Roborock, whose rendered image is trimmed to the occupied extent] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  hidden_regions are stored as normalized rects with no record of the frame they were authored against, so a re-map re-aims the masks onto different physical areas — and masks hide content by default
- [x] **A5-FURNIS-6** `mapping/mapping_services.py:1969` [both] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Clearing a home-scope art placement setdefaults an empty home_art dict, flipping the 'no furnished data' sentinel from None to a confident empty payload
- [x] **A7-ROBORO-1** `mapping/roborock_raw_map.py:158` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  A raster containing ZERO rooms is published as present:True — decode's own room_ids signal is computed and discarded
- [x] **A7-ROBORO-5** `mapping/roborock_raw_map.py:198` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Two functions in this module read the same `flip_y` key with OPPOSITE defaults, so a decoded dict missing the key renders flipped but drift-checks unflipped
- [x] **A7-ROBORO-6** `mapping/roborock_raw_map.py:284` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  geometry_drift reports max_center_delta: 0.0 when there are no common rooms — an optimistic accumulator that survives an empty loop
- [x] **A7-ROBORO-7** `mapping/roborock_raw_map.py:96` [roborock] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  The IMAGE-block dimension guard is `header_len >= 16`, but the four dims occupy the LAST 16 bytes of a header whose first 8 are the fixed type/len fields — anything under 24 reads dims out of the header's own metadata
- [x] **A6-TRK-6** `mapping/tracker.py:196` [both] -- **RP-030** (`05e75b3`, `466f8f3`, `83bfa91`, 2026-08-03)  
  Dock-drift append rewrites the entire log file on every reading, and a failed write silently forfeits that drift event via the already-committed _last_dock_pos
- [x] **EP-1** `button.py:200` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  The maintenance reset button discards a documented failure result and reports success
- [x] **A6-VAC-2** `dock/manager.py:93` [eufy] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Dock action returns performed=True / "Dock action sent." when the resolved button entity exists only in the registry (disabled or not loaded) — a silent no-op reported as success
- [x] **A5-SVC-3** `learning/services.py:735` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  retry_missed_rooms permanently destroys the map's room-enable selection and persists it to disk even when the start was BLOCKED and nothing ran
- [x] **A5-SVC-4** `learning/services.py:486` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  record_estimate_accuracy's schema requires no keys at all; an entry missing map_id/slug writes a permanently unreadable durable record and returns a confident success payload
- [x] **A4-PP-RP-3** `profiles/manager.py:1283` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  start_run_profile mutates and persists every room's selection and settings BEFORE the start is allowed, and never reverts when the start refuses
- [x] **A4-PP-RP-7** `profiles/manager.py:1258` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Applying a profile whose rooms no longer exist silently deselects and persists every room on the map, and reports the failure as "profile_not_found"
- [x] **A1-WIRE-2** `services/_common.py:57` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  resolved_call_data's docstring claims an unresolvable map_id always raises; discover_rooms is the one consumer that silently falls through and persists the payload under an empty-string map key
- [x] **A2-JOB-9** `services/_common.py:58` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  resolved_call_data's docstring claims a "clear error" on unresolvable map_id; the actual failure is a bare TypeError, and no service in either module raises ServiceValidationError
- [x] **A4-SETUP-4** `services/adapter_config.py:57` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_adapter_config / delete_adapter_config declare no supports_response and return None on every rejection path — a rejected write is indistinguishable from a successful one
- [x] **A4-SETUP-14** `services/adapter_config.py:198` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_vacuum_capabilities uses the raising get_manager() while its siblings in the same module use the tolerant .get() form, and it writes storage on a read-shaped service
- [x] **A6-DIAG-1** `services/dock.py:83` [eufy] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Dock actions return performed:true / "Dock action sent." when the resolved button entity has no state — the press is silently dropped by HA
- [x] **A6-DIAG-7** `services/dock.py:59` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_dock_action_status raises a raw TypeError when map_id cannot be auto-resolved — the only unwrapped handler in the three modules, and _common's docstring claims the opposite
- [x] **A6-DIAG-4** `services/errors.py:71` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  acknowledge_error returns the same {"acknowledged": true} whether the latch was deleted, merely MARKED, or was never there — and both docstrings still describe the pre-audit delete semantics
- [x] **A1-WIRE-1** `services/job_control.py:156` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_manager() is re-fetched after a device-length await, so a config-entry reload mid-dispatch loses the just-started job record (or raises a bare KeyError)
- [x] **A2-JOB-1** `services/job_control.py:322` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  start_selected_rooms discards every refusal — no supports_response, no exception, DEBUG log only; docs promise a response it cannot return
- [x] **A2-JOB-3** `services/job_control.py:238` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  clear_active_job destroys a running job's record unconditionally and returns nothing — no status precondition, no supports_response, immediate persist
- [x] **A2-JOB-7** `services/job_control.py:156` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  async_save() sits after the try/except in every job_control handler — a raise after dispatch leaves a running job in memory only
- [x] **A6-DIAG-2** `services/maintenance.py:94` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  set_maintenance_interval accepts ANY component string, persists it, and returns saved:true — its sibling reset_maintenance raises ServiceValidationError for exactly that input
- [x] **A6-DIAG-3** `services/maintenance.py:46` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  set_maintenance_interval bypasses the min/max its own docstring claims, and interval_hours: 0 silently turns off the consumable's alert
- [x] **A6-DIAG-9** `services/maintenance.py:95` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Mutate-then-save is not atomic in all three write services: a save failure surfaces an error while the change has already taken effect in memory
- [x] **A2-JOB-5** `services/queue.py:40` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Break schemas do not enforce the break_type→parameter dependency, and the two sibling schemas disagree on which break types exist
- [x] **A2-JOB-6** `services/queue.py:51` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_queue_steps returns `breaks` in a shape set_queue_breaks rejects — the documented read-modify-write round trip fails validation
- [x] **A3-ROOMS-5** `services/room_profiles.py:168` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  apply_room_profile silently no-ops on unknown room ids and returns a success-shaped response with no way to tell
- [x] **A3-ROOMS-7** `services/room_profiles.py:52` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_user_room_profile silently overwrites an existing custom profile and reports saved: true, while its sibling rename_room_profile refuses the identical collision
- [x] **A3-ROOMS-11** `services/room_profiles.py:122` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Error-surfacing is inconsistent across the area: rooms.py wraps 4 of 5 handlers, room_profiles.py wraps 0 of 8, access_graph.py wraps 0 of 2
- [x] **A3-ROOMS-10** `services/rooms.py:251` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_managed_rooms is the most destructive service in the area and the only mutation registered without supports_response
- [x] **A5-RUNPROF-1** `services/run_profiles.py:97` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  save_run_profile never inspects the manager's `saved` flag — a save that stored nothing returns a success-shaped response and raises nothing
- [x] **A5-RUNPROF-2** `services/run_profiles.py:114` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  apply_run_profile persists a full room-selection wipe and reports no error when the profile's rooms no longer exist on the map
- [x] **A5-RUNPROF-3** `services/run_profiles.py:146` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  overwrite_run_profile exposes the step-sequence destruction with no warning, no confirmation, no response signal — and commits it with async_save
- [x] **A5-RUNPROF-5** `services/run_profiles.py:71` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  rename_run_profile accepts a blank name and silently relabels the profile 'Untitled', returning renamed:True — the sibling save rejects the same input
- [x] **A5-RUNPROF-6** `services/run_profiles.py:152` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  overwrite_run_profile with no rooms enabled returns overwritten:False as a success — the raise gate matches one literal reason, not the failure flag
- [x] **A5-RUNPROF-7** `services/run_profiles.py:90` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  get_saved_run_profiles and get_dashboard_snapshot lack the package's try/except wrap; an unresolvable map_id surfaces as a raw TypeError, contradicting resolved_call_data's docstring
- [x] **A4-SETUP-7** `services/setup.py:215` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  Three setup handlers subscript data["map_id"] after resolved_call_data and raise a bare KeyError — the helper's docstring claims the manager raises a clear error instead
- [x] **A4-SETUP-8** `services/setup.py:222` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_save_rooms stamps the setup step complete unconditionally, unlike both of its sibling step-advancing handlers
- [x] **A4-SETUP-10** `services/setup.py:100` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  floor_types accepts any string; an unrecognised value is silently clamped to "hardwood" at read time, so a mistyped carpet becomes a wet-mopped carpet
- [x] **A4-SETUP-11** `services/setup.py:229` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_delete_map auto-resolves an omitted map_id to whatever map happens to be active at call time
- [x] **A4-SETUP-12** `services/setup.py:184` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_get_map_rooms returns a success-shaped empty room list when the runtime manager is missing — the caller cannot tell "integration not loaded" from "map has no rooms"
- [x] **A4-SETUP-13** `services/setup.py:336` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  setup_set_map_camera stores an unvalidated entity_id and reports success even when the entity does not exist
- [x] **A1-CRUD-7** `themes/manager.py:370` [both] -- **RP-031** (`6a8c965`, `87220b4`, `4f5fa7a`, `d677cc9`, 2026-08-02)  
  set_theme_tags silently discards tags past 16 or longer than 32 chars and still returns ok:True
- [x] **A5-SVC-9** `learning/services.py:72` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  Schemas mark map_id Required on three services the documentation marks optional, so an automation written from the docs fails validation
- [x] **A1-SERVIC-4** `mapping/mapping_services.py:443` [Both — the geometry layer is brand-independent; only the final dispatch conversion differs.] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  `_saved_zone_coord`'s docstring claims it "mirrors the hidden-regions sanitizer" but omits that sanitizer's degenerate-drop — a zone that can be saved but can NEVER be cleaned, with no service able to repair its geometry
- [x] **A1-SERVIC-7** `mapping/mapping_services.py:115` [Both (no runtime effect).] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  19 schemas (lines 115-301) are dead — defined once, referenced nowhere — and two of them are near-duplicate twins of LIVE schemas whose defaults would be rejected by the live validators
- [x] **A3-IMAGE--10** `mapping/mapping_services.py:964` [Both.] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  Four of the five services in this block have no services.yaml description, including the destructive delete_map_image
- [x] **A4-CUSTOM-7** `mapping/mapping_services.py:1650` [Both.] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  set_custom_segments' user-facing description is two features stale — it claims map-level scope and an uploaded-backdrop requirement that the layout + live-dims paths superseded
- [x] **A5-FACADE-5** `services.yaml:1179` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  services.yaml declares a REQUIRED 'carpet' field on save_user_room_profile and overwrite_room_profile that the voluptuous schema rejects
- [x] **A1-WIRE-3** `services/dock.py:174` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  Sixteen registered services documented as public API have no services.yaml descriptor, including set_dock_event_count whose five dock siblings all have one
- [x] **A1-WIRE-4** `services/room_profiles.py:203` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  get_room_profiles is the only one of the 79 registrations with no schema, so caller-supplied scoping arguments are accepted and silently ignored
- [x] **A3-ROOMS-4** `services/room_profiles.py:43` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  services.yaml advertises required fields that the voluptuous schemas reject — three services fail outright when the user fills the form HA renders
- [x] **A3-ROOMS-3** `services/rooms.py:79` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  save_managed_rooms stamps every room's floor type as user-confirmed while its schema makes it structurally impossible to supply one
- [x] **A4-SETUP-15** `services/setup.py:353` [both] -- **RP-032** (`4fe48ab`, `8b90c28`, `bf75b22`, `2c461dd`, `04adb30`, `78c8bd0`, `64f566d`, `c9c4cba`, `a293ad8`, `1d52fa6`, `64e718b`, 2026-08-02)  
  None of the 10 setup_* services and 5 of the 6 adapter-config services have services.yaml or translation entries
- [x] **A6-VAC-3** `core/manager.py:1126` [eufy] -- **RP-033** (`06ffc73`, 2026-08-02)  
  refresh_vacuum_capabilities does NOT reproduce startup's detect_capabilities inputs — it silently drops the dock-button entity candidates, contradicting the comment above it
- [x] **A3-COMMON-2** `listeners/_common.py:198` [future_brand_only] -- **RP-033** (`06ffc73`, 2026-08-02)  
  completion_secondary_satisfied() returns True from a config FLAG without verifying the entity it delegates to exists; the "Invariant" asserted in the caller is never validated
- [x] **A4-POSE-4** `listeners/pose_sampler.py:242` [future_brand_only] -- **RP-033** (`06ffc73`, 2026-08-02)  
  A zero or negative interval_s survives adapter registration (warn-only) and then splits the sampler in two: register() drops it, _sample_vacuum_once does not
- [x] **DQ-DE-3** `queue/dispatch_engines.py:316` [future_brand_only] -- **RP-033** (`06ffc73`, 2026-08-02)  
  DreameSegmentEngine's documented 'direct envelope (no command)' is unreachable — an omitted command defaults to Eufy's room_clean
- [x] **DQ-DE-4** `queue/dispatch_engines.py:422` [future_brand_only] -- **RP-033** (`06ffc73`, 2026-08-02)  
  An omitted dispatch.template silently resolves to the Eufy engine with no warning, and the claimed registration-time rejection does not exist
- [x] **A4-SETUP-2** `services/adapter_config.py:67` [both] -- **RP-033** (`06ffc73`, 2026-08-02)  
  save_adapter_config accepts a two-key config and registers it OVER the live code adapter — every omitted block silently resolves to Eufy behaviour on a Roborock
- [x] **A4-SETUP-3** `services/adapter_config.py:108` [both] -- **RP-033** (`06ffc73`, 2026-08-02)  
  delete_adapter_config unregisters the CURRENTLY REGISTERED adapter — after startup that is the code adapter — leaving the vacuum with no adapter at all
- [x] **A4-SETUP-5** `services/adapter_config.py:86` [both] -- **RP-033** (`06ffc73`, 2026-08-02)  
  save_adapter_config persists to storage BEFORE registering, so a config the registry flags as invalid is written to disk anyway and reloaded at every restart
- [x] **A4-SETUP-9** `services/setup.py:131` [both] -- **RP-033** (`06ffc73`, 2026-08-02)  
  adapter `setup.steps` is never validated at registration despite two docstrings and the schema claiming it is; two declared step IDs have no completion writer and strand the wizard permanently
- [x] **A1-INIT-3** `core/manager.py:347` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  Startup re-seed of the bundled theme library resurrects themes the user deleted, and re-points default_theme_id
- [x] **A1-CRUD-1** `themes/manager.py:305` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  overwrite_theme WIPES the target theme's entire palette when the vacuum has no active theme — ok:True, persisted, no undo
- [x] **A1-CRUD-2** `themes/manager.py:303` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  overwrite_theme replaces the target with a copy of a DIFFERENT theme (the vacuum's active one), and silently repoints the vacuum at the target
- [x] **A1-CRUD-3** `themes/manager.py:386` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  delete_theme of a bundled/core theme is silently undone at the next HA restart — the seeder re-adds it
- [x] **A1-CRUD-4** `themes/manager.py:321` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  overwrite_theme can permanently replace a bundled theme's palette while preserving source:"core", so user content keeps claiming to be shipped
- [x] **A1-CRUD-5** `themes/manager.py:391` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  delete_theme nulls the active pointer but leaves the vacuum's dirty working draft orphaned; the next save writes a theme containing only the deltas
- [x] **A1-CRUD-6** `themes/manager.py:351` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  rename_theme writes into the raw stored entry with no isinstance-dict guard, unlike set_theme_tags — a corrupt entry raises TypeError out of the service
- [x] **A1-CRUD-8** `themes/manager.py:350` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  rename_theme accepts a blank/whitespace name and silently stores "Untitled"; no duplicate-name check on rename or save_theme_as_new
- [x] **A2-DRAFT-1** `themes/manager.py:391` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  delete_theme clears active_theme_id but leaves the deleted theme's working draft and draft_dirty in place — the orphan draft bleeds over the card's default look forever and survives restart
- [x] **A2-DRAFT-2** `themes/manager.py:417` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  set_active_theme destroys the working draft unconditionally with no confirmation, no undo and no same-id short-circuit — clicking the already-active preset tile silently wipes every unsaved edit
- [x] **A2-DRAFT-3** `themes/manager.py:411` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  set_active_theme's global-default branch is the only mutator that returns without firing _notify_updated, leaving the theme sensor's default_theme_id attribute stale
- [x] **A2-DRAFT-6** `themes/manager.py:654` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  _import_scoped strips matching keys out of the working draft but never recomputes draft_dirty, so the draft can be left empty with the dirty flag stuck True
- [x] **A2-DRAFT-7** `themes/manager.py:224` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  _minimal_theme_mutation_response cannot express 'there is now no active theme' — a None active_theme_id is dropped from the payload rather than sent as null
- [x] **A3-PORT-1** `themes/manager.py:544` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  import_theme performs no key validation; the card applies every imported key as a real CSS declaration on the card host, so one imported theme file can render the card permanently blank
- [x] **A3-PORT-2** `themes/manager.py:643` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  _import_scoped clears a floor namespace in all three buckets but only re-applies the buckets the payload happens to contain, silently destroying per-layer opacity settings while reporting success
- [x] **A3-PORT-3** `themes/manager.py:625` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  A scoped import rewrites the ACTIVE library entry in place with no core/provenance check, permanently corrupting a bundled preloaded theme that the seeder will never repair
- [x] **A3-PORT-4** `themes/manager.py:411` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  set_active_theme with vacuum_entity_id=None returns without firing _notify_updated — the only mutation in the module that skips the callback fan-out, leaving default_theme_id stale in HA state
- [x] **A3-PORT-5** `themes/manager.py:554` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  Import name de-duplication appends '(imported)' at most once, so repeated imports of the same theme produce multiple indistinguishable library entries
- [x] **A3-PORT-7** `themes/manager.py:42` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  _clean_theme_tags coerces non-string items with str(), reachable only through the unvalidated import payload, and silently drops rather than truncates over-long and over-count tags
- [x] **A3-PORT-8** `themes/manager.py:172` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  The _get_theme_library_entries docstring claims write-time normalization that does not exist — _normalize_theme_entry is called from two sites and both are read paths
- [x] **SN-6** `themes/manager.py:412` [both] -- **RP-034** (`c005ad6`, 2026-08-02)  
  Setting the GLOBAL default theme returns without notifying, so the theme sensor is stale indefinitely
- [x] **EP-6** `binary_sensor.py:86` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  _attr_suggested_object_id is not a Home Assistant attribute - four sites rely on a dead assignment
- [x] **A3-FLOW-2** `config_flow.py:103` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  Changing the vacuum in the options flow ADDS a second managed vacuum instead of replacing the first — the old pick is never reconciled away
- [x] **A3-FLOW-3** `config_flow.py:98` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  The options flow rebuilds the options dict from the stale form snapshot, so a submit can resurrect a vacuum that was deleted while the dialog was open
- [x] **A6-VAC-5** `core/manager.py:1084` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  get_managed_vacuums reads data["capabilities"] raw and reports supports_* as None when no snapshot exists, unlike its sibling get_vacuum_capabilities which detects on demand
- [x] **A6-PRE-3** `jobs/job_monitor.py:58` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  PreflightResult declares `available` with a documented contract the producer never honours, and omits two keys the producer writes
- [x] **A6-PRE-4** `jobs/job_monitor.py:32` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  BlockedRoomEntry.source documents "access_graph" for graph-propagated blocks; the producer writes "access_dependency", and the wrong literal is hand-copied into an exposed sensor attribute's type
- [x] **A5-METRICS-3** `listeners/job_metrics.py:44` [future_brand_only] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  `_duration_state_to_seconds` silently treats any unrecognized unit as seconds, and re-resolves the unit per event with no mid-run consistency check
- [x] **A5-METRICS-4** `listeners/job_metrics.py:117` [future_brand_only] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  Station-water subscription guesses an entity key that exists nowhere, ignores the adapter's `supports_station_water` declaration, and swallows every lookup failure silently
- [x] **A5-METRICS-5** `listeners/job_metrics.py:165` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  watch_map's type annotation and the `int` value_type branch are both stale — the annotation declares 3-tuples while all three writers store 4-tuples, and no entry ever uses `int`
- [x] **EP-3** `number.py:22` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  Interval bounds are framework constants, and the ceiling is BELOW a shipped component's declared max
- [x] **INF-1** `panels.py:29` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  panels.py claims to be the single registration seam; a fourth site hand-copies all three of its constants
- [x] **DQ-PH-5** `queue/queue_engine.py:62` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  QueueEntry / PayloadItem / ActiveJobSnapshot describe a shape the module has never emitted, and disagree with build_active_job_state on the fields it does write
- [x] **SN-1** `sensor/__init__.py:98` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  A managed vacuum with no imported map gets ZERO per-vacuum sensors, and importing a map never creates them
- [x] **SN-8** `sensor/__init__.py:91` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  active_job_entities and its explanatory comment are dead
- [x] **SN-10b** `sensor/theme.py:75` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  A raw stored null theme name renders as the string 'None' — valid, but not reachable in normal operation
- [x] **INF-2** `timestamp_utils.py:8` [both] -- **RP-035** (`1c2d8b1`, `45aa65f`, 2026-08-03)  
  _LOCAL_TZ is a FIXED offset captured at import, so naive legacy timestamps get the wrong offset half the year
- [x] **A1-EST-1** `learning/estimator.py:167` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Confidence breakpoint table has a dead band at 0.79–0.80; the best-learned rooms fall through it and render as LOW / red "error"
- [x] **A1-EST-2** `learning/estimator.py:844` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  App-started (external) runs contribute battery=0.0 samples; the estimator consumes a learned 0.0 as a real number and derives battery_warning / mid_job_recharge_risk = False from it
- [x] **A1-EST-3** `learning/estimator.py:476` [roborock] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  _find_room_match Pass 1 can NEVER match a Roborock room: it compares the raw "" intensity against the rebuilder's normalized "standard", so every Roborock room takes a permanent -0.15 intensity-mismatch penalty
- [x] **A1-EST-4** `learning/estimator.py:843` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Estimate consumes avg_minutes with no outlier rejection and no band check, and a single poisoned sample scores MEDIUM confidence because stddev of one sample is 0 by construction
- [x] **A1-EST-5** `learning/estimator.py:148` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  HIGH confidence is mathematically unreachable for any real room, yet _learning_velocity reports runs_to_high=0 at 10 samples and runs_to_medium=0 always
- [x] **A1-EST-6** `learning/estimator.py:484` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  _find_room_match relaxed passes return the lexicographically-first bucket and ignore sample_count entirely — a 1-sample bucket beats a 30-sample one
- [x] **A2-ACC-2** `learning/estimator.py:1122` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  reanchor_timeline ignores its own reanchor_at parameter — every ETA is anchored to job start plus the sum of room durations, so all wall-clock dead time is invisible and "Done at" times slide into the past
- [x] **A2-ACC-3** `learning/estimator.py:1178` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Reanchoring drops inter-room transit from remaining rooms while keeping it in overhead — remaining ETAs jump earlier then later (oscillation) and the job ETA inflates by one transit leg per completed room on a run that is exactly on estimate
- [x] **A2-ACC-4** `learning/estimator.py:1189` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  A skipped room can never be resolved: it holds "current" for the rest of the run, adds its full estimate to every later room's ETA, and permanently blocks all_completed
- [x] **A2-ACC-5** `learning/estimator.py:1130` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  Completed-room slug matching is keyed on the literal string "none" — the documented slug fallback is dead, and a room with a null slug is marked complete before it is cleaned
- [x] **A2-ACC-6** `learning/estimator.py:637` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  The "exact vs allocated" quality flag is recorded and never used — job-average actuals are blended into the same drift mean, permanently capping affected rooms below HIGH confidence while the card promises they will get there
- [x] **A2-ACC-7** `learning/estimator.py:592` [both] -- **RP-036** (`97689a6`, `ebcea69`, `715f841`, 2026-08-03)  
  A non-dict `rooms` block crashes both accuracy readers — including estimate() on the event loop — while the sibling reader in the same subsystem explicitly tolerates it
- [x] **A3-SNAP-2** `core/manager.py:3914` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  get_dashboard_snapshot composes get_job_progress_snapshot TWICE, so job_progress and job_control in the same payload can describe different rooms — and every side effect in the progress composer fires twice per card poll
- [x] **A1-EST-9** `learning/estimator.py:766` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  estimate() runs ensure_dirs (four mkdir syscalls) three times per call on the event loop, even on full cache hits
- [x] **A3-IO-4** `learning/history_store.py:148` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  ensure_dirs runs inside every path getter, so the caches that exist to keep the loop-bound estimate off disk still issue ~32 blocking filesystem syscalls per dashboard snapshot
- [x] **A4-STATE-7** `learning/history_store.py:232` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  load_live_snapshot performs 4 mkdir syscalls plus an open()/read() on the Home Assistant event loop at every cold finalize
- [x] **A2-GEO-2** `mapping/map_source.py:381` [eufy] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  zone_membership scans the entire room_outline raster with a per-cell normalize_rendered before the bbox reject, synchronously on the event loop — measured ~0.10 s per zone, ~1.0 s per dashboard read
- [x] **A7-ROBORO-2** `mapping/roborock_raw_map.py:200` [roborock] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  raster_room_bboxes runs an O(width*height) pure-Python per-pixel loop directly on the Home Assistant event loop
- [x] **A6-TRK-7** `mapping/tracker.py:286` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  start_job/end_job are dispatched to an executor thread on the strength of a comment describing disk I/O that start_job does not perform
- [x] **DR-ONB-5** `sensor/onboarding.py:55` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  The sensor recomputes the entire onboarding summary twice per update
- [x] **A2-DRAFT-5** `themes/services.py:230` [both] -- **RP-037** (`a00ee36`, `7b53ed4`, `4d7912d`, 2026-08-03)  
  Every update_working_draft triggers an immediate full Store.async_save of the entire integration data dict, and the card fires it on `input` — once per keystroke in text and number token fields
- [x] **DR-DOCK-1** `dock/manager.py:383` [eufy] -- **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  The dock-event timestamp is written BEFORE the debounce, so a debounced event still corrupts last_*
- [x] **DR-DOCK-2** `dock/manager.py:383` [both] -- **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  record_dock_event validates nothing; its sibling set_dock_event_count validates the same vocabulary
- [x] **DR-DOCK-3** `dock/manager.py:446` [both] -- **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  A manual counter reset leaves the debounce marker, suppressing the next genuine event
- [x] **A1-REG-1** `listeners/dock_events.py:74` [eufy] -- **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  dock_events treats any arrival at a trigger value as a NEW dock cycle — a startup, an entity re-add, or an `unavailable` blip mid-cycle re-records the event and increments the durable counter
- [x] **A1-REG-4** `listeners/dock_events.py:91` [future_brand_only] -- **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  dock_events.register() never reads the adapter's `dock_events.enabled` flag — a brand that declares enabled:False but inherits triggers still records dock events
- [x] **A6-GUARD-3** `listeners/dock_events.py:72` [eufy] -- **RP-038** (`1c8da5a`, `b474581`, 2026-08-02)  
  dock_events treats a first-sighting (old_state=None) and an unavailable-recovery as a fresh dock cycle, inflating maintenance counters and resetting last_dry_start
- [x] **DR-DIAG-5** `diagnostics.py:53` [both] -- **RP-039** (`4a0afb9`, `1981640`, `56fb7be`, `498a285`, `4b07de2`, 2026-08-03)  
  Dead `_SENTINELS` alias sits in the one file whose header explains why that set must not fork
- [x] **A1-ID-5** `adapters/eufy/discovery.py:47` [eufy] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  adapters/eufy/discovery.py is a dead, divergent second implementation of get_active_map_id / discover_rooms_for_vacuum with hand-copied sentinel and key literals
- [x] **DR-BAT-2** `battery/manager.py:601` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  An out-of-order sample is correctly skipped but still rewinds the last-sample anchor
- [x] **DR-BAT-3** `battery/manager.py:653` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  After a stale-session discard, charging stays untracked until the next charge cycle
- [x] **INF-7** `const.py:27` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Four constants are defined and never read - including three service names for services that do not exist
- [x] **A2-CB-3** `core/manager.py:579` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The manager's four own callback registries append without a duplicate check while the theme registry they delegate to dedupes, and unregister removes only one copy
- [x] **A2-CB-4** `core/manager.py:1035` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  remove_vacuum_record wipes every bucket the five callback registries exist to mirror and fires none of them, dropping the notification obligation its narrower sibling remove_map documents
- [x] **A4-START-3** `core/manager.py:2943` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_start_status can never surface a non-blocking lifecycle warning message — preflight's "ready" text shadows it, making dock-drying starts show warning=True with the message "Ready to start cleaning."
- [x] **DQ-ACT-7** `dispatch/manager.py:421` [future_brand_only] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The OFF-fallback lowercases the select's options for the membership test but then sends the lowercased string as the option value
- [x] **DR-BAT-1** `docs/dev/12-battery-system.md:88` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Doc §3 states the MAX_DELTA_PCT boundary one step off from the code and from its own §5.2
- [x] **DR-BAT-4** `docs/dev/12-battery-system.md:338` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Doc omits two live conditions present in the code
- [x] **DR-ONB-6** `docs/dev/18-onboarding-manager.md:228` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Doc cites the start gate at core/manager.py:2776; it is at 2805
- [x] **A3-IO-5** `learning/history_store.py:368` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_completed_job_path interpolates an unvalidated job_id into a filesystem path, giving exclude/restore_learning_job an arbitrary *.json overwrite primitive — the exact hole the sibling module already hardened
- [x] **A3-IO-7** `learning/history_store.py:196` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  write_json is rename-atomic but not durable — no fsync before os.replace, so a power loss can leave a zero-length learned file that read_json then reports as "no data"
- [x] **A3-IO-8** `learning/history_store.py:599` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  append_job_csv_row / append_room_csv_rows are dead, and each CSV header is a hand-copied literal duplicated between the dead append writer and the live rebuild writer
- [x] **A3-COMMON-5** `listeners/_common.py:52` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_adapter_value() is a second, independent implementation of the identical lookup already shipped in adapters/registry.py
- [x] **A4-POSE-6** `listeners/pose_sampler.py:10` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Module docstring still declares the sampler 'Capture-only / inert — nothing consumes pose_samples yet', but the W5c consumption wire has landed
- [x] **A3-EXT-5** `mapping/map_source.py:808` [future_brand_only] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Two room extractors disagree on the input coordinate frame and the dead one is the one under test
- [x] **DR-MAP-1** `maps/map_manager.py:62` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_map_bucket returns a DETACHED dict on a miss and live storage on a hit
- [x] **DR-MAP-2** `maps/map_manager.py:95` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_vacuum_maps_summary mixes a live room_count with CACHED enabled/disabled counts
- [x] **A1-ID-6** `models/models.py:162` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  RoomRecord documents grants_access_to as 'list[str] — room slugs' but every producer and consumer stores integer room ids
- [x] **INF-3** `models/models.py:257` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  VacuumCapabilities is a never-constructed dataclass whose field names do not exist in the real capability payload
- [x] **DR-ONB-4** `onboarding/manager.py:66` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The five-key default record is hand-duplicated between _get_map_onboarding and reset_onboarding
- [x] **A6-PP-EST-H2O-2** `planning/run_plan.py:237` [future_brand_only] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  A declared water_rates table REPLACES the core table wholesale, so an adapter that omits "off" bills 4.0 ml/min for water-off mop rooms — contradicting the comment that asserts the invariant
- [x] **A6-PP-EST-GUESS-1** `planning/run_plan.py:378` [eufy] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  estimate_job_water_usage drops the timeline's source/sample_count provenance, so default-guess room timings are presented as a measured "Job will use N ml"
- [x] **A6-PP-EST-CLAMP-1** `planning/run_plan.py:476` [eufy] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Tank-remaining ml is unclamped while its own percent is clamped to [0,100], and robot_internal_tank_ml is reported but never used in any calculation
- [x] **DQ-PAY-7** `queue/queue_engine.py:294` [future_brand_only] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  clean_passes_field: null omits passes in two engines but produces a None dict key in build_room_clean_payload
- [x] **INF-6** `repairs.py:1` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The repair flow is unreachable - nothing ever raises an issue - and the doc asserts the opposite
- [x] **A3-CRUD-7** `rooms/room_crud.py:318` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  get_managed_rooms returns the live stored rule dicts and metadata sub-objects by reference despite copying the outer containers
- [x] **DR-ONB-3** `sensor/onboarding.py:62` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  The 'empty means complete' guard exists in setup/status.py and was never mirrored onto the onboarding summary — forgotten override sibling
- [x] **DR-SETUP-2** `setup/drift.py:117` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  auto_refresh_on still uses the bare or-coercion that code-flag CS-2 fixed for its three siblings
- [x] **DR-SETUP-3** `setup/drift.py:336` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Two unguarded int(key) coercions on drift-history keys, in a module that guards every other one
- [x] **DR-SETUP-4** `setup/protection.py:44` [both] -- **RP-040** (`7714931`, `d37e501`, `d86e18e`, `59cdf66`, `f3387e3`, `cc9baba`, `0e6b1e0`, `faf2e89`, `aa413d7`, `4405267`, `ecb47ef`, `d242c51`, `f7eae2d`, `0db5e11`, `c2bff98`, `bea97f9`, `21dce08`, `74a6ac6`, `93b83be`, `41aedd6`, `9c42f03`, 2026-08-02)  
  Protection evaluation calls .get() on map buckets and room records without isinstance guards
- [x] **DOCK-1** `learning/job_finalizer.py:939` [eufy (Roborock declares no code tables, so it degrades to 'trust the run')] -- **RP-046** (`5b21a1a`, `14a4f43`, 2026-08-04)  
  total_error_seconds is subtracted from cleaning_time_seconds with no notion of WHOSE fault it was, so a station fault raised while the robot cleaned normally is charged against the robot's cleaning time

---

## TIER 3 -- carried over from before audit #7, never closed

- [ ] **`active_boundaries` round-trip (SEG-1)** -- Deferred deliberately: it changes a persisted record field and warrants separate scrutiny.
- [ ] **Pose sampler predicates** -- Two call sites were deliberately not re-pointed at the shared in-flight helper, because doing so would silently add `paused` to what gets sampled. Wants its own change.
- [ ] **Roborock room migration** -- Room *creation* now takes brand-correct defaults. Rooms created before that still carry the old values. Stored user data, so repairing it is a product decision.
- [ ] **Three card strings untranslated** -- `common.service_failed`, `learning.room_skipped`, `learning.run_incomplete_toast` are English-only across the 17 non-English locales.
- [ ] **Card: the two failure-renders-as-success paths (FE-ERR-1 / MZ-2)** -- Blocked on a backend `supports_response` change.
- [ ] **Card: the qualification gap (CC-5)** -- Surface provenance, truncation and absent data honestly rather than as confident values.
- [ ] **Card: surface captured run errors (`run_errors`)** -- The backend now carries app-started-run error evidence end to end. Nothing displays it.
- [ ] **OpenDyslexic font support** -- Contract settled — English-only gate, one token override, glyph coverage proven per locale before offering another. No code written.
- [ ] **Roborock edge-mopping: the adapter contradicts itself (was: control removal)** -- RE-SCOPED 2026-08-01 — the earlier framing ('the card renders a control the adapter declares unsupported, so gate or remove it') is BACKWARDS and must not be actioned as written. Two facts, both in the Roborock adapter: (1) supports_edge_mopping is a HARDCODED brand-wide False at adapter.py:177 and :580 — flat literals, NO model gating, unlike the Eufy adapter which asks `model_family in {...}` for its per-model capabilities. That is the brand-vs-model conflation pattern: a per-model fact frozen at brand level. (2) the adapter's OWN vocabulary already disagrees — vocabulary.py:148, the `vacuum_mop_deep` room profile, ships `edge_mopping: True`. So the adapter requests a capability it declares absent. Chris confirms his S6 cannot edge mop, but correctly notes that is a MODEL fact, not a brand fact — other Roborock models plausibly can. CONSEQUENCE: gating the card on supports_edge_mopping would hide the control on every Roborock including models that can do it, and would leave vacuum_mop_deep requesting an absent capability. RECOMMENDED (consistent with Q12's 'unsupported and unsurfaced until verified... add an independently validated declaration' precedent): leave the declaration False, FIX vacuum_mop_deep to stop requesting edge_mopping (the near-one-liner), and treat model-gating as a SEPARATE change requiring verified per-model device facts. Do not invent hardware capabilities. Deferred by Chris 2026-08-01: patch later, it is near a one-liner.

---

## Suggested order for a cheap execution window

Ordered by (verified) x (blast radius) x (cost), not by severity label.

1. **C5** -- 2 lines, verified, closes a gap I introduced. Cheapest real win.
2. **C7** -- verified CRITICAL. Slug uniqueness at discovery: wrong physical room AND silent
   destruction of the second room's stored settings. Fix the docstring's false claim too.
3. **C1** -- verified CRITICAL seam. The other wrong-physical-room path.
4. **C10** -- small, and the third route to the same wrong-room outcome (a failed refresh is
   indistinguishable from a successful one, so stale ids reach the wire).
5. **C9** -- destructive writes. An empty selection wiping a map's rooms is one bad call away.
6. **C3** -- try/finally so one transient failure stops bricking every future run.
7. **C8** -- decide reconciliation's trigger. The machinery is built and nothing calls it.
   This is the ROOT of C1/C7 rather than another instance of them.
8. **C2** -- cancel correctness. Needs care around the await boundaries.
9. **C6** -- user-visible on every mop room, but changes resolution precedence. Test hard.
10. **C4** -- per-phase attribution. Touches the shape of learning data.
11. Tier 2 HIGHs, then MEDIUMs. LOWs only when the file is already open for another reason.

**Hardware gate: 5 of 60 landed packets validated on a real vacuum** (RP-013a, RP-013b, RP-013d, RP-013e, RP-013f). The remaining 55 are green in CI only -- treat an unvalidated packet as unshipped.

## Campaign cost, for calibration

| Audit | Tokens | Wall |
|---|---|---|
| #7 dispatch+queue | 1.58M | 23 min |
| #8 profiles+planning | 1.95M (incl. a re-verify my own harness bug forced) | 40 min |
| #9 jobs | 1.50M | 23 min |
| #10 rooms | 1.07M | 21 min |

Cost tracks the 8-agent shape far more than subsystem size -- #10 covered 2,531 LOC for 1.07M
while #7 covered 1,515 LOC for 1.58M. Scope future audits by agent count, not by LOC.

## ADJUDICATED -- judged not-a-fix, with reasoning. NOT open, NOT forgotten.

A finding here was examined and deliberately not fixed. The reasoning is kept in
full so audit #2 can overturn it on evidence rather than rediscover it from
scratch. Audit findings are adjudicated in `.claude/notes/_adjudicated_findings.json`
(an overlay -- the audit JSON itself is frozen evidence and is never edited);
direct-read rows carry `wontfix` inline.

- **A2-POLYGO-5** (#18 mapping services) `mapping/mapping_services.py:769`  
  Stale `image_segment_adjustments` survive a CV re-analysis and are re-applied by segment_id to whatever polygon now carries that id - moving a room the user never edited  
  -> OVERSTATED (2026-08-04) -- OVERSTATED — the premise does not hold for any reachable trigger, and the proposed cure would have caused the harm it was guarding against. Both findings assume a re-analysis can reassign segment_N to a DIFFERENT polygon, so a stored nudge would move a room the user never edited. EMPIRICAL DISPROOF (Chris, 2026-08-04): he cleared the adjustments and forced re-analysis THIRTY times — everything stayed stable. Ids moved only when he loaded NEW images. That is the same determinism already established in the #18:A3-IMAGE--1 adjudication (no RNG, no set-iteration in the path; the id rides with the admitted blob), now confirmed by direct observation rather than by reading the code. And a new image is not this defect: the user has just replaced the map, the rooms genuinely changed, and re-nudging is the expected outcome — the same reasoning that retired A3-IMAGE--1. WHY THE FIX WAS WORSE THAN THE BUG: the specced token was image_segments['analyzed_at'], a wall-clock stamp minted fresh on EVERY successful analysis (mapping_services.py:1165) with no content fingerprint anywhere in the module. Since a re-analysis yields identical ids and a NEW timestamp, the gate would have suppressed every valid adjustment on every re-analysis — and the card force-re-analyses on each CV-variant upload (src/bindings/map.js:1104), so a user who dragged an edge and then uploaded a variant would silently lose the nudge. Precisely the 'destroys hand-made work at exactly the wrong moment' failure A3-IMAGE--1's fix was rejected for. A stamp keyed on a CONTENT fingerprint rather than a timestamp would be sound, but with the trigger disproven there is nothing left for it to protect. SCOPING CLAIM ALSO WRONG. The spec carried a 'secondary leak' where leftover CV adjustments apply to CUSTOM segments. The two systems are separate by construction — CV mints segment_N (adapters/eufy/segmentor.py:1289), custom mints custom_N (mapping_services.py:1685), into separate stores resolved by _resolve_active_scope. They cannot collide unless a hand-written service call supplies a colliding id, which is a deliberate affordance (caller-supplied ids let segment_room_links survive an edit), not a defect. Chris: the custom polygon system is completely separate from CV. The spec's 'optional, recommended' half — making adjust_map_segment scope-resolved so it works in custom mode — is therefore REJECTED outright: adjust is a CV nudge tool, and the custom system has its own editing path (set_custom_segments replaces polygons wholesale). ONE RESIDUAL, tracked separately and NOT part of these findings: _handle_get_map_segments applies image_segment_adjustments to scope['segments_store'] with no mode check (mapping_services.py:1210), so in custom mode it consults a CV-only store. Inert today because the namespaces differ; it is a latent aliasing seam and a one-line guard, not the defect filed here.

- **A3-IMAGE--1** (#18 mapping services) `mapping/mapping_services.py:1174`  
  Re-analysis rebinds the user's room links and manual segment adjustments onto positionally-reassigned segment ids  
  -> OVERSTATED (2026-08-03) -- The mechanism as written does not hold, and the proposed cure is worse than the disease. (1) Ids are NOT positionally reassigned. adapters/eufy/segmentor.py mints segment_id when a blob is ADMITTED (:1289 kept regions, :1474 count-deficit recoveries) and the id rides with that blob; the sorts at :1414 and :1485 reorder the LIST and renumber nothing. (2) The pipeline is deterministic -- no RNG and no set-iteration anywhere in the path -- so the same image with the same tuning yields byte-identical ids. A plain re-analysis therefore cannot reassign anything, which is what the finding's 'any re-analysis in which blob ordering shifts' claims. Ids can only shift when the admitted blob SET changes: tuning altered (min_area_pixels / expected_room_count / max_segments, via the dedup at :1416-1432, the recovery branch at :1444-1483, or the truncate at :1487), or a genuinely different map image. NEITHER TRIGGER IS REACHABLE FROM THE UI. The card has exactly two analyze call sites (src/bindings/map.js:1104 after an upload, :1204 for an explicit re-analyze) and both pass ONLY {force_reanalyze: true} -- no tuning parameters at all -- so a card-driven re-analysis always uses the adapter's declared tuning and is therefore deterministic and id-stable. Altering tuning requires a hand-written service call from YAML or dev-tools, i.e. a deliberate expert action on a computer-vision pipeline; Chris's position, and it is the right one, is that a user who hand-tunes a CV segmenter has picked up a foot-gun of their own making and does not need the backend to defend them from it. The other trigger, a different image, arrives via upload -- where the user has just supplied a new map, so the rooms genuinely changed and relinking is the expected outcome rather than a defect. (3) 'Silently' is wrong. The link injects room_id onto the segment and the card renders that room's name on the polygon, so a stale link paints the wrong room name onto a map of the user's own home -- among the most visible failure modes this integration has, and Chris confirms this subsystem surfaces its failures in practice. The residual real case is narrow: a re-tune that swaps two similar adjacent rooms where the wrong label is not obvious. (4) A fix was written and REJECTED: retiring links whose segment geometry moved. Re-tuning IS the intended workflow -- the CV output is human-corrected at the end via card-side translations, edge nudges and vertex moves -- so the guard fires precisely when the user is iterating on tuning and deletes hand-made room links at exactly the wrong moment. The rooms did not move; only the segmentation did. Trading a visible mislabel for silent destruction of the user's own work is a bad trade. Its 'old centre inside new bbox' test was also a hidden threshold, scale-dependent (a large room's bbox swallows any centre; a closet's retires on noise) and asymmetric -- and in a CV subsystem an explicit tuned threshold, e.g. bbox IoU declared in mapping.segmenter_tuning beside the existing knobs, is the correct idiom rather than something to avoid. If this is ever revisited, the shape is a per-link IoU CONFIDENCE surfaced to the card, never a backend deletion.

- **A4-CUSTOM-6** (#18 mapping services) `mapping/mapping_services.py:1752`  
  adjust_map_segment persists a map-level record keyed by a segment id that CV re-analysis recycles — a nudge authored for one room silently re-attaches to whichever segment inherits that id  
  -> OVERSTATED (2026-08-04) -- OVERSTATED — the premise does not hold for any reachable trigger, and the proposed cure would have caused the harm it was guarding against. Both findings assume a re-analysis can reassign segment_N to a DIFFERENT polygon, so a stored nudge would move a room the user never edited. EMPIRICAL DISPROOF (Chris, 2026-08-04): he cleared the adjustments and forced re-analysis THIRTY times — everything stayed stable. Ids moved only when he loaded NEW images. That is the same determinism already established in the #18:A3-IMAGE--1 adjudication (no RNG, no set-iteration in the path; the id rides with the admitted blob), now confirmed by direct observation rather than by reading the code. And a new image is not this defect: the user has just replaced the map, the rooms genuinely changed, and re-nudging is the expected outcome — the same reasoning that retired A3-IMAGE--1. WHY THE FIX WAS WORSE THAN THE BUG: the specced token was image_segments['analyzed_at'], a wall-clock stamp minted fresh on EVERY successful analysis (mapping_services.py:1165) with no content fingerprint anywhere in the module. Since a re-analysis yields identical ids and a NEW timestamp, the gate would have suppressed every valid adjustment on every re-analysis — and the card force-re-analyses on each CV-variant upload (src/bindings/map.js:1104), so a user who dragged an edge and then uploaded a variant would silently lose the nudge. Precisely the 'destroys hand-made work at exactly the wrong moment' failure A3-IMAGE--1's fix was rejected for. A stamp keyed on a CONTENT fingerprint rather than a timestamp would be sound, but with the trigger disproven there is nothing left for it to protect. SCOPING CLAIM ALSO WRONG. The spec carried a 'secondary leak' where leftover CV adjustments apply to CUSTOM segments. The two systems are separate by construction — CV mints segment_N (adapters/eufy/segmentor.py:1289), custom mints custom_N (mapping_services.py:1685), into separate stores resolved by _resolve_active_scope. They cannot collide unless a hand-written service call supplies a colliding id, which is a deliberate affordance (caller-supplied ids let segment_room_links survive an edit), not a defect. Chris: the custom polygon system is completely separate from CV. The spec's 'optional, recommended' half — making adjust_map_segment scope-resolved so it works in custom mode — is therefore REJECTED outright: adjust is a CV nudge tool, and the custom system has its own editing path (set_custom_segments replaces polygons wholesale). ONE RESIDUAL, tracked separately and NOT part of these findings: _handle_get_map_segments applies image_segment_adjustments to scope['segments_store'] with no mode check (mapping_services.py:1210), so in custom mode it consults a CV-only store. Inert today because the namespaces differ; it is a latent aliasing seam and a one-line guard, not the defect filed here.

- **SN-10a** (agent: sensor (2-lens verified)) `sensor/theme.py:75`  
  KILLED: the claim that a hand-edited theme import can store a raw null name  
  -> KILLED — the reachability premise is fatal to the claim AS RECORDED. Stage B's reproducer executed it: import_theme does `name = str(source_theme.get('name','')).strip()` (themes/manager.py:537), so a JSON null becomes the STRING 'None', which is truthy and passes the `if not name` gate. The stated entry path — 'reachable via a hand-edited import' — cannot produce the defect. That sentence was mine and it was wrong. Split from the original SN-10 so Corpus C does not have to assert the LINE is correct; the line-level defect survives as SN-10b.

- **DR-DBG-5** (direct read) `debug_capture.py:263`  
  The restore guard cannot distinguish its own DEBUG from a user's mid-capture `logger:` DEBUG  
  -> Reaching it requires starting the flight recorder — a tool whose entire purpose is to avoid enabling `logger:` debug — and then enabling `logger:` debug anyway, mid-capture. That is a user footgun, not a defect: the two actions contradict each other. Documented in the module and in the post rather than guarded against.

## Regenerating this file

    python .claude/notes/_gen_checklist.py

Reads `.claude/notes/_audit_runs.json` (label -> workflow output path). To add an audit,
append one line to that manifest and re-run. Clusters are hand-curated in the generator --
a new audit's findings arrive as Tier 2 singles until they are clustered by hand.
