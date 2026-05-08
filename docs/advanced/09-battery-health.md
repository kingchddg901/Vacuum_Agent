# Battery Health Tracking

The battery health subsystem records every battery sample, classifies charge sessions, computes per-job drain rates, and surfaces ten sensors plus a Metrics sub-tab. This document covers the math, the zone-definition rationale, the per-bucket aggregation rules, and how to use the data in automations.

For the user-facing tour see [user-guide/13-battery-health.md](../user-guide/13-battery-health.md). For internal architecture see [dev/battery-system.md](../dev/battery-system.md).

---

## Cycle counting

The integration uses the industry-standard **cumulative drain ÷ 100** definition:

```
cycles = cumulative_drain_pct / 100
```

Every percent the battery drops is added to a running counter, regardless of whether you charge it back up. After 100 percentage points of *drain* (which can take many partial discharges), one full cycle has been logged. Charging never decrements the counter — only drain wears the cell.

The counter:

- **Persists across HA restarts.** Stored in `eufy_vacuum.storage`.
- **Is monotonic.** Never decreases, never resets — match it against manufacturer cycle ratings (~1000 cycles for typical Li-ion robots) to estimate remaining service life.
- **Ignores absurdly large jumps.** If a single sample reports a delta over 50 percentage points (likely a sensor reset or HA restart gap), the whole delta is discarded. Otherwise the counter would inflate every time HA missed events while the integration was unloaded.

---

## Charge zones

Li-ion charge curves have three distinct phases. Two of them are diagnostic; one isn't. The integration tracks each.

### Low zone — battery ≤ 29 %

Slow start of the charge curve. If the cell was deeply discharged the charger uses a precharge / lower-CC current to safely revive the cell, transitioning to full constant-current at around 25-30 %. Slow rebound from low SoC suggests cell chemistry issues — soft shorts, electrolyte degradation. Less commonly the leading degradation indicator, but catches failure modes the high-zone metric misses.

The integration updates `sensor.<vacuum>_charge_rate_low_zone` only when battery is in this range.

### Mid zone — 29-80 %

Constant-current phase. Maximum charge rate; battery accepts current at full speed. **Charge rate here is dominated by the charger and thermal headroom, not the battery's condition.** Mixing this zone into the average dilutes the diagnostic signal — that's exactly why the integration tracks zones separately rather than reporting a single "average rate".

This zone has no dedicated sensor. It does feed `sensor.<vacuum>_charge_rate` (the overall instantaneous rate), but most of that sensor's variance comes from the slow zones.

### High zone — battery ≥ 80 %

Constant-voltage phase ("CV taper"). Voltage is held at maximum while current decays. As cells age, internal resistance rises and the charger has to taper sooner and slower — so this region stretches noticeably long *before* nominal capacity loss shows up. **The earliest early-warning signal.**

The integration updates `sensor.<vacuum>_charge_rate_high_zone` only when battery is in this range.

### Mid-job recharge — 15→75 %

Not a zone of the charge curve but a *type* of session. When the X10 Pro Omni runs a multi-room job and battery drops to ~15 %, it returns to the dock for a partial recharge to ~75 %, then resumes. Other Eufy models use similar logic.

Mid-job recharges are gold-standard diagnostic data:

- Tight, repeatable window — same start/end SoC every time.
- Pure constant-current region — no precharge slowness, no CV taper variance.
- Consistent thermal load — vacuum is hot from cleaning every time.
- Frequent — every multi-room job that exceeds ~85 % drain triggers one.

`sensor.<vacuum>_mid_job_recharge_rate` exposes a rolling mean of these sessions' average rates. A drop of 5-10 % in this metric over months is a more reliable health signal than the headline `_battery_health` percentage.

---

## Health proxy

`sensor.<vacuum>_battery_health` compares the *current* charge speed to a *baseline* established from your first qualifying full charges.

### Baseline

A "qualifying full charge" is a session where:

- `start_battery ≤ 30 %`
- `end_battery ≥ 95 %`

After the first **5** qualifying sessions are recorded, the baseline is locked in as the average minutes-per-percent across those five sessions. Until then, the health sensor returns None (the at-a-glance chip in the card shows "Building baseline").

### Current

A 7-day rolling window of qualifying sessions. If no sessions fall in the window, the most recent qualifying session is used as a fallback so the sensor never gets stuck at None after baseline is set.

### Formula

```
health_pct = round(baseline_min_per_pct / current_min_per_pct * 100, 1)
```

Interpretation:

| Range | Meaning |
|---|---|
| 95-105 % | Matches baseline. Normal noise. |
| 85-95 % | Mild degradation or environmental shift. Worth tracking trend. |
| 70-85 % | Moderate aging. Battery is past prime. |
| < 70 % | End-of-life. Replacement recommended within months. |
| Above 105 % | Briefly possible — cooler ambient, looser charge cycle, or noise on a small dataset. Not a malfunction. |

### Important caveats

