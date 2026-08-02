# Tranche-2 Packets — Wave 5: mapping (RP-026..RP-030)

Conventions per SYNTH-06 header. Sequencing: RP-026 → RP-027 (same files);
RP-028 → RP-029 (same file); RP-030 last (small batch over the settled base).

---

## RP-026 — Every map/pose read bound to (device, map, content) (RF-09; Q13 closure rules)

```yaml
packet_id: RP-026
family_id: RF-09
finding_ids: ["#11:A1-LC-1", "#11:A3-EXT-1", "#11:A4-RB-2", "#11:A4-RB-1",
  "#11:A1-LC-3", "#11:A1-LC-5", "#11:A4-RB-3", "#11:A3-EXT-2", "#18:A7-ROBORO-3",
  "#11:A4-RB-4", "#11:A4-RB-5", "#11:A4-RB-6",
  "agent: sensor (2-lens verified):SN-5"]
files: [custom_components/eufy_vacuum/mapping/map_source_runtime.py,
  custom_components/eufy_vacuum/mapping/map_source_coordinator.py,
  custom_components/eufy_vacuum/mapping/roborock_raw_map.py,
  custom_components/eufy_vacuum/sensor/map_overlays.py, tests/]
symbols: [eufy_inmem_candidates, eufy_mapdata_obj_from_candidates,
  roborock_candidates, find_mapdata, roborock_result_from_candidates,
  _refresh_storage_map_source mtime cache, _commit_result,
  roborock_geometry_drift_from_candidates, map_overlays._result]
problem: the Eufy in-memory candidate walk takes NO vacuum identity (first
  coordinator wins — a second Eufy robot is served the first's map/rooms/pose);
  the Roborock walk takes no device and never binds the found map to the requested
  map_id (multi-floor zone conversion in the wrong frame); the storage mtime cache
  omits the map_id check its sibling performs; commits are last-writer-wins across
  awaits; one duck-typed false positive permanently blanks the source; the content
  version hashes ONLY the raster while the cache carries mutable geometry (and the
  roborock payload ships unhashed room_names); the overlays sensor ignores the
  cache's map_id.
required_behavior: >
  VERIFY-FIRST GATE (before Sonnet assignment, main agent): confirm on the LIVE
  fork version that EufyCleanCoordinator carries device_id and that the vacuum
  entity's device-registry entry yields a deterministic key to select it. If no
  deterministic linkage exists, the EUFY half returns to synthesis (fork-PR
  option); the Roborock half proceeds regardless.

  >>> GATE CLEARED 2026-08-01 (main agent, against the live install). BOTH halves
  >>> hold; the EUFY half PROCEEDS and no fork PR is needed.
  >>>
  >>> (1) device_id EXISTS. Fork `robovac_mqtt` **1.13.1**
  >>>     (github.com/jeppesens/eufy-clean), `coordinator.py:73`
  >>>     `class EufyCleanCoordinator(DataUpdateCoordinator[VacuumState])`,
  >>>     `coordinator.py:85` `self.device_id = device_info["deviceId"]`. Set
  >>>     unconditionally in __init__ from a REQUIRED key (a missing deviceId
  >>>     raises KeyError at construction), so it is never absent on a live
  >>>     coordinator. Used at 16+ sites including the store keys and dispatcher
  >>>     signals.
  >>>
  >>> (2) THE LINKAGE IS DETERMINISTIC, and it is the device registry itself.
  >>>     `coordinator.py:200` publishes `identifiers={(DOMAIN, self.device_id)}`
  >>>     with DOMAIN="robovac_mqtt". Verified end to end on the live install:
  >>>       vacuum.alfred (platform robovac_mqtt)
  >>>         -> entity_registry.device_id
  >>>         -> device_registry identifiers [("robovac_mqtt", "AFC96X0F33201054")]
  >>>     and "AFC96X0F33201054" IS the coordinator's device_id. So the selection
  >>>     key is: read the vacuum entity's device, take the identifier tuple whose
  >>>     domain is the fork's, and match its value against coordinator.device_id.
  >>>     No name matching, no ordering assumption, no prefix heuristic.
  >>>
  >>> (3) GENERALIZES TO ROBOROCK, which the packet did not assume. The same
  >>>     shape holds: vacuum.ivy -> [("roborock", "57R4LhSyBB7y24BiKWWGiI")].
  >>>     Prefer the one identity mechanism for both halves rather than a
  >>>     Eufy-specific lookup plus a separate Roborock one — the question is
  >>>     "which device is this entity?", and it has one answer.
  >>>
  >>> Consequence: the 4 sub-findings gated here are UNBLOCKED. The
  >>> single-coordinator unconditional-select fallback in (1) below still stands
  >>> as the degradation path, but it is now a fallback rather than the primary.
  (1) (AMENDED per REVIEW-07 T2-D3) eufy_inmem_candidates takes vacuum_entity_id;
  when a root holds exactly ONE coordinator, select it unconditionally (DEBUG
  note — preserves today's working single-device behaviour even if linkage
  fails to resolve); when MULTIPLE coordinators exist, select by device_id match
  and return absent (present:false, reason device_not_found) on no-match — never
  first-wins (LC-1/EXT-1).
  (2) roborock_candidates prefers the per-vacuum image-entity root at EVERY call
  site (the two sites that skip it gain it), else duid-filtered entry roots
  (RB-2); find_mapdata takes the requested map identity and matches the flag-keyed
  maps dict when present (RB-1).
  (3) LC-3: the mtime early-return adds the map_id equality check (mirror
  _commit_result's); LC-5: _commit_result gains a per-vacuum generation counter —
  an older-generation commit is discarded with a DEBUG note.
  (4) RB-3: rejected candidates CONTINUE the walk instead of hard-returning.
  (5) EXT-2/ROBORO-3 (the rule, not a shared helper): each source's version hash
  covers EVERYTHING its payload/cache serves — Eufy adds the geometry fields;
  roborock_render_data folds room_names into the hash input.
  (6) RB-4: the roborock room payload carries map identity + a room-set stamp;
  RB-5: drift pairs MapData/MapContent only when both resolve from the same root
  object (else absent+reason); RB-6: image_entity_object logs its three None
  paths at DEBUG once.
  (7) SN-5: map_overlays._result checks the cache entry's map_id (and surfaces
  the stale flag for RP-027's contract).
closure_rules_q13: multi-Eufy closure = SOURCE_DECIDABLE_GATE (line-cited
  selection logic) + single-device regression on Alfred (behaviour unchanged) —
  the multi-device hardware proof stays OPEN (recorded unsatisfied; future
  hardware/tester; NO fabricated closure).
compatibility_constraints: two-robot Roborock accounts change served data (to the
  correct robot) — release notes.
rollback_plan: 4 commits — (a) Eufy device selection, (b) Roborock scoping +
  binding + walk fixes, (c) cache identity (mtime/generation), (d) version-hash
  inputs + payload stamps + sensor check. (a)-(d) share map_source files: strict
  order, rebases (lesson 4).
reproducer_script: NEW _proof_map_identity.py — two fake coordinators with
  distinct device_ids/rasters: before → both vacuums served coordinator[0]'s
  raster; after → each its own, no-match absent; geometry mutation with identical
  raster: before → stale cache served; after → version miss.
expected_before: ["vacuum B served A's map", "geometry change not invalidated"]
expected_after: ["per-device selection", "device_not_found absent", "version
  covers geometry", "older generation discarded"]
validity_notes: fixtures model the fork's REAL shapes (hass.data domain bucket →
  entry → coordinators list; _map_data attrs) — from the corpus's verified walk
  descriptions, re-confirmed in the verify-first gate.
tests_to_add_or_modify: selection matrix; binding; generation ordering; hash-input
  coverage; continue-not-return; sensor map_id check.
superseded_tests: first-hit walk pins (rewrite against scoped walks; docstrings
  record the binding invariant).
broader_gates: full suite.
hardware_gate: tier 2 — single-device regression on BOTH devices in the Wave-5
  batch (live map + overlays sensor unchanged); multi-device OPEN per Q13.
stop_conditions: [verify-first gate fails (Eufy half returns to synthesis); the
  image-entity root is absent on live HA for Ivy (report — do not widen the walk)]
escalation_target: main agent → Chris
```

