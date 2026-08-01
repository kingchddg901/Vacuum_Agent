# Sonnet Application Packets — Wave 1 (RP-005..RP-009)

---

## RP-005 — Room-store wipe guard at the room_crud chokepoints

```yaml
packet_id: RP-005
title: empty/absent discovery can no longer replace a non-empty room store
repair_family: RF-02
goal: the five CRITICAL wipe paths refuse with machine-readable reasons
violated_invariant: destructive replace requires affirmative evidence
findings_addressed: ["#10:A3-CRUD-1", "#13:A3-ROOMS-1", "#13:A3-ROOMS-2",
  "#13:A4-SETUP-1", "#14:A5-FACADE-1", "#14:A5-FACADE-2", "#14:A5-FACADE-3",
  "#10:A2-REC-4"]
findings_not_closed: ["#13:A3-ROOMS-10" (supports_response — RP-031),
  "#13:A3-ROOMS-3" (floor_types field — RP-031/RF-28)]
target_commit: post-RP-004 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/rooms/room_crud.py
  - custom_components/eufy_vacuum/rooms/room_manager.py
  - custom_components/eufy_vacuum/services/rooms.py
  - custom_components/eufy_vacuum/services/setup.py
  - tests/
symbols_to_add: [rooms.room_crud._refuse_destructive_replace]
symbols_to_modify: [RoomMapManager.save_managed_rooms, RoomMapManager.rebuild_map,
  RoomMapManager.reconcile_room (migrate arm), RoomMapManager.discover_rooms,
  room_manager.build_managed_rooms signature docs, _SAVE_MANAGED_ROOMS_SCHEMA,
  _SETUP_SAVE_ROOMS_SCHEMA]
ordered_edits:
  - step: 1
    what: >
      Add `_refuse_destructive_replace(stored_rooms: dict, new_rooms: dict,
      source_desc: str) -> dict | None` in rooms/room_crud.py: returns
      {"saved": False, "reason": "empty_replacement_refused", "source": source_desc,
      "stored_room_count": N} when new is empty and stored is non-empty; else None.
      Module docstring records the question and the drift that justified it (the two
      siblings that already guarded — reconcile_room's no_discovery, workflow's
      import refusal — and the five CRITICALs that did not).
  - step: 2
    what: save_managed_rooms (:221-296): after building managed_rooms, call the guard
      before the `map_bucket["rooms"] = managed_rooms` assignment; on refusal return
      the refusal dict (no mutation, no floor-confirm loop, no notify).
  - step: 3
    what: rebuild_map (:403-442) — same guard before assignment.
  - step: 4
    what: reconcile_room migrate arm (:145-173) — keep the existing no_discovery
      guard; ADD a minimum-evidence guard: refuse when plan_migration's new_rooms
      would drop more than half of stored rooms AND the discovery list is smaller
      than the stored list, reason "partial_discovery_refused", overridable with a
      new explicit kwarg force=True (service schema gains vol.Optional("force")).
      Rationale in-comment: discovery legitimately returns partial lists
      (unnamed/blank segments are skipped), REC-4.
  - step: 5
    what: discover_rooms (:50-79): when discover_rooms_payload returns rooms=[] AND
      the existing cached discovery for that map is non-empty, keep the old cache,
      return the payload with "cache_kept": true and reason "empty_discovery_kept"
      (FACADE-2). A genuinely-empty first discovery still writes (absent ≠ failed).
  - step: 6
    what: >
      enabled_room_ids null-vs-absent: in _SAVE_MANAGED_ROOMS_SCHEMA and
      _SETUP_SAVE_ROOMS_SCHEMA replace `vol.All(cv.ensure_list, [vol.Coerce(int)])`
      with a validator that maps None → refusal (vol.Invalid "enabled_room_ids: null
      is not a selection; omit the key to keep the current selection") and []
      → vol.Invalid "empty selection cannot delete rooms; use enabled flags or
      remove_map". (ROOMS-2's exact confusion becomes a loud schema error.)
compatibility_behavior_to_preserve:
  - the import path (workflow) and first-ever discovery still create stores freely
  - explicit enabled subsets still prune to the selected set (non-empty)
forbidden_simplifications:
  - guard must compare against the STORED store, not the discovery (a shrunk-but-
    non-empty discovery is step 4's business, not step 2's)
  - no silent logging-only guard — refusals must reach the caller (RP-031 will
    surface them; until then the service returns the refusal dict on the
    supports_response services and logs WARNING on the rest)
reproduction:
  reproducer_script: reuse .claude/notes/_proof_setup.py (attach; extends the proven
    setup_save_rooms wipe harness) + a new case for enabled_room_ids: None through
    the REAL schema (execution precedent in the corpus: cv.ensure_list(None) == [])
  expected_before:
    asserted_values: map_bucket["rooms"] == {} after each of the five paths
    required_output_fragments: ["rooms after save: 0"]
    forbidden_output_fragments: ["refused"]
  expected_after:
    asserted_values: stored rooms unchanged; refusal reasons per path
    required_output_fragments: ["empty_replacement_refused"]
    forbidden_output_fragments: ["rooms after save: 0"]
regression:
  existing_tests: room_crud/save tests
  tests_to_add: [five wipe paths refuse; first-import still writes; explicit subset
    still prunes; None/[] schema rejections; migrate force override]
  closure_assertions: per finding — each of the 8 verified at its own entrance
hardware_validation: tier 0 (SOURCE_DECIDABLE_GATE) — approver main agent
rollback_plan: git revert; no schema/storage migration
stop_and_escalate_when:
  - any in-repo caller intentionally wipes via empty discovery (report; do not keep it)
  - the card sends enabled_room_ids: [] anywhere (grep src/ — if found, card change
    required first; escalate)
```

