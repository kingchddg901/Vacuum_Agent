# Tranche-2 Packets — Wave 6: service surface & platform (RP-031..RP-040) + card stubs

Conventions per SYNTH-06 header. Sequencing: RP-031 → RP-032 (gate after content);
RP-033 independent; RP-034/035/036/037/038 independent; RP-039 last-but-one;
RP-040 last. RP-037 blocked_by RP-013c.

---

## RP-031 — Service failure convention applied per module (RF-14 + RF-05; Q9)

```yaml
packet_id: RP-031
family_id: RF-14 (+RF-05)
finding_ids: ["#13:A2-JOB-1", "#13:A2-JOB-3", "#13:A2-JOB-7", "#13:A3-ROOMS-5",
  "#13:A3-ROOMS-7", "#13:A3-ROOMS-10", "#13:A3-ROOMS-11", "#13:A4-SETUP-4",
  "#13:A4-SETUP-7", "#13:A4-SETUP-8", "#13:A4-SETUP-12", "#13:A5-RUNPROF-1",
  "#13:A5-RUNPROF-2", "#13:A5-RUNPROF-3", "#13:A5-RUNPROF-5", "#13:A5-RUNPROF-6",
  "#13:A6-DIAG-1", "#13:A6-DIAG-2", "#13:A6-DIAG-3", "#13:A6-DIAG-6",
  "#13:A6-DIAG-7", "#13:A6-DIAG-9", "#16:A5-SVC-3", "#16:A5-SVC-4",
  "#8:A4-PP-RP-3", "#8:A4-PP-RP-7", "#17:A1-CRUD-7",
  "agent: platforms (2-lens verified):EP-1", "#14:A6-VAC-2", "#13:A1-WIRE-1",
  "#13:A1-WIRE-2", "#13:A2-JOB-9", "#13:A5-RUNPROF-7", "#13:A4-SETUP-10",
  "#13:A4-SETUP-11", "#13:A4-SETUP-13", "#13:A4-SETUP-14", "#13:A6-DIAG-4",
  "#13:A2-JOB-5", "#13:A2-JOB-6", "#13:A2-JOB-8_response_note"]
files: [custom_components/eufy_vacuum/services/ (all modules),
  custom_components/eufy_vacuum/learning/services.py,
  custom_components/eufy_vacuum/profiles/manager.py,
  custom_components/eufy_vacuum/themes/manager.py,
  custom_components/eufy_vacuum/dock/manager.py,
  custom_components/eufy_vacuum/button.py, src/, tests/]
problem: refusals are dropped at service/entity boundaries — DEBUG-logged results,
  reason-literal gates, success-shaped empty responses, saved:true no-ops, dock
  "action sent" for presses HA dropped; apply/start flows commit destructive
  selection changes BEFORE authorization with no rollback; saves sit outside the
  failure paths so memory/disk diverge.
required_behavior: >
  Q9 VERBATIM taxonomy, applied module-by-module with a per-handler table (the
  packet's appendix enumerates all ~60 handlers × class):
  - OPERATIONAL/automation-common (start_*, retry, apply, clean_*): structured
    {success:false, reason:...} responses; supports_response=True on every one;
    NEVER raise on refusal; callers branch on FLAGS (all reason-literal gates
    replaced — RUNPROF-2/5/6's exact defect).
  - CALLER ERROR (bad input, unknown target): ServiceValidationError.
  - ADMIN/DESTRUCTIVE config mutations (delete/overwrite/reset): raise
    HomeAssistantError on internal failure; refusals as ServiceValidationError.
  Plus RF-05 ordering per site: 05a (validate-then-mutate: start_run_profile,
  retry_missed_rooms, apply_run_profile refuse BEFORE the selection wipe — snapshot
  not needed once ordering is right); 05b (save-with-mutation: job_control saves
  move inside the success path with the landed-mutation persisted on HANDLED
  errors — the JOB-7 rule; DIAG-9's three write services mutate-then-save
  atomically with rollback-on-save-failure). DIAG-1/VAC-2: dock actions verify the
  pressed entity had a live state; EP-1: the reset button inspects the result and
  writes an error attribute instead of silent success. DIAG-2: repr(err) sinks
  routed through the redactor. WIRE-1: get_manager captured once per handler
  invocation. SETUP-7/DIAG-7/JOB-9/RUNPROF-7: unresolvable map_id becomes
  ServiceValidationError (the resolver's documented contract made true).
  DQ-ACT-6 disposition: the pre-call device-state restore is WONTFIX per REVIEW
  (best-effort restore attempt + log only) — recorded here, needs Chris's ack at
  review of this packet.
card_half: >
  CF-5 UNBLOCKS HERE (the two failure-renders-as-success paths): the card's
  core.js action wrapper consumes {success:false, reason} for the operational
  class — card packet CARD-PLAN §1 (stub below) ships with or immediately after
  this packet; every new reason string is a CODE with i18n keys in en.js + ALL 17
  locale packs (lesson 3; check:i18n gates).
rollback_plan: ONE COMMIT PER SERVICE MODULE (8 commits) — job_control, rooms,
  run_profiles, setup, maintenance+dock, learning, themes, entity-layer. No two
  modules in one commit; the handler table maps commit→handlers.
reproducer_script: NEW _proof_service_contract.py — table-driven over the handler
  matrix: each refusal path asserts its class (response-flag / SVE / HAE) and that
  no mutation persisted on refusal.
expected_before: ["refusal dropped (None returned)", "success-shaped no-op",
  "selection wiped on blocked start"]
expected_after: ["success:false surfaced", "SVE on caller error",
  "no mutation before authorization"]
tests_to_add_or_modify: per-handler class conformance (generated table test —
  asserts every registered mutation handler declares supports_response or raises);
  ordering tests for 05a/05b sites.
superseded_tests: every test pinning silent-refusal returns — docstrings cite Q9.
broader_gates: full suite + frontend gates.
hardware_gate: tier 1 (HC-5 card walk — refusal toasts render localized).
stop_conditions: [a handler class assignment is ambiguous under Q9 — list, ask;
  any automation-common service raising today whose raise an automation may rely
  on (grep docs)]
escalation_target: main agent → Chris
```