---

## RP-027 — Staleness reaches every consumer (RF-10) — blocked_by RP-026

```yaml
packet_id: RP-027
family_id: RF-10
finding_ids: ["#11:A1-LC-2", "#11:A5-POSE-2", "#11:A5-POSE-4", "#11:A5-POSE-5",
  "#11:A1-LC-4", "#11:A5-POSE-1", "#11:A2-GEO-1", "#11:A5-POSE-3"]
files: [custom_components/eufy_vacuum/mapping/map_source_coordinator.py,
  custom_components/eufy_vacuum/mapping/map_source.py,
  custom_components/eufy_vacuum/listeners/pose_sampler.py,
  custom_components/eufy_vacuum/sensor/map_overlays.py, tests/]
symbols: [_commit_result hold path, _refresh_storage_map_source mtime return,
  _load_live_pose_geom, async_get_map_live_pose, live_pose_overlay]
problem: the hold path re-serves frozen moving fields (current_room, robot_anchor,
  path) as present:True with a stale flag NOTHING reads — a docked Roborock
  reports a phantom room for up to 6h INTO ATTRIBUTION at 2s cadence; the mtime
  early-return additionally bypasses the live-pose override, re-serving the frozen
  pose it exists to kill; the live-pose reader is the ONE reader never repointed
  to memory-primary geometry (memory-frame pixel through storage-frame geometry)
  and skips the store_version guard every sibling applies.
required_behavior: >
  (1) consumer split (the hold itself STAYS — deliberate for display): the hold
  path NULLS the moving fields for the attribution surface — held results carry
  current_room=None/robot_anchor=None/path=[] plus held_static=True; the card
  surface keeps the frozen statics + stale flag (CF-6 qualification display is the
  NAMED card consumer, not closed here). pose_sampler and the tracker treat a
  held/stale read as no-sample.
  (2) POSE-4: the live pose carries sampled_at; consumers ignore poses older than
  2× the sampler interval.
  (3) POSE-5/LC-4: the mtime early-return re-applies _apply_inmem_pose_to_result
  before returning (the cache holds geometry, not the pose overlay).
  (4) POSE-1/GEO-1: _load_live_pose_geom becomes memory-primary with storage
  fallback (the pattern every sibling uses) so the pixel and the geometry share a
  frame; POSE-3: the storage fallback applies the store_version guard.
rollback_plan: 3 commits — (a) hold-path split + sampler refusal, (b) mtime pose
  re-apply, (c) pose geometry repoint + guard. All share map_source_coordinator:
  strict order.
reproducer_script: NEW _proof_stale_consumers.py — held result: before →
  attribution consumed phantom current_room; after → no-sample; frozen-store pose:
  before → frozen overlay re-served; after → live override applied.
expected_before: ["phantom room attributed from hold", "frozen pose re-served"]
expected_after: ["held read yielded no sample", "pose overlay live", "memory-frame
  geometry"]
tests_to_add_or_modify: hold-split matrix (display vs attribution surfaces);
  sampled_at staleness; mtime pose re-apply; frame parity fixture (GEO-1's
  arithmetic case).
superseded_tests: tests pinning present:True-with-moving-fields on holds.
broader_gates: full suite.
hardware_gate: tier 2 Wave-5 batch — docked-Ivy hold: card keeps the map, the
  attribution log shows no phantom samples (observable in a short capture).
stop_conditions: [any consumer needs held MOVING data (report which)]
escalation_target: main agent → Chris
```