---

## RP-006 — read_json tri-state and RMW refusals

```yaml
packet_id: RP-006
title: unreadable is not absent — destructive RMWs refuse on failed reads
repair_family: RF-03
goal: no learned/authored history is erased because a read failed
findings_addressed: ["#16:A3-IO-2", "#16:A2-ACC-1", "#16:A3-IO-3", "#14:A1-INIT-2",
  "#14:A2-CB-2", "#10:A4-SRC-2", "#18:A3-IMAGE--2", "#18:A3-IMAGE--3", "#16:A5-SVC-6",
  "#16:A4-STATE-8"]
target_commit: post-RP-005 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/learning/history_store.py
  - custom_components/eufy_vacuum/learning/job_finalizer.py
  - custom_components/eufy_vacuum/learning/estimator.py
  - custom_components/eufy_vacuum/learning/manager.py
  - custom_components/eufy_vacuum/core/manager.py
  - custom_components/eufy_vacuum/rooms/source_refresh.py
  - custom_components/eufy_vacuum/mapping/mapping_services.py
  - tests/
symbols_to_add: [history_store.ReadOutcome (ABSENT|OK|UNREADABLE tri-state wrapper) or
  read_json(..., strict=...) variant — implementer picks the SHAPE, semantics fixed]
ordered_edits:
  - step: 1
    what: history_store.read_json returns/exposes the tri-state; existing callers keep
      None-tolerant behaviour via a thin compat wrapper (read paths unchanged).
  - step: 2
    what: job_finalizer trouble-rooms RMW (:1624-1657) — on UNREADABLE skip the update,
      log WARNING once ("trouble-rooms update skipped: store unreadable"); ABSENT
      seeds {} as today. (IO-2)
  - step: 3
    what: >
      (AMENDED per REVIEW D4) estimator.record_estimate_accuracy (:589-664) — same
      rule for accuracy_stats. Cache policy for UNREADABLE: cache it WITH a
      retry-after stamp (60s monotonic backoff) — NOT uncached. Rationale: an
      uncached UNREADABLE would re-attempt the blocking read on EVERY estimate()
      call on the event loop for the duration of an SMB outage (hot-loop). After
      the backoff expires, the next read retries; a successful read replaces the
      entry (IO-3's permanent-None poisoning still closed).
  - step: 4
    what: core/manager room-history preload (:2206-2286) — on rebuild failure keep the
      persisted cache (do not assign {}), do not set ready (retry next trigger)
      (INIT-2); the post-await assignment MERGES over writes that landed during the
      await keyed by job id, or re-reads-and-reconciles (CB-2) — implementer picks,
      packet requires "no concurrent write lost" as the testable property.
  - step: 5
    what: rooms/source_refresh set_cached_room_source call site (:274-286) — an empty
      per_map from a non-empty previous cache logs WARNING and keeps the old cache
      (SRC-2; freshness stamping itself is RP-007's).
  - step: 6
    what: mapping_services analyze path (:1100, :1172-1175) — write the result only
      when result.get("available") is truthy; on failure KEEP the previous
      image_segments and return the failure envelope to the caller (IMAGE--2); the
      cache-hit gate checks available, not truthiness (IMAGE--3).
  - step: 7
    what: learning/manager.rebuild_accuracy_stats (:994-1010) — build the replacement
      in memory over the archive replay, then ONE save at the end; no blank-first
      (SVC-6).
  - step: 8
    what: live snapshot (STATE-8) — clear last_job_snapshot.json + _live_snapshot_cache
      at successful finalize (call sited in job_finalizer's success path), and
      _collect_finalization_inputs prefers the ACTIVE job's job_id over a snapshot
      whose job_id differs (mismatch logged).
forbidden_simplifications:
  - read paths (estimate serving) stay tolerant — only WRITE-BACK boundaries refuse
  - no fsync work here (IO-7 is a separate small packet)
reproduction:
  reproducer_script: NEW _proof_rmw_conflation.py — chmod/corrupt each store file,
    drive the RMW, assert survival (before: file replaced with one-job store)
  expected_before:
    required_output_fragments: ["trouble_rooms rooms after RMW: 1"]
  expected_after:
    required_output_fragments: ["update skipped: store unreadable", "rooms after RMW: 9"]
regression:
  tests_to_add: [per-member fault-injection tests; ABSENT-first-run seeding unchanged]
hardware_validation: tier 0
rollback_plan: git revert per step-group (three commits: learning stores / caches /
  mapping store)
stop_and_escalate_when: [a Windows/SMB-specific errno makes UNREADABLE undetectable —
  report the errno, keep fail-soft]
```

