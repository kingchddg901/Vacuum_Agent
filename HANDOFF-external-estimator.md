# HANDOFF — External-Job Estimator / Attribution

Scratch handoff for the fork picking up the **external-job estimator** work. Not
for commit (delete or gitignore). Everything below is as of the handoff; verify
against code before assuming.

---

## 1. The goal

Issue: <https://github.com/kingchddg901/Vacuum_Agent/issues/4>

Today the learning system only ingests jobs **dispatched by the integration**.
App-started ("external") cleans are ignored, because HA doesn't expose the
room-cleaning payload for them — and the device's `active_cleaning_target` is
unreliable (it stayed `unavailable` for the whole example run).

We want to **capture external jobs on an *untrusting* basis** and **attribute
them to a room** from signals we *can* observe (position trail, cleaned area,
time, detectable mode), so they can optionally feed learning as low-trust data.

The crux that started this: with `active_cleaning_target` dead, can we recover
the room **geometrically** (position trail vs learned per-room bounds) + by
**area/time/settings**?

---

## 2. The blind protocol (IMPORTANT — keep it)

The user **knows** which room the example run was, and is deliberately **keeping
it hidden** from the assistant so the algorithm isn't overfit to the answer.
Rules:

- Produce **blind rankings**; the user confirms yes/no. Do **not** guess the room
  into the design.
- Confirmed so far: the **area-gated 4-room shortlist contains the real room**
  (Kitchen, Cat Room, Bathroom, Office). It is **NOT Cat Room** (a confident
  point-estimate guess that was wrong — see §4 lesson).

---

## 2b. This fork's job — work backwards from the answer

This fork is the **non-blind oracle**. It will be **told the real room** and works
**backwards**: given ground truth, find which signal(s) + threshold(s) *uniquely*
pick the true room out of the 4-room shortlist (Kitchen, Cat Room, Bathroom,
Office), and decide what the blind estimator (main session) is missing.

- **It makes no code changes.** It only reads live data and runs the prototypes
  (§9). It does **not** need the uncommitted v4 changes committed — the prototypes
  recompute area / time / buckets / edge straight from the raw job archive, so the
  fork is fully self-served by the data + scripts.
- **Report findings as discriminator *logic*, not the room name.** The main
  session must stay blind (§2) — naming the room defeats the experiment. Good
  output is a *rule the blind side can implement*, e.g. "area+time only narrow to
  the shortlist; the deciding signal is the footprint centroid vs de-polluted
  bounds, threshold ≈ N" — phrased without revealing which room it is.
- **Sanity-check against the data, not just the answer.** Confirm the proposed
  discriminator actually separates the true room from the other three on the real
  numbers (and on Run 2, when available) — not a coincidence that happens to point
  at the known answer.

---

## 3. What's already built (learning-stats building blocks)

