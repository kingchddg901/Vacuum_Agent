# Repair Family Catalogue — Part B: remaining families (RF-17..RF-33), rejected candidates, deferrals, singles

Same conventions as Part A. Target commit `c61b3eb`.

---

## RF-17 — Themes: provenance, draft lifecycle, notify parity, import validation

```yaml
family_id: RF-17
status: accepted
members: [A1-CRUD-1, A1-CRUD-2, A1-CRUD-3, A1-CRUD-4, A1-CRUD-5, A1-CRUD-6, A1-CRUD-8, A2-DRAFT-1, A2-DRAFT-2, A2-DRAFT-3, A2-DRAFT-6, A2-DRAFT-7, A3-PORT-1, A3-PORT-2, A3-PORT-3, A3-PORT-4, A3-PORT-5, A3-PORT-7, A3-PORT-8, SN-6, A1-INIT-3]
candidate_root_cause: >
  Four sub-mechanisms in themes/manager.py:
  (a) overwrite_theme writes the ACTIVE theme's resolved payload over the target — wrong
      source entirely; with no active theme it wipes the target to {} (CRUD-1/2).
  (b) no provenance model: core themes deletable-but-reseeded (CRUD-3, INIT-3),
      overwritable while keeping source:"core" (CRUD-4), scoped imports corrupt the
      active core entry permanently (PORT-3).
  (c) draft lifecycle asymmetries: delete orphans the draft (CRUD-5/DRAFT-1 — one
      defect), set_active destroys the draft with no same-id short-circuit (DRAFT-2),
      _import_scoped never recomputes draft_dirty (DRAFT-6).
  (d) notify parity: the global-default branch of set_active_theme is the one mutator
      that skips _notify_updated (DRAFT-3/PORT-4/SN-6 — one defect, three findings).
  Plus import validation (PORT-1: unvalidated keys become live CSS on the card host —
  a blank-card injection), and small response/validation asymmetries.
shared_invariant: >
  (a) overwrite's source is the DRAFT-on-TARGET semantics the docstring claims, and an
      unresolvable source refuses; (b) source:"core" entries are immutable-in-place
      (copy-on-write or refuse + tombstone for delete); (c) every path that changes what
      a draft sits on resolves the draft (clear or carry) and recomputes draft_dirty;
      (d) every mutation notifies; (e) imported keys are validated against the token
      allowlist before storage.
counterevidence_checked: >
  - (a)'s intended semantics need Chris (the card flow may rely on "overwrite with my
    current look"): packet offers the minimal fix (refuse when no active theme; document
    the active-as-source semantics loudly) and the full fix (draft-over-TARGET) as a
    flagged decision. Default = minimal fix, no silent redesign.
  - (b) tombstones: delete-a-core-theme is a legitimate user intent; refusing forever is
    hostile. Tombstone list (deleted_core_ids) consulted by the seeder is small and
    honest.
  - Killed A3-PORT-6 (theme-id collision at microsecond resolution — unreproducible)
    bounds (c): no id-generation rework in this family; CRUD-8/A1-CRUD-8-adjacent id
    issues stay LOW/document-only. But note profiles' SECOND-resolution ids (RF-19's
    A3-PP-CRUD-8/A4-PP-RP-5) are NOT killed by that precedent — different resolution,
    reproducible; they get the `while id in store` retry there.
disposition: repair_independently (one module, several bounded packets; provenance check
  becomes a module-local helper `_is_core_entry` — not exported)
empirical_requirements: tier 1 (theme editor on live card after deploy).
repair_dependencies: RF-14's convention for ok:True honesty (tag-truncation etc.).
estimated_closure_count: 21
confidence: high
```

---

## RF-18 — Brand vocabulary injection through the profile catalog seams

```yaml
family_id: RF-18
status: accepted
members: [DQ-Q-4, A1-PP-RES-6, A2-PP-CAP-2, A1-PP-RES-8, A2-PP-CAP-7, DQ-PAY-1, A3-PP-CRUD-1, A3-PP-CRUD-4, DQ-Q-2, A1-PP-RES-5, A2-PP-CAP-4, DQ-PAY-6, A3-PP-CRUD-7, DQ-Q-6, A2-PP-CAP-6, A2-PP-CAP-3, A3-PP-CRUD-6, A2-PP-CAP-1, A5-PP-RP-7, A5-PP-RP-8, A1-INIT-5, A1-EST-7, A1-EST-8, A2-LIFE-3, A6-DIAG-8, DQ-PAY-5, DQ-DE-3, DQ-DE-4, A1-PP-RES-9, A6-PP-EST-TD-1, EP-8]
candidate_root_cause: >
  The brand catalog exists and is correctly consumed at SOME seams, but:
  (i) normalize_room_profile's third-level literals ("Max"/"Off"/"Quick") fire whenever
      a brand DELIBERATELY omits an axis (Q-4/RES-6/CAP-2 — the live mechanism the four
      killed lookalikes narrowed this family to);
  (ii) resolve_profile_catalog's `or` fallbacks make a declared-EMPTY block
      indistinguishable from absent (RES-8/CAP-7);
  (iii) ProfileManager's get_room_profiles / _match_profile_from_fields /
      get_effective_room_details / apply_room_profile never thread the catalog they
      have in hand (PAY-1/CRUD-1/CRUD-4/Q-2 — CAP-1 proves the catalog parameter is
      structurally inert on every production call);
  (iv) _protected_room_config and apply_capability_gate stamp Eufy display literals for
      framework concepts (PAY-6/CRUD-7/Q-6/CAP-6), clean_intensity has no capability
      flag (CAP-3), the protected-names set is frozen from Eufy builtins (CRUD-6);
  (v) hardcoded four-key display sets (RP-7, RES-5/CAP-4) and assorted Eufy literals in
      brand-agnostic modules (INIT-5 backfill, estimator wash bounds EST-7, is_mop set
      EST-8, lifecycle wash vocabulary LIFE-3, dock event vocab DIAG-8, engine defaults
      DE-3/DE-4, value_map fail-open PAY-5).
shared_invariant: >
  The adapter catalog is the sole source of profile/vocabulary truth; a framework
  literal may exist only where no brand can reach it (and then as the canonical
  neutral value, not Eufy display casing); declared-empty is honored as empty.
counterevidence_checked: >
  - The FOUR killed lookalikes (DQ-PAY-3, A2-PP-CAP-5, A4-PP-RP-8, A1-PP-RES-1) prove
    stored rooms ALWAYS materialize keys via RoomConfig.asdict — so any member premised
    on absent ROOM keys is dead. Every member above was re-checked: all fire on the
    PROFILE/catalog path (normalize_room_profile / resolve_profile_catalog / literal
    stamping), which the kills explicitly leave live.
  - protected_room_config rescues carpet/clean_mode at both payload entry points
    (killed A1-PP-RES-1) — (iv)'s fix must preserve that clamp's SAFETY semantics while
    fixing only the vocabulary it writes.
  - ~50% of divergence deliberate: per-member adjudication kept "wide"/1/False (framework
    canonical) OUT of the literal purge; only Eufy DISPLAY vocabulary ("Max","Off",
    "Quick", wash strings, dock strings) is in scope.
  - DE-3/DE-4 (engine template defaults to Eufy) is dispatch-layer, same invariant
    ("absent resolves to Eufy silently") — kept here for the invariant audit, executes
    with RF-32's registration-validation packet (cross-listed, closes once).
disposition: centralize (catalog threading through ProfileManager — the vacuum_entity_id
  is already at every call site; helpers exist; this is completing an 80%-applied seam,
  audit #4's verdict)
proposed_source_of_truth: profiles/room_profiles.resolve_profile_catalog (fixed
  `key in block` semantics) + ProfileManager methods gaining catalog resolution.
compatibility_risks: >
  Roborock rooms stop acquiring "Quick"/"Off"/"Max" via apply paths. EXISTING stored
  Roborock rooms already carrying Eufy literals are the carried Roborock-room-migration
  item (CF-3) — named as follow-on, NOT closed by this family.
empirical_requirements: tier 0 + tier 1 (Ivy panel: apply a profile, inspect stored
  room). Wire behaviour rescued today by lowercase ranks — regression tests pin that.
repair_dependencies: RF-19 (resolution precedence) — same functions; RF-19 lands first.
estimated_closure_count: 31 (members closed individually per §L; DE-3/DE-4 close via RF-32)
confidence: high
```

