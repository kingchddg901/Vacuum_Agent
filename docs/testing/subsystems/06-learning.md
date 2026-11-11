# 06 — Learning — Subsystem Test Map

> **This is the template.** Learning is the most completely tested subsystem, so
> its test map is the model for documenting the others. Copy this structure
> (coverage map → what's tested → how it's tested → gaps → extending) when you
> write the test map for another subsystem.

The learning subsystem records cleaning runs, rebuilds per-room/per-profile
stats, estimates ETAs with a confidence model, and finalizes completed jobs. It
is exercised by **750 tests across 18 files** (704 test functions, expanded by
parametrization).

Source: `custom_components/eufy_vacuum/learning/`
Architecture reference: [26 — The Learning Record Store](../../dev/26-learning-record-store.md) through [30 — External Runs](../../dev/30-external-runs.md)


### Captured settings the mode cannot apply (`CAP`, added 2026-08-08)

External (app-started) runs are captured by reading the vacuum's global setting
selects per tick — the only window into what the app set, since VA did not dispatch
the job and has no payload for it. But a select keeps reporting a value whether or
not the current mode uses it.

Confirmed on hardware: the Eufy app **disables** the suction picker in mop-only mode,
and `select.<vac>_suction_level` went on reading `Max` throughout. Capturing that
recorded the run as having used Max suction — a number never applied, entering
Learning Review and the estimate buckets looking exactly like a measurement.
Indistinguishable from a real one, which is why it would never have been noticed.

`_drop_settings_the_mode_does_not_use` removes them, symmetrically:

| mode | inert, therefore dropped |
|---|---|
| mop-only | `fan_speed` |
| vacuum-only | `water_level`, `mop_intensity` |
| vacuum+mop | nothing — both halves apply |

`water_level` and `mop_intensity` are dropped together because they are ONE device
value under two label sets (upstream maps Quiet/Automatic/Max onto Low/Medium/High);
dropping one would leave a phantom reading of the same inert setting.

`test_capture_inert_settings.py` (9 tests). The two that stop the filter going wrong
in opposite directions:

- **CAP-3** — vacuum+mop keeps everything, so a fix cannot "work" by dropping too much.
- **CAP-4** — an unrecognised mode drops NOTHING. Parameterised over a real Eufy
  protocol mode the X10 lacks (`Mopping after sweeping`) as well as a recognised alias
  (`Vacuum and mop`), so a FUTURE mode arriving cannot silently be treated as "these
  fields do not matter". Retaining is the conservative branch: discarding a real
  measurement is worse than keeping an inert one, and review lets the user correct it.

Mirrors the dispatch side, where `queue_engine` only writes `water_level` /
`edge_mopping` for mop modes.

---

## Coverage map

| Source module | Stmts | Cov | Test file(s) | Layer | Mocking |
|---------------|------:|----:|--------------|-------|-------|
| `utils.py` | 120 | 99% | `tests/unit/test_learning_utils.py` | unit (pure) | clean |
| `estimator.py` | 535 | 96% | `tests/unit/test_learning_estimator.py` | unit (pure + class) | **bare x1** |

#### The staleness gate (`LE-24`..`LE-29`) — added 2026-11-07, previously untested

`estimator._is_stats_stale` had **no tests of any kind**: `grep -rn
"_is_stats_stale\|_STALE_THRESHOLD_DAYS\|stats_stale" tests/` returned nothing. It has
four arms and a threshold, and it is the only thing that tells a user their learned data
has gone old — the module docstring says the payload carries `stats_stale=True` *"so the
card can warn the user"*, and `learning/manager.py` surfaces it in the dashboard
snapshot. A gate that silently answered `False` would leave the warning permanently off;
one that answered `True` would cry wolf on every rebuild. Neither has a symptom anywhere
else.

It was live when these were written: on the real box one vacuum's `room_stats` carried
`rebuilt_at` 2026-10-11, 27 days against a 30-day threshold.

**`LE-25`/`LE-26` are a PAIR and that is the point.** Together they fence
`_STALE_THRESHOLD_DAYS` in both directions — raise it and `LE-26` fires, lower it and
`LE-25` does. A single "it goes stale eventually" test pins the *direction* and not the
*number*.

> **The first draft of that pair did not bite, and the reason is worth keeping.** It
> built its fixtures from the constant — `_stats_rebuilt_days_ago(_STALE_THRESHOLD_DAYS)`
> — so moving the constant moved the fixture with it, and the test asserted only "the
> gate is `>` relative to whatever the constant happens to be". Ablation proved it:
> 30 → 31 and 30 → 29 both left the suite **green**. The boundaries are literal `30` and
> `31` now. A hardcoded shipped value inside an *assertion* is a FENCE and is the correct
> shape; deriving it from the thing under test is the self-referential trap, the same one
> `tests/replay/test_harvest_units.py` fell into by importing the unit table it was
> meant to be checking (see [`RN0RGR1H`](../../dev/00c-replicas.md)).
| `history_store.py` | 839 | 95% | `tests/unit/test_learning_history_store.py` | unit (`tmp_path` FS) | **bare x1** |
| `stats_rebuilder.py` | 501 | 96% | `tests/unit/test_learning_stats_rebuilder.py` | unit (`tmp_path` FS) | **bare x1** |
| `job_finalizer.py` | 641 | 95% | `tests/unit/test_learning_job_finalizer.py` + `tests/integration/test_learning_services.py` | unit (pure) + integration | **bare x8** |
| `manager.py` | 965 | 95% | `tests/integration/test_learning_services.py` + `tests/unit/test_learning_profile_label.py` + `tests/unit/test_profile_name_filter.py` | integration | clean |
| `services.py` | 268 | 97% | `tests/integration/test_learning_services.py` | integration | clean |
| `external_ingest.py` | 433 | 95% | `tests/unit/test_learning_external_ingest.py` | unit (pure) | **bare x1** |
| `job_segmenter_engines.py` | 100 | 98% | `tests/unit/test_job_segmenter_engines.py` | unit (pure) | clean |
| `room_attribution_engines.py` | 149 | 98% | `tests/unit/test_room_attribution_engines.py` (seam) + `tests/adapters/eufy/test_room_attribution.py` (classifier) | unit (pure) | clean |
| `counter_segmentation.py` | 202 | 96% | `tests/unit/test_counter_segmentation.py` + `tests/unit/test_counter_resegmentation.py` | unit (pure) | clean |
| `brand_facts.py` | 54 | 100% | `tests/unit/test_learning_brand_facts.py` | unit (pure) | clean |
| `external_run.py` | 340 | 98% | `tests/integration/test_manager_external_finalize.py` + `tests/integration/test_manager_lifecycle_status.py` | integration | clean |
| `zone_learning.py` | 94 | 100% | `tests/unit/test_zone_learning.py` | unit (pure) | clean |
| `constants.py` | 3 | 100% | (exercised via `external_run.py` / `test_manager_external_finalize.py`) | unit (pure) | clean |

