# Repair Family Catalogue — Part A: foundation & critical families (RF-01..RF-16)

**Produced by:** Fable synthesis pass, 2026-07-31/08-01 session. Target commit `c61b3eb` (source-identical to frozen `5be0931` for `custom_components/` and `src/`).
**Input:** `corpus/audit-findings-canonical.jsonl` (516 records, 484 open). Severity re-grades against the FROZEN plan §5 rubric are noted inline as `regrade:`.
**Member ids** are corpus `finding_id`s (unique across the corpus; the closure matrix resolves them to `canonical_id`s and validates completeness).

Legend for disposition: per §H — centralize / standardize_locally / repair_independently / migrate_or_version / document_only / defer.

---

## RF-01 — Finalize exactly-once: the protected window must cover the permanent gate  ★ FOUNDATION, PRIORITY 1

```yaml
family_id: RF-01
status: accepted
members: [HW-FINAL-1, A2-LIFE-1, A5-SVC-2, A5-STR-5, A3-SNAP-3]
candidate_root_cause: >
  The claim (finalize_claimed_at) is released in a finally: (learning/manager.py:737-741)
  while the permanent gate (finalized=True) is written by the CALLER in another module
  after an await (listeners/lifecycle.py L316→L334 executor round-trip→L349;
  jobs/active_job.py:2035). The comment at manager.py:738-739 asserting "finalized is the
  gate, so releasing does not reopen it" is false as written — hardware-proven double
  finalize on Ivy (ivy-run-BEFORE.log, 4 emissions for 2 jobs).
shared_invariant: >
  (a) Success permanence is written INSIDE the claimed window — no interleaving point may
  observe claim-released + finalized-unset after a successful body run.
  (b) The claim's refusal dict is not a success: every consumer must branch on it before
  firing events, marking slots finalized, or reporting success.
evidence_for_grouping: >
  HW-FINAL-1 is (a), CONFIRMED_EXECUTED on hardware + source-traced. A2-LIFE-1, A5-SVC-2,
  A5-STR-5 are three independent consumers violating (b) with the identical mechanism
  (refusal dict consumed as success → null-payload EVENT_JOB_FINISHED / fabricated
  status "completed" / bogus finalized:True). A3-SNAP-3 is the read side of the same
  window (snapshot never reads the claim, offers Pause/Cancel on a finishing run).
counterevidence_checked: >
  - Not a Roborock defect (corpus record rules this out explicitly; race is brand-agnostic,
    Eufy merely luckier in the capture). Repair must NOT be scoped to the adapter.
  - Refuted mechanisms (a) str(map_id) key miss, (b) two map buckets, (c) 71e089c-style
    wrapper bypass — recorded in HW-FINAL-1, do not re-try.
  - The claim itself (synchronous write before first await) is CORRECT; only the release
    ordering and the consumers are wrong. Do not redesign the claim.
intentional_divergence: >
  mark_active_job_finalized (caller-side) legitimately continues to set finalized=True and
  write finalize_summary — it becomes idempotent second writer, not the sole gate.
nonmembers:
  - A6-GUARD-2 / A6-GUARD-4 (double-cancel): the claim correctly rejects the second
    finalize there; the defect is upstream single-flight of CANCEL → RF-06.
  - The `_stored_job is None` no-else hole (same code block): carried as an explicit
    escalation question inside RP-001, not a separate finding.
disposition: repair_independently  # one bounded edit at the chokepoint + one consumer-contract pass
reason_disposition_is_best: >
  (a) is a single-site ordering fix at the chokepoint — no new abstraction is warranted.
  (b) is three call sites adopting the SAME check (`result.get("completed_job")` presence /
  `finalized: False` refusal shape) — standardize locally; a helper
  `finalize_result_succeeded(result)` in learning/manager.py (next to the producer, with
  its inverse — M1 corollary) is justified because the success-shape test is already
  open-coded at manager.py:651, :793, :888 and getting it wrong is exactly this family.
proposed_source_of_truth: >
  learning/manager.py::async_finalize_completed_job — success path writes
  _stored_job["finalized"] = True BEFORE popping finalize_claimed_at; claim released
  bare only on the failure/raise path. Plus finalize_result_succeeded() predicate.
compatibility_risks: >
  Consumers that today fire EVENT_JOB_FINISHED on refusals will stop firing them —
  that is the fix; automations keyed on the null-payload duplicate event (unlikely,
  payload is all-None) would see one fewer event.
migration_requirements: none (in-memory + per-job record field already exists)
empirical_requirements: >
  HARDWARE_BASELINE_GATE (tier 2, Ivy): the BEFORE capture exists
  (ivy-run-BEFORE.log). Post-repair: reproduce the cancel-and-dock double-entity flip;
  finalize body must emit exactly once per job. Alfred re-run desirable, not required.
repair_dependencies: none — this is the root of the graph.
estimated_closure_count: 5
confidence: high
```

**Fix shape (decided):** release-on-failure-only + gate-inside-window. In
`async_finalize_completed_job`: replace the `try/finally` with
`try: result = await self._finalize_claimed(...)` / `except BaseException: pop claim; raise`;
on the return path, when `isinstance(result, dict) and isinstance(result.get("completed_job"), dict)`
write `_stored_job["finalized"] = True` **then** pop the claim; when the result is not a
success shape, pop the claim only (retryable). Rejected alternative: moving
`mark_active_job_finalized` before the awaits in lifecycle — it would fix only ONE of the
entry points and leave the service/reaper paths racy; the chokepoint owns the guarantee
(same reasoning that moved the claim off the wrapper at `71e089c`).

---

## RF-02 — Destructive replace from an empty/absent source (the room-store wipe family)  ★ 5 CRITICALs at one seam

