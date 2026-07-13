# 01 — The Learning System

The learning system watches your vacuum's cleaning runs over time and builds per-room timing data from them. As it accumulates more runs, it produces increasingly accurate time estimates, ETA chips, and progress percentages in the card. The system is optional — the integration works without it, but you lose all estimate and ETA features.

---

## How It Works

Every time a cleaning job finishes, the integration finalizes the run into a completed-job record and archives it to disk. This happens both for runs this integration dispatched and for runs you started from the vacuum's own app (see [Attributing app-started and dispatched runs](#attributing-app-started-and-dispatched-runs)). A separate process called the stats rebuilder then reads all archived jobs and computes per-room averages. Those averages are what the estimator uses the next time you start a clean.

The flow looks like this:

1. Job starts — a live snapshot is saved capturing the room list, battery level, and pre-job estimate.
2. Job ends — the finalizer archives the completed-job record, including outcome, duration, which rooms were actually cleaned, and any estimate-versus-actual data.
3. Stats are rebuilt from all archived jobs — unless learning processing is turned off, in which case the run is collected now and processed later (see [Collecting vs processing runs](#collecting-vs-processing-runs)).
4. The estimator reads the rebuilt stats and uses them for the next run.

---

## What Is a Learning Job

Not every completed run contributes to learned stats. A run that contributes is called a **learning job**. A run qualifies only when:

- Its outcome status is `completed` (not `cancelled`, `failed`, `interrupted`, or `test`).
- It passes basic sanity checks — valid room count and a positive duration.
- It has not been manually excluded.
- No learning blockers were set (for example, a cancel-like detection or missing room attribution).

Runs that do not qualify are still archived to history. They count toward your run log and metrics displays but do not move per-room averages. You can see which runs were excluded and why in the learning history snapshot.

Two cases are captured rather than dropped:

- **Interrupted runs.** A run cut short by power loss, a mid-run restart, or a firmware hang no longer vanishes (or corrupts a later run's record). It is finalized as `interrupted` into the same review flow — visible, but not contributing to averages.
- **Extreme unexplained idle.** A completed run with a large idle stretch that is *not* a charge/wait phase or a logged error is held from learning, so one anomaly can't skew a room's baseline. Held runs stay visible and are restorable.

---

## Attributing app-started and dispatched runs

For the learning system to credit a run to the right rooms, it has to know which rooms the vacuum actually cleaned. Two run types are handled, on both Eufy and Roborock:

- **Dispatched runs** — started by this integration, so the queue already names the target rooms in order.
- **App-started (external) runs** — started from the vacuum's own app, with no queue to anchor to.

Both recover the cleaned-room set from a live room signal captured during the run. The signal source is brand-specific: Roborock reads its native current-room name and matches it to a managed room; Eufy reads the decoded-map pose from the live map. (Without a live map, Eufy falls back to today's manual review step — attribution is purely additive.)

**External runs** are attributed after the fact and open the review panel pre-answered with the rooms the vacuum cleaned, instead of a blank guess. The clean-versus-not decision is made by swept floor area: a room whose `cleaning_area` grew by at least ~0.5 m² while the vacuum was in it counts as cleaned, while a parked dock or a mop-wash (which sweep ~0 m²) do not. Because this is area-based, it needs no exact position fix.

**Dispatched runs** already have a planned room order, but the vacuum can deviate from it. The finalizer compares the planned order against the live room signal and either:

- **confirms** the assignment when they agree,
- **rescues** it when the planned order was already known-unreliable, or
- **flags** it when the two confidently disagree — the planned assignment is kept (never silently overwritten) and the run gets a **Room Mismatch** badge in the review panel for you to check.

Strict-order (phased) jobs are left untouched — they capture accurate per-phase timings directly.

### Cleaning-area units and the sanity bound

`cleaning_area` is normalized to canonical square meters using each sensor's own `unit_of_measurement`, read live so an in-app unit change is handled. On an imperial Home Assistant, Eufy's sensor reports square feet while Roborock's reports square meters; read as-is, Eufy areas were inflated ~10.76×. When a counter resets or drops mid-run, per-room area sums only the positive increments, so a non-monotonic counter is re-baselined rather than double-counted.

The device's own run-total area is the sanity ceiling: attributed per-room area can fall short of it (transit and approach accrue but belong to no room), but if the attributed sum exceeds the device total by more than 10% the run is flagged `area_over_attributed` as likely double-counted.

---

## Data Collected Per Room

The stats rebuilder aggregates learning jobs into per-room stat entries. Each entry is keyed by room slug, map ID, clean mode, clean passes, carpet flag, and clean intensity — so a room vacuumed once versus vacuumed twice with a mop gets separate learned entries.

Each entry stores:

| Field | What it is |
|---|---|
| `avg_minutes` | Average clean duration for this room and settings combination |
| `minutes_stddev` | Standard deviation of that duration across samples |
| `avg_battery_used` | Average battery percentage consumed |
| `sample_count` | Number of learning jobs that contributed |
| `mean_abs_pct_error` | Mean absolute error between past estimates and actuals (a fraction, not a percent) — stored separately in `accuracy_stats.json` under the same room key, not in the per-room stats entry |

The accuracy data (estimate versus actual) is stored separately in `accuracy_stats.json` and is used to apply a penalty to confidence when your past estimates for a room have been consistently wrong.

---

## How Confidence Works

Each room in an estimate gets a confidence score from 0.0 to 1.0. The score is built from several components:

**Base score**
- Learned match found: `0.55`
- No match, using default fallback: `0.20`

**Sample bonus** — up to `+0.25`, saturating at 10 samples. The more runs the system has seen for this room, the higher the bonus.

**Variance penalty** — up to `-0.25`. Calculated from the coefficient of variation (standard deviation divided by mean). If the room takes a wildly different amount of time each run, the score drops.

**Intensity mismatch penalty** — `-0.15`. If the system found a match for this room but at a different clean intensity setting than the one currently configured, it applies this penalty.

**Accuracy penalty** — up to `-0.20`. If your past estimates for this room have been off by more than 20% on average, the full penalty applies.

The **job-level confidence** is always the minimum of all room scores. The weakest room drives the whole job's confidence. This is a hard rule — a single unknown room pulls the entire estimate down to low confidence.

### Confidence tiers

| Label | Score range | Card variant |
|---|---|---|
| `high` | 0.80 – 1.00 | Success (green) |
| `medium` | 0.50 – 0.79 | Warning (yellow) |
| `low` | 0.00 – 0.49 | Error (red) |

### Learning velocity

For each room the system also exposes a **learning velocity** — how many more runs are needed to reach `medium` and `high` confidence. The card uses this to show messages like "3 more runs to reliable estimate."

---

## How Estimates Are Displayed in the Card

Before a job starts, the estimator computes a full job estimate from the ordered room list. The estimate includes:

- **Per-room timeline** — each room's expected duration, start and end offsets from job start, and an ETA timestamp.
- **ETA chips** — the projected finish time for the whole job and for each upcoming room.
- **Progress percentage** — once a room completes with a known actual duration, the timeline is *reanchored*: completed rooms show their real duration, and remaining room ETAs are shifted to account for any difference from the estimate.
- **Job ETA** — the wall-clock time the job is expected to finish, updated each time a room completes.

The card shows confidence as a colored chip alongside each ETA. Green means the estimate is backed by solid history; yellow means it is building; red means it is a default guess.

---

## Zone learning

[Saved zones](../user-guide/04a-zones.md) run as steps get their own learning track, separate from and much simpler than room learning. A zone has a stable `zone_id` (no slug-matching to do), a size that comes deterministically from its drawn box (never learned), and it cleans in one uninterrupted pass (no counter-stream segmentation, no transit, no drift). So the only thing learned for a zone is **time**.

### Wall-clock, not area

A zone's time is learned as a **wall-clock total** — from the moment the phase dispatches to the moment it completes. That is deliberate: for a small zone the clock is dominated by *preparation*, not floor area. A ~0.5 m² mop zone might take five minutes almost entirely spent docking to wet the pad and washing afterward — its size says nothing useful about that. Wall-clock captures the wait you actually experience; area does not.

The learned time is keyed by **`(zone_id, mode)`**, where mode is the coarse **mop** vs. **vacuum** bucket — the one dimension that materially changes a zone's time (a mop pass docks to wet and wash; a vacuum pass does not). Mop and vacuum runs of the same zone never share samples.

### What qualifies

- **Completed runs only.** A cancelled or partial zone would under-count, so only a completed phase folds into the average.
- **Single-zone steps only.** A [zone step](../user-guide/04a-zones.md#add-a-zone-to-a-run-a-zone-step) that cleans several saved zones at once can't attribute its one wall-clock time to a single `zone_id`, so it is *estimated* (as the sum of its zones) but not *learned*. A step with exactly one zone is what teaches that zone.

Each qualifying observation folds into a running mean, so history is never re-scanned. The per-zone data lives on the map bucket (`learned_zones[zone_id][mop|vacuum]`) and is persisted with the map — a re-map that invalidates a saved zone drops its learned times too.

### How a zone is estimated

| Situation | Estimate source |
|---|---|
| At least one learned sample for this zone and mode | The **learned average** — it takes over immediately at the first sample. |
| No sample yet, but the zone's size is known | **Area × a per-mode rate** (a mop pass is much slower per m² than a vacuum pass), shown as the "estimated from size" fallback with a `~`. |
| Neither | No estimate — the chip shows a "learning…" hint. |

Every estimate is clamped to a sane band so a degenerate area or one wild sample can't produce an absurd ETA. These per-zone estimates feed the zone chip's time and roll into the whole-run estimate alongside the room model.

---

## The Stale Flag

The learning system considers its stats stale if the last rebuild is more than **30 days** old. When stats are stale, every estimate payload includes `stats_stale: true`, and the card surfaces a warning so you know the estimates may not reflect recent changes in your cleaning patterns.

Stats go stale if the vacuum has not been run for a month, or if the rebuild process has not been triggered (for example, after a fresh install with no completed jobs yet). Running a full clean and letting the job finalize will trigger a stats rebuild automatically and clear the stale flag.

---

## Trouble Rooms

After every job finalization the system updates a per-room miss counter. A room is counted as missed when the job ended as `cancelled`, `failed`, or `interrupted` and that room's ID was in the queue but not in the completed rooms list.

A room is flagged `is_trouble` when both of these conditions are true:

- `miss_count >= 2` — the room has been missed in at least two runs.
- `miss_rate >= 0.33` — it has been missed in at least one-third of the runs it was queued for.

The card surfaces the trouble flag on the room tile so you can investigate whether the room has an access problem, a persistent navigation failure, or is regularly cancelled before the vacuum reaches it.

You can inspect the raw trouble room data using the `eufy_vacuum.get_trouble_rooms_log` service, which returns per-room counts and rates.

---

## Collecting vs processing runs

By default, every finalized run is both collected (archived to history) and processed (stats rebuilt) right away. On low-power hardware you can split those steps: turn processing off so runs are only collected, then catch up in one batch when convenient. Both services below are box-level — they apply to all managed vacuums.

Turn per-run processing off:

```yaml
service: eufy_vacuum.set_learning_processing
data:
  enabled: false
```

While processing is off, completed runs are still saved but the per-run stats rebuild is skipped, so nothing churns. A pending-run count shows how many runs are waiting. Process the backlog on demand, without turning per-run processing back on:

```yaml
service: eufy_vacuum.process_pending_runs
```

Turning processing back on (`set_learning_processing` with `enabled: true`) reprocesses the backlog and resumes normal per-run processing.

---

## Rebuilding Stats

When you want to force the system to recompute all learned stats from scratch — for example, after manually excluding or restoring runs — use the `eufy_vacuum.rebuild_learning_stats` service:

```yaml
service: eufy_vacuum.rebuild_learning_stats
data:
  vacuum_entity_id: vacuum.alfred
```

This re-reads every archived completed job, recomputes per-room averages and job aggregates, and writes fresh `room_stats.json` and `job_stats.json` files. The stats cache is invalidated and the new data is loaded automatically.

The optional `rebuild_csv: true` flag also regenerates flat CSV exports of all jobs and rooms if you use those for external analysis.

Stats are also rebuilt automatically when:

- A learning job is finalized normally (after each cleaning run).
- You exclude or restore a job using `eufy_vacuum.exclude_learning_job` or `eufy_vacuum.restore_learning_job`.

---

## Resetting Learning Data

### Exclude a single job from learning

To remove one run from the stats without deleting it:

```yaml
service: eufy_vacuum.exclude_learning_job
data:
  vacuum_entity_id: vacuum.alfred
  job_id: "job_2026-04-15T08-30-00"
  reason: "interrupted_run"
```

The job remains in your history. It just stops contributing to per-room averages. Stats are rebuilt automatically.

### Restore an excluded job

```yaml
service: eufy_vacuum.restore_learning_job
data:
  vacuum_entity_id: vacuum.alfred
  job_id: "job_2026-04-15T08-30-00"
```

This reverses the exclusion and triggers a stats rebuild.

### Reset all learning data for a vacuum

There is no dedicated reset service. To start fresh, delete the learning directory for the vacuum from your Home Assistant config folder:

```
config/eufy_vacuum/learning/<vacuum_slug>/
```

This removes all archived jobs, learned stats, accuracy data, and the live snapshot. After restarting HA (or triggering a rebuild), the system starts accumulating data again from zero. Use this only if you want a completely clean slate — for example, after significant changes to your room layout or cleaning settings.
