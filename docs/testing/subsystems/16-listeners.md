# 16 — Listeners — Subsystem Test Map

The listeners subsystem wires HA state-change events to manager actions:
lifecycle (auto-finalize), job-progress ticks, job-metrics watch maps,
dock-events, path-blockers (mid-job rule re-evaluation), discovery passes,
pause-timeout escalation, and pose sampling (external-run pose time-series
capture for room auto-attribution) — plus the registration/teardown plumbing.
Covered by **234 tests across 12 integration files**, with the pose sampler
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
| `lifecycle.py` | 145 | 94% | `test_listeners_state_driven.py`, `test_listeners_active.py`, `test_listeners_registration.py` | integration | **bare x28** |
| `path_blockers.py` | 142 | 95% | `test_listeners_state_driven.py`, `test_listeners_path_blockers.py` | integration | spec'd |
| `job_metrics.py` | 98 | 94% | `test_listeners_active.py`, `test_listeners_job_metrics_negative.py` | integration | **bare x28** |
| `stall_capture.py` | 152 | 83% | `tests/unit/test_stall_capture_listener.py`, `tests/unit/test_receipts_criterion.py`, `tests/unit/test_receipts_happy_path.py`, `tests/unit/test_receipts_concurrency.py` | unit (pure helpers, the decline paths, the whole chain, and two chains at once) | clean |
| `receipts/` | new | — | `tests/unit/test_receipts.py` | unit | clean |
| `dock_events.py` | 65 | 92% | `test_listeners_active.py`, `test_listeners_state_driven.py` | integration | **bare x28** |
| `discovery.py` | 81 | 99% | `test_listeners_timers.py` | integration | clean |
| `entity_rename.py` | new | — | `tests/unit/test_listeners_entity_rename.py` | unit | spec'd |
| `core/manager.py` (D4 migration) | new | — | `tests/unit/test_manager_entity_rename_migration.py` | unit | clean |
| `pause_timeout.py` | 89 | 95% | `test_listeners_timers.py` | integration | clean |
| `_common.py` | 80 | 91% | `test_listeners_common.py` | integration | clean |
| `job_progress.py` | 48 | 92% | `test_listeners_active.py` | integration | **bare x28** |
| `pose_sampler.py` | 165 | 90% | `test_pose_sampler.py` (unit) | unit | **bare x5** |

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

- **`lifecycle.py` (94%)** — missing lines 115, 126, 129, 144, 516, 521: the
  no-manager early return, the unmatched-vacuum debug-log-and-return, and
  guards inside the finalize/mark-finalized flow. Same defensive shape as
  before this campaign's growth.
- **`path_blockers.py` (95%)** — missing lines 179, 250-251, 256-257: a
  non-dict-room skip inside the watcher-build rule walk, and event-dedup
  guards.
- **`dock_events.py` (92%)** — missing lines 77, 81, 85: event-dedup guards.
- **`job_metrics.py` (94%)** — missing lines 44, 48, 206: capability-read /
  value-parse guards in the metrics-change handler.
- **`_common.py` (93%)** — missing lines 50-51, 73-74, 106, 114: broad-except
  fallbacks in the adapter-vocab/value readers plus a non-dict traversal guard.
- **`pause_timeout.py` (92%)** — missing lines 161, 175, 182-183: guards
  inside the tick (manager gone, unknown map_id, and one new arm not yet
  itemized by name).
- **`discovery.py` (99%)** — only line 190: the body of the periodic
  safety-net `_on_tick` callback; the timer fires it but no test advances the
  adapter-configured interval. Trivial.
- **`job_progress.py` (95%)** — only line 75: the `continue` that skips the
  "unknown" map_id during a tick.
- **`pose_sampler.py` (89%)** — missing lines 93-94, 155, 173, 176, 185,
  193-194, 210-212, 262, 339, 372, 379: the no-`task_status` /
  unreadable-state fallback to the pose `robot_docked` flag and the
  not-attribution / no-live-map vacuum skips (defensive gating). The
  external-only sampling and the parked/docked nulling happy paths are
  covered by `tests/unit/test_pose_sampler.py`.

These are deliberately uncovered at the ~90% meaningful-coverage ceiling: the
teardown/guard branches are defensive, and the sequenced-phase /
mapping-tracker branches in lifecycle exercise paths that require a full
integration boot with a live tracker rather than the per-unit fixtures used
here.