---

## RF-19 — Profile resolution precedence and the custom-snap

```yaml
family_id: RF-19
status: accepted
members: [A1-PP-RES-2, A3-PP-CRUD-2, A6-PP-EST-DSP-1, A6-PP-EST-DSP-2, DQ-PAY-2, A1-PP-RES-4, A6-PP-EST-H2O-1, A1-PP-RES-3, A1-PP-RES-7, A3-PP-CRUD-5, A3-PP-CRUD-8, A4-PP-RP-5, A5-PP-RP-2_display_note, A2-PP-CAP-3_dup_check]
candidate_root_cause: >
  (i) water_level (and carpet fan_speed) resolve with floor-default-over-profile
      precedence while every sibling field is room-over-profile (RES-2) — and
      _match_profile_from_fields builds candidates WITHOUT a water key, so the resolver
      rewrites the profile's own water and the just-applied profile immediately
      re-labels "custom" (CRUD-2, DSP-1/2 display halves).
  (ii) granite/concrete are selectable floor types absent from every water-defaults
      table → water_level resolves to "" and goes to the wire verbatim (PAY-2/RES-4/
      H2O-1 — one fix, three findings).
  (iii) path_type=None backfill → str(None)="None" on the Eufy wire (RES-3).
  (iv) dangling profile refs resolve silently to the default (RES-7 — display side of
      RF-20's rename orphans).
  (v) save-as-profile round-trip drops path_type (CRUD-5); second-resolution ids with
      no exists check (CRUD-8, RP-5).
shared_invariant: >
  Field precedence is uniform (room-explicit > profile > floor-safety-CLAMP) where the
  clamp only ever REDUCES risk (carpet: water off) and never silently rewrites the
  selected profile's identity; every selectable floor type has a defined water default;
  no None/"" reaches the wire.
counterevidence_checked: >
  - The carpet override is plausibly deliberate SAFETY — the repair reframes it as an
    explicit clamp applied after resolution (semantics preserved: carpet still forces
    fan Max/water Off) while removing the identity-rewrite side effect. If Chris
    declares floor-default-over-profile intentional for water generally, disposition
    flips to document_only for RES-2 and the custom-snap is fixed in
    _match_profile_from_fields alone (candidate gains the profile's water key) — packet
    carries both, gated on his call.
  - granite/concrete default VALUE is a product choice (proposal: map to the tile/
    marble default per brand — hard floors; NOT "off"), flagged for Chris.
disposition: repair_independently (bounded edits in room_profiles.py + manager.py)
empirical_requirements: tier 0; DSP display halves verified on card (tier 1).
repair_dependencies: none; RF-18 depends on this landing first.
estimated_closure_count: 13
confidence: high on mechanisms, medium on the precedence PRODUCT decision (Chris).
```

---

## RF-20 — Referential integrity on rename/delete

```yaml
family_id: RF-20
status: accepted
members: [A3-PP-CRUD-3, A3-ROOMS-8, A3-CRUD-4, A6-ZONE-C-2, A3-IO-6, A4-CUSTOM-5, A3-IMAGE--6, A6-ZONE-C-5]
candidate_root_cause: >
  Deletes/renames mutate only their own store: profile rename/delete leaves rooms
  pointing at vanished keys (CRUD-3/ROOMS-8, silently resolving to a built-in via
  RES-7); remove_map leaves run-profile library, queue state and onboarding state to be
  resurrected by re-import with WRONG room ids (A3-CRUD-4 — CRITICAL); saved-zone delete
  leaves queue/profile zone steps silently dropped at dispatch (ZONE-C-2); renaming the
  vacuum entity orphans the whole learning archive directory (IO-6); zone/layout ids
  are reused after delete while durable refs persist (CUSTOM-5); image delete sweeps no
  back-references (IMAGE--6); layout create/delete strands segmentation_mode (ZONE-C-5).
shared_invariant: >
  A destructive rename/delete either migrates/clears every durable referrer or reports
  the referrer count and refuses/warns. The set of per-(vacuum,map) stores is enumerated
  in ONE place consumed by remove_map (and by RF-25's id-remap walker).
counterevidence_checked: >
  - IO-6 (entity rename → archive dir) fix candidates: key by config-entry/unique_id
    (migration of directory naming = MIGRATION_INSPECTION_GATE) vs detect-and-offer-move.
    Deferred decision to packet with Chris input; interim: detect mismatch and warn
    loudly (no silent cold restart).
  - Zone-id reuse (CUSTOM-5): fix = include a monotonic counter or uniqueness against
    referenced ids too — small; kept despite LOW because zone ids are durably referenced.
disposition: centralize (the per-map store registry); repair_independently for the
  rename paths.
proposed_source_of_truth: maps/map_manager.py or rooms/room_crud.py — one
  PER_MAP_STORES enumeration used by remove_map; ProfileManager rename/delete gain
  referrer scans.
estimated_closure_count: 8
empirical_requirements: tier 0/1.
repair_dependencies: RF-25 shares the store registry — build it in this family first.
confidence: high
```

---

## RF-21 — Estimator/ETA correctness cluster