`counter_segmentation.py` lives at the package root (not under `learning/`) — it
is the shared counter-plateau segmentation primitive used here and by the jobs
subsystem's live rollover, tabled here alongside the engine that wraps it.

¹ `room_attribution_engines.py` reads low in the *learning* run because the real
`swept_area_winding_v1` classifier (winding/swept-area math) is exercised in
`tests/adapters/eufy/test_room_attribution.py` (Eufy-specific, run with the
adapter suite, not these other files); the learning-run number only reflects the
seam-level registry/tuning tests in `tests/unit/test_room_attribution_engines.py`.

Numbers are line coverage with branch coverage enabled, measured by running all
these files together (see [running-tests §per-file vs combined](../02-running-tests.md#per-file-vs-combined-coverage)).

---

## What's tested

### `utils.py` — pure coercion + normalization helpers
`_safe_int`, `_safe_float`, `_safe_bool`, `_room_profile_key`, plus the 1.8.0
area/time normalization, sanity, and idle-wall helpers. Sentinel strings
(`""`, `"unknown"`, `"unavailable"`), `None` defaults, float-string parsing,
non-numeric fallback. Grouped by function (no ID prefix).

**Coverage details:**
- **`_safe_int`**: rejects sentinels and None, converts via `int(float(value))` (raises ValueError on NaN/inf), returns default on any exception
- **`_safe_float`**: rejects sentinels and None, returns `float(value)` as-is (does NOT reject NaN/inf; `float('nan')` succeeds), returns default on ValueError only
- **`_safe_bool`**: rejects sentinels and None, truthy strings `{"true", "on", "yes", "1"}` (case-insensitive, stripped), falsy otherwise; returns `bool(value)` for non-strings with exception fallback

**Area/time normalization + sanity (1.8.0):**
- **`cleaning_area_to_m2`** (`test_cleaning_area_*`): normalizes a raw `cleaning_area`
  reading to canonical m² by the sensor's live `unit_of_measurement` via `_AREA_TO_M2`
  (ft²→`0.09290304`). ft² converts, m² passes through, an absent/unknown unit is left
  as-is (assumed already m² — we never guess a factor), blank/bad → `None`; unit lookup
  is case- and space-insensitive.
- **`area_sanity`** (`test_area_sanity_*`): the device run total is the upper bound —
  `attributed_sum > sensor_total * 1.10` (default `AREA_OVER_ATTRIBUTION_TOLERANCE`) sets
  the `area_over_attributed` flag; under-bound, exact, and within-tolerance sums pass, and
  it returns `None` when there is no usable sensor total.
- **`evaluate_idle_wall_hold`** + the `IDLE_WALL_HOLD_*` constants: the pure cold-start
  idle-wall decision — holds an otherwise-eligible completed run whose wall time exceeds
  active cleaning by ≥ the 20-min floor with no charge/wait break-phase or logged error
  (`reason == "extreme_idle_wall"`). Exercised by `tests/unit/test_idle_wall_guard.py`
  alongside its finalizer wiring (below).

### `estimator.py` — compute helpers + `LearningEstimator` (prefix `LE`)
- **Confidence model** (LE-1..LE-7): score→breakpoint mapping, clamping, the
  learned-base + sample-bonus + variance/intensity/accuracy-drift penalties, the
  default-source 0.20 base.
- **Velocity** (LE-8..LE-9): runs-to-tier for new vs already-trusted vacuums.
- **Overhead** (LE-10..LE-12): startup/transition/return always present; mop-wash
  cycles scaling with projected mop minutes; non-`by_time` modes yielding zero.
- **Wash-frequency normalization** (LE-13..LE-14): alias lookup, empty→`unknown`.
- **Room matching** (LE-15..LE-17): exact match, ignore-intensity fallback pass,
  no-match.
- **Estimator surface** (LE-18..LE-23): `estimate` error payload vs full result,
  `next_room`, `reanchor_timeline` offset/marking.

### `tests/unit/test_estimate_reason_keys.py` — an unavailable estimate the user can read (prefix `ERK`)

A cross-language gate, and the second instance of the shape `BRK` covers for start refusals
([02 — Jobs](02-jobs.md)): the backend sends a machine code, the card resolves it through
`learning.estimate_error.<code>`, and the backend's English `message` is the last-resort
fallback. Here the defect was not an empty vocabulary but **the wrong FIELD**. The panel's
branch is entered by `estimate.error || estimate.available === false`, and the three codes
arriving on the second path are carried by `reason` — which the renderer did not read, so
`code` was undefined for all of them and `coded-label.js` ranks `message` above its
`genericKey`. Two of the three rendered the backend's English in all 17 packs; the third is a
PREPARED key rather than a fixed defect — see `ERK-6`.

The previous release added a key to this family for `estimate_failed`, and **that key's presence is why the
sink read as covered**: it is emitted per ROOM by `manager.py`'s `room_entries` loop, which
no surface renders, so it can never reach this panel. It is kept as the seam for when one
does, and `ERK-5` pins that it must not be read as coverage.

| case | what it holds |
|---|---|
| `ERK-1` | every reason `get_planned_job_estimate` can emit has a key (`ready` excepted — the available case renders a figure, not a sentence). The function needs a live hass so it cannot be executed the way `BRK-1` executes its ladder; it is sliced from its own `def` and walked as an **AST**, because the third code is the literal default inside `str(estimate.get("reason", "estimate_unavailable"))` — a shape no `"reason": "..."` pattern matches. The equivalent miss has happened here before: the census's start-blocker list was missing `blocked`, the default of `preflight.get("reason", "blocked")`. |
| `ERK-2` | the mutation control for that detector — and it earned its place: the first version of the walk descended into `.get("reason", …)` collecting *every* argument, so it harvested the key name and demanded a `learning.estimate_error.reason` key |
| `ERK-3` | the inner estimator declares no `reason` of its own, which is **what makes the default the whole set** rather than an open one. If it ever declares one, that value reaches the panel through the `.get` and is invisible to `ERK-1`, which slices the manager — so this fails and says to re-enumerate. |
| `ERK-4` | the estimator's `error` set is exactly `{no_payload}` — each passes straight through `get_planned_job_estimate`'s `**estimate` spread onto `estimate.error` — and `no_payload` is deliberately NOT in this family: it keeps `learning.estimate_queue_first`, the one case with something for the user to DO |
| `ERK-5` | `estimate_failed` stays keyed, still has a producer, and is not emitted by this panel's producer |
| `ERK-6` | `estimate_unavailable` is PREPARED, not live. Its literal is real, so `ERK-1` requires a key — but `available` can only go false through the one estimator return that *also* sets `error: "no_payload"`, which the renderer short-circuits before the resolver. Every clause of that argument is pinned: each return sets `can_run_now`, the False one carries exactly `no_payload`, and the short-circuit exists. **Enumerating a producer's literals is not the same as establishing reachability** — I called this a third fixed defect on the strength of the literal alone, which is the identical conflation that made `estimate_failed` read as coverage one release earlier. |

The card half is `[EST-3]` in `src/renderers/backend-sentence-vocab.test.mjs`, and it drives
the **renderer** rather than re-implementing its resolver call. That distinction is the whole
reason it exists: `[EST-1]` re-implements the call, and **stays green against the shipped
bug** — measured by reverting `code: estimate.error || estimate.reason` to `code:
estimate.error`, which turns `[EST-3]` red and leaves `[EST-1]` passing. A test of a resolver
cannot see a wrong argument at the call site.

### `history_store.py` — file-backed store + helpers
`_vacuum_slug`, path construction, JSON read/write round-trips, completed-job
build/save/load, jobs-index payloads, accuracy/room/job stats load, the
`build_completed_job_payload` outcome logic (learning blockers,
`used_for_learning` flip). Grouped by function/method. The `"interrupted"` outcome
of a stranded/force-finalized run is blocked from learning
(`test_build_completed_job_payload_interrupted_blocks_learning`: `job_interrupted`
blocker, `used_for_learning` False), and the jobs-index build carries the 1.8.0
marker keys (`origin`, `has_attribution_disagreement`, `area_over_attributed`) the
self-heal detector keys on.

**`HS-14`–`HS-21`** (added 2026-11-07, 90% → **93%**; 796 of 839 statements) close
the id-validation and finalize-edge gaps:

- **`HS-14`** — every path builder refuses a traversal id, while the *loaders*
  translate it to `None`. That split is deliberate and `get_completed_job_path`'s
  docstring explains why: the id reached it from `restore_learning_job` "as
  caller-supplied input and was interpolated here unvalidated — pathlib does not
  normalise '..', so a crafted id gave those services an arbitrary *.json overwrite
  primitive." It also pins the regex's real boundary: `^[A-Za-z0-9._+-]+$` **admits
  the dot**, so `".."` is a valid id yielding a file named `...json` *inside*
  `jobs_dir`. The guard rejects traversal, not every odd id.
- **`HS-17`** is the one with a consequence beyond a shape check. A job finalized
  while still paused has to accrue that open pause: `paused_duration_seconds` only
  accumulates on *resume*, and paused time is subtracted from cleaning time
  downstream, so losing the final pause inflates the learned duration for every
  room in the run.
- **`HS-20`** pins `None` against `0` in the timing helpers. `_idle_seconds`
  answering 0 for "I could not tell" is a measurement the caller would trust; it is
  documented to fall back to the raw gap on `None`.
- The rest: a corrupt phased parent loading as `None` (`HS-15`), the `0.0`
  wall-clock fallback (`HS-16`), a parentless phase as a no-op (`HS-18`), an
  undeclared phase appended in index order rather than dropped (`HS-19`), and
  `_native_finalize_brand` refusing an empty entity id (`HS-21`).

**Of the 31 statements still uncovered, 16 are deliberate**: 15 are shape guards the
coverage triage marked DEFENSIVE ("keep the guards; do not pad coverage with them" —
no producer emits those shapes), and 2113 is a genuinely unreachable `else` arm. The
remaining ~15 are ordinary follow-up.

#### The live:RECHARGE-ATTR-1 wiring (`HS-T6`, `HS-T7`) — done

The last four statements (2209-2212) are closed. The *predicate*
(`monotone_shift_run`) was already covered in `test_external_ingest_attribution.py`
with runs of 3/1/0. Those fence `_SHIFT_BLOCK_MIN_RUN` **downward only**: lower it
to 1 and the file's two run-of-1 cases go red (`test_a_single_disagreement_does_not_block`
and `test_shift_must_be_consecutive`, which is also a run of 1), but raise it to 3
and every one of them still passes, because a run of 3 blocks either way. The upward fence is `HS-T6`, whose three rows
make a run of exactly **2**, against `HS-T7`'s exactly **1** — so between them the
constant cannot move in either direction unseen, and a boundary test added to the
unit file later would be padding rather than coverage. (The one place that number
was genuinely loose was the replay harness, which had copied it; see
[01 § the replay harness](../01-overview.md#the-replay-harness).) What was open was
the wiring inside
`build_completed_job_payload`, and reaching it is not a matter of handing the builder
a `room_timings` list — **there is no parameter for one.** The rows have to be
produced, by the counter segmenter plus the pose reconcile, which means satisfying
the whole chain:

1. **Not a phased job and not a native-finalize brand.** The block lives inside an
   `else:` arm; a job carrying `phases` takes the earlier arm and never evaluates the
   predicate at all. Measured: adding `phases` makes the blocker vanish.
2. **`pose_samples` truthy** — the wiring sits inside `if _pose_samples:`.
3. **Three counter segments.** A run of 2 needs two shifted rows *and* a successor for
   the second, because the last row can never contribute to the run.
4. **`segment_count == queue_count`**, so `transit_capture_valid` → `positional_valid`
   is True. This is the subtle one, and the reason the note used to say "the FLAG
   rather than RESCUE branch": with `positional_valid` **False** the reconcile takes
   its RESCUE arm, which rewrites `room_id` and writes `pose_correction: "rescued"` —
   and never writes the `attribution_disagreement` the predicate reads. The two arms
   are **mutually exclusive**, so an "invalid capture" fixture cannot reach this code
   at all. Ablation confirms it: forcing `positional_valid=False` reddens *both* tests.
5. **Every pose window must name the next segment's room**, which is what makes the
   slide monotone rather than three unrelated disagreements.

`HS-T7` is the discriminator, not padding: one shifted row is ordinary border
ambiguity, which the FLAG branch exists to leave alone, and
`has_attribution_disagreement` is True in **both** tests — so only the outcome block
separates "ambiguous" from "disqualified". That is why `HS-T6` asserts on
`used_for_learning` / `learning_blockers` rather than on the disagreement rollup.

> **`_dominant_room` is a mode over the window, not the first tick**, and the first
> draft of `HS-T7` got this wrong: it flipped only the first of segment 0's three
> ticks, which leaves the shifted room dominant 2-to-1, so the run stays at 2 and the
> test would have asserted the opposite of what the code does. All three ticks are
> flipped. Likewise `_ps`'s `ca` argument is passed on every sample on purpose — a
> pose stream with no `cleaning_area` resolves to mode `anchor_only` and the reconcile
> leaves the rows untouched, giving a fixture that quietly proves nothing.

The read/write error arms that used to be on that list — 553-555, 600-603 and 766 —
are **done**, as `TS-8..TS-10` in `test_rmw_tristate.py` where the note said they
belonged (that is what took the count from 43 to 35):

- **`TS-8`** — the primitive's catch-all, reached with input that *cannot* reach the
  handlers above it: invalid UTF-8 makes `read_text` raise `UnicodeDecodeError`,
  a `ValueError` subclass but not a `JSONDecodeError`. Without the catch-all the read
  *raises*, and an RMW caller promised a tri-state gets an exception instead of
  `UNREADABLE` — the one outcome the mechanism exists to report.
- **`TS-9`** — `write_json` must not orphan its temp file when `os.replace` fails,
  parametrised over an `OSError` and a `KeyboardInterrupt`. That second row is the
  point: the handler is `except BaseException`, which looks like a mistake and is
  not. Ablation confirms it — narrowing it to `except Exception` reddens **only**
  the `KeyboardInterrupt` row, so a Ctrl-C between the write and the replace is
  precisely when an orphan would otherwise be left, and least likely to be noticed.
- **`TS-10`** — the trouble-rooms reader refusing a payload that parsed fine but is
  the wrong *container*. `read_json_outcome` accepts a dict **or** a list by design,
  so a list is `READ_OK`; converting that to `UNREADABLE` is what stops the RMW
  writer, which would otherwise read `(READ_OK, None)` as "no trouble rooms yet" and
  replace a store it could not understand with only its own delta.

### `stats_rebuilder.py` — pure builders + `LearningStatsRebuilder`
`_room_key`, `_room_baseline_key`, `_stddev`, and the rebuild paths that turn
archived completed jobs into room/profile/job stats + the jobs index.

### `job_finalizer.py` — split across two layers
- **Unit** (pure helpers): `_parse_iso_to_utc`, `_compute_total_error_seconds`
  (interval merge, unresolved-bound-by-next, zero-duration skip),
  `_apply_water_actuals` (dock-water totals, wash-overhead split, unexpected
  cycles).
- **Integration** (the pipeline): cancel-likely detection branches
  (LS-40..LS-47), error-tracker latch harvest, error-seconds adjustment,
  incomplete-run/trouble-room logs, battery-metrics handoff (LS-53).
- **1.8.0 additions**: `_duration_state_to_seconds` converts a bare-number
  `cleaning_time` to seconds by the adapter-declared `cleaning_time_unit`
  (Roborock reports minutes — previously stored 60× low); `_apply_idle_wall_hold`
  wires the pure idle-wall verdict into the outcome (held via a restorable
  `extreme_idle_wall` learning-blocker, never a hard exclude), with
  `_run_had_break_phase` supplying its charge/wait exemption — both covered by
  `tests/unit/test_idle_wall_guard.py`, which also golden-checks real archive records.
  That file also covers `_run_had_charge_wait_phase`: the `mid_job_recharge` flag now
  trips on a deliberate native `charge_wait` step (not only an unplanned deep-low
  return), keeping that intentional recharge out of the per-config drain buckets — a
  plain `wait` phase is never flagged.
  The forced `"interrupted"` lifecycle (a stranded run that was force-finalized) is
  covered by `test_collect_inputs_interrupted_outcome` (it takes the `was_interrupted`
  arm and skips the cancel-likely probe rather than misclassifying a truncated run as
  completed).

### `manager.py` + `services.py` — orchestration + HA services (prefix `LS`)
LS-1..LS-53 in `test_learning_services.py`: service registration, the
read/snapshot services (history snapshot, metrics snapshot, room estimates),
exclude/restore round-trips, finalize variants (forced status, cancelled,
completed-clears-incomplete), accuracy recording and the trust-metrics path, the
old-format jobs-index rebuild, and `async_preload_learning_stats` guards.

`test_learning_profile_label.py` additionally covers `manager._settings_profile_label`
(SPL-1/SPL-2) as a focused unit.

The 1.8.0 **learning-processing toggle** (`set_learning_processing` /
`process_pending_runs` — collect-always, process-on-demand, with a pending-count
display) is covered by `tests/integration/test_learning_processing_toggle.py`:
default-on + toggle, the pending counter, finalize gating the stats rebuild on the
toggle, off-does-not-catch-up vs on-catches-up, `process_pending_runs` staying off,
and the dashboard-snapshot exposure. The **self-heal jobs-index detector** (rebuilds
the index once when the new marker keys `origin` / `has_attribution_disagreement` /
`area_over_attributed` are missing) rides the same snapshot seam. Separately,
`tests/integration/test_manager_external_finalize.py` drives the external grace-timer
finalize end-to-end (`EXT-FIN-1`), the W5c pose-only stand-up record when the counter
segmenter finds nothing (`EXT-FIN-2`), the slot-clears-on-build-error guard
(`EXT-FIN-3`, the zombie-`external`-slot protection), and the learned-baseline read
on that path — present bands reaching the segmenter (`EXT-FIN-4`) and a degenerate
(`EXT-FIN-5`) or outright corrupt (`EXT-FIN-6`) `room_stats.json` degrading instead
of raising out of the executor job — plus the
confirm/re-segment paths that graduate a reviewed run. See
[The learned-baseline read](#the-learned-baseline-read-and-why-the-three-sites-differ)
for why the three read sites filter differently.

### `external_ingest.py` — app-started capture + dispatched reconcile
Detection of runs started outside HA, the pending-record build + persistence, the
re-segmentation service, and the confirm path that turns a reviewed run into a
learned job (the v2 samples-saved re-segment plus the v1 fallback). The
pose-based room-attribution path (`_resolve_attribution` / `_attribute` /
`build_attributed_job`) runs the resolved room-attribution engine over a run's
pose stream to pre-fill which managed rooms it cleaned; the engine itself is
tested separately (see the room-attribution seam below), and its
caller-side wiring is covered by `tests/unit/test_external_ingest_attribution.py`
(the `_apply_pose_identity` / `_dominant_room` enrich of counter segments, the
`build_attributed_job` pose-only stand-up record — the Roborock/noop-segmenter
shape — the sensor-total sanity stamp, engine-error degradation to counter-only,
and a real-capture stale-`cleaning_area` regression).

Since 1.8.0 the same file also reconciles **dispatched** runs:
`reconcile_dispatched_identity` compares the atomic finalize's positional (segment
K → queue room K) identity against the native current-room the pose sampler
buffered and **confirms** on agreement, **rescues** when `positional_valid` is
False, or **flags** an `attribution_disagreement` (never silently overriding a
working assignment) — the `test_reconcile_*` cases cover confirm / rescue / flag
plus the anchor-only, no-pose, and unnamed-window no-ops. Attribution and
reconcile run for external **and** dispatched runs on **both** Eufy
(`live_pose`) and Roborock (`native_current_room`).

### `job_segmenter_engines.py` — pluggable job-segmenter seam
The `JobSegmenter` registry + the `counter_plateau_v1` engine: byte-identical
delegation to `counter_segmentation` (the fidelity battery), `DEFAULT_TUNING`
mirroring the module constants, and the counter-plateau fallback — not noop — for an
absent/unknown engine. The legacy `eufy_counter_v1` id is dual-accepted and has its own
registry-row assertion.

### `room_attribution_engines.py` — pluggable room-attribution seam
The sibling of the job-segmenter seam (it owns *which managed room* a segment is,
not its *time/area* boundary). Split across two files:
- **Seam tests** (`tests/unit/test_room_attribution_engines.py`): the
  `get_room_attribution_engine` registry — resolves a registered engine, the
  Eufy-fallback for an absent/unknown name, the `known_names` list — plus
  `DEFAULT_TUNING`-by-reference, `validate_tuning` (partial merge over defaults),
  and the `NoopRoomAttributor` (empty result, key-rejecting `validate_tuning`).
- **Classifier tests** (`tests/adapters/eufy/test_room_attribution.py`, run with
  the adapter suite): the real `swept_area_winding_v1` rule — segment by
  `current_room`, drop transit by path-winding, separate cleaned-vs-parked-dock by
  swept `cleaning_area`, and the anchor-only fallback when area is absent.
  Validated on the three adversarial external runs (9/9 cleaned-room calls).

### `brand_facts.py` — the BrandFacts contract learning reads instead of the adapter
`EufyBrandFacts` surfaces each adapter fact faithfully (entity ids, alias maps,
mid-run + cancel vocab, engine specs — `BF-1`); `cancel_service_exclusion_states`
is normalized, stripped/lowered, matching the caller that used to do it inline
(`BF-2`); empty/absent adapter config degrades to safe defaults — `None` / `{}`
/ empty set (`BF-3`); `brand_facts_for()` resolves an adapter-registry-backed
`EufyBrandFacts` (`BF-4`). This is the seam a host re-hosting the learning
engine swaps to port a new brand without learning ever importing the adapter
directly — see docs/dev/10-learning-system.md §9.3.

### `external_run.py` — app-started (external) run capture + review, on the manager
`ExternalRunManager` owns the whole external-run lifecycle: detect + open/close
the capture slot, the grace-timer machinery that defers finalize while the
robot stays docked mid-run (task_status-driven re-checks), booking a mid-run
dock as overhead, segmenting the buffered samples into a pending review
record, and the review-wizard server side (confirm / list-pending / discard /
resegment). It was extracted from `core/manager.py`, which keeps thin
delegators for every moved method, so its tests live under the manager's own
suites: `tests/integration/test_manager_external_finalize.py` drives the
grace-timer finalize end-to-end (`EXT-FIN-1`), the pose-only stand-up record
when the counter segmenter finds nothing (`EXT-FIN-2`), and the
slot-clears-on-build-error guard (`EXT-FIN-3`); `test_manager_lifecycle_status.py`
covers the capture-open path. `EXTERNAL_FINALIZE_GRACE_S` /
`EXTERNAL_GRACE_MAX_RECHECKS` (`constants.py`) size the grace window and its
recheck cap.

**The review-wizard server side**, same file: `CXR-*` (confirm), `DXR-*`
(discard), `RXR-*` (re-segment), `GEP-*` (list pending), `ERO-*` (return
overhead), and `PJI-*` for the `pending_job_id` validator all three share.

`PJI-1` is the one to read first. The card echoes `pending_job_id` back on
confirm / discard / re-segment, each of which interpolates it into a filesystem
path before unlinking or rewriting — and `pathlib` does not normalise `..`, so
`_is_valid_pending_job_id` is what stops an authenticated caller turning that
into a delete/write primitive over an arbitrary `.json` path. It is parametrised
over six malformed shapes against all three handlers.

> **Its assertion is a surviving SENTINEL file, not the return value, and that
> distinction is load-bearing.** A valid-but-missing id already returns
> `{'ok': False, 'error': 'pending_not_found'}` from re-segment's own `except`
> arm, byte-identical to the guard's refusal — so a test checking only the dict
> stays green with the guard deleted. The sentinel in turn only works because the
> helper creates `external_jobs/` first: the OS resolves path components left to
> right, so with that directory absent the traversal fails on ENOENT before `..`
> can cancel, and the assertion rides on a path that cannot resolve. Measured:
> without the `mkdir`, deleting re-segment's guard reddened nothing.

The rest close the error arms the happy-path tests leave open: a failed unlink
reported rather than swallowed (`DXR-2`), the two best-effort swallows **after**
graduation that must not fail an already-written job — the pending cleanup
(`CXR-5`) and the stats rebuild (`CXR-6`) — a present `room_stats.json` whose
baselines reach the re-segmenter (`RXR-5`, against `RXR-3`'s absent-file
fallback), and a non-cleaning span with equal endpoints skipped instead of booked
as a 0 s return trip (`ERO-3`).

#### The learned-baseline read, and why the three sites differ

All three external-run entry points read `learned/room_stats.json` →
`room_baselines`, and **they do not read it the same way** — which looks like the
classic shorter-copy divergence and is not:

| Site | Hands the callee | Filters by `map_id`? |
|------|------------------|----------------------|
| `_finalize_external_run` → `build_pending_record` | the raw list + a `map_id` | no — the callee does |
| `resegment_external_run` → `resegment_pending_record` | the raw list + a `map_id` | no — the callee does |
| `confirm_external_run` → `build_graduated_job` | `bands_by_slug`, keyed by slug alone | **yes, it must** |

The first two route through `external_ingest.py::_baseline_area_by_slug`, which
drops every foreign-map entry itself, so a filter at those call sites would merely
duplicate that predicate. Confirm collapses the map dimension *before* the call —
`bands_by_slug` is keyed by slug only — so filtering there is load-bearing:
without it the build is last-entry-wins across maps and no code downstream can
recover the right band. `CXR-7` pins that by consequence rather than by spying:
two bands share a slug, the foreign-map one is written second and would block the
confirm, so the filter is the only reason the run graduates.

Three facts worth keeping, all measured 2026-11-07:

- **`map_id` is an `int` on disk** (`stats_rebuilder.py` emits it through
  `_safe_int`) while the live map id is the string `"6"`. Every comparison coerces
  both sides with `str()`; `EXT-FIN-4` asserts the int arrives unconverted so a
  fixture cannot quietly agree with a reader that dropped the coercion.
- **The guards are not symmetric.** `(json.load(handle) or {})` is load-bearing at
  all three sites — a bare `null` is valid JSON, so `except (OSError, ValueError)`
  does not catch it, and `None.get(...)` would raise `AttributeError` out of the
  executor. The *trailing* `or []` is only load-bearing at confirm, which iterates
  the value directly; the other two pass it to a callee that already opens with
  `for entry in baselines or []`. `EXT-FIN-5` (finalize) and `RXR-6` (re-segment)
  each record that asymmetry in their docstrings and prove it by ablation — removing
  their trailing `or []` reddens **nothing**, a declared-empty result rather than a
  discovered one — while `CXR-8` is the site where that same guard does bite.

  The degenerate-payload matrix, all three payloads being valid JSON that the
  `except` therefore cannot catch:

  | | `null` | `{}` | `{"room_baselines": null}` |
  |---|---|---|---|
  | finalize | `EXT-FIN-5` | `EXT-FIN-5` | `EXT-FIN-5` |
  | confirm | `CXR-10` | `CXR-10` | `CXR-8` |
  | re-segment | `RXR-6` | `RXR-6` | `RXR-6` |

  `CXR-8` sits in its own cell because confirm is the one site that iterates the
  value, so only there does a null `room_baselines` reach a `for` statement; it
  cannot reach the `or {}` half, whose payload parses to a dict. Of the cells, only
  the `null` column can bite — `{}` is covered by `.get`'s own default, so it is a
  coverage case and each docstring says so rather than claiming a proof.
- **The `ValueError` half had never run at any of the three sites**, and the reason
  was the fixture shape rather than anyone's intent: the suite's only
  `room_stats.json` writer serialised through `json.dumps`, which cannot emit bytes
  that fail to parse. The arm was unreachable *by construction*, so no amount of
  care writing tests against that helper would have found it.
  `_write_room_stats_text` writes raw text so it is reachable at all, and the
  payload helper now delegates to it. All three sites are driven with a truncated
  file — `RXR-7`, `EXT-FIN-6`, `CXR-9` — against `RXR-3`'s `OSError` half.

  It took three tests rather than one because **the predicate has three copies with
  three different bodies**, and a differing body is a differing consequence:

  | Site | Except body | What a corrupt file costs |
  |------|-------------|---------------------------|
  | finalize | `baselines = []` | the read is inside an `async_add_executor_job`, so an escape loses the **whole pending record** and the event — the app-started run is gone |
  | confirm | `pass` | `bands_by_slug` stays `{}`, so the gate reads **cold_start** rather than blocking |
  | re-segment | `baselines = []` | the re-segment proceeds with no learned areas |

  Proving one copy establishes only that the exception is *named* somewhere, not
  what each site does next. Ablation confirms they are independent: stripping
  `ValueError` from any one site reddens exactly that site's test and nothing else.

  `EXT-FIN-6` asserts the **event**, not the baselines, and that choice is
  load-bearing — with the guard intact the bands are empty, which on the baselines
  alone is indistinguishable from `EXT-FIN-1`'s absent-file case. The event is what
  separates "degraded" from "raised".

  **Still open:** confirm's degenerate-payload cases beyond `CXR-8`'s null.
- **Finalize's successful read had never run.** `EXT-FIN-1`'s own note said the
  absent-file `except` was "exercised for free" — no test had a `room_stats.json`
  on disk while a finalize went through, so the read itself was unexecuted until
  `EXT-FIN-4`. The spy on the real `build_pending_record` is what makes it bite:
  hardcoding `baselines=[]` leaves `EXT-FIN-1` green and only `EXT-FIN-4` red.

> **`config_dir` is per-test, not shared.** `RXR-3` used to unlink
> `room_stats.json` before asserting its absence, on the stated grounds that phac's
> `config_dir` is shared across tests. It is not: `tests/conftest.py` overrides
> `hass_config_dir` with a function-scoped `str(tmp_path)`, and a probe confirmed
> two tests in one module see different directories. The unlink was a guaranteed
> no-op guarding a hazard that does not exist; it is gone, and the assertion stays
> as a precondition that would go red if module-scoped seeding were ever added.

#### `_room_footprints` — the cold-start size fingerprint (`RFP-1..3`, `EXT-FIN-7`)

The raster footprint map (`{device room id → m²}`) is what the external-run
shortlist ranker falls back on *before any room has a learned area*: when nothing is
learned yet, how big a segment is, is what says which room it was. So an empty
footprint map is not cosmetic — it is the ranker having nothing to go on, on exactly
the runs it exists for.

**It had no tests at all.** A grep returned nothing, and measurement agreed: only
`if not map_data: return {}` had ever run.

Two things about the fixture are worth copying rather than re-deriving:

- **It is built by the production encoder**, `mapdata_dict_from_obj` — the same call
  the live memory path makes — so the key set and the base64 come from production
  code and agree with the live dict by construction.
- **Do not copy `MS-1`'s raster.** Its two rooms are 3×3 = 9 cells, and at
  resolution 5 that is 9 × 0.0025 = 0.0225 m², which `_area_m2` rounds to **0.0** —
  so both fail the consumer's `area > 0` and the result is `{}`. The loop would
  execute, the test would pass, and the only output demonstrated is the same empty
  dict the old coverage already had. Measured through the real producer: at
  resolution 5 a room needs **20 cells** to be visible at all (19 → 0.0, 20 → 0.1).

That rounding is also why `area > 0` is live and load-bearing. The producer applies
no minimum-pixel filter, so without that guard a one-cell speckle enters the
fingerprint claiming a real room is 0 m². `RFP-2` drives it with a sliver *alongside
a surviving sibling*, because asserting `{}` alone would also pass if the loop were
skipped entirely.

**Two guards there are DEAD, and the docstrings say so instead of implying coverage:**

| Guard | Why it cannot fire |
|-------|--------------------|
| `rid > 0` (the other half of the same `and`) | the producer admits a cell only through `0 < rid < _CATCH_ALL_RID` and emits that same rid as `number` |
| the inner `except (TypeError, ValueError)` | `number` is always an `int` and `area_m2` always a `float` from `round()` — **and** the producer call sits *outside* that `try`, so even a producer raise lands in the outer `except` instead |

A DEAD verdict is only as good as the premise under it, and a premise with no test is
a comment — so `MS-21` pins that gate on the producer side. Widening it reddens three
tests across both layers, `RFP-1` among them (it asserts the catch-all rid never
reaches the footprint map).

`RFP-3` pins the outer `except Exception` and is labelled as pinning a **swallow**
rather than a reachable path: `async_get_map_data_dict` documents that it never
raises, so the test patches away the very boundary whose contract makes the guard
unnecessary. It earns its place because the comment on that except promises something
about the *whole* finalize — footprints are fetched before the record is built, so an
escape there loses the record and the event, not just the footprints.

`EXT-FIN-7` is the path to `RFP-1`'s piece: it spies on the real
`build_pending_record` through the grace finalize, so footprints computed correctly
but dropped on the floor — or passed under the wrong keyword — go red there while
`RFP-1` stays green. Ablation confirms the split: stubbing the finalize's call while
leaving the method intact reddens `EXT-FIN-7` **alone**.

#### `_external_queued_room_ids` — the device's own tap order (`QRI-1..4`)

The live-map camera's `active_segments` attribute is the **device's** record of which
rooms were selected and *in what order*. For an app-started run that is ground truth,
where the alternative is inferring the cleaned set from swept area — which gives you
membership but never the order the user tapped. It drives `not_reached` on the
external record, and is gated on the adapter declaring
`external_run.queue_from_active_segments` (Dreame), so a brand without such a
snapshot keeps the pose-only path.

**Every guard in here is live**, which is the opposite of `_room_footprints` above and
for one reason: that loop consumes a list built by *our own* producer, so two of its
guards are dead. This one consumes an **attribute off another integration's camera
entity** — arbitrary data that may be absent, a dict, a string, or carry duplicates
and zeroes, with nothing upstream normalising it. So `int()` really can raise,
`rid > 0` really can be false, and the dedupe really can fire. `QRI-3` is a table of
nine such shapes.

Two of those rows are worth knowing about:

- **`"1,2,3"` (a string).** A string *is* iterable, so without the
  `isinstance(seg, list)` refusal the loop would walk **characters**, the commas
  would be silently skipped by the `int()` guard, and the result would be `[1, 2, 3]`
  from something that was never a list.
- **`[]` must come back as `None`, not `[]`.** The caller distinguishes "no snapshot
  available" from "a snapshot that selected nothing"; the trailing `or None` is what
  makes that distinction, and `QRI-3` pins both halves.

Every test here drives the **real** `_resolve_live_map_image_entity` through the
documented per-vacuum override, which is existence-checked — so these cover the
wiring as well as the parsing and there is no piece-vs-path split to make.

Two things the ablation established that reading the table would not have:

- `dedupe_first_position` is **also an order assertion** — `[2, 1, 2, 3, 1]` dedupes
  to `[2, 1, 3]`, so sorting the output reddens it as well as `QRI-2`. Two rows guard
  the tap order, not one.
- `QRI-4` (no resolvable camera) is **not purely a resolver test**: `cam` being None
  leaves `seg` None, and the element loop sits *outside* the `try`, so it reaches the
  same `isinstance` refusal as the absent-attribute row by a different route. Delete
  that refusal and `QRI-4` raises rather than returning None.

### `zone_learning.py` — saved-zone TIME learning (pure, `ZL-1..ZL-21`)
A deliberately tiny parallel to room learning: a saved zone has a stable
`zone_id`, a deterministic (never-learned) area, and cleans in one
uninterrupted pass, so the only thing learned is a **wall-clock time average**
keyed by `(zone_id, clean_mode)` (the `"mop"`/`"vacuum"` bucket).
`collect_zone_observations` pulls a single-zone phase's timing into one
observation and skips multi-zone steps (time isn't attributable to one
`zone_id`) and non-zone/malformed input; `update_learned_zone` seeds
`avg=wall, count=1` on the first sample then runs a running mean, keeping mop
and vacuum (and different zone ids) in separate buckets;
`record_observations` folds a batch and returns the applied count;
`estimate_zone_seconds` prefers the learned average once a sample exists,
falls back to area × a per-mode rate before any sample, and clamps the
estimate to a sane band. Store lives on the map bucket
(`map_bucket["learned_zones"]`), persisted with the map.

**Reading a store this build did not write (`ZL-11..ZL-20`).** The module is at
100%, and the half that was uncovered until 2026-11-07 is every `except` arm and
`isinstance` re-seed that handles a `learned_zones` store whose shape is wrong.
Those are normally the shape to leave uncovered and classify — one stage
re-validating the one before it — and these are the exception, for two reasons
worth keeping straight:

- **The producer is a file, not a function.** This store is `learned_zones` as some
  earlier build left it on disk, read back across versions and recoverable by hand.
  There is no in-process signature guaranteeing its shape.
- **The bad value is persisted, not discarded.** `update_learned_zone` mutates a
  store the caller then writes. An arm that raised instead of re-seeding would break
  learning for that whole map permanently; one that quietly produced garbage would
  ship a wrong ETA.

So the tests assert consequences rather than lines, and the consequences are
asymmetric in ways a line-count check would miss: an unreadable `wall_seconds`
**drops** its timing while an unreadable `area_m2` **keeps** it (wall time is what
is being learned; area only feeds the cold-start fallback) — two `except` arms three
lines apart doing deliberately opposite things. Re-seeding one zone's corrupt bucket
must not take the map's other zones with it. An unreadable bucket must fall back to
area and **not** report `source: "learned"`, because that word is a claim to the
user that the figure came from this zone's own history. `ZL-19` sweeps every
unreadable store shape in one parametrize, including the row that matters most — a
perfectly valid store with no sample for the mode being asked about, which must
behave like the corrupt ones rather than borrowing the other mode's average.
`ZL-20` is the combination, because each of the others bends one field and a store
recovered from an older build is not polite enough to be wrong in one place at a
time.

**Two findings came out of writing them, both recorded rather than fixed:**

- **`normalize_clean_mode` has no caller, and never had one.** Measured: zero
  references in the live tree (its only other mention is a retired doc), and
  `git log -S` shows it arrived in `a2dd9092` with the `def` alone — born orphaned,
  not orphaned later. It is the named form of a rule its one real producer,
  `phase_runner.py::_capture_zone_phase_timing`, computes inline from the same
  `job_metadata["has_mop_mode"]` field. `ZN-11b` in
  `tests/integration/test_zone_phase.py` now pins the two against each other by
  calling **both**, so drift in either reddens it — which a restated copy of the
  expression could not do. `ZN-11` keeps its literal `== "mop"`: that one pins the
  value, `ZN-11b` pins the agreement, and neither subsumes the other (ablating only
  the helper reddens `ZN-11b` alone; ablating only the producer reddens both).
  Whether to wire the helper and delete the inline copy is a separate call.
- **A rejected fold used to leave an empty bucket behind — FIXED 2026-11-07.**
  `update_learned_zone` ran `store.setdefault(str(zone_id), {})` before its
  conversions could raise, so an observation rejected for a bad wall time still
  minted its zone key — and because `applied` is non-zero from the batch's good
  observations, the caller persisted it. Inert to read (every reader goes through
  `estimate_zone_seconds`, which treats `{}` like an absent key) but on disk, and
  only a rebuild cleared it. The function is now **all-or-nothing**: every conversion
  that can fail happens above the first mutation, so `ZL-16` asserts
  `list(store) == ["z_good"]` — the assertion it could not make before.

  **Three conversions, not one.** `float()` for the running mean, `int()` for
  `last_wall_seconds` (which rejects values `float()` accepts — `"300.5"`), and
  `round()` for the area. The first pass at the fix hoisted the two `wall_seconds`
  calls and left `round(area_m2, 2)` below the mutation, where it raises on a
  non-number for exactly the same reason, so `ZL-21` carries one row per conversion:
  hoisting two of three is indistinguishable from hoisting all three unless something
  exercises the one left behind. It still **raises** rather than returning quietly,
  because `record_observations` counts an application only when the call returns — a
  silent no-op would inflate that count and make the caller persist for nothing.

  Proven a no-op for working installs by differential run rather than by argument:
  both implementations over 10,206 generated input combinations gave **5,670
  successes with 0 divergences** and the same exception class on all 4,536
  rejections, of which **2,688 had residue the old code wrote and the new one does
  not**. The sweep was then shown able to see a difference by injecting one into the
  old side, which it flagged on all 5,670 successes — a differential that finds
  nothing has not been shown able to find anything.

### `counter_segmentation.py` — counter-plateau segmentation primitives
`find_candidates` / `select_active` / `build_segments` — the frame-invariant
plateau detection shared by live rollover, external-run ingest, and learned
history; the engine above delegates to these. The `build_segments` freeze/stall
**wall-carve** (a gap longer than `stall_wall_s` between `cleaning_time` ticks is
dead time, subtracted from that segment's `time_wall_s`) is covered in
`test_counter_segmentation.py`: a carved interior freeze, a sub-threshold gap left
intact (normal runs stay byte-identical), and a freeze that becomes a boundary
landing in overhead rather than inflating a room — external-run robustness Item 2.

---

## How it's tested

Four distinct setups, chosen by what the module needs:

### 1. Pure helpers — import and call
`utils`, the compute helpers in `estimator`, and the pure helpers in
`job_finalizer`. No `hass`, no fixtures, no filesystem. Fast, no shared state.

```python
from custom_components.eufy_vacuum.learning.utils import _safe_int
def test_safe_int_sentinel(): assert _safe_int("unavailable") == 0
```

### 2. Store / rebuilder — `MagicMock` hass + `tmp_path`
`history_store` and `stats_rebuilder` do real file I/O. The unit tests give them
an **isolated** filesystem by mocking `hass` and pointing `config_dir` at
pytest's `tmp_path`:

```python
def _make_store(tmp_path):
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    return LearningHistoryStore(hass)
```

This is the key difference from integration tests: each test gets a **fresh**
config dir, so there is **no shared-`config_dir` accumulation**
([gotchas §2](../05-gotchas-and-pitfalls.md)). Prefer this style for any
store-backed logic — it is both faster and cleaner than the integration `hass`.

### 3. Estimator class — construct with a store, feed seeded stats
`LearningEstimator` is built on a store and exercised by handing it room/accuracy
stats, asserting on the estimate/confidence output.

### 4. Integration services — `learning_services` fixture + seeding
`test_learning_services.py` registers learning services on top of the `manager`
fixture (learning services are **not** part of `async_register_services`, so the
file defines its own fixture):

```python
@pytest.fixture
async def learning_services(hass, manager):
    await async_register_learning_services(hass)
    yield manager
    await async_unregister_learning_services(hass)
```

Plus the per-file seeding helpers `_seed_completed_job` (via
`LearningHistoryStore`) and `_seed_active_job` (into
`manager.data["active_jobs"]`). Sync methods like `finalize_completed_job` run
through `hass.async_add_executor_job`. Because this layer shares `config_dir`,
assertions use presence/`>=`, and any file written in a non-canonical shape is
restored in a `finally` ([gotchas §2-3](../05-gotchas-and-pitfalls.md)).

> Two conventions coexist here: the newer files use ID prefixes (`LE-n`,
> `LS-n`); the older store/rebuilder/utils files group tests by
> `# --- function ---` comment banners. Either is fine — match the file you are
> editing.

---

## Known gaps (deliberately untested)

Coverage is high (89-100% per module); the remainder is mostly defensive
guards, inactive code, or paths reachable only by injecting malformed data.

- **`job_finalizer` cancel-detection sub-branches** — the
  `early_return_likely_cancelled` return (~line 1277) and the learning-estimate
  call it depends on (`manager._get_learning_manager()` / `expected_room_minutes`,
  initialized ~1238 and set from the timeline ~1252) need a non-zero learning
  estimate staged to reach; low value. The floor-time fast-path above it (the
  `floor_time_too_short` return, ~1222-1235) is similarly conditional.
- **Defensive `except` / `# pragma: no cover` blocks across all modules** —
  e.g. `job_finalizer` 1354-1359 (incomplete-run-log write) and 1449-1453
  (trouble-rooms write), and the per-room `estimate_failed` handler logic in
  `manager`. Reachable only by injecting malformed data; intentionally skipped.
- **`manager` accuracy-normalization guards (800, 805, 808)** —
  scattered defensive branches in the accuracy-stats normalization loop: the
  `else: accuracy_entries = []` shape fallback and the non-dict / empty-slug
  `continue` guards. (The percent/confidence-weight derive paths at 813/822 are
  now covered.) The canonical dict shape is fully covered; the rest are
  back-compat / malformed-input guards.
- **`manager` direct reload path (271-284)** — the immediate
  reload-from-disk helper; integration tests drive the executor-backed preload
  instead, so this synchronous variant is uncovered. Low value.

These are skipped on purpose ([conventions §what not to test](../04-patterns-and-conventions.md#what-not-to-test)).

> **Retired:** the former `_auto_derive_room_boundary` gap (an inert
> trace→room-boundary derivation in `job_finalizer`) is gone. The learned
> per-room bounds store was removed in the mapping shelve, and room identity now
> comes entirely from the device native current-room signal (the room-attribution
> seam above) — nothing in learning runs in drifting vacuum coordinates anymore.

---

## Extending

When you add learning behavior:

1. **Pure logic?** Add to the matching unit file (`utils`, `estimator`,
   `history_store`, `stats_rebuilder`, or the `job_finalizer` helper tests). Use
   `tmp_path` if it touches the store.
2. **A new service or finalize path?** Add a coverage target (`LS-n`) to
   `test_learning_services.py`, seed with the existing helpers, and start from
   [recipe D](../06-recipes.md#recipe-d--learning-finalize-integration-the-happy-path).
3. **Reader/writer of a stats file?** Seed through the real writer so the shape
   stays canonical ([gotchas §3](../05-gotchas-and-pitfalls.md)).
4. Re-measure with all six files together to get the true module number.
