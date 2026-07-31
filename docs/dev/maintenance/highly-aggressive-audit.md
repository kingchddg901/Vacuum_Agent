# Highly Aggressive Audit

A deliberately hostile, multi-agent review of this integration, run subsystem by subsystem.
This page is the working ledger: **what it found, what has been fixed, and what has not.**

## What the campaign is

Each audit takes one subsystem and runs **eight agents** against it — six discovery agents
split by area, then two adversarial verifiers over the pooled findings. One verifier is
scored on *false positives killed*; the other must reproduce each finding with concrete
inputs and correct the severity. A finding only survives if neither kills it.

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

## Confidence

Findings below were reported by an agent and confirmed by two independent adversarial
verifiers. **A small number were additionally re-checked by hand against source; the rest
were not.** Treat an unverified entry as a strong lead, not an established defect, and
re-verify before acting on it — findings have gone stale within hours when other fixes
landed in between.

---

## Completed

**41 changes shipped**, all with tests, all deployed.

| | |
|---|---|
| Audits fully applied | #1 lifecycle · #2 learning · #3 external ingestion · #4 adapters · #5 error tracker |
| Partly applied | #6 card (root cause + top of the repair order) |
| Not yet applied | #7 onward — see [Open](#open) |

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
| `994f16e` | docs(maintenance): commit the hostile-audit ledger — completed and open, in one place |

---

## Open

**180 findings** across 5 audits, none applied. 14 clusters + 147 singles.

CRITICAL 11 · HIGH 48 · MEDIUM 58 · LOW 63

The same audits recorded **321 areas examined and found correct**.

> **No fix from any audit has run on physical hardware.** That gate comes before a release tag.

### Clusters — several findings, one fix each. Start here.

#### C1. Live-id resolution falls back to STALE stored ids — **verified by hand**

- **Seam:** `dispatch/manager.py:317`
- **Closes:** DQ-DE-1, DQ-ACT-1
- **Defect:** A single-target strict-order phase makes `dropped` non-empty EQUIVALENT to new_segments==[], so the 'live source unavailable' fallback fires for a target that was resolved and REJECTED. The robot cleans a different physical room, and the watchdog re-dispatches the same stale id up to 3x.
- **Fix:** Distinguish 'live source unavailable' (keep stored ids) from 'targets resolved and rejected' (skip or abort). Also correct phase_runner.py:1029, whose comment describes behaviour the code does not have.

#### C2. Cancel is lost across the dispatch chain's awaits

- **Seam:** `jobs/phase_runner.py:553`
- **Closes:** A1-WD-1, A2-CAN-1
- **Defect:** _cancel_in_flight is read ONCE per attempt, then four sequential awaits follow (global pre-calls, per-room live settings, live map refresh, dispatch) with no re-read. The user cancels, the robot returns to base, then drives back out and cleans the phase's room.
- **Fix:** Re-read the job (or re-check the cancel flag) between each await inside _dispatch_active_phase.

#### C3. _phase_dispatch_pending left set makes a run un-reapable forever

- **Seam:** `jobs/phase_runner.py:530`
- **Closes:** A1-WD-2, A5-STR-3, A2-CAN-3, A4-AJ-3
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

#### C9. Destructive room writes with no confirmation or preservation

- **Seam:** `rooms/room_crud.py`
- **Closes:** A3-CRUD-1, A3-CRUD-4
- **Defect:** save_managed_rooms unconditionally replaces map_bucket['rooms'], so an empty selection wipes the map's stored rooms. remove_map leaves the map's saved run-profile library, queue state and onboarding orphaned rather than removing or migrating them.
- **Fix:** Guard the wholesale replace against an empty/degenerate discovery, and make remove_map account for every structure keyed on that map_id.

#### C10. async_refresh_room_source returns None on success AND on every failure path

- **Seam:** `rooms/source_refresh.py`
- **Closes:** A4-SRC-1
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

#### C14. The tracker's end_job runs only on a SUCCESSFUL finalize