---

## RP-007 — Dispatch never sends stale segment ids

```yaml
packet_id: RP-007
title: total live-resolution miss refuses; the room-source cache proves freshness
repair_family: RF-08
goal: the two wrong-room CRITICALs close; re-segment produces loud refusal, not wrong rooms
findings_addressed: ["#7:DQ-ACT-1", "#7:DQ-DE-1", "#10:A4-SRC-1", "#10:A4-SRC-3",
  "#10:A4-SRC-4", "#10:A4-SRC-5", "#7:DQ-ACT-5"]
target_commit: post-RP-006 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/rooms/source_refresh.py
  - custom_components/eufy_vacuum/dispatch/manager.py
  - custom_components/eufy_vacuum/jobs/phase_runner.py
  - custom_components/eufy_vacuum/__init__.py   # cache invalidation hook only
  - tests/
ordered_edits:
  - step: 1
    what: async_refresh_room_source returns {"ok": bool, "reason": str|None,
      "refreshed_at": iso}; cache entries stamped refreshed_at; get_cached_room_source
      exposes (data, age_s). Five exits become distinguishable (SRC-1).
  - step: 2
    what: flatten_maps_response keys collision-safely — when a computed key already
      exists, append "#flag{N}"/"#idx{N}" and WARN (SRC-3); single-map fallback in
      room_discovery UNCHANGED (its misuse is #10:A1-ID-2 — RF-25's packet).
  - step: 3
    what: in-flight coalescing — module-level per-entity asyncio.Lock + share the
      in-flight future; a response older than the newest committed refresh does not
      replace it (monotonic generation counter) (SRC-4).
  - step: 4
    what: cache invalidation on unload/per-vacuum teardown (pop the entity key) via
      the RP-003 ledger (SRC-5).
  - step: 5
    what: _resolve_live_dispatch_payload total-miss branch (dispatch/manager.py:317
      region) — REFUSE instead of returning the stale payload: raise
      HomeAssistantError("no target rooms resolved on the current map — the map may
      have been re-segmented; re-import rooms") for the job-start path. Partial-miss
      skip behaviour unchanged.
  - step: 6
    what: per-room phase dispatch (phase_runner.py:1019-1027) — catch that refusal for
      a ONE-room phase: log, mark the phase's room skipped (feeds RF-11's cumulative
      evidence later), advance to the next phase instead of wedging.
  - step: 7
    what: >
      (DECIDED per GATE4 Q16 — variant (a), packet UNBLOCKED) dispatch requires
      freshness — before rewriting segments, if the cache's refreshed_at is older
      than REFRESH_TTL (constant, 15 min) AND the refresh result was not ok, REFUSE.
      This includes the asleep/unreachable-Roborock cold-boot case: NO stored-id
      fallback, NO dispatch-to-wake. The refusal reason is user-visible and
      actionable: "the robot's live room data is unavailable — wake the robot (or
      wait for the Roborock integration to reconnect), then try again." Once a live
      refresh succeeds, resolve against the current map and dispatch normally.
      Reason routes through the card as a CODE per the RF-27 convention. TTL
      constant documented as operational, not empirical tuning.
  - step: 8
    what: DQ-ACT-5 — in _run_global_pre_calls, tag the mixed_mode_water_policy entry
      as safety-critical; if ITS call fails, abort the dispatch (raise) instead of
      logging; plain fan pre-calls stay best-effort.
forbidden_simplifications:
  - do not remove the stored-id payload path entirely (brands without
    resolve_live_ids_by_slug keep it)
  - the refusal string is user-facing: route through the i18n code convention if it
    reaches the card (coordinate with RF-27's code style — return reason codes)
reproduction:
  reproducer_script: NEW _proof_stale_dispatch.py — seed stored rooms with slugs A/B,
    live source with neither (total miss) and with only A (partial), assert wire
    payload per case
  expected_before:
    required_output_fragments: ["total miss dispatched stored ids"]
  expected_after:
    required_output_fragments: ["total miss refused", "partial miss skipped B"]
regression:
  tests_to_add: [total-miss refusal, per-room-phase skip-and-advance, freshness gate,
    collision keying, coalescing (two concurrent refreshes, one service call)]
hardware_validation: >
  tier 2 (HC-2, Ivy): needs Ivy awake; normal dispatch unchanged; then simulate the
  re-segment case by renaming a room in the vendor app and dispatching — expect the
  refusal, not a wrong-room clean. HARDWARE_BASELINE_GATE: Ivy dispatch-path BEFORE
  capture (the two cancelled jobs partially cover; one clean start/finish run wanted).
rollback_plan: git revert (three commits: source_refresh / dispatch refusal / pre-call)
stop_and_escalate_when:
  - any consumer of async_refresh_room_source's None return exists outside dispatch
    (grep first; report)
  - Ivy hardware shows the app_segment_clean silently ignoring the refusal path's
    absence (i.e. device-side behaviour differs) — report capture
```