```yaml
family_id: RF-02
status: accepted
members: [A3-CRUD-1, A3-ROOMS-1, A3-ROOMS-2, A4-SETUP-1, A5-FACADE-1, A5-FACADE-2, A5-FACADE-3, A2-REC-4]
candidate_root_cause: >
  RoomMapManager.save_managed_rooms / rebuild_map / reconcile_room(migrate) replace
  map_bucket["rooms"] wholesale from data["discovery"] (or a migration plan), and only
  reconcile_room guards against an empty source. build_managed_rooms additionally treats
  enabled_room_ids=[] (which cv.ensure_list mints from null) as "explicitly select
  nothing" → managed = {} → total wipe, persisted by the service's async_save.
shared_invariant: >
  A destructive replacement of a non-empty persisted room store requires affirmative
  evidence: a non-empty, map-matching source snapshot, and a selection that is not the
  null-coerced empty list. Absent evidence → refuse with a machine-readable reason.
evidence_for_grouping: >
  Same wipe (map_bucket["rooms"] = {}) reachable through four entrances
  (service save_managed_rooms, setup_save_rooms, core facade, rebuild_map), plus the
  discovery-cache flavour (FACADE-2: good cache overwritten with []). The guard ALREADY
  EXISTS in two siblings (reconcile_room's no_discovery early-return; workflow
  _import_active_map) — forgotten-override-sibling shape, cause is hand-copied
  preconditions rather than a shared gate.
counterevidence_checked: >
  - "Empty selection = disable all rooms" is NOT a legitimate reading: disabling is the
    `enabled` flag; deletion of all room records loses floor types, rules, graph, colors.
    The intentional-removal path is remove_map / reject_rooms.
  - REC-4 (migrate) has a different SOURCE (plan_migration output) but the identical
    question; its guard needs a minimum-evidence test (not just non-empty) because
    discovery legitimately returns partial lists — the packet keeps that distinction.
  - Killed lookalike A5-AG-3 confirms rebuild_map has no in-repo caller — FACADE-3 stays
    LOW and rides along at the same chokepoint.
intentional_divergence: >
  _import_active_map's refusal-to-import-empty stays as is (its own message shape).
nonmembers:
  - A5-SVC-3 / A4-PP-RP-3 / RUNPROF-2 (selection wiped by apply/retry): different
    invariant (mutate-before-validate) → RF-05.
  - IO-2 / ACC-1 (read-failure conflated with empty at file RMW) → RF-03.
disposition: centralize
reason_disposition_is_best: >
  One guard at the delegate chokepoint (rooms/room_crud.py) covers all four entrances —
  the exact pattern that closed 10 card findings at one seam in audit #6. The question
  ("may this snapshot replace this store?") is asked identically by save/rebuild/migrate.
proposed_source_of_truth: >
  rooms/room_crud.py: module-level `_refuse_destructive_replace(stored_rooms, new_rooms,
  source_desc) -> dict | None` returning a {saved: False, reason: ...} refusal when
  new is empty and stored is non-empty. Lives beside the writers it guards (M1: rooms is
  the ring that owns the question; NOT common/). Schema side: enabled_room_ids
  null-vs-absent distinction fixed at the two schemas (vol.Any(None→refuse) or explicit
  None passthrough so build_managed_rooms sees None, not []).
compatibility_risks: >
  An automation that deliberately wiped a map by calling save_managed_rooms with an empty
  discovery would now get a refusal — that "feature" was undocumented data loss.
migration_requirements: none
empirical_requirements: SOURCE_DECIDABLE_GATE + tier 0 tests; no hardware run.
repair_dependencies: none
estimated_closure_count: 8
confidence: high
```

---

## RF-03 — A failed read is not an empty store (read-modify-write conflation)

```yaml
family_id: RF-03
status: accepted
members: [A3-IO-2, A2-ACC-1, A3-IO-3, A1-INIT-2, A4-SRC-2, A3-IMAGE--2, A3-IMAGE--3, A5-SVC-6, A4-STATE-8]
candidate_root_cause: >
  history_store.read_json collapses corrupt/unreadable/absent into one value (None);
  every read-modify-write over it (trouble_rooms per finalize, accuracy per record,
  stats caches, room-history preload, roborock room-source cache, CV segmentation store)
  then treats "could not read" as "empty" and commits a destructive write. Sibling
  flavour: a well-formed FAILURE envelope replaces or masquerades as good cache
  (IMAGE--2/3), and rebuild blanks the store before the replay is known possible (SVC-6).
shared_invariant: >
  Absent, unreadable, and failure-shaped inputs are three distinct states; only ABSENT
  may seed an empty store on a write path; unreadable/failed must refuse the write and
  must not be cached as a permanent answer.
evidence_for_grouping: >
  Identical consequence class (permanent destruction of learned/authored history that has
  no rebuilder by design — trouble_rooms, accuracy, custom segmentation) via the same
  conflation, across three storage subsystems.
counterevidence_checked: >
  - read_json's None-on-corrupt is deliberate fail-soft for READ paths (estimator serving
    "no data" beats crashing the loop) — the invariant violation is only at WRITE-BACK
    boundaries. So the repair distinguishes reader tolerance from RMW refusal; do NOT
    make read_json raise for all callers (that would trade data loss for loop crashes).
  - SVC-6's blank-then-replay is a different mechanism (ordering) with the same
    consequence; kept as a member because the packet's rule ("no destructive write until
    the replacement is materialized") covers it: build replacement in memory, then one
    atomic save.
  - A4-STATE-8 (live snapshot never cleared, stale outranks) is adjacent (staleness not
    read-failure) — kept as member for the same "source must prove freshness before a
    destructive finalize consumes it" rule; the packet clears the snapshot on finalize.
intentional_divergence: >
  write_json atomic-replace semantics stay; estimator read paths stay tolerant.
nonmembers: [CRUD-1-themes (overwrite_theme — RF-17: different mechanism, source
  resolution), FACADE-2 (discovery cache — RF-02, service-level guard)]
disposition: centralize
reason_disposition_is_best: >
  read_json is ALREADY the single seam (one function, one module). Extending it to a
  tri-state result (or a raise-on-unreadable variant `read_json_strict` used by the RMW
  callers) is the smallest change that every member consumes. Helper lives in
  history_store next to write_json (builder with its inverse).
proposed_source_of_truth: learning/history_store.py::read_json (tri-state) + per-RMW refusal.
compatibility_risks: a finalize during a transient SMB outage now SKIPS the trouble-rooms
  update (logged) instead of erasing history — strictly better; no schema change.
migration_requirements: none
empirical_requirements: SOURCE_DECIDABLE_GATE + tier 0 (fault-injection unit tests).
repair_dependencies: RF-01 first (both touch finalize write path; avoid combined commits).
estimated_closure_count: 9
confidence: high
```

---

## RF-04 — Entity ownership by string prefix (registry-deletion family)  ★ spec-example family — independently re-derived