---

## RP-028 — Mapping services: no phantom buckets, addressed writes (RF-15)

```yaml
packet_id: RP-028
family_id: RF-15
finding_ids: ["#18:A1-SERVIC-1", "#18:A6-ZONE-C-6", "#18:A5-FURNIS-1",
  "#18:A3-IMAGE--5", "#13:A2-JOB-8", "#13:A5-RUNPROF-8", "#13:A6-DIAG-5",
  "#13:A6-DIAG-6", "#17:A2-DRAFT-4", "#18:A1-SERVIC-5", "#18:A4-CUSTOM-1"]
files: [custom_components/eufy_vacuum/maps/map_manager.py,
  custom_components/eufy_vacuum/services/_common.py,
  custom_components/eufy_vacuum/mapping/mapping_services.py,
  custom_components/eufy_vacuum/services/queue.py,
  custom_components/eufy_vacuum/services/snapshots.py,
  custom_components/eufy_vacuum/services/errors.py,
  custom_components/eufy_vacuum/services/dock.py,
  custom_components/eufy_vacuum/themes/manager.py, tests/]
symbols: [NEW maps.require_map_bucket, NEW _common.require_managed_vacuum,
  mapping_services handlers (29 map-taking), _handle_set_custom_segments,
  _handle_upload/delete_map_image filenames, queue mutators, error/dock/theme
  entry points]
problem: ensure_map_bucket setdefaults on read — 29 mapping schemas take free-form
  map_id and every handler mints the bucket (on Roborock map_id is the user-editable
  NAME: a vendor-app rename orphans everything while writes report saved);
  queue/profile/error/dock/theme stores mint durable buckets for any well-formed
  entity_id; image filenames interpolate unsanitized map_id; set_custom_segments
  is a REPLACE-ALL that cannot name its target layout; mapping_services uses the
  shared map resolver zero times vs 59 elsewhere.
required_behavior: >
  (1) require_map_bucket beside ensure/get in maps/map_manager (builder-with-
  inverse): returns the bucket or a refusal {success:false, reason: map_not_found,
  known_maps:[...]}; ALL mapping SERVICE handlers adopt it; import/setup paths
  keep ensure. Killed-FURNIS-2 boundary preserved: display-preference services
  with a DOCUMENTED fallback keep it; actuating/durable writers refuse.
  (2) mapping_services adopts resolved_call_data for optional map_id resolution
  (SERVIC-5) — schemas align (vol.Optional) where services.yaml documents optional
  (content parity finalized by RP-032's gate).
  (3) require_managed_vacuum in services/_common (registry-known vacuum) adopted
  by queue mutators, snapshots' writers, errors, dock counters, themes'
  _get_vacuum_theme service paths (JOB-8/RUNPROF-8/DIAG-5/DIAG-6/DRAFT-4);
  read-shaped services stop persisting (errors' ensure moved to write paths).
  (4) IMAGE--5: filenames use a sanitized token (allowlist [-a-z0-9_], collision-
  checked against existing files) with the raw map_id kept in the storage record.
  (5) CUSTOM-1: set_custom_segments requires layout_id (schema + services.yaml);
  active-layout fallback REFUSED for the destructive replace (mirror upload's
  contract).
compatibility_constraints: writes against unknown maps/vacuums now refuse (Q9
  classes) — release notes; Roborock rename-orphan RECOVERY stays out of scope
  (CF-3-adjacent, named).
rollback_plan: 3 commits — (a) require_map_bucket + mapping adoption + resolver,
  (b) managed-vacuum checks across modules, (c) filenames + CUSTOM-1.
  (a)+(c) share mapping_services.py — order a→c.
reproducer_script: NEW _proof_phantom_buckets.py — write against unknown map
  (before: phantom bucket persisted, saved:true; after: map_not_found);
  light.kitchen queue mutation (before: durable bucket; after: refused);
  set_custom_segments without layout_id (after: refused).
expected_before: ["phantom bucket minted", "unmanaged id persisted"]
expected_after: ["map_not_found + known_maps", "not_a_managed_vacuum",
  "layout_id required"]
tests_to_add_or_modify: per-handler refusal matrix; ensure-vs-require site audit
  test (greppable: no ensure_map_bucket in service handlers); filename sanitizer;
  display-fallback preservation.
superseded_tests: tests pinning bucket-minting reads.
broader_gates: full suite. hardware_gate: none (SOURCE_DECIDABLE).
stop_conditions: [a service both reads and creates BY DESIGN (import path) found
  in the sweep — list, keep ensure, document]
escalation_target: main agent → Chris
```

