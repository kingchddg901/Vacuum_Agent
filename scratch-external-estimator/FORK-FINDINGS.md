# Per-Room Timing Extraction, Attribution & Learning Gate (internal + external) — Design + Findings

Scratch / design doc. **Supersedes the earlier layered version of this file.**
Issue: <https://github.com/kingchddg901/Vacuum_Agent/issues/4>

---

## TL;DR — the design

Auto-attributing an app-started ("external") clean to a single room is **not
achievable** from HA-exposed signals (proven below: ~67% top-1 ceiling, SLAM frame
drift, cold-start rooms). **Don't try to be perfect.** Instead, human-in-the-loop:

1. **CAPTURE** the external job as an observed-only, low-trust record.
2. **SHORTLIST** likely rooms — rank by frame-invariant signals (area + return-leg
   travel); **top-3 ≈ 80%** — and offer an **"other…" full-list** fallback.
3. **USER CONFIRMS** the room (resolves the ambiguity we can't).
4. **NORMS-GATE** for learning: check the job against the *confirmed* room's learned
   bands. In-norms → ingest. Out-of-norms → flag / open a new settings bucket; never
   blend into existing norms.

The device *knows* the room (`active_cleaning_target`) but hides it for app jobs — the
human is the substitute for that missing signal. Each component does what it's good at;
nothing pretends to a confidence it doesn't have.

## The bigger win — the same machinery feeds INTERNAL learning (the "gold")

The counter-plateau segmentation (see §1) is **not external-only**. *Every* job — internal
or external — decomposes into ordered per-room **(area Δ, time Δ, battery Δ)** straight
from the counters. The only thing that differs is how each segment gets a room identity:

| step | internal job | external job |
|---|---|---|
| detect | the integration dispatched it (known) | counter reset with no active job |
| segment | counter plateaus → per-room deltas | same |
| **identify room** | **map segment K → dispatched queue room K** (certain) | area+travel shortlist → user confirms |
| learn-gate | actual area vs expected size | same + sanity-check the user's pick |

Two payoffs, both validated (`gate.py`):
1. **Multi-room internal jobs become per-room learnable.** The handoff §3 skipped them
   ("equal-splitting would corrupt per-room area") — the counter deltas split area and
   time *exactly*, no estimation. Worked multi-room run = Room A (5 m², 270 s) + Room B
   (4 m², 270 s).
2. **Area-vs-expected is a learning data-quality gate.** A clean that comes in under the
   room's learned size is a partial/interrupted clean whose short time would poison the
   room's timing baseline — gate it out of *timing* learning. On the archive this flags
   **~12%** of single-room cleans, and removing them **tightened Kitchen's time stddev
   101 s → 80 s** (~20%) — cleaner baselines, for free. Variable rooms gain more
   (Bathroom area swings [3..15] m², sd 5.7 — exactly what the gate catches).

This also sharpens the external **norms-gate** (§4) and adds a confirmation
sanity-check: if the user picks a room whose expected size is far from the observed
area, warn (likely mis-pick or an unsplit multi-room). Most rooms have stable area
(Dining [11..11], Hallway [6..6], Office [5..6], Cat [3..4], Entryway [1..1],
Kitchen [2..5]) so the gate trusts them; only the genuinely variable rooms get flagged.

### Validated end-to-end on a ground-truth internal job (`segment_internal.py`)
Internal multi-room job `job_2026-06-06T14-54-30` (`active_cleaning_target = "Hallway,
Kitchen"` — note: that sensor IS populated for internal jobs, only `unavailable` for
external). Blind counter-segmentation vs the device's own queue:
- **2 plateaus → 2 segments == 2 queued rooms**; deltas sum to the official totals
  (area 8 m², time 330 s).
- Segment 1 = **240 s / 6 m²**, segment 2 = **90 s / 2 m²**. Mapped to the queue:
  Hallway, Kitchen. The order even **self-checks by area** (seg-1's 6 m² fits Hallway's
  expected 6, not Kitchen's 4).
- **Gate**: Hallway 6 vs ~6 → in-norms (learn); Kitchen **2 vs ~4 → flag** — and rightly,
  `cleaning_intensity` was **"Quick"** for that segment (a deliberately light pass).
- The integration's *own* record proves the gap: `room_cleaning_minutes: null` (no
  per-room split for multi-room), yet `used_for_learning: true` with no blockers — so
  today the good Hallway sample is unused while the Quick-Kitchen rides along ungated.
  The counter split + area gate fixes both.

---

## Why auto-attribution fails — signal autopsy

| signal | frame-invariant? | verdict |
|---|---|---|
| time (in-room cleaning) | — | **dead** — settings-dependent; the 540 s gentle-mode run has no learned baseline and repeats exactly (not an outlier) |
| absolute position / bounds geometry | ✗ | **dead** — transit pollution + SLAM frame drift + cold-start (see below) |
| device map CV polygons | ✗ | **dead end** — pixel space, no raw↔pixel transform |
| **area (m²)** | ✓ | **backbone**, but coarse/variable (a ±1.5 gate misses the true room 18%) |
| **travel (return-leg)** | ✓ | usable — *physical distance*, adds a modest lift |
| mode / mop | ✓ | hard gate (excludes carpet rooms when the job mopped) |
| access-graph topology | ✓ (invariant) | can't be applied to a single trail without position (circular); travel already proxies the geometry it would give |

### The three things that kill position geometry
1. **Transit pollution** — a room's recorded bounds claim ground it never cleans.
   Kitchen's *tightest, cleanest* honest box (x[15075–15773] y[2439–6317]) contains the
   Hallway run's centroid (15156, 4924) — yet Kitchen never enters the hallway.
2. **SLAM frame drift** — the *physically fixed dock* reports different raw coords every
   run: (16461,21) / (16390,108) / (15802,1526). The drift is inconsistent (112 u to
   ~1500 u), has no fixed anchor, and dock-normalization makes cross-run overlap *worse*
   (IoU→0). Cross-session geometry can't be aligned, so even clean bounds wouldn't help.
3. **Cold-start** — only **4 of 10 rooms** have any usable bounds (Kitchen, Bathroom,
   Entryway, Cat Room); Hallway and Bryan have none at all.

---

## Empirical ceiling — leave-one-out on 39 archived single-room jobs

| features | top-1 | top-2 | top-3 |
|---|---|---|---|
| area only | 59% | 67% | **82%** |
| area + return-leg | **67%** | **77%** | 79% |

Travel *tightens* the guess (top-1 +8, top-2 +10) but slightly hurts top-3 (noisy with
small n). `return-leg ≡ total-travel` — use the return leg (simplest, prep-free).
**Data-limited**: only Kitchen is well-sampled (n=16); the rest are n≤5. Confusions are
exactly the structural collisions: **area-twins** (Kitchen↔Cat Room) and **equidistant
straight-shots** (Hallway↔Bathroom — same travel "shell"). ⇒ good enough to *shortlist*,
not to *decide*. Hence the human step.

---

## The frame-invariant features — how to compute them
- **area** = `cleaning_area_m2`, read **after** the per-job reset to 0 (the pre-reset
  value is stale from the previous job — saw a stale 9 where the truth was 6).
- **travel** = prefer the archive's `return_to_dock_minutes` (already clean). Else
  `duration_minutes − room_cleaning_minutes`. Use `room_cleaning_minutes` for in-room,
  **not** `cleaning_time_seconds` (the counter undercounts — 390 s vs 9.64 min wall-clock).
  From a live CSV: return-leg = `returning`→`docked`; for the out-leg use the **last**
  dock exit (mop-prep toggles docked↔cleaning at the start and inflate a naive measure).
- **mode** = `select.alfred_cleaning_mode` contains "mop" → exclude carpet rooms.
- Travel is **physical distance, not access-tree depth** — a straight-shot deep room
  (Bathroom, depth 3) has *less* travel than a shallower one (Hallway, depth 2).

---

## The design in detail

### 1. Capture  *(ARCH — needs design + approval pause before code, per large-change workflow)*
Detect `vacuum → cleaning` with **no active integration job** → write an observed-only
record (`source = "external"`). Finalize on the existing completion signals
(`listeners/lifecycle.py`: `has_observed_active_lifecycle` + `task_status == Completed`).
No positional buffering needed — the features are area/time/mode.

**HARD boundary signals — the counters, not the state (`timeline.py`).** `cleaning_time`
and `cleaning_area` are the ground-truth cleaning-progress counters:
- **Reset → 0 (both, together) = job boundary** (new queue dispatched). Hard.
- **Plateau (both stop incrementing) = room boundary / room-completed** — the robot is
  transiting or washing (with `wash_frequency = ByRoom` it washes after each room).
- **A contiguous increment-run = one room's actual cleaning**; its **area delta = that
  room's area**, **time delta = that room's time**.
- The counters BEAT the vacuum/task state: in the worked run, `vacuum=cleaning` /
  `task=Cleaning` for 20:11–20:12 while the counters never moved — a phantom "cleaning"
  (faffing between washes). Counting on state would have invented a third room; the
  counters show two. ⇒ "is it really cleaning?" = "did the counter move?".

**This puts multi-room external jobs IN SCOPE** (the handoff §3 punted on them because
area couldn't be split). Segment by plateaus and read deltas — no equal-splitting:
worked run = Room A (270 s, 5 m²) + Room B (270 s, 4 m²) = 9 m² total. Then shortlist
each room, user confirms the ordered list, norms-gate each.
**Boundaries WITHOUT a wash (no-mop / adjacent rooms) — use the AREA trace, not the gap
(`nomop_boundary.py`).** The minutes-long plateau only happens with `wash_frequency =
ByRoom`. Strip the wash and an inter-room hop becomes a **delayed (not skipped)
`cleaning_time` step** — the next +30 tick lands ~10–13 s late (a ~40 s gap). The catch:
a **multi-pass turn looks identical in the gap** (a 2-pass room turns at its midpoint,
also a ~40 s gap, reproducibly — verified on two Kitchen runs). They are told apart by
`cleaning_area`, which counts **unique m² covered**:
- **Room transition** → area **jumps and keeps rising** (new floor). no-mop Bath→Hall:
  gap 40–43 s with area `1→3`, then 3→4→5→6.
- **Pass-turn** → area is **flat and stays flat** (re-covering the same room). 2-pass
  Kitchen: ~40 s gap at the midpoint with area pinned at 4 for the *entire* 2nd pass.

So a room boundary = **a delayed `cleaning_time` step whose `cleaning_area` jumps and then
continues climbing.** For **internal jobs this is fully constrained**: known
`clean_passes` ⇒ expect `(passes−1)` *flat-area* delayed steps per room (turns); known
room count (queue) ⇒ expect `(rooms−1)` *area-jump* delayed steps (transitions). The value
where area plateaus = that room's **true size**; a multi-pass room whose area never
plateaus-then-holds ⇒ a **dropped pass** (a learning-quality flag).

This recovers per-room splits for **every internal multi-room job, mop or not** — the
no-mop case is *not* a dead end (earlier draft was wrong). Notes: `cleaning_time` is a
pure 30 s clock (verified — every step is +30 across all 6 captured jobs), so the signal
is in gap-timing + the area trace, never the step size; `cleaning_area` is 1 m² coarse, so
a transition into a very small room (<~2 m²) may not show a clean +2 jump, and the ~10 s
delay is near jitter — so the **area trace is the reliable half, the delayed step only
corroborates**.

**The area trace also recovers job STRUCTURE for EXTERNAL jobs (`pass_detect.py`)** — the
two things the device hides for app jobs. Unique-m² `cleaning_area` rises during pass 1
then **holds** while later passes re-cover, so:
- **pass count** = `total_cleaning_time / (cleaning_time at the LAST area increase)` —
  verified: the two external 2-pass Kitchen runs read 540/270 = **2.0**, the 1-pass
  external Hallway reads 270/270 = **1.0**;
- **true room area** = the plateau value (not inflated by extra passes);
- **room count** = the number of area-**jump** transitions + 1.

So the internal/external split is really about **identity, not structure**:
- *Structure* (room count, pass count, per-room area & time) is recoverable for **both** —
  from the counter/area trace alone.
- *Identity* (which room) is the only external-specific gap (the queue /
  `active_cleaning_target` are hidden), and that's what the area+travel shortlist +
  user-confirm covers.
Payoff: an external 2-pass clean's doubled time is no longer anomalous (the trace says
"2 passes" → gate against the 2-pass band), and a 2-pass single room can't be mistaken
for a 2-room job.

### 2. Shortlist
Rank rooms by normalized (area, return-leg) distance; apply the carpet/mop gate; present
**top-3 + "other… (full list)"**. Rooms with no baseline (cold-start) live only in the
full list until they accumulate history.

### 3. User confirms
The human resolves the area-twin / equidistant-shell ambiguities we can't. 100% where our
signals top out at 67%.

### 4. Norms-gate  *(reuses existing learning infra — small addition)*
Given the confirmed room R, look up R's baseline for the job's settings
(`room_baselines` + `estimator._find_room_match`, the 5-pass lookup). Check **area within
[min,max]/±stddev** and **time within the `by_clean_times` / `by_edge_mopping` band**.
- in-norms → ingest for learning (user-confirmed + consistent ⇒ trustworthy).
- out-of-norms → **flag / open a new settings bucket; do not blend** into existing norms.

**Worked example (the case that broke time-attribution becomes a feature here):** the
540 s gentle-mode Kitchen run — area 4 is in Kitchen's band, but 540 s ≫ Kitchen's learned
270–390 s (its history is all Max/High). The gate flags it as a new settings combo rather
than poisoning the Max/High norm. Exactly right.

---

## Reuse / touch-points
- `learning/room_baselines`, `learning/estimator._find_room_match`,
  `trust_score` / `excluded_from_learning` (quarantine) — already exist.
- `listeners/lifecycle.py`, `jobs/active_job.py`, `learning/job_finalizer.py` — capture/finalize.
- `rooms/access_graph.py` — topology; optional, for queue/UX ordering, **not** attribution.

## Gotchas (each cost real debugging)
- **Stale pre-reset sensor values** (`cleaning_area`, `cleaning_time`) — read post-reset.
- **`cleaning_time` counter undercounts** in-room time — use `room_cleaning_minutes`.
- **Mop-prep toggles** (docked↔cleaning at the start) inflate a naive transit — use the
  return-leg or the last dock-exit.
- **Vacuum-state window is useless for app jobs** (barely reads `cleaning`, ~2–6 samples
  at the dock) — gate trails on `cleaning_time` instead.

## Archived dead-ends (don't re-explore)
- **Envelope-containment geometry** — worked on the two Kitchen runs (de-pollute by fixed
  cutoff + point-in-any-box, top-3-ish), but fails the Run-2 window and Run-3, and is
  killed outright by frame drift.
- **Single-run shape/centroid match** — overfit to one fortuitous window.
- **Dock-normalization** — drift isn't a clean translation; IoU→0.
- **CV map segments** — pixel space, no transform to raw coords.

## Prototypes (`scratch-external-estimator/`)
- `segment_internal.py` — **ground-truth validation**: blind counter-segmentation of an internal multi-room job vs the device queue + area gate (Hallway learn / Kitchen flag).
- `nomop_boundary.py` — **the transition-vs-pass-turn discriminator**: delayed-step + area-jump (transition, area keeps rising) vs delayed-step + flat area (pass-turn). Run on no-mop multi-room + a 2-pass single-room CSV.
- `pass_detect.py` — **reads pass count + true room area from an external job** (no device cooperation): passes = total / clean_time-at-last-area-rise (2.0/2.0/1.0 on the three external runs).
- `scan_cadence2.py` / `find_gap.py` / `rise_segments.py` / `run_anatomy.py` — supporting: prove the 30 s quantization, locate the long gaps, count rise-stretches, anatomize a single run.
- `timeline.py` — merged counter/state timeline; shows the job-reset & room-plateau hard boundaries (+ the phantom "cleaning"). Run on a multi-room CSV.
- `gate.py` — validates the area-vs-expected learning gate (per-room area stability, ~12% flagged, Kitchen timing-band tightening).
- `calibrate2.py` — **the recommended attributor** (joint area+return-leg, LOO top-k). Start here.
- `calibrate.py` — first LOO (hard area-gate + travel; shows the 18% area-miss).
- `decompose.py` — `transit = floor − in-room − dock-actions` decomposition + leg breakdown.
- `transit.py` — transit/return-leg per run (with the mop-prep-toggle fix).
- `dock_drift.py` — the dock-drift / frame-instability evidence.
- `attribute.py` — full pipeline incl. area+mop gate + abstain (the Hallway abstain test).
- `prep.py` — room envelope inventory (which rooms are representable) + CSV entity list.
- earlier geometry/area-time probes: `verify*.py`, `depollute.py`, `estimator_v5.py`,
  `attrib.py`, `sizematch.py`, `compare_runs.py` (kept as the dead-end record).

## Test data (ground truth — blind experiment concluded)
Run1/Run2 = **Kitchen** (4 m², 540 s gentle mop). Run3 = **Hallway** (6 m², 270 s in-room,
L-shaped straight-shot, no bounds). The blind protocol is retired: the conclusion is
human-in-the-loop, so there is no auto-classifier left to overfit.