```yaml
family_id: RF-04
status: accepted
members: [DR-SETUP-1, A2-CB-1, SN-3, EP-2, INF-5, DR-SENS-2, A2-CB-5, SN-7]
candidate_root_cause: >
  unique_id = f"{vac_key}_{map_id}_{room_id}_{suffix}" is a non-injective flat join
  (`_` is both separator and content, vac_key/map_id variable-length), there is no
  parser, and the four fan-out subscribers + the post-delete registry sweep all
  re-derive ownership by startswith(prefix) — so vacuum_alfred_2_* is a prefix-subset
  of vacuum_alfred + map "2". PROVEN destructive (DR-SETUP-1 measured: all 8 sibling
  entities removed from the registry; EP-2: maintenance numbers destroyed and
  unrebuildable by the callback that removed them).
shared_invariant: >
  Entity ownership questions ("which entities belong to (vacuum, map)?") are answered by
  structured identity, never by string-prefix matching over a non-injective join.
evidence_for_grouping: five consumer sites, one construction site, one proven consequence.
counterevidence_checked: >
  §G run INDEPENDENTLY of the spec's worked example (which arrives carrying authority —
  treated as a lead only). The example implies a compatibility reader or registry
  migration. MY CONCLUSION DIFFERS: no unique_id migration is needed at all, because no
  consumer needs to PARSE arbitrary ids —
  (a) the live fan-out subscribers (switch/number/sensor ×2) hold entity OBJECTS in their
      entity_map; each entity already carries its own vacuum_entity_id and map_id
      attributes. Classify stale by comparing the entity's own attributes to the
      notified (vacuum_entity_id, map_id) tuple — the tuple the notifier ALREADY passes
      and the consumers currently throw away. Zero registry risk.
  (b) EP-2's cross-domain hazard (maintenance numbers in the same entity_map) dies with
      (a): a maintenance entity has map_id=None and never matches a room-sync sweep.
  (c) the setup/delete.py registry sweep (entities may not be live) computes the EXACT
      unique_id set for the deleted map from its stored room ids × the known suffixes,
      plus the map-scoped singletons, via make_room_unique_id itself — a closed set,
      no prefix. INF-5's negative result (no within-one-vacuum collision constructible at
      {map}_{room} boundary) makes the closed-set computation sound.
  Agreement with the spec's "replace the named prefix consumers" half is corroboration;
  its migration half is REJECTED as unnecessary risk (the campaign's only real
  entity-registry migration risk disappears).
intentional_divergence: unique_id format itself is retained (INF-5 downgraded to
  document_only within this family — non-injective but no longer consumed as parseable).
nonmembers: [SN-1 (missing sensors — RF-34), SN-4 (rename propagation — RF-34)]
disposition: centralize
reason_disposition_is_best: one ownership predicate + one closed-set builder replaces five
  hand-copied prefix scans; DR-SENS-2's duplicated 40-line blocks fold into the same
  shared sync helper (the two blocks are byte-identical already).
proposed_source_of_truth: >
  entity_helpers.py — beside make_room_unique_id (builder + matcher in one module, M1
  corollary): `unique_ids_for_map(vac, map_id, room_ids) -> set[str]` and the
  attribute-based `entity_belongs_to(entity, vac, map_id)`. Consumers: switch.py:71,
  number.py:101, sensor/__init__.py:255+312, setup/delete.py:136.
compatibility_risks: none — no unique_id changes, no registry migration; existing
  customizations preserved (that is the point).
migration_requirements: none
empirical_requirements: tier 1 (deploy-live; entity list inspection after a room edit
  and after a map delete on a two-vacuum-name-prefix install is simulatable in tests;
  hardware pass = panel + entity list only).
repair_dependencies: none
estimated_closure_count: 8 (SN-7/A2-CB-5 close via the shared sync helper adopting the
  guarded write pattern; verify each independently per §L family-closure rule)
confidence: high
```

---

## RF-05 — Mutate/persist before validate (destructive apply-before-authorize)

```yaml
family_id: RF-05
status: accepted (split into 05a/05b at packet level)
members: [A4-PP-RP-3, A5-SVC-3, A4-PP-RP-7, A5-RUNPROF-2, A5-RUNPROF-3, A2-JOB-7, A6-DIAG-9, A4-SETUP-5, DQ-ACT-6]
candidate_root_cause: >
  05a: apply/start flows commit destructive room-selection + settings changes to storage
  BEFORE the start/authorization decision, with no snapshot/rollback (start_run_profile,
  retry_missed_rooms, apply_run_profile-with-missing-rooms).
  05b: handlers mutate manager.data then save outside the failure path (or save before
  registry validation), so memory/disk diverge on error (job_control save-after-except,
  maintenance/dock mutate-then-save, adapter_config persist-before-register).
shared_invariant: >
  05a: no destructive persisted mutation before the operation is authorized; a refused
  operation leaves the store byte-identical.
  05b: the persistence decision is taken WITH the mutation (same success path), never
  skipped on handled errors after the mutation landed.
counterevidence_checked: >
  05a and 05b pull in OPPOSITE directions (05a: don't persist early; 05b: don't leave
  landed mutations unpersisted) — they are one family only at the level of "ordering of
  mutate/validate/persist is undesigned"; packets are separate and MUST NOT share a
  helper. DQ-ACT-6 (device select left modified on failed dispatch) is device state,
  not storage: rollback of a physical select is best-effort by nature → packet notes it
  as a restore-attempt + log, or explicit wontfix per Chris.
disposition: standardize_locally (two patterns, applied per site; no shared helper)
reason_disposition_is_best: the sites differ in what "authorize" means (start status /
  saved flag / registry validation); a shared abstraction would encode incompatible
  exceptions — the §L warning case.
proposed_source_of_truth: pattern documented in docs/dev (order: validate → mutate →
  persist → report; or snapshot → mutate → validate → commit/rollback).
compatibility_risks: retry_missed_rooms/blocked start no longer destroys selection —
  user-visible improvement; no contract change.
empirical_requirements: SOURCE_DECIDABLE_GATE + tier 0.
repair_dependencies: RF-14 (the same handlers gain refusal-raising; combine per-module
  edits into one packet per module to avoid double-touching files, but keep commits per
  concern).
estimated_closure_count: 9
confidence: high
```

---

