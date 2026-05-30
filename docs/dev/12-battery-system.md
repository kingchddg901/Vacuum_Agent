# Battery Health System — Developer Reference

> **Scope:** This document is a complete implementation reference for the `eufy_vacuum` battery health subsystem. Every formula, constant, threshold, file path, and storage shape is derived directly from the source. A developer should be able to re-implement the system from this document alone.

For user-facing material see [user-guide/13-battery-health.md](../user-guide/13-battery-health.md). For automation and zone-rationale depth see [advanced/09-battery-health.md](../advanced/09-battery-health.md).

---

## 1. Overview

The battery health system answers three questions:

1. **How worn is the battery?** Cumulative drain ÷ 100 = cycles.
2. **How fast does it charge today, vs how fast it used to?** Zone-aware rate tracking + a baseline-relative health proxy.
3. **What does each cleaning job cost in battery terms?** Per-job drain rates and per-mode aggregates.

The architecture is a single manager (`BatteryHealthManager`) that listens for HA state changes on the vacuum's battery sensor and the vacuum entity itself, classifies each charge session at open time, accumulates samples + sessions, and feeds ten read-only sensors. Job-level metrics arrive from the learning system's `JobFinalizer` via a direct call.

```
┌────────────────────────────────────────────────────────────────┐
│  Home Assistant state engine                                  │
│  (sensor.<vac>_battery, vacuum.<vac>)                          │
└──────────────────────────────┬─────────────────────────────────┘
                               │ async_track_state_change_event
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  BatteryHealthManager._on_state_event                         │
│    → _sample_now → _process_sample                            │
│      ├── update cumulative_drain_pct + cycles                 │
│      ├── update zone-specific rate stats                      │
│      └── update_session (open / accumulate / close)           │
└──────────────────────────────┬─────────────────────────────────┘
                               │ closes session
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  _close_session                                                │
│    ├── compute summary                                         │
│    ├── append to session_history_recent (size HISTORY_LIMIT)  │
│    ├── append to sessions.csv (raw_store.append_session)      │
│    ├── update mid-job rate stat (if kind == "mid_job")        │
│    ├── _update_health (if qualifying)                          │
│    └── _attach_post_job_charge_if_pending (if kind=="post_job")│
└────────────────────────────────────────────────────────────────┘

      ▲                                     ▲
      │                                     │
      │ record_job_metrics (direct call)    │ HA sensors poll
      │                                     │ via update listener
┌─────┴─────────────────┐         ┌─────────┴────────────────────┐
│ JobFinalizer.finalize │         │ BatteryHealthManager → 10    │
│   → compute_job_      │         │ Sensor entities              │
│     battery_metrics   │         │   _charge_cycles, _charge_   │
│   → battery_manager.  │         │   rate, _battery_health,     │
│     record_job_metrics│         │   _last_job_*, _mid_job_     │
└───────────────────────┘         │   recharge_rate              │
                                  └──────────────────────────────┘
```

---

## 2. File layout

```
custom_components/eufy_vacuum/battery/
├── __init__.py        # exports BatteryHealthManager
├── manager.py         # BatteryHealthManager + tunables
├── store.py           # JSONL/CSV writers (raw_store)
├── sensors.py         # 10 SensorEntity subclasses + build_battery_sensors()
└── job_metrics.py     # compute_job_battery_metrics() — pure compute
```

Cross-file hooks:

- `const.py` — `DATA_BATTERY = "battery"`
- `__init__.py` (root) — instantiates manager in `async_setup_entry`, calls `.start(known_vacuum_ids)`, calls `.stop()` in `async_unload_entry`
- `sensor/__init__.py` — calls `build_battery_sensors(manager, vacuum_entity_id)` per vacuum and adds to entity list
- `learning/job_finalizer.py` — imports `compute_job_battery_metrics` and `DATA_BATTERY`; computes metrics after `cleaning_area_m2` is set; calls `battery_manager.record_job_metrics(...)` for completed and used-for-learning jobs

---

## 3. Tunable constants

All in `battery/manager.py`:

