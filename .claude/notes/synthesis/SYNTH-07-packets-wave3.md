# Tranche-2 Packets — Wave 3: identity & stores (RP-015..RP-020)

Conventions per SYNTH-06 header. Sequencing (REVIEW-03): RP-015 (incl. its Q4
migration) → RP-018; RP-016 → RP-017; RP-013c → RP-020.

---

## RP-015 — Slug uniqueness at the admission boundary + Q4 dedupe migration (RF-24)

```yaml
packet_id: RP-015
family_id: RF-24
finding_ids: ["#10:A1-ID-1", "#10:A2-REC-2", "#10:A1-ID-3", "#11:A6-TRK-5"]
files: [custom_components/eufy_vacuum/rooms/room_discovery.py,
  custom_components/eufy_vacuum/rooms/utils.py,
  custom_components/eufy_vacuum/mapping/tracker.py,
  custom_components/eufy_vacuum/core/manager.py, tests/]
symbols: [discover_rooms_for_vacuum slug emit, slugify_room_name, _norm_room_name,
  NEW startup migration _dedupe_stored_slugs]
problem: slugify has no uniqueness guarantee (docstring claims it) — two same-name
  rooms share a slug; on Roborock the second dispatches the FIRST's segment
  (CRITICAL); reconciliation collapses the two identities and migrate overwrites one
  room's settings with the other's (CRITICAL); an all-quote name slugifies to "" and
  passes; the tracker normalizes names DIFFERENTLY from slugify (merges identities
  rooms/ keeps distinct). D5 (review): STORED rooms may already hold duplicates —
  slug-led carry (RP-018) over such a store reintroduces REC-2.
required_behavior: >
  (1) discovery emit: after building the room list, deterministically disambiguate
  colliding slugs — unsuffixed slug stays with the LOWEST stable room_id; every
  colliding sibling gets `{slug}_r{room_id}` (Q4 verbatim). A slug that strips to
  empty is refused at discovery (room skipped with a WARNING naming the raw name).
  (2) Q4 STORED-SLUG DEDUPE MIGRATION (runs once at manager init, before any carry):
  scan every map's stored rooms; apply the SAME rule; write a manifest entry per
  change {map_id, room_id, old_slug, new_slug, reason: duplicate_slug_migration}
  persisted under data["migrations"]["slug_dedupe"]; idempotent (no-op when no
  duplicates); collision behaviour: rule is deterministic so re-runs converge;
  partial failure: the scan is in-memory then one save (all-or-nothing); ROLLBACK
  restores old_slug FROM THE MANIFEST — never strip-suffix inference (Q4).
  Slug-keyed learning stores are NOT rewritten (a collided room's history was
  already misattributed — the suffixed room starts fresh, per the accepted design);
  the manifest records this consequence.
  (3) TRK-5: tracker adopts slugify_room_name (with NFC) — _norm_room_name deleted.
allowed_changes: listed + tests
prohibited_changes: no suffixing of non-colliding rooms (Q4); no learning-store
  rewrite; slugify's transform rules for non-colliding inputs unchanged.
compatibility_constraints: entity names/ids for COLLIDED rooms change (suffixed) —
  release-note item; MIGRATION_INSPECTION_GATE: before/after dumps of one duplicate
  fixture + the manifest, approver main agent.
migration_plan: as (2). rollback_plan: 2 commits — (a) admission uniqueness +
  tracker adoption, (b) the stored dedupe migration. Revert (b) alone restores
  stored slugs via manifest replay (script in packet appendix).
reproducer_script: NEW _proof_slug_collision.py — two "Bathroom" rooms: before →
  same slug, dispatch resolves first's segment for both, reconciliation phantom
  id_changed; after → bathroom + bathroom_r7, distinct dispatch, no phantom.
expected_before: ["both rooms slug=bathroom", "second dispatched first's segment"]
expected_after: ["bathroom + bathroom_r7", "distinct segments", "manifest 1 entry"]
validity_notes: drive dispatch through the REAL slug_to_live_id first-wins builder.
tests_to_add_or_modify: collision determinism; empty-slug refusal; migration
  idempotence + manifest + rollback replay; tracker/slugify parity.
superseded_tests: any test pinning _norm_room_name's separator folding.
broader_gates: full suite. hardware_gate: none (SOURCE_DECIDABLE + fixtures).
stop_conditions: [any consumer keys on slug BY POSITION such that suffixing breaks
  it (grep first: learning keys map_id::slug tolerate new slugs)]
escalation_target: main agent → Chris
```