---

## RP-032 — The declaration parity gate (RF-28) — blocked_by RP-031

```yaml
packet_id: RP-032
family_id: RF-28
finding_ids: ["#13:A3-ROOMS-4", "#14:A5-FACADE-5", "#13:A1-WIRE-3",
  "#13:A4-SETUP-15", "#18:A1-SERVIC-5_yaml_half", "#18:A1-SERVIC-6_gate_note",
  "#18:A1-SERVIC-7", "#16:A5-SVC-9", "#13:A2-JOB-5", "#13:A2-JOB-6",
  "#13:A1-WIRE-4", "#13:A3-ROOMS-3", "#18:A6-ZONE-C-7_schema_note",
  "#18:A4-CUSTOM-7", "#18:A3-IMAGE--10", "#18:A1-SERVIC-4"]
files: [tests/ (the gate), custom_components/eufy_vacuum/services.yaml,
  every schema module the gate flags, docs/advanced/03-services.md]
problem: services.yaml advertises fields the schemas reject (carpet ×2,
  floor_types); 16+ registered services have no descriptor; docs mark required
  fields optional; 19 dead schemas incl. near-twin traps; break-schema round trip
  fails validation; one registration has no schema.
required_behavior: >
  (1) THE GATE (contract test, the expansion-ready-seam pattern): loads
  services.yaml + walks every hass.services.async_register call (AST) and asserts —
  every registered service has a schema; every service has a services.yaml entry
  OR is on the reviewed INTERNAL_SERVICES allowlist (checked in, with a comment
  per entry — Chris reviews the list at this packet's review); every services.yaml
  field exists in the schema with matching required-ness; no dead schemas
  (defined-unreferenced fails). Runs in the normal suite.
  (2) content fixes to green: carpet fields, floor_types (add to schema — the
  manager accepts it), the 16 descriptors (or allowlist), map_id
  optionality alignment (with RP-028's resolver adoption), JOB-5/6 break-schema
  round trip (get_queue_steps shape accepted by set_queue_breaks), WIRE-4 schema
  added, dead-schema deletion (SERVIC-7), docs table sync (SVC-9), zone kind
  vol.In, CUSTOM-7/IMAGE--10 prose+descriptors, SERVIC-4 degenerate-drop parity.
rollback_plan: 2 commits — (a) the gate (allowed to fail-list initially via an
  expected-failures file), (b) content fixes + empty the failure list. Gate stays.
reproducer: the gate IS the proof (before: N failures enumerated; after: 0).
expected_before: ["parity gate: 40+ violations"]
expected_after: ["parity gate: 0 violations, allowlist N entries"]
superseded_tests: none (additive gate).
broader_gates: full suite + mkdocs --strict (docs touched).
hardware_gate: none.
stop_conditions: [a services.yaml field the schema SHOULD reject by design —
  document in the allowlist mechanism, don't silently widen schemas]
escalation_target: main agent → Chris
```

---

## RP-033 — Adapter-config seam hardened (RF-32)

```yaml
packet_id: RP-033
family_id: RF-32
finding_ids: ["#13:A4-SETUP-2", "#13:A4-SETUP-3", "#13:A4-SETUP-5",
  "#13:A4-SETUP-9", "#7:DQ-DE-4", "#7:DQ-DE-3", "#14:A6-VAC-3", "#12:A4-POSE-4",
  "#12:A3-COMMON-2", "#9:A1-WD-5_validation_half"]
files: [custom_components/eufy_vacuum/services/adapter_config.py,
  custom_components/eufy_vacuum/adapters/registry.py,
  custom_components/eufy_vacuum/adapters/config_schema.py,
  custom_components/eufy_vacuum/queue/dispatch_engines.py,
  custom_components/eufy_vacuum/dispatch/manager.py,
  custom_components/eufy_vacuum/core/manager.py, tests/]
problem: save_adapter_config accepts a two-key config and registers it OVER the
  live code adapter — every omitted block silently resolves to Eufy behaviour;
  delete unregisters the LIVE adapter leaving none; persist-before-validate;
  setup.steps never validated despite three claims; absent dispatch.template →
  Eufy engine silently; the documented no-command envelope unreachable;
  capability refresh drops probe-only candidates; tuning values unclamped at
  registration.
required_behavior: >
  (1) ADAPTER_CONFIG_SCHEMA (exists, test-only today) applied at save time —
  violations ServiceValidationError (Q9); registration HARD-raises on: missing
  required blocks, unknown dispatch.template, absent template on a stored config
  (DE-4 — code adapters keep the legacy default with a deprecation log),
  unknown setup.steps (SETUP-9 — the three claims become true), non-positive
  tuning/timing values (POSE-4/WD-5 halves; runtime clamps from RP-011 stay as
  defense), completion.require_job_active_clear without a declared job_active
  entity (COMMON-2 → registration warning + flag ignored at runtime).
  (2) validate THEN persist (SETUP-5); delete_adapter_config removes the stored
  row AND re-registers the CODE adapter (SETUP-3).
  (3) DE-3: an explicit `command: null` produces the direct envelope (documented
  behaviour implemented); absent still defaults with the deprecation log.
  (4) VAC-3: refresh_vacuum_capabilities re-supplies the adapter's
  entity_candidates (probe keys included) — the comment becomes true.
compatibility_constraints: previously-saved invalid configs REFUSE to register at
  startup → the code adapter stays live + a repair-style WARNING names the stored
  row (better than silent-Eufy; release notes).
rollback_plan: 3 commits — (a) schema-at-save + validate-then-persist,
  (b) registration raises + delete restore, (c) DE-3/VAC-3/flag checks.
reproducer_script: NEW _proof_adapter_seam.py — two-key config save (before:
  registered over live, omitted blocks→Eufy; after: SVE listing missing blocks);
  delete (before: no adapter; after: code adapter restored).
expected_before: ["two-key config shadowed live adapter", "delete left no adapter"]
expected_after: ["save refused: missing blocks", "code adapter restored"]
tests_to_add_or_modify: schema-at-save matrix; startup invalid-stored handling;
  delete restore; steps validation; DE-3 envelope.
superseded_tests: warn-only registration pins — docstrings record the raise
  contract.
broader_gates: full suite. hardware_gate: tier 1 reload check (HC-5).
stop_conditions: [Chris's live box has a stored adapter config that would refuse —
  check FIRST via diagnostics; if present, coordinate before landing]
escalation_target: main agent → Chris
```