- **Seam:** `mapping/tracker.py`
- **Closes:** A6-TRK-1, A6-TRK-4
- **Defect:** end_job has exactly one caller, so every cancel, abort and stranded-reap leaves tracker state live into the next run. The last room of every job also never fires room_completed, because end_job resets the state that would emit it.
- **Fix:** Call end_job from every terminal path, and flush the final room before the reset.

### Singles

<details><summary><strong>CRITICAL</strong> (2)</summary>

- **A3-EXT-2** `mapping/map_source_runtime.py:966` · eufy  
  Content version hashes ONLY the room raster, but the cache it gates holds the grid geometry the fork mutates independently  
  During and after any run in which the map grows, or across any session where Eufy re-localizes its coordinate origin (a documented behaviour of this device), the robot dot lands metres from where the robot is, the room b
- **A4-PP-RP-2** `profiles/manager.py:1086` · both  
  overwrite_run_profile unconditionally destroys a saved profile's step sequence; save_run_profile preserves it — same "snapshot the current run" contract, opposite behaviour  
  A saved run "Downstairs, wait 30 min for the floor to dry, then Upstairs" (or any rooms->zone / multi-group run) loses its entire sequence the first time the user opens its editor and saves — e.g. just to fix a typo in t

</details>

<details><summary><strong>HIGH</strong> (29)</summary>

- **DQ-ZONE-1** `dispatch/manager.py:234` · eufy  
  Zone-clean pass count is never clamped on the Eufy branch — the clamp lives inside the device_mm branch Eufy never enters  
  An automation / YAML / script call `eufy_vacuum.start_zone_clean` (or `clean_saved_zone`/`clean_saved_zones`) with clean_times above the device ceiling reaches the robot unmodified: the value lands in the SelectZonesClea
- **DQ-ACT-5** `dispatch/manager.py:442` · roborock  
  The mixed-batch water SAFETY pre-call is best-effort — if it fails the clean still dispatches and the robot wet-mops the vacuum-only rooms  
  The robot wet-mops a room the user explicitly configured vacuum-only — on hardwood, rugs, or carpet. The user is shown a normal successful start; the only trace is a stack trace in the HA log. The failure mode is silent
- **A4-AJ-1** `jobs/active_job.py:472` · both  
  Mid-job recharge NEVER ends: the recharge-end branch is unreachable dead code, so recharge_seconds_accumulated is always 0 and every recharging run is silently held from learning  
  Any run where the robot returns to dock to recharge mid-job (the common case for large multi-room Eufy jobs) is silently excluded from learning with an `extreme_idle_wall` blocker, and its stored duration is inflated by
- **A2-CAN-2** `jobs/active_job.py:2255` · both  
  Cancelling a sequenced run reports the WRONG missed rooms — per-phase reset of queue_room_ids/completed_room_ids feeds the incomplete-run log and trouble-rooms counters  
  After cancelling a stepped run the card's incomplete-run banner and the EVENT_RUN_INCOMPLETE automation payload name the wrong rooms — under-reporting (rooms silently never retried by a `retry_missed_rooms` automation) o
- **A5-STR-2** `jobs/active_job.py:2447` · both  
  async_finalize_stranded_job calls the finalizer unguarded — one raising finalize kills the entire reaper tick for every vacuum, every minute, forever  
  One stranded job whose finalize raises permanently disables BOTH reapers for EVERY managed vacuum. Paused jobs past their timeout are never cancelled, stranded runs are never recovered, and the offending job itself stays
- **A6-PRE-1** `jobs/job_monitor.py:217` · both  
  The vacuum-state busy branch is unreachable for every HA-standard vacuum state — an errored or externally-cleaning robot classifies as "ready" and Start dispatches at it  
  The card shows "Ready to start cleaning." and an enabled Start button while the robot is sitting on the floor in an error/stuck state or paused mid-run. Pressing Start passes the only start gate and dispatches a real cle
- **A5-STR-4** `jobs/job_monitor.py:357` · both  
  A dispatched run the device never started can never be reaped, then the NEXT run's completion signals finalize the stale slot with the wrong run's data  
  A dispatch the robot never acted on leaves a phantom 'running' job that no automatic path can clear, and the next app-started run is silently recorded against it: wrong rooms, wrong duration, wrong start time, fed into l