---

## RP-016 — Referential integrity: the per-map store registry + rename/delete scans (RF-20)

```yaml
packet_id: RP-016
family_id: RF-20
finding_ids: ["#10:A3-CRUD-4", "#8:A3-PP-CRUD-3", "#13:A3-ROOMS-8",
  "#18:A6-ZONE-C-2", "#18:A4-CUSTOM-5", "#18:A3-IMAGE--6", "#18:A6-ZONE-C-5",
  "#16:A3-IO-6"]
files: [custom_components/eufy_vacuum/maps/map_manager.py,
  custom_components/eufy_vacuum/rooms/room_crud.py,
  custom_components/eufy_vacuum/profiles/manager.py,
  custom_components/eufy_vacuum/mapping/mapping_services.py,
  custom_components/eufy_vacuum/learning/history_store.py, tests/]
symbols: [NEW maps.map_manager.PER_MAP_STORES, remove_map, rename_room_profile,
  delete_room_profile, _handle_delete_saved_zone, _generate_saved_zone_id,
  _handle_delete_map_image, _handle_delete_custom_layout, get_paths]
problem: remove_map leaves run-profile library, queue state and onboarding state
  behind — re-import with the same map_id resurrects profiles holding room ids from
  the DELETED segmentation (CRITICAL); profile rename/delete orphans referring rooms
  silently; saved-zone delete leaves queue/profile zone steps dead-but-listed;
  zone/layout ids reuse after delete while durably referenced; image delete sweeps no
  back-references; layout create/delete strands segmentation_mode; renaming the
  vacuum entity silently orphans the learning archive.
required_behavior: >
  (1) PER_MAP_STORES: one enumeration in maps/map_manager.py (docstring lists every
  per-(vacuum,map) bucket + its owner) consumed by remove_map — which now clears ALL
  of them (run_profiles, queue, onboarding join the existing five). RP-017's
  id-remap walker consumes the SAME registry.
  (2) rename/delete_room_profile scan data["maps"][*][*]["rooms"] for referrers:
  rename REPOINTS them; delete refuses when referrers exist unless force=True
  (response lists the rooms) — per Q9, ServiceValidationError on refused force-less
  delete with referrer count.
  (3) delete_saved_zone scans queue breaks + run-profile zone steps; response carries
  referencing_steps; deletion proceeds but the steps are PRUNED in the same write
  (silent dead ids end).
  (4) zone/layout id generators include a persisted monotonic counter so ids never
  reuse after delete (CUSTOM-5).
  (5) delete_map_image sweeps layout backdrop/art variant references (mirror
  upload's layout-awareness); ZONE-C-5: create records prior mode, delete restores it.
  (6) IO-6 interim: get_paths detects an existing sibling archive dir whose slug
  matches the entity's PREVIOUS object_id (registry lookup) and WARNS loudly with
  the rename-detected message; NO directory migration (DEF-5 stands).
allowed_changes: listed + tests
prohibited_changes: no archive directory migration; no card changes (prune results
  surface via existing lists).
compatibility_constraints: delete_room_profile gains refusal semantics (Q9 class:
  destructive-config → raise); release-note item.
migration_plan: none beyond (4)'s counter seed (max existing ordinal).
rollback_plan: 3 commits — (a) registry + remove_map, (b) profile/zone referential
  scans, (c) image/layout/IO-6. (b)+(c) both touch mapping_services.py — (b) first.
reproducer_script: NEW _proof_referential.py — remove_map → re-import: before →
  resurrected profiles with dead room ids; after → clean slate. Rename profile →
  rooms repointed.
expected_before: ["resurrected run profile with dead ids", "orphaned profile_name"]
expected_after: ["all per-map stores cleared", "referrers repointed"]
tests_to_add_or_modify: registry completeness test (asserts every setdefault-keyed
  per-map bucket in the codebase is registered — grep-driven fixture, the
  declaration-proving pattern); scan/prune matrices; counter no-reuse.
superseded_tests: tests pinning remove_map's five-bucket scope.
broader_gates: full suite. hardware_gate: none (SOURCE_DECIDABLE).
stop_conditions: [a per-map bucket exists that the registry test finds but whose
  owner objects to clearing on remove_map — escalate with the bucket name]
escalation_target: main agent → Chris
```

