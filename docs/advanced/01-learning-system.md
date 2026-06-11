# The Learning System

The learning system watches your vacuum's cleaning runs over time and builds per-room timing data from them. As it accumulates more runs, it produces increasingly accurate time estimates, ETA chips, and progress percentages in the card. The system is optional — the integration works without it, but you lose all estimate and ETA features.

---

## How It Works

Every time a cleaning job finishes, the integration finalizes the run into a completed-job record and archives it to disk. A separate process called the stats rebuilder then reads all archived jobs and computes per-room averages. Those averages are what the estimator uses the next time you start a clean.

The flow looks like this:

1. Job starts — a live snapshot is saved capturing the room list, battery level, and pre-job estimate.
2. Job ends — the finalizer archives the completed-job record, including outcome, duration, and any estimate-versus-actual data.
3. Stats are rebuilt from all archived jobs.
4. The estimator reads the rebuilt stats and uses them for the next run.

---

## What Is a Learning Job

Not every completed run contributes to learned stats. A run that contributes is called a **learning job**. A run qualifies only when:

- Its outcome status is `completed` (not `cancelled`, `failed`, `interrupted`, or `test`).
- It passes basic sanity checks — valid room count and a positive duration.
- It has not been manually excluded.
- No learning blockers were set (for example, a cancel-like detection or missing room attribution).

Runs that do not qualify are still archived to history. They count toward your run log and metrics displays but do not move per-room averages. You can see which runs were excluded and why in the learning history snapshot.

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
