# Battery health

The integration includes a battery-health subsystem that tracks battery wear, charge speed, and per-job efficiency over time. It samples the vacuum's battery level on every state change, classifies each charge session, and rolls everything into ten Home Assistant sensors plus a per-job battery_metrics block on every completed job.

The point is to spot a degrading battery long before it starts cutting jobs short. With consistent indoor temperatures (your vacuum doesn't experience the cold-garage swings that confound this kind of measurement), the trend is genuinely useful — not lab-grade, but easily good enough to flag a battery that needs replacing 6-12 months before it would otherwise become a problem.

You don't have to do anything to enable it. After the integration loads, sensors start sampling and the at-a-glance view appears in the **Metrics → Battery** sub-tab.

---

## What the system tracks

Three categories of data:

1. **Charge wear** — cumulative cycles, computed as cumulative drain ÷ 100. This is the industry-standard wear measure: every 1 % the battery drops adds 0.01 to the cycle count, regardless of whether you charge it back up. After 100 percentage points of total drain (which can take many partial discharges), one cycle is logged.
2. **Charge speed by zone** — the rate at which the battery gains percent per minute, tracked separately for the slow regions where degradation shows up first:
   - **Low zone (≤ 29 %)** — slow start of the charge curve.
   - **High zone (≥ 80 %)** — the constant-voltage taper. This is the most sensitive early-warning indicator; as a battery ages, internal resistance rises and the charger has to taper sooner and slower.
   - **Mid-job (15→75)** — the recharges the vacuum does mid-clean to keep going. These are gold-standard data: tight, repeatable window in the pure constant-current region with consistent thermal load.
3. **Per-job efficiency** — for every completed cleaning job, the integration records battery used, duration, area cleaned (m²), and computes drain rates: %/min, %/hour, and %/m². Per-mode/suction/water aggregates accumulate over time.

---

## The ten sensors

After the first restart following install, ten sensors appear under your vacuum's device:

| Sensor | Unit | What it shows |
|---|---|---|
| `_charge_cycles` | (count) | Cumulative drain ÷ 100. Survives HA restarts. |
| `_charge_rate` | %/min | Last instantaneous charge rate. |
| `_charge_rate_low_zone` | %/min | Last rate when battery ≤ 29 %. |
| `_charge_rate_high_zone` | %/min | Last rate when battery ≥ 80 %. |
| `_mid_job_recharge_rate` | %/min | Rolling mean of mid-job recharge rates. |
| `_last_charge_duration` | min | Length of the most recent completed charge session. |
| `_battery_health` | % | Charge speed vs the first five qualifying full charges. None until the baseline is seeded. |
| `_last_job_drain_per_min` | %/min | Battery drain rate of the most recent completed job. |
| `_last_job_drain_per_hour` | %/h | Same metric scaled to hours. |
| `_last_job_drain_per_m2` | %/m² | Battery used per square metre on the most recent job. |

The entity ID prefix is the vacuum's object ID — for example, `vacuum.alfred` produces `sensor.alfred_charge_cycles`, `sensor.alfred_battery_health`, etc.

Each sensor also exposes rich attribute data for cards and automations. The three `_last_job_*` sensors carry per-clean-mode, per-fan-speed, and per-water-level aggregate means in their attributes — see [advanced/09-battery-health.md](../advanced/09-battery-health.md) for the full attribute list.

---

## Reading the Battery sub-tab

Open **Metrics → Battery** in the dashboard panel. The view has five sections:

1. **Top chips** — four headline numbers: cycles, health %, current charge rate, last-job %/m².
2. **Charge rates by zone** — one row per tracked region (overall, low, high, mid-job, last full session) with the most recent rate and a brief note on what that zone is good for.
3. **Drain per m² by single-bucket job** — a running mean drain rate per clean mode, fan speed, and water level. Only jobs where every room used the same setting feed these means; mixed-mode runs feed only the **All jobs** row. Until you've run enough single-bucket jobs, the per-bucket rows show "no single-bucket jobs yet".
4. **Most recent completed job** — full per-job metrics. Once the post-job recharge finishes, that session's duration, delta percent, and average rate appear here too — useful for comparing "this job used 25 %" against "the recharge that followed took 73 minutes 60→100 %".
5. **Raw data files** — paths to the CSV and JSONL the integration writes (see below).

---

## Charting

You don't need extra software to chart these sensors — they live in HA's recorder like any other. Drop one of these into your dashboard:

```yaml
type: history-graph
title: Battery health trend
hours_to_show: 720   # 30 days
entities:
  - sensor.alfred_battery_health
  - sensor.alfred_charge_rate_high_zone
  - sensor.alfred_mid_job_recharge_rate
```

For longer windows or per-mode bar charts, [apexcharts-card](https://github.com/RomRider/apexcharts-card) and [plotly-graph-card](https://github.com/dbuezas/lovelace-plotly-graph-card) are both excellent. Either can chart the live sensors and pull months of history out of HA's recorder.

---

## Raw data files

For long-term review beyond what the recorder retains, the integration also writes raw data to disk:

```
config/eufy_vacuum/battery/<object_id>/sessions.csv
config/eufy_vacuum/battery/<object_id>/samples.jsonl
```

- **sessions.csv** — one row per completed charge session: start/end timestamps, duration, start/end battery, delta percent, avg/min/max rate, sample count, ended reason ("full" vs "stopped"), and session kind ("mid_job", "post_job", "idle"). Open in any spreadsheet.
- **samples.jsonl** — every accepted battery sample as a JSON object on its own line: timestamp, battery level, charging flag, delta from previous sample, instantaneous rate, zone, drain added, cumulative cycles. Easy to tail or process with `jq`.

These files grow forever; the integration doesn't trim them. If they get unwieldy, archive and rotate them yourself — nothing else reads them, so removing them won't break the live sensors or the card.

---

## What "health %" actually means

When you've completed five qualifying full charges (start ≤ 30 %, end ≥ 95 %), the integration locks in a baseline: the average minutes-per-percent across those five charges. After that, the health sensor starts publishing.

Health is the ratio of baseline to current speed, expressed as a percentage:

- **100 %** — current charge speed matches the baseline.
- **Below 100 %** — current charges are slower than baseline. A new battery typically reads 95-105 %; a moderately aged one drifts to 80-90 %; a battery near end-of-life drops below 70 %.
- **Above 100 %** — current charges are faster than baseline. This can happen briefly with environmental shifts or simply with measurement noise when the data set is small.

The **mid-job recharge rate** is a useful second opinion. It's a rolling mean rather than a comparison-to-baseline, so it doesn't have a "100 % means good" interpretation, but its trend over months is the cleanest signal you'll get from this hardware. A steady drop in the mid-job rate is a more reliable sign of degradation than the headline health %.

---

## Caveats

- **First samples may take a while to be useful.** The cycles counter starts at 0 and accumulates; health is None until baseline is seeded; per-mode aggregates need a few single-bucket jobs to mean anything. Expect 1-2 weeks of normal use before everything is populated.
- **The vacuum reports SoC %, not actual current/voltage.** All the rates here are observed minutes per percentage point — a useful proxy that conflates battery condition, charger behaviour, and ambient temperature. Indoor use stabilises temperature; the charger is fixed; so what's left is mostly the battery.
- **Don't read a single bad week as "the battery is failing".** Trends matter more than instantaneous values. Same-season comparisons across months are more diagnostic than month-to-month within a year.
- **Mid-job recharges are gold.** If you don't run multi-room jobs that trigger them, the most reliable signal is unavailable; the 0→100 baseline approach still works but is noisier.

For the full math, attribute schemas, zone-definition rationale, and automation ideas, see [advanced/09-battery-health.md](../advanced/09-battery-health.md).