---

## RP-034 — Themes: provenance, draft lifecycle, notify parity, import safety (RF-17; Q7)

```yaml
packet_id: RP-034
family_id: RF-17
finding_ids: ["#17:A1-CRUD-1", "#17:A1-CRUD-2", "#17:A1-CRUD-3", "#17:A1-CRUD-4",
  "#17:A1-CRUD-5", "#17:A1-CRUD-6", "#17:A1-CRUD-8", "#17:A2-DRAFT-1",
  "#17:A2-DRAFT-2", "#17:A2-DRAFT-3", "#17:A2-DRAFT-6", "#17:A2-DRAFT-7",
  "#17:A3-PORT-1", "#17:A3-PORT-2", "#17:A3-PORT-3", "#17:A3-PORT-4",
  "#17:A3-PORT-5", "#17:A3-PORT-7", "#17:A3-PORT-8",
  "agent: sensor (2-lens verified):SN-6", "#14:A1-INIT-3"]
files: [custom_components/eufy_vacuum/themes/manager.py,
  custom_components/eufy_vacuum/themes/preloaded.py,
  custom_components/eufy_vacuum/themes/services.py, src/, tests/]
required_behavior: >
  (1) Q7 VERBATIM — overwrite_theme = DRAFT-OVER-TARGET: resolved = target's own
  palette + the vacuum's draft applied over it; refuse ({success:false, reason})
  when the target is missing OR the draft is empty/unresolvable; NEVER the active
  theme as source; never an empty overwrite; recompute draft state after the
  write (draft cleared, dirty recomputed).
  (2) provenance: source=="core" entries are copy-on-write for overwrite/scoped
  import (the write lands on a user copy, active pointer repointed, provenance
  honest — PORT-3/CRUD-4); delete of a core theme writes a deleted_core_ids
  tombstone the seeder consults (CRUD-3/INIT-3).
  (3) draft lifecycle: delete clears the deleted theme's draft + dirty
  (CRUD-5/DRAFT-1); set_active_theme same-id → no-op short-circuit; different-id
  with a dirty draft → refuse without confirm:true (DRAFT-2 — card sends confirm
  after its own dialog; card half + i18n key); _import_scoped recomputes
  draft_dirty (DRAFT-6); DRAFT-7: active_theme_id transmitted as explicit null.
  (4) notify parity: the global-default branch notifies (DRAFT-3/PORT-4/SN-6).
  (5) import safety: imported token/color/alpha KEYS validated against the
  known-token allowlist (--evcc-* namespace + registered names; rejects listed in
  the response) — one bad file can no longer blank the card (PORT-1); PORT-2:
  scoped import clears only the namespaces the payload supplies; PORT-5:
  duplicate-name suffix loops to uniqueness; PORT-7: tags cleaned with reported
  drops (CRUD-7's truncation also reported); CRUD-6: rename gains the isinstance
  guard; CRUD-8: blank rename refused (SVE).
card_half: confirm-dialog for destructive theme switches + refusal toasts — i18n
  keys in en.js + ALL 17 locale packs (lesson 3).
rollback_plan: 4 commits — (a) Q7 overwrite, (b) provenance+tombstones,
  (c) draft lifecycle + notify, (d) import validation + misc. All share
  manager.py: strict order.
reproducer_script: NEW _proof_theme_semantics.py — overwrite with empty draft
  (before: target wiped to {}; after: refused); core delete → restart-sim
  (before: resurrected; after: tombstoned); malicious import key (before: stored;
  after: rejected list).
expected_before: ["target wiped by empty draft", "core theme resurrected",
  "arbitrary CSS key stored"]
expected_after: ["draft-over-target", "tombstone held", "keys validated"]
tests_to_add_or_modify: Q7 matrix; copy-on-write provenance; tombstone/seeder;
  draft lifecycle parity across all mutators; allowlist.
superseded_tests: active-as-source pins — docstrings cite Q7.
broader_gates: full suite + frontend gates.
hardware_gate: tier 1 (HC-5 theme editor walk).
stop_conditions: [the token allowlist cannot be derived from one source
  (check theme-lint's list first — reuse it, don't fork it)]
escalation_target: main agent → Chris
```

---

## RP-035 — Sensor/entity platform batch (RF-34)