---

## RP-017 — Id-remap coverage + CV-overlay invalidation (RF-25a)

```yaml
packet_id: RP-017
family_id: RF-25
finding_ids: ["#16:A4-STATE-3", "#18:A5-FURNIS-4", "#18:A2-POLYGO-5",
  "#18:A4-CUSTOM-6", "#18:A3-IMAGE--1", "#18:A3-IMAGE--4", "direct read:DR-ONB-1",
  "direct read:DR-ONB-2"]
files: [custom_components/eufy_vacuum/rooms/room_crud.py,
  custom_components/eufy_vacuum/learning/job_finalizer.py,
  custom_components/eufy_vacuum/mapping/mapping_services.py,
  custom_components/eufy_vacuum/onboarding/manager.py, tests/]
symbols: [id_remap walker (room_crud), _update_trouble_rooms_log keying,
  area_label_anchors, image_segment_adjustments, segment_room_links,
  remap_confirmed_floor_types, check_for_new_rooms]
problem: id-keyed sidecar stores are never remapped on re-segment (trouble_rooms —
  the one store the reconcile-migrate walker forgets; label anchors re-aim onto
  different rooms); CV overlays (adjustments, room links) key on per-run ordinal
  segment ids that re-analysis recycles — a nudge authored for one room re-attaches
  to whichever segment inherits the id; re-upload doesn't invalidate segments; the
  confirmed-floor remap corrupts itself on overlapping id sets (PROVEN: {1:2,2:3,3:4}
  loses 2 of 3); new-room check compares per-map stored vs unscoped live.
required_behavior: >
  (1) the id_remap walker iterates RP-016's PER_MAP_STORES entries that declare
  id-keyed sub-maps (registry entries gain a keying descriptor) — trouble_rooms and
  area_label_anchors join; trouble_rooms additionally becomes map-scoped going
  forward (new records keyed map_id::room_id; reader accepts both forms — additive).
  (2) CV overlays: re-analysis and re-upload INVALIDATE image_segment_adjustments +
  segment_room_links for that map (cleared with an INFO log listing counts) — ids
  are per-run ordinals, remap is impossible (honest invalidation, not fabricated
  stability; catalogue pin).
  (3) DR-ONB-1: remap builds into a NEW dict (two-dict algorithm), swap at end.
  (4) DR-ONB-2: check_for_new_rooms compares only when the queried map is the
  active map (else returns indeterminate) — matching its per-map stored side.
allowed_changes: listed + tests
prohibited_changes: no geometry-fingerprint re-keying of CV overlays in this packet
  (a future feature; do not foreclose, do not build).
compatibility_constraints: trouble_rooms dual-form keys — reader tolerance test.
migration_plan: none (dual-read; old bare keys age out via Q6's rebuilder in RP-020).
rollback_plan: 2 commits — (a) walker + stores, (b) CV invalidation + ONB fixes.
reproducer_script: NEW _proof_id_remap.py — renumber remap {1:2,2:3,3:4}: before →
  floor confirmations lost, anchors re-aimed, trouble counters transplanted; after →
  all follow the remap; CV re-analysis clears overlays with counts.
expected_before: ["confirmations lost: 2 of 3", "trouble counters on wrong room"]
expected_after: ["remap complete, nothing lost", "overlays invalidated: adjustments=2 links=3"]
tests_to_add_or_modify: overlapping/swap remaps; dual-form trouble keys; invalidation
  on both re-analysis and re-upload; active-map gate for new-room check.
superseded_tests: disjoint-remap-only fixtures (add overlap cases; keep originals).
broader_gates: full suite. hardware_gate: none.
stop_conditions: [any OTHER id-keyed sidecar found during the registry sweep —
  add it, report it]
escalation_target: main agent → Chris
```