## RF-06 — Cancel/pause effectiveness at the dispatch chokepoint

```yaml
family_id: RF-06
status: accepted
members: [DQ-ACT-2, A1-WD-1, A2-CAN-1, A2-CAN-3, A4-AJ-3, A2-CAN-5, A2-CAN-6, A6-GUARD-2, A6-GUARD-4]
candidate_root_cause: >
  (i) _dispatch_active_phase performs 4 sequential awaits (pre-calls, per-room settings,
  live resolve, wire send) and never re-reads the job — cancel/pause set flags/status
  synchronously but the in-flight dispatch lands anyway (ACT-2/WD-1/CAN-1 are one
  defect reported three times; CAN-5 is the pause flavour).
  (ii) cancel clears _phase_dispatch_pending BEFORE return_to_base and neither the
  completion gate nor maybe_advance_phase checks _cancel_in_flight, so the cancel's own
  dock reads as phase completion (CAN-3/AJ-3 — one defect twice).
  (iii) cancel is not single-flight: status stays started for the 30s confirm window, so
  a second cancel (double-tap, blocker re-fire, overlapping reaper tick) enters and the
  loser nulls finalize_summary (CAN-6, GUARD-2, GUARD-4).
shared_invariant: >
  Cancellation and pause are effective at the last suspension point before the wire
  send; a job being cancelled is in a distinct state that (a) refuses new dispatches,
  (b) suppresses completion-gate advancement, (c) admits no second cancel.
counterevidence_checked: >
  - The exactly-once learning claim already prevents duplicate RECORDS in (iii) — the
    remaining damage is the nulled finalize_summary + duplicate device commands; family
    survives on those consequences.
  - (ii)'s clear-early is intentional for the dock-completion detection design; the fix
    is NOT to keep the flag set (would wedge) but to make the gate check
    _cancel_in_flight — preserving the flag's phase semantics. Recorded so Sonnet does
    not "simplify" by reordering the clear.
nonmembers: [A2-CAN-4/WD-4 (resume/restart re-arm — RF-07, watchdog lifecycle),
  path_blockers unavailable trigger (RF-13 — what fires the cancel, not the cancel)]
disposition: standardize_locally
reason_disposition_is_best: >
  three bounded edits in jobs/ (a re-check inside _dispatch_active_phase immediately
  before _dispatch_clean_payload; _cancel_in_flight checks in lifecycle gate +
  maybe_advance_phase; a cancel single-flight latch mirroring the finalize claim's
  shape). No new module: the state already lives on the job record.
proposed_source_of_truth: jobs/active_job.py (cancel latch) + jobs/phase_runner.py
  (dispatch re-check) + listeners/lifecycle.py (gate condition).
compatibility_risks: a cancel now aborts an in-flight dispatch — the robot may receive
  return_to_base WITHOUT the clean that raced it; strictly the intended semantics.
empirical_requirements: >
  HARDWARE_BASELINE_GATE tier 2 (dispatch path batch): cancel-during-dispatch on both
  brands; Ivy baseline exists (two cancels captured), Alfred cancel run needed
  (baseline gap: cancel not captured on Alfred — note in hardware register).
repair_dependencies: RF-01 (finalize contract) first; RF-07 shares files — sequence
  packets, do not combine commits.
estimated_closure_count: 9
confidence: high
```

---

## RF-07 — Watchdog wedge states and the reaper that cannot reach them

```yaml
family_id: RF-07
status: accepted
members: [A1-WD-2, A5-STR-3, DQ-ACT-3, A1-WD-4, A2-CAN-4, A1-WD-5, A5-STR-4, A5-STR-1, A5-STR-2]
candidate_root_cause: >
  _run_advanced_phase has no try/except/finally: a raising dispatch or exhausted retry
  exits with _phase_dispatch_pending set (WD-2, ACT-3, STR-3), which is ALSO an
  unconditional reaper exclusion — wedge + blinded recovery in one flag. Restart/resume
  re-arm covers only dock phases (WD-4, CAN-4). A dispatched-never-started run never
  arms has_observed_active_lifecycle so it is permanently unreapable and the NEXT run's
  signals finalize the stale slot (STR-4). The reaper itself dies forever on one raising
  finalize (STR-2 — the fix already applied to cancel at active_job.py:2249 was never
  mirrored) and consults only task_status vocabulary (STR-1).
shared_invariant: >
  Every exit from the phase watchdog resolves _phase_dispatch_pending (cleared, or
  converted into a REAPABLE state with a timestamp); the reaper can reach every
  non-progressing state and survives per-job failures.
counterevidence_checked: >
  - STR-3's exclusion exists to stop the reaper killing a job mid-dispatch — correct for
    a LIVE watchdog; the repair distinguishes "watchdog alive" (excluded) from
    "watchdog dead/gave up" (reapable) via a pending_since timestamp + age bound, not by
    removing the exclusion.
  - WD-4's comment claims a recovery path that does not exist — doc-vs-code divergence
    resolved on the code side (re-arm room_group/zone with a fresh dispatch attempt).
nonmembers: [WD-3 (has_native dead fallback — RF-12-adjacent vocabulary; folded into
  RF-11's attribution packet where the phase-confirm signal is adjudicated)]
disposition: standardize_locally
proposed_source_of_truth: jobs/phase_runner.py (try/finally + pending_since),
  jobs/job_monitor.py (reap arms), listeners/pause_timeout.py (per-slot isolation).
empirical_requirements: tier 2 dispatch batch (same runs as RF-06); WD-5 tier 0.
repair_dependencies: RF-06 (same files; RF-06's cancel latch lands first).
estimated_closure_count: 9
confidence: high
```

---

## RF-08 — Live-resolution freshness: never dispatch stale segment ids

