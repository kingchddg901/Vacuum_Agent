# 01 — Core — Subsystem Test Map

The core package is the orchestrator: `EufyVacuumManager` ties every subsystem
together and owns the live read surfaces the dashboard polls (lifecycle, job
progress, start-status), plus the storage layer, capability cache, error-tracker
latch, the post-job water amendment, and the brand-agnostic charging /
low-battery-return reads. Covered by **428 tests across 16 files**.

Source: `custom_components/eufy_vacuum/core/`
Architecture reference: [33 — The Orchestrator](../../dev/33-the-orchestrator.md), [35 — The Fault Tracker](../../dev/35-the-fault-tracker.md)


### `vacuum_identity.py` — per-vacuum state needs a real vacuum (added 2026-08-08)

Per-vacuum records are created by `setdefault(vacuum_entity_id, ...)` in a dozen
places, and none of them asked whether the id referred to anything. Two records
reached a live install as a result:

| record | how |
|---|---|
| `onboarding["vacuum.your_vacuum"]` | the CARD'S OWN PLACEHOLDER (`src/main.js`), persisted because a status QUERY created the record it was asking about — a read that writes |
| `setup_progress["vacuum.iv"]` | a truncated entity id, carrying a full `completed_steps` / `room_drift_history` record |

Neither corrupted anything, which is why they sat there. The defect is that the set
only ever grew: every typo, placeholder and renamed entity left a record nothing reaps.

Three parts: reads stopped creating (`OnboardingManager._get_map_onboarding(create=False)`),
creation is guarded by `is_real_vacuum`, and a one-shot sweep clears what is already
stored. `test_vacuum_identity.py` (14 tests) pins the shape:

| id | what it holds |
|---|---|
| `VI-1` | a vacuum HA knows is REAL even with no stored record — a NEW vacuum must be addable |
| `VI-2` | a vacuum with a stored record is REAL even if HA forgot it — a rename must not delete history |
| `VI-3` | a placeholder or typo is not real |
| `VI-4` | the sweep removes exactly the orphans, nothing else |
| `VI-5` | **the sweep can never empty `vacuums`** — presence there IS the proof of realness |
| `VI-6` | it runs once; a deliberate re-creation is not re-reaped |
| `VI-7` | planning is pure, so a deletion can be reviewed before it happens |
| `VI-8` | a malformed bucket is skipped rather than taking setup down on boot |
| `VI-9` | a **registered** vacuum with **no state** is real — an offline one must not be swept |
| `VI-10` | a non-dict bucket contributes **nothing** to a delete plan — the filter that makes the sweep loop's own type re-check unreachable |

**VI-1 and VI-2 are the pair that matters.** The discriminator is deliberately not
"already known to the manager" — that would make adding a vacuum impossible — nor
"HA has the entity", which would delete a renamed vacuum's history. Either proof
suffices, and VI-5 guards the catastrophic case: if a stored record ever stopped
counting as proof, this sweep would delete every vacuum on the install.

**VI-9 covers the entity-REGISTRY arm, and carries a fixture trap worth naming.** A
vacuum that is powered off, unavailable, or not yet loaded has no state while its
entity is perfectly real, so `hass.states.get` cannot answer and the registry is the
only thing between a sleeping vacuum and the sweep. If the test also set a state for
that entity, the state arm would return `True` first, the registry block would never
execute, and the test would go on passing **with that whole block deleted** — so
`hass.states.get(...) is None` is an assertion in the test, not a comment, and a
second assertion on an unregistered id keeps a lookup that said yes to everything
from satisfying the first.

⚠ **`is_real_vacuum`'s `if hass is None: return False` is SUBSUMED**, and its red set is
declared empty in the test file rather than left looking like a gap. With the guard
ablated, `getattr(None, "states", None)` skips the state arm and `er.async_get(None)`
raises inside the `try` below it, whose blanket `except` returns `False` — the same
answer by a longer road. Measured over 8 inputs (`hass` `None` with and without a
stored record, with a bad prefix, with a maps-only record; a `hass` with no
`.states`; `.states` set to `None`; a `hass` that knows the entity and one that does
not): every answer identical, nothing escaping either way. Noted because the obvious
next move, "add a test for that guard", cannot succeed.

**VI-10 pins an UNREACHABILITY rather than a behaviour, which is why it adds no
coverage.** The `isinstance(node, dict)` test exists twice — once in
`orphaned_vacuum_keys`, which VI-8 pins, and again inside `sweep_orphaned_vacuums`'
delete loop. The second can never see a non-dict, because every `(bucket, key)` it
iterates came from the first, which answers `[]` for a bucket that is not a dict; the
plan is built four lines above the loop over the same dict, so there is no window for
the type to change. That makes the re-check's unreachability a property of the
*filter*, so the filter is what gets pinned — an unreachable guard with no recorded
reason is the one that gets "simplified" away later.