---

## RP-018 — Slug-led carry + Q5 enablement semantics (RF-25b) — blocked_by RP-015

```yaml
packet_id: RP-018
family_id: RF-25
finding_ids: ["#10:A2-REC-8", "#10:A3-CRUD-2", "#10:A3-CRUD-3", "#7:DQ-Q-5",
  "#10:A3-CRUD-6", "#10:A3-CRUD-5"]
files: [custom_components/eufy_vacuum/rooms/room_manager.py,
  custom_components/eufy_vacuum/maps/map_manager.py,
  custom_components/eufy_vacuum/rooms/room_crud.py, tests/]
symbols: [build_managed_rooms, rebuild_map_bucket]
problem: the reachable room writers carry settings by NUMERIC id — a re-segment
  renumber transplants floor type, access grants, rules and dock flag onto different
  physical rooms; save auto-confirms floor types (permanently satisfying the
  onboarding gate with guessed "hardwood"); both writers auto-enable+auto-approve
  rooms the user never saw; rejected rooms resurrect.
required_behavior: >
  (1) carry-over becomes SLUG-LED with id fallback: match stored room by slug first
  (unique post-RP-015), by id only when no slug matches; identical outcome when ids
  and slugs agree (the compat case), divergence only in the renumber case being
  fixed.
  (2) Q5 verbatim: FIRST import of a map enables all discovered rooms; incremental
  discovery adds genuinely-new rooms DISABLED and unconfirmed; never silently into
  an existing queue. First-import detection: the map bucket had no rooms before this
  write.
  (3) floor-type confirmation only for rooms whose floor_types entry was SUPPLIED
  (CRUD-3); rebuild parity: both writers answer confirmation identically.
  (4) build_managed_rooms consults rejected_rooms (CRUD-5).
blocked_by: RP-015 INCLUDING its dedupe migration (D5 — slug-led carry over
  duplicate slugs would collapse identities).
compatibility_constraints: HIGH-visibility (how every room edit persists); staged
  per REVIEW: this packet is stage (b)+(c) of RF-25; release-note item.
migration_plan: none (carry logic only; storage untransformed — revert restores
  id-led carry).
rollback_plan: 2 commits — (a) slug-led carry, (b) enable/confirm semantics.
reproducer_script: NEW _proof_slug_carry.py — renumber fixture (Kitchen 16→21,
  Bedroom takes 16): before → Bedroom inherits Kitchen's grants/dock flag; after →
  Kitchen's settings follow Kitchen; new room arrives disabled.
expected_before: ["transplanted grants onto wrong room", "unseen room enabled"]
expected_after: ["settings follow slug", "new room disabled+unconfirmed",
  "first import enables all"]
tests_to_add_or_modify: carry matrix (stable / renumber / rename+renumber with
  RP-015 slugs); Q5 both modes; confirmation-supplied-only; rejected filter.
superseded_tests: id-led carry pins (room_manager tests) — docstrings record Q5/D5.
broader_gates: full suite.
hardware_gate: >
  closure for the carry (b) requires ONE REAL Ivy re-map capture (REVIEW pin):
  rename/merge a room in the Roborock app, re-import, verify settings followed
  slugs. HARDWARE_BASELINE_GATE, Chris's session; fixtures close the rest.
stop_conditions: [any consumer proves dependent on id-led transplant]
escalation_target: main agent → Chris
```

---

## RP-019 — Reconciliation becomes reachable and reviewable (RF-25c)