```yaml
family_id: RF-08
status: accepted
members: [DQ-ACT-1, DQ-DE-1, A4-SRC-1, A4-SRC-2b_dispatch_note, A4-SRC-3, A4-SRC-4, A4-SRC-5]
  # A4-SRC-2's cache-overwrite half is closed by RF-03; its "dispatch trusts it" half here.
candidate_root_cause: >
  _resolve_live_dispatch_payload's total-miss branch RETURNS THE STALE PAYLOAD (the
  documented safety inverts exactly when it matters most: full re-segment); the
  refresh (async_refresh_room_source) is indistinguishable success/failure/skip and the
  cache carries no freshness stamp, no map-name collision handling, no coalescing, no
  invalidation — so "resolved live" is a belief, not a fact.
shared_invariant: >
  Dispatch may send only segment ids that were resolved against a live source proven
  fresh (stamped, matching the requested map); a total resolution miss REFUSES the
  dispatch with a user-visible reason, exactly as a partial miss skips rooms.
counterevidence_checked: >
  - Refusing on total miss can strand a run mid-sequence (per-room phases, DE-1):
    packet specifies skip-room-and-advance for phase dispatches vs refuse-start for
    job dispatch — different consumers, same invariant, explicitly not unified into one
    behaviour.
  - The stale-fallback comment says "dispatching stored ids" was a deliberate
    last-resort. Deliberate-but-wrong per the wrong-room consequence (frozen rubric:
    wrong-room actuation = HIGH/CRIT); documented intent does not survive the
    consequence test.
disposition: centralize (freshness lives in rooms/source_refresh.py; refusal at the two
  dispatch consumers)
proposed_source_of_truth: rooms/source_refresh.py — refresh returns a result
  {ok, refreshed_at, maps}; cache entries stamped; get_cached_room_source exposes age;
  collision-safe keying (map name + flag/index disambiguation) per SRC-3.
compatibility_risks: after a full re-segment, dispatch now fails loudly ("no target
  rooms on the current map — re-import rooms") instead of cleaning the wrong rooms.
empirical_requirements: tier 2 Roborock dispatch batch (Ivy) — needs Ivy woken
  (reference_roborock_idle_disconnect); HARDWARE_BASELINE_GATE unsatisfied until an Ivy
  dispatch-path capture exists (the two cancelled jobs partially cover it).
repair_dependencies: none (independent of RF-06/07 despite touching dispatch/manager.py
  — different functions; do not combine commits).
estimated_closure_count: 7
confidence: high
```

---

## RF-09 — Mapping source identity: bind every read to (device, map)

```yaml
family_id: RF-09
status: accepted
members: [A1-LC-1, A3-EXT-1, A4-RB-2, A4-RB-1, A1-LC-3, A1-LC-5, A4-RB-3, SN-5, A3-EXT-2, A7-ROBORO-3, A4-RB-5, A4-RB-6, A4-RB-4]
candidate_root_cause: >
  The Eufy in-memory candidate walk takes no vacuum identity (first coordinator wins —
  LC-1/EXT-1 are one defect at two layers); the Roborock walk takes no device and no map
  binding (RB-1/RB-2); caches are keyed without map_id on one path (LC-3) and
  last-writer-wins across awaits (LC-5); the content-version hash covers only the room
  raster while the cached value carries mutable geometry (EXT-2, and the same shape in
  roborock_raw_map's version vs room_names — ROBORO-3). RB-3: first duck-typed match
  hard-returns, so one false positive blanks the source. SN-5: the reader ignores the
  map_id the writer maintains ("never serve another map's geometry" wired into the
  writer only).
shared_invariant: >
  Every map/pose payload is bound to (device identity, map identity, content identity
  covering EVERYTHING served) at production, and every reader checks the binding.
counterevidence_checked: >
  - Single-vacuum installs mask LC-1/EXT-1. (CORRECTED per GATE4 Q13: Chris does NOT
    own an Omni E28 — the memory/handoff inventory was wrong. Multi-Eufy is
    hypothetical on his hardware; the defect remains real for any two-Eufy install
    and closure follows Q13: source verification + single-device regression, the
    multi-device proof left open, no fabricated closure.)
  - RB-4 (segment number as only identity, synthetic names) is identity of ROOMS not of
    the source; kept as member because the fix (stamp map identity + room-set identity
    into the payload) is the same binding stamp; the deeper re-map identity problem is
    RF-25's.
  - EXT-2's fix (hash geometry fields into the version) is cheap and local; ROBORO-3's
    is the same question, different inputs — standardize the RULE ("the version covers
    what the payload serves"), not a shared hash helper (different sources, different
    fields; a shared helper would take a field list = bare vocabulary, the anti-pattern).
disposition: standardize_locally (per-source binding; no new cross-source abstraction)
proposed_source_of_truth: mapping/map_source_runtime.py (device-scoped candidate
  selection: Eufy — select coordinator by device_id resolved from the vacuum's device
  registry entry; Roborock — require the per-vacuum image-entity root where available,
  else duid match), mapping/map_source_coordinator.py (map_id check on the mtime cache;
  commit-generation counter for LC-5).
compatibility_risks: two-robot accounts change served data (to the CORRECT robot) —
  flag in release notes.
empirical_requirements: >
  Multi-vacuum verification needs BOTH Eufy devices live (Alfred + Omni) — tier 2,
  new capture; single-vacuum regression = tier 1. EXT-2 fix is SOURCE_DECIDABLE.
repair_dependencies: none; sequence before RF-10 (same files).
estimated_closure_count: 13
confidence: medium-high (device-selection mechanics need packet-time source reads of the
  fork's coordinator device_id linkage — flagged in the packet as a verify-first step)
```

---

## RF-10 — Staleness must reach the consumer (sticky-hold qualification)

```yaml
family_id: RF-10
status: accepted
members: [A1-LC-2, A5-POSE-2, A5-POSE-4, A5-POSE-5, A1-LC-4, A5-POSE-1, A2-GEO-1, A5-POSE-3]
candidate_root_cause: >
  The hold path re-serves frozen moving fields (current_room, robot_anchor, path) as
  present:True with a stale flag NOTHING reads (POSE-2 proves zero readers); the mtime
  early-return additionally bypasses the live-pose override (POSE-5/LC-4); the live-pose
  reader is the ONE reader never repointed to memory-primary geometry (POSE-1/GEO-1 —
  one defect twice: memory-frame pixel through storage-frame geometry, feeding room
  attribution at 2s cadence) and skips the store_version guard (POSE-3).
shared_invariant: >
  Held/stale data is either withheld from consumers that act on it (attribution,
  sampling) or delivered with a consumed staleness contract (display); pose is always
  normalized against the SAME geometry frame that produced it.
counterevidence_checked: >
  - The hold itself is DELIBERATE and correct for display (docked Roborock would
    otherwise blank the card for hours) — the family does NOT remove the hold; it splits
    consumers: attribution/sampler refuse stale; card gets the flag surfaced (downstream
    card packet = carried CF-6 qualification gap, named as consumer, not closed here).
  - POSE-1/GEO-1's fix direction: repoint _load_live_pose_geom to memory-primary with
    storage fallback (the pattern every sibling already uses) — NOT recomputing frames.
disposition: standardize_locally
proposed_source_of_truth: mapping/map_source_coordinator.py (hold path nulls moving
  fields for the attribution surface OR consumers gate on stale — packet decides per
  consumer; _load_live_pose_geom memory-primary).
empirical_requirements: tier 2 (lifecycle batch, Eufy: live pose vs room attribution
  on a real run — OBS-B-1 cross-check territory).
repair_dependencies: RF-09 first (same files, identity before freshness).
estimated_closure_count: 8
confidence: high
```

