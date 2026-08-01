# Tranche-2 Packets — Wave 4: dispatch & planning (RP-021a/b..RP-025)

Conventions per SYNTH-06 header. Sequencing: RP-013a → RP-021a (shared run_plan.py);
RP-024 → RP-025 (same functions). RP-021 split a/b (size, mirroring D14's lesson).

---

## RP-021a — Plan validation & phase structure (RF-35 part 1; Q17 applied)

```yaml
packet_id: RP-021a
family_id: RF-35
finding_ids: ["#7:DQ-Q-3", "#9:A6-PRE-2", "#14:A4-START-1", "#14:A4-START-2",
  "#8:A5-PP-RP-3", "#7:DQ-DE-5", "#7:DQ-Q-1", "#8:A5-PP-RP-1", "#8:A5-PP-RP-4",
  "#8:A5-PP-RP-5", "#7:DQ-Q-7", "#7:DQ-DE-2", "#8:A5-PP-RP-6",
  "#8:A6-PP-EST-LBL-1"]
files: [custom_components/eufy_vacuum/planning/run_plan.py,
  custom_components/eufy_vacuum/queue/queue_engine.py,
  custom_components/eufy_vacuum/queue/dispatch_engines.py,
  custom_components/eufy_vacuum/core/manager.py,
  custom_components/eufy_vacuum/jobs/job_monitor.py,
  custom_components/eufy_vacuum/profiles/manager.py, tests/]
symbols: [_build_steps_phases, _build_effective_start_plan, get_start_status
  payload_room_count, start_selected_rooms phase-0 dispatch,
  engine build_payload/build_phases envelopes, normalize_run_profile_steps
  (validation arm only), _order_advisory]
problem: zone-first plans are permanently unstartable with a false "invalid payload"
  (room_count validated from phase 0 alone — THREE findings, one fix; the killed
  DQ-ACT-4/DQ-PH-4 prove the preflight fires); engine envelopes omit queue identity
  so every multi-group plan silently flattens to ONE atomic dispatch discarding
  group sequencing; a fully-blocked stepped Roborock plan yields an EMPTY phase list
  and phases[0] IndexErrors the whole dashboard snapshot; user-authored
  leading/trailing charge_wait steps are silently trimmed while the card shows them;
  cleared queue means every room; single-phase engines swallow strict_order while
  the caller hides the advisory on the request alone.
required_behavior: >
  (1) Q17 VERBATIM (supersedes trim-removal): leading charge_wait is UNSUPPORTED —
  normalize_run_profile_steps' validation arm REJECTS a leading charge_wait/wait at
  SAVE time (ServiceValidationError, reason leading_break_unsupported) and
  _build_steps_phases EXPLICITLY NORMALIZES any legacy stored one away with an INFO
  log + a `normalized_steps` note in the plan (no silent trim; the card half shows
  the validation message / omits the normalized step — CARD-PLAN stub named).
  Trailing breaks: same treatment. NO non-clean phase-0 state machine.
  (2) zone-first: payload_room_count for get_start_status sums room_count over ALL
  phases, PLUS a phase-0 type branch in start_selected_rooms that routes a zone
  phase 0 through dispatch_zone_clean (mirror phase_runner's existing zone branch)
  — closes DQ-Q-3/PRE-2/START-1/START-2. Zone-first proceeds per Q17.
  (3) engine envelope: build_payload/build_phases return queue_room_ids (the phase's
  own ids) — DE-5; _build_steps_phases' collapse fallback then genuinely unions
  groups; AND the collapse itself is replaced: a multi-group plan with no breaks
  builds ONE PHASE PER GROUP (sequenced) instead of flattening (Q-1/RP-1); the
  group-step settings overlay survives per group (RP-4-collapse half).
  (4) empty phase list → structured refusal from _build_effective_start_plan
  ({blocked: true, reason: no_dispatchable_phases}) — never IndexError (RP-3).
  (5) DQ-Q-7: build_room_clean_payload distinguishes explicit-empty queue_room_ids
  (no rooms → empty payload refused upstream) from None (no filter) — signature
  takes None-vs-list through unchanged.
  (6) DE-2/RP-6: engines report honored_strict_order in the envelope; the advisory
  suppression keys on the ENVELOPE, not the request; stepped Roborock stops claiming
  advisory order (RP-6).
  (7) LBL-1: resolved_rooms carry floor_type so _room_surface_labels resolves
  (one-key addition at build_room_clean_payload).
allowed_changes: listed + tests. prohibited_changes: no phase-runner changes (Wave 2
  landed); no profile apply/save semantics (RP-021b); the _BREAKS import from
  step_types (RP-013a) is the base — rebase on it.
card_half: validation message for rejected leading breaks + normalized-step display —
  new i18n key in en.js + ALL 17 locale packs; `npm run check:i18n` (lesson 3).
compatibility_constraints: saving a profile with a leading break now errors (was
  silently mistruncated at dispatch) — release notes; legacy stored profiles
  normalize loudly, never fail to start.
migration_plan: none (normalization is read-time; storage untouched).
rollback_plan: 4 commits — (a) whole-plan validation + zone phase-0,
  (b) envelope + per-group phases, (c) Q17 validation/normalization + card half,
  (d) advisory/labels/queue semantics. (a)(b)(c) all touch run_plan.py — strict
  order a→b→c, later ones rebase (lesson 4).
reproducer_script: NEW _proof_plan_structure.py — zone-first profile starts (before:
  invalid_payload refusal; after: zone dispatched); [groupA, groupB] plan (before:
  one flat dispatch; after: two sequenced phases); all-blocked stepped plan (before:
  IndexError; after: structured refusal); leading charge_wait save (after:
  ServiceValidationError) + legacy stored (after: normalized + noted).
expected_before: ["zone-first blocked: invalid_payload", "2 groups flattened to 1
  dispatch", "IndexError killed snapshot"]
expected_after: ["zone-first dispatched via zone branch", "2 sequenced group phases",
  "no_dispatchable_phases refusal", "leading_break_unsupported"]
validity_notes: the zone-first before-arm must show the killed findings' behaviour
  (preflight refusal) — pins that DQ-ACT-4/DQ-PH-4's guards stayed real until this
  packet, per REVIEW-05's clean-area obligation.
tests_to_add_or_modify: whole-plan count matrix; per-group phase build; empty-plan
  refusal; Q17 both arms (save-reject + legacy-normalize); envelope
  honored_strict_order; explicit-empty queue.
superseded_tests: the collapse-fallback test that manufactures queue_room_ids the
  engines never emitted (A5-PP-RP-4's finding — now the engines DO emit it: rewrite
  the test against the real envelope, docstring records DE-5); trim tests
  (leading/trailing) — docstring records Q17.
broader_gates: full suite + frontend gates (card half).
hardware_gate: tier 2 — Alfred stepped runs already scheduled (HC-2b); ADD one Ivy
  stepped-order run (per-room phases) validating per-group sequencing on
  honors_clean_order=False hardware.
stop_conditions: [any consumer depends on the flattened single-dispatch shape;
  phase-0 zone dispatch needs pre-calls the zone branch doesn't perform — report,
  do not improvise]
escalation_target: main agent → Chris
```

---

## RP-021b — Run-profile round trip (RF-35 part 2)

```yaml
packet_id: RP-021b
family_id: RF-35
finding_ids: ["#8:A4-PP-RP-2", "#8:A4-PP-RP-1", "#8:A4-PP-RP-4", "#8:A4-PP-RP-6",
  "#13:A5-RUNPROF-4"]
files: [custom_components/eufy_vacuum/profiles/manager.py,
  custom_components/eufy_vacuum/services/run_profiles.py,
  custom_components/eufy_vacuum/planning/run_plan.py, tests/]
symbols: [overwrite_run_profile, apply_run_profile, save_run_profile,
  normalize_run_profile_steps, _build_steps_phases overlay]
problem: overwrite_run_profile unconditionally destroys the step sequence save
  preserves (CRITICAL — same snapshot contract, opposite behaviour); apply discards
  the per-room settings the profile was saved with (falls back to whatever rooms are
  set to now) and leaves no record the profile is stepped, so a plain Start runs it
  flat or inherits the map's unrelated leftover breaks; the step overlay is the one
  dispatch path skipping _protected_room_config; the steps schema accepts a bare
  list.
required_behavior: >
  (1) RP-2: overwrite re-snapshots steps exactly as save does (get_queue_steps when
  has_breaks) — the "discard STALE steps" comment replaced with the contract.
  (2) RP-1: apply restores the PROFILE's saved per-room settings (profile["rooms"]
  snapshots) onto the rooms it enables — the design the save-side comment states;
  step room_groups stay id-only.
  (3) RP-4: apply stamps map_bucket["applied_run_profile"] = {id, stepped: bool,
  applied_at}; _build_effective_start_plan prefers the applied profile's steps over
  the map's leftover queue_breaks when the stamp is fresh (cleared on start/step
  edit) — a plain Start after apply runs the profile as authored.
  (4) RP-6: the _build_steps_phases per-group overlay routes merged rooms through
  protected_room_config (closing the one unprotected dispatch path).
  (5) RUNPROF-4: steps schema validates per-element shape (vol.Schema per step
  type); silently-dropped malformed steps become a structured refusal listing them
  (Q9 caller-error class).
blocked_by: RP-021a (same files; envelope semantics).
compatibility_constraints: apply now changes room settings to the PROFILE's saved
  values (previously kept current values) — this IS the documented contract; release
  notes. applied_run_profile is additive storage.
rollback_plan: 3 commits — (a) overwrite/save parity, (b) apply restore + stamp +
  plan preference, (c) overlay protection + schema. (b)+(c) share run_plan.py.
reproducer_script: NEW _proof_profile_roundtrip.py — stepped profile: overwrite
  (before: steps=[] flat; after: steps preserved); apply→Start (before: flat or
  leftover breaks; after: authored steps); saved quiet-bedroom settings (before:
  current-room settings dispatched; after: profile settings dispatched).
expected_before: ["overwrite destroyed steps", "plain Start ran flat",
  "apply kept current settings"]
expected_after: ["steps preserved on overwrite", "Start ran authored steps",
  "profile settings restored"]
tests_to_add_or_modify: overwrite/save parity; apply restore matrix; stamp
  freshness/clear; overlay protection; schema per-type validation.
superseded_tests: tests pinning overwrite's steps=[] or apply's
  current-settings fallback — docstrings record the round-trip contract.
broader_gates: full suite. hardware_gate: rides HC-2b (apply a stepped profile,
  plain Start, verify authored execution in the capture).
stop_conditions: [profile["rooms"] snapshots missing on legacy stored profiles —
  report count; fall back to current-settings for THOSE with an INFO log, do not
  invent settings]
escalation_target: main agent → Chris
```

---

## RP-022 — Declared caps on every branch; Q12 zone repeats (RF-23)

```yaml
packet_id: RP-022
family_id: RF-23
finding_ids: ["#7:DQ-ZONE-1", "#7:DQ-PAY-4", "#13:A2-JOB-4", "#18:A1-SERVIC-3",
  "#7:DQ-ZONE-3", "#7:DQ-ZONE-4", "#18:A6-ZONE-C-8", "#14:A3-SNAP-4",
  "#7:DQ-ZONE-2", "#7:DQ-ZONE-5"]
files: [custom_components/eufy_vacuum/dispatch/manager.py,
  custom_components/eufy_vacuum/adapters/eufy/adapter.py,
  custom_components/eufy_vacuum/core/manager.py,
  custom_components/eufy_vacuum/mapping/mapping_services.py, src/, tests/]
symbols: [dispatch_zone_clean cap resolution, eufy adapter capabilities block,
  get_dashboard_snapshot zone_max/zone_bounds, _handle_create_saved_zone]
problem: clamps live inside coordinate-space branches — Eufy ships clean_times
  verbatim while THREE schema comments claim dispatch enforces a ceiling; area
  bounds only in device_mm, side bounds only in the else, regardless of declaration;
  Eufy's side check silently skips on unreadable dims while the sibling branch
  refuses; zone size unchecked at author time; the snapshot invents zone_max=10
  while dispatch enforces none; supports_zone_clean consulted by the card only;
  zone_bounds shipped with no consumer.
required_behavior: >
  (1) Q12 VERBATIM (supersedes clamp-to-2): Eufy zone repeats are UNSUPPORTED —
  the Eufy adapter declares zone repeats unsupported (omits zone_passes_max +
  explicit supports_zone_repeat: false); dispatch NORMALIZES Eufy zone
  clean_times>1 to 1 with a WARNING; the card hides the repeat control for brands
  declaring unsupported (card half: capability-driven visibility — CARD-PLAN stub;
  no i18n needed, control removal only). Roborock's device_mm clamp unchanged.
  (2) cap resolution HOISTED above the coordinate-space branch: zone_max,
  min/max area AND side bounds all resolved from the declaration once and enforced
  on EVERY branch (ZONE-3); undeclared bound = unenforced (no invented defaults —
  SNAP-4's snapshot reads the same resolution, no more hardcoded 10).
  (3) ZONE-4: unreadable live dims on the normalized branch REFUSE (parity with the
  mm branch's existing refusal) — behaviour change flagged (Eufy zone cleans fail
  loudly when the live map is unavailable).
  (4) ZONE-2: dispatch_zone_clean consults supports_zone_clean and refuses when
  false. (5) ZONE-C-8: create_saved_zone advisory-checks size against the same
  resolution (warning in response, save proceeds — author-time is advisory, dispatch
  enforces). ZONE-5 closes: the card consumes zone_bounds for draw-time hints
  (card half, same stub).
compatibility_constraints: Eufy clean_times>1 now normalizes to 1 (was sent
  verbatim to firmware with unknown behaviour) — release notes; unreadable-dims
  refusal is new user-visible behaviour.
rollback_plan: 3 commits — (a) hoisted resolution + branch parity, (b) Q12
  declaration + normalization, (c) author-time advisory + snapshot/card. (a)+(b)
  share dispatch/manager.py.
reproducer_script: NEW _proof_zone_caps.py — Eufy zone clean_times=5 (before: 5 on
  wire; after: normalized 1 + warning); declared side bound violated on the mm
  branch fixture (before: ignored; after: refused); unreadable dims (before: silent
  skip; after: refusal).
expected_before: ["clean_times=5 shipped", "declared bound ignored on other branch"]
expected_after: ["normalized to 1 (zone repeats unsupported)", "bound enforced both
  branches", "unreadable dims refused"]
tests_to_add_or_modify: resolution matrix (declared/undeclared × branch); Q12
  normalization; author-time advisory; snapshot parity with dispatch.
superseded_tests: any test pinning the device_mm-only clamp or the snapshot's 10.
broader_gates: full suite + frontend gates (card half).
hardware_gate: tier 2 — one Alfred zone clean (normalization visible in span) on
  the Wave-4 batch; Ivy zone clean already validated in tranche 1's HC runs.
stop_conditions: [Eufy firmware behaviour for clean_times>1 becomes verifiable —
  per Q12 that's a future independent declaration, not this packet]
escalation_target: main agent → Chris
```

---

## RP-023 — Access graph: one answer, a verdict, delta gates, coded issues (RF-26 + RF-27)

```yaml
packet_id: RP-023
family_id: RF-26 (+RF-27)
finding_ids: ["#10:A5-AG-1", "#8:A6-PP-EST-BLK-1", "#10:A5-AG-2", "#10:A6-AGX-1",
  "#10:A6-AGX-2", "#10:A6-AGX-3", "#10:A6-AGX-5", "#10:A6-AGX-6", "#10:A6-AGX-4",
  "agent: infra (2-lens verified):INF-9", "agent: platforms (2-lens verified):EP-5"]
files: [custom_components/eufy_vacuum/rooms/access_graph.py,
  custom_components/eufy_vacuum/planning/run_plan.py,
  custom_components/eufy_vacuum/core/manager.py,
  custom_components/eufy_vacuum/entity_helpers.py,
  custom_components/eufy_vacuum/button.py, src/state/room-access.js,
  src/bindings/room-access.js, src/i18n/en.js,
  custom_components/eufy_vacuum/frontend/locales/, tests/]
symbols: [NEW access_graph.compute_reachability, get_access_graph_health,
  _validate_room_access_graph, update_room_fields gate, get_room_access_editor,
  _format_access_graph_issue → issue codes, get_floor_type_label,
  EufyVacuumSavedRunProfileButton name, accessEditableRooms]
problem: reachability is re-implemented divergently (preflight graph-scoped, mid-run
  queue-scoped — a queued room whose transit parent is unselected reports blocked
  and can CANCEL the job); one unconfigured room makes the whole graph 'partial'
  blocking every run with no room named; no verdict distinguishes allow-everything
  from block-everything; the structural gate rejects UNRELATED per-room edits; the
  editor blames candidates for pre-existing violations and drops graph-scoped
  issues; every issue message is hard-coded English rendered verbatim in 18 locales;
  floor labels + a button name are English literals; the card renders a dock-room
  edge as "Missing Room N".
required_behavior: >
  (1) ONE exported compute_reachability(rooms, graph, mode=global|queue_projection)
  where queue_projection seeds from GLOBAL reachability then projects (AG-1/BLK-1);
  both call sites repoint.
  (2) AG-2 (regraded HIGH): a non-dock room with no inbound edge = per-room WARNING
  + that room excluded from graph-gated runs; NOT a map-wide block. ESCALATION NOTE:
  this semantics change was recommended in synthesis but was NOT a numbered Gate-4
  question — Chris reviews this packet's semantics line before assignment
  (stop_condition below).
  (3) graph state exposes a verdict (allow_all | partial_block | blocked_all +
  offending rooms); health report carries it (AGX-1).
  (4) AGX-2: update_room_fields validates structurally ONLY when the edit touches
  access fields (delta-scoped); AGX-3: editor computes baseline-vs-candidate diff
  and blames only introduced issues; AGX-5: per-room editor carries graph_issues
  alongside room_issues.
  (5) RF-27: issue messages become CODES + params; the card translates (new i18n
  namespace in en.js + ALL 17 locale packs — the 9 issue codes × 18 locales is THE
  card half, budgeted; `npm run check:i18n`). INF-9: floor labels via translation
  keys (backend returns the floor_type code; card already has setup.floor_* keys).
  EP-5: the saved-run-profile button gains a translation key.
  (6) AGX-6: accessEditableRooms stops filtering the dock room out before the
  selected-target check (renders the real room, not "Missing Room N").
compatibility_constraints: service responses swap message→code+params — the card
  half ships IN THIS PACKET (bindings prefer code; legacy message kept one release
  as fallback field).
rollback_plan: 4 commits — (a) reachability + repoints, (b) verdict + AG-2 +
  editor/delta, (c) codes + i18n + card, (d) INF-9/EP-5/AGX-6.
reproducer_script: NEW _proof_reachability.py — queued room with unselected transit
  parent mid-run (before: blocked + cancel path; after: reachable); unconfigured
  new room (before: map-wide block; after: warning + room excluded); unrelated
  color edit on a broken graph (before: rejected; after: saved).
expected_before: ["mid-run reported transit-parented room blocked", "one room
  blocked the whole map", "color edit rejected by graph"]
expected_after: ["queue projection seeds global", "warning + single-room exclusion",
  "delta-scoped gate passed"]
tests_to_add_or_modify: reachability parity (two modes, shared core); verdict
  matrix; delta gate; editor diff; code+params round-trip; i18n key coverage.
superseded_tests: queue-scoped walk pins; map-wide-block pins (docstring records
  the AG-2 decision once Chris confirms).
broader_gates: full suite + frontend gates.
hardware_gate: tier 1 (HC-5 card walk: graph editor + issue rendering in a non-EN
  locale).
stop_conditions: [BEFORE ASSIGNMENT: Chris confirms the AG-2 warning+exclude
  semantics (unnumbered decision); any automation consumes the English message
  strings]
escalation_target: main agent → Chris
```

---

## RP-024 — Resolution precedence, safety clamps, and the custom-snap (RF-19; Q2+Q3)

```yaml
packet_id: RP-024
family_id: RF-19
finding_ids: ["#8:A1-PP-RES-2", "#8:A3-PP-CRUD-2", "#8:A6-PP-EST-DSP-1",
  "#8:A6-PP-EST-DSP-2", "#7:DQ-PAY-2", "#8:A1-PP-RES-4", "#8:A6-PP-EST-H2O-1",
  "#8:A1-PP-RES-3", "#8:A1-PP-RES-7", "#8:A3-PP-CRUD-5", "#8:A3-PP-CRUD-8",
  "#8:A4-PP-RP-5", "#14:A5-FACADE-4"]
files: [custom_components/eufy_vacuum/profiles/room_profiles.py,
  custom_components/eufy_vacuum/profiles/manager.py,
  custom_components/eufy_vacuum/adapters/roborock/vocabulary.py, tests/]
symbols: [resolve_room_profile_for_room, _match_profile_from_fields,
  FLOOR_TYPE_WATER_DEFAULTS (both), save_user_room_profile,
  _generate_room_profile_id/_generate_run_profile_id, save_room_profile_from_room]
problem: water_level (and carpet fan) resolve floor-default-OVER-profile while every
  sibling field is room-over-profile — the just-applied mop profile immediately
  re-labels "custom" because the match candidate lacks a water key; granite/concrete
  are selectable with NO water default so "" reaches the wire; path_type=None
  backfill becomes the string "None" on the Eufy wire; dangling profile refs resolve
  silently to the default; save-as-profile drops path_type; second-resolution ids
  with no exists check silently overwrite; the facade's user_1 default overwrites.
required_behavior: >
  (1) Q2 VERBATIM: explicit room value > selected profile value > brand/floor
  default only-when-absent; floor SAFETY applied AFTERWARD as an explicit clamp
  (carpet may force water off + fan behaviour); ordinary hard-floor defaults never
  override an explicit profile value. resolve_room_profile_for_room restructured to
  that ladder + clamp stage; _match_profile_from_fields candidates built with the
  profile's FULL field set (incl. water) so match compares like-for-like (kills the
  custom-snap: CRUD-2, DSP-1/2).
  (2) Q3 VERBATIM: granite/concrete added to BOTH brands' water-defaults tables at
  the brand's tile/marble value; never ""/None/forced-off; the mop-with-no-water
  correction can no longer produce "" (PAY-2/RES-4/H2O-1).
  (3) RES-3: path_type present-with-None falls through to the profile (treat None
  as absent in the ladder); the startup backfill stops seeding path_type=None
  (leaves the key absent).
  (4) RES-7: a dangling profile_name resolves to default WITH a
  resolved_fallback=True flag in the effective details (display honesty; RP-016
  ends new danglers).
  (5) CRUD-5: save_room_profile_from_room carries path_type verbatim (derivation
  only when the room lacks it). CRUD-8/RP-5/FACADE-4: id generators gain a
  `while id in store` counter suffix; the facade's omitted-name path mints a unique
  id like its sibling.
blocked_by: none (RP-025 depends on THIS).
compatibility_constraints: resolution outcomes change where floor defaults were
  overriding explicit profile water — the Q2 contract; release notes with a
  worked example. Golden resolution fixtures pinned BEFORE the edit (REVIEW-05
  clean-area obligation).
rollback_plan: 3 commits — (a) ladder + clamp + match candidate, (b) Q3 tables +
  path_type, (c) round-trip + ids.
reproducer_script: NEW _proof_precedence.py — vacuum_mop_quick on hardwood (before:
  water floor-default 'Low' overrode profile 'Medium', re-labelled custom; after:
  'Medium', label sticks); granite mop room (before: water ""; after: tile value);
  carpet still clamps to Off.
expected_before: ["profile water overridden by floor default", "custom-snap",
  "granite water=''"]
expected_after: ["explicit ladder + clamp", "profile label sticks",
  "granite water=<brand tile value>", "carpet clamp preserved"]
tests_to_add_or_modify: ladder matrix per field; clamp stage; match like-for-like;
  Q3 both brands; None-as-absent; id uniqueness.
superseded_tests: RES-2's asymmetric-precedence pins — docstrings record Q2.
broader_gates: full suite. hardware_gate: tier 1 (profile apply on live card, label
  persistence) on HC-5.
stop_conditions: [golden fixtures reveal a resolution the ladder cannot express —
  stop with the case]
escalation_target: main agent → Chris
```

---

## RP-025 — The catalog is the vocabulary (RF-18) — blocked_by RP-024

```yaml
packet_id: RP-025
family_id: RF-18
finding_ids: ["#7:DQ-Q-4", "#8:A1-PP-RES-6", "#8:A2-PP-CAP-2", "#8:A1-PP-RES-8",
  "#8:A2-PP-CAP-7", "#7:DQ-PAY-1", "#8:A3-PP-CRUD-1", "#8:A3-PP-CRUD-4",
  "#7:DQ-Q-2", "#8:A1-PP-RES-5", "#8:A2-PP-CAP-4", "#7:DQ-PAY-6",
  "#8:A3-PP-CRUD-7", "#7:DQ-Q-6", "#8:A2-PP-CAP-6", "#8:A2-PP-CAP-3",
  "#8:A3-PP-CRUD-6", "#8:A2-PP-CAP-1", "#8:A5-PP-RP-7", "#8:A5-PP-RP-8",
  "#14:A1-INIT-5", "#16:A1-EST-7", "#16:A1-EST-8", "#13:A6-DIAG-8", "#7:DQ-PAY-5",
  "#13:A3-ROOMS-6", "#13:A3-ROOMS-9", "agent: platforms (2-lens verified):EP-8",
  "#8:A6-PP-EST-TD-1", "#8:A1-PP-RES-9", "#12:A2-LIFE-3"]
files: [custom_components/eufy_vacuum/profiles/room_profiles.py,
  custom_components/eufy_vacuum/profiles/manager.py,
  custom_components/eufy_vacuum/planning/run_plan.py,
  custom_components/eufy_vacuum/core/manager.py,
  custom_components/eufy_vacuum/learning/estimator.py,
  custom_components/eufy_vacuum/listeners/lifecycle.py,
  custom_components/eufy_vacuum/dock/manager.py,
  custom_components/eufy_vacuum/services/dock.py,
  custom_components/eufy_vacuum/services/rooms.py,
  custom_components/eufy_vacuum/queue/queue_engine.py,
  custom_components/eufy_vacuum/room_entities.py, tests/]
symbols: [resolve_profile_catalog, normalize_room_profile, get_room_profiles,
  _match_profile_from_fields, get_effective_room_details, apply_room_profile,
  _protected_room_config, apply_capability_gate, get_available_profile_names,
  _settings_profile_display, startup backfill, _load_mop_wash_config, is_mop,
  _wash_triggers, dock event vocab, _write_room_field, update_room_fields
  vocabulary validation]
problem: the brand catalog exists but (i) normalize_room_profile's third-level
  literals ("Max"/"Off"/"Quick") fire exactly when a brand DELIBERATELY omits an
  axis; (ii) `or`-fallbacks make declared-EMPTY blocks indistinguishable from
  absent; (iii) ProfileManager's entry points never thread the catalog they have in
  hand (the catalog parameter is structurally inert on every production call);
  (iv) protected/gate stamp Eufy display literals for framework concepts;
  clean_intensity has no capability flag; protected names frozen from Eufy
  builtins; (v) hardcoded four-key display sets; Eufy literals in the backfill,
  estimator wash bounds, is_mop set, lifecycle wash vocabulary, dock event vocab;
  value_map fail-open; room-field writes accept any vocabulary string.
required_behavior: >
  (bounded by the four killed lookalikes: stored rooms ALWAYS materialize keys —
  every edit below is on the catalog/profile path, none on stored-room-absent-key
  premises)
  (i) normalize_room_profile third arms become brand-neutral: "" for display-axis
  fields (fan/water/intensity), framework canonicals stay ("wide"/1/False/"vacuum").
  (ii) resolve_profile_catalog uses `key in block` — declared-empty honored
  (RES-8/CAP-7).
  (iii) get_room_profiles/_match_profile_from_fields/get_effective_room_details
  gain vacuum_entity_id→catalog threading (the sites have it in scope);
  apply_room_profile's already-resolved catalog becomes live (CAP-1's inertness
  ends).
  (iv) _protected_room_config + apply_capability_gate take the catalog and write
  ITS no-water/default tokens (safety SEMANTICS unchanged — the carpet/non-mop
  clamps still fire, killed-RES-1's rescue preserved); clean_intensity gated on a
  new supports_clean_intensity capability (Eufy true, Roborock absent→false);
  protected names = catalog builtins ∪ framework four (CRUD-6).
  (v) display sets from the catalog (RP-7/RES-5/CAP-4); backfill uses
  room_defaults' brand answer (INIT-5); estimator reads wash_frequency_bounds from
  the adapter (EST-7) and canonicalizes is_mop via _canonical_clean_mode (EST-8);
  lifecycle wash detector delegates to dock_events' adapter-driven vocabulary
  (LIFE-3 vocab half; edge half = RP-038); dock event types derive from the
  adapter declaration at all three sites (DIAG-8); _write_room_field logs WARNING
  on an unmapped value (fail-open kept, loud — PAY-5); update_room_fields
  validates clean_mode/fan_speed against the adapter vocabulary
  (ServiceValidationError, Q9 caller-error class — ROOMS-6/9); EP-8's defaults
  derive from DEFAULT_ROOM_PROFILE_NAME/catalog; TD-1/RES-9 docstring+dead-branch
  cleanups ride along.
compatibility_constraints: Roborock rooms stop ACQUIRING Eufy literals via apply
  paths; EXISTING stored literals are CF-3 (named, not closed here). Golden
  per-brand resolution fixtures pinned BEFORE edit.
rollback_plan: 5 commits by mechanism group (i/ii, iii, iv, v-display+backfill,
  v-consumers). Groups share room_profiles.py/manager.py — strict order, rebases.
reproducer_script: NEW _proof_catalog_vocab.py — Roborock apply_room_profile
  (before: "Quick"/"Off"/"Max" written; after: brand values/omissions); declared
  empty builtins honored; update_room_fields fan_speed='Turbo' refused.
expected_before: ["Roborock room acquired Quick", "empty block inherited Eufy",
  "Turbo accepted silently"]
expected_after: ["brand vocabulary only", "declared-empty honored",
  "Turbo refused: not in adapter vocabulary"]
tests_to_add_or_modify: per-brand golden resolutions; declared-empty matrix;
  capability gate for intensity; vocabulary validation; wash-vocab delegation.
superseded_tests: tests pinning the Eufy literals in normalize/gate/protected
  paths — docstrings record the catalog contract.
broader_gates: full suite. hardware_gate: tier 1 — Ivy: apply a profile, inspect
  the stored room on live HA (no Eufy literal acquisition) on HC-5.
stop_conditions: [any wire payload changes for EUFY in the golden fixtures (the
  purge must be Eufy-invisible); a brand token needed by the clamp has no catalog
  key — report, do not invent]
escalation_target: main agent → Chris
```