- **DQ-ACT-3** `jobs/phase_runner.py:552` · both  
  A raising dispatch kills the phase watchdog task and wedges the run in 'started' forever  
  One transient service error mid-run (robot briefly unavailable, cloud hiccup) leaves the job permanently 'started'. The completion gate never fires, so the run is never finalized, learning records nothing, and every subs
- **A1-WD-3** `jobs/phase_runner.py:889` · both  
  has_native gates on the DECLARED entity-id string (always truthy on both shipped brands), so the coarse fallback is dead code and Eufy verifies phases against a signal its own adapter declares unusable as a live current-room source  
  On a Eufy 'vacuum -> charge to 80% -> mop' profile, the mop phase is re-dispatched up to 3 times, 90 seconds apart, while the robot is already mopping — each room_clean restarts the clean, so the robot repeatedly abandon
- **DQ-ACT-2** `jobs/phase_runner.py:1025` · roborock _(finder said CRITICAL; verifier corrected)_  
  Cancel is defeated by the phase watchdog: _cancel_in_flight is checked once, before two multi-second awaits, then the clean is dispatched unconditionally  
  User presses Cancel Run. The robot heads for the dock, then turns around and cleans the next room. The integration has already finalized and discarded the job, so nothing tracks or will stop the run; the user must cancel
- **DQ-PH-1** `learning/history_store.py:996` · both  
  Every break/zone phase flips transit_capture_valid to False, so a stepped run's per-room learning silently degrades to an even split of the run's wall time — charge/wait dock time included  
  Every run that uses the charge_wait / wait / zone step feature writes corrupted per-room baselines: the exact per-room area and wall-minutes that were captured are thrown away, and each room instead learns an even share
