# Eufy native current-room transition detection (hybrid)

**Status:** design proposed 2026-06-19; **Wave 0 validation CAPTURED 2026-06-20.** The freshness gate
**PASSED** (signal is live server-side with the map tab fully closed), and a **blind** room-attribution
test **recovered the exact cleaned set (3/3, precision = recall = 1.0)** on a deliberately adversarial
external run — dock-trap avoided, tiny-room floor caught. Direction approved (hybrid: native-primary +
heuristic fallback). **All three adversarial cases PASSED — 9/9 cleaned-room calls, 0 false positives** across:
dock-trap (room 8 excluded when parked), dock-room-cleaned (room 8 included when cleaned, parked↔cleaned
flip on spread), tiny-room floor (1 m² / 30 s), and the **interleaved mop-wash** "vicious" run
(3-way cross-check: probe ↔ record ↔ device history; **cleaned-area** confirmed as the wash/clean
tiebreaker). **Still APPROVAL PAUSE on runtime code:** the meanest realistic cases held, so what remains
before code is to **formalize the dwell + spread + winding + cleaned-area rule with the validated
thresholds** (and re-confirm the file:line anchors). See
[Wave 0 results](#wave-0--the-validation-gate-captured-2026-06-20). Anchors below are *as-investigated*
and must be re-confirmed at implementation time (verify-vs-code rule).

## The question

Eufy now exposes a per-frame `current_room` (read from the eufy-clean fork's in-memory `MapData`,
surfaced on the map-overlays sensor). Historically Eufy had no native current-room, so run-time
room-transition detection used the **counter-plateau / timing heuristic** (`eufy_counter_v1`).
Roborock instead gets a **native** rollover via the brand-agnostic `live_transition` seam. Can
Eufy's `current_room` now drive transition detection through that same seam?

## Verdict

**Yes — with caveats — via the EXISTING `live_transition.native_transition_source` seam.** The seam
has zero brand-specific engine code, so an Eufy adapter could in principle ride the same
`_maybe_roll_current_room_by_native_signal` path Roborock uses. **But the signal is the wrong shape
today, and it is itself an inference** — so the answer is a *hybrid*, not a flag flip.

Two facts shape the whole design:

1. **Shape mismatch.** The seam consumes a live room-**NAME** entity (slug-matched to job targets,
   `_resolve_native_target_room_id` at `jobs/active_job.py:883-929`) wired as
   `entities.active_cleaning_target`. Eufy's `current_room` is an inferred raster-lookup room **ID**
   (`mapping/map_source.py:231-260`, surfaced at `sensor/map_overlays.py:72-84`), and Eufy already
   uses `active_cleaning_target` as a completion **sentinel** (`adapters/eufy/adapter.py:353`). So a
   name-surfacing + slug-reconciliation shim and a completion-path migration are prerequisites.
2. **It's inference, not an upstream signal.** Our "prefer dedicated upstream signals over inferred
   state" principle would push native-only — but Eufy's `current_room` is a raster lookup *we*
   compute, not a device field. It is a better-grounded inference than counter-plateau, yet it goes
   **blind (`None`)** exactly when the robot is between rooms or docked. That is precisely where the
   heuristic must remain as a fallback.

## The seam (existing, brand-agnostic)

Three collaborators (`jobs/active_job.py:596-708`):

- `live_transition.native_transition_source: True` — Eufy is currently `False` (`adapters/eufy/adapter.py:632`).
- `entities.active_cleaning_target` → a **live room-NAME** sensor.
- the ~5s tick caller `_maybe_roll_current_room_by_timing` (`core/manager.py:3111`), which
  short-circuits into the native branch when the flag is set (`jobs/active_job.py:701-708`).

Native rollover logic is **order-agnostic and idempotent** (`jobs/active_job.py:931-1001`):
first-confirmed target is *adopted* with no completion (queue order was a guess); a move to a
different target *completes only the previously-confirmed* target; same-target is a no-op. Unknown /
transit / non-job-target names resolve to `None` and are ignored (`:931`) — this is the built-in
transit + dock filter. Roborock proves coordinate drift is irrelevant here: its rollover is
purely name-driven and uses no position/bounds (`position_lock_reliable` is also `False`).

Sequenced/strict-order jobs bypass both paths (`jobs/active_job.py:687-688`) and instead read the
same native signal through the phase watchdog's `native_current_room_target_id` accessor
(`core/manager.py:4954`).

**Dock-start phantom is already handled (not a new edge case).** When the dock sits *inside a queued
room*, `current_room` reads that room while parked, then changes as the robot leaves — naively
"completing" a room that was never cleaned. This is documented + tested: `NR-10` (sequenced jobs no-op
the live rollover via the phases guard, `:687`) and `NR-4` (the first confirmed signal is *adopted*
with **no** completion). Eufy inherits both by riding the seam; we just mirror those cases in the Eufy
contract tests (shim #6). Confirmed empirically in Wave 0 — the dock room was *seen* but correctly not
attributed (see below).

## The hybrid design

**Native-primary, heuristic-fallback, gated on availability + an N-frame settle.**

- When `current_room` resolves to a confirmed job-target name **and** has held for **N consecutive
  ticks**, the native path completes/advances.
- When it is `None` / stale / off-map / docked, fall back to the dormant `eufy_counter_v1`
  counter-plateau engine (kept wired at `adapters/eufy/adapter.py:613`, `counter_segmentation.py`).
- The settle requirement replaces the smoothing the plateau logic gave for free — the native
  rollover path has **no debounce of its own** (settle/verify/retry lives only in the strict-order
  phase watchdog, `core/manager.py:4835-4988`, not in grouped-job rollover).

This captures most of the better-grounded-signal win while the heuristic covers the inference's
blind spots.

## Prerequisite shims

| # | Shim | Why | Anchor |
|---|---|---|---|
| 1 | Live current-room-**NAME** sensor (rid → `room.number` → managed name, slug-reconciled) | seam matches by slug, not id | `mapping/map_source.py:201,:259`, `sensor/map_overlays.py:82` |
| 2 | Migrate Eufy completion off the `active_cleaning_target` sentinel → adopt `require_job_active_clear: True` | frees the entity to carry the live name (Roborock's approach) | `adapters/eufy/adapter.py:353`, `adapters/roborock/adapter.py:201` |
| 3 | **Server-side** refresh of the rid/name during a run, independent of the map tab | the 2s freshness is UI-poll-coupled (`src/cards/main.js:600-625`) and does NOT run when the tab is backgrounded | new periodic task |
| 4 | N-frame settle on the native rollover for non-phased jobs | no built-in debounce; doorway cells can flicker the rid for one frame | `jobs/active_job.py:931-1001` |
| 5 | Re-map reconciliation: re-resolve rid→name when the raster version changes | rid raster is content-versioned (`eufy_version_of`, sha1) | `mapping/map_source.py:449-456`, cf. `adapters/roborock/adapter.py:274` |
| 6 | Contract tests mirroring `NR-1..NR-11` for the Eufy adapter | parity with Roborock's native-rollover suite | `tests/integration/test_native_rollover.py` |

The flag flip + per-room-live-settings reuse are nearly free; shims 1–4 are the real work.

## Wave 0 — the validation gate (CAPTURED 2026-06-20)

**Instrumentation:** throwaway server-side service `eufy_vacuum.debug_log_live_room` (in
`mapping/mapping_services.py`, REMOVE after validation) — resolves the live pose every 2s via the same
`async_get_map_live_pose` path and logs `{t, current_room, robot_docked, robot_anchor, …}` to
`config/eufy_current_room_probe_<vacuum>.jsonl`, with **no card open**. Two runs captured on
`vacuum.alfred`: a 2-room dispatched run + a deliberately adversarial 3-room external run.

**Result — the gate PASSED on all three numbers:**
1. **Refresh server-side, card closed: YES.** 351 distinct anchors / 375 consecutive changes over the
   external run — the fork pushes pose via MQTT independent of any UI poll. So **shim #3 may be
   unnecessary** (the signal is already live without us driving it). *Caveat:* no in-repo proof the
   `_robot_pixel` frame is stable mid-run; observed-only.
2. **Flicker: 0 single-tick room blips** on the dispatched run; on the external run the only 1-tick
   blips were `None`/transit cells and **post-dock previous-room flashes**, all filtered by dwell.
3. **`None`-while-cleaning: 0%.** The signal never went blind through either run, even across a 43 s
   inter-room transit.

**Decisive headline — blind room attribution recovered the exact cleaned set.** From `current_room`
alone (no labels), classifying each room the signal saw by **dwell + anchor spread + path-winding**,
the predicted cleaned set `{2, 4, 6}` matched the ground-truth external job record exactly:

| Room | Name / area | Signal | Verdict |
|---|---|---|---|
| 4 | Hallway 6 m² | dwell 118 s, spread 0.069, winding 126 | CLEANED ✓ |
| 2 | Bathroom 2 m² | dwell 110 s, spread 0.054, winding 31 | CLEANED ✓ |
| 6 | Entryway **1 m²** | dwell 46 s, spread 0.026, winding 5.2 | CLEANED ✓ (tiny floor) |
| 8 | Dining (dock) | dwell **271 s** (longest!), spread **0.015** | dock — correctly NOT attributed |
| 7 | — | 8× ~16 s, winding ~1.2 | transit hallway — not attributed |

The two hard cases both broke right: the **dock trap** (room 8 had the *longest dwell of the whole run*
and would be the #1 false positive on dwell alone — only its **low spread** excluded it) and the
**tiny-room floor** (entryway, 1 m², ~60 s clean — cleared the transit band: min-cleaned 46 s vs
max-transit 18 s, a 28 s gap).

**Caveats (why the gate isn't fully closed):**
- **n=1 per pattern** (2 runs). Thresholds were *interpreted on this data*, not pre-registered.
- **The naïve auto-classifier mis-included the dock** (room 8) on dwell; the **spread-rescue** rule is
  what excluded it. So the signal *contains* enough to be exact, but the rule (dwell + spread + winding,
  with a dock spread-rescue) must be **formalized and re-validated** before it runs unsupervised.
- ~~**Dock-room-*cleaned* is untested.**~~ **CLOSED 2026-06-20 (run #2, dock-room-first).** Dining
  (room 8, the dock room) was cleaned first; the classifier flipped it **parked→cleaned** correctly on
  spread alone: **cleaned-dock spread 0.073** (one contiguous park+clean run, cleaning dominates) vs
  **parked-dock ~0.015–0.016** (last run + this run's end park) — a ~4.5× gap, same physical room,
  both directions correct. Blind prediction `{2, 6, 8}` = ground truth exactly (precision = recall = 1.0).
  The **max-spread-per-run** aggregation was validated (room 8 had both a cleaned run and a park run;
  max picked the clean). Combined **6/6** cleaned-room calls across the two adversarial external runs,
  0 false positives. (then 6/6.)
- **Interleaved mop-wash (the "vicious" case): PASSED 2026-06-20 (run #3) — now 9/9 across all three
  adversarial runs, 0 false positives.** Kitchen(mop)→Dining(vacuum, the dock room)→Hallway(vacuum+mop)
  with mid-run washes; blind `{4,5,8}` = ground truth. Room 8 had **5 runs**; **max-spread-per-run**
  picked the dining clean (spread 0.071) out of the start-wash/early-clean/clean+folded-wash/park/
  final-wash pile. A **three-way cross-check** — probe `current_room` ↔ finalized record ↔ device-history
  CSV — all agreed. **Cleaned-area (`sensor.*_cleaning_area`) validated as the wash/clean tiebreaker:**
  swept m² accrues during cleans (kitchen ~2, dining ~8, hallway ~2) and is **FLAT during the wash**
  (03:44–03:46, `vacuum=docked`/`dock=Washing`, 0 m² added) — separating "washing in the dock room" from
  "cleaning the dock room" when spread can't (same room id, contiguous). Measured (not assumed): the
  device does **NOT** wash on every mode switch (no wash between kitchen-mop and dining-vacuum) — real
  cadence ≠ predicted. And `sensor.*_active_cleaning_target` stayed **`None`** the whole external run →
  the in-job seam's name-signal is unavailable for app cleans, so external runs **must** use this
  classifier (→ W5), not the seam. **Set attribution is robust on dwell+spread+winding; *time*
  attribution needs cleaned-area to subtract the folded wash (run 5 = ~600s clean + ~170s wash).**

## External-run auto-attribution (first-class consumer — validated)

The headline use is **not just** the in-job rollover. An app-started (external) clean has no
dispatched queue, so the integration can't anchor to targets — today it leans on the counter-plateau
heuristic + a manual room-set step in the external-capture wizard. The Wave 0 external run was exactly
this case, and `current_room` recovered the cleaned rooms **exactly** (3/3) — so it can **auto-attribute
external runs** instead of inferring/asking. Treated here as a first-class consumer, built to the same
bar (rare-use is no reason to half-build it; and it rides the same signal as the in-job rollover, so
it's cheap to add).

Two concrete wins seen in the data:
- The external job record logged **`transitions: []`** — the capture system recorded *zero*
  transitions — while `current_room` captured the full device path (`8→7→4→…→2→…→6→8`) with clean
  handoffs. So the native signal **adds path/transition data the capture system doesn't have today.**
- The dwell+spread+winding classifier separated the 3 cleaned rooms from the dock + transit rooms with
  clean margins (see the Wave 0 table).

**The classification rule — FORMALIZED 2026-06-20** (`scratch-external-estimator/room_attribution.py`
+ `test_room_attribution.py`, a pure-Python prototype with the 3 runs as regression fixtures):
1. Segment by `current_room` into contiguous runs; per run compute dwell, anchor spread (RMS),
   path-winding (`path_len / net_disp`), bbox area.
2. **Drop TRANSIT by winding** — a run with winding < ~1.5 is a straight pass-through (transit
   rooms measured 1.0–1.22; cleaned rooms ≥ 4.9). Robust across all 3 runs.
3. **Cleaned vs parked-dock by SWEPT AREA** — `sensor.<vac>_cleaning_area` delta over the room's
   windows ≥ ~0.5 m² ⇒ cleaned; a wash/park sweeps ~0 m². Aggregate per room by its best run
   (NOT total dwell).

**KEY FINDING the formalization surfaced — swept-area is REQUIRED, not optional.** The anchor-only
signals (dwell + spread + winding) **cannot** separate a *jittering parked dock* from a clean: in
run #1, room 8 (parked) sits inside the cleaned cluster on every anchor axis (dwell 271 s, winding 43,
spread 0.028 — all ≥ the cleaned tiny rooms). The harness proves it — **anchor-only = 9/9 recall but
1 false positive** (the parked dock leaks through); the live "9/9" had silently patched that with
manual judgment on that exact room. **Area-augmented = 9/9, 0 FP.** So the earlier "spread-rescue"
framing was not robust; the device swept-area is the load-bearing clean/parked separator. (The probe
`debug_log_live_room` now logs `cleaning_area` + `task_status`/`dock_status` so future runs carry it
natively.) Distinct from the in-job seam (job-target slug match, unavailable for external runs), this
is a **segment-by-current_room + swept-area** classifier — the role the counter-plateau heuristic
plays today, but grounded in observed position + device area.

## Waves (post-gate, pending approval)

- **W0.5** — DONE: all adversarial runs captured + the rule **formalized** with regression fixtures
  (`scratch-external-estimator/`). Outstanding: the probe now logs `cleaning_area`, so capture a couple
  more runs to re-validate the **area-augmented** rule end-to-end (the anchor-only fixtures used the
  record's per-room area as a stand-in for runs #1/#2; run #3 was device-verified).
- **W1** — shim #1 (name sensor) + shim #2 (completion migration), with tests. No behavior change yet.
- **W2** — shim #3 (server-side run-time refresh) **only if W0.5 contradicts** the "already-live" finding.
- **W3** — flip `native_transition_source` + shim #4 (settle) + availability fallback gate; `NR`-parity tests.
- **W4** — strict-order path via `native_current_room_target_id` + shim #5 (re-map reconciliation).
- **W5** — external-run auto-attribution (chosen first; planned by the w5-external-attribution-plan
  workflow). Wires the classifier into the external-capture path to auto-derive cleaned rooms, gated
  on a confidence check with the manual wizard as fallback. Sliced:
  - **W5a — DONE 2026-06-20.** Ported the classifier to a pluggable engine
    `learning/room_attribution_engines.py` (`eufy_anchor_winding_v1`, mirrors the `job_segmenter`
    seam: Protocol + by-ref `DEFAULT_TUNING` + Eufy-fallback registry); added the swept-area-from-
    `cleaning_area`-timeline derivation the prototype received pre-aligned; declared the adapter
    `room_attribution` block (`adapters/eufy/adapter.py`) + registry validation. **Ships DORMANT** —
    no consumer yet. Tests: `tests/unit/test_room_attribution_engines.py` (RA-1..10, seam) +
    `tests/adapters/eufy/test_room_attribution.py` (the 3 adversarial runs, 9/9 area + the anchor-only
    dock false-positive + a synthetic full-pipeline). Full suite green (2527).
  - **W5b — DONE 2026-06-20 (built + adversarially reviewed).** Run-active sampler
    `listeners/pose_sampler.py` (cadence + gating from the adapter's `room_attribution` block;
    EXTERNAL-only; `map_state_source`-gated) appends `{current_room, anchor, cleaning_area}` to
    `pose_samples` via `record_pose_sample` (`jobs/active_job.py`). **Capture-only/inert.** The
    review caught + fixed: a real robust-mode false-negative (swept-area is now authoritative over
    the winding drop), docked-tick buffer poisoning (sampler nulls `current_room`/`anchor` on
    `robot_docked` → a parked dock is a genuine None-run), and an adapter-discipline miss
    (`cleaning_area` now read from `entities.cleaning_area`, not a guessed name). Tests:
    `tests/unit/test_pose_sampler.py` + `record_pose_sample` cases in `test_jobs_active_job.py`;
    full suite green (2543).
  - **W5b live experiment — DONE 2026-06-20, PASS.** One real 5-room external clean on
    `vacuum.alfred` (rooms 5,6,7,8,9; 404 sampler ticks / 13.5 min), sampler + throwaway probe both
    capturing. Diff (`scratch-external-estimator/w5b_diff.py`, time-aligned on overlap): **freshness**
    nearest-probe \|dt\| median 1.0s = pure 2s-cadence phase, no staleness; **frame** anchor coord
    ranges identical and coincident-tick (\|dt\|≤0.6s, n=120) anchor distance median 0.000 — the
    sampler reads the *same live value* as the probe, so anchor-unit thresholds port directly;
    **transitions** macro room-sequence matches the probe, the 7 disagreements (98.3% agree) are all
    1-tick flickers / ~1s boundary phase present on BOTH sides (no systematic lag). Preserved native
    fixture: `scratch-external-estimator/w5b_live_pose_samples.json`. **Notable:** this run's
    counter-plateau finalize wrote NO record (`build_pending_record → None`, 25 counter samples, no
    plateaus) and the slot was cleared `external→idle` on normal completion — `pose_samples` must be
    read out of `.storage` before that reset (they're dropped from the record AND wiped). Recorder
    ground truth: cleaning 08:13:11 → returning 08:23:44 → docked/`Completed` 08:24:40 (a clean finalize,
    NOT premature — an early probe-flag-based "premature finalize" read was wrong; the probe's
    `robot_docked` stayed `False` through the real dock).
  - **W5c previewed on the real samples** (`scratch-external-estimator/w5b_attribute_real.py`, the
    engine run directly on the 404 native ticks): `mode=robust`, `cleaned=[5 (kitchen, 6 m²),
    9 (~2 m²)]`. **The win:** room 8 (the dock room) had the MOST presence of any room — 100 ticks /
    200 s — but **0.0 m² swept → `parked/dock`, not cleaned.** Hard version of the trap: the pose source
    reported the parked robot as "moving in room 8" the whole time (`robot_docked` never flipped) AND
    `cleaning_area` was non-monotonic (stale 16 → reset → 10); the positive-delta swept logic absorbed
    both. Counter-segmentation found nothing here → argues W5c should let the pose path stand up a
    record on its own, not only enrich a counter-segmented one. (cleaned set still wants the user's
    ground truth of what the app actually cleaned.)
  - **Refinement W5c must carry — docked-gate signal.** The sampler's F2 docked-nulling keys off the
    pose source's `robot_docked`, which is UNRELIABLE (stayed `False` through the 08:24:40 dock → the
    null path never fired; 100 dock/return ticks were recorded as room 8 and only swept-area excluded
    them). Gate docked-nulling on the MQTT-backed `task_status`/vacuum state instead
    (`Returning`/`Completed`/`docked`/`Charging` — these flipped cleanly and on-time), so the
    parked-dock exclusion has an independent reliable signal and doesn't lean solely on swept-area
    (which itself can be flaky, as `cleaning_area` was here).
  - **W5c — DONE 2026-06-20 (built + adversarially reviewed).** Pose attribution wired into the
    external-run finalize, backend-only (the card already auto-selects `shortlist[0]`, so promoting
    the classified room there pre-answers the wizard with NO frontend change):
    - `learning/external_ingest.py`: `_resolve_attribution`/`_attribute` (engine + tuning from the
      adapter's `room_attribution` block, Eufy fallback — mirrors `_resolve_engine_tuning`);
      `_apply_pose_identity` + `_dominant_cleaned_room` + `_promote_pose_room` ENRICH each counter
      segment with its dominant cleaned room → `shortlist[0]` (ROBUST mode only — anchor-only can
      false-positive a parked dock, so it doesn't override the settings shortlist); `build_attributed_job`
      STANDS UP a pose-only record when the counter segmenter finds nothing (the common app-run case —
      this morning's run produced no counter record). `build_pending_record` gained a `pose_samples`
      param; `attribution_mode` is stamped on the record for the card.
    - `listeners/pose_sampler.py`: `_is_parked` — the docked-gate now reads the MQTT `task_status` vs
      the adapter's `vocabulary.active_run_task_states` (reliable), falling back to the pose
      `robot_docked` flag only when task_status can't be read (the F2-via-MQTT refinement above).
    - `core/manager.py`: `_finalize_external_run` passes `slot["pose_samples"]` through and now ALWAYS
      clears the slot (try/finally) so a build error can't orphan a `status="external"` zombie.
    - **Hybrid gate:** no pose stream / empty cleaned set → `attribution` is None → exactly pre-W5c
      behavior (availability fallback). robust vs anchor_only rides `attribution_mode`.
    - **Adversarial review (16 agents):** 5 findings survived refutation; only one was a real fix —
      an uncaught `engine.attribute()` exception that dropped the run AND orphaned the slot. FIXED:
      `_attribute` degrades to counter-only on engine error + the finalize try/finally always clears.
      The other 4 were verified-but-inert (dead `gap_transit_s` field, missing `source` label on enrich
      records, pose metadata lost on re-segment, unreachable out-of-order `wall_s`) — documented, no
      change. Tests: `tests/unit/test_external_ingest_attribution.py`, `test_pose_sampler.py` (MQTT
      gate incl. the exact live failure), `tests/integration/test_manager_external_finalize.py`
      (EXT-FIN-2 pose-only finalize, EXT-FIN-3 slot-clears-on-error). Full suite 2559 pass / 1 skip.
  - **W5d (later)** — opt-in auto-confirm for proven high-confidence robust runs.

  **W5 gating + adapter discipline.** The native path rides `current_room`, which is *derived from
  map data* (`current_room_for_pixel` over the fork's in-memory `MapData` raster — `map_source.py:231`;
  no map → `async_get_map_live_pose` returns `{present:false, reason:"no_geom"}`, `manager.py:4153`).
  So: no map → `current_room` is `None` → the engine returns an empty cleaned set → **W5c's
  availability gate falls back to today's manual wizard** (and the in-job track falls back to the
  map-independent counter-plateau heuristic). W5 is therefore **purely additive** — with the live map
  you get the native signal, without it you get exactly today's behavior. Two consequences for the
  build:
  - **W5b's sampler gates on `map_state_source` presence** — don't sample pose for a vacuum with no
    live map (the rows would be all-`None`).
  - **All brand settings stay in the adapter.** The engine choice, the thresholds
    (`wind_transit`/`dwell_min_s`/`swept_area_min_m2`), and the **sampler `interval_s`** (which the
    `dwell_min_s` tuning assumes) all come from the adapter's `room_attribution` block — the single
    operative source, mirroring `job_segmenter.tuning`. Core `listeners/` + `external_ingest` read
    those (resolved via a helper like `_resolve_engine_tuning`); they must **never hardcode** the
    cadence or thresholds. Same rule for the W5c confidence/availability gate values.

## Open unknowns (honest)

- No in-code assertion that the live `_robot_pixel` frame is stable mid-run — inferred from fork
  behavior, not proven here (`mapping/map_source.py:407-415`).
- Device→fork→render latency rides on top of our freshness guarantee and is outside this repo; the
  seam's idempotency absorbs a coarse cadence, but the settle value (N) must come from W0 data.

## Related

- `docs/dev/map-state-source.md` — where the rid signal comes from.
- `docs/dev/29-roborock-adapter.md` — the native-rollover precedent.
- `docs/dev/06-job-lifecycle.md` — the rollover tick + phase model.
- memory: `reference_eufy_intersession_coord_drift`, `project_room_segmentation_unified`,
  `feedback_kiss_upstream_signals`, `feedback_archive_cheap_raw_data`,
  `feedback_quality_not_gated_by_usage` (why external-run auto-attribution is first-class despite rare use).
