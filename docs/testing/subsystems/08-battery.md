# 08 — Battery — Subsystem Test Map

The battery subsystem tracks cell wear: it accumulates battery samples into
charge cycles, summarizes charge sessions, derives a CC/CV regime health proxy
vs. an install baseline, and records per-job drain metrics. Covered by **97 tests across the 4 core files**, plus a service-level test for `battery_rebaseline`.

Source: `custom_components/eufy_vacuum/battery/`
Architecture reference: [docs/dev/12-battery-system.md](../../dev/12-battery-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `job_metrics.py` | 77 | 98% | `tests/unit/test_battery_metrics.py` | unit (pure) |
| `store.py` | 40 | 100% | `tests/unit/test_battery_store.py` | unit (`tmp_path`) |
| `sensors.py` | 167 | 97% | `tests/unit/test_battery_sensors.py` | unit (mock manager) |
| `manager.py` | 421 | 92% | `tests/integration/test_battery_manager.py` | integration |
| `__init__.py` (service) | — | 100% | `tests/integration/test_init_battery_rebaseline_service.py` | integration (service) |

---

## What's tested

### `job_metrics.py` — per-job drain computation (pure)
The drain-rate math (per-minute / per-hour / per-m², single-bucket detection,
weighting). Pure functions, near-fully covered.

### `store.py` — JSONL sample + session CSV store (`tmp_path`)
`append_sample` / `append_session` file round-trips, header creation, and the
read helpers, against an isolated `tmp_path` config dir.

### `sensors.py` — sensor entities (prefix `BS`, mock manager)
The `build_battery_sensors` factory and all entity classes
(`ChargeCycles`, `ChargeRate` overall/low/high, `LastChargeDuration`,
`BatteryHealth`, `RegimeChargeSpeed` cc/cv, `LastJobMetric` ×3,
`MidJobRecharge`) — `native_value`, `extra_state_attributes`, the
`_bucket_means` projection, None handling, and `unique_id`/`suggested_object_id`
derivation. Tested with a `MagicMock` manager whose `get_record` returns a
crafted record.

### `manager.py` — `BatteryHealthManager` (prefix `BM`, integration)
Two layers, against the real `manager` fixture:
- **Record management** — `ensure_record` (create + repair), listeners,
  `rebaseline`, `record_job_metrics` (last-job + aggregates + single-bucket),
  `_update_aggregate_bucket`.
- **The `_process_sample` pipeline** — driven by crafted `(level, charging, dt)`
  sample sequences: cycle counting, the `MAX_DELTA_PCT` rejection guard, the
  overall/low-zone/high-zone charge rates, session open→accumulate→close
  (including the `"full"` close at 100%), the 50→90 health-proxy baseline anchor
  (CC + CV regimes), and out-of-range rejection.

### `__init__.py` — `battery_rebaseline` service (prefix `INIT-REBASE`, service)
The `eufy_vacuum.battery_rebaseline` service handler registered during setup.
Boots the integration through the real config-entry path, swaps in a spy battery
manager, then drives the service via `hass.services.async_call` and asserts the
handler read `vacuum_entity_id` from the call data and delegated exactly once to
`bm.rebaseline(...)` — including the `if not ok` "no record found" branch when
`rebaseline` returns `False`.

---

## How it's tested

Five patterns:
1. **Pure import** — `job_metrics`.
2. **`tmp_path`** — `store`.
3. **Mock manager** — `sensors`: the entities only read `manager.get_record()`,
   so a `MagicMock` with a canned record exercises every property without hass.
4. **Real manager + crafted samples** — `manager`: construct
   `BatteryHealthManager(hass, runtime_manager=manager)` and call
   `_process_sample(...)` directly with explicit `battery_level` / `charging` /
   `ts`. This drives the whole cycle/rate/session/health state machine
   deterministically without real battery sensors.
5. **Service through real setup** — `__init__.py`: boot the integration via the
   config-entry path, swap in a spy battery manager, and call the registered
   `battery_rebaseline` service to assert the handler's delegation contract.

> The `_process_sample` tests must be `async def` — the method calls
> `hass.async_add_executor_job` for the JSONL append, which needs a running
> event loop. Record-management tests can stay sync.

---

## Known gaps

`manager.py` (91%) is mostly covered, including the HA wiring and the
charging/session-classification paths that earlier revisions of this doc
listed as gaps. The HA-wiring path (`start`/`stop`, `_wire_vacuum`,
`_on_state_event`, `_sample_now`, and the `_is_charging` substring fallback)
is exercised by `test_wire_and_state_event` [BM-18] and
`test_is_charging_delegates_and_fallback` [BM-14]; `_classify_session_kind`
and `_attach_post_job_charge_if_pending` by [BM-17]/[BM-19]/[BM-20].

What's left is defensive-by-design or low-value edge branches, intentionally
left uncovered under the ~90% meaningful-coverage ceiling:

- **Defensive guards** — the `except ValueError` in the listener-unsub
  (manager.py:269-270), the `_wire_vacuum` already-wired re-entry guard
  (:328), the `_has_active_job` non-dict guards (:390, :393), the legacy
  `min_per_pct` clear in `rebaseline` (:896), the `_attach_post_job` malformed
  `recorded_ts` / opened-before-job drops (:1039-1040, :1044), and the
  `_parse_iso` passthrough/except branches (:1112, :1117-1118).
- **Sanity-timeout & ring-buffer trims** — the 12 h stale-session force-close
  (:585-586) and the `HISTORY_LIMIT` history truncation (:695); both need a
  long-gap or 50+-session fixture to reach.
- **`_close_session` kind-specific branches** — the `mid_job` rate-stat call
  (:704), the `post_job` linkage call (:724), and the `mid_job` return in
  `_classify_session_kind` (:735). The underlying helpers are unit-tested
  directly ([BM-15], [BM-17]); only the in-`_close_session` dispatch for those
  kinds is uncovered (the `_feed`-driven session tests close `idle` sessions).
- **`_compute_regime_pct` fallback paths** — the within-window skip/append and
  the no-recent / non-positive-current fallbacks (:849, :852, :862, :866).

Other modules are at the ceiling: `job_metrics.py` (98%) — only the
`(TypeError, ValueError)` est-parse guard (:156-157); `sensors.py` (97%) —
the no-`hass` write-state guard (:166) and the non-dict bucket skip (:485);
`store.py` and `__init__.py` at 100%. The core wear/health/session math is
fully covered.

---

## Extending

1. **Drain math / new metric?** `job_metrics` unit test — pure.
2. **A new sensor?** Add a `BS` test with the mock-manager record.
3. **New sample-pipeline behavior?** Add a `BM` `async` test with a crafted
   `_feed(...)` sequence and assert on `get_record(...)`.