---

## RP-008 — Blocker rules: unavailable is indeterminate, and edges are deduped

```yaml
packet_id: RP-008
title: a sensor dropout can no longer pause/cancel a live run
repair_family: RF-13
goal: GUARD-1 CRITICAL closed; blocker evaluation is three-valued with hold-previous
findings_addressed: ["#12:A6-GUARD-1", "#12:A6-GUARD-2"]
findings_not_closed: [other RF-13 members (RP-031/RP-035 batches);
  GUARD-4 reaper overlap (RP-011)]
target_commit: post-RP-007 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/rooms/access_graph.py
  - custom_components/eufy_vacuum/listeners/path_blockers.py
  - custom_components/eufy_vacuum/planning/run_plan.py
  - tests/
ordered_edits:
  - step: 1
    what: >
      AccessGraphManager._room_rule_matches (access_graph.py:907 region): when the
      rule entity's state is in BLANK_STATE_VALUES (or the State is None), return
      INDETERMINATE (new tri-state, or a (matched, known) tuple). Negating operators
      (not_equals, not_in) and `missing` MUST NOT match on INDETERMINATE.
  - step: 2
    what: >
      the runtime report (run_plan.py:1529+ region) treats INDETERMINATE as
      HOLD-PREVIOUS: a room currently blocked stays blocked; a room currently clear
      stays clear; the report carries "indeterminate_rules": [...] for diagnostics.
      Rationale pinned: treat-as-unmatched would UNPAUSE a genuinely-blocked run on
      dropout; treat-as-matched is GUARD-1's bug inverted.
  - step: 3
    what: path_blockers._handle_path_blocker_change — ignore transitions where either
      side is unavailable/unknown for RULE EVALUATION purposes (the state change
      still logs at DEBUG); plus a per-vacuum in-flight guard on _process (single
      concurrent evaluation; a queued re-check runs after) closing GUARD-2's
      unbounded spawn.
  - step: 4
    what: the pause/cancel ACTION path re-checks that the triggering rule still
      matches with a KNOWN state before calling async_cancel_active_job (defense in
      depth; cancel single-flight itself is RP-010).
reproduction:
  reproducer_script: NEW _proof_blocker_unavailable.py — state-machine fixture:
    blocker sensor open→unavailable during a started job with a not_equals rule;
    assert no cancel; then genuine open→closed asserts cancel fires once with two
    rapid events.
  expected_before:
    required_output_fragments: ["cancel fired on unavailable"]
  expected_after:
    required_output_fragments: ["unavailable held previous verdict", "single cancel on real edge"]
regression:
  tests_to_add: [negating operators vs unavailable, hold-previous both directions,
    concurrent _process single-flight]
hardware_validation: tier 2 optional ride-along (HC-2, Alfred): flip a blocker helper
  to unavailable mid-run; expect no pause/cancel; log carries indeterminate note.
rollback_plan: git revert
stop_and_escalate_when:
  - any shipped rule semantics DEPEND on matching unavailable (grep docs + Chris's
    own automations — ask Chris; his install uses blocker rules)
```