- **A4-RB-1** `mapping/map_source_runtime.py:373` · roborock _(finder said CRITICAL; verifier corrected)_  
  Roborock MapData lookup never binds the found map to the requested map_id — a multi-map (multi-floor) device converts drawn zones in the wrong floor's coordinate frame  
  On a Roborock with more than one saved map (a two-storey home — the exact case the adapter's `active_map = select.{id}_selected_map` block exists for), the user draws a zone box on the upstairs map and the robot vacuums
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
- **A2-REC-4** `rooms/room_crud.py:173` · both  
  migrate replaces the whole room map from one discovery snapshot — any room missing from that snapshot is permanently deleted, guarded only by 'the list wasn't empty'  
  One flaky or partially-named discovery turns a confirmation about id shifts into permanent deletion of rooms' entire configuration, with no preview, no undo, and no backup — the deletion bypasses drift's deliberate 3-pas
- **A3-CRUD-3** `rooms/room_crud.py:279` · both  
  save_managed_rooms auto-confirms floor type for every room it writes, permanently satisfying the onboarding_required start gate with the guessed value "hardwood"  
  The gate whose entire purpose is to force the user to declare carpet vs hardwood before the first clean is satisfied by a guess, on the very first import, for rooms the user has not looked at. A carpeted room reads as us
- **A2-REC-8** `rooms/room_manager.py:64` · both  
  The reachable room writer (save_managed_rooms/build_managed_rooms) carries settings by numeric id only, so a renumber stamps one room's floor type and access grants onto a different physical room  
  After a re-segment the robot runs the wrong room's settings on the wrong physical room — carpet/mop decisions inverted (mopping a carpeted room) and reachability grants pointing at the wrong neighbours, with no error and
- **A3-CRUD-2** `rooms/room_manager.py:64` · both  
  build_managed_rooms matches stored rooms by numeric id while room identity is the slug — a re-save after a re-segment transplants the previous occupant's access grants, rules and dock flag onto a different physical room and erases the reconciliation evidence  
  After any re-segment followed by the ordinary rescan-and-save, rooms silently carry the wrong configuration: the wrong room is flagged as the dock room, access grants point through rooms that are no longer adjacent (so r

</details>

<details><summary><strong>MEDIUM</strong> (54)</summary>

- **A6-AGX-2** `core/manager.py:1374` · both _(finder said HIGH; verifier corrected)_  
  The structural gate on every per-room edit is absolute, not a delta: one stored graph violation rejects unrelated edits (fan speed, enable, color) with "The requested access links would make the graph invalid."  
  After a Roborock re-segment + migrate, the user can no longer change ANY room setting on that map — changing a room's fan speed or disabling a room fails with an error claiming they requested illegal access links, which
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
- **A3-REC-5** `jobs/active_job.py:1721` · both  
  Every counter sample carries battery=None — last_battery_percent is read but never written by anything, so per-room battery attribution is dead on both recording paths  
  Per-room battery drain is never observed on either brand: every completed_job record's room_timings[].battery_delta is null, so the only per-room battery figure available anywhere is the even split total_battery_used / r
- **A2-CAN-5** `jobs/active_job.py:2101` · both  
  Pause has NO in-flight flag at all — a dispatch already inside _dispatch_active_phase lands after vacuum.pause and the robot cleans while the record says 'paused'  
  The card shows Paused while the vacuum keeps cleaning — the user's Pause visibly did nothing and no error is shown. The pause interval is also charged as paused time against the room's timing, so the room's learned durat
- **A2-CAN-4** `jobs/active_job.py:2155` · both _(finder said HIGH; verifier corrected)_  
  Pause+resume permanently kills the phase watchdog for room_group and zone phases — resume re-arms ONLY dock phases and never restores the dispatch guard  
  A pause+resume during a stepped run silently skips a room or an entire saved-zone step, and the run then finalizes as a normal successful completion (the guard that would have stalled it is gone). The user sees a clean '
- **A5-STR-1** `jobs/active_job.py:2378` · eufy _(finder said CRITICAL; verifier corrected)_  
  Strand exclusion consults only task_status against a narrower vocabulary — an Eufy dock service cycle reaps a healthy mid-run job as `interrupted`  
  A healthy Eufy vacuum+mop run parked at the dock for a service cycle is finalized as `interrupted` mid-run. `mark_active_job_finalized` sets status='completed' and clears the slot; the robot then resumes and cleans the r
- **A5-STR-5** `jobs/active_job.py:2464` · both  
  async_finalize_stranded_job reports success regardless of the finalizer's answer — a refused finalize still marks the slot 'completed' and fires a bogus EVENT_JOB_FINISHED  
  On an overlapping tick the user gets two EVENT_JOB_FINISHED events for one run — one carrying real data, one claiming status 'completed' with job_id None for a run that was actually interrupted and, in the None/missing_s
- **A6-PRE-2** `jobs/job_monitor.py:268` · both _(finder said HIGH; verifier corrected)_  
  invalid_payload uses phase 0's room count as the whole run's room count — a saved run profile whose first step is a zone is accepted on save but can never start  
  A user saves a run profile like "clean the hallway zone first, then the bedrooms", presses its exposed button, and gets "Room-clean payload is missing or invalid." every time, with rooms visibly selected and a valid queu
- **A1-WD-4** `jobs/phase_runner.py:125` · both _(finder said HIGH; verifier corrected)_  
  An HA restart during a room_group or zone phase's un-confirmed window strands the run — the re-arm covers ONLY dock phases and the comment's claimed recovery path cannot fire  
  Restart HA (or reload the integration) while a phased run is between rooms, and the run stops dead: the robot never leaves the dock, the card shows the job still 'started' forever, no error and no log line is emitted, th
- **A1-WD-5** `jobs/phase_runner.py:891` · future_brand_only  
  Adapter-declared phase_timing overrides are applied with no clamping — poll_seconds: 0 pins the event loop in a hot loop, max_attempts: 0 dispatches nothing and wedges the phase  
  A future brand adapter (the seam exists precisely so a third path-optimizing brand can declare its own profile) that ships a typo or a deliberate 0 either freezes Home Assistant's event loop for every integration on the
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
- **A6-TRK-2** `mapping/tracker.py:316` · both _(finder said HIGH; verifier corrected)_  
  resume_sampling is provably unreachable — _sampling_paused is a one-way latch, so all room attribution stops permanently at the first mid-job recharge  
  As soon as a run docks for an unplanned low-battery recharge, live per-room attribution dies for the whole rest of the run: no further `eufy_vacuum_room_completed` events, no dwell accrual, and the card's ETA timeline st
- **A6-TRK-3** `mapping/tracker.py:450` · both _(finder said HIGH; verifier corrected)_  
  The HOLD path keeps ACCRUING dwell and movement for a room the robot has already left, inflating duration_seconds and forcing confidence to 1.0  
  src/controllers/learning-controller.js:154-164 reads `duration_seconds`, records it as the room's `actual_duration_minutes` (620/60 = 10.3 min instead of 0.3 min), adds it to `_jobProgress.completedRoomMinutes`, and call
- **DQ-Q-5** `maps/map_manager.py:197` · both  
  A map rebuild silently auto-enables AND auto-approves rooms that never existed before, adding them to the clean queue unseen  
  After a Rebuild Map, any segment that appeared since the last rebuild — a room the user renamed into existence in the vendor app, or on Eufy a phantom segment the CV segmenter split off — is cleaned on the next Start wit
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
- **A4-SRC-3** `rooms/source_refresh.py:205` · roborock  
  flatten_maps_response keys the cache by map NAME with last-writer-wins and no collision detection; a collapsed cache chains into room_discovery's single-map fallback and serves one map's segment ids for a different map_id  
  In a multi-map (multi-floor) Roborock home, a map whose cache key collides vanishes from discovery, and jobs targeting it can be dispatched against the surviving map's segment ids — the robot cleans the equivalently-name
- **A4-SRC-2** `rooms/source_refresh.py:280` · roborock _(finder said HIGH; verifier corrected)_  
  set_cached_room_source is called unconditionally on every successful service call, so a response the flatten shim does not recognise (or an empty maps list) silently REPLACES a good cache with {} — logged at DEBUG only  
  Every room silently disappears from the setup tab, the card, and the room picker; after three passes the drift system reports the user's entire room set as removed. Any job whose targets can no longer be resolved degrade
- **A1-ID-4** `setup/drift.py:540` · both  
  Drift keys its history by bare device room_id across ALL maps but feeds it only the ACTIVE map's discovery, so a multi-map vacuum's inactive rooms decay toward 'removed' and colliding ids mask each other  
  A user with an upstairs and a downstairs map is repeatedly told that the rooms on whichever floor is not currently active have been removed from the vacuum, with the wrong floor's name attached; and a room genuinely dele
- **A6-AGX-6** `src/state/room-access.js:85` · both  
  The card's access modal renders an existing edge into the dock room as "Missing Room N" — an edge that exists is displayed as a stale reference to a room that does not  
  The editor misrepresents the stored graph: a live room is labelled missing/stale, inviting the user to delete a valid edge. Conversely they cannot re-create it, because the dock room is filtered out of the selectable lis

</details>

<details><summary><strong>LOW</strong> (62)</summary>

- **A1-ID-5** `adapters/eufy/discovery.py:47` · eufy  
  adapters/eufy/discovery.py is a dead, divergent second implementation of get_active_map_id / discover_rooms_for_vacuum with hand-copied sentinel and key literals  
  No user impact today (dead code), but it is a green-tested Eufy-flavoured copy of the identity functions sitting in the adapter package a future brand port would read first — reviving it re-introduces the 'null' sentinel
- **DQ-ZONE-5** `core/manager.py:4030` · both _(finder said MEDIUM; verifier corrected)_  
  zone_bounds is computed and shipped in the dashboard snapshot but has no consumer anywhere — and the card replaces the precise refusal message with a generic toast  
  Roborock's declared ceiling is 3.05 m² (roborock/adapter.py:614) — about a 1.75 m square, smaller than many ordinary draws — so a user drawing a normal box gets a refusal on press, and the actionable text explaining WHY
- **DQ-ACT-7** `dispatch/manager.py:421` · future_brand_only  
  The OFF-fallback lowercases the select's options for the membership test but then sends the lowercased string as the option value  
  On a future brand whose select uses capitalized or numeric options, the mop-intensity pre-call silently no-ops and the run uses whatever water the device was last left on — the same physical outcome as DQ-ACT-5, reached
- **A2-CAN-6** `jobs/active_job.py:2189` · both  
  async_cancel_active_job is re-entrant — a second cancel arriving inside the 30 s confirm window overwrites finalize_summary with all-None  
  The post-run summary on the card goes blank after a double cancel — no outcome, no learning verdict, no sanity flags — even though the record on disk is intact. An automation listening on EVENT_JOB_FINISHED fires twice,
- **A6-PRE-4** `jobs/job_monitor.py:32` · both  
  BlockedRoomEntry.source documents "access_graph" for graph-propagated blocks; the producer writes "access_dependency", and the wrong literal is hand-copied into an exposed sensor attribute's type  
  The blocked-room `source` is surfaced as the `last_block_source` attribute on a per-room HA sensor. A user (or a future card branch) writing an automation template against the documented `access_graph` value silently nev
- **A6-PRE-3** `jobs/job_monitor.py:58` · both  
  PreflightResult declares `available` with a documented contract the producer never honours, and omits two keys the producer writes  
  Latent trap rather than live misbehaviour: nothing reads `available` today (manager.get_start_status derives the all-blocked case from included_room_count instead, core/manager.py:2834). Any future consumer that trusts t
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
- **A6-TRK-5** `mapping/tracker.py:47` · both _(finder said MEDIUM; verifier corrected)_  
  _norm_room_name normalises differently from slugify_room_name — it merges room identities that rooms/ keeps distinct, and lacks the NFC canonicalisation slugify was given specifically to prevent this  
  Case (a): live dwell is attributed to the wrong room id whenever two rooms' names differ only in a separator character, and the card's reanchored timeline marks the wrong room complete. Case (b): for non-ASCII room names
- **A6-TRK-6** `mapping/tracker.py:196` · both  
  Dock-drift append rewrites the entire log file on every reading, and a failed write silently forfeits that drift event via the already-committed _last_dock_pos  
  On an SD-card or eMMC HA install the rewrite amplification is real flash wear for a purely diagnostic log; the cost scales with how often the reported docked position jitters, which is exactly what the log exists to meas
- **A6-TRK-7** `mapping/tracker.py:286` · both  
  start_job/end_job are dispatched to an executor thread on the strength of a comment describing disk I/O that start_job does not perform  
  No user-visible failure proven: the individual dict operations are GIL-atomic and the interleaving window is a handful of bytecodes, so at worst one position sample is misrouted at job start. The real cost is that a fals
- **A3-CRUD-6** `maps/map_manager.py:181` · both _(finder said MEDIUM; verifier corrected)_  
  Both room writers auto-enable and auto-approve rooms the user has never seen (DQ-Q-5 extension: the live instance is save_managed_rooms, not rebuild_map)  
  A segment that appeared since the last save — a re-segment splitting one room in two, or a stray CV artefact — is added to the map already enabled, already approved and already floor-type-confirmed by the next `save_mana
- **A1-ID-6** `models/models.py:162` · both  
  RoomRecord documents grants_access_to as 'list[str] — room slugs' but every producer and consumer stores integer room ids  
  No current runtime defect; it is a loaded trap on the only place a developer looks up the field's namespace, in the exact subsystem where mixing the id and slug namespaces produces wrong-room behaviour.
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
- **DQ-PH-6** `queue/queue_engine.py:466` · future_brand_only  
  advance_active_job_phase resets every per-phase pointer except _native_current_room_id, leaving a latent cross-phase carry-over that only the phases-gate currently hides  
  None today. It is a tripwire under the phases-gate: relaxing active_job.py:937 (which is the natural fix for DQ-PH-2/DQ-PH-3, since a multi-room group phase genuinely needs intra-phase rollover) immediately activates dup
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
- **A4-SRC-5** `rooms/source_refresh.py:80` · roborock _(finder said MEDIUM; verifier corrected)_  
  The room-source cache is never invalidated — not on config-entry unload/reload, not on map switch, not when a vacuum is unmanaged — and it keeps hass.data[DOMAIN] alive so the unload cleanup never fires  
  Right after a reload — the moment the user is most likely to be reconfiguring rooms — discovery and dispatch can resolve against a snapshot from before the reload with no indication of its age. Stale entries for removed/
- **A4-SRC-4** `rooms/source_refresh.py:274` · roborock _(finder said MEDIUM; verifier corrected)_  
  No in-flight coalescing or lock on the refresh: triggers spawn unbounded concurrent get_maps cloud calls, and an older response landing last becomes the resident cached snapshot — including one that started before a map switch and lands after it  
  Redundant cloud calls raise the probability of the get_maps failure that triggers SRC-1's wrong-room dispatch. When a pre-switch response wins the race, the cache holds the previous map's segment ids under the current ma

</details>

### Carried forward from before the audits

- **`active_boundaries` round-trip (SEG-1)** — Deferred deliberately: it changes a persisted record field and warrants separate scrutiny.
- **Pose sampler predicates** — Two call sites were deliberately not re-pointed at the shared in-flight helper, because doing so would silently add `paused` to what gets sampled. Wants its own change.
- **Roborock room migration** — Room *creation* now takes brand-correct defaults. Rooms created before that still carry the old values. Stored user data, so repairing it is a product decision.
- **Three card strings untranslated** — `common.service_failed`, `learning.room_skipped`, `learning.run_incomplete_toast` are English-only across the 17 non-English locales.
- **Card: the two failure-renders-as-success paths** — Blocked on a backend `supports_response` change.
- **Card: the qualification gap** — Surface provenance, truncation and absent data honestly rather than as confident values.
- **Card: surface captured run errors** — The backend now carries app-started-run error evidence end to end. Nothing displays it.
- **OpenDyslexic font support** — Contract settled — English-only gate, one token override, glyph coverage proven per locale before offering another. No code written.

---

## Suggested repair order

Ordered by (verified) × (blast radius) × (cost), not by severity label.

1. **C5** — 2 lines, verified, and it closes a gap introduced by an earlier fix in this campaign. Cheapest real win.
2. **C7** — verified CRITICAL. Slug uniqueness at discovery: wrong physical room, plus silent replacement of the second room's stored settings. Correct the docstring's false claim at the same time.
3. **C1** — verified CRITICAL seam. The other wrong-physical-room path.
4. **C11** — verified CRITICAL. Give the Eufy in-memory source a vacuum identity. Latent on a single-robot install, but a second Eufy robot gets the first one's map, rooms, pose and render raster — so a room tap cleans the wrong room. The fix pattern already exists on the Roborock side.
5. **C10** — small, and a third route to the same wrong-room outcome: a failed refresh is indistinguishable from a successful one, so stale ids reach the wire.
6. **C9** — destructive writes. An empty selection wiping a map's stored rooms is one bad call away.
7. **C3** — a `try/finally` so one transient failure stops bricking every subsequent run.
8. **C8** — decide reconciliation's trigger. The machinery is built and nothing calls it. This is the *root* of C1 and C7 rather than another instance of them.
9. **C13** — the sticky-hold `stale` flag has no consumer, so a frozen pose is served as present. Cheap, and it makes a whole class of phantom-room report visible.
10. **C14** — call the tracker's `end_job` from every terminal path, not only a successful finalize.
11. **C12** — pose frame mismatch. Needs the memory-vs-storage frame question settled first.
12. **C2** — cancel correctness. Needs care around the await boundaries.
13. **C6** — user-visible on every mop room, but it changes resolution precedence, so test hard.
14. **C4** — per-phase attribution. Touches the shape of learning data.
15. Remaining HIGHs, then MEDIUMs. LOWs only when the file is already open for another reason.

## Calibration

Measured cost per audit, for scoping future runs.

| Audit | Subsystem | LOC | Tokens | Wall |
|---|---|---|---|---|
| #7 | dispatch + queue | 1,515 | 1.58M | 23 min |
| #8 | profiles + planning | 3,677 | 1.95M *(includes a re-verify forced by a harness bug)* | 40 min |
| #9 | jobs / run execution | 3,914 | 1.50M | 23 min |
| #10 | rooms / identity | 2,531 | 1.07M | 21 min |
| #11 | map source + tracker (scoped) | 3,126 | 1.39M | 27 min |

Cost tracks the **eight-agent shape far more than subsystem size** — one audit covered
2,531 lines for 1.07M tokens while another covered 1,515 lines for 1.58M. Scope by agent
count, not by lines of code.

