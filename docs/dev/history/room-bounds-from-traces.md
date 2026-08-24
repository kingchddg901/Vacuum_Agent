# RETIRED — Room bounds from traces (and bounds review)

> **This is HISTORY. The code is deleted. Nothing here describes current behaviour.**
> Moved out of `11 — Mapping system` on 2026-08-14, verbatim,
> because it was the only retired design left sitting inside a live subsystem doc — a
> reader had to reach a banner to learn that four pages of present-tense algorithm
> described nothing that runs. Room tracking now reads the device's native
> current-room signal; see 11 §1.
>
> **Preserve the sections below verbatim — do not trim, do not "reconcile".** The
> present tense in them describes the RETIRED algorithm. This is the sole in-repo
> record of the design; the code is recoverable only from git history.

## Why it was retired

It rode the device's vacuum-coordinate frame, and Eufy **re-bases its coordinate
origin every session**, so bounds learned in one session did not describe the next.
Cross-session drift made the store unusable regardless of sample quality. Nothing
runs in vacuum coordinates now.

## What it got right, and why it is kept

It was **calibration-immune**, and that is the part worth not losing. CV gives room
shapes in PIXEL space; traces gave bounds in VACUUM space; the two were never
converted into each other. The USER tied them together by identity through
`segment_room_links` (`{segment_id: room_id}`), so a position resolved to a ROOM and
the room already knew its polygon. No decoded map, no affine fit, no transform to
drift.

That matters historically: when this was built, **Eufy's map was not decoded at all**.
There was a picture and a position stream and nothing joining them. This design was
the answer to that, not a workaround for a missing transform.

The linking half is **still live** — 11 §8.1, §10.2, and every custom layout owns its
own `segment_room_links`. Only the vacuum-space bounds store was deleted. A revival is
one store, not a mechanism.

## Revival criteria

Two requirements, and they are sufficient — attribution bootstraps itself, so no
native current-room signal is needed anywhere (§3.2: a single-room job attributes
every sample to that room unconditionally, and multi-room jobs then attribute against
bounds that already exist).

**1 — Stable INTER-session robot `(vx, vy)`, or a solvable shift.**
Absolute stability is not required; a recoverable offset is enough. The dock is the
natural landmark and is already observable in vacuum coordinates — §3.1 pauses
sampling there precisely to stop dock samples polluting bounds. Record the docked
`(vx, vy)` at session start, diff against the previous session, apply to the stored
bounds.

**The criterion is RESIDUAL ERROR AGAINST TOLERANCE, not the shape of the transform.**
This system is deliberately coarse: `BOUNDS_MARGIN = 50` on every containment test
(§3.3), P10–P90 trimming discarding the outer 20% of samples (§3.4), and a min/max
union across up to 20 runs (§3.6). Heading is never an input — the store is
axis-aligned min/max X/Y and containment tests, and overlapping claims are expected,
resolved first-match-wins (§3.2). It does not want precision.

So the test is: **after applying the dock-based shift, is the residual under ~50
vacuum units AT THE FAR CORNER of the map** — not merely near the dock? A pure
translation is corrected exactly at any distance by one landmark. A rotated frame is
not, and its error grows with distance: 1° at 5,000 units from origin is ~87 units,
past the margin, while the same rotation is invisible next to the dock.

**The failure mode is box INFLATION, not a wrong answer.** Because bounds are a
min/max UNION across runs, an uncorrected frame error makes every box grow until
rooms overlap everything and first-match-wins decides by insertion order. That is
precisely what the original retirement recorded — the cross-session bounds "were a
smear" — which is the signature of union-under-drift rather than a clean break.

**2 — A PERSISTENT map that can be sectioned any way you like, giving an image polygon
tied to room identity.**
How the sectioning happens is irrelevant — CV, hand-authored custom layouts, or a
device-published layout all satisfy it. What matters is that a polygon carries a room
identity. **The map must also SURVIVE a session**: the tie is `{segment_id: room_id}`,
and re-running CV "re-segments and forces a relink" (11 §8.1), so a device that
rebuilds its map between sessions breaks the identity tie and you relink forever.

### Who would benefit — and who would not

The two properties are independent, and it is a mistake to assume a stable origin
implies published rooms. A device needs a persistent internal frame to give stable
coordinates; it does not have to hand US a decoded room layout.

- **Eufy** — emits per-axis position, gives us no room geometry (we CV the PNG). This
  is exactly the shape that benefits. It fails only requirement 1.
- **Roborock** — publishes a native current-room signal, so nothing needs learning.
- **Dreame** — publishes per-room `x0/y0/x1/y1` plus `calibration_points`, and its dock
  position held to a few units across three-plus days and many sessions once its map
  settled (measured 2026-08-14). It satisfies requirement 1 and makes the system
  redundant by satisfying far more than requirement 2.

So the beneficiary is a brand with a stable (or solvable) origin and **no** published
room geometry. Chris, 2026-08-14, on retiring it to history: *"if we ever have that
situation its built already or close enough."*

---

### 3.1 What a "trace" is

A trace is a time-ordered list of vacuum position samples collected during a single cleaning job. Each sample is `(vx, vy)` in vacuum coordinate units. Samples are collected in `MappingTracker._handle_position_update` by reading the `robot_position_x` and `robot_position_y` HA sensor states.