```yaml
packet_id: RP-019
family_id: RF-25
finding_ids: ["#10:A2-REC-1", "#10:A2-REC-5", "#10:A2-REC-3", "#10:A2-REC-6",
  "#10:A2-REC-7", "#10:A1-ID-2", "#10:A1-ID-4", "#12:A6-GUARD-5"]
files: [custom_components/eufy_vacuum/rooms/room_crud.py,
  custom_components/eufy_vacuum/rooms/reconciliation.py,
  custom_components/eufy_vacuum/services/rooms.py,
  custom_components/eufy_vacuum/rooms/room_discovery.py,
  custom_components/eufy_vacuum/setup/drift.py, tests/]
symbols: [discover_rooms, reconcile_room, compute_reconciliation, plan_migration,
  discover_rooms_for_vacuum single-map fallback, update_drift_history,
  _list_configured_room_ids]
problem: the slug-aware migration path is unreachable from the product (no card
  wiring, no trigger); migrate applies a plan the user never saw (cache can change
  between review and confirm); rename+renumber in one edit is invisible; renames
  orphan slug-keyed learning; dismissals never consulted; the single-map fallback
  serves ANOTHER map's rooms relabeled with the requested id; drift is map-unscoped
  (inactive maps decay toward removed; map switches accrue false strikes).
required_behavior: >
  (1) discover_rooms' response embeds the reviews + a plan_token (hash of the
  reviews + discovery snapshot); reconcile_room REQUIRES the token and refuses on
  mismatch ("plan_changed — re-discover") (REC-5). Card wiring is the NAMED
  downstream consumer (CARD-RECON packet stub in SYNTH-10) — backend makes it
  wireable now.
  (2) with RP-015's unique slugs, compute_reconciliation pairs rename+renumber via
  slug-set diff + id continuity (REC-3). (AMENDED per REVIEW-07 T2-D4) REC-6's
  rename repair uses a persisted `slug_aliases` map (old→new per map): ARCHIVES
  carry the old slug, so any rebuild regenerates old-slug keys — a dict-walker
  remap is structurally insufficient. The stats rebuilder folds aliased keys and
  the estimator's room-match lookups consult the alias map; archives are NOT
  rewritten (rejected: heavy, destructive). Files add learning/stats_rebuilder.py
  + learning/estimator.py to files_allowed for this half.
  (3) dismissals: compute_reconciliation takes dismissed_at and suppresses
  identical reviews until the discovery snapshot changes (REC-7).
  (4) ID-2: the single-map fallback requires the cached map key to MATCH the
  requested map_id (else no rooms + reason) — no relabeling.
  (5) drift map-scoping: run_discovery_pass passes the active map_id through;
  history keys gain the map component (dual-read); _list_configured_room_ids scopes
  to that map (ID-4/GUARD-5).
compatibility_constraints: reconcile_room gains a required token — Q9 class:
  destructive-config → ServiceValidationError without it; release notes + docs.
migration_plan: drift history dual-form keys, additive.
rollback_plan: 3 commits — (a) token contract, (b) pairing + slug_remap,
  (c) fallback + drift scoping.
reproducer_script: NEW _proof_reconciliation.py — review/confirm with a cache swap
  between (before: applies the swapped plan; after: refuses plan_changed);
  rename+renumber pairing; wrong-map fallback refusal.
expected_before: ["migrate applied unseen plan", "renamed+renumbered room deleted",
  "other map's rooms relabeled"]
expected_after: ["plan_changed refusal", "paired rename+renumber review",
  "fallback refused wrong map"]
tests_to_add_or_modify: token round-trip; pairing matrix; dismissal suppression;
  fallback map-match; drift dual-form + scoping.
superseded_tests: drift unscoped-union tests — update with map-scoping rationale.
broader_gates: full suite. hardware_gate: rides RP-018's Ivy re-map session (same
  capture validates pairing on real renumber data).
stop_conditions: [token hashing pulls in non-deterministic fields]
escalation_target: main agent → Chris
```

---

