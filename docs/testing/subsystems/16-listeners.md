# 16 — Listeners — Subsystem Test Map

The listeners subsystem wires HA state-change events to manager actions:
lifecycle (auto-finalize), job-progress ticks, job-metrics watch maps,
dock-events, path-blockers (mid-job rule re-evaluation), discovery passes,
pause-timeout escalation, and pose sampling (external-run pose time-series
capture for room auto-attribution) — plus the registration/teardown plumbing.
Covered by **279 tests across 13 integration files**, with the pose sampler
covered separately by `tests/unit/test_pose_sampler.py` (24 tests) — 191
cases total.

<!-- The two bold counts above are HAND-MAINTAINED (same reason as 15-adapters:
the integration/unit split can't be computed by the single-header model). -->

Source: `custom_components/eufy_vacuum/listeners/`
Architecture reference: [19 — The Event Ingress Layer](../../dev/19-event-ingress.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `lifecycle.py` | 146 | 94% | `test_listeners_state_driven.py`, `test_listeners_active.py`, `test_listeners_registration.py` | integration | **bare x28** |
| `path_blockers.py` | 144 | 98% | `test_listeners_state_driven.py`, `test_listeners_path_blockers.py` | integration | spec'd |
| `job_metrics.py` | 98 | 94% | `test_listeners_active.py`, `test_listeners_job_metrics_negative.py` | integration | **bare x28** |
| `stall_capture.py` | 162 | 100% | `tests/unit/test_stall_capture_listener.py`, `tests/unit/test_receipts_criterion.py`, `tests/unit/test_receipts_happy_path.py`, `tests/unit/test_receipts_concurrency.py` | unit (pure helpers, the decline paths, the whole chain, and two chains at once) | clean |
| `receipts/` | new | — | `tests/unit/test_receipts.py` | unit | clean |
| `dock_events.py` | 84 | 93% | `test_listeners_active.py`, `test_listeners_state_driven.py` | integration | **bare x28** |
| `discovery.py` | 83 | 99% | `test_listeners_timers.py` | integration | clean |
| `entity_rename.py` | 47 | 89% | `tests/unit/test_listeners_entity_rename.py` | unit | spec'd |
| `core/manager.py` (D4 migration) | new | — | `tests/unit/test_manager_entity_rename_migration.py` | unit | clean |
| `pause_timeout.py` | 89 | 95% | `test_listeners_timers.py` | integration | clean |
| `clean_order_refresh.py` | 54 | 97% | `test_listeners_registration.py` | integration | spec'd |
| `_common.py` | 81 | 91% | `test_listeners_common.py` | integration | clean |
| `job_progress.py` | 48 | 92% | `test_listeners_active.py` | integration | **bare x28** |
| `pose_sampler.py` | 142 | 94% | `test_pose_sampler.py` (unit) + `test_pose_sampler_cadence.py` | unit + integration | **bare x5** |

**Two gates, and neither alone is sufficient — demonstrated, not assumed.**
`scripts/check_receipts.py` is a static AST scan: it proves a receipt's call site EXISTS and
that the catalog agrees with it in both directions. `test_receipts_happy_path.py` proves the
call site RUNS. Making one receipt unreachable without deleting it (`if False:` around the
emit) leaves the static gate GREEN and turns the runtime test RED — which is
`feedback_audit_callsite_reachability` in miniature: static and runtime reachability are
different questions, and a correct call site with no execution passes every scan.

The happy-path file exists because the first two receipt tests both ended in a *decline*, so
six of nine catalog keys — every success receipt — were reached by nothing. A system whose
founding rule is "success is not allowed to be silent" had no test that success speaks.

`test_receipts_concurrency.py` asserts a **dependency, not a capability**. Two vacuums
stalling at once produce interleaved receipts that a reader *can* separate — but only
because every receipt in this catalog carries the vacuum as its first fact. That is a
property of the catalog, not of the protocol: the moment a chain reaches a station whose
facts omit the vacuum (a shared renderer, a store keyed by path, a queue), the grouping key
vanishes and only chronology is left, which §10 says is not enough. The test fails at that
moment rather than after it, which is when a correlation id should be added.

---

## What's tested

- **Registration / teardown** (`test_listeners_registration`) — each listener
  family registers its state-change subscriptions and unregisters cleanly.
  The module list is DERIVED FROM THE TREE, not hand-maintained: `[LR-5]` fails
  if `listeners/` and `_ALL_MODULES` disagree. That guard exists because the list
  silently fell four modules behind the package, and a hand-maintained scope list
  reports the same clean result whether it is complete or four short.
  `[LR-6a]`/`[LR-6b]` are a matched pair — a dock arrival DOES trigger a read, and
  after `remove()` it does NOT. The positive control is load-bearing: the teardown
  half alone passes just as happily against a listener that never fires, and that
  is precisely the bug it caught.
- **State-driven actions** (`test_listeners_state_driven`) — a vacuum state
  change drives lifecycle auto-finalize and path-blocker re-evaluation.
- **Active watch maps** (`test_listeners_active`) — dock-event recording,
  job-metrics entity watch construction.
- **Timers** (`test_listeners_timers`) — the discovery pass and pause-timeout
  escalation fire on their timer callbacks.
- **Shared helpers** (`test_listeners_common`) — `_common.py` dispatch utilities.
- **Path-blocker actions** (`test_listeners_path_blockers`) — a matched
  mid-job blocker rule drives the pause / cancel / event action and the
  watcher-build filtering that drops malformed/disabled/non-blocker rules.
- **Job-metrics negative/guard paths** (`test_listeners_job_metrics_negative`)
  — the metrics-change handler's entry-miss / no-state / unavailable / manager-gone
  and value-parse (`ValueError`) guards.
- **Pose sampling** (`test_pose_sampler`, unit) — external-run pose time-series
  capture: parked/docked nulling of `current_room`/`anchor` via MQTT `task_status`
  (with the pose `robot_docked` flag as fallback), cadence resolution from the
  adapter's `room_attribution` block, and the external-only + live-pose-only gating.

---

### Stall capture (`SL`) — the opt-in consumer

`stall_capture.py` subscribes to `EVENT_STALL_DETECTED` and, **when armed for that
vacuum**, renders the room the robot stopped in, writes it beside that vacuum's learning
data, raises a persistent notification and fires `EVENT_STALL_CAPTURED` with the path
(issue #47).

It is a CONSUMER, not part of the detector, and that is load-bearing rather than stylistic.
`EVENT_STALL_DETECTED` already feeds `detect_run_anomalies`, which sets the `stall` /
`running_long` / `skipped` fields the card's snapshot reads — so gating the detector on
this feature's switch would silently disable anomaly reporting for anyone who turned off
stall photos. It also keeps two failure modes apart for the maintainer dev card: with the
switch off an injected stall still fires and still reports anomalies, so "no picture"
means the consumer rather than the injector.

The targets cover the decisions AROUND the render (the renderer itself is `SC` in
[07-mapping](07-mapping.md)):

| id | what it holds |
|---|---|
| `SL-1` | **absent arming is OFF** — an upgrade never starts writing images of someone's home; a broken store disarms rather than raising |
| `SL-2` | the path is per (vacuum, map) and STABLE — no timestamp, so nothing accumulates and an automation can hardcode it |
| `SL-3` | a Roborock map id is a NAME ("Main floor"), so it is sanitised — and a hostile id cannot traverse |
| `SL-4` | the map label prefers the brand's DECLARED entity and falls back to the id |
| `SL-5` | `unknown` / `unavailable` is not a label — the id beats "stalled … on unknown" |
| `SL-6`/`SL-7` | render geometry is passed through verbatim, never re-derived; unusable data yields `None` rather than a partial payload |
| `SL-11` | a brand declaring `active_map` as a **candidate LIST** still gets a label, from the list's FIRST element; an empty list falls back to the id |
| `SL-12` | registration is a **hand-off**: a fired `EVENT_STALL_DETECTED` really reaches `_capture`, and reaches it with a COPY of the event payload |

`SL-4` records a real brand asymmetry rather than papering over it. Roborock declares
`select.<id>_selected_map`, whose state IS the map name. Eufy declares only
`sensor.<id>_active_map`, whose state is the numeric id; its friendly name lives on the
fork's `switch_map` select, which the Eufy adapter does not declare. Guessing that entity
id to get a nicer string would be exactly the brand-ism this project keeps removing.

The message therefore reads **"on map X"** rather than "on X" — which carries a bare id
("on map 12") without needing per-brand phrasing, and still reads correctly for a brand
that supplies a name ("on map Main floor"). Declaring the name properly needs a NEW entity
ROLE: the role list in `core/capabilities.py` is fixed, and `active_map` must keep
resolving to the ID because map-id resolution depends on it. That is a contract change,
not the one-line adapter tweak it first looked like.

### The receipts pilot (`RC`) — and `stall_capture.py` at 100% (2026-11-08)

The `RC-*` ids live in three files beside the `SL-*` ones and had no entry here
until this campaign closed the module out:
`tests/unit/test_receipts_criterion.py` (`RC-C*`, the pilot's success criterion),
`test_receipts_happy_path.py` (`RC-H*`, success must actually speak) and
`test_receipts_concurrency.py` (`RC-X`, two captures at once).

| id | what it holds |
|---|---|
| `RC-C` / `RC-C2` | replay of the 2026-08-09 incident: the dump ALONE says `not_armed` — and the mirror, an armed run does not decline |
| `RC-C3` | the runtime is gone, and the decline still NAMES its own station |
| `RC-C4` | a stall with no resolved room declines `no_room`, and that outranks `not_armed` |
| `RC-C5` | present render data the geometry step refuses declines `unusable` rather than crashing — three causes, three rows |
| `RC-C6` | a missing picture says WHICH absence: `no_pillow` or `unusable` |
| `RC-H` / `RC-H2` / `RC-H3` | the whole chain speaks in causal order; a poseless brand reads `weak` not `lc`; a write failure speaks then STOPS |
| `RC-H4` | a corrupt stored rotation costs the ORIENTATION, not the capture |
| `RC-H5` | with nothing capturing receipts, the net is not counted at all |
| `RC-X` | two interleaved captures stay attributable |

**Four of the six decline reasons this module owns had never fired in a test.**
`no_runtime`, `no_room`, `unusable` (twice) and `no_pillow` existed as emit SITES
and nothing ran them — which is `feedback_audit_callsite_reachability` reproduced
inside the instrument built to detect it, a split
`test_receipts_happy_path.py`'s own header already records finding once:
`check_receipts.py` is a static AST scan, so it proves "a call SITE exists, not
that it ever RUNS". The same was true one layer up: `register()` was reached by
the setup tests while `_on_stall`, the callback it subscribes, was invoked by
NOTHING — the three bus-level stall tests fire the event without registering the
listener, and the receipts tests await `_capture` directly, so the hand-off
between them was the one link nothing crossed (`SL-12`).

**One reason in the vocabulary is still unemittable, and is NOT closed.**
`DECLINE_REASONS` declares `no_map`; all six emit sites are in this module and
none of them emits it. (The `no_map` strings in `mapping_services.py` and
`setup/status.py` are a different vocabulary — service refusal reasons.) The
receipts module's own docstring already names it as declared-but-never-emitted.
It is recorded here because it is the same class of defect as the four above.

**`C33` is also still open**, and the test prose says so rather than smoothing it
over: `unusable` stands for FOUR distinct causes across TWO emit sites, and
`RC-C5`/`RC-C6` pin all four without splitting them, because splitting them is a
code change (new reasons plus the `DECLINE_REASONS` vocabulary).

#### The pragma that was costing coverage rather than buying it

`is_enabled`'s `except Exception:` carried `# pragma: no cover - defensive; a
broken store must not raise here` and was this file's single entry in
`tests/pragma_allowlist.json`. Two things were wrong with it, in opposite
directions:

- it failed the repo's own rule (a waiver is for logger lines; that body is
  `return False`), which is why the census counted it; **and**
- the arm was **already covered**, by `SL-1`
  `test_a_broken_store_disarms_rather_than_raises`, which hands in a manager whose
  `data` property raises. So the pragma was subtracting two EXERCISED statements
  from numerator and denominator alike.

Removing it drained the allowlist row, which `PR-3` then required to be deleted —
the direction that gate is built for. The general shape is worth keeping: **a
`pragma: no cover` is not evidence that the code under it is untested.** Measure
before classifying.

> ⚠ **THE FIRST VERSION OF THIS PARAGRAPH OVERCLAIMED THE ARITHMETIC.** It said
> removing the waiver "RAISED the measured figure". It raises the PACKAGE figure by
> two covered statements; at this file's 100 % it changes nothing (160/160 →
> 162/162), because excluding *covered* statements cannot move a ratio with zero
> missing. The 86.56 % → 100 % here is entirely the new tests. The claim was true of
> the state it was written against and false of the state it shipped in.

**A SECOND WAIVER OVER EXERCISED CODE SAT 45 LINES AWAY, in the same file, and only
an audit of the first deletion found it.** `_trail_from_ring`'s handler is driven by
`[SL-8]` `test_an_unreadable_ring_costs_the_trail_not_the_capture`, which monkeypatches
`pose_store.read_range` to raise — so it was hiding three covered statements. It is
*rule*-compliant (the census allows an inert `return []` beside the logger call), which
is exactly why the rule is not the whole test. Deleted; the file stays at 100 %, now
over 165 statements. One instance got swept and the file did not — the partial-guard
shape in its smallest form.

**Three pragmas remain and all three are within the rule** — the `except` in
`remove`, in the notification block, and in `register`'s `_run`, each a handler whose
body is logger calls plus at most an inert return. Two of them hide behaviour that is
genuinely untested, and this is the honest record of it rather than a claim of
completeness:

> ⚠ **THIS LIST SAID "four pragmas" AND CITED 119, 172, 422, 459.** Every
> substantive claim about them held, but three of the four numbers were stale by
> exactly 7 — the comment lines *this same commit* inserted into `is_enabled` — and
> a fourth handler has since been deleted too (below). `check_doc_citations.py`
> cannot catch this: a bare number with no `file.py:` prefix is not a citation to it,
> so the commit's own "0 wrong" gate line never covered them. Symbols from here on.

- **`remove`'s handler** hides the loop CONTINUATION that makes `remove()` best-effort across
  ALL unsubs. `break` versus `continue` is invisible unless the raising unsub is
  first — and production only ever puts ONE unsub in that list, so the multi-unsub
  shape a test would need is one no shipped code path produces. Stated here
  instead of tested, deliberately.
- **`register._run`'s handler** hides the task containment, which is the reason `_capture` is
  wrapped at all. `SL-12` drives `_on_stall` and `_run` but not the `except`.
- **the notification handler** hides nothing by the rule, but it does hide a fact:
  its body IS executed, and only because every test reaching the notification block passes a
  `SimpleNamespace` hass, so `persistent_notification.async_create` raises and the
  handler swallows it. **No test in the repo has ever observed the notification
  being CREATED** — the only arm ever exercised on that path is the failure one.

#### Two reachability claims stated at their real strength

Both of these guards are reachable only from stored state no in-package writer can
produce, and the tests say so rather than inventing an incident:

- `map_label`'s list normalisation (`SL-11`) is in the file's FIRST commit
  (`76b79e78`), not in a fix. What makes it reachable is that
  `adapters/config_loader.load_stored_adapter_configs` registers a stored
  `.storage` config with no schema validation.
- `RC-H4`'s rotation guard has exactly one in-package writer, schema-bound to
  `vol.In([0, 90, 180, 270])` — and `git log -S` shows the writer and that schema
  arrived in the same commit, so there was never a coerce-free version. What
  remains is the store: `core/storage.py` does no load-time validation. **The
  near-identical guard in `core/manager.py::get_dashboard_snapshot` is still
  uncovered** (it differs only in spelling the `.get` default), so that half of
  the class remains untested package-wide.

And one limit of `RC-H4` worth carrying, because the test's title is wider than
its guard: the `except (TypeError, ValueError)` covers a corrupt VALUE. The same
store can put a string or a list at `maps[vacuum][map_id]`, and `.get` on that
raises **AttributeError**, which this handler does not catch and nothing in
`_capture` catches either. A corrupt bucket *does* cost the capture. Widening the
tuple is a code change and a separate decision.

#### One vacuous test found and fixed in passing

`SL-4`'s `test_map_label_prefers_the_declared_entity` passed `map_id="Main floor"`
— **exactly the label it asserts** — so the fallback `return str(map_id)`
satisfied it and the test stayed GREEN with the ENTIRE declared-entity read
deleted. It was found by ablating that read while verifying `SL-11`, and the fix
is one character class: the id is now `"7"`. The general form is the one this
campaign keeps paying for — **an expected value that the fallback also produces
is not a discriminator** — and the ablation harness now carries that ablation as a
standing check.

> ⚠ **THAT SENTENCE USED TO CREDIT THE ABLATION HARNESS (`S4`), AND IT WAS A FALSE
> CLAIM OF PROTECTION.** The harness is an untracked scratchpad file, so a clone had
> none of it and CI reddened for nobody — the same hazard as a shipped feature whose
> spec lives in a git-ignored directory. The guard now ships: the test asserts
> `map_id != expected` in its own body, which fires in the suite the moment someone
> collapses the two. An ablation harness can prove a test bites today; only something
> tracked keeps it biting.

### Entity rename (`ER`) — detection only, on purpose

`entity_rename.py` is the D4 detector: a managed vacuum's entity id is a **storage
address**, so renaming one strands seventeen store sections plus the learning tree
while `ensure_vacuum_record` quietly creates a fresh empty one. Until this listener
existed, nothing noticed.

It **records and does not repair** — moving the data is a migration over the user's
only copy and lands on its own review. What the listener buys on its own is that the
old id is captured at the one moment it is observable: once Home Assistant has renamed
the entity, the old id exists nowhere else.

The tests cover the decisions rather than the plumbing — what counts as a rename
(`ER-2`: an icon or friendly-name change is not one), whose rename matters (`ER-3`),
and two that defend specific reasoning:

- **`ER-5`** — two renames APPEND. Keyed by vacuum, `a→b` then `b→c` would let the
  second overwrite the first and leave `a` unresolvable, which is the loss the
  listener exists to prevent.
The **repair** is `core/manager.py::_apply_pending_entity_renames`, covered by
`tests/unit/test_manager_entity_rename_migration.py` (`RN`). Two of its targets defend specific
reasoning: **`RN-2`** proves sections are DISCOVERED rather than listed — a section invented after
the migration was written still moves, which a hardcoded list of seventeen would miss — and
**`RN-6`** proves the fallible half runs first: the filesystem move is attempted before any dict
is touched, so a tree failure leaves *nothing* moved rather than a store pointing at a tree still
under the old name. Ablating the abort turns `RN-6` red on its own.

- **`ER-6`** — the managed check is against the **old** id. Moving it to the new id
  turns every real rename into "not ours", because the new id is by definition one
  that was never stored. Ablation confirms `ER-1`, `ER-5` and `ER-6` go red together.

## How it's tested

The `manager` / `manager_with_services` fixtures plus `hass.states.async_set`
to drive events and `hass.async_block_till_done()` to flush. The unsubscribe
teardown excepts are best-effort (`# pragma: no cover`).

---

## Known gaps

The uncovered lines are dominated by best-effort teardown/guard branches that
are intentionally left uncovered (`# pragma: no cover` on the unsubscribe
excepts), early-return guards on malformed/duplicate events, and a few
adapter-config sub-branches:

Every module in this subsystem grew this campaign (`lifecycle.py` 121→144
statements, `path_blockers.py` 106→142, `job_metrics.py` 88→98, `pause_timeout.py`
59→74, `pose_sampler.py` 137→159, smaller growth elsewhere), so the specific
line numbers below are freshly pulled from a `--cov-report=term-missing` run
against this revision rather than re-verified item-by-item for every module —
spot checks on `lifecycle.py` and `path_blockers.py` confirm the *shape*
(early-return / defensive guards) still holds:

- **`lifecycle.py`** — the entry's line numbers had rotted (115/126/129/144/516/521)
  and "same defensive shape" was wrong about two of them. `LC-11`..`LC-15` close
  them:
  - **`LC-11`/`LC-13`** are the no-manager return and the unmatched-vacuum branch.
    `LC-13` asserts the DECISION LOG, not just the return, because the branch exists
    precisely so a lifecycle signal does not "die without a word" — a bare `return`
    with no log would satisfy an absence-only test. `decision_log.emit` logs at
    DEBUG under `custom_components.eufy_vacuum.decision_log` and is guarded on
    `isEnabledFor`; both were read out of that module rather than assumed, since an
    assertion on the wrong logger passes for the wrong reason.
  - **`LC-12`** is not defensive at all. The watch-entity match is made per vacuum
    against that vacuum's own declared entities; without it EVERY known vacuum
    matches EVERY watched entity, so one robot finishing a job drives finalization
    for another — reading the other's active job and writing its transitions. It
    needs two vacuums, which no lifecycle test had, and it asserts on the
    `vacuum_entity_id` **kwarg** rather than call counts, because the mock manager
    ignores which vacuum it was asked about and a wrongly-matched second vacuum
    produces calls identical in shape.
  - **`LC-14`/`LC-15`** are the `maybe_handle_external_run` True arm and its False
    control. `_mgr` hard-wires that call to `AsyncMock(return_value=False)` "to keep
    that branch inert", so the True arm had never executed — and it is the one that
    matters for app-started runs: True means an external slot was opened or
    finalized, and without `any_changes` the pass never reaches `async_save`, so the
    slot exists in memory only and is gone on the next restart. The **idle** job in
    `LC-14` is load-bearing: a started job sets `any_changes` through the internal
    path and masks the line.

  ⚠ `LC-11` and `LC-13` drive the CAPTURED handler; `LC-12`, `LC-14` and `LC-15` go
  through the real bus because what they assert happens inside the spawned
  `_process()` task. `LC-12` also pins
  `finalize_learning_for_active_job.return_value`: left untouched, that autospec'd
  async method returns a coroutine nothing awaits, and the test passes while leaking
  a ResourceWarning (measured — it was the only one of the five that did).

  All five set `.return_value` on the **already-autospec'd** mock rather than
  assigning a fresh `AsyncMock` over it. A first draft did the latter, and the W0
  mock ratchet caught it (28 → 31) — correctly, because assigning over a spec'd
  method throws its signature protection away, which is the thing `spec_manager`
  exists to provide. Same correction in `test_pose_sampler.py` for `PS-3`
  (`record_pose_sample.return_value = False`, 5 → 6 refused).
- **`path_blockers.py` (95%)** — missing lines 179, 250-251, 256-257: a
  non-dict-room skip inside the watcher-build rule walk, and event-dedup
  guards.
- **`dock_events.py`** — the entry read "missing lines 77, 81, 85: event-dedup
  guards"; the numbers had rotted and only one of the three real gaps was a dedup
  guard. Now pinned by `LS-24`..`LS-26`:
  - **`LS-24`** is the one that is not defensive at all. An `extra_watch` carrying
    `triggers: {}` whose role RESOLVES still writes `watched[entity]` *and*
    `extra_triggers[entity] = {}` — and at event time `extra_triggers.get(id)`
    returning `{}` is **not None**, so the `_triggers is None` fallback never
    consults the adapter's own `dock_events.triggers` for that entity. Point such a
    watch at the same entity as `dock_status` and every real wash event on it is
    silently shadowed. The role has to resolve for the test to bite: an
    empty-trigger watch that resolves no entity is subsumed by the `not _entity`
    guard below it, which `continue`s either way.
  - **`LS-25`/`LS-26`** drive the removed-entity (`new_state=None`) and
    manager-gone guards. `LS-26`'s event must be a GENUINE edge
    (`idle -> washing`, a declared trigger) — a non-edge event does nothing whether
    the guard is present or not, so it cannot expose it.

  ⚠ **Both call the CAPTURED handler, never the bus.** HA catches and logs
  exceptions raised inside a `@callback`, so a test firing through
  `hass.states.async_set` swallows the `AttributeError` a missing guard raises and
  passes inverted. Driving the closure directly is also the only way to synthesise
  a `new_state=None` event, which the real state machine will not emit on demand.
- **`entity_rename.py`** — `ER-7`..`ER-9` close the three guards between the
  entity_id check and the append.
  `ER-7`'s guard is a three-clause compound and **only two of its clauses can
  bite**, which is measured rather than asserted: ablating each clause separately,
  `not new_entity_id` and `old == new` each redden exactly one parametrised row,
  while `not old_entity_id` reddens **nothing** — an empty old id is not in
  `data["vacuums"]`, so the managed check below returns anyway. Using old-empty as
  the red input would have looked like coverage and proved nothing. `ER-9` covers a
  `pending_entity_renames` value off disk that is not a list; note the repair
  DISCARDS the prior value, so the test asserts the list holds exactly one entry.
- **`job_metrics.py`** — the entry here read "missing lines 44, 48, 206:
  capability-read / value-parse guards", and both the numbers and the
  characterisation were wrong. The real gaps were the `ms` and hour branches of
  `_duration_state_to_seconds`, the declared-support-with-no-entity arm of the
  station-water wiring, and the two `value_type` arms that RECORD (area and float) —
  not guards at all, and between them the inputs to every per-minute and per-m²
  learning mean. Now pinned by `JMN-12` and `JMN-14`..`JMN-16`:
  - **`ms` and hour aliases** (`JMN-12`) — unconverted, they fall to the
    "assume seconds" fall-through: 300000 ms stored as 300000 s (**×1000**) and
    0.5 h as 0 s (**×3600**). Expected values are hand-written, not taken from the
    function. The unit PRECEDENCE that keeps this honest was already pinned in both
    directions by `test_entity_unit_wins_over_adapter_fallback` and
    `test_adapter_unit_fallback_converts_bare_minutes` — a draft duplicate of it was
    dropped, and the ablation is what revealed the duplication by reddening the
    pre-existing test alongside the new one.
  - **station water declared but undeclared** (`JMN-14`) — `supports_station_water`
    True with neither `water_level` nor `station_water` present. Without the guard,
    `watch_map[None]` puts `None` into the list handed to
    `async_track_state_change_event`, which raises and takes down registration for
    *every* vacuum. The reverse case (entity without the flag) is `JMN-10`.
  - **the recording arms** (`JMN-15`, `JMN-16`) — only the area *refusal* arm had
    been driven. The ft² row is the discriminator: a unitless-only test passes
    against a handler that ignores units, because unitless is the identity case.
    `JMN-16` uses a fractional 42.5 because 42 would be recorded identically by the
    `int` arm beside it.

  ⚠ **`_duration_state_to_seconds` here is a THIRD copy of replica set `RN2ZQ5NG`**,
  which declared two. It carried no `REPLICA` marker, appeared nowhere in
  `docs/dev/00c-replicas.md`, and was pinned by nothing — `RPL-7` derives the
  vocabulary from the *primary*'s AST. Measured when anchored: identical alias
  families and identical answers across all 25 aliases and fallbacks either side
  knows, so it was consistent, merely unguarded. `RPL-7d` now drives the union of
  both copies' aliases through both. By enumeration of the duration tests that
  existed before (`s`, `min`, `fortnight`, `seconds`), **a change to the `ms` factor
  alone would have reddened nothing** — which is what the anchor is for, and it was
  found while writing the branch tests above rather than by any gate.
- **`_common.py` (91%)** — missing lines 77, 82-83, 105-106, 139, 217. The line
  numbers in this entry had rotted (it read 50-51, 73-74, 106, 114 at 93%), and so
  had the claim that all of it was defensive. Two of those lines were not:
  - **217**, the `unavailable_is_active` arm, is now pinned by `LC-18`. The flag
    exists because two callers want opposite readings of an *unreadable* `job_active`
    binary — the finalize gate must treat silence as still-running and refuse to
    finalize, the arming gate must treat it as strict not-on — so the test asserts
    both readings of the same state. `test_listeners_active`'s own
    `test_lifecycle_recharge_guard_suppresses_on_unavailable_binary` names this arm
    and never reaches it (see 05-gotchas §10): deleting the arm reddened **0 of 70**
    tests in those two files.
  - **77**, `get_adapter_vocab`'s no-adapter return, is now *executed* by `LC-1` —
    which previously asked about a vacuum the `manager` fixture had registered an
    adapter for (05-gotchas §13). Two separate ablations, because they are two
    separate claims: changing that `return fallback` to `frozenset()` reddens `LC-1`
    and leaves `LC-1b` green, so the test does bite on the **value**; but deleting
    the `if config is None` **guard** reddens nothing, because `None.get(...)` raises
    into the blanket `except` which returns the same fallback. The guard is
    SUBSUMED and its red set is declared empty.

  82-83 and 139 have since been closed too, and 139 is worth reading before anyone
  calls it covered:
  - **82-83** (`LC-19`) is the input that actually tests `get_adapter_vocab`'s
    "Never raises" promise. The existing missing-section cases do not: there the
    `.get` chain succeeds and finds nothing, whereas a section whose VALUE is a
    list, str or int makes the expression itself raise, and only the broad `except`
    keeps the promise. Reachable because adapter shape is a declaration and
    code-sourced adapters register warn-only.
  - **139** (`LC-20`) is a CONTRACT test, and no shipped brand reaches it.
    Measured: no shipped `dock_events.triggers` vocabulary contains `none` (Eufy
    ships washing/emptying/drying variants, Dreame washing and drying, Roborock
    declares no dock_status role and goes through `extra_watches`), so against
    everything that ships today the guard is **subsumed** — without it
    `str(None).lower()` is `"none"`, which is in no trigger set. It is pinned anyway
    because the vocabulary is a PARAMETER of a pure public helper and
    `lifecycle.py` really does pass `None` when a dock_status entity is removed. A
    vocabulary containing `none` is the entire red input; with an ordinary one the
    test passes with the guard deleted.

  105-106 remain a genuinely defensive broad-except fallback.
- **`pause_timeout.py` (92%)** — missing lines 161, 175, 182-183: guards
  inside the tick (manager gone, unknown map_id, and one new arm not yet
  itemized by name).
- **`discovery.py` (99%)** — only line 190: the body of the periodic
  safety-net `_on_tick` callback; the timer fires it but no test advances the
  adapter-configured interval. Trivial.
- **`job_progress.py`** — "only line 75" was stale. `JP-5`/`JP-5b` pin Lever B's
  gating (the live-room pulse is for CONTIGUOUS runs; a strict-order run already
  gets a free refresh on each state flip, and `JP-4` deliberately asserted nothing
  about where the gate sits), and `JP-6` pins the stuck watch's own try/except.
  `JP-6` uses TWO vacuums with the first raising: the single-vacuum version cannot
  distinguish "the event still fired for this vacuum" from "the loop survived to the
  next one", and the second is the more important half — without the except the
  exception escapes the loop body, so the raising vacuum never reaches `async_fire`
  AND the one after it is never processed, turning 2 tick events into 0. Stuck
  detection rides this ticker rather than a fourth timer, so a fault there sits
  directly upstream of the `EVENT_JOB_PROGRESS_TICK` the card's live view needs.
  The remaining `unknown`-map `continue` is still uncovered, and the trace's own note
  on it is worth keeping: a persisted `active_jobs[vac]["unknown"]` slot written by
  an older build would distinguish it, and no producer for one was found — so it is
  recorded as UNVERIFIED rather than classified either way.
- **`pose_sampler.py` (94%)** — missing lines 142-143, 212-214, 294, 429, 436. These
  numbers had rotted too (the entry read 89% with a different dozen lines). Line
  **436**, the POSE-2 in-flight guard, is the one worth reading about: it was named
  by `PC-3` and reached by nothing, because both of that test's ticks fired at the
  same frozen clock and the **cadence** guard two lines above skipped the vacuum
  first. `PC-3` now advances the clock to 11.5 so the cadence has elapsed while the
  first sample is still parked, and it reddens on the guard's removal.
  Two mechanisms in that fix are worth knowing before touching this file:
  `asyncio.wait_for` is useless here because the test freezes `hass.loop.time` and
  asyncio schedules timers against it, and the release must be unconditional or the
  hang moves into `hass` teardown. Both are written up in 05-gotchas §14.
  The external-only sampling and the parked/docked nulling happy paths are covered
  by `tests/unit/test_pose_sampler.py`; cadence, tick isolation and the in-flight
  guard by `tests/integration/test_pose_sampler_cadence.py`.

  The other four are closed by `PS-1`..`PS-3` and `PC-4`:
  - **`PS-1`** (142-143) — `room_attribution.tuning.interval_s` is **not validated
    by the registry**, which the module comment states, so a non-numeric declaration
    is live on shipped brands rather than hypothetical. Both exceptions the `except`
    names are driven (a string → ValueError, a list or dict → TypeError), so
    narrowing the tuple reddens its own rows. The cost if it goes:
    `_room_attribution_interval_s` is called UNGUARDED from `register()`, so one bad
    declaration stops the sampler registering for the **whole fleet**. The expected
    2.0 is written as a literal, not read from `_FALLBACK_INTERVAL_S` — reading the
    constant would make the test pass against whatever the fallback became.
  - **`PS-2`** (212-214) — the live-pose provider raising. It is called DIRECTLY,
    never through `_handle_pose_tick`, because the tick's POSE-5 `except` swallows
    exactly the exception a missing try/except here would raise: routed through the
    tick this test passes INVERTED.
  - **`PS-3`** (308→332) — the 24-hour pose ring is deliberately NOT gated on
    `record_pose_sample`'s return, and every prior test stubbed that True so the
    False arm never ran. The two sinks answer different questions: the buffer is
    job-scoped and guards live attribution, the ring is a parallel copy that
    outlives the job. The ablation is the plausible tidy-up — an `else: continue`
    under the buffer's acceptance — which would drop ring history for exactly the
    samples the buffer rejected while every other test stayed green.
  - **`PC-4`** (429) — a mixed fleet where one member declares no
    `room_attribution`. Without the guard, `now_ts - last < None` raises TypeError
    in the tick BODY, **outside** the per-vacuum try, so the whole cycle dies and
    every later vacuum goes unsampled. The interval-less vacuum sits in the MIDDLE
    of the list on purpose: at the end, a `continue` wrongly written as `break` or
    `return` would be indistinguishable from correct behaviour.

These are deliberately uncovered at the ~90% meaningful-coverage ceiling: the
teardown/guard branches are defensive, and the sequenced-phase /
mapping-tracker branches in lifecycle exercise paths that require a full
integration boot with a live tracker rather than the per-unit fixtures used
here.
