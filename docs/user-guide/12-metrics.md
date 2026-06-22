# 12 — Metrics

The Metrics tab shows aggregated data the integration has collected across all cleaning jobs for your vacuum. It covers how much cleaning time has been logged, how the integration's learning system is performing, how water is being used, and what the dock has been doing. You can filter all of this data by room, cleaning profile, job status, or whether a job was used by the learning system.

## Opening the Metrics tab

Click **Metrics** in the tab bar. The card fetches a snapshot from the integration backend and renders the view. If the snapshot has not loaded yet, the card shows "Loading metrics...". If metrics are unavailable for any reason (for example, no jobs have been recorded), the card shows the reason message instead of the panels.

---

## Overview stats

At the top of the view, a summary panel labelled **Metrics** shows four figures:

| Stat | What it counts |
|---|---|
| **Jobs** | Total job records in the current snapshot (after any active filters) |
| **Used** | Jobs that were used by the learning system |
| **Excluded** | Jobs that were excluded from learning |
| **Updated** | Timestamp of the last snapshot refresh |

The subtitle below the panel title reads: "Usage, learning quality, water, and dock metrics across the learning dataset."

---

## Filters

A **Filters** panel sits next to the overview stats. It lets you narrow all metrics down to a subset of jobs. Each filter is a row of chip buttons — click a chip to apply that filter, click the same chip again (or the "All …" chip) to clear it.

The four filters are:

- **Room** — show only jobs that cleaned a specific room. The options come from the rooms the integration knows about for this vacuum.
- **Profile** — show only jobs that ran under a specific cleaning profile. Profile chips include a tooltip showing extra detail when available.
- **Status** — show only jobs with a specific status (for example, completed, failed, or interrupted).
- **Learning Use** — show only jobs that were or were not used for learning.

Selecting a filter immediately re-fetches the snapshot from the backend with the updated filter values, so all panels and tabs reflect the filtered data.

---

## Tabs

Below the filters, a tab bar switches between six data views. The default tab when you first open Metrics is **Learning**.

The six tabs are: **Learning**, **Rooms**, **Profiles**, **Water**, **Dock**, and **Battery**.

---

### Learning tab

The Learning tab is the primary view for understanding how the integration's learning system is performing over time.

**Time-window cards** — three cards at the top show cleaning activity across three windows:

| Card | Window |
|---|---|
| Today | Jobs run today |
| Last 7 Days | Jobs run in the past 7 days |
| Last 30 Days | Jobs run in the past 30 days |

Each window card shows total cleaning duration, job count, how many jobs were used for learning, total water used, and mid-job recharge count.

**Summary mini-cards** — a grid of six compact cards shows:

| Card | What it shows |
|---|---|
| Found Profiles | Number of profiles that have learning history attached |
| Exact Stats | Number of exact room-learning stat groups |
| Baselines | Number of room baseline groups |
| Accuracy Rows | Number of accuracy stat rows |
| Recharge Count | Observed mid-job recharges across all matching jobs |
| Wash Cycles | Wash cycles recorded across matching jobs |

**Found profile cards** — if the current filters return any profiles with learning history, up to 8 profile cards appear below the summary grid. Each card shows the profile name, trust level, run counts, and a **Save Profile** button if the profile is a save candidate and saving is supported. If no found profiles matched, the tab shows "No found profiles were returned for the current filters."

---

### Rooms tab

The Rooms tab shows a card for each room that has metric data under the current filters.

Each room card shows:

- Room name
- Average cleaning duration
- Total run count and how many of those runs were used for learning
- Trust level (the integration's confidence in its learned data for that room)
- How many more runs are needed to reach "trusted" status

If no rooms matched the current filters, the tab shows "No room metrics matched the current filters."

---

### Profiles tab

The Profiles tab shows two sections.

**Room-profile cards** — one card per room-profile combination that has data under the current filters. Each card shows:

- Profile name and optional subtitle (typically the room name)
- A **Save Candidate** badge if the integration has identified this profile as worth saving
- Average cleaning duration
- Run count and learning-used count
- Average water usage
- Trust level
- A **Save Profile** button if the profile is a save candidate, saving is supported, and a save service is configured. The button shows "Saving..." while the operation is in flight.

**Found Profiles section** — below the room-profile cards, up to 12 found-profile cards appear with the heading "Found Profiles" and subtitle "Detected profile families and trust state." These cards follow the same layout as those on the Learning tab.

If no room-profile metrics matched the current filters, a "No room-profile metrics matched the current filters." message is shown in place of the first section.

---

### Water tab

The Water tab focuses on water consumption.

**Summary mini-cards** — three cards at the top show totals across all matching jobs:

| Card | What it shows |
|---|---|
| Robot Water | Total water applied directly by the robot during cleaning |
| Water Overhead | Total water used by the dock for washing and other operations |
| Total Water | Combined total of robot water and overhead water |

All water values are displayed in millilitres (ml), rounded to the nearest whole number.

**Highest Water Rooms** — up to 8 rooms, sorted by average total water use (highest first), appear as cards. Each card shows the room name, average total water per run, and a breakdown into robot water and overhead water.

**Highest Water Profiles** — up to 8 profiles, sorted the same way, appear with the same breakdown.

Both sections only appear if there is data to show under the current filters.

---

### Dock tab

The Dock tab shows counts and timestamps for events recorded at the charging dock.

**Event counts and water** — six mini-cards:

| Card | What it shows |
|---|---|
| Mop Wash | Total dock mop wash events |
| Dust Empty | Total dock dust-empty events |
| Dry Starts | Total dock dry-start events |
| Wash Cycles | Wash cycles inferred from job records |
| Water Overhead | Total dock water overhead in ml |
| Avg Overhead / Job | Average dock water overhead per job in ml |

**Event timestamps and rebuild times** — six more mini-cards showing when things last happened:

| Card | What it shows |
|---|---|
| Last Mop Wash | Timestamp of the most recent dock mop wash |
| Last Dust Empty | Timestamp of the most recent dock dust empty |
| Last Dry Start | Timestamp of the most recent dock dry start |
| Last Dry Duration | Duration of the most recent dock dry cycle |
| Room Stats Rebuilt | Timestamp of the most recent room stat rebuild |
| Accuracy Updated | Timestamp of the most recent accuracy stat update |

Timestamps are shown in short-month format (for example, "Apr 18, 9:30 AM"). Fields with no recorded data show "Unknown".

---

### Battery tab

The Battery tab is a focused readout of the integration's battery health subsystem. It samples battery level on every state change, classifies charge sessions, and rolls everything up into twelve sensors plus a per-job metrics block. The tab is the at-a-glance view; for the full feature explanation see [13. Battery health](13-battery-health.md).

**Top chips** — four headline numbers:

| Chip | What it shows |
|---|---|
| Charge cycles | Cumulative drain ÷ 100. Each percent of battery used adds 0.01 to the count. Persists across HA restarts. |
| Health % | CV-regime charge speed (80→90 % phase, the resistance proxy) compared to *your install's* baseline. Headline alias of the `_cv_charge_speed` sensor. 100% means matching the baseline; below 100% means slower-than-baseline. The companion `_cc_charge_speed` sensor tracks the CC regime (capacity proxy) for the full picture. Shows "Building baseline" until one qualifying recharge (start ≤ 50 %, end ≥ 90 %) has been recorded. See [13-battery-health.md](13-battery-health.md#seeding-the-baseline-faster) for how to force the seeding instead of waiting, and the `eufy_vacuum.battery_rebaseline` service for use after a battery swap. |
| Charge rate | Most recent instantaneous %/min while charging. |
| Last job %/m² | Battery used per square metre on the most recent completed job. |

**Charge rates by zone** — five rows, one per tracked region of the charge curve:

| Zone | Range | Notes |
|---|---|---|
| Overall | Any active charge | Last instantaneous rate. |
| Low (≤ 29 %) | Slow precharge / soft-cell signal. | Updated only when battery is in this zone. |
| High (≥ 80 %) | CV taper — earliest indicator of capacity loss. | Updated only when battery is in this zone. |
| Mid-job (15→75) | Rolling mean across mid-job recharge sessions. | The cleanest health signal: tight zone, pure CC region. |
| Last full session | Duration of the most recent completed charge. | Plus delta percent. |

**Drain per m² by single-bucket job** — a table of running mean drain rates broken down by clean mode, fan speed, and water level. Rows that say "no single-bucket jobs yet" appear until you've run a job where every room used the same value for that key. Mixed-mode runs feed the **All jobs** row only — they don't pollute per-bucket means.

**Most recent completed job** — a table of the per-job metrics: duration, area, battery used, drain rates, and the single-mode/fan/water tags (or "(mixed)" when not single-bucket). Includes the **Post-job recharge** linkage when present — once the vacuum finishes the recharge that follows the job, that session's duration, delta, and average rate appear here.

**Raw data files** — the full path to the per-vacuum CSV and JSONL the integration writes:

```
config/eufy_vacuum/battery/<object_id>/sessions.csv
config/eufy_vacuum/battery/<object_id>/samples.jsonl
```

You can chart any of the live sensors with HA's history-graph or [apexcharts-card](https://github.com/RomRider/apexcharts-card); for long-term review open the CSV in a spreadsheet.
