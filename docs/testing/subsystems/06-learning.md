# Learning — Subsystem Test Map

> **This is the template.** Learning is the most completely tested subsystem, so
> its test map is the model for documenting the others. Copy this structure
> (coverage map → what's tested → how it's tested → gaps → extending) when you
> write the test map for another subsystem.

The learning subsystem records cleaning runs, rebuilds per-room/per-profile
stats, estimates ETAs with a confidence model, and finalizes completed jobs. It
is exercised by **377 tests across 11 files** (369 test functions, expanded by
parametrization).

Source: `custom_components/eufy_vacuum/learning/`
Architecture reference: [docs/dev/10-learning-system.md](../../dev/10-learning-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file(s) | Layer |
|---------------|------:|----:|--------------|-------|
| `utils.py` | 52 | 97% | `tests/unit/test_learning_utils.py` | unit (pure) |
| `estimator.py` | 410 | 94% | `tests/unit/test_learning_estimator.py` | unit (pure + class) |
| `history_store.py` | 428 | 91% | `tests/unit/test_learning_history_store.py` | unit (`tmp_path` FS) |
| `stats_rebuilder.py` | 460 | 93% | `tests/unit/test_learning_stats_rebuilder.py` | unit (`tmp_path` FS) |
| `job_finalizer.py` | 519 | 90% | `tests/unit/test_learning_job_finalizer.py` + `tests/integration/test_learning_services.py` | unit (pure) + integration |
| `manager.py` | 680 | 95% | `tests/integration/test_learning_services.py` + `tests/unit/test_learning_profile_label.py` | integration |
| `services.py` | 241 | 91% | `tests/integration/test_learning_services.py` | integration |
| `external_ingest.py` | 281 | 94% | `tests/unit/test_learning_external_ingest.py` | unit (pure) |
| `job_segmenter_engines.py` | 99 | 98% | `tests/unit/test_job_segmenter_engines.py` | unit (pure) |
| `counter_segmentation.py` | 165 | 95% | `tests/unit/test_counter_segmentation.py` + `tests/unit/test_counter_resegmentation.py` | unit (pure) |

`counter_segmentation.py` lives at the package root (not under `learning/`) — it
is the shared counter-plateau segmentation primitive used here and by the jobs
subsystem's live rollover, tabled here alongside the engine that wraps it.

Numbers are line coverage with branch coverage enabled, measured by running all
these files together (see [running-tests §per-file vs combined](../02-running-tests.md#per-file-vs-combined-coverage)).

---

## What's tested

### `utils.py` — pure coercion helpers
`_safe_int`, `_safe_float`, `_safe_bool`, `_room_profile_key`. Sentinel strings
(`""`, `"unknown"`, `"unavailable"`), `None` defaults, float-string parsing,
non-numeric fallback. Grouped by function (no ID prefix).

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

### `history_store.py` — file-backed store + helpers
`_vacuum_slug`, path construction, JSON read/write round-trips, completed-job
build/save/load, jobs-index payloads, accuracy/room/job stats load, the
`build_completed_job_payload` outcome logic (learning blockers,
`used_for_learning` flip). Grouped by function/method.

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

### `manager.py` + `services.py` — orchestration + HA services (prefix `LS`)
LS-1..LS-53 in `test_learning_services.py`: service registration, the
read/snapshot services (history snapshot, metrics snapshot, room estimates),
exclude/restore round-trips, finalize variants (forced status, cancelled,
completed-clears-incomplete), accuracy recording and the trust-metrics path, the
old-format jobs-index rebuild, and `async_preload_learning_stats` guards.

`test_learning_profile_label.py` additionally covers `manager._settings_profile_label`
(SPL-1/SPL-2) as a focused unit.

### `external_ingest.py` — app-started-run capture + review wizard
Detection of runs started outside HA, the pending-record build + persistence, the
re-segmentation service, and the confirm path that turns a reviewed run into a
learned job (the v2 samples-saved re-segment plus the v1 fallback).

### `job_segmenter_engines.py` — pluggable job-segmenter seam
The `JobSegmenter` registry + the `eufy_counter_v1` engine: byte-identical
delegation to `counter_segmentation` (the fidelity battery), `DEFAULT_TUNING`
mirroring the module constants, and the Eufy-fallback for an absent/unknown engine.

### `counter_segmentation.py` — counter-plateau segmentation primitives
`find_candidates` / `select_active` / `build_segments` — the frame-invariant
plateau detection shared by live rollover, external-run ingest, and learned
history; the engine above delegates to these.

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
  `early_return_likely_cancelled` return (line 1258) and the learning-estimate
  call it depends on (`manager._get_learning_manager()` / `expected_room_minutes`
  at 1218-1219) need a non-zero learning estimate staged to reach; low value.
  The floor-time fast-path above it (around 1203-1216) is similarly conditional.
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
- **`_auto_derive_room_boundary` (`job_finalizer` 1455-1503)** — currently
  inactive: the method runs its eligibility gates then unconditionally returns
  None (skip-log at 1497-1503). Uncovered lines 1489/1493 are room-guard
  branches inside that inert gate. No behavior to test until the feature is
  re-activated.

These are skipped on purpose ([conventions §what not to test](../04-patterns-and-conventions.md#what-not-to-test)).

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
