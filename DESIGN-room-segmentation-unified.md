# Unified Room Segmentation & Per-Room Learning — Implementation Design

Merges two efforts into one: my transit/travel work (Phases 1–5, shipped-but-uncommitted)
and `scratch-external-estimator/FORK-FINDINGS.md` (counter-plateau segmentation). This is
the go-forward plan. Large-change workflow: **approval pause before any code; phased waves;
not-a-rewrite; explicit contracts.**

---

## 1. The core primitive — counter-plateau segmentation

`cleaning_time` and `cleaning_area` are cumulative **progress counters**, not state:
- `cleaning_time` = a pure 30 s clock (+30 per tick while actively cleaning). Plateaus during
  transit/wash. Resets to 0 at job start; **may or may not reset per room** (firmware/mode
  dependent — ByRoom wash = cumulative+plateau; some modes reset). **So resets are NOT the
  boundary signal.**
- `cleaning_area` = unique m² covered (+~1 per new floor). **Flat** while re-covering
  (multi-pass) or transiting.

**Boundary signals, in robustness order:**
1. **Job boundary** = both counters reset to 0 together. Hard.
2. **Room boundary, ByRoom wash** = a minutes-long **plateau** (both counters stop = the
   inter-room wash trip). Hard.
3. **Room boundary, no wash / adjacent** = a **delayed `cleaning_time` step** (~40 s gap vs
   the 30 s cadence) **where `cleaning_area` jumps and keeps rising** (new floor).
4. **Pass-turn (NOT a boundary)** = a ~40 s delayed step but `cleaning_area` stays **flat**
   (re-covering the same room).

The discriminator for 3 vs 4 is the **area trace** (jumps-and-rises ⇒ transition; flat ⇒
pass-turn). `cleaning_time` step size is never the signal (it's a fixed 30 s clock); the
signal is **gap-timing + the area trace**. Validated in `FORK-FINDINGS.md`
(`segment_internal.py`, `nomop_boundary.py`) and my own CSV trace of the same job.

## 2. Per-room decomposition (what each segment yields)

Segment the post-reset stream by boundaries → contiguous increment-runs = per-room bouts.
Per segment:
- **area Δ** = `cleaning_area` delta = that room's **true area** (exact, no estimation — works
  for multi-room, which Phase 3 couldn't do).
- **time (wall)** = wall-clock span of the bout = the **learnable duration** (NOT the counter
  delta — `cleaning_time` *undercounts* in-room time, 390 s vs 9.64 min). Counter delta stored
  too (active-cleaning time).
- **battery Δ** over the bout.
- **inter-room gap** = wall-clock from this bout's last rise to the next bout's first rise =
  transit (+ wash, in ByRoom).

## 3. Room identity

- **Internal:** segment K → dispatched **queue room K** (certain; `active_cleaning_target` is
  also populated for internal jobs as a cross-check).
- **External (later phase):** identity is hidden by the device → area + return-leg **top-3
  shortlist** (~80%) → **user confirms** → norms-gate. Auto-attribution caps at ~67%.

## 4. Learning-quality gate (the "gold")

Per segment, compare observed **area vs the room's learned expected area** (`room_baselines`
band):
- observed area ≪ expected ⇒ **partial/interrupted clean** ⇒ exclude from **timing** learning
  (its short time would poison the baseline). ~12% of cleans flagged; tightened Kitchen
  stddev **101 → 80 s** on the archive.
- multi-pass room whose area never plateaus-then-holds ⇒ **dropped-pass** flag.
- in-norms ⇒ learn.

This fixes a live bug: today multi-room jobs write `room_cleaning_minutes: null` yet
`used_for_learning: true`, so a good per-room sample is wasted while a light "Quick" pass
rides along ungated.

## 5. Capability-gated geometry (adapter's call — locked constraint)

The bounds/position layer **stays in core**, but **whether to trust it is the adapter's
call**. Core is brand-neutral and never hardcodes "geometry unreliable." It asks the adapter
(e.g. `position_lock_reliable` capability / method); **Eufy answers false** (firmware
re-bases the raw frame every session — no fixed anchor), other brands may answer true. Do not
delete the layer; do not generalize Eufy's failure.

## 6. Reuse vs rebuild (from my Phases 1–5)