| Constant | Default | Purpose |
|---|---|---|
| `MAX_DELTA_PCT` | 50.0 | Reject single-sample deltas this large or larger. Prevents inflation from sensor resets / HA gaps. |
| `MAX_RATE_INTERVAL_SEC` | 600.0 | Skip rate computation when sample interval exceeds this. Drain still counts toward cycles (drain is time-independent). |
| `LOW_ZONE_MAX` | 29 | Battery level ≤ this counts as "low zone". |
| `HIGH_ZONE_MIN` | 80 | Battery level ≥ this counts as "high zone". |
| `SESSION_MAX_HOURS` | 12.0 | Force-close stale open sessions older than this. |
| `HISTORY_LIMIT` | 50 | Max sessions kept in `session_history_recent` ring buffer. |
| `BASELINE_SAMPLE_COUNT` | 5 | Qualifying full charges needed to lock in the baseline. |
| `CURRENT_WINDOW_DAYS` | 7 | Window for the "current" health average. |
| `HEALTH_QUALIFY_START_MAX` | 30 | A "qualifying full charge" starts at or below this. |
| `HEALTH_QUALIFY_END_MIN` | 95 | …and ends at or above this. |
| `POST_JOB_CHARGE_LINK_HOURS` | 4.0 | Window in which the next charge session is attached to the just-finished job. |

---

## 4. Storage schema

Lives in the main `eufy_vacuum.storage` under the top-level `battery` key:

```python
{
    "battery": {
        "vacuums": {
            "vacuum.alfred": {
                "cycles": 12.34,
                "cumulative_drain_pct": 1234.0,
                "last_battery_level": 82,
                "last_sample_ts": "2026-05-08T12:34:56+00:00",
                "last_charging": False,
                "current_session": None | {
                    "start_ts": "...",
                    "start_battery": 60,
                    "samples": 12,
                    "rate_sum": 5.4,
                    "rate_min": 0.32,
                    "rate_max": 0.68,
                    "kind": "mid_job" | "post_job" | "idle",
                },
                "stats": {
                    "rate_overall_per_min": 0.42,
                    "rate_low_zone_per_min": 0.31,
                    "rate_high_zone_per_min": 0.18,
                    "last_charge_duration_min": 73.0,
                    "last_charge_delta_pct": 40,
                    "health_pct": 92.5,
                },
                "baseline": {
                    "min_per_pct": 1.05,
                    "session_count": 5,
                },
                "session_history_recent": [
                    {... session summary ...},
                    ...
                ],
                "last_job": None | {
                    "job_id": "...",
                    "recorded_at": "...",
                    "battery_used_pct": 12,
                    "duration_min": 30.2,
                    "area_m2": 65.5,
                    "drain_per_min": 0.397,
                    "drain_per_hour": 23.84,
                    "drain_per_m2": 0.183,
                    "is_single_clean_mode": True,
                    "is_single_fan_speed": True,
                    "is_single_water_level": True,
                    "single_clean_mode": "vacuum_mop",
                    "single_fan_speed": "max",
                    "single_water_level": "off",
                    "by_clean_mode": {...},
                    "by_fan_speed": {...},
                    "by_water_level": {...},
                    "edge_mopping": {"on_share": 0.32, "off_share": 0.68},
                    "weighted_by": "estimated_minutes",
                    "post_job_charge": None | {... session summary ...},
                },
                "job_aggregates": {
                    "all_jobs": {... aggregate bucket ...},
                    "by_clean_mode":  {"vacuum_mop": {... bucket ...}, "vacuum": {...}},
                    "by_fan_speed":   {...},
                    "by_water_level": {...},
                },
                "mid_job_recharge_stats": {
                    "count": 18,
                    "rate_sum": 9.8,
                    "rate_mean_per_min": 0.544,
                    "last_rate_per_min": 0.51,
                    "last_recorded_at": "...",
                },
            }
        }
    }
}
```

`_new_record()` and `_new_aggregate_bucket()` in `manager.py` are the source-of-truth templates. `ensure_record()` repairs older records by setdefault-ing every key from the template.

---

## 5. Sample lifecycle

### 5.1 Listener wiring (`start`)

For each vacuum entity passed to `start(...)`, the manager:

1. Computes `battery_sensor_id = f"sensor.{object_id}_battery"`.
2. Maps both `battery_sensor_id` and `vacuum_entity_id` → `vacuum_entity_id` in `_battery_to_vacuum`.
3. Subscribes to state-change events on both entities via `async_track_state_change_event`.
4. Calls `_sample_now(vacuum_entity_id)` once to capture an initial sample.