```yaml
packet_id: RP-035
family_id: RF-34
finding_ids: ["agent: sensor (2-lens verified):SN-1", "agent: sensor (2-lens
  verified):SN-4", "agent: sensor (2-lens verified):SN-8", "agent: sensor (2-lens
  verified):SN-9", "agent: sensor (2-lens verified):SN-10b",
  "agent: platforms (2-lens verified):EP-3", "agent: platforms (2-lens
  verified):EP-4", "agent: platforms (2-lens verified):EP-6", "agent: platforms
  (2-lens verified):EP-7", "#15:A3-FLOW-2", "#15:A3-FLOW-3",
  "agent: infra (2-lens verified):INF-1", "agent: infra (2-lens verified):INF-2",
  "#9:A6-PRE-3", "#9:A6-PRE-4", "#7:DQ-PH-5", "#12:A5-METRICS-3",
  "#12:A5-METRICS-4", "#12:A5-METRICS-5", "#14:A6-VAC-5"]
files: [custom_components/eufy_vacuum/sensor/, number.py, button.py,
  binary_sensor.py, room_entities.py, config_flow.py, panels.py, __init__.py,
  timestamp_utils.py, jobs/job_monitor.py, queue/queue_engine.py,
  listeners/job_metrics.py, core/manager.py, tests/]
required_behavior: >
  SN-1 (HIGH, lead item): the per-vacuum sensor loop iterates MANAGED VACUUMS
  (not data["maps"]) + a creation hook on map import/vacuum add — a vacuum gets
  its sensors without a restart; SN-4 (AMENDED per REVIEW-07 T2-D5): room rename
  REMOVES+RE-ADDS the entity object with fresh translation placeholders under
  the SAME unique_id — the registry entry persists and a user's own name
  override legitimately wins. Do NOT use registry.async_update_entity(name=...)
  (it writes a USER-override name, stomping customizations and freezing future
  translation updates). The sync helper's currently-discarded rebuilt entity is
  the mechanism; SN-9: overlays sensor
  returns available=False instead of the literal 'unavailable'; SN-10b: the
  one-expression str(None) render fix; SN-8/EP-6/INF-x dead code removed
  (active_job_entities, _attr_suggested_object_id sites, INF-1's fourth panel
  site imports panels' constants, INF-3/7 ride in RP-040's DEAD batch — NOT
  here); EP-3: interval ceiling = adapter's declared max (declaration rule);
  EP-4: the polling class sets _attr_should_poll honestly + comment fixed;
  EP-7: mixed managed/unmanaged updates apply both halves (managed via
  update_room_fields, rest via the merge branch) or refuse listing dropped keys;
  FLOW-2/3: options flow REPLACES the managed vacuum (old record reconciled
  away with a confirm) and re-reads current options at submit; INF-2: timezone
  resolved per-call via HA's dt_util (DST-correct) — legacy naive timestamps
  parse with the offset in force on their date; PRE-3/4, DQ-PH-5, METRICS-3/4/5,
  VAC-5: TypedDict/annotation truth restored, unit fallback logged, station-water
  key derived from the capability declaration, get_managed_vacuums uses the
  guaranteed-snapshot sibling.
rollback_plan: 4 commits — (a) SN-1/SN-4 creation+rename, (b) sensor honesty +
  dead assignments, (c) flow + panels + tz, (d) contracts/annotations.
reproducer_script: NEW _proof_platform_batch.py — import a map on a fresh vacuum
  (before: zero per-vacuum sensors; after: created); rename room (before: stale
  friendly name; after: updated); INF-2 date-dependent offset case.
expected_before: ["no per-vacuum sensors until restart", "friendly name stale",
  "July timestamp stamped January offset"]
expected_after: ["sensors created on import", "friendly name updated",
  "offset per timestamp date"]
tests_to_add_or_modify: creation-path matrix; rename propagation; availability;
  options-flow replace; tz table across DST.
superseded_tests: maps-keyed loop pins; fixed-offset tz pins.
broader_gates: full suite. hardware_gate: tier 1 (HC-5 entity list after import).
stop_conditions: [options-flow replace semantics: the OLD vacuum's stored data
  disposition (keep vs remove) is a product call — default KEEP with a WARNING,
  escalate if Chris wants removal]
escalation_target: main agent → Chris
```

---

## RP-036 — Estimator correctness batch (RF-21) — blocked_by RP-013b