---

## RF-11 — Phased-run recording: group attribution, completed-rooms, and the even-split trap

```yaml
family_id: RF-11
status: accepted
members: [DQ-PH-1, A3-IO-1, DQ-PH-3, A3-REC-1, A3-REC-2, A3-REC-3, DQ-PH-2, A2-CAN-2, A4-STATE-1, A4-STATE-2, A4-STATE-6, DQ-PH-6, A3-REC-4, A4-AJ-2, A1-WD-3]
candidate_root_cause: >
  Five compounding holes in how sequenced/phased runs are recorded:
  (1) phase writers deliberately set room_timing=[] for break/zone phases; the reader
      treats [] as "capture failed" → transit_capture_valid=False → EVERY stepped run
      learns an even wall-time split including dock time (DQ-PH-1 + A3-IO-1, one defect).
  (2) a multi-room group phase records queue_room_ids[0] only — whole group's
      time/area/battery on one room, N-1 rooms vanish (DQ-PH-3 + A3-REC-1); phase 0
      reads the WHOLE-RUN queue so the credited room may not even be in the phase
      (A3-REC-2).
  (3) completed_room_ids is reset per phase and never refilled (no rollover for phased
      jobs — A3-REC-3), so cancel/strand reports wrong missed rooms (DQ-PH-2/A2-CAN-2),
      the LAST room of every non-completed run is "missed" by construction and the
      documented retry automation loops (A4-STATE-1), and clear_incomplete_run erases an
      unrelated run's missed record on ANY completion (A4-STATE-2).
  (4) build_completed_job_payload's queue block prefers the LIVE queue (A4-STATE-6) —
      the exact incident (job_2026-07-13) already fixed for resolved_rooms and not for
      queue.
  (5) the two sample recorders still use the permanently-true started_at-and-not-ended_at
      predicate and fan writes into every map bucket (A3-REC-4/A4-AJ-2 — the module's own
      docstring names run_is_in_flight as the required fix).
shared_invariant: >
  A phased job's durable record must be assembled from phase-scoped evidence:
  per-phase rooms, per-phase timing validity by PHASE TYPE (not truthiness), a
  job-cumulative completed set, and the job's OWN frozen queue.
evidence_for_grouping: >
  All five holes corrupt the same durable record (completed_job) consumed by the same
  three consumers (learning ingest, incomplete-run/trouble-rooms, live progress), and
  OBS-B-1's three-inconsistent-durations hardware observation sits exactly at this seam.
counterevidence_checked: >
  - (2) cannot be "fixed" by inventing per-room timings inside an Eufy group phase —
    the device provides no per-room boundary there. The honest repair: record the group
    AS a group (allocated across members, flagged allocated, confidence capped) — which
    A2-ACC-6 shows the accuracy store already half-supports (single_room flag exists,
    unused). Fabricating exact per-room splits is FORBIDDEN in the packet.
  - (5) handoff records the sample recorders were DELIBERATELY left off
    dispatched_job_is_in_flight (must include external) — the correct target is
    run_is_in_flight, which includes external; this matches the module docstring's own
    prescription. Not a violation of the recorded intent.
  - killed A3-REC-6/REC-7 (learned-area fallback dead; counter-reset premise
    unestablished) bound what (2)'s packet may assume about counter semantics: the
    phase-slice counters are run-cumulative unless proven otherwise; no reset-detection
    logic may be introduced on the killed premise.
  - A4-STATE-1's last-room synthesis must NOT mark the last room completed on cancels
    without evidence (it may genuinely be missed) — fix is (3)'s cumulative set +
    timing-evidence-based completion of the final room at finalize, with the
    interrupted-case left honest.
intentional_divergence: >
  advance_active_job_phase resetting per-phase queue_room_ids stays (phases ARE
  fresh sub-jobs); the new job-cumulative completed set is a SEPARATE field, not a
  reinterpretation of the per-phase one.
nonmembers: [A2-ACC-* (estimator-side — RF-21), tracker holds (RF-31)]
disposition: repair_independently (five coordinated packets over one seam; no new
  abstraction beyond the cumulative-completed field and a phase-type-aware validity test)
proposed_source_of_truth: >
  (1) history_store.build_completed_job_payload: validity = per-phase
      `phase_type in CLEANING_PHASE_TYPES` (import from step_types — the module that
      exists for exactly this question; INF-8 closes at the same time) instead of
      truthiness of room_timing.
  (2) phase_runner._capture_finishing_phase_timing: emit one timing entry per
      resolved_room with allocated=True + per-phase resolved_rooms as the id source
      (fixes A3-REC-2 simultaneously).
  (3) queue_engine.advance_active_job_phase appends the finished phase's completed
      evidence to job-level `completed_room_ids_cumulative`; finalizer consumes it.
  (4) history_store queue block prefers the job's frozen queue (mirror the
      resolved_rooms precedence already shipped).
  (5) recorders adopt run_is_in_flight (leave the map-bucket fan-out to a scoped
      fix: write only to the bucket whose job matches).
compatibility_risks: >
  learned records gain fields (allocated flags, cumulative set) — additive, no schema
  version bump needed; stats_rebuilder must tolerate old records (it already tolerates
  absent keys). Learning outcomes will CHANGE for stepped runs (they stop learning
  poisoned even-splits) — that is the point; flag in release notes.
empirical_requirements: >
  HARDWARE_BASELINE_GATE tier 2 (lifecycle+finalize batch): a stepped run with a
  charge_wait + a 2-room group on Alfred, before/after. BASELINE GAP: the existing
  Alfred baseline is a single-room quick run — a stepped-run BEFORE capture is REQUIRED
  before this family lands (only decaying item this synthesis adds).
repair_dependencies: RF-01 (finalize single-execution) MUST land first — every
  verification run here reads the finalize output.
estimated_closure_count: 15
confidence: high on mechanisms; medium on (2)'s allocation design (product-visible,
  Chris reviews the allocated-timing semantics at Gate 4).
```