All in `custom_components/eufy_vacuum/learning/`. **Uncommitted**, **synced to
the live install** for testing (`Z:\custom_components\eufy_vacuum\learning\`),
**714 unit tests green**, `docs/dev/10-learning-system.md` updated. `room_stats`
is now **schema_version 4**.

Activate on live: **HA restart** (re-import) + call service
`eufy_vacuum.rebuild_learning_stats` (or wait for the next internal job).

1. **`avg_area_m2`** (+ `area_m2_min/max/stddev`, `area_sample_count`) on
   `room_stats` exact entries **and** `room_baselines`. Aggregated **single-room
   jobs only** (`cleaning_area_m2` is a job total = the room's area only when
   `room_count == 1`; multi-room jobs are skipped — equal-splitting would corrupt
   per-room area). Area is **settings-invariant**.
2. **Setting buckets** on `room_baselines`: `by_clean_times` (`"1"`/`"2"`) and
   `by_edge_mopping` (`"on"`/`"off"`). Each bucket =
   `{sample_count, avg_minutes, minutes_min, minutes_max, minutes_stddev,
   avg_battery_used}`. The **min/max/stddev band** is mandatory — match within
   variance, never to a point mean. Learning-jobs-only.
3. **`edge_mopping` in the exact `room_stats` key.** It was edge-blind, so per-room
   timing blended edge-on/edge-off. Now edge-on and edge-off are learned
   separately. Estimator `_find_room_match` is a **5-pass** lookup:
   exact (incl. edge) → ignore intensity → ignore carpet → **ignore edge** →
   ignore passes. (passes & edge kept longest; they move time most.)
4. **`edge_mopping` in the accuracy/drift key too**, and **all key building
   unified on one `_room_key`** (now in `utils.py` next to `_room_profile_key`,
   re-exported from `stats_rebuilder`). Used by stats grouping + accuracy
   write + both accuracy reads — so room_stats and accuracy **cannot drift**.
   `room_actuals` (built in `manager.py`) now carries `edge_mopping`.

Files touched: `utils.py`, `stats_rebuilder.py`, `estimator.py`, `manager.py`,
`tests/unit/test_learning_stats_rebuilder.py`,
`tests/unit/test_learning_estimator.py`, `docs/dev/10-learning-system.md`.

Caveat: old 6-field accuracy entries are orphaned by the key change (harmless;
re-accumulate). Delete `accuracy_stats.json` for a clean slate if wanted.

---

## 4. The attribution algorithm (converged shape + findings)

**Shape: `area-gate → settings-bucketed time (within variance band) → geometry
tiebreak`.** NOT a flat weighted sum (a weighted sum let bad signal shapes
outvote the clean one — see lessons).

Per-signal findings:

- **Area = the backbone.** Settings-invariant, pollution-immune, calibration-free.
  Gate `|room_avg_area − job_area| ≤ ~1.5 m²` eliminates 5–6 wrong-size rooms
  immediately. This is what gives the confident shortlist.
- **Learned map bounds are TRANSIT-POLLUTED.** In `map_6.json`, aggregate
  per-room AABBs are unions over runs, so transit balloons them to ~whole-map:
  **7.1 of 8 rooms' boxes contain every trail point**, and several rooms share
  byte-identical whole-map boxes. ⇒ centroid/point-in-bounds attribution is
  **unusable until de-polluted** (Thread A). The per-run `job_bounds_history`
  entries hold tighter, honest geometry — the raw material is there.
- **Time must be matched WITHIN A VARIANCE BAND** (min/max/stddev), learning-
  filtered. **Lesson:** point-matching to the mean manufactured false confidence
  and produced a **wrong** answer (Cat Room). With bands, the example's 540 s is
  **outside every room's no-edge band** → time alone is *inconclusive* here.
- **Edge-mop materially changes time and is undetectable from the CSV — but
  inferable.** The **cleaning mode IS detectable** (`select.alfred_cleaning_mode`
  = "Vacuum and mop" + water consumed ⇒ mopping happened ⇒ carpet rooms excluded,
  edge-mop possible). The device applies **map-stored per-room settings** (passes,
  edge) even to app jobs, so the **stored room config is the predictor** for the
  undetectable settings. Stored config also resolves passes (the example is
  clearly 2-pass; 1-pass is excluded by time everywhere).
- **DATA GAP:** the candidate rooms have **zero edge-on time history**, so
  "edge adds time" is currently a *capability/direction* argument, not a
  quantified bucket. `by_edge_mopping` will fill once edge-on jobs run.

Open question being tested: the 540 s is either an **outlier** or a **real
edge/gentle-settings signature with no learned baseline**. The user is running
the **same room again** for a 2nd CSV to decide (see §5).

---

## 5. Example data + the run-2 experiment

**Run 1** CSV (the worked example): `C:\Users\CKing\Downloads\history.csv`
(HA recorder export). External app job, `vacuum.alfred`, **map 6**,
`work_mode = Room`, `active_cleaning_target = unavailable` throughout,
mode "Vacuum and mop", water 64→52 (mopping), intensity Normal / water Low /
mop Quiet / suction Standard.

**Run-1 fingerprint:** area **4 m²**, `cleaning_time` **540 s** (~9 min),
75 position points, trail centroid **(15578, 4925)**, bbox **X[15360–16040]
Y[~4000–5835]**.

**Run 2 (done — `scratch-external-estimator/run2-history.csv`):** same room, same
settings. **Result: 540 s and 4 m² repeat *exactly* → the 540 s is NOT an
outlier.** It's the room's real signature for the app's gentle settings
(Quiet / Low / Normal), which the learned no-edge bands (270–390 s) don't cover.
⇒ **time cannot attribute external app jobs** until that settings combo has
learning history; **area (rock-stable 4 m²) + geometry are the signals.**

**Geometry is weaker than hoped — single-run footprints don't match**, and it is
*not* fixable by the obvious filters:
- vacuum-`cleaning`-state window: IoU 0.19, centroid dist 198.
- **cleaning_time-gated** window (in-room only — `cleaning_time` ticks only once
  the robot is *at the room*, so this strips the dock→room transit): IoU **0.06**,
  *worse* → transit wasn't the problem.
- **dock-normalized** (subtract each run's docked baseline to cancel SLAM frame
  drift; the dock's raw coords moved (16461,21)→(16390,108), ~70–90 u/session):
  IoU **0.00**, also worse → not simple frame drift either.

⇒ The ~200 u offset is **genuine coverage/path variation**: Run 1 cleaned the
left sub-band (x≈15416–15678), Run 2 the right (x≈15642–15903). **A single run's
footprint is NOT a reliable room fingerprint.** Consequences:
- Represent a room as a **stable envelope = union of many clean runs**; attribute
  a single run by **containment** in that envelope (do the run's points fall
  inside room X?), *not* by footprint overlap / centroid match.
- Reinforces the **untrusting** thesis: confident single-run external attribution
  probably isn't achievable from area+time+geometry alone → area-gate to a
  shortlist + a low-confidence geometric lean + **flag for review**.
- **Thread A win (from the cleaning_time observation):** build per-room bounds by
  sampling **only while `cleaning_time` is active** — a device-provided transit
  filter — unioned over runs; cleaner than the current vacuum-state sampling.
  (Use it for the *time* axis too: `cleaning_time` is transit-free in-room time.)

Reproduce: `scratch-external-estimator/compare_runs.py`.

---

## 6. Architecture / code map

- **Job model / lifecycle:** `jobs/active_job.py`, `queue/queue_engine.py`. Jobs
  are created **only** when the integration dispatches. **No external-job
  capture** — the core missing piece. Finalization gated in
  `listeners/lifecycle.py` on `has_observed_active_lifecycle` +
  `task_status == Completed` + `active_target` cleared.
- **Mapping bounds:** `<config>/eufy_vacuum/mapping/<vacuum_slug>/map_<id>.json`
  (e.g. `Z:\eufy_vacuum\mapping\alfred\map_6.json`). Active map from
  `sensor.alfred_active_map`. Each room: `job_bounds_history` (AABBs in **raw
  vacuum coords** = same space as `robot_position_x/y_raw`, so point-in-bounds is
  valid) + aggregate `bounds` (union) + `excluded` flag. `_point_in_bounds`,
  `update_room_bounds`, percentile-trim already exist in `mapping/manager.py`.
  NOTE: `.storage/eufy_vacuum.storage` holds **CV image-segments** (pixel space,
  720×729) — a *different* geometry with no raw↔pixel transform; **don't use it
  for trail attribution** (dead end already explored).
- **Trust model to reuse:** `mapping/trace_review.py` (verdict
  accepted/rejected/needs_refine; in_room_ratio, transit_ratio, spread). Learning
  has `trust_score`/`trust_level`, `excluded_from_learning`, `outlier_score`. An
  external job should ingest as **low-trust** and pass through this gate.
- **Learning:** `learning/{stats_rebuilder,estimator,job_finalizer,history_store,
  manager}.py`. Job archive:
  `<config>/eufy_vacuum/learning/<slug>/jobs/*.json` — each has
  `job.cleaning_area_m2`, `job.cleaning_time_seconds`, `duration_minutes`,
  `resolved_rooms[]` (with `edge_mopping`, `clean_passes`),
  `outcome.used_for_learning`. Rebuilt stats: `learned/room_stats.json` (v4),
  `accuracy_stats.json`.
- **Room identity:** `(vacuum, map_id, room_id)`; slug descriptive. map_6 rooms:
  1 Heidi and Chris (carpet), 2 Bathroom, 3 Bryan (carpet), 4 Hallway,
  5 Kitchen, 6 Entryway, 7 Living Room, 8 Dining Room, 9 Office, 11 Cat Room.

---

## 7. Open threads / next steps

1. **(a) Commit the v4 learning batch** (area + variance buckets + edge in stats
   key + edge in accuracy key). Uncommitted, live-synced. Never `git add -A`.
2. **(c) Thread A — de-pollute the bounds** (the geometry disambiguator; fixes
   internal attribution too). **Root fix (from the cleaning_time finding):**
   timestamp position samples and **collect bounds only from in-room samples —
   those taken while `cleaning_time` is actively ticking** — which excludes the
   dock→room (and, if `cleaning_time` pauses between rooms, the room→room) transit
   that balloons today's boxes (the 7.1/8 pollution). For multi-room jobs,
   **segment the run on cleaning-active gaps** and map segment K → the Kth
   dispatched room, so per-room sample sets need **no** reliance on the (circular,
   polluted) bounds at all. Then build each room's geometry as a **stable envelope
   = union of many such clean runs** (convex hull / trimmed box + density
   centroid). **VERIFY FIRST:** does `cleaning_time` *pause* during inter-room
   transit on a multi-room job? (run a 2-room job, watch the counter) — if yes it
   strips ~all transit; if no, only the initial dock→room leg, and inter-room
   segmentation needs another signal.
   **Gate spec (confirmed on single-room run2, `cadence.py`):** `cleaning_time`
   rises in **30 s steps while cleaning**. Compare each +30 increment to
   wall-clock: ~30 s/+30 = in-room (collect); a long gap = transit/wash (skip).
   Run2 showed exactly one big gap (193 s = dock→room transit + mop-wash) then
   flat ~30 s for the whole clean; cleaning jitter was 30–41 s vs the 193 s
   transit, so a **~60–90 s threshold** cleanly separates them. ⇒ Multi-room:
   each inter-room transit should be another such gap → split into cleaning
   segments → segment K = Kth dispatched room → per-room samples with no reliance
   on the polluted bounds.

   **VALIDATED on a real 2-room run (`multi room run.csv`, `segment.py`).** The
   full segmentation logic from `cleaning_time` alone: **rising** (+30 in ≤~75 s)
   = cleaning → collect; **plateau** (held) = wash/transit → skip; **reset** (→0)
   = next room → new segment. Result: 2 rooms split purely from the timer,
   **47 % of samples stripped** (transit/wash/dock), **zero dock leak** (lowest
   kept y 3645 vs dock y≈21–900). Crucially the two rooms **overlap
   geometrically** (centroids ~100 u apart) yet were separated **temporally** by
   the timer — i.e. we do NOT need geometry to separate rooms, which sidesteps the
   "all rooms collapse to 2 blobs" problem entirely. ⇒ This is the collector spec
   for the rebuild: per-segment, rising-only sampling; segment K → Kth dispatched
   room (internal jobs → direct; external jobs → clean clusters that area /
   de-polluted bounds attribute). Resolves both multi-room collection AND the
   systemic pollution, and weakens issue #4's "external jobs unlearnable" premise.
   **`cleaning_area` corroborates** (`area_vs_time.py`): it resets at the
   *identical* timestamps and plateaus in the same wash window, just coarser
   (~1 m²/step, ~half the events) — so use `cleaning_time` as the fine gate and
   `cleaning_area` as an independent cross-check (require BOTH to reset → glitch-
   robust room boundaries). Bonus: each segment's `cleaning_area` peak IS that
   room's area (Room A=4 m², Room B=9 m²), so the size axis falls out per-room
   from the same segmentation pass — no separate job-archive aggregation needed.

   **GEOMETRY VERDICT — raw coordinates are unreliable; don't build on them
   (`dock_check.py`).** The dock is physically fixed, yet its reported position
   ranges over 4 runs: Run1 (16461,21), Run2 (16390,108), Hallway (15802,1526)
   [Multi's (15780,2405) is partly a mid-return artifact] — a ~1450-unit y jump
   between sessions. So the docked-position readout is **dead as an anchor**
   (confirms: do NOT use a dock-offset) and there is real session-to-session
   coordinate shift. Caveat: the *same* room WAS ~200-unit consistent across
   Run1/Run2/Multi, so it's not full-scramble-every-run — but raw geometry is too
   shaky to anchor attribution, union across sessions, or separate adjacent rooms
   (~200-unit wobble). ⇒ **Drop raw-coordinate geometric attribution. Rely on the
   frame-invariant signals** (`cleaning_area` size, `cleaning_time`, within-run
   segmentation, + dispatched room order for internal jobs). Consequence: NAMING
   an external room is hard without geometry (rooms aren't uniquely sized — Kitchen
   ≈ blind room ≈ 4 m²), so external single-room naming circles back toward issue
   #4's original limit; internal-job learning is unaffected and gets clean
   per-room data. This also means the mapping subsystem's raw-coordinate
   `job_bounds_history` is of questionable value cross-session — Thread A's
   de-pollution may matter less than just NOT trusting raw bounds across runs.
   **Real pollution mechanism (the "distant rooms" theory was WRONG).** The
   Kitchen is *next to the dock* yet is the most polluted (whole-map), which
   breaks the distance/transit story. `job_pollution.py` shows why: only **2**
   jobs are credited to multiple rooms (not the cause), and **Kitchen's pollution
   comes from SINGLE-room kitchen runs that each span the whole map** (y≈8421)
   sitting beside **tight** kitchen runs (y≈870–3878) — 6 of 12 runs whole-map,
   6 tight. Same room, same single-room dispatch, wildly inconsistent extent ⇒
   ~half of kitchen's runs are **anomalous** (a few outlier samples / glitch /
   spurious traversal), and a raw min/max **AABB is destroyed by a single
   outlier**, which the union then keeps forever. Most runs (Kitchen=12) ⇒ most
   chances to catch a bad one ⇒ most polluted. ⇒ Thread A needs **outlier-robust
   geometry** (IQR/percentile sample trim, convex hull / density region instead of
   raw min/max, and/or rejecting anomalous *runs*) **in addition to** the
   cleaning_time transit-gate — the two fix different polluters (transit vs
   glitches). To pin the exact cause, grab a whole-map run's **raw trail**
   (recorder/live only — the job archive stores just the bound summary) and check
   if it's a few wild outliers (glitch) or genuine spread (mislabel/wander).
   (Still true: the union grows with run count, so more runs = more accumulated
   pollution today; the layered fix below inverts that.)

   **Raw samples are archived** — `Z:\eufy_vacuum\mapping\vacuum_alfred\
   raw_samples_room_<id>_<slug>.jsonl` (per-room; one JSON line per job:
   `{job_id, recorded_at, samples:[[x,y],…]}`). The fork can **replay any
   de-pollution algorithm against real per-job samples** — see
   `scratch-external-estimator/kitchen_diagnose.py`. Diagnosis of the whole-map
   kitchen runs (NOT simple glitch outliers): **two polluters** —
   (1) **transit tails**: samples trailing to the dock (y≈51–324) from
   approach/return, because sampling spans the whole `cleaning` state →
   `cleaning_time`-gating strips them; and
   (2) **anomalous big runs**: 4–6 'kitchen' runs of **640–692 samples spanning
   4000+ units even after P10–90 trim** (vs tight runs: 17–96 samples → ~400
   span) — look like whole-house/multi-room jobs recorded under one room; robust
   trimming barely dents them.
   ⇒ **Layered fix:** cleaning_time-gate (transit) + robust geometry/IQR (glitches
   + tails) + per-room **segmentation** (split big jobs to the right room via
   cleaning-active gaps → dispatched order) + **run-level anomaly rejection** (drop
   a run whose robust span ≫ the room's median). **Oddity to chase:** kitchen's
   robust core sits y≈4500–6300 in big runs vs y≈1900–4600 in others — and nowhere
   near "next to the dock" (y≈324); the kitchen *attribution itself* may be
   contaminated. **Dig outcome (`analyze_attribution.py`):** contamination is
   **systemic, not kitchen-specific** — most rooms' files hold whole-map spreads,
   and several rooms (Heidi, Cat Room) have **no clean run at all**, so they can't
   even be *located* from this archive. Room centers collapse into ~2 coordinate
   bands (y≈4300 Kitchen/Bathroom/Heidi = nearer-dock zone; y≈6000 the rest) and
   don't separate within a band. The dock (16461,21) is a far high-x/low-y corner,
   so every dock→room leg is a long diagonal = the low-y transit tail. **The
   archive cannot self-validate** de-pollution (no clean reference; circular) —
   validating any fix needs an **independent ground truth**: the physical layout,
   or the CV room polygons (`.storage` image-segments) + a raw↔pixel calibration.
   (Center-based attribution is hopeless here regardless; needs containment in
   de-polluted per-room envelopes.)

   **Rebuild plan (logic-checked).** The archive is too polluted to salvage
   incrementally → rebuild from scratch. BUT the saved samples are `[x,y]` with
   **no per-sample timestamps**, so the `cleaning_time` transit-gate **cannot be
   applied retroactively** (can't tell transit from in-room); only statistical
   trimming, which fails on the anomalous whole-map runs. ⇒ The real rebuild is
   **forward**: (1) change the collector to gated + **timestamped** sampling
   (store per-sample `ts` + `cleaning_time` next to `[x,y]` so the archive is
   *replayable*), (2) clear the polluted bounds, (3) accumulate clean runs into a
   union envelope. **Do NOT bake in a dock-offset "stability" correction** — it
   was tested (dock-normalizing 2 same-room runs made IoU *worse*, 0.06→0.00):
   cross-run variance is dominated by coverage variation, not a uniform frame
   shift, and the docked-baseline coord is a noisy/stale anchor. Stability comes
   from de-pollution + union-over-runs (absorbs the ~70–90u drift); if drift
   correction is ever needed, verify it lowers variance first and use multi-point
   registration (CV map/landmarks), not a single dock subtraction.

   **Gate the rebuild through the protection system.** `clear_room_bounds`
   (manager.py:1514) is today an unguarded one-call wipe (`rooms[key] = {}`). A
   from-scratch rebuild is a destructive op → route it through `setup/protection.py`
   (graduated normal/elevated/high+typed), like map-deletion. Refinements: (a) it's
   *narrower* than map-delete (wipes bounds+history, **keeps** rooms/rules/access-
   graph/profiles) → add a bounds-specific `evaluate_bounds_rebuild_protection`
   (reasons = has_learning_data, has_active_job; NOT rules/access-graph). (b) One
   map-level gated entrypoint (evaluate once, confirm once, clear all rooms), not N
   per-room wipes. (c) The `baseline_protected` guard (manager.py:1554) only blocks
   per-entry *pruning*; the full wipe bypasses it — correct for from-scratch (the
   baseline IS the polluted data), and the typed-confirm gate makes that safe.
   (d) Confirmation copy must state the consequence: bounds go **empty and refill
   over the next N gated cleans** (can't repopulate from the timestamp-less
   archive).
3. **BIG architectural piece — external-job capture + ingestion** (NOT started;
   needs a design + **approval pause** before coding, per the large-change
   workflow):
   - Detect `vacuum → cleaning` with no active job → an **observed-only** record
     (`source = "external"`).
   - Buffer the position trail (reuse the mapping tracker's sampling); finalize on
     the existing completion signals.
   - Attribute via §4 (area-gate → bucketed-time band → de-polluted geometry).
   - Ingest **low-trust**: `excluded_from_learning = True` (or a quarantine pool),
     run through `trace_review`; never let it corrupt trusted stats.
   - Likely files: `listeners/lifecycle.py`, `jobs/active_job.py`,
     `learning/job_finalizer.py`.
4. **Run 2 CSV** outlier check (§5) — pending from the user.
5. Smaller: edge-on time history will fill `by_edge_mopping` over time, making
   edge quantitative instead of directional.

---

## 8. Working agreements

- **Blind protocol** (§2) — don't learn/assert the room; rank, let the user confirm.
- **Large-change workflow:** design/plan + **mandatory approval pause** before
  big/architectural code (the external-capture wiring qualifies). Phased, not a
  rewrite, full-file correctness, explicit contracts.
- **Commit/release only when told. Never `git add -A`.** eufy_vacuum is
  HACS-managed; live testing is via **hand-sync** to `Z:\custom_components\
  eufy_vacuum\...` (overwritten on next HACS update — fine for iterating).
- **Tests:** `pytest tests --no-cov` in the pre-baked `eufy-vacuum-test` Docker
  image, **run via PowerShell** (Git Bash mangles `--workdir`):
  `docker run --rm -v "<repo>:/workspace" -w /workspace eufy-vacuum-test python -m pytest tests/unit --no-cov -q`.
  Behavior gate = 0 failures.
- Read `.storage` to inspect, **never edit it** (use HA UI). Mapping/learning JSON
  under `<config>/eufy_vacuum/` is fine to read.

---

## 9. Reproducing the analysis

Blind prototype scripts copied into **`scratch-external-estimator/`** (next to
this file, so they travel with the fork) alongside `run1-history.csv` (the Run-1
data):

- `attrib.py` — trail vs learned bounds (shows the 7.1/8 pollution).
- `sizematch.py` — per-room area + time profiles from the job archive.
- `estimator_proto.py` / `estimator_v2.py` — early weighted-sum (kept to show the
  point-estimate failure mode; superseded).
- `estimator_v3.py` — joint (passes × edge) buckets.
- `estimator_v4.py` — config-aware weighting (stored passes/edge, mode gate).
- `estimator_v5.py` — **variance-band** matching, learning-filtered (the right
  method). **Start here.**

They read live data on this machine (`Z:\eufy_vacuum\learning\alfred\jobs\*.json`,
`Z:\eufy_vacuum\mapping\alfred\map_6.json`) and hardcode the Run-1 CSV path
(`C:\Users\CKing\Downloads\history.csv`, also copied here as `run1-history.csv`);
repoint as needed. Core scoring sketch:

```
# area-gate → bucketed-time band → geometry tiebreak (blind)
for room in rooms:
    if abs(room.avg_area_m2 - job.area) > 1.5: continue        # area gate
    if room.is_carpet and job_mopped: continue                 # mode/mop gate
    # passes & edge unknown -> use stored config as predictor; match job.time
    # within the room's by_clean_times / by_edge_mopping band [min..max] (+/-stddev)
    # geometry: only once bounds are de-polluted (Thread A)
```