---

## RP-029 — Zone & custom-layout safety (map_version, indeterminate refusals, geometry) — blocked_by RP-028

```yaml
packet_id: RP-029
family_id: RF-25/RF-13 cousins (zone-safety batch per SYNTH-01b)
finding_ids: ["#18:A6-ZONE-C-1", "#18:A6-ZONE-C-3", "#18:A6-ZONE-C-4",
  "#18:A4-CUSTOM-3", "#18:A4-CUSTOM-4", "#18:A2-POLYGO-1", "#18:A2-POLYGO-3",
  "#18:A2-POLYGO-4", "#18:A6-ZONE-C-7", "#18:A2-POLYGO-2", "#18:A2-POLYGO-8",
  "#18:A3-IMAGE--7"]
files: [custom_components/eufy_vacuum/mapping/mapping_services.py,
  custom_components/eufy_vacuum/mapping/segment_primitives.py, tests/]
symbols: [_handle_clean_saved_zone(s), _create_saved_zone, _backfill_saved_zone_area,
  _handle_set_saved_zone_room, rasterize_primitives, mask_to_polygon,
  _apply_segment_adjustments, _handle_get_map_segments, _handle_delete_map_image]
problem: saved-zone clean dispatches when the active-map signal is blank (the
  guard is permissive); the doc-specified map_version invalidation key exists
  NOWHERE; the area/room backfill fails OPEN on an indeterminate active map and
  permanently persists wrong-map values; room_number=None conflates
  never-computed with user-chose-Unassigned; authored segments grow ~1 pixel per
  save compounding without bound; get_map_segments writes room_id into PERSISTED
  dicts returned by reference; multi-loop merges silently drop all but the
  largest; kind ignored at clean; numpy/Pillow-missing wipes the layout as
  saved:true; malformed primitives skip silently; delete reports deleted while
  the file remains.
required_behavior: >
  (1) ZONE-C-1: blank/indeterminate active map REFUSES the zone clean
  (indeterminate ≠ match — RF-13's rule applied to mapping); same for the
  backfills (ZONE-C-4/CUSTOM-3: compute only on a POSITIVE map match).
  (2) ZONE-C-3: implement the documented map_version — stamped on zone create
  from the live source's version (RP-026's content hash), checked at clean:
  mismatch → refusal "zone predates a re-map; re-draw it" (i18n code, card half
  named in CARD-PLAN).
  (3) CUSTOM-4: backfill writes room_number only with room_number_source=
  "computed"; the user's set_saved_zone_room writes source="user" — backfill
  never overwrites source="user" (incl. explicit null).
  (4) POLYGO-1: rasterize/trace round-trip made half-open-consistent (trace at
  the fill's true extent; pinned by a save→load→save idempotence test — zero
  drift over 3 cycles). POLYGO-3: _apply_segment_adjustments returns COPIES;
  the get_map_segments caller writes into the response only.
  (5) POLYGO-4: multi-loop results keep all loops ≥ a minimal area as a
  multipolygon list OR report dropped loop count in the response (implementer
  picks the smaller change; dropping silently is the defect). POLYGO-2/8: the
  capability-missing and per-primitive-failure paths return structured reasons
  (skipped list) and NEVER write an empty layout over a non-empty one (RP-006's
  rule reused). ZONE-C-7: non-"clean" kinds refuse dispatch. IMAGE--7:
  deleted:file_removed reported honestly; storage record kept when removal
  failed.
rollback_plan: 3 commits — (a) refusals + map_version, (b) backfill sources,
  (c) geometry/rasterize + response honesty.
reproducer_script: NEW _proof_zone_safety.py — blank active map clean (before:
  dispatched; after: refused); re-map then clean (after: version mismatch);
  3× save/load cycle (before: +3px growth; after: byte-stable); missing-numpy
  save (before: wiped layout saved:true; after: refused).
expected_before: ["dispatched on blank active map", "zone survived re-map
  silently", "polygon grew per save", "layout wiped saved:true"]
expected_after: ["indeterminate refused", "map_version mismatch refusal",
  "round-trip stable", "capability_missing refusal"]
tests_to_add_or_modify: refusal matrix; version stamp/check; source-flag
  precedence; round-trip idempotence; multi-loop/skip reporting.
superseded_tests: permissive-guard pins (docstrings record indeterminate≠match).
broader_gates: full suite. hardware_gate: tier 2 ride-along — one Ivy saved-zone
  clean post-re-map attempt in the Wave-5 batch (expects the refusal).
stop_conditions: [map_version source unavailable for a brand at create time —
  stamp absent + check skips WITH a warning, report the brand]
escalation_target: main agent → Chris
```