- **The vacuum reports SoC %, not actual current/voltage.** What we measure is *observed minutes per percent*. That conflates battery condition + charger behaviour + ambient temperature. Indoor use stabilises temperature; the charger is fixed; so what's left is the battery — but the metric isn't direct capacity.
- **Don't over-react to a single bad week.** Trends matter more than instantaneous values. Same-season comparisons across months are diagnostic; month-to-month within a year is noise.
- **The mid-job recharge rate is a useful second opinion.** Different methodology (rolling mean rather than baseline-relative) so the two metrics drift independently. A drop in *both* is a strong signal; a drop in only one warrants more data before acting.

---

## Per-job battery_metrics

Every completed cleaning job gets a `battery_metrics` block attached to its job record (in addition to the existing job-finalizer fields). The block covers job-level drain rates and an attempt at per-mode/suction/water attribution.

### Schema

```python
{
    "battery_used_pct": 12,                  # battery_start - battery_end
    "duration_min": 30.2,                    # wall-clock minus pauses + recharges
    "area_m2": 65.5,                         # from sensor.<vacuum>_cleaning_area
    "drain_per_min": 0.397,
    "drain_per_hour": 23.84,
    "drain_per_m2": 0.183,

    "is_single_clean_mode": True,            # eligible for per-mode aggregate
    "is_single_fan_speed": True,
    "is_single_water_level": True,
    "single_clean_mode": "vacuum_mop",       # set when is_single_*
    "single_fan_speed": "max",
    "single_water_level": "off",

    "by_clean_mode":   {"vacuum_mop": {"area_m2": 65.5, "share": 1.0, "rooms": 4}},
    "by_fan_speed":    {...},
    "by_water_level":  {...},

    "passes_share":    {"1": 0.65, "2": 0.35},
    "edge_mopping":    {"on_share": 0.32, "off_share": 0.68},

    "weighted_by":     "estimated_minutes" | "room_count" | "none",
}
```

### Weighting

Per-room m² is not reported by the device — only the job-wide total. To produce per-bucket area shares, the integration prorates total m² across rooms by **`estimated_minutes`** from the learning system's per-room enrichment. So if the job's 65.5 m² had 10 min vacuum_mop and 5 min vacuum (estimated), the vacuum_mop bucket gets 0.667 share = 43.7 m².

When estimates aren't available (e.g. learning hasn't seen those rooms enough), the fallback is equal-weight per room. Either way the per-bucket area shares sum to the job total.

### Single-bucket gating — the most important rule

**Per-bucket drain attribution is only honest for jobs where every room used the same setting for that key.** A mixed-mode run can't tell you "mop mode used X %/m² and vacuum mode used Y %/m²" because the vacuum doesn't report per-room battery telemetry.

The integration handles this with single-bucket gating:

- Mixed-mode runs feed only the **All jobs** running mean.
- Single-bucket runs (every room same `clean_mode`, or same `fan_speed`, or same `water_level`) feed both **All jobs** *and* the matching per-bucket mean.

This is the same single-room-jobs-are-king philosophy the learning system uses for per-room timing. Keeps aggregates unbiased; mixed runs still get full job-level stats.

### Post-job recharge linkage

When `record_job_metrics` fires, the next charge session within 4 hours is linked to that job's record as `last_job.post_job_charge`. The block includes the recharge's start/end battery, duration, average rate, and ended_reason. This gives you a "this job used 25 % battery → the recharge that followed took 73 minutes 60→100 %" pairing — the ground-truth recovery curve, useful for spotting jobs that disproportionately stress the battery.

If the vacuum doesn't dock for a full charge within 4 hours (e.g. you pull it off mid-recharge), the linkage is dropped to avoid false attribution.

---

## Sensors reference

All ten sensors are pre-fixed with the vacuum's object_id (e.g. `sensor.alfred_charge_cycles` for `vacuum.alfred`).

| Sensor suffix | State | Unit | Attributes |
|---|---|---|---|
| `_charge_cycles` | cumulative cycles | (count) | cumulative_drain_pct, completed_sessions |
| `_charge_rate` | last instantaneous rate | %/min | battery_level, charging, last_sample_ts |
| `_charge_rate_low_zone` | last rate when ≤ 29 % | %/min | as above |
| `_charge_rate_high_zone` | last rate when ≥ 80 % | %/min | as above |
| `_mid_job_recharge_rate` | rolling mean of mid-job rates | %/min | sample_count, last_rate_per_min, last_recorded_at |
| `_last_charge_duration` | minutes for last completed session | min | last_charge_delta_pct |
| `_battery_health` | charge speed vs baseline | % | baseline_min_per_pct, baseline_session_count, completed_sessions |
| `_last_job_drain_per_min` | drain rate of last job | %/min | (see below) |
| `_last_job_drain_per_hour` | scaled to hours | %/h | (see below) |
| `_last_job_drain_per_m2` | drain per m² of last job | %/m² | (see below) |