Why both entities? `sensor.<vac>_battery` carries the level; `vacuum.<vac>` carries the state string and `task_status` / `dock_status` attributes that the charging-detection helper consumes. Either changing means the charging flag may have flipped.

### 5.2 `_process_sample`

Reads `battery_level` (via `manager._get_battery_level`) and `charging` (via `manager._is_recharge_like_state`, with a substring-fallback if the runtime manager renames it again). Then:

```python
if battery_level is None or battery_level < 0 or battery_level > 100:
    return                                  # invalid — skip

prev_level = record["last_battery_level"]
prev_ts = parse(record["last_sample_ts"])

if prev_level is not None and prev_ts is not None:
    elapsed_sec = (ts - prev_ts).total_seconds()
    raw_delta = battery_level - prev_level   # +charging, -draining

    if abs(raw_delta) <= MAX_DELTA_PCT:
        # Cycle accounting — drain only, valid over any interval.
        if raw_delta < 0:
            drain_added = -raw_delta
            cumulative_drain_pct += drain_added
            cycles = cumulative_drain_pct / 100

        # Rate metrics — only for charging samples within MAX_RATE_INTERVAL_SEC.
        if raw_delta > 0 and elapsed_sec <= MAX_RATE_INTERVAL_SEC:
            rate_per_min = delta_pct / (elapsed_sec / 60)
            update rate_overall_per_min
            if zone == "low":  update rate_low_zone_per_min
            if zone == "high": update rate_high_zone_per_min

# Session lifecycle (see section 6)
_update_session(record, battery_level, charging, ts, rate_per_min)

# Persist
record["last_battery_level"] = battery_level
record["last_sample_ts"] = ts
record["last_charging"] = charging

raw_store.append_sample(...)              # samples.jsonl
_schedule_save()                          # eufy_vacuum.storage
_notify(vacuum_entity_id)                 # → sensor refresh
```

---

## 6. Session lifecycle

A session is opened, accumulates samples, then closes. Each session has a `kind` set at open time.

### 6.1 Open

```python
prev_charging = record["last_charging"]
if not prev_charging and charging:
    record["current_session"] = {
        "start_ts": ts,
        "start_battery": battery_level,
        "samples": 1,
        "rate_sum": 0.0,
        "rate_min": None,
        "rate_max": None,
        "kind": _classify_session_kind(vacuum_entity_id),
    }
```

### 6.2 Classification (`_classify_session_kind`)

```python
if _has_active_job(vacuum_entity_id):
    return "mid_job"        # vacuum mid-clean, paused for recharge
pending = _pending_post_job.get(vacuum_entity_id)
if pending and (now - pending.recorded_ts) <= POST_JOB_CHARGE_LINK_HOURS:
    return "post_job"       # within link window of a finalized job
return "idle"               # user docked it, opportunistic top-up
```

`_has_active_job` checks the runtime manager's `data["active_jobs"][vacuum]` for any map state with `started_at` and no `ended_at`.

### 6.3 Accumulate

While `charging` continues:

```python
session.samples += 1
if rate_per_min and rate_per_min > 0:
    session.rate_sum += rate_per_min
    session.rate_min = min(rate_min, rate_per_min)
    session.rate_max = max(rate_max, rate_per_min)
```

### 6.4 Close

Triggered when `charging` flips false OR `battery_level >= 100`:

```python
duration_min = (ts - start_ts).total_seconds() / 60
delta_pct = end_battery - start_battery
avg = rate_sum / samples if samples > 0 else None

summary = {
    start_ts, end_ts, duration_min,
    start_battery, end_battery, delta_pct,
    avg_rate_per_min, min_rate_per_min, max_rate_per_min,
    samples,
    ended_reason: "full" if end_battery >= 100 else "stopped",
    kind,
}

# Append to ring + raw store + state.
session_history_recent.append(summary)
trim to HISTORY_LIMIT
raw_store.append_session(summary)        # sessions.csv
_update_health(record)                   # health proxy

if kind == "mid_job" and avg > 0:
    _update_mid_job_rate_stat(record, avg)

if kind == "post_job":
    _attach_post_job_charge_if_pending(vacuum_entity_id, summary)

record["current_session"] = None
```

### 6.5 Stale-session safeguard