```yaml
family_id: RF-21
status: accepted
members: [A1-EST-1, A1-EST-2, A1-EST-3, A1-EST-4, A1-EST-5, A1-EST-6, A1-EST-9, A2-ACC-2, A2-ACC-3, A2-ACC-4, A2-ACC-5, A2-ACC-6, A2-ACC-7]
candidate_root_cause: >
  Independent defects sharing one file and one consumer (the card's ETA/confidence UI):
  dead band 0.79–0.80 renders the BEST rooms as LOW/error (EST-1); external runs
  contribute battery=0.0 consumed as real (EST-2); Roborock intensity "" vs "standard"
  normalization mismatch permanently penalizes every Roborock room (EST-3); no outlier
  rejection though min/max are computed and stored (EST-4); HIGH tier mathematically
  unreachable while velocity promises it (EST-5); relaxed matches take the
  lexicographically-first bucket ignoring sample_count (EST-6); reanchor ignores its
  anchor param so ETAs slide into the past (ACC-2), drops transit asymmetrically
  (ACC-3), cannot resolve skipped rooms though EVENT_ROOM_SKIPPED exists (ACC-4),
  slug-matches on the literal "none" (ACC-5); the exact-vs-allocated quality flag is
  recorded and never used (ACC-6 — consumed by RF-11's allocation design).
shared_invariant: none single — grouped for packet economy (one file, one reviewer
  context), NOT as a shared-repair family. Explicitly a bounded-batch, not a
  centralization.
counterevidence_checked: >
  - EST-2's fix must not simply treat 0.0 as absent (a genuine 0.0 delta exists for
    trivial rooms): correct fix is upstream — external ingest writes NO battery block →
    rebuilder must not coerce absent to 0.0 (track battery_sample_count like area).
  - Tuned constants (breakpoint table values, penalties) are EMPIRICAL — packets fix
    STRUCTURE (dead band closed, band checks consume stored min/max) without re-tuning
    values (source-decidability rule).
disposition: repair_independently
estimated_closure_count: 13
empirical_requirements: tier 0 + tier 2 observation ride-along (ETA behaviour on the
  RF-11 validation runs); EST-2 verified against an app-started run capture.
repair_dependencies: RF-11 (record shape: allocated flags feed ACC-6's fix).
confidence: high
```

---

## RF-22 — Learning accumulator rebuild scope and cache coherence

```yaml
family_id: RF-22
status: accepted
members: [A5-SVC-1, A5-SVC-5, A5-SVC-8, A4-STATE-5, A4-STATE-9, A4-STATE-3, A4-STATE-4]
candidate_root_cause: >
  exclude/restore_learning_job rebuild only the four derived files, never the three
  incremental accumulators — the poison the services exist to remove stays in
  accuracy_stats/learned_zones/battery aggregates (SVC-1; async_rebuild_learning_
  accumulators EXISTS and has exactly two callers); the service accuracy write skips
  the manager cache invalidation its four siblings perform (SVC-5); invalidate-then-
  preload races an in-flight preload (SVC-8); trouble_rooms has no rebuilder and its
  "self-healing rate" justification is disproven — the denominator only advances while
  queued (STATE-5, reopens the 3d decision with NEW evidence); incomplete_run/
  trouble_rooms are id-keyed, map-unscoped stores the card applies to whatever map is
  active (STATE-3/4 — the card half of STATE-4 is a named frontend consumer).
shared_invariant: >
  Every durable learning store is either rebuildable from the archive or explicitly
  registered as raw-evidence-with-no-rebuilder; exclude/restore reach ALL of them;
  cache invalidation accompanies every write.
counterevidence_checked: >
  - STATE-5 challenges Chris's explicit 3d drop ("rates self-heal"). The new fact
    (denominator freezes when unqueued) was not before him. Presented as a REOPEN
    QUESTION with the evidence, not silently reversed. Interim packet fixes only the
    reachable wrongness (map-scoping via RF-25's id-remap coverage).
disposition: repair_independently
estimated_closure_count: 7
empirical_requirements: tier 0; exclude→verify accuracy_stats on disk (fixture).
repair_dependencies: RF-01, RF-11 (record shape), RF-25 (id-remap walker).
confidence: high
```

---

## RF-23 — Per-brand caps enforced by declaration, not by branch

```yaml
family_id: RF-23
status: accepted
members: [DQ-ZONE-1, DQ-PAY-4, A2-JOB-4, A1-SERVIC-3, DQ-ZONE-3, DQ-ZONE-4, A6-ZONE-C-8, A3-SNAP-4, DQ-ZONE-2, DQ-ZONE-5]
candidate_root_cause: >
  dispatch_zone_clean's clamps live inside coordinate-space branches: the repeat cap
  only in device_mm (Roborock) so Eufy ships clean_times verbatim (ZONE-1, with the
  schema comment claiming otherwise — JOB-4/SERVIC-3 same claim, three findings one
  fix); area bounds only in device_mm, side bounds only in the else, regardless of what
  the adapter DECLARED (ZONE-3); Eufy's side check silently skips when live dims are
  unreadable while the sibling branch refuses (ZONE-4); zone size not checked at author
  time (ZONE-C-8); the snapshot invents zone_max=10 while dispatch enforces none
  (SNAP-4); supports_zone_clean consulted by the card only (ZONE-2); zone_bounds
  computed and shipped with no consumer (ZONE-5).
shared_invariant: >
  Every declared cap (zone_max, passes, side/area bounds) is enforced at dispatch on
  EVERY branch, advisory-checked at author time, and reported to the card from the same
  declaration — one resolution, three consumers.
disposition: centralize (cap resolution hoisted above the coordinate-space branch in
  dispatch/manager.py; author-time check calls the same resolver)
counterevidence_checked: >
  - Eufy's true zone repeat ceiling is HARDWARE TRUTH (docs treat room passes_max=2;
    zone cap undeclared) — packet clamps to declared zone_passes_max/passes_max with
    the DEFAULT resolved once (2 for Eufy via adapter declaration, added explicitly);
    Chris confirms the device ceiling at Gate 4.
  - ZONE-4's missing-dims refusal makes Eufy zone cleans FAIL when the live map is
    unavailable — matches the mm-branch's existing refusal semantics; behaviour change
    flagged.
estimated_closure_count: 10
empirical_requirements: tier 2 zone dispatch (one zone clean per brand) — batch with
  RF-08's Ivy runs; Eufy zone run on Alfred.
repair_dependencies: none
confidence: high
```

---

## RF-24 — Room identity derivation: slug uniqueness at the admission boundary

```yaml
family_id: RF-24
status: accepted
members: [A1-ID-1, A2-REC-2, A1-ID-3, A6-TRK-5, A1-ID-5, A1-ID-6]
candidate_root_cause: >
  slugify_room_name has no uniqueness guarantee (docstring claims it, code lacks it —
  ID-1 CRITICAL: duplicate names dispatch the FIRST room's segment on Roborock);
  reconciliation collapses same-name rooms into one identity and migrate overwrites one
  room's settings with the other's (REC-2 CRITICAL); an all-quote name slugifies to ""
  and passes (ID-3); the tracker normalizes names DIFFERENTLY from slugify (TRK-5);
  a dead divergent second implementation of discovery exists (ID-5); RoomRecord
  documents slugs where ids are stored (ID-6).
shared_invariant: >
  One slug derivation, applied at the single admission boundary (discovery emit), with
  a STABLE uniqueness guarantee: colliding slugs are deterministically disambiguated
  (suffix `_r{room_id}` for all but the lowest room_id) and an empty slug is refused
  there. All name→id resolution routes through the same derivation.
counterevidence_checked: >
  - Disambiguation changes the slug of the SECOND room only, and only in the collision
    case — where today that room's learning history is already misattributed to the
    first room's slug. Starting it fresh under a distinct slug is honest, not lossy.
    Product-visible: Chris confirms the suffix scheme at Gate 4.
  - Stability: `_r{room_id}` is stable across discoveries while the device keeps the id
    — on Roborock a re-segment renumbers ids and reshuffles slugs anyway (that churn is
    RF-25's domain, not worsened here).
  - TRK-5's fix = tracker adopts slugify (with NFC), not a third normalizer.
disposition: centralize (already-central function gains the guarantee; boundary check
  at discovery)
estimated_closure_count: 6
empirical_requirements: SOURCE_DECIDABLE + tier 0 (collision fixtures).
repair_dependencies: lands BEFORE RF-25 (reconciliation consumes unique slugs).
confidence: high
```