A **list**, not a string, and that is the whole difference from VI-8: iterating
`"corrupt"` yields single characters, none `vacuum.`-prefixed, so VI-8's first
assertion answers `[]` with the filter removed as well and cannot see this guard at
all (VI-8 bites only through its second row, where `for key in None` raises). A list
of entity-id-shaped strings is the shape that would silently produce *plausible*
orphan keys for a sweep that deletes user data. Ablation-measured: relaxing the filter
to a `None` check reddens VI-10 and leaves VI-8 green, which is what says the two are
not duplicates.

**Two more arms are classified rather than tested, and the file's honest ceiling is
93.75%.** The false arm of `if getattr(hass, "states", None) is not None:` is
DEFENSIVE with no producer outside a test harness — a real `HomeAssistant` sets
`.states` in its constructor and never clears it, both call sites
(`onboarding/manager.py`, `setup/drift.py`) pass one, and the docstring says the
fallback exists for "tests constructing a bare manager", so a test of it would be a
test of the fixture. It is not subsumed (ablated, a `.states`-less object raises
`AttributeError` outside the `try` below) — the input simply cannot arrive from
anywhere this integration runs. With that arm, the subsumed `hass is None` pair and
the unreachable re-check above, 1 statement and 3 branch arms of 64 units stay
uncovered: **93.75%, and 95% is not reachable here** without a vacuous test or a
pragma on a non-logger line. Stated rather than papered over.

---

### `battery_aggregates_migration.py` — replaying a ratio's history (added 2026-08-23)

`test_battery_aggregates_migration.py` (13 tests) covers the one-shot replay of drain
aggregates accumulated before the C17 partnered-numerator repair.

The repair it completes is not the repair itself. C17 gave each drain mean its own
numerator, gated on both halves of the ratio being present, and is correct for a bucket
that starts empty — which is what all three of its own tests construct, and why none of
them could see what happens on an install that was already running. The partnered
numerators are NEW KEYS: an upgraded bucket keeps a `duration_min_sum` holding all-time
data while its numerator restarts at 0.0, so the first job folded in afterwards
publishes roughly one job's drain over every job's duration. Measured on the live
install on 2026-08-23, before C17 had been deployed to it: the next run would have
published 0.0 and 0.0066 %/min against honest figures of 0.292 and 0.4613.

[BAM-1] drives that collapse through the real `_update_aggregate_bucket` rather than
asserting the migration's own bookkeeping. It is the only test here that describes the
harm; the other twelve exist because of it.

The rest weight the REFUSALS and the retries, because this rewrites a user's own derived
history and cannot be undone from anything else on disk:

- [BAM-3] an empty pre-C17 bucket is NOT a target. The first draft of this test used a
  freshly built bucket, which already carries the partnered keys — so it passed against
  a deliberately broken guard and proved nothing. The shape that bites is a vacuum added
  before C17 that has never run: old format, no partnered keys, all sums at zero.
  `vacuum.robin` was in exactly that state on the live install.
- [BAM-4] a numerator PRESENT and 0.0 is not a target either. That is what an honest
  run of drain-less jobs produces under the new rule; the arithmetic looks identical to
  the broken case, so detection keys on absence rather than on the value.
- [BAM-10] a missing subsystem DEFERS and does not latch — reachable rather than
  theoretical, because `async_at_started` fires immediately on a config-entry reload.
- [BAM-11] one unreadable archive does not abort the others, and does not latch.
- [BAM-9] the previous aggregates are snapshotted first.

---

### `pause_timeout_migration.py` — lifting a timeout nobody chose (added 2026-08-09)

`test_pause_timeout_migration.py` (7 tests) covers the one-shot repair that raises a
stored `pause_timeout_minutes_default` of 0 to 15.

The bug it repairs is two-part. The default was 0 — the timeout OFF — and no adapter
declared otherwise; and `get_pause_timeout_settings` PERSISTED that fallback on read,
so the first time anything asked, a hard 0 was stamped into the store and "never
configured" became indistinguishable from "deliberately disabled". The consequence is
a paused run that nothing ever closes: the pause reaper owns it, and the pause reaper
was off. Found on a live install on 2026-08-09.

The tests weight the REFUSALS as heavily as the repair, because this migration
knowingly overwrites a value a user could have set through Developer Tools:

- [PTM-2] a configured non-zero value survives — a repair that rewrote every vacuum to
  15 would satisfy the happy path and silently discard every real preference;
- [PTM-3] an ABSENT value stays absent, so the vacuum keeps inheriting the computed
  default. Stamping 15 here would recreate exactly the read-side write-back the repair
  exists to undo — the bug reintroduced by its own fix;