> **Legacy entity ID note:** Installs registered before the entity ID pinning
> fix may have `sensor.<vacuum>_last_job_drain_rate` instead of
> `sensor.<vacuum>_last_job_drain_per_min` — this is the same sensor under an
> older label-derived name. Both forms are supported by the panel card. New
> installs and freshly-deleted-and-recreated registry entries will use the
> `_per_min` form. To migrate an existing install: delete the entity from
> Settings → Devices & Services → Eufy Vacuum → Entities and reload the
> integration; it'll re-register at the new name.

### Last-job sensor attributes

The three `_last_job_*` sensors carry the same rich attribute payload, including:

- `job_id`, `recorded_at`, `duration_min`, `area_m2`, `battery_used_pct`
- `single_clean_mode`, `single_fan_speed`, `single_water_level` — null when mixed
- `weighted_by` — how per-room weights were computed
- `post_job_charge` — the linked recharge session (null if not yet observed)
- `all_jobs_mean`, `all_jobs_count` — running mean across all jobs
- `by_clean_mode_mean`, `by_fan_speed_mean`, `by_water_level_mean` — per-bucket means and counts (only fed by single-bucket jobs)

---

## Raw data files

Two append-only files per vacuum, written under:

```
config/eufy_vacuum/battery/<object_id>/
```

### samples.jsonl

One JSON object per line, written on every accepted sample:

```jsonl
{"ts": "2026-05-08T12:34:56+00:00", "battery_level": 82, "charging": true, "delta_pct": 1.0, "rate_per_min": 0.5, "zone": "high", "drain_added": 0.0, "cycles": 12.34}
```

Use `tail -f` or `jq` for live monitoring; rotate or archive periodically since the file grows forever.

### sessions.csv

One row per completed charge session, header on first write:

```csv
start_ts,end_ts,duration_min,start_battery,end_battery,delta_pct,avg_rate_per_min,min_rate_per_min,max_rate_per_min,samples,ended_reason,kind
```

`kind` is one of `mid_job` / `post_job` / `idle`. `ended_reason` is `full` (battery hit 100 %) or `stopped` (charging ended early). Open in any spreadsheet for trend charting.

---

## Automation examples

### Notify on health drop

```yaml
automation:
  - alias: Battery health below 80 percent
    trigger:
      - platform: numeric_state
        entity_id: sensor.alfred_battery_health
        below: 80
        for: "01:00:00"   # debounce against noise
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Vacuum battery aging"
          message: >
            Charge speed is now {{ states('sensor.alfred_battery_health') }}% of baseline.
            Consider scheduling a battery check or replacement.
```

### Track cycles for replacement planning

```yaml
template:
  - sensor:
      - name: "Alfred battery cycles remaining"
        unit_of_measurement: "cycles"
        state: >
          {{ 1000 - (states('sensor.alfred_charge_cycles') | float(0)) | round(0) }}
        attributes:
          replacement_due_at: >
            {{ ((1000 - (states('sensor.alfred_charge_cycles') | float(0))) /
                ((states('sensor.alfred_charge_cycles') | float(0)) /
                 ((as_timestamp(now()) - as_timestamp('2026-01-01')) / 86400 / 365))) | round(1) }} years
```

### Skip cleaning if battery health critically low

```yaml
automation:
  - alias: Pause schedule if battery is dying
    trigger:
      - platform: numeric_state
        entity_id: sensor.alfred_battery_health
        below: 65
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.daily_vacuum_schedule
      - service: notify.mobile_app_phone
        data:
          title: "Vacuum schedule paused"
          message: >
            Battery health dropped below 65%. Daily schedule disabled —
            jobs may not complete reliably until the battery is replaced.
```

### Compare per-mode efficiency

The per-mode means are exposed as attributes on `sensor.alfred_last_job_drain_per_m2`:

```yaml
template:
  - sensor:
      - name: "Mop drain per m2"
        state: >
          {{ state_attr('sensor.alfred_last_job_drain_per_m2', 'by_clean_mode_mean')
             .get('vacuum_mop', {}).get('mean', 0) | round(3) }}
        unit_of_measurement: "%/m²"

      - name: "Vacuum drain per m2"
        state: >
          {{ state_attr('sensor.alfred_last_job_drain_per_m2', 'by_clean_mode_mean')
             .get('vacuum', {}).get('mean', 0) | round(3) }}
        unit_of_measurement: "%/m²"
```

Compare these two over a few weeks to see how much extra battery your mop runs cost.

---

## Charting

Recommended approach: live sensors → HA's history-graph or apexcharts-card. Long-term trends → CSV in a spreadsheet.

```yaml
# Health trend chart — drop into a dashboard card
type: history-graph
title: Battery health (90 days)
hours_to_show: 2160
entities:
  - sensor.alfred_battery_health
  - sensor.alfred_mid_job_recharge_rate
  - sensor.alfred_charge_rate_high_zone
```

For per-mode bar charts and grouped time series, [apexcharts-card](https://github.com/RomRider/apexcharts-card) handles attribute access and grouping cleanly.