---

## RF-25 — Identity through re-segment: reachable reconciliation and id-keyed store repair

```yaml
family_id: RF-25
status: accepted
members: [A2-REC-1, A2-REC-8, A3-CRUD-2, A2-REC-3, A2-REC-5, A2-REC-6, A2-REC-7, A3-CRUD-5, A3-CRUD-3, DQ-Q-5, A3-CRUD-6, A5-FURNIS-4, A2-POLYGO-5, A4-CUSTOM-6, A3-IMAGE--1, A3-IMAGE--4, DR-ONB-1, DR-ONB-2, A1-ID-2, A1-ID-4, A6-GUARD-5]
candidate_root_cause: >
  The slug-aware migration path (plan_migration) is UNREACHABLE from the product
  (REC-1: no card wiring, no auto-trigger), so the reachable writers carry settings by
  NUMERIC id — a renumber transplants floor type, access grants, rules and dock flag
  onto different physical rooms (REC-8/CRUD-2); rename+renumber in one edit is
  invisible and migrate deletes the room's data (REC-3); migrate applies a plan the
  user never saw (REC-5); renames orphan slug-keyed learning (REC-6); dismissals are
  never consulted (REC-7); rejected rooms resurrect (CRUD-5); save auto-confirms floor
  types satisfying the onboarding gate forever (CRUD-3) and both writers auto-enable
  unseen rooms into the queue (DQ-Q-5/CRUD-6); id-keyed sidecar stores are never
  remapped (label anchors FURNIS-4, CV adjustments POLYGO-5/CUSTOM-6, room links
  IMAGE--1, image_segments on re-upload IMAGE--4); the confirmed-floor remap corrupts
  itself on overlapping id sets (DR-ONB-1); discovery drift is map-unscoped
  (ID-4/GUARD-5, single-map fallback relabels another map's rooms ID-2, count check
  unscoped ONB-2).
shared_invariant: >
  Physical-room identity survives a re-segment: carry-over is slug-led with id
  fallback; every id-keyed durable store is covered by the id_remap walker; new/unseen
  rooms enter DISABLED and unconfirmed; destructive migration requires the reviewed
  plan (token/echo) and never runs against empty or wrong-map discovery.
counterevidence_checked: >
  - Making build_managed_rooms slug-led changes carry-over for EXISTING installs where
    ids were stable — behaviour identical when ids and slugs agree; divergence only in
    the renumber case being fixed. Verified no consumer depends on id-led transplant.
  - Auto-enabling new rooms may be DESIRED onboarding convenience for the FIRST import
    (all rooms enabled) — packet distinguishes first-import (enable all) from
    incremental discovery (disabled + review), preserving the documented first-run UX.
  - CV segment ids are PER-RUN ordinals — POLYGO-5/CUSTOM-6/IMAGE--1's honest repair is
    invalidation on re-analysis (clear adjustments/links or key them by geometry
    fingerprint), NOT a remap (nothing stable to map to). Different mechanism from room
    ids — split packet, same family.
  - Surfacing reconciliation in the card is PRODUCT work (Chris) — the backend packets
    make it wireable (service response carries the plan echo + token); card work is a
    named downstream consumer, not closed here.
disposition: migrate_or_version (identity carry-over change + id-remap coverage), with
  the card surfacing deferred to Chris.
proposed_source_of_truth: rooms/room_manager.build_managed_rooms (slug-led carry),
  rooms/room_crud id_remap walker extended over the RF-20 store registry,
  reconciliation gaining rename+renumber pairing via unique slugs (RF-24).
compatibility_risks: HIGH-visibility family — touches how every room edit persists.
  Staged: (a) walker coverage (safe), (b) slug-led carry (flagged), (c) gating/enable
  semantics (flagged), (d) plan-token migrate (service contract addition).
empirical_requirements: tier 2 (Roborock re-segment simulation via stored fixtures is
  possible for most; a REAL Ivy re-map capture is the honest gate for (b) —
  HARDWARE_BASELINE_GATE, needs an Ivy map edit session).
repair_dependencies: RF-24 (unique slugs) and RF-20 (store registry) first; RF-02's
  guard shares the chokepoint file.
estimated_closure_count: 21
confidence: high on mechanisms; product decisions flagged.
```

---

## RF-26 — Access graph: one reachability answer, a real verdict, delta-scoped gates

```yaml
family_id: RF-26
status: accepted
members: [A5-AG-1, A6-PP-EST-BLK-1, A5-AG-2, A6-AGX-1, A6-AGX-2, A6-AGX-3, A6-AGX-5, A6-AGX-6]
candidate_root_cause: >
  access_graph exports edges but not the reachability ANSWER, so preflight walks ALL
  rooms while the mid-run report walks the QUEUE only — a queued room whose transit
  parent is unselected reports blocked and can cancel the job (AG-1/BLK-1, one defect
  twice); a new room with no inbound edge makes the whole graph 'partial' hard-blocking
  every run with no room named (AG-2); the health report emits no verdict so
  allow-everything and block-everything are indistinguishable and its own remediation
  moves users from the first to the second (AGX-1); the structural gate rejects
  UNRELATED per-room edits absolutely (AGX-2); the editor blames every candidate for
  pre-existing violations (AGX-3), drops graph-scoped issues from per-room views
  (AGX-5); the card renders a dock-room edge as "Missing Room N" (AGX-6 — src/ member,
  the one open frontend finding; ships with this family's backend contract).
shared_invariant: >
  Reachability is computed by ONE exported function (graph-scoped, with an explicit
  queue-projection mode that seeds from global reachability); the graph state exposes a
  verdict; structural validation gates only the DELTA an edit introduces.
disposition: centralize (the reachability function in rooms/access_graph.py — it owns
  the question; both consumers repoint)
counterevidence_checked: >
  - AG-2's "no inbound = error" may be deliberate strictness — but blocking EVERY run
    on the map for one unconfigured room fails the consequence test (broad inability to
    perform primary function = HIGH per frozen rubric; regrade AG-2 MEDIUM→HIGH).
    Proposed semantics: unconfigured room = warning + that room excluded, not
    map-wide block. Chris confirms.
estimated_closure_count: 8
empirical_requirements: tier 0 + tier 1 (graph editor on live card).
repair_dependencies: none
confidence: high
```

---

