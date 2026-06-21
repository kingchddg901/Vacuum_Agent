# External-run robustness — long-pause / freeze tolerance

Three tracked items surfaced 2026-06-20 from an overnight external (app-started) run where the
**robot froze mid-clean for hours**. The freeze corrupted the finalized review record on both
axes — the counter time/area segmentation *and* the W5c pose-attribution identity. Evidence
record: `external_jobs/job_2026-06-20T17-57-45Z.json` (see appendix).

## Design boundary (why these are *tolerance* fixes, not a cancel)

**Dispatched runs are integration-owned** → `listeners/pause_timeout.py` runs a 1-minute
watchdog that `async_cancel_active_job`s a paused job past its timeout. A frozen *dispatched*
job would have been auto-cancelled, so it never reaches this corrupted-record state.

**External runs are observer-only.** The integration did not start the app's job and must not
cancel it out from under the user — so external runs are **deliberately excluded** from the
pause-timeout watchdog. The consequence: external capture has to **tolerate** an arbitrarily
long pause/freeze gracefully, because nothing will stop it. All three fixes below are
capture/segmentation **robustness**, NOT pause-detection-to-cancel.

---

## Item 1 — pose sampler floods + rotates its buffer under a stall

**Where:** `listeners/pose_sampler.py` (the 2s ticker) + `jobs/active_job.py`
(`record_pose_sample`, `_MAX_POSE_SAMPLES = 3000`).

**Symptom:** a frozen-but-still-"present" robot keeps reporting the same static pose, so the
sampler records a redundant sample every 2s. Over a long freeze it hits the 3000 cap and the
del-oldest rotation **evicts the real cleaning data** from earlier in the run. `_is_parked`
does NOT catch this — `task_status` stays `Cleaning` through a firmware freeze.

**Why it matters:** in the evidence run the retained buffer covered only `18:20→20:00` (the late
+ frozen span); the early real cleaning (17:57→18:20) was gone. That directly starved W5c
(Item 3): the early counter segments had no pose coverage left to attribute.

**Fix:** a **stall detector** — when the anchor hasn't moved beyond a small epsilon over N
consecutive samples, stop recording (or record a single "stalled" marker) until it moves
again. Protects the buffer's real data and bounds the redundant writes. (Capture-side only; no
cancel.)

---

## Item 2 — a super-long pause corrupts the external counter segmentation

**Where:** the counter segmenter via `learning/external_ingest.build_pending_record` +
`_finalize_external_run` overhead accounting.

**Symptom (from the evidence record):** the freeze produced a **phantom 0 m² segment**
(order 2, `"weak"` boundary) and **inflated wall times** (orders 3 & 6 ran ~18 min each vs a
normal 3–9 min room) where pause time leaked into adjacent segments. `return_overhead_s=2773`
(46 min) WAS booked as overhead, but the segmentation still mangled into 7 segments for a
~5-room partial. The mid-run 0 m² segment survives because `_enrich_segments` only drops
*trailing* sub-`_MIN_ROOM_AREA_M2` segments (a leading/middle ~0 m² is kept on purpose, for the
cleaning_area-lag case — which a freeze defeats).

**Fix (tolerance, not cancel):** detect a contiguous span with **no cleaning_area progress over
a long wall gap** (a stall, distinct from a normal wash plateau) and book it **fully as
overhead** — excluded from segmentation rather than emitted as a 0 m² "room" / smeared into the
neighbors. Optionally cap the captured run window at the stall so the post-freeze recovery
movement doesn't extend it. Do NOT cancel the run (observer-only).

---

## Item 3 — W5c pose enrichment silently no-ops on a degenerate cleaned set

**Where:** `learning/external_ingest._apply_pose_identity` (returns early when `cleaned` is
empty) → the wizard falls back to the settings-ranked `shortlist[0]`.

**Symptom (from the evidence record):** `attribution_mode=robust` (the engine ran), but
**`pose_room_id` is empty on all 7 segments** and **`shortlist[0]` = `9:Office` on every one** —
so step 2 pre-fills *every* room as "Office." With the buffer rotated (Item 1) the cleaned set
came back empty/degenerate, so there was nothing to promote, and the all-vacuum_mop segments
tie to one room under settings ranking. The plumbing is correct; the input defeated it.

**Fix:** when attribution yields an **empty/degenerate cleaned set** (or robust mode but ~0
swept area across all rooms), set an explicit low-confidence marker on the record
(`attribution_mode` → something like `"unavailable"`, or an `attribution_confidence` field) so
the card can show "pose attribution unavailable for this run — pick rooms manually" instead of
silently defaulting all segments to the same settings-ranked room.

> **✅ ADDRESSED 2026-06-20.** `build_pending_record` now sets `attribution_confidence` on the
> record: `"available"` when pose named ≥1 segment, `"unavailable"` when a pose stream existed but
> named NONE (degenerate/empty cleaned set, anchor-only that isn't promoted, or the engine
> declined to attribute), `None` when no pose stream was captured. The card keys its "pose
> attribution unavailable — pick rooms manually" prompt off `"unavailable"`.

