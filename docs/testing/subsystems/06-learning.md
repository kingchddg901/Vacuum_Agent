# Learning — Subsystem Test Map

> **This is the template.** Learning is the most completely tested subsystem, so
> its test map is the model for documenting the others. Copy this structure
> (coverage map → what's tested → how it's tested → gaps → extending) when you
> write the test map for another subsystem.

The learning subsystem records cleaning runs, rebuilds per-room/per-profile
stats, estimates ETAs with a confidence model, and finalizes completed jobs. It
is exercised by **~220 tests across 6 files** (214 test functions; parametrized
cases bring the run to 221).

Source: `custom_components/eufy_vacuum/learning/`
Architecture reference: [docs/dev/10-learning-system.md](../../dev/10-learning-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file(s) | Layer |
|---------------|------:|----:|--------------|-------|
| `utils.py` | 32 | 95% | `tests/unit/test_learning_utils.py` | unit (pure) |
| `estimator.py` | 336 | 96% | `tests/unit/test_learning_estimator.py` | unit (pure + class) |
| `history_store.py` | 378 | 93% | `tests/unit/test_learning_history_store.py` | unit (`tmp_path` FS) |
| `stats_rebuilder.py` | 333 | 94% | `tests/unit/test_learning_stats_rebuilder.py` | unit (`tmp_path` FS) |
| `job_finalizer.py` | 506 | 91% | `tests/unit/test_learning_job_finalizer.py` + `tests/integration/test_learning_services.py` | unit (pure) + integration |
| `manager.py` | 683 | 91% | `tests/integration/test_learning_services.py` | integration |
| `services.py` | 186 | 99% | `tests/integration/test_learning_services.py` | integration |

Numbers are line coverage with branch coverage enabled, measured by running all
six files together (see [running-tests §per-file vs combined](../02-running-tests.md#per-file-vs-combined-coverage)).

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

Coverage is high; the remainder is mostly unreachable-without-mocking or dead:

- `job_finalizer` cancel detection's estimate-driven sub-branches
  (`early_return_likely_cancelled`, the learning-estimate call at 1195-1202) —
  need a non-zero learning estimate staged; low value.
- Defensive `except` blocks across all modules (e.g. `job_finalizer` 1316-1321,
  1411-1412; `manager` 1924-1925) — reachable only by injecting malformed data.
- `manager` 796-821 legacy list-shape accuracy fallback — the canonical path is
  the dict shape; the list branch is a back-compat guard.
- `_auto_derive_room_boundary` (`job_finalizer` 1451/1455) — currently inactive.

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