## RF-27 — i18n leaks (backend English into an 18-language product)

```yaml
family_id: RF-27
status: accepted
members: [A6-AGX-4, INF-9, EP-5]
candidate_root_cause: backend formats English literals (graph issue messages, floor
  labels, button names) that the card renders verbatim across 18 locales.
shared_invariant: backend returns CODES + params; the card translates (the convention
  the codebase already uses everywhere else); entities use translation keys.
disposition: standardize_locally
notes: >
  The three untranslated CARD strings are carried CF-4 (frontend packet, trivial).
  AGX-4's fix changes the room-access service response shape (message → code+params)
  — card consumer named (bindings/room-access.js prefers backend message today).
estimated_closure_count: 3 (+CF-4 downstream)
empirical_requirements: tier 0/1; check:i18n gate.
repair_dependencies: ships with RF-26 (same response payloads touched once).
confidence: high
```

---

## RF-28 — Declaration parity gate: services.yaml ↔ schemas ↔ docs

```yaml
family_id: RF-28
status: accepted
members: [A3-ROOMS-4, A5-FACADE-5, A1-WIRE-3, A4-SETUP-15, A1-SERVIC-5, A1-SERVIC-6, A1-SERVIC-7, A5-SVC-9, A2-JOB-5, A2-JOB-6, A1-WIRE-4, A3-ROOMS-3, A6-ZONE-C-7, A4-CUSTOM-7, A3-IMAGE--10, A1-SERVIC-4]
candidate_root_cause: >
  services.yaml advertises fields the schemas reject (carpet ×2, floor_types), 16+
  registered services have no descriptor, 8 mapping services document optional map_id
  against Required schemas, 19 dead schemas including near-twin traps, docs mark
  required fields optional, break-schema round trip fails validation, one registration
  has no schema at all, zone kind free-form vs documented enum, stale service prose.
shared_invariant: >
  Every registered service: schema present; services.yaml entry present (or on an
  explicit internal allowlist); every services.yaml field exists in the schema with
  matching required-ness; read-modify-write round trips validate.
disposition: centralize — BUILD THE GATE (a contract test loading services.yaml +
  registered schemas and asserting parity), then fix content until green. This is the
  expansion-ready-seam pattern (contract-test gate precedent: c9ee622/f12a87c).
counterevidence_checked: >
  - Gate must not force descriptors onto genuinely-internal services — the allowlist is
    explicit and reviewed (Chris sees the list; A4-SETUP-15's 16 become either
    documented or listed-internal deliberately).
estimated_closure_count: 16
empirical_requirements: tier 0 (the gate IS the evidence).
repair_dependencies: RF-14 (some schemas change there; run the gate after).
confidence: high
```

---

## RF-29 — Event-loop hygiene (blocking I/O, duplicate compose, save flood)

```yaml
family_id: RF-29
status: accepted
members: [A1-EST-9, A3-IO-4, A4-STATE-7, A7-ROBORO-2, A2-GEO-2, DR-ONB-5, A3-SNAP-2, A2-DRAFT-5, A6-TRK-6, A6-TRK-7]
candidate_root_cause: >
  ensure_dirs inside every path getter (~32 mkdir/stat per snapshot), per-pixel Python
  loops on the loop (ROBORO-2 diagnostics, GEO-2 zone_membership pre-bbox), snapshot
  composes the progress payload TWICE with side effects firing twice per card poll
  (SNAP-2 — also a correctness item: the two copies can disagree), theme draft saves
  the whole store per keystroke (DRAFT-5), dock-drift full-file rewrite per reading
  (TRK-6), executor dispatch justified by I/O that does not exist (TRK-7).
shared_invariant: hot read paths are syscall-free after warm-up; snapshot composition is
  pure (side effects hoisted out of the read path) and single; high-frequency writes are
  debounced (async_delay_save).
disposition: repair_independently
counterevidence_checked: >
  - SNAP-2's fix (memoize within one snapshot call + hoist _maybe_roll side effects to
    the tick path) changes WHERE rollover events fire from — verified consumers
    (listeners) are indifferent to the caller; packet pins that.
estimated_closure_count: 10
empirical_requirements: tier 0 + blocking-I/O test guard (repo notes) extended.
repair_dependencies: RF-11 (SNAP-2's rollover hoist touches the same progress path).
confidence: high
```

---

## RF-30 — Dock events are edges from known states

```yaml
family_id: RF-30
status: accepted
members: [A1-REG-1, A6-GUARD-3, DR-DOCK-1, DR-DOCK-2, DR-DOCK-3, A1-REG-4, A2-LIFE-3_edge_half]
candidate_root_cause: >
  dock_events treats first-sighting/unavailable-recovery as fresh cycles (REG-1/GUARD-3
  one defect), the timestamp is written before the debounce so a debounced event still
  corrupts last_* (DOCK-1), record_dock_event validates nothing while its sibling does
  (DOCK-2), counter reset leaves the debounce marker (DOCK-3), the adapter's
  dock_events.enabled flag is never read (REG-4), and the inline lifecycle wash
  detector re-implements the edge logic divergently (LIFE-3 — vocabulary half in RF-18).
shared_invariant: a dock event is a transition FROM a known non-trigger state TO a
  trigger state; debounce, timestamp and counter commit atomically; the adapter's
  enabled flag governs.
disposition: standardize_locally (dock_events owns the edge test; lifecycle delegates)
estimated_closure_count: 7
empirical_requirements: tier 2 ride-along (Alfred mop-wash cycle) — batch with
  lifecycle runs; restart-mid-dry is the sharp case.
repair_dependencies: none
confidence: high
```

---

## RF-31 — Tracker lifecycle (attribution start/stop/hold)

```yaml
family_id: RF-31
status: accepted
members: [A6-TRK-1, A6-TRK-2, A6-TRK-3, A6-TRK-4, A4-AJ-1, A4-POSE-1, A4-POSE-2, A4-POSE-5, DQ-PH-6_pointer_note]
candidate_root_cause: >
  end_job fires only on successful finalize — cancel/strand leave the tracker stuck on
  the dead job blocking the NEXT run's sampling (TRK-1); resume_sampling is provably
  unreachable (one-way pause latch behind a same-tick double-check — TRK-2, and the
  recharge-end branch is the same dead code from the job side, A4-AJ-1 HIGH: recharge
  never ends, recharging runs silently held from learning); the HOLD path accrues dwell
  for a room the robot left, forcing confidence 1.0 (TRK-3); the last room never fires
  room_completed (TRK-4); sampler cadence collapses to min() across vacuums while ticks
  are valued at each vacuum's own interval (POSE-1 — Roborock samples over-weighted
  2.5x); fire-and-forget overlapping ticks (POSE-2); one raising vacuum drops the rest
  of the tick (POSE-5).
shared_invariant: >
  The tracker's job lifecycle mirrors the JOB's lifecycle (every terminal path releases
  it); pause/resume are reachable inverses; per-vacuum sampling uses per-vacuum cadence
  or values ticks at the actual cadence; per-vacuum isolation on shared tickers.
counterevidence_checked: >
  - A4-AJ-1's dead branch: the fix is EVENT-DRIVEN recharge-end detection (charging→not
    charging transition observed by the listener), not "fix the double-check" (the
    second check is structurally same-tick). Design note pinned so Sonnet doesn't
    "repair" the unreachable branch in place.
  - CF-2 (pose sampler predicate divergence) preserved — explicitly out of scope.
disposition: standardize_locally
estimated_closure_count: 9
empirical_requirements: tier 2 lifecycle batch (cancel a run; verify tracker released;
  mid-run recharge run on Alfred for AJ-1 — needs a low-battery staged run, note in
  hardware register as the one EXPENSIVE capture; alternative: simulate charging state
  transitions in tests + SOURCE_DECIDABLE for the release paths).
repair_dependencies: RF-06/RF-07 (cancel paths call the release).
confidence: high
```