Deduplication is applied at collection time: if the new `(vx, vy)` is identical to the most recently recorded position, it is discarded. This prevents the X and Y sensors firing separately on the same movement event from creating double entries.

Sampling pauses during mid-job dock returns (`pause_sampling` / `resume_sampling`) to prevent hundreds of identical dock-position samples from corrupting room bounds.

Samples are flushed to a temporary file (`_samples_active.json`) every 25 unique positions so that an HA restart mid-job can recover the partial run.

### 3.2 Attribution Strategy

At the end of a job, `RoomBoundsStore.update_room_bounds` attributes samples to rooms:

**Single-room job** (exactly one non-transition room in the job's room dict): all samples are attributed to that room unconditionally.

**Multi-room job**: for each sample `(vx, vy)`, the first room whose stored bounding box (expanded by `BOUNDS_MARGIN`) contains the point receives credit. Rooms with fewer than `MULTI_ROOM_MIN_RUNS = 4` active history entries are skipped as attribution anchors because their bounds are not yet reliable enough. Unattributed samples are discarded.

### 3.3 `BOUNDS_MARGIN = 50`

After attribution, the bounding box query in `_update_confidence` also uses the same margin:

```python
BOUNDS_MARGIN = 50.0  # vacuum units
```

This adds 50 vacuum units to each side of the stored bounding box when testing whether a position falls within a room. The margin exists to handle two situations:
- The robot may clean right up to the boundary of its known box, or slightly beyond it, as the room boundaries are learned incrementally.
- Coordinate jitter in the vacuum's reported position means exact bounding-box containment would miss valid cleaning positions near edges.

### 3.4 Percentile Trimming

Before samples are committed to history, `_percentile_trim` is applied:

```python
def _percentile_trim(samples, p_lo=0.10, p_hi=0.90):
    # Requires >= 10 samples (_TRIM_MIN_SAMPLES) to apply trimming.
    xs = sorted(vx for vx, _ in samples)
    ys = sorted(vy for _, vy in samples)
    n = len(xs)
    lo_i = int(n * 0.10)
    hi_i = min(int(n * 0.90), n - 1)
    x_lo, x_hi = xs[lo_i], xs[hi_i]
    y_lo, y_hi = ys[lo_i], ys[hi_i]
    return [(vx, vy) for vx, vy in samples if x_lo <= vx <= x_hi and y_lo <= vy <= y_hi]
```

The outermost 10% of both the X and the Y distributions are discarded (independently). A sample survives only if it is within both P10–P90 ranges. This eliminates:
- Dock-adjacent outlier coordinates that slip through the pause gate.
- Large coordinate excursions caused by the robot leaving a room briefly to navigate.
- Sensor glitch spikes that report a physically impossible position for one sample.

Below 10 samples, no trimming is applied because there is insufficient data to compute meaningful percentiles.

### 3.5 History Cap — 20 Entries

Each room's `job_bounds_history` is capped at 20 entries (newest first):

```python
history = [job_entry] + history
history = history[:20]
```

The newest entry becomes index 0. The oldest survives entry becomes index 19. This is the *baseline entry* and is protected from manual exclusion (see Section 7). Capping at 20 prevents unbounded file growth while retaining enough history for meaningful outlier detection.

### 3.6 Bounds Recomputation

After every history update, `_recompute_bounds_from_history` rebuilds the active bounding box:

```python
active = [e for e in history if not e.get("excluded", False)]
min_x = min(e["min_x"] for e in active)
max_x = max(e["max_x"] for e in active)
min_y = min(e["min_y"] for e in active)
max_y = max(e["max_y"] for e in active)
```

The resulting bounds is the *union* of all active (non-excluded) job entries. There is no decay or weighting — every active run contributes equally to the envelope. The centroid `cx, cy` is the midpoint of the union box. `run_count` is the number of active entries. `updated_at` is the `recorded_at` timestamp of the most recently added entry (index 0).

---

---

## 7. Excluded History Entries

> **Retired (mapping split).** The interactive **bounds-review** surface — which let
> a user exclude an outlier run's `job_bounds_history` entry from the accumulated box —
> is fully gone, along with the `job_bounds_history` store it operated on (§3).
>
> - **Frontend view deleted outright.** `src/renderers/mapping-review.js`,
>   `src/actions/mapping-review.js`, `src/state/mapping-review.js`, and
>   `src/styles/mapping-review.js` no longer exist, and the "Map Bounds Review" nav
>   tab/view is removed. (Some leftover `mapping_review.*` i18n keys still sit in the
>   locale bundle — a separate code-cleanup, not a feature.)
> - **Services gone.** `clear_room_bounds`, `exclude_room_job_bounds`,
>   `restore_room_job_bounds`, `rebuild_room_bounds_from_archive`, and
>   `get_room_bounds_snapshot` are all absent from `services.yaml`.
> - **Scoring gone.** The `boundary.py` transition-candidate scoring that flagged
>   L-shaped / corridor rooms was removed; `boundary.py` now holds only
>   `point_in_polygon` (§9.2).
>
> There is no longer any bounds store to exclude from. The retired review design lives
> in git history.

---