```yaml
packet_id: RP-036
family_id: RF-21
finding_ids: ["#16:A1-EST-1", "#16:A1-EST-2", "#16:A1-EST-3", "#16:A1-EST-4",
  "#16:A1-EST-5", "#16:A1-EST-6", "#16:A2-ACC-2", "#16:A2-ACC-3", "#16:A2-ACC-4",
  "#16:A2-ACC-5", "#16:A2-ACC-6", "#16:A2-ACC-7"]
files: [custom_components/eufy_vacuum/learning/estimator.py,
  custom_components/eufy_vacuum/learning/stats_rebuilder.py,
  custom_components/eufy_vacuum/learning/external_ingest.py,
  custom_components/eufy_vacuum/learning/manager.py, tests/]
required_behavior: >
  STRUCTURE-ONLY (no re-tuning of empirical constants — source-decidability rule):
  EST-1: the 0.79–0.80 dead band closed (MEDIUM max = HIGH min boundary,
  half-open test) and the fall-through returns the NEAREST bucket, not LOW;
  EST-2: the rebuilder tracks battery_sample_count (like area) — external runs
  write NO battery block and absent≠0.0; the estimator substitutes the default
  when count==0; EST-3: the projection canonicalizes clean_intensity with the
  rebuilder's `or "standard"` rule (one shared normalization — the mismatch, not
  a new module); EST-4: estimate consults stored minutes_min/max — a mean outside
  its own band caps confidence and clamps to the band edge; EST-5: velocity
  reports runs_to_* against the ACHIEVABLE ceiling (no promise of unreachable
  HIGH; if HIGH is structurally unreachable post-EST-1, the tier table's
  reachability is asserted in a test); EST-6: relaxed passes prefer highest
  sample_count (deterministic tiebreak documented); ACC-2: reanchor_timeline uses
  its anchor param (wall-clock offsets from NOW) — "Done at" stops sliding into
  the past; ACC-3: transit handled symmetrically (remaining rooms re-add their
  transit legs; overhead's transit reduced per completed room); ACC-4: reanchor
  takes skipped_room_ids (EVENT_ROOM_SKIPPED's data, plumbed by the caller) —
  skipped rooms resolve, all_completed reachable; ACC-5: slug None → skip slug
  matching (no literal "none" key); ACC-6: the drift mean weights exact
  (single_room/non-allocated) samples over allocated ones (consumes RP-013b's
  flags — the recorded-but-unused quality flag goes live); ACC-7: isinstance
  guards on the rooms block (tolerant like the sibling reader).
rollback_plan: 3 commits — (a) EST group, (b) ACC/reanchor group, (c) ingest/
  rebuilder halves. (a)+(b) share estimator.py: order a→b.
reproducer_script: NEW _proof_estimator_batch.py — table-driven: dead-band score
  0.795 (before: LOW/error; after: MEDIUM≥); external run battery (before: 0.0
  diluted the mean; after: absent); reanchor with a 10-min pause (before: Done-at
  in the past; after: anchored now).
expected_before: ["best room rendered LOW", "external battery 0.0 consumed",
  "ETA slid into the past"]
expected_after: ["dead band closed", "battery absent≠0", "anchored to now",
  "skipped room resolved"]
tests_to_add_or_modify: boundary tests; battery-count matrix; reanchor scenarios
  incl. oscillation regression; weighted drift.
superseded_tests: tests pinning the fall-through-to-LOW and anchor-ignoring
  reanchor.
broader_gates: full suite. hardware_gate: tier 2 ride-along (ETA observation on
  the Wave-2/4 captures — ACC-2/3 visible on any stepped run).
stop_conditions: [EST-1's boundary choice changes any OTHER tier's population in
  goldens beyond the dead band — stop (that would be re-tuning)]
escalation_target: main agent → Chris
```

---

## RP-037 — Event-loop hygiene (RF-29) — blocked_by RP-013c

```yaml
packet_id: RP-037
family_id: RF-29
finding_ids: ["#16:A1-EST-9", "#16:A3-IO-4", "#16:A4-STATE-7", "#18:A7-ROBORO-2",
  "#11:A2-GEO-2", "direct read:DR-ONB-5", "#14:A3-SNAP-2", "#17:A2-DRAFT-5",
  "#11:A6-TRK-7"]
required_behavior: >
  ensure_dirs memoized per path-set (one mkdir pass per process per dir —
  EST-9/IO-4/STATE-7); ROBORO-2's per-pixel loop moves to the executor (and
  diagnostics awaits it); GEO-2: bbox reject BEFORE normalize_rendered per cell
  (invert the bbox once); ONB-5: the sensor computes the summary once per update
  cycle; SNAP-2: get_dashboard_snapshot composes the progress payload ONCE
  (memoized within the call) and the side-effecting rollover/anomaly steps HOIST
  to the tick path (listener), leaving the snapshot pure — consumers verified
  indifferent to the caller (REVIEW pin); DRAFT-5: update_working_draft persists
  via async_delay_save (2s) — the flood becomes one write; TRK-7: the executor
  dispatch justified by nonexistent I/O replaced with a plain call + honest
  comment.
files: [learning/history_store.py, learning/estimator.py, diagnostics.py,
  mapping/roborock_raw_map.py, mapping/map_source.py, sensor/onboarding.py,
  core/manager.py, jobs/active_job.py, themes/services.py,
  listeners/job_progress.py, mapping/tracker.py, listeners/lifecycle.py, tests/]
rollback_plan: 3 commits — (a) fs/loop hygiene, (b) SNAP-2 purity hoist,
  (c) draft debounce + misc. (b) rebases on RP-013's progress-path changes.
reproducer_script: NEW _proof_loop_hygiene.py — syscall-count assertions
  (mock-patched mkdir/stat counters) before/after; SNAP-2: two snapshot calls in
  one poll produce identical payloads and fire zero events.
expected_before: ["32 mkdir calls per snapshot", "progress composed twice,
  events fired from read path"]
expected_after: ["0 mkdir on warm path", "single compose, pure read"]
tests_to_add_or_modify: purity test (snapshot fires no events); debounce; counts.
superseded_tests: any test relying on snapshot-driven rollover side effects —
  now driven by the tick (docstrings record the hoist).
broader_gates: full suite. hardware_gate: tier 2 ride-along (rollover events
  still fire on live runs — watch one capture).
stop_conditions: [a consumer DEPENDS on card-poll-driven rollover (no tick
  running) — stop, report]
escalation_target: main agent → Chris
```

---

## RP-038 — Dock events are edges (RF-30)