---

## RF-32 — Adapter-config seam: stored configs cannot silently shadow the code adapter

```yaml
family_id: RF-32
status: accepted
members: [A4-SETUP-2, A4-SETUP-3, A4-SETUP-5, A4-SETUP-9, DQ-DE-4, DQ-DE-3, A6-VAC-3, A1-WD-5_validation_half, A4-POSE-4, A3-COMMON-2, A1-SERVIC-1_adapter_note]
candidate_root_cause: >
  save_adapter_config accepts a two-key config and registers it OVER the live code
  adapter — every omitted block resolves to Eufy behaviour on any brand (SETUP-2 —
  audit #4's "every unapplied edge fails toward Eufy silently" at its root);
  delete unregisters the LIVE adapter leaving none (SETUP-3); persist-before-validate
  (SETUP-5); setup.steps never validated despite three claims (SETUP-9); an absent
  dispatch.template silently resolves to the Eufy engine (DE-4) and the documented
  no-command envelope is unreachable (DE-3); refresh_vacuum_capabilities drops the
  probe-only candidates (VAC-3); phase_timing/tuning accepted unclamped (WD-5/POSE-4
  validation halves); completion flag never validated against entity existence
  (COMMON-2).
shared_invariant: >
  A stored adapter config is validated against the FULL contract (ADAPTER_CONFIG_SCHEMA
  — which exists and is applied only in tests today) BEFORE it may shadow the code
  adapter; hard violations raise; deletion restores the code adapter; absent blocks
  resolve to the CODE adapter's own brand, never cross-brand.
disposition: centralize (validation at registration — the seam exists, apply it)
estimated_closure_count: 11
empirical_requirements: tier 0 (contract tests); tier 1 reload check.
repair_dependencies: RF-16 (registration lifecycle) first.
confidence: high
```

---

## RF-33 — Diagnostic instruments tell the truth (flight recorder + diagnostics)

```yaml
family_id: RF-33
status: accepted
members: [DR-DBG-1, DR-DBG-2, DR-DBG-4, DR-DBG-6, DR-DBG-7, DR-DIAG-1, DR-DIAG-2, DR-DIAG-3, DR-DIAG-4, DR-DIAG-5, HW-DIAG-1, DR-LR-1]
candidate_root_cause: >
  The flight recorder stores exc_info tracebacks unredacted/untruncated (DBG-1 — HIGH,
  and §6 makes the recorder the campaign's validation instrument, multiplying dump
  volume); the switch bypasses the services' auto-stop bookkeeping (DBG-2); free-form
  areas silently record nothing (DBG-4); status lies after stop (DBG-6); same-second
  dumps collide (DBG-7); diagnostics' read-only claim is false (DIAG-1), nine repr(err)
  sinks bypass redaction (DIAG-2), failed probes vanish from the warnings block
  (DIAG-3), entry.title unredacted (DIAG-4); live_refresh treats a misdeclared response
  contract as transient and retries forever at DEBUG (DR-LR-1).
shared_invariant: the diagnostic surfaces apply the SAME redaction/truncation to every
  sink, report their own state truthfully, and classify permanent misconfiguration as
  permanent.
disposition: repair_independently
priority_note: DBG-1 lands in WAVE 1 — before the recorder is used for this campaign's
  hardware validation dumps (it will produce many).
estimated_closure_count: 12
empirical_requirements: tier 0 (DBG-1 has a proven reproducer pattern in the record).
repair_dependencies: none
confidence: high
```

---

## RF-34 — Sensor/entity platform gaps

```yaml
family_id: RF-34
status: accepted
members: [SN-1, SN-4, SN-8, SN-9, SN-10b, EP-3, EP-4, EP-6, EP-7, A3-FLOW-2, A3-FLOW-3, INF-1, INF-2, A6-PRE-3, A6-PRE-4, DQ-PH-5, A5-METRICS-3, A5-METRICS-4, A5-METRICS-5, A4-VAC-5_placeholder]
members_note: A4-VAC-5_placeholder = A6-VAC-5 (get_managed_vacuums raw capability read).
candidate_root_cause: >
  Platform-level independents: the per-vacuum sensor loop iterates data["maps"] so a
  vacuum has ZERO per-vacuum sensors until a restart after import (SN-1 — HIGH, fix:
  iterate managed vacuums + create on the import/reload path); room rename never
  reaches friendly names (SN-4); reserved-state literal 'unavailable' (SN-9); dead
  registries/dead assignments (SN-8, EP-6, INF-1's fourth panel site, PRE-3/PH-5/
  METRICS-5 TypedDict drift, METRICS-4 guessed entity key); interval bounds conflict
  with adapter declarations (EP-3 — pairs with RF-23's declaration rule); options-flow
  add-instead-of-replace and stale-snapshot resurrect (FLOW-2/3); fixed-offset
  timezone captured at import mis-stamps naive legacy timestamps half the year
  (INF-2 — mechanical, real); mixed-update key drop (EP-7).
shared_invariant: none single — platform batch grouped for packet economy.
disposition: repair_independently
estimated_closure_count: 20
empirical_requirements: tier 1 (entity list after import — SN-1's fix is directly
  visible on live HA).
repair_dependencies: RF-04 (same files for the sync helpers) first.
confidence: high
```

---

## RF-35 — Stepped-run planning: the engine envelope and the collapse/zone-first traps