---

## RP-009 — Entity ownership without prefix matching

```yaml
packet_id: RP-009
title: room-sync sweeps and the map-delete sweep stop matching by string prefix
repair_family: RF-04
goal: DR-SETUP-1's proven cross-vacuum registry deletion becomes impossible; EP-2's
  maintenance-entity destruction becomes impossible
findings_addressed: ["direct read:DR-SETUP-1", "#14:A2-CB-1",
  "agent: sensor (2-lens verified):SN-3", "agent: platforms (2-lens verified):EP-2",
  "direct read:DR-SENS-2", "#14:A2-CB-5",
  "agent: sensor (2-lens verified):SN-7"]
findings_not_closed: ["agent: infra (2-lens verified):INF-5" → document_only rider in
  this packet (docstring: non-injective join, no parser, no consumer parses)]
target_commit: post-RP-008 master
files_allowed_to_change:
  - custom_components/eufy_vacuum/entity_helpers.py
  - custom_components/eufy_vacuum/switch.py
  - custom_components/eufy_vacuum/number.py
  - custom_components/eufy_vacuum/sensor/__init__.py
  - custom_components/eufy_vacuum/setup/delete.py
  - tests/
symbols_to_add:
  - entity_helpers.unique_ids_for_map(vacuum_entity_id, map_id, room_ids, suffixes)
  - entity_helpers.entity_belongs_to(entity, vacuum_entity_id, map_id)
  - sensor.__init__._sync_dynamic_entities (shared sync used by both 40-line twins)
symbols_to_modify: [switch._on_rooms_updated sweep (:71-83), number sweep (:101),
  sensor sweeps (:255, :312), setup/delete registry sweep (:136)]
ordered_edits:
  - step: 1
    what: >
      (AMENDED per REVIEW D2) entity_helpers gains the two functions BESIDE
      make_room_unique_id (builder and matcher in one module — doc-32 corollary;
      docstring carries the question + the drift: five prefix scans, one proven
      cross-vacuum deletion). Ownership attributes VERIFIED AT SOURCE:
      EufyVacuumRoomEntity.__init__ sets _vacuum_entity_id/_map_id
      (room_entities.py:35-36) and the platform room entities inherit. They are
      PRIVATE — add two read-only @property accessors (vacuum_entity_id, map_id) on
      the shared base entity and have entity_belongs_to consume the PROPERTIES; do
      NOT reach for the underscore attrs from entity_helpers. Where an entity class
      lacks map_id, ADD it at construction (all are built with it in scope); never
      fall back to prefix.
  - step: 2
    what: switch/number/sensor sweeps classify stale via entity_belongs_to + absence
      from desired — never by unique_id string. number.py's sweep additionally
      restricts to ROOM entities (its entity_map mixes maintenance numbers — EP-2).
  - step: 3
    what: the two byte-identical sensor sync blocks (:250-350 region) fold into
      _sync_dynamic_entities(entity_dict, desired_builder, refresh_helper)
      (DR-SENS-2); the shared helper routes state writes through
      _request_entity_state_write (closing A2-CB-5's unguarded-write asymmetry and
      SN-7's inconsistency by making the funnel the single documented convention —
      docstring states the thread-model decision).
  - step: 4
    what: >
      (AMENDED per REVIEW D3) setup/delete.py sweep — replace prefix matching with
      the CLOSED SET: unique_ids_for_map(vac, map_id, room_ids=stored rooms of the
      map being deleted, suffixes=ALL room-entity suffixes) ∪ the map-scoped
      singleton ids; remove EXACTLY the registry entries whose unique_id is in that
      set. Registry entries the old prefix scan would have matched but the closed
      set does not (pre-fix orphans: rooms removed before this repair, older id
      schemes) are ENUMERATED AND REPORTED in the service result
      (orphan_candidates: [...]) and NOT deleted — never delete what cannot be
      re-derived. Orphan cleanup policy is Chris's Q15.
forbidden_simplifications:
  - NO unique_id format change, NO registry migration (explicit §G decision — the
    spec example's migration half is rejected as unnecessary risk)
  - no startswith anywhere in the touched sweeps after this packet (grep-assertable)
reproduction:
  reproducer_script: attach .claude/notes/_proof_setup.py (DR-SETUP-1's proven
    harness — vacuum.alfred + vacuum.alfred_2, map 2 delete) + extend with EP-2's
    maintenance-number case
  expected_before:
    asserted_values: sibling entity registry entries removed == 8
    required_output_fragments: ["removed vacuum_alfred_2_"]
  expected_after:
    asserted_values: sibling removals == 0; only the deleted map's ids removed
    forbidden_output_fragments: ["removed vacuum_alfred_2_"]
regression:
  tests_to_add: [two-vacuum prefix-subset fixture across all four sweeps;
    maintenance entities survive room sync; closed-set delete exactness;
    shared sync helper parity test]
hardware_validation: tier 1 (HC-1): live entity list before/after a room edit and a
  map delete — user customizations intact.
rollback_plan: git revert (entity_helpers additions are additive)
stop_and_escalate_when:
  - any entity class cannot carry map_id at construction (report which)
  - registry entries exist whose unique_id is NOT reconstructible from stored rooms
    (orphans from older versions) — report count; a separate cleanup decision goes
    to Chris (do not delete unknowns)
```