At every sample, if `current_session.start_ts` is older than `SESSION_MAX_HOURS`, the session is discarded with a debug log. Prevents a stuck "currently charging" record if the integration missed the close transition.

---

## 7. Health proxy (`_update_health`)

Called on every session close. Two phases:

### 7.1 Baseline lock-in

```python
qualifying = [
    s for s in session_history_recent
    if s.start_battery <= HEALTH_QUALIFY_START_MAX
    and s.end_battery >= HEALTH_QUALIFY_END_MIN
    and s.delta_pct > 0 and s.duration_min > 0
]
if record.baseline.min_per_pct is None and len(qualifying) >= BASELINE_SAMPLE_COUNT:
    seeds = qualifying[:BASELINE_SAMPLE_COUNT]
    avg = mean(s.duration_min / s.delta_pct for s in seeds)
    record.baseline.min_per_pct = avg
    record.baseline.session_count = len(seeds)
```

### 7.2 Health computation

```python
if record.baseline.min_per_pct is None:
    record.stats.health_pct = None
    return

cutoff = now - CURRENT_WINDOW_DAYS days
recent = [s.duration_min / s.delta_pct for s in qualifying if s.end_ts >= cutoff]
if not recent:
    recent = [last_qualifying_session.duration_min / .delta_pct]   # fallback

current_min_per_pct = mean(recent)
if current_min_per_pct <= 0:
    health_pct = None
else:
    health_pct = round(baseline.min_per_pct / current_min_per_pct * 100, 1)
```

---

## 8. Mid-job rate stat (`_update_mid_job_rate_stat`)

Called only when a closed session has `kind == "mid_job"` and `avg > 0`:

```python
stats = record.mid_job_recharge_stats
stats.count += 1
stats.rate_sum += avg
stats.rate_mean_per_min = stats.rate_sum / stats.count
stats.last_rate_per_min = avg
stats.last_recorded_at = now
```

Surfaced as `sensor.<vacuum>_mid_job_recharge_rate` (state = `rate_mean_per_min`).

---

## 9. Job metrics ingestion (`record_job_metrics`)

Called from `learning/job_finalizer.py` after the completed_job dict is built and `cleaning_area_m2` is attached. Only fires for jobs with:

- `outcome.status` in `{"completed", "interrupted"}`
- `outcome.used_for_learning != False`

(Cancelled, failed, and test runs are skipped — their drains are not representative.)

> **Thread context:** The finalizer body runs in HA's executor thread pool (`hass.async_add_executor_job`), so `record_job_metrics` and everything it calls — `_schedule_save`, `_notify`, sensor `async_write_ha_state` — are reached from a worker thread, not the event loop. The dispatch helpers in this module bridge across that boundary; see [01-architecture-overview.md §7 Concurrency & Thread Safety](01-architecture-overview.md#7-concurrency--thread-safety) for the rule and pattern.

### 9.1 What it does

1. Snapshots the metrics into `record.last_job` (small enough to ship as sensor attributes).
2. Updates `record.job_aggregates.all_jobs` running mean (every job).
3. If `is_single_clean_mode` and `single_clean_mode` is set → updates `by_clean_mode[single_clean_mode]` aggregate.
4. Same for `is_single_fan_speed` and `is_single_water_level`.
5. Sets `_pending_post_job[vacuum_entity_id] = {job_id, recorded_ts: now}` so the next charge session within `POST_JOB_CHARGE_LINK_HOURS` gets linked.
6. `_schedule_save()` + `_notify(vacuum_entity_id)`.

### 9.2 Aggregate bucket math (`_update_aggregate_bucket`)

Each bucket stores cumulative sums to enable on-the-fly mean computation without keeping every job around:

```python
bucket.count += 1
bucket.drain_pct_sum += metrics.battery_used_pct
bucket.duration_min_sum += metrics.duration_min
bucket.area_m2_sum += metrics.area_m2

bucket.drain_per_min_mean  = drain_pct_sum / duration_min_sum
bucket.drain_per_hour_mean = (drain_pct_sum / duration_min_sum) * 60
bucket.drain_per_m2_mean   = drain_pct_sum / area_m2_sum
```

The means are **time-weighted** (sums in numerator + denominator), not arithmetic averages of per-job means. A 60-min job and a 30-min job contribute proportionally to their durations.

---

## 10. Per-job metrics compute (`compute_job_battery_metrics`)