```yaml
family_id: RF-35
status: accepted
members: [DQ-DE-5, DQ-Q-1, A5-PP-RP-1, A5-PP-RP-4b_collapse, A5-PP-RP-3, A5-PP-RP-5, DQ-Q-3, A6-PRE-2, A4-START-1, A4-START-2, A4-PP-RP-2, A4-PP-RP-1, A4-PP-RP-4, A4-PP-RP-6, A5-RUNPROF-4, A5-PP-RP-6, DQ-Q-7, DQ-DE-2, A5-PP-RP-7_note, A6-PP-EST-LBL-1]
members_note: A5-PP-RP-4b_collapse = A5-PP-RP-4 (dead all_ids proof rides the same fix).
candidate_root_cause: >
  (i) engine envelopes omit queue_room_ids (DE-5 — root), making the collapse
      fallback's group-union dead and every multi-group plan silently flatten to ONE
      atomic dispatch discarding group sequencing and the per-group step overlay
      (DQ-Q-1/RP-1/RP-4-collapse); a fully-blocked stepped Roborock plan collapses to
      an EMPTY phase list and phases[0] raises IndexError killing the dashboard
      snapshot (RP-3 — HIGH);
  (ii) user-authored leading/trailing charge/wait steps are silently trimmed while the
      card still shows them (RP-5);
  (iii) zone-first plans are permanently unstartable with a false "invalid payload"
      because room_count is validated from phase 0 alone (DQ-Q-3/PRE-2/START-1 — one
      fix, three findings; killed DQ-ACT-4/DQ-PH-4 CONFIRM the preflight fires, so the
      repair is count-over-all-phases + a phase-type branch in start_selected_rooms'
      phase-0 dispatch, START-2);
  (iv) run-profile step semantics: overwrite destroys the step sequence save preserves
      (RP-2 — CRITICAL), apply discards saved per-room settings (RP-1) and leaves no
      record the profile is stepped so a plain Start runs it flat or inherits the map's
      leftover breaks (RP-4); the step overlay bypasses _protected_room_config (RP-6);
      steps schema accepts a bare list (RUNPROF-4); stepped Roborock claims advisory
      order while enforcing it (RP-6-display/RP-8 → RF-18); cleared queue = every room
      (DQ-Q-7); strict_order silently swallowed by single-phase engines (DE-2).
shared_invariant: >
  The phase list preserves authored structure (groups, breaks, zones) end-to-end:
  engines return phases that carry their queue identity; validation sums over ALL
  phases; profile apply/start round-trips steps + per-room settings; an empty phase
  list is a refusal, never an IndexError.
counterevidence_checked: >
  - The trim (RP-5) has a stated rationale ("a break with no clean to bracket") that is
    FALSE for leading charge_wait ("charge to 95 then clean" is coherent) — but a
    LEADING break as phase 0 requires start_selected_rooms to dispatch a non-clean
    phase 0, which the killed findings show preflight refuses today. Fix order matters:
    (iii)'s whole-plan validation must land WITH (ii)'s trim removal, else un-trimmed
    leading breaks become unstartable. Packet sequences them together.
  - DQ-Q-7's empty-queue-means-all is load-bearing for the no-filter path (killed
    guards confirm zero-room STARTS are blocked upstream) — fix narrows semantics at
    the payload builder only for the explicit-empty case; adjudicated per the
    build_room_clean_payload contract.
disposition: repair_independently (coordinated packets over planning/run_plan.py +
  queue engines + profiles/manager.py)
estimated_closure_count: 20
empirical_requirements: tier 2 stepped-run batch on Alfred (SAME runs as RF-11 —
  one capture serves both); Roborock stepped run on Ivy for RP-3/order.
repair_dependencies: RF-11 lands with/after (shared stepped-run validation runs);
  RF-01 first.
confidence: high
```

---

# Rejected candidate families (§G — recorded so they are not re-proposed)

```yaml
- rejected_family: "One global 'absent-vs-empty' helper across all subsystems"
  reason: >
    RF-02 (service-level replace guard), RF-03 (file RMW tri-state), RF-13 (entity
    sentinel three-valued logic), RF-15 (bucket minting) share a SLOGAN, not an
    invariant: their inputs (discovery snapshots, JSON files, HA states, service args)
    and refusal behaviours (refuse-write, skip-update, hold-verdict, raise) are
    incompatible. A shared helper would be a grab-bag encoding four exception sets —
    the §L anti-pattern. Kept as four families.
- rejected_family: "Unify RF-02 with RF-03 (both 'empty wipes store')"
  reason: different evidence classes (absent snapshot vs unreadable file) and different
    correct behaviour on the empty case (RF-02 refuses; RF-03's ABSENT case must still
    seed empty stores on first run). Cross-referenced instead.
- rejected_family: "One 'vocabulary constants' module (all hand-copied literal sets)"
  reason: >
    feedback_centralize_question_not_vocabulary — the fix is per-question helpers that
    already exist (in-flight predicates, BLANK_STATE_VALUES, step_types) plus new ones
    ONLY where a question has an owner (RF-04 ownership, RF-23 caps). A bare shared set
    invites the second generation of hand-maintained logic. ~50% of set divergence is
    deliberate (e.g. pose-sampler CF-2, external_mid_run vs blocked_dock vocabularies —
    A5-STR-1's fix is to CONSULT the second set, not merge them).
- rejected_family: "Coordinate-frame family (A3-EXT-4 outline negation + A2-GEO-* +
    ROBORO-4/5 + POSE frame mix)"
  reason: >
    superficially 'frame math wrong' but each site has a DIFFERENT authority: EXT-4's
    sign must match the FORK's renderer (external contract — fix is to mirror the
    fork's transform, verified against its two consumers); GEO-5/6's half-open vs
    inclusive extents are internal consistency; ROBORO-4's ro_dx=0 claim needs a raw
    hardware payload to disprove (deferred empirical); POSE-1's fix is repointing the
    geometry source, not changing math. No shared repair is better than local ones.
    EXT-4, GEO-3, GEO-5, GEO-6, ROBORO-5 → independent repairs (grouped into the
    mapping-geometry packet for economy); ROBORO-4 → deferred (below).
- rejected_family: "All 'docstring/comment asserts a guard that does not exist' as one
    documentation family"
  reason: the comment is evidence of INTENT per finding — some resolve code-side (WD-4,
    SETUP-9), some doc-side (TRK-7, POSE-6-docstring). Adjudicated per member inside
    their mechanism families; a doc-only sweep would close numbers, not defects.
- rejected_family: "Second-resolution id collisions everywhere (profiles + themes +
    zones + dumps)"
  reason: themes' microsecond variant was KILLED as unreproducible; profiles/run-profiles
    (second resolution, blind assign) and dump filenames ARE reproducible and get
    while-in-store retries locally (RF-19, RF-33); saved-zone reuse-after-delete is a
    referential-integrity case (RF-20). Shared helper unwarranted.
```

# Deferred / empirical (§H-F — with reopen evidence named)

```yaml
- id: DEF-1
  members: [A7-ROBORO-4]
  reason: whether the raw IMAGE-block frame equals the parser's rendered frame needs a
    raw Roborock map payload with a nonzero top/left captured from hardware.
  reopen_when: an Ivy raw-map capture (flight recorder + get_maps dump) shows nonzero
    decoded top/left; then the drift check gains the offset.
- id: DEF-2
  members: [A7-ROBORO-6, A7-ROBORO-7, A7-ROBORO-1, A7-ROBORO-5, A7-ROBORO-3_hash_input_choice]
  reason: ROBORO-1/5/6/7 are source-decidable and small — NOT deferred for evidence,
    only batched into one low-risk packet (listed here because their validation is
    fixture-only; ROBORO-3's hash-input choice rides RF-09's rule).
  note: moved to RF-09/packet batch — kept for traceability.
- id: DEF-3
  members: [A2-POLYGO-6, A2-POLYGO-7]
  reason: CV scoring/feature observations on empirically-tuned code the campaign method
    cannot adjudicate (segmentor excluded by charter). Fix would change tuned behaviour
    with no corpus to validate against.
  reopen_when: a labelled map-image corpus exists (EMPIRICAL_CORPUS_GATE).
- id: DEF-4
  members: [SEG-1_active_boundaries_roundtrip (carried CF-1)]
  reason: changes a persisted record field; deliberate deferral per carried note.
  reopen_when: Chris schedules it; MIGRATION_INSPECTION_GATE applies.
- id: DEF-5
  members: [IO-6_directory_migration_half]
  reason: re-keying the learning archive directory is a data migration
    (MIGRATION_INSPECTION_GATE); interim warn-only fix ships in RF-20.
```