---

## RP-030 — Mapping small-correctness batch (RF-09/29 riders + geometry conventions)

```yaml
packet_id: RP-030
family_id: batch (SMALL-CORRECTNESS mapping members + dissolved DEF-2)
finding_ids: ["#11:A2-GEO-3", "#11:A2-GEO-5", "#11:A2-GEO-6", "#11:A2-GEO-4",
  "#11:A3-EXT-3", "#11:A3-EXT-4", "#11:A4-RB-7", "#11:A4-RB-8", "#11:A5-POSE-7",
  "#11:A5-POSE-6", "#18:A7-ROBORO-1", "#18:A7-ROBORO-5", "#18:A7-ROBORO-6",
  "#18:A7-ROBORO-7", "#18:A5-FURNIS-3", "#18:A5-FURNIS-5", "#18:A5-FURNIS-6",
  "#18:A3-IMAGE--9", "#18:A3-IMAGE--11", "#11:A6-TRK-6", "#18:A1-SERVIC-6"]
files: [custom_components/eufy_vacuum/mapping/map_source.py,
  custom_components/eufy_vacuum/mapping/map_source_runtime.py,
  custom_components/eufy_vacuum/mapping/roborock_raw_map.py,
  custom_components/eufy_vacuum/mapping/mapping_services.py,
  custom_components/eufy_vacuum/mapping/tracker.py, tests/]
problem_and_behavior: >
  Grouped independents, one line each (full mechanisms in the corpus records;
  REJECTED as a family — each site keeps its own authority):
  GEO-3/POSE-7: normalize_rendered gains an optional reject-out-of-grid mode;
  the pose/room callers use it (off-grid → None, matching the card's decoder);
  GEO-5: bbox and width_m agree on the inclusive extent (+1 both or neither —
  match the card's roomIdAt convention; pinned by a parity test);
  GEO-6: zone_membership tests cell CENTERS (docstring's claim becomes true);
  GEO-4/RB-8: clamped corners DETECTED and skipped in correspondences (the
  docstring's claimed guard implemented);
  EXT-3: mapdata_dict_from_obj requires the geometry field set — missing fields
  → absent-with-reason, never a confidently wrong map;
  EXT-4: outline offset sign MIRRORS the fork's two consumers (verified against
  render_map_png + room_id_at_normalized — external contract);
  RB-7: _walk/_structure_tree handle __slots__ objects via dir()-fallback
  descend (bounded);
  POSE-6: sampler docstring updated (consumption landed);
  ROBORO-1: zero-room raster → present:false, reason no_rooms (decode's own
  room_ids signal consumed); ROBORO-5: ONE flip_y default (True) via a shared
  module constant both readers use; ROBORO-6: max_center gets the same
  empty-common guard as min_iou; ROBORO-7: dims read only when header_len ≥ 24;
  FURNIS-3: viewport clamps (zoom [0.05,20], cx/cy [0,1]) mirroring the sibling;
  FURNIS-5: hidden_regions stamped with the authored frame's map_version
  (RP-029's stamp) — mismatch renders nothing + warns (masks hide content);
  FURNIS-6: home-art clear no longer setdefaults an empty dict (sentinel
  preserved); IMAGE--9: post-await layout re-check failure returns
  layout_not_found instead of silent skip; IMAGE--11: min_area_pixels absent →
  adapter's tuning (the is-not-None check made reachable);
  TRK-6: dock-drift append is a real append (open 'a') with size-triggered
  compaction; failed write re-queues the drift event (commit marker after
  write); SERVIC-6: backdrop_source gains vol.In(["live","upload"]).
rollback_plan: 3 commits by file group (map_source*, roborock_raw_map,
  mapping_services+tracker).
reproducer_script: NEW _proof_mapping_batch.py — table-driven: each case prints
  its id + before/after fragment.
expected_before: ["off-grid clamped to edge", "zero-room raster present:true",
  "flip_y defaults disagree"]
expected_after: ["off-grid rejected", "no_rooms absent", "single flip_y source"]
tests_to_add_or_modify: one focused test per member (21).
superseded_tests: GEO-5/GEO-6 convention pins updated with the chosen convention.
broader_gates: full suite. hardware_gate: none (fixtures; EXT-4 verified against
  fork source, not hardware).
stop_conditions: [EXT-4: the fork's two consumers DISAGREE with each other —
  stop, that is a fork bug to report upstream, not ours to average]
escalation_target: main agent → Chris
```
