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

## The sensors

After the first restart following install, twelve sensors appear under your vacuum's device:

| Sensor | Unit | What it shows |
|---|---|---|
| `_charge_cycles` | (count) | Cumulative drain ÷ 100. Survives HA restarts. |
| `_charge_rate` | %/min | Last instantaneous charge rate. |
| `_charge_rate_low_zone` | %/min | Last rate when battery ≤ 29 %. |
| `_charge_rate_high_zone` | %/min | Last rate when battery ≥ 80 %. |
| `_mid_job_recharge_rate` | %/min | Rolling mean of mid-job recharge rates. |
| `_last_charge_duration` | min | Length of the most recent completed charge session. |
| `_battery_health` | % | Headline charge speed vs install baseline. Alias of `_cv_charge_speed`. |
| `_cv_charge_speed` | % | CV regime (80→90 % charging) speed vs baseline — the resistance proxy. |
| `_cc_charge_speed` | % | CC regime (50→80 % charging) speed vs baseline — the capacity proxy. |
| `_last_job_drain_per_min` | %/min | Battery drain rate of the most recent completed job. |
| `_last_job_drain_per_hour` | %/h | Same metric scaled to hours. |
| `_last_job_drain_per_m2` | %/m² | Battery used per square metre on the most recent job. |

The entity ID prefix is the vacuum's object ID — for example, `vacuum.alfred` produces `sensor.alfred_charge_cycles`, `sensor.alfred_battery_health`, `sensor.alfred_cc_charge_speed`, etc.

Each sensor also exposes rich attribute data for cards and automations. The three `_last_job_*` sensors carry per-clean-mode, per-fan-speed, and per-water-level aggregate means in their attributes — see [advanced/09-battery-health.md](../advanced/09-battery-health.md) for the full attribute list.

> **Why two charge-speed sensors plus a headline?** A battery's charge curve has two distinct regimes that age in **opposite directions**. Capacity loss makes the constant-current portion (50→80 %) appear *faster* per percent (less energy per percent), while resistance rise makes the constant-voltage taper (80→90 %) appear *slower* per percent (the charger has to back off sooner and longer). Averaging them into one number cancels real signal. The integration tracks each regime separately; the headline (`_battery_health`) is just an alias of the CV regime sensor (`_cv_charge_speed`), since CV-side slowdown is what most people mean by "battery health". Watch CC if you want capacity loss; watch CV (or the headline) for resistance rise.

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
  - sensor.alfred_battery_health        # headline (= CV regime)
  - sensor.alfred_cc_charge_speed       # capacity proxy (CC regime)
  - sensor.alfred_mid_job_recharge_rate # rolling mean, third-opinion