```yaml
packet_id: RP-038
family_id: RF-30
finding_ids: ["#12:A1-REG-1", "#12:A6-GUARD-3", "direct read:DR-DOCK-1",
  "direct read:DR-DOCK-2", "direct read:DR-DOCK-3", "#12:A1-REG-4",
  "#12:A2-LIFE-3_edge_half"]
files: [custom_components/eufy_vacuum/listeners/dock_events.py,
  custom_components/eufy_vacuum/dock/manager.py,
  custom_components/eufy_vacuum/listeners/lifecycle.py, tests/]
required_behavior: >
  a dock event is a transition FROM a known non-trigger state TO a trigger state:
  old_state None / unavailable / unknown is NOT an edge (REG-1/GUARD-3);
  record_dock_event validates event_type against the counter map like its sibling
  (DOCK-2); the timestamp write moves INSIDE the debounce decision so a debounced
  event corrupts nothing (DOCK-1); counter reset clears the debounce marker
  (DOCK-3); register() honors dock_events.enabled (REG-4); the lifecycle inline
  wash detector delegates its edge test to dock_events' logic (LIFE-3 edge half;
  vocabulary half landed in RP-025).
rollback_plan: 2 commits — (a) edge semantics + validation, (b) enabled flag +
  lifecycle delegation.
reproducer_script: NEW _proof_dock_edges.py — restart mid-dry (before: new cycle
  recorded, counter++, last_dry_start reset; after: no event); real
  drying→completed→drying (after: one event).
expected_before: ["restart counted as new dock cycle", "debounced event moved
  timestamp"]
expected_after: ["first-sighting ignored", "timestamp commits with counter"]
tests_to_add_or_modify: edge matrix (None/unavailable/recovery/real); debounce
  atomicity; reset coherence; enabled gate.
superseded_tests: level-test pins in lifecycle's wash detector.
broader_gates: full suite. hardware_gate: tier 2 ride-along — one Alfred mop-wash
  cycle + an HA restart mid-dry in the Wave-6 batch (counters stable).
stop_conditions: []
escalation_target: main agent → Chris
```

---

## RP-039 — Teardown remainder (RF-16) + diagnostics honesty remainder (RF-33)

```yaml
packet_id: RP-039
family_id: RF-16 + RF-33 (two rollback groups; graph defect fixed — RF-16's
  remaining 19 findings previously had no packet)
finding_ids: ["#15:A1-UP-1", "#15:A2-DOWN-1", "#15:A4-RELOAD-1", "#15:A1-UP-2",
  "#15:A1-UP-3", "#15:A2-DOWN-2", "#15:A4-RELOAD-2", "#16:A5-SVC-7",
  "#15:A2-DOWN-3", "#15:A4-RELOAD-4", "#15:A4-RELOAD-3", "#13:A1-WIRE-5",
  "direct read:DR-DBG-3", "#12:A1-REG-2", "#12:A2-LIFE-2", "#14:A6-VAC-4",
  "#12:A1-REG-3", "#12:A6-GUARD-6", "direct read:DR-DBG-2", "direct read:DR-DBG-4",
  "direct read:DR-DBG-6", "direct read:DR-DBG-7", "direct read:DR-DIAG-1",
  "direct read:DR-DIAG-2", "direct read:DR-DIAG-3", "direct read:DR-DIAG-4",
  "direct read:DR-DIAG-5", "direct read:HW-DIAG-1", "direct read:DR-LR-1"]
files: [__init__.py, panels.py, learning/services.py, core/water_amendment.py,
  debug_capture.py, listeners/lifecycle.py, listeners/discovery.py,
  core/manager.py, diagnostics.py, live_refresh/manager.py, tests/]
required_behavior: >
  GROUP A (RF-16, builds on RP-003's ledger): panels registered ANYWHERE record
  into the entry's panel ledger (the two orphan sites; duplicate-URL returns the
  existing url instead of None — UP-1/DOWN-1/RELOAD-1); async_setup_entry gains a
  try/except unwind that tears down what registered before re-raising (UP-2);
  learning services unregister list DERIVED from the registration table (one
  tuple, both consumers — UP-3×4); water_amendment + debug auto-stop handles join
  the RP-003 ledger (DOWN-3/RELOAD-4/RELOAD-3/WIRE-5/DBG-3); lifecycle _process
  tasks tracked and cancelled on remove (LIFE-2); per-vacuum teardown reaches
  discovery triggers + cache markers (REG-3/GUARD-6/VAC-4).
  GROUP B (RF-33): the debug switch shares the services' auto-stop ledger
  (DBG-2); free-form areas validated against the configured map with a refusal
  listing valid keys (DBG-4); status() clears run fields on stop (DBG-6); dump
  filenames gain a millisecond+counter suffix (DBG-7); diagnostics: the
  capability call made genuinely inert under refresh=False (DIAG-1), repr(err)
  sinks redacted (DIAG-2 — same masking seam as RP-004), failed probes surface
  in warnings (DIAG-3), entry.title redacted (DIAG-4), dead _SENTINELS alias
  removed (DIAG-5), the unreachable job-active warning corrected per HW-DIAG-1's
  settled analysis; live_refresh classifies ServiceValidationError as PERMANENT
  (sticky-disable + one WARNING — DR-LR-1).
rollback_plan: TWO GROUPS, 4 commits — A1 (panels+setup unwind), A2 (services
  table + ledger joins + per-vacuum), B1 (debug), B2 (diagnostics+live_refresh).
  Groups share __init__.py (A1/A2) — strict order.
reproducer_script: extend _proof_manager_reload.py — reload ×2: single panel, no
  ghost services, water/debug timers cancelled; diagnostics dump: zero secrets
  in repr sinks.
expected_before: ["duplicate fallback panel", "5 ghost services after unload",
  "secret in vacuums_error"]
expected_after: ["one panel", "0 ghost services", "repr sinks redacted"]
tests_to_add_or_modify: reload-parity suite (registration inventory before ==
  after); table-derived unregister; debug ledger; redaction sweep.
superseded_tests: hand-listed unregister pins.
broader_gates: full suite. hardware_gate: tier 1 (HC-6: reload ×2 on live HA).
stop_conditions: [the setup unwind cannot tear down a partially-registered HA
  platform forward-reference — report, do not force]
escalation_target: main agent → Chris
```