- [PTM-4] the latch holds, so a user who sets it back to 0 afterwards keeps 0;
- [PTM-7] malformed store buckets do not raise, since this runs at startup and a
  throw takes the integration down with it.

Unlike the room-vocabulary repair it needs no adapter declaration to judge a target,
so it cannot be deferred by a provider that has not finished setting up and latches
unconditionally.

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `manager.py` | 2343 | 95% | `test_manager_lifecycle_status.py`, `test_manager_progress.py`, `test_manager_delegation.py`, `test_manager_start_selected.py`, `test_manager_external_finalize.py`, `test_manager_init_migrations.py`, `test_core_manager_registry.py`, `test_manager_compare_sources.py`, `test_manager_live_pose.py`, `test_core_manager_helpers.py` (unit) | int + unit | **bare x10** |
| `error_tracker.py` | 455 | 96% | `test_core_error_tracker.py` | integration | **bare x1** |
| `capabilities.py` | 339 | 98% | `test_core_capabilities.py` | integration | clean |
| `charging.py` | 42 | 100% | `test_charging.py` (unit) | unit | clean |
| `run_state.py` | 15 | 100% | `test_core_run_state.py` (unit) | unit | clean |
| `water_amendment.py` | 128 | 98% | `test_core_water_amendment.py` | integration | clean |
| `storage.py` | 21 | 100% | `test_core_storage.py` | integration | clean |