```

Charting CC and CV side-by-side over months is the most informative view: divergence between them tells you whether you're seeing capacity loss (CC drops faster) or resistance rise (CV drops faster), which can point to different replacement urgencies.

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

The first time the integration sees a **qualifying recharge** (start ≤ 50 %, end ≥ 90 %), it locks that session in as your baseline — the minutes-per-percent rate for *each regime* (CC and CV) is recorded as the anchor. After that, the three health-related sensors start publishing. The "current" side of the ratio is a 14-day rolling window of qualifying sessions.

This is a **per-install baseline**, not an estimate of factory-fresh performance. The integration has no way to know how a brand-new pristine version of your specific battery would charge — that depends on cell chemistry, charger hardware, ambient temperature, and a dozen other factors no software can introspect. So instead of pretending, it anchors on what *your* battery actually did the first time it was measured. Every future reading is "how does today compare to back then" — which is exactly the question that matters.

### CC vs CV: read both regimes, not just the headline

The headline `_battery_health` shows the CV regime (resistance proxy). For most users, that's the signal that matters — CV-phase slowdown is the textbook "battery aging" indicator. But the two regimes age in opposite directions, so reading both gives you the full picture:

- **`_cv_charge_speed` (= `_battery_health`)** — falls below 100 as resistance rises. The cell can't accept current as fast in the 80→90 % CV taper, so %/min slows. This is what most people mean by "battery health". A drop below 80 over months is a strong signal.
- **`_cc_charge_speed`** — also falls below 100 as capacity drops. Each percent of a smaller-capacity cell holds less energy, so the constant-current 50→80 % phase appears *faster* per percent (less to fill), which means the inverted ratio (baseline / current) reads lower. Counterintuitive but consistent with how the math works out.

Both metrics use the same scale: **higher = healthier**, 100 = matches your baseline. Falls in *both* over a long horizon are a strong replacement signal. A fall in only one is worth watching but not acting on alone — environmental drift can move either independently for weeks.

### Reading the headline number

Health % (the headline) is the ratio of baseline CV speed to current CV speed:

- **100 %** — current CV charge speed matches your install baseline.
- **Below 100 %** — current charges are slower than the baseline. A young battery hovers at 95-105 %; a moderately aged one drifts to 80-90 %; a battery approaching end-of-life drops below 70 %.
- **Above 100 %** — current charges are faster than the baseline. This can happen briefly with environmental shifts or simply with measurement noise when the data set is small.

The window for what counts as "qualifying" is intentionally wide (50→90 rather than the textbook 30→95): a vacuum that mostly runs single-room jobs rarely drains far enough on its own for the strict window to ever trigger, which would leave the baseline unseeded for months. The 50→90 window covers both the CC region (50→80) and the CV taper (80→90), so a single qualifying recharge is enough to anchor both regimes at once.

The **mid-job recharge rate** is a useful third opinion alongside the two regime sensors. It's a rolling mean rather than a comparison-to-baseline, so it doesn't have a "100 % means good" interpretation, but its trend over months is the cleanest signal you'll get from this hardware. A steady drop in the mid-job rate is a more reliable sign of degradation than the headline health %.

---

## Seeding the baseline faster

The baseline is anchored on the **very first** qualifying recharge the integration observes — so if you run heavy enough to drain to ≤ 50 % and then let it charge to ≥ 90 %, that one cycle is enough.

If you don't want to wait for the baseline to seed naturally, force it with a heavy-load job — settings that maximise power draw will get you to ≤ 50 % battery in one run:

1. **Queue as many rooms as you can** — every room is ideal, but more rooms = more drain whatever the count.
2. **Set max suction** (turbo / max — whichever is your top setting).
3. **Set max water level** if you're mopping. Mop pads dragged at high pressure pull serious wattage; vacuum-only is fine if you don't have mop pads installed but will drain slower.
4. **Narrow path / 2 passes** if your model supports it. Doubles the time-on-job per square metre.
5. **Edge cleaning on.** Adds an extra perimeter pass.

Run that and let it dock for an uninterrupted recharge to ≥ 90 %. As soon as the recharge session closes, the integration anchors **both regimes** (CC and CV) from that single session, and all three health-related sensors (`_battery_health`, `_cv_charge_speed`, `_cc_charge_speed`) start publishing.

Total time is one job + one recharge — typically 3-5 hours end to end. Best done within the first week or two of installation while the battery is healthy, since this anchor is what every future health % is compared against. Seeding when the battery is already worn means health % will read "100 %" of an already-degraded baseline.

If you've already let the integration run for a while without seeding (existing install, only short jobs / partial charges), forcing one deep cycle still works — the baseline is set the first time it sees a qualifying session in the recent history, regardless of how old the integration is.

### After replacing the battery

When you swap in a new battery the existing baseline is wrong (it describes the old battery), so health % becomes meaningless. The integration has a service for this — call **`eufy_vacuum.battery_rebaseline`** in Developer Tools → Services with your vacuum's entity ID. The baseline is cleared immediately for **both regimes** (CC and CV), and the next qualifying recharge re-anchors all of them on the new battery.

The service only clears the baseline anchor — your cycle counter, per-job aggregates, mid-job rate, and session history are all left alone (those are still meaningful: cycles is total wear regardless of which battery, aggregates are about the *vacuum's* power profile not the battery's age).

---

## Caveats

- **First samples may take a while to be useful.** The cycles counter starts at 0 and accumulates; health is None until baseline is seeded; per-mode aggregates need a few single-bucket jobs to mean anything. Expect 1-2 weeks of normal use — or a deliberate seeding pass per the "Seeding the baseline faster" section above — before everything is populated.
- **The vacuum reports SoC %, not actual current/voltage.** All the rates here are observed minutes per percentage point — a useful proxy that conflates battery condition, charger behaviour, and ambient temperature. Indoor use stabilises temperature; the charger is fixed; so what's left is mostly the battery.
- **Don't read a single bad week as "the battery is failing".** Trends matter more than instantaneous values. Same-season comparisons across months are more diagnostic than month-to-month within a year.
- **Mid-job recharges are gold.** If you don't run multi-room jobs that trigger them, the most reliable signal is unavailable; the per-install baseline approach still works but is noisier.

- **The baseline is whatever the first qualifying recharge happened to be.** If that first recharge happened on a hot day, with mop pads dragging on a heavy water level, after a long job — your baseline reflects all of that. The point is consistency, not perfection: the *trend* over months tells you the story, not the absolute number. If you want a cleaner anchor, see "Seeding the baseline faster" — running a planned heavy-load job under known settings gives you a deliberate baseline rather than whatever the integration happened to catch first.

For the full math, attribute schemas, zone-definition rationale, and automation ideas, see [advanced/09-battery-health.md](../advanced/09-battery-health.md).