Pure function in `battery/job_metrics.py` — no HA, no I/O. Returns the full `battery_metrics` dict.

### 10.1 Inputs

- `battery_start`, `battery_end` — both required for drain computation
- `duration_minutes` — from `completed_job.job.duration_minutes` (already net of pauses + recharges)
- `cleaning_area_m2` — from `sensor.<vac>_cleaning_area` at finalize time
- `resolved_rooms` — list of per-room dicts, each with `clean_mode`, `fan_speed`, `water_level`, `clean_passes`, `edge_mopping`, optionally `estimated_minutes`

### 10.2 Weighting (`_prorate_weights`)

Returns `(weights, label)`:

```python
estimates = [room.get("estimated_minutes", 0) for room in rooms]
total_est = sum(estimates)

if total_est > 0:
    weights = [e / total_est for e in estimates]   # prorated by est. minutes
    label = "estimated_minutes"
else:
    weights = [1/N for _ in rooms]                 # equal weight
    label = "room_count"
```

### 10.3 Bucketing (`_bucketed_share`)

```python
buckets = {}
for room, weight in zip(rooms, weights):
    key = bucket_key(room.get(field))     # lowercased; null → "unknown"
    bucket = buckets.setdefault(key, {"share": 0, "rooms": 0})
    bucket.share += weight                # → sums to 1.0 across all buckets
    bucket.rooms += 1
    if area_m2:
        bucket.area_m2 += weight * area_m2
```

### 10.4 Single-bucket detection

```python
is_single_clean_mode  = len(by_clean_mode)  == 1
is_single_fan_speed   = len(by_fan_speed)   == 1
is_single_water_level = len(by_water_level) == 1
single_clean_mode  = next(iter(by_clean_mode))  if is_single_clean_mode  else None
# ...same for fan / water
```

These flags gate per-bucket aggregation downstream. The intentional design: per-bucket *drain* attribution requires single-bucket runs because the vacuum doesn't report per-room battery telemetry. Mixed runs feed only the all-jobs aggregate.

---

## 11. Post-job charge linkage (`_attach_post_job_charge_if_pending`)

Called from `_close_session` when the closed session has `kind == "post_job"`. Logic:

```python
pending = _pending_post_job.get(vacuum_entity_id)
if not pending: return

session_start = parse(session_summary.start_ts)
if session_start is None or session_start < pending.recorded_ts:
    return  # session opened before the job ended — not its recharge

if (session_start - pending.recorded_ts) > POST_JOB_CHARGE_LINK_HOURS:
    pop pending
    return  # too late — treat as independent session

record.last_job.post_job_charge = {
    "job_id":    pending.job_id,
    "start_ts":  session.start_ts,
    "end_ts":    session.end_ts,
    "duration_min": session.duration_min,
    "start_battery": session.start_battery,
    "end_battery":   session.end_battery,
    "delta_pct":     session.delta_pct,
    "avg_rate_per_min": session.avg_rate_per_min,
    "ended_reason":  session.ended_reason,
}
pop pending
_notify(vacuum_entity_id)
```

The `_pending_post_job` dict is in-memory only — it doesn't survive HA restarts. If the integration is unloaded between job finalization and the recharge session opening, the linkage is lost. Acceptable trade-off; restoring on reload would require persisting the pending state and replaying classification logic.

---

## 12. Raw data files (`battery/store.py`)

Two append-only files per vacuum, written under `config/eufy_vacuum/battery/<object_id>/`:

### 12.1 samples.jsonl

Append on every accepted sample, one JSON object per line. Fields (from `_SAMPLES_FIELDS`):

```
ts, battery_level, charging, delta_pct, rate_per_min, zone, drain_added, cycles
```

Best-effort write — `OSError` is logged at debug and swallowed so a transient FS issue can't crash the manager.

### 12.2 sessions.csv

Append on every closed session. Header is written when the file is empty:

```
start_ts, end_ts, duration_min,
start_battery, end_battery, delta_pct,
avg_rate_per_min, min_rate_per_min, max_rate_per_min,
samples, ended_reason
```

Note `kind` is in the in-memory ring buffer but **not** in the CSV (added after the file format was frozen). Add to `_SESSION_HEADER` if you want it in the spreadsheet view; existing CSVs would just have an empty column.

`datetime` values are formatted as ISO; floats rounded to 4 decimals; None → empty cell.