---

## RF-12 — The in-flight question: point every asker at the owned helpers

```yaml
family_id: RF-12
status: accepted
members: [A5-METRICS-1, A6-VAC-1, DR-SENS-1, A3-COMMON-6, A3-COMMON-4, A5-STR-1_vocab_note]
candidate_root_cause: >
  jobs/active_job.py owns dispatched_job_is_in_flight (queue question) and
  run_is_in_flight (robot question, includes "external") with docstrings prescribing
  exactly who should call which. Five+ sites hand-inline {"started","paused"} literals
  and answer the ROBOT question with the QUEUE set: job_progress ticker (external runs
  get no Lever B refresh), dock-action gate (fires mid-external-run — HIGH), active_job
  sensor ('none' during external), listener layer generally; the completion-vocabulary
  defaults are hand-copied in two modules (COMMON-4).
shared_invariant: exactly the helpers' own docstrings — robot questions ask
  run_is_in_flight; queue questions ask dispatched_job_is_in_flight.
counterevidence_checked: >
  - CF-2 (carried): pose-sampler predicates were DELIBERATELY not re-pointed (would add
    `paused` to sampling) — preserved as intentional divergence; explicitly excluded.
  - Each member re-adjudicated for robot-vs-queue: job_progress=robot (external ticks
    wanted — Lever B's stated purpose), dock gate=robot (the docstring names it),
    active_job sensor=robot-with-distinct-label (display 'external', not 'started' —
    additive state, card copes: verify card enum), COMMON-6's listener sites=
    per-site adjudication table in the packet (some are queue questions!).
disposition: standardize_locally (imports, not new abstraction — the helper EXISTS;
  this is feedback_centralize_question_not_vocabulary in its purest form)
proposed_source_of_truth: jobs/active_job.py helpers (existing).
empirical_requirements: tier 2 external-run capture (app-started run on Alfred) for
  VAC-1/SENS-1/METRICS-1 verification — batch with RF-11's lifecycle runs.
repair_dependencies: none
estimated_closure_count: 6
confidence: high
```

---

## RF-13 — unavailable/unknown is not a comparable value

```yaml
family_id: RF-13
status: accepted
members: [A6-GUARD-1, A3-COMMON-1, A3-SNAP-1, SN-2, DR-MNT-1, A6-PRE-1, A4-POSE-3, A3-COMMON-3]
candidate_root_cause: >
  State reads compare the literal strings "unavailable"/"unknown" (or a None state) as
  if they were values: blocker rules match every negating operator on a dropout and
  CANCEL a live run (GUARD-1 — CRITICAL, return_to_base from a Zigbee blip);
  is_job_active treats a not-yet-added entity as "no job" defeating the recharge guard
  (COMMON-1); mop_active collapses unreadable to False (SNAP-1); the maintenance sensor
  fabricates a full-life value from a missing attribute (SN-2+DR-MNT-1, one cluster);
  preflight's busy branch is unreachable because the same set is both evidence and
  exemption (PRE-1).
shared_invariant: >
  An unreadable entity yields INDETERMINATE. Indeterminate never satisfies a negating
  operator, never reads as a definite boolean, and never fabricates a numeric default
  that feeds statistics.
counterevidence_checked: >
  - GUARD-1's fix must decide what indeterminate does to an ACTIVE rule match: hold the
    previous verdict (no state change on dropout) — not "treat as unmatched" (which
    would UNPAUSE a run when the sensor drops mid-block). Packet pins hold-previous.
  - PRE-1 is set-logic (active set used as exemption) rather than sentinel conflation —
    kept because the repair is the same review of one predicate, but flagged: its fix
    changes start-preflight behaviour for error-state robots (blocked instead of ready)
    — Chris sees it at Gate 4.
  - INF-4 (BLANK_STATE_VALUES 20% consolidated) is the vocabulary substrate — folded in
    as the mechanical half (finish the consolidation at the 4 hand-copy sites).
members_also: [INF-4]
disposition: standardize_locally (three-valued handling per site; BLANK_STATE_VALUES
  import completion for the vocabulary)
empirical_requirements: GUARD-1: tier 2 optional — simulatable in tests (state-machine
  fixture); hardware confirmation cheap on Alfred (toggle a blocker sensor
  unavailability mid-run) — recommended, batch with lifecycle runs.
repair_dependencies: none
estimated_closure_count: 9
confidence: high
```

---

## RF-14 — Service error contract: refusals must be observable  ★ unblocks two carried card items

```yaml
family_id: RF-14
status: accepted
members: [A2-JOB-1, A2-JOB-3, A3-ROOMS-5, A3-ROOMS-7, A3-ROOMS-10, A4-SETUP-4, A4-SETUP-8, A4-SETUP-12, A5-RUNPROF-1, A5-RUNPROF-5, A5-RUNPROF-6, A6-DIAG-1, A6-DIAG-2, A6-DIAG-6, A5-SVC-4, A1-CRUD-7, A2-POLYGO-8, A3-IMAGE--7, A3-IMAGE--8, A4-CUSTOM-2, EP-1, A2-POLYGO-2_response_half, A6-VAC-2]
candidate_root_cause: >
  Result-returning manager APIs whose failure shapes are discarded at the service/entity
  boundary: refusals logged at DEBUG and dropped (start_selected_rooms — the only start
  service without supports_response), reason-literal gates that match one failure and
  fall through the rest (RUNPROF-1/5/6), success-shaped empty responses, saved:true on
  no-op or failed writes, dock "action sent" for a press HA dropped. Audit #6 proved the
  card-side twin (core.js hides every service failure); the two carried
  failure-renders-as-success card items are BLOCKED on precisely this backend contract.
shared_invariant: >
  A mutation service either raises (ServiceValidationError for caller error,
  HomeAssistantError for internal failure) or returns a response whose failure flag the
  registered contract exposes (supports_response) — and handlers gate on FLAGS
  (saved/applied/overwritten/performed), never on reason literals.
counterevidence_checked: >
  - Not every silent no-op is wrong: read-services returning empty-success where the
    integration is not loaded (SETUP-12) get the sibling error shape, not a raise.
  - The convention CHOICE (raise vs response) is per-service-class and is a Chris-visible
    contract change (HA UI shows raised errors as toasts) — packet batch carries a
    convention table; default: destructive/mutating → raise on refusal + keep response;
    fire-and-forget → add supports_response.
  - EP-1/A6-VAC-2 are entity-layer callers of the same result-returning APIs — same
    invariant, entity fix = inspect result, surface via HA persistent notification? NO —
    packet keeps it minimal: log + do-not-save-on-failure (parity with the service
    sibling that already raises).
disposition: standardize_locally (one stated convention, applied per module; the
  convention text lands in docs/dev — no code abstraction beyond what exists)
compatibility_risks: automations calling these services will start seeing errors where
  they previously "succeeded" — release-note item; this is the truth surfacing.
empirical_requirements: tier 0/1; card packet (CF-5) becomes unblocked AFTER the
  supports_response/raise change on the named services — card work named as downstream
  consumer, NOT closed by these packets.
repair_dependencies: coordinate with RF-05 (same handlers) — one packet per module
  covering both concerns, commits separated by concern.
estimated_closure_count: 23
confidence: high
```