`manager.py` is the single largest module in the codebase; most of its public
surface delegates to a subsystem (see [the delegation seam](#whats-tested)),
so its own tests target the logic that genuinely lives in the orchestrator.

---

## What's tested

- **Lifecycle + error overlay** (`LS`) — `get_lifecycle_state` folds the
  ErrorTracker active-run latch into the user-visible message: a live
  `current_message` wins; a blank current message with error history derives a
  "Run had N error(s); last: …" summary.
- **Start-status gates** (`LS`) — `get_start_status` blocks a new run on a paused
  job (`job_paused`), incomplete floor-type onboarding (`onboarding_required`),
  and every-selected-room-blocked (`all_selected_rooms_blocked`, reached by
  building a complete access graph so rule-bearing rooms clear the graph gate).
- **Live job progress** (`PR`) — `get_job_progress_snapshot`: idle terminal
  snapshot, started timeline (estimate / reanchored), completed-room reanchor,
  and **run-anomaly detection**. The anomaly logic + event emission live in
  `ActiveJobTracker.detect_run_anomalies` (`jobs/active_job.py`); the snapshot
  composer calls it (`self.active_job.detect_run_anomalies(...)`) and folds the
  returned fields in. Three anomalies are covered: **stall** (bounds gate blocking
  and the room stuck ≥ 2× its estimate — fires `EVENT_STALL_DETECTED` once per
  room per job), **running_long** (the soft band 1.5×–2× below stall, no event),
  and **skipped** (a queued room advanced past but not completed — fires
  `EVENT_ROOM_SKIPPED` once per room per job). `test_manager_progress.py`
  exercises all three through the manager.
- **Finalize bridge** (`PR`) — `finalize_learning_for_active_job`: no-learning →
  None, missing `started_at` → not finalized, full job → `completed_job`.
- **Room-history ingest** — `_ingest_jobs_index_entry_into_room_history`
  (newer-wins merge, bad-row skips).
- **Pure helpers** (`CMH`, unit) — `_safe_float`, `_safe_int`,
  `_normalize_path_block_action`, `_hours_text`, `_display_label`,
  `_settings_profile_display`.
- **Delegation seams** (`MD`) — every thin forwarder (`return self.<sub>.x(...)`)
  is smoke-tested through the manager so a delegation lost in a refactor fails
  loudly. This is the **#11 / #13 bug-class net** (a forwarder that went missing
  while a listener still called it).
- **ErrorTracker** (`ET`) — latch lifecycle, secondary-error detection.
- **Run-state predicate** (`RS`, unit) — `run_state.py`'s brand-agnostic "is
  the robot cleaning right now?" read, sibling of `charging.py`, feeding the
  current-room non-cleaning accumulator: HA-standard non-cleaning states
  recognized for any brand; **fails open** on unknown/unavailable/empty/None;
  paused/idle/error deliberately excluded; an adapter's declared vocabulary
  *extends* the standard set (never replaces it), matched
  case/whitespace-insensitively, with a malformed declaration falling back to
  the standard set.
- **Capabilities / storage / water amendment** — capability resolution + cache,
  the persistent store round-trip, and the post-job water patch.
- **Maintenance source resolution** (`CAP-5`, `CAP-5b`, `CAP-5c`, `CAP-5d`) — which entity ends
  up counting each component. The order is `user override > own sensor > proxy > picked clock`,
  and each rung is pinned separately because each has its own way of going wrong. `CAP-5b`: one
  picked clock fills every gap without displacing a component that counts itself. `CAP-5c`:
  **`proxy_for` outranks the clock but never an own counter** — a proxy is the adapter's explicit
  statement about one component, the clock a generic per-vacuum fallback, and inverting either
  boundary silently swaps a real counter for a borrowed one. `CAP-5d`: an unresolvable borrow
  falls through to the clock rather than pinning a dead derived id.

  `proxy_for` was deleted on 2026-09-12 and restored on 2026-09-14; the failure that removed it
  is now pinned as `UAC-20` in [09 — maintenance](09-maintenance.md), and the rule that a
  borrowed counter must never drive a Replacement row is pinned across all three brands in
  `tests/adapters/test_adapter_contract.py` — that one bites the exact shape v2.1.0 shipped,
  where Eufy's Swivel Wheel reported the filter's 360-hour service life as its own.

---

## How it's tested

Driven against the real `manager` fixture (`tests/integration/conftest.py`). The
error overlay uses a recording `_FakeErrorTracker` registered at
`hass.data[DOMAIN][DATA_ERROR_TRACKER]`. Progress tests wire a real
`LearningManager` and seed an active job with `_seed_job(...)`. The delegation
smoke test calls each seam with minimal valid args and asserts it forwards
without `AttributeError`.

---

## Known gaps

`manager.py` (94%, 2113 total statements this campaign, up from a
1850-statement baseline — a ~14% growth) — the external-run
capture/review orchestration (`maybe_handle_external_run` /
`_external_grace_finalize` / `confirm` / `resegment` /
`get_external_pending_runs` / `discard`), the room-history ingest helpers, the
registry-model backfill, the init migrations, the job/dock delegations, and
the progress snapshot are covered (the EXT-*, CMR-*, init-migration,
delegation, and progress suites). What's left is 89 missed statements + 74
partial branches (`--cov-report=term-missing` for the current line list) —
still mostly the defensive tail (`# pragma: no cover` best-effort log-only
excepts, malformed-input guards, the recorder-dependent return-overhead
extraction skipped when no recorder is configured under test), but the file's
growth means this list has not been re-itemized line-by-line since the count
last stood at ~16 lines; treat the qualitative description as directional, not
exhaustive.

The remaining per-module gaps are within the held ceiling: `error_tracker.py`
(87%) and `water_amendment.py` (92%) are short of the others only on defensive
except/guard paths; `capabilities.py` (95%), `charging.py` (100%),
`run_state.py` (100%) and `storage.py` (100%) are effectively complete.

### The flag the user owns — `test_user_capability.py` (added 2026-10-19)

**Some capabilities we DERIVE and some we GUESSED, and they were stored as the same
value.** Roborock answers "can this vacuum vary its cleaning path?" from whether the
device's own mop-route select carries a usable value — knowledge. Eufy answered it with
`model_family in {"x10", "x8"}`: a conservative stand-in, made when nobody had checked
the other models, for knowledge that was never gathered. Read as a plain boolean, that
guess **denies a control to hardware that may well have it**.

So the flag moves to the person who can see the machine (`set_vacuum_capability`), and
"nobody has established this" becomes representable. `resolve_vacuum_capability` returns
the user's answer, else what the brand derived, else `None` — and a consumer must test
`is False`, because collapsing `None` reinstates the defect.

**The name is deliberately not `supports_path_control`.** `dispatch/manager.py::
dispatch_goto` reads that one as GO-TO support, and Roborock had been populating it from
the mop-route select — so an unavailable select could have gated go-to. Inert only
because that brand declares no goto service and the earlier guard catches first. Two
capabilities now have two names.

| id | what it holds |
|---|---|
| `UC-1` | "nobody knows" is `None`, not `False` |
| `UC-2` | a brand's derived answer is used when the user is silent |
| `UC-3` | the user wins, **in both directions** — False→True is the headline, True→False lets someone switch off a control their device rejects |
| `UC-4` | clearing hands the question back to detection, so a wrong answer is never a trap |
| `UC-5` | only allowlisted capabilities are user-answerable — without it this is a back door for overriding hardware facts |
| `UC-6` | the answer is durable: the per-vacuum record, **not** the stored adapter config, which `config_loader.py` documents as a flip-flop that reverts at the next restart |

All four behavioural ablations redden it. The card half is
`src/state/supports-cleaning-path.test.mjs` (`SCP-1..4`), which pins the tristate and
the `=== false` gate; collapsing `null` to `false` there reddens two of the four.