## RP-020 — Learning stores: full rebuild reach + Q6 rebuilder + claim-block hygiene (RF-22)

```yaml
packet_id: RP-020
family_id: RF-22
finding_ids: ["#16:A5-SVC-1", "#16:A5-SVC-5", "#16:A5-SVC-8", "#16:A4-STATE-5",
  "#16:A4-STATE-3", "#16:A4-STATE-4", "#16:A4-STATE-9"]
files: [custom_components/eufy_vacuum/learning/services.py,
  custom_components/eufy_vacuum/learning/manager.py,
  custom_components/eufy_vacuum/learning/history_store.py,
  custom_components/eufy_vacuum/learning/job_finalizer.py,
  custom_components/eufy_vacuum/core/manager.py, tests/]
symbols: [handle_exclude_learning_job, handle_restore_learning_job,
  async_rebuild_learning_accumulators, NEW rebuild_trouble_rooms,
  incomplete_run map-scoping, NEW clear_incomplete_run service,
  async_finalize_completed_job claim block]
problem: exclude/restore rebuild only the four derived files — the poison stays in
  accuracy_stats/learned_zones/battery aggregates (the seam comment says the
  opposite); the service accuracy write skips cache invalidation its four siblings
  perform; invalidate-then-preload races an in-flight preload; trouble_rooms has no
  rebuilder and Q6 ACCEPTS adding one (denominator freezes when unqueued —
  disproven self-heal); incomplete_run/trouble_rooms are map-unscoped and the card
  applies missed ids to whatever map is active; banner dismissal is client-only.
required_behavior: >
  (1) exclude/restore call async_rebuild_learning_accumulators (SVC-1); the seam
  comment becomes true.
  (2) SVC-5: the service accuracy write invalidates+preloads like its siblings;
  SVC-8: preload gains a generation counter — an invalidate bumps it and a landing
  stale load with an old generation is discarded.
  (3) Q6: rebuild_trouble_rooms from archived job evidence, MAP-SCOPED (writes the
  map_id::room_id form from RP-017), joins async_rebuild_learning_accumulators;
  live finalize path unchanged.
  (4) STATE-4 backend: the incomplete_run payload's map_id becomes load-bearing —
  the retry service refuses when log.map_id != active map (card half NAMED:
  retryMissedRooms must pass/compare map_id — CARD-RECON stub, CF-consumer list).
  (5) STATE-9: expose clear_incomplete_run service so dismissal can be durable
  (card wires later; registered + unregistered symmetrically per RF-16 lesson).
  (6) Lesson-6 owner — claim-block hygiene: in async_finalize_completed_job, the
  `if _stored_job is not None:` block gains its explicit else (returns the Q1
  no_active_job_record refusal) so the invariant is LOCAL to the claim block, not
  dependent on the entry guard staying upstream. Behaviour identical post-Q1;
  structure closes HW-FINAL-1's recorded side-hole.
blocked_by: RP-013c (record shape), RP-017 (map-scoped key form).
rollback_plan: 3 commits — (a) accumulator reach + cache coherence, (b) Q6 rebuilder
  + map scoping + clear service, (c) claim-block else. (a)+(b) share
  learning/services.py — (a) first.
reproducer_script: NEW _proof_rebuild_reach.py — poisoned accuracy sample; exclude:
  before → poison persists in accuracy_stats; after → gone; trouble_rooms rebuilt
  map-scoped from archives.
expected_before: ["poison survived exclude", "trouble_rooms bare-key frozen"]
expected_after: ["accumulators rebuilt clean", "trouble_rooms rebuilt map-scoped"]
tests_to_add_or_modify: accumulator reach matrix; generation-counter race; rebuilder
  parity vs live path; retry map-refusal; else-branch refusal.
superseded_tests: the seam-comment test asserting exclude's old scope, if pinned.
broader_gates: full suite. hardware_gate: none (fixtures; archives are the corpus).
stop_conditions: [rebuilder and live path disagree on any fixture's counters —
  stop, reconcile before landing]
escalation_target: main agent → Chris
```