| Piece | Disposition |
|---|---|
| Phase 1 `_apply_cleaning_time_sample` (reset-based, cleaning_time only) | **Rebuild** → buffer time-aligned (t, ct, ca, batt) samples + a pure `segment_counters()` |
| Phase 2 job-record blocks (`room_timings`/`transitions`/`transit_capture_valid`/`overhead_observed`) | **Keep + extend** (add per-room `area_m2`, wall time, battery; segmentation confidence) |
| Phase 3 aggregation (`transit_stats`/`access_graph_edges`/ingress-egress/overhead) | **Keep**; now also gets per-room area for multi-room + the area gate |
| Phase 4 estimator (transit fallback chain, `estimated_transit_minutes_before`, `transition_source`) | **Keep**; wire to new per-room data |
| Schema bumps (room_stats 5 / job_stats 4) | **Keep**; may extend |
| Segmentation unit tests | **Rewrite** (reset → counter-plateau); downstream tests mostly keep |

## 7. Contracts

**Capture (core, brand-agnostic).** Buffer one event per counter change into
`active_job["counter_samples"]`, carrying last-seen of the other counter + battery:
`[{t, cleaning_time, cleaning_area, battery}]`. Replaces the incremental segmenter + the
cleaning_area-only sensor write feeding learning.

**Segmenter (pure, testable).** Called on the partial stream (live → tentative
`current_room_id`) and the full stream (finalization → authoritative):
```
segment_counters(samples, *, expected_rooms=None, clean_passes=None,
                 cadence_s=30.0, gap_factor=1.4) -> list[Segment]
Segment = {index, t_start, t_end, area_start, area_end, area_delta_m2,
           time_wall_s, time_active_s, battery_delta, gap_before_s,
           kind: "room"|"job_start", boundary: "reset"|"wash_plateau"|"area_jump"}
```
Internal constraint: expect exactly `expected_rooms-1` area-jump transitions and
`sum(passes-1)` flat-area pass-turns; resolve ambiguity against that budget.

**Gate (reuses learning infra).**
```
gate_segment_for_learning(segment, room_baseline) -> {learn: bool, reason, flags}
```

## 8. Phasing (each wave is an approval checkpoint)

- **Wave 1** — capture rework: buffer counter samples; `segment_counters()` in core; replace
  reset-segmenter. Rewrite segmentation tests. *(Pure/unit — no live-path risk yet.)*
- **Wave 2** — finalization: segment→queue mapping (internal), per-room blocks incl.
  `area_m2`/wall-time/battery + segmentation confidence. Adapt finalizer + history_store.
- **Wave 3** — aggregation + **area-quality gate**: per-room area from multi-room; gate
  partials out of timing learning. Verify the 101→80 s tightening on the archive.
- **Wave 4** — estimator: consume the new per-room data (Phase 4 is mostly there).
- **Wave 5** — capability-gated geometry: adapter `position_lock_reliable`; demote Eufy's
  bounds AND-gate; fold plateau boundary into live `_maybe_roll_current_room_by_timing`.
- **Wave 6 (separate design + UI)** — external-run **ingestion UI is a first-class
  deliverable** (user-flagged): identity can't be auto-resolved (~67% ceiling), so the
  Lovelace card *is* the resolver. Flow: observed-only capture → top-3 shortlist (+full
  list) → **user confirms the room(s) in the card** → norms-gate ingest. Needs backend
  services (capture / list-pending / confirm-ingest) **and** the card confirm flow.

## 9. Test + verification
- Pure-Python unit tests per wave (`pytest tests --no-cov`, 0 warnings).
- Re-segment the real archive jobs; confirm per-room splits sum to job totals (validated:
  Hallway 240 s/6 m² + Kitchen 90 s/2 m² = 330 s/8 m²) and the gate flags ~12%.
- Live: a multi-room ByRoom run + a no-wash run + a 2-pass single-room run (the three cases
  in §1) confirm boundaries and pass-turns.

## 10. Open decisions (need your call before Wave 1)
1. **Scope:** internal per-room + counter-plateau + area-gate now (Waves 1–5); external
   (Wave 6) as a separate design later? *(recommend yes)*
2. **Capture model:** buffer raw counter samples + pure re-segmenter (live + final),
   replacing the incremental reset-segmenter? *(recommend yes — robust, testable, serves both)*
3. **Per-room duration metric:** wall-clock span as the learnable time (counter delta also
   stored)? *(recommend yes — counter undercounts)*
4. **Commit strategy:** commit current Phase 1–5 as a baseline checkpoint first, then rework
   on top; or keep uncommitted and commit the unified result? *(recommend: branch + commit
   baseline for a revert point)*
5. **Coordination:** confirm I own all the shared files now (`active_job.py`,
   `job_finalizer.py`, `history_store.py`, `stats_rebuilder.py`, `estimator.py`) — the other
   agent's work is the design doc + prototypes, done?