# Singles / document-only / dead-code batch

```yaml
- batch: DOC-ONLY
  members: [DR-BAT-1, DR-BAT-4, DR-ONB-6, A6-PP-EST-TD-1_docstring_half, A3-PORT-8,
    A6-TRK-7, A1-ID-6, A6-PP-EST-GUESS-1_provenance_note, A5-POSE-6, DQ-ZONE-5_doc_half]
  disposition: document_only — docs/dev corrections + docstring truth restoration;
    one packet, mkdocs --strict gate.
- batch: DEAD-CODE
  members: [A1-ID-5, A3-EXT-5, A3-IO-8, INF-3, INF-6, INF-7, SN-8, A1-SERVIC-7_removal_half, DR-DIAG-5]
  disposition: repair_independently (deletions with test coverage of the survivor);
    INF-6 (repairs.py unreachable) additionally needs a Chris decision: delete the
    repair flow or wire the first issue — recommend delete-for-now (idiomatic over
    aspirational).
- batch: SMALL-CORRECTNESS (true singles)
  members: [A3-IO-5, A3-IO-7, DR-BAT-2, DR-BAT-3, A2-GEO-3, A2-GEO-4, A2-GEO-5,
    A2-GEO-6, A3-EXT-3, A3-EXT-4, A4-RB-7, A4-RB-8, A5-POSE-7, A6-AGX-6_note,
    A2-POLYGO-1, A2-POLYGO-3, A2-POLYGO-4, A3-IMAGE--9, A3-IMAGE--11, A4-CUSTOM-3,
    A4-CUSTOM-4, A6-ZONE-C-1, A6-ZONE-C-3, A6-ZONE-C-4, A6-ZONE-C-8_author_note,
    A5-FURNIS-3, A5-FURNIS-5, A5-FURNIS-6, A1-SERVIC-6, DR-MAP-1, DR-MAP-2,
    A3-COMMON-5, A2-CB-3, A2-CB-4, A5-PP-RP-8, A6-PP-EST-H2O-2, A6-PP-EST-CLAMP-1,
    A6-PP-EST-DSP-2_note, A1-EST-5_note, A4-SETUP-6, A4-SETUP-7, A4-SETUP-10,
    A4-SETUP-11, A4-SETUP-13, A4-SETUP-14, A1-WIRE-1, A1-WIRE-2, A2-JOB-9,
    A5-RUNPROF-7, A6-DIAG-3, A6-DIAG-4, A6-ZONE-C-2_ui_note, A5-METRICS-2, A3-REC-5b]
  note: >
    A5-METRICS-2/A3-REC-5 (battery=None, no writer) is ONE repair: subscribe the
    battery entity in job_metrics' watch_map (both adapters declare it) — closes both
    + OBS-B-3. A6-ZONE-C-1 (blank active-map dispatch) + A4-CUSTOM-3/C-4 (backfill
    fail-open) are the "indeterminate ≠ match" rule (RF-13's cousin) applied to
    mapping — grouped into one zone-safety packet with ZONE-C-3 (map_version key:
    implement the documented invalidation stamp on create + check on clean).
    POLYGO-1 (one-pixel growth) fix: trace at pixel centers or subtract the inclusive
    fill (draw at res, trace at res, scale by (res-1)/res is WRONG — packet pins the
    correct half-open contract with a round-trip test).
    A4-SETUP-6 (reject_rooms map-unscoped, no confirmation): add map_id scoping +
    protection-gate parity with delete_map, plus an un-reject service (Chris confirms
    surface).
  disposition: repair_independently, batched by module into packets.
```

---

# Addendum — completeness-check assignments (caught by the matrix validator)

The generated matrix flagged 21 findings absent from every member list. Adjudicated
individually:

```yaml
- family_id: RF-03
  members: [A2-CB-2]
  note: same defect as A1-INIT-2 at the same line seen from the callback side —
    replace-after-await discards concurrent writes; the RF-03 packet's
    "no destructive replace from a pre-await snapshot" rule covers it (merge, don't
    replace, or re-read after the executor hop).
- family_id: RF-06
  members: [A2-JOB-2]
  note: start_zone_clean bypasses every lifecycle gate and dispatches mid-job —
    the "dispatch consults job state" invariant; fix = route through
    get_start_status's blocker evaluation (mid-job → refuse) while keeping its
    documented no-tracking semantics.
- family_id: RF-08
  members: [DQ-ACT-5]
  note: regrade holds at HIGH — the mixed-batch water pre-call IS the safety
    mechanism; when it fails the dispatch must refuse (wet-mop-on-dry-rooms =
    destructive actuation per frozen rubric), matching RF-08's refusal semantics.
- family_id: RF-14
  members: [A3-ROOMS-11, A6-DIAG-7]
- family_id: RF-15
  members: [A4-CUSTOM-1]
  note: a REPLACE-ALL write that cannot name its target layout — "writes name their
    target" is the same addressing invariant; fix = require layout_id (schema +
    services.yaml) with active-layout fallback refused for the destructive replace,
    mirroring upload_map_image's existing contract.
- family_id: RF-18
  members: [A3-ROOMS-6, A3-ROOMS-9]
  note: room-field writes validate values against the brand vocabulary at the boundary
    (the color field's strict validator is the in-file exemplar) — vocabulary comes
    from the adapter catalog, closing the store-vs-wire divergence.
- family_id: RF-19
  members: [A5-FACADE-4]
- family_id: RF-11
  members: [INF-8]
  note: run_plan imports _BREAKS/CLEANING phase sets from step_types (closes with
    RF-11(1)'s phase-type validity fix).
- batch: SMALL-CORRECTNESS-2
  members: [A3-CRUD-7, A4-POSE-6, A4-START-3, A6-VAC-5, DQ-ACT-7, DQ-PAY-7,
    DR-ONB-3, DR-ONB-4, DR-SETUP-2, DR-SETUP-3, DR-SETUP-4]
  note: >
    DR-ONB-3 mirrors the setup/status.py bool(managed) guard onto the onboarding
    summary (the found-sibling technique); DR-ONB-4 derives the two five-key default
    records from one builder; DR-SETUP-2 applies the CS-2 is-not-None guard to
    auto_refresh_on; A4-POSE-6 is the docstring update (goes with the DOC-ONLY pass
    but is code-adjacent, kept here). Batched by module into the same packets as
    SMALL-CORRECTNESS.
```