---

## RP-040 — Closing batches: small-correctness, dead code (Q8), docs, reject_rooms (Q10)

```yaml
packet_id: RP-040
family_id: batches (SMALL-CORRECTNESS + SMALL-CORRECTNESS-2 + DEAD-CODE + DOC-ONLY)
finding_ids: ["#10:A1-ID-5", "direct read:DR-BAT-2", "direct read:DR-BAT-3",
  "agent: infra (2-lens verified):INF-7", "#14:A2-CB-3", "#14:A2-CB-4",
  "#14:A4-START-3", "#7:DQ-ACT-7", "direct read:DR-BAT-1", "direct read:DR-BAT-4",
  "direct read:DR-ONB-6", "#16:A3-IO-5", "#16:A3-IO-7", "#16:A3-IO-8",
  "#12:A3-COMMON-5", "#12:A4-POSE-6", "#11:A3-EXT-5", "direct read:DR-MAP-1",
  "direct read:DR-MAP-2", "#10:A1-ID-6", "agent: infra (2-lens verified):INF-3",
  "direct read:DR-ONB-4", "#8:A6-PP-EST-H2O-2", "#8:A6-PP-EST-GUESS-1",
  "#8:A6-PP-EST-CLAMP-1", "#7:DQ-PAY-7", "agent: infra (2-lens verified):INF-6",
  "#10:A3-CRUD-7", "direct read:DR-ONB-3", "direct read:DR-SETUP-2",
  "direct read:DR-SETUP-3", "direct read:DR-SETUP-4"]
# NOTE (Stage M6, 2026-08-02): the 32 members ABOVE are what actually LANDED from
# the generated closing-batch table (.claude/notes/synthesis/RP-040-batch-table.md,
# 33 members/22 files) -- this list replaces this block's original prose closure
# so the ledger generators can resolve it automatically (previously null/null,
# "needs hand curation" per _gen_packet_closure.py). "#13:A4-SETUP-6" (Q10) is
# EXCLUDED: EJECTED per SONNET-STAGE-PROMPTS.md's Held table -- its
# required_behavior below is a real 3-part design (map_id schema field + a new
# setup_unreject_rooms service + protection/confirmation routing), not the
# one-line fix the closing-batch table assumed.
#
# UNRESOLVED SCOPE GAP, flagged not silently dropped: this block's original prose
# also named DR-MNT-1+SN-2 (cluster), A3-SNAP-1, A3-COMMON-1, A3-COMMON-3, SN-8,
# and DR-DIAG-5 as RP-040 headline members. NONE of them appear in the generated
# closing-batch table (which itself reports 0 unresolved / 0 ejected against its
# own scope), and no fix for them landed in Stage M6. Unclear whether they are
# owned by another packet, already closed by some other path, or a genuine gap in
# _gen_batch_table.py's cross-referencing against closure-matrix.json. Needs
# investigation before being treated as either covered or still open.
required_behavior: >
  Q10 VERBATIM (the one product item): setup_reject_rooms requires map_id, routes
  through the protection/confirmation standard of the other destructive setup
  actions, and a setup_unreject_rooms service reverses it (registered/
  unregistered symmetrically; services.yaml + docs; RP-032's gate covers it).
  Q8: repairs.py and its references deleted. The RF-13 remainder members
  (SNAP-1/COMMON-1/SN-2+DR-MNT-1) apply the tri-state rule per their records.
  **PRE-1 EJECTED to RP-041 per Q20** (relevance-gated blocking is a design, not
  a one-liner — the batch's own ejection rule applied). Everything else per its
  corpus record, one focused edit + one focused test each, batched into commits
  BY FILE.
rollback_plan: per-file commits (the generated table maps commit→members).
reproducer: table-driven _proof_closing_batch.py for the behaviour-bearing
  members; DOC-ONLY gated by mkdocs --strict; DEAD-CODE by the full suite.
expected_before/after: per-member fragments in the generated table.
superseded_tests: per-member, recorded in the table.
broader_gates: full suite + mkdocs --strict + frontend gates (unreject card
  affordance if Chris wants one — ask at review).
hardware_gate: none.
stop_conditions: [any batch member's one-line fix turns out to need design —
  eject it to a named follow-up, do not improvise]
escalation_target: main agent → Chris
```

---

## RP-041 — Job-relevant error blocking at preflight (Q20; ejected from RP-040)