---

## 13. Sensors (`battery/sensors.py`)

`build_battery_sensors(manager, vacuum_entity_id)` returns a list of ten `SensorEntity` instances. All inherit from `_BatteryBase`:

```python
class _BatteryBase(SensorEntity):
    _attr_should_poll = False

    async def async_added_to_hass(self):
        self._unsub = self._manager.add_update_listener(self._on_manager_update)

    def _on_manager_update(self, vacuum_entity_id):
        # Notifications can arrive from the event loop (state-change samples)
        # OR from the JobFinalizer's executor pool (worker thread). Route
        # async_write_ha_state through call_soon_threadsafe so it's safe
        # from any caller context.
        if vacuum_entity_id != self._vacuum_entity_id: return
        hass = getattr(self, "hass", None)
        if hass is None: return

        @callback
        def _write():
            self.async_write_ha_state()

        hass.loop.call_soon_threadsafe(_write)

    def _record(self):
        return self._manager.get_record(self._vacuum_entity_id)
```

The `call_soon_threadsafe` wrapping is required because `record_job_metrics`
fires the manager's `_notify` chain from inside the JobFinalizer's executor
thread. See [01-architecture-overview.md §7 Concurrency & Thread Safety](01-architecture-overview.md#7-concurrency--thread-safety)
for the integration-wide rule and dispatch patterns; this is one specific
instance of it.

Each subclass overrides `native_value` and `extra_state_attributes` to project a specific slice of the record.

Naming convention follows the rest of the integration, plus a `suggested_object_id` to pin the entity_id deterministically:

```python
attr_name = build_entity_name(vacuum_entity_id, label)        # "Alfred Charge Cycles"
attr_unique_id = f"{vacuum_entity_id.replace('.', '_')}_{suffix}"
                                                              # "vacuum_alfred_charge_cycles"
attr_suggested_object_id = f"{object_id}_{suffix}"            # "alfred_charge_cycles"
```

`_attr_suggested_object_id` only takes effect on **first registration** of an
entity. For installs that registered sensors before this was added, the
entity_ids stay at their old label-derived IDs (e.g. `sensor.alfred_last_job_drain_rate`
when the label was "Last Job Drain Rate" and the suffix was "last_job_drain_per_min").
The card's `state/metrics.js#batteryMetrics` includes a fallback chain in the
`_batterySensor` lookups for the two known mismatches:

```javascript
last_job_per_min: _batterySensor("last_job_drain_rate")
                    || _batterySensor("last_job_drain_per_min"),
last_job_per_m2:  _batterySensor("last_job_drain_per_m2")
                    || _batterySensor("last_job_drain_per_m_"),
```

Future sensors should choose a label whose slugified form matches the
`unique_suffix` to avoid this drift; the `_attr_suggested_object_id` belt
covers the case where it can't.

---

## 14. Lifecycle integration

### 14.1 `__init__.py` setup

```python
battery_manager = BatteryHealthManager(hass, runtime_manager=manager)
battery_manager.start(manager.get_known_vacuum_ids())
hass.data[DOMAIN][DATA_BATTERY] = battery_manager
```

Order matters: must run *after* the runtime manager is initialized (to read battery levels) and *before* `async_forward_entry_setups(entry, PLATFORMS)` so sensors can find the manager via `hass.data[DOMAIN][DATA_BATTERY]`.

### 14.2 `__init__.py` unload

```python
battery_manager = domain_data.pop(DATA_BATTERY, None)
if battery_manager is not None:
    battery_manager.stop()
```

`stop()` calls every recorded `unsub` from `_vacuum_unsubs` and clears the maps. The next `start()` re-registers cleanly.

### 14.3 `learning/job_finalizer.py` hook

After the existing `cleaning_area_m2` and `cleaning_time_seconds` writes:

```python
try:
    # `resolved_rooms` lives at the TOP LEVEL of completed_job
    # (build_completed_job_payload promotes it there), not inside the
    # inner "job" dict. Looking inside _job returns an empty list, which
    # forces weighted_by="none" and empty per-bucket maps even on
    # genuinely single-room runs.
    resolved_rooms = completed_job.get("resolved_rooms")
    if not isinstance(resolved_rooms, list) or not resolved_rooms:
        resolved_rooms = _job.get("resolved_rooms")
    if not isinstance(resolved_rooms, list) or not resolved_rooms:
        resolved_rooms = (
            payload_state.get("resolved_rooms")
            if isinstance(payload_state, dict) else []
        )

    battery_metrics = compute_job_battery_metrics(
        battery_start=battery_start,
        battery_end=battery_end,
        duration_minutes=_job.get("duration_minutes"),
        cleaning_area_m2=inputs.get("cleaning_area_m2"),
        resolved_rooms=resolved_rooms or [],
    )
    _job["battery_metrics"] = battery_metrics

    outcome_status = str(completed_job.get("outcome", {}).get("status", "")).lower()
    if outcome_status in {"completed", "interrupted"} and outcome.get("used_for_learning", True):
        battery_manager = self.hass.data.get(DOMAIN, {}).get(DATA_BATTERY)
        if battery_manager is not None:
            battery_manager.record_job_metrics(
                vacuum_entity_id=vacuum_entity_id,
                metrics=battery_metrics,
                job_id=job_id,
            )
except Exception:
    _LOGGER.exception("battery: failed to compute job metrics")
```

**Lookup order rationale:** `completed_job.resolved_rooms` is the
canonical location populated by `build_completed_job_payload`, which
falls back through `payload_state.resolved_rooms` and
`active_job_state.resolved_rooms` itself. The two extra fallbacks here
(`_job.resolved_rooms`, `payload_state.resolved_rooms`) only matter if
the build pipeline is changed in future; at the time of writing the
top-level read is the only one that actually fires.

The `try/except` is defensive — a failure here must not block job finalization.

---

## 15. Restart safety

| Concern | Handling |
|---|---|
| Cumulative cycles survive restart | Persisted in `eufy_vacuum.storage` under `battery.vacuums.<vid>.cycles` and `cumulative_drain_pct`. |
| Drain across an HA outage | Counts toward cycles when the post-restart sample arrives. The delta is rejected if it exceeds `MAX_DELTA_PCT`, otherwise added. |
| Rate metrics across an HA outage | Skipped — the `MAX_RATE_INTERVAL_SEC` gate rejects the first post-restart sample's rate computation (would be averaged over the gap). |
| Health baseline | Persisted, never resets. To re-baseline, manually delete `record.baseline` from storage. |
| Open charge session at restart | Closed implicitly on the next sample if `charging` reads false; otherwise the stale-session safeguard force-closes after `SESSION_MAX_HOURS`. |
| Post-job charge linkage pending at restart | **Lost.** `_pending_post_job` is in-memory only. The next charge session after restart classifies as `idle`. |
| Job aggregates | Persisted; new jobs continue contributing without recompute. |

---

## 16. Testing without hardware

For development without a live vacuum, the manager's `_process_sample` is the single entry point. A test harness can construct a `BatteryHealthManager` with a stub `runtime_manager` providing `data`, `_get_battery_level`, and `_is_recharge_like_state`, then drive a synthetic sample stream through `_process_sample` directly — no HA event bus needed.

Useful synthetic fixtures:

- 0→100 charge over 90 minutes (full session, fed into baseline)
- 80→100 partial recharge (high zone update only)
- 100→0 drain (one full cycle accumulated)
- 60→62 in 4 hours simulated (long gap — drain counts, rate skipped)
- 15→75 mid-job recharge with `_has_active_job` mocked True (mid-job stat update)

---

## 17. Known limitations / future work

- **Per-room m² is not available.** The vacuum reports only job-wide `cleaning_area_m2`. Per-bucket attribution prorates by `estimated_minutes`. If Eufy ever exposes per-room area, swap the prorate logic.
- **Charge-rate temperature confound.** Outdoor / unconditioned spaces will affect rate. The current health proxy assumes consistent temperature; that's true for typical indoor use but would need a temperature compensation layer for garage installs.
- **No per-bucket drain attribution for mixed runs.** By design — see section 10. If you need per-mode drain numbers and rarely run single-mode jobs, you need more single-mode runs, not more code.
- **Sensor entity IDs are derived from the vacuum's object_id.** If the user renames their vacuum, the entity IDs migrate via the normal HA entity-registry rename flow. Storage keys remain the original vacuum_entity_id from the integration's perspective — the rename doesn't break the link.
- **Post-job recharge linkage is in-memory.** Section 11 covers the trade-off.