> **Partially addressed by Item 4's fix (2026-06-20).** `_apply_pose_identity` no longer
> early-returns on an empty `cleaned` set — it now **presence-names** each counter segment by its
> dominant pose room. So a segment that *has* pose coverage gets a real (low-confidence) room
> instead of the settings-ranked default. The freeze evidence run is still defeated because its
> buffer was rotated (Item 1) — the early segments had *no* pose coverage, so the fallback returns
> `None` for them. The explicit "attribution unavailable" marker is still worth adding for the
> truly-no-pose case.

---

## Item 4 — stale `cleaning_area` drops the run's FIRST cleaned room  ✅ FIXED 2026-06-20

**Where:** `learning/external_ingest._apply_pose_identity` + the swept-area engine
(`room_attribution_engines`).

**Symptom (live, vacuum.alfred 2026-06-20, NOT a freeze):** a normal multi-room run cleaned
Kitchen(5) first, then Dining(8). The Eufy `cleaning_area` sensor was **stuck stale** through the
whole Kitchen clean — flat at 26 m², then reset to 2 m² with **zero positive steps** across
Kitchen's ~2 minutes (confirmed by `scratch stale_area_timeline.py`). The swept-area engine
credits area first-to-last per room, so Kitchen got ~0 swept → `cleaned={8}` only, and the
attribution **dropped the first room**. The counter segmenter still split *both* windows
(`cleaning_time` tracked fine), so the record kept 2 segments but Kitchen's segment fell back to
the settings-ranked `shortlist[0]` (a wrong room: `2:Bathroom`). Captured **[8]** instead of **[5,8]**.

**Why the obvious fixes don't work** (both ruled out against the raw 562-tick capture):
- *Anchor fallback* (rescue a swept~0 room by dwell/spread/winding): a real stale-masked clean is
  **not separable** from a genuinely parked dock on anchors alone (Kitchen spread 0.050 / winding
  6.85 vs a morning parked dock 0.043 / 1.50 — only ~1.2× apart, winding non-monotonic). This is the
  original F1 rationale for making swept-area authoritative; re-admitting anchors re-admits parked docks.
- *Consecutive-delta sum* (sum only positive `cleaning_area` steps to survive a mid-run reset):
  Kitchen had **0 positive steps** — the sensor was flat-stuck, not rising-then-reset — so there is
  no area signal to recover. Sum = 0.

**Fix (cross-signal via the counter):** when the **counter** found a real cleaning segment but pose
attribution can't confirm a *cleaned* room in its window, **name that segment by the dominant
`current_room`** the robot physically dwelt in (`_dominant_room` with `cleaned=None`), tagged
`pose_confidence="presence"`. Safe because the counter (a `cleaning_time`/area plateau) has already
vouched the window *is* a clean — the only open question is *which* room, and dwell answers it. A
swept-confirmed room still wins first and is tagged `pose_confidence="cleaned"`. Verified on the real
capture ([8] → [5,8]); regression-pinned at
`tests/fixtures/external_run/alfred_stale_area_first_room_2026-06-20.json` +
`tests/unit/test_external_ingest_attribution.py::test_stale_area_first_room_rescued_real_capture`.

**Residual risk / interaction with Item 2:** the presence fallback will also name a *phantom* counter
segment (e.g. the freeze 0 m² segment) if it has pose coverage — but it's tagged low-confidence
`presence` and the user reviews it, and once Item 2 excludes phantom segments the fallback never sees
them. **Not** fixed for the STAND-ALONE pose-only path (`build_attributed_job`, no counter to vouch):
a fully stale-masked first room with no counter signal still needs the deeper fix — capture
`cleaning_time` in the pose stream so the engine can tell active-clean (time rising) from parked
(time flat) even when `cleaning_area` glitches.

---

## Appendix — evidence record (`job_2026-06-20T17-57-45Z.json`)

```
source=(none)  attribution_mode=robust  segment_count=7  return_overhead_s=2773  gap_transit_s=60
seg 0 | 2.0 m² | wall=156  | job_start     | pose=∅ | shortlist[0]=9:Office
seg 1 | 2.0 m² | wall=179  | wash_plateau  | pose=∅ | shortlist[0]=9:Office
seg 2 | 0.0 m² | wall=120  | weak          | pose=∅ | shortlist[0]=9:Office   <- phantom (freeze)
seg 3 | 7.0 m² | wall=1062 | wash_plateau  | pose=∅ | shortlist[0]=9:Office   <- inflated (~18 min)
seg 4 | 4.0 m² | wall=519  | wash_plateau  | pose=∅ | shortlist[0]=9:Office
seg 5 | 7.0 m² | wall=360  | wash_plateau  | pose=∅ | shortlist[0]=9:Office
seg 6 | 4.0 m² | wall=1068 | wash_plateau  | pose=∅ | shortlist[0]=9:Office   <- inflated (~18 min)
```
Battery context: run started at 68% (not full — depleted by prior attempts), heavy config drained
~1.2%/min to 8%, a short-cut recharge to 23%, then froze ~20:03Z (battery + pose sensors went
stale together). Never docked → never finalized until manual recovery the next morning.
