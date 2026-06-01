# Battery — Subsystem Test Map

The battery subsystem tracks cell wear: it accumulates battery samples into
charge cycles, summarizes charge sessions, derives a CC/CV regime health proxy
vs. an install baseline, and records per-job drain metrics. Covered by **84
tests across 4 files**.

Source: `custom_components/eufy_vacuum/battery/`
Architecture reference: [docs/dev/12-battery-system.md](../../dev/12-battery-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `job_metrics.py` | 77 | 98% | `tests/unit/test_battery_metrics.py` | unit (pure) |
| `store.py` | 44 | 92% | `tests/unit/test_battery_store.py` | unit (`tmp_path`) |
| `sensors.py` | 165 | 86% | `tests/unit/test_battery_sensors.py` | unit (mock manager) |
| `manager.py` | 413 | 72% | `tests/integration/test_battery_manager.py` | integration |

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

---

## How it's tested

Three patterns:
1. **Pure import** — `job_metrics`.
2. **`tmp_path`** — `store`.
3. **Mock manager** — `sensors`: the entities only read `manager.get_record()`,
   so a `MagicMock` with a canned record exercises every property without hass.
4. **Real manager + crafted samples** — `manager`: construct
   `BatteryHealthManager(hass, runtime_manager=manager)` and call
   `_process_sample(...)` directly with explicit `battery_level` / `charging` /
   `ts`. This drives the whole cycle/rate/session/health state machine
   deterministically without real battery sensors.

> The `_process_sample` tests must be `async def` — the method calls
> `hass.async_add_executor_job` for the JSONL append, which needs a running
> event loop. Record-management tests can stay sync.

---

## Known gaps

`manager.py` (72%) leaves the **HA wiring** uncovered: `start`/`stop`,
`_wire_vacuum`, `_on_state_event`, `_sample_now`, and the `_is_charging`
substring fallback — these need registered state-change listeners and real
battery/charging entities. Also the `post_job` charge-linkage helper
(`_attach_post_job_charge_if_pending`) and a few `_classify_session_kind` edge
branches. All reachable with a fuller fixture; the core wear/health math is
covered.

---

## Extending

1. **Drain math / new metric?** `job_metrics` unit test — pure.
2. **A new sensor?** Add a `BS` test with the mock-manager record.
3. **New sample-pipeline behavior?** Add a `BM` `async` test with a crafted
   `_feed(...)` sequence and assert on `get_record(...)`.