```yaml
packet_id: RP-041
family_id: RF-13 (the FULL remainder — expanded per REVIEW-07 T2-D2; two HIGHs
  moved out of RP-040's prose into ownership here)
finding_ids: ["#9:A6-PRE-1", "#12:A3-COMMON-1", "#14:A3-SNAP-1",
  "agent: sensor (2-lens verified):SN-2", "direct read:DR-MNT-1",
  "#12:A3-COMMON-3", "#12:A4-POSE-3", "agent: infra (2-lens verified):INF-4"]
additional_required_behavior_t2d2: >
  COMMON-1 (HIGH): is_job_active treats a NOT-YET-ADDED/removed job_active entity
  per unavailable_is_active (state None joins the indeterminate arm — the
  Roborock mid-recharge guard holds through entity absence). SNAP-1: mop_active
  becomes the declared tri-state (None when the declared entity is unreadable,
  not False). SN-2+DR-MNT-1 (HIGH cluster): a MISSING usage_hours attribute makes
  source_available False (no fabricated full-life value into statistics) and
  reset_maintenance's invalid_usage_hours becomes reachable for it. COMMON-3:
  docstring truth (returns the literal, or make it return ""). POSE-3: _is_parked
  falls back per its documented contract when task_status is unreadable on the
  native path. INF-4: finish the BLANK_STATE_VALUES consolidation at the four
  hand-copy sites (the vocabulary substrate for all of the above).
files: [custom_components/eufy_vacuum/jobs/job_monitor.py,
  custom_components/eufy_vacuum/core/error_tracker.py,
  custom_components/eufy_vacuum/listeners/_common.py,
  custom_components/eufy_vacuum/listeners/pose_sampler.py,
  custom_components/eufy_vacuum/listeners/lifecycle.py,
  custom_components/eufy_vacuum/core/manager.py,
  custom_components/eufy_vacuum/maintenance/manager.py,
  custom_components/eufy_vacuum/sensor/maintenance.py,
  custom_components/eufy_vacuum/entity_helpers.py,
  custom_components/eufy_vacuum/adapters/config_schema.py,
  custom_components/eufy_vacuum/adapters/eufy/adapter.py,
  custom_components/eufy_vacuum/adapters/roborock/adapter.py,
  custom_components/eufy_vacuum/jobs/active_job.py, tests/]
symbols: [build_start_blocker_from_lifecycle busy branch, NEW
  job_monitor.fault_blocks_job, adapter fault_relevance block,
  ErrorTracker active-latch accessor]
problem: the vacuum-state busy branch is unreachable for every HA-standard state
  (the active set is both evidence and exemption) — an errored or
  externally-cleaning robot classifies "ready" and Start dispatches at it.
root_cause: set logic uses one vocabulary for two opposite questions; and a naive
  fix (blanket error-blocks-start) would over-block per Q20.
required_behavior: >
  Q20 VERBATIM: an error state blocks start ONLY when the fault is relevant to
  the job being started ("no water for a vac job is invalid" — Chris).
  (1) fix the set logic: vacuum_state == "error" (and externally-cleaning states)
  enter the busy evaluation instead of falling through to ready.
  (2) NEW question-helper fault_blocks_job(fault, requested_job) in job_monitor
  (the asker owns the question; M1): resolves the active fault's class from the
  error tracker's latch + the adapter's NEW optional fault_relevance block
  (fault-class → affected modes, e.g. water_system: [mop, vacuum_mop];
  dustbin/suction: [vacuum, vacuum_mop]).
  (3) defaults CONSERVATIVE: an unmapped or unclassifiable fault is relevant to
  ALL jobs (stuck/wheel/battery-class faults prevent any run); the IRRELEVANT set
  is the narrow declared one. A water-class fault with a vacuum-only queue →
  start ALLOWED with a warning in the response naming the ignored fault.
  (4) externally-cleaning (untracked run) → blocked as busy, reason
  external_run_in_progress (distinct from error).
  Eufy's fault classes seed from the error-mining vocabulary
  (project_eufy_error_mining — ErrorCode proto); Roborock from its error codes;
  both adapters ship a MINIMAL map (water-class only) — expansion is data, not
  code (expansion-ready seam, tiny surface).
compatibility_constraints: starts that silently dispatched at an errored robot now
  refuse or warn — release notes; the warning path keeps mixed cases startable.
rollback_plan: 2 commits — (a) set-logic fix + external busy, (b) relevance
  helper + adapter maps.
reproducer_script: NEW _proof_fault_relevance.py — errored robot (water fault) ×
  vac-only job (before: ready+dispatch; after: allowed with warning); × mop job
  (after: blocked, fault named); unmapped fault × any job (after: blocked).
expected_before: ["error state classified ready", "mop job dispatched with water fault"]
expected_after: ["water fault + vac job: allowed with warning",
  "water fault + mop job: blocked", "unmapped fault: blocked"]
tests_to_add_or_modify: relevance matrix (fault class × job mode); set-logic
  reachability (the busy branch fires); external-run busy.
superseded_tests: any test pinning error→ready fall-through.
broader_gates: full suite. hardware_gate: tier 0/1 (fault states simulable);
  ride-along observation if a real fault occurs during other batches.
stop_conditions: [a fault class cannot be resolved from the latch on either brand
  — report; the class map then keys on raw code with the same defaults]
escalation_target: main agent → Chris
```

---

# CARD-PLAN — named frontend consumer stubs (not §K packets; scheduled after their backends)

| Stub | Unblocked by | Content |
|---|---|---|
| CARD-1 refusal consumption | RP-031 | core.js action wrapper branches on {success:false, reason}; CF-5's two failure-renders-as-success paths close; reason-code i18n (en + 17) |
| CARD-2 qualification | RP-027, RP-013b | stale/held badge + allocated-timing provenance display (CF-6) |
| CARD-3 run errors | none | surface captured run_errors (CF-7) |
| CARD-4 strings | none | the three untranslated strings (CF-4) |
| CARD-5 map scoping | RP-020 | retryMissedRooms map_id check (STATE-4 card half) |
| CARD-6 plan honesty | RP-021a, RP-022 | leading-break validation message; zone-repeat control hidden per declaration (Q12/Q17); zone_bounds draw hints |
| CARD-7 recon UI | RP-019 | reconciliation review/confirm flow (plan_token) — PRODUCT design with Chris first |
| CARD-8 edge-mopping | none | CF-9 Roborock-only capability-driven removal (Q11) |
| CARD-9 theme confirm | RP-034 | dirty-draft confirm dialog + refusal toasts |

Every stub budgets i18n across all 18 locales and runs the frontend gates
(lesson 3). OpenDyslexic (CF-8) stays its own planned feature.