---

## RF-15 — Durable state minted for unknown targets (phantom buckets)

```yaml
family_id: RF-15
status: accepted
members: [A1-SERVIC-1, A6-ZONE-C-6, A5-FURNIS-1, A3-IMAGE--5, A2-JOB-8, A5-RUNPROF-8, A6-DIAG-5, A6-DIAG-6_scope_half, A2-DRAFT-4, A1-SERVIC-5]
candidate_root_cause: >
  ensure_map_bucket setdefaults on read; 29 mapping schemas take free-form map_id and
  every handler mints the bucket (Roborock map_id = user-editable NAME, so a vendor-app
  rename orphans everything silently while writes report saved); queue/profile/error/
  dock/theme stores setdefault durable buckets for any well-formed entity_id;
  mapping_services uses resolved_call_data zero times vs 59 elsewhere (SERVIC-5).
shared_invariant: >
  Durable per-(vacuum, map) state is created only for managed vacuums and imported maps;
  read paths and not-found paths never create; unresolvable map_id refuses (per
  _common's own documented contract) rather than minting or guessing.
counterevidence_checked: >
  - ensure_map_bucket's create-on-demand is CORRECT for the import path — the repair
    adds `require_map_bucket` (refusing reader) beside ensure/get in maps/map_manager
    (builder-with-inverse, M1) and flips SERVICE handlers to it; import/setup keep ensure.
  - The killed A5-FURNIS-2 (first-stored-map fallback documented as deliberate for a
    display-only preference) BOUNDS this family: display-preference services may keep
    documented fallbacks; actuating/durable writers may not. That distinction is in the
    packet.
  - Roborock rename-orphan recovery (re-attaching orphaned buckets after a map rename)
    is NOT in scope here — that is a migration/product feature; this family stops the
    silent phantom growth. Recorded as a Chris question (map-identity strategy, ties
    to CF-3).
disposition: centralize (require_map_bucket + managed-vacuum check in services/_common,
  adopted per handler; mapping_services adopts resolved_call_data)
estimated_closure_count: 10
empirical_requirements: SOURCE_DECIDABLE + tier 0.
repair_dependencies: RF-14 (refusal surfacing must exist so the new refusals are
  observable); sequence after.
confidence: high
```

---

## RF-16 — Setup/unload parity: everything registered is torn down

```yaml
family_id: RF-16
status: accepted
members: [A1-INIT-1, A1-UP-1, A2-DOWN-1, A4-RELOAD-1, A1-UP-2, A1-UP-3, A2-DOWN-2, A4-RELOAD-2, A5-SVC-7, A2-DOWN-3, A4-RELOAD-4, A4-RELOAD-3, A1-WIRE-5, DR-DBG-3, A1-REG-2, A2-LIFE-2, A4-SRC-5, A6-VAC-4, A1-REG-3, A6-GUARD-6]
candidate_root_cause: >
  async_initialize spawns loop-lifetime work with no shutdown seam (INIT-1 — CRITICAL:
  a reloaded entry's PREVIOUS manager writes stale self.data over the live store);
  panels registered outside setup are untracked (×3 findings, one defect); 5 of 21
  learning services never unregistered (×4 findings, one defect); water-amendment
  listener+timer closure-local (×3); debug auto-stop timer closure-local (×3);
  lifecycle _process tasks untracked; room-source cache never invalidated; per-vacuum
  teardown doesn't reach listeners or cache markers.
shared_invariant: >
  Every loop-lifetime resource (task, timer, listener, service, panel, cache key)
  created by the integration is attached to a teardown ledger that unload and
  per-vacuum teardown fully drain. The idiomatic ledger is entry.async_on_unload.
counterevidence_checked: >
  - Killed A3-FLOW-1 confirms the reload-on-any-entry-change listener is HA-idiomatic
    and stays — reloads get SAFE, not rarer.
  - The learning-services list: derive the unregister list from the single registration
    table (dedup ladder: derived constant — appropriate; the QUESTION "what did we
    register" has one owner). NOT a domain-wide service sweep (would remove other
    entries' services in multi-entry futures).
  - INIT-1's fix = manager.async_shutdown() cancelling its spawned tasks/timers +
    entry.async_on_unload(manager.async_shutdown) — plus each subsystem exposing its
    cancel. The stale-write hazard also needs the manager to STOP writing after
    shutdown (a closed flag checked by async_save) — belt and braces, both specified.
disposition: centralize (the ledger pattern via entry.async_on_unload; per-leak edits)
proposed_source_of_truth: __init__.py (ledger usage) + core/manager.async_shutdown.
empirical_requirements: tier 1 (reload the entry twice on live HA; assert single panel,
  no ghost services, no duplicate managers) — cheap and high-value on Chris's box.
repair_dependencies: RF-01 first (INIT-1's stale-manager writes interact with finalize
  testing); this family EARLY because reload-safety underpins every later hardware pass.
estimated_closure_count: 20
confidence: high
```
