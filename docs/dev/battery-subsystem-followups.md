# Battery subsystem — accounting follow-ups

Two tracked items surfaced 2026-06-20 while reviewing `battery/` against a **mid-job
recharge run** (an external Vac+Mop clean that returned to dock at 9% and recharged).
Neither is a bug in the real-time session engine — cycle counting, charge-session
tracking, the CC/CV regime split, the per-install health proxy, and the gold-standard
`mid_job_recharge_stats` all handle a recharge correctly. Both items are about the
**per-job drain metric** (`battery/job_metrics.py` → fed by `learning/job_finalizer.py`).

Context: the session engine (`battery/manager.py`, `BatteryHealthManager`) watches the
battery *sensor* and is job-type-agnostic, so charge/cycle/health data is captured for any
run. The per-job *drain* metric is a separate, dispatched-run-only path — that's where both
gaps live.

---

## Item 1 — per-job drain is recharge-naive (biases dispatched recharge runs low)

**Where:** `learning/job_finalizer.py:770` calls
`compute_job_battery_metrics(battery_start=…, battery_end=…)` with the raw job-edge battery
levels. `battery/job_metrics.py:_safe_drain` computes `drain = start − end`.

**Symptom:** on a job with a mid-job recharge, `start − end` **nets out the recharge**, so
`battery_used_pct`, `drain_per_min`, `drain_per_hour`, and `drain_per_m2` understate the true
discharge. Example: 100 → 9 (drained 91), recharge to 80, finish at 50 → reported drain 50,
true discharge ≈ 121.

**Why it matters:** `BatteryHealthManager.record_job_metrics` feeds **single-bucket** jobs
(`is_single_clean_mode/fan_speed/water_level`) into the `by_clean_mode` / `by_fan_speed` /
`by_water_level` drain aggregates, with **no `mid_job_recharge` gate**. A single-setting
recharge run (e.g. Vac+Mop / Turbo / Low water) therefore injects an understated drain into
those per-config means and biases them low. Note the asymmetry: **duration IS
recharge-adjusted** (recharge seconds are booked as overhead, `job_finalizer.py` ~line 502),
but **drain is not** — so `drain_per_min` is wrong in both numerator and denominator-relative
terms.

**Fix options:**
- **(a) Gate it out (simplest, mirrors the existing anti-bias design).** When the job had a
  mid-job recharge (`battery.mid_job_recharge_observed` / `recharge_seconds_accumulated > 0`),
  exclude it from the per-job drain aggregates — same spirit as the `is_single_*` gates that
  already keep mixed-mode jobs out of per-bucket drain. The job still records `last_job`; it
  just doesn't pollute the means.
- **(b) Compute true drain (more complete).** Source the per-job discharge from the session
  engine's `cumulative_drain_pct` delta over the job window — it already sums *only* drops
  across the recharge, so it's the true discharge by construction. Then the aggregate is both
  correct AND keeps the recharge run as a data point.

**Recommendation:** (a) now (cheap, honest), (b) later if recharge runs become common enough
that dropping them loses meaningful coverage.

---

## Item 2 — external (app-started) runs compute no per-job battery metrics

**Where:** `learning/external_ingest.py` has **zero** battery references;
`build_graduated_job` emits no `battery` / `battery_metrics` block.

**Symptom:** `drain_per_m2` and the per-config drain aggregates only ever build from
**dispatched** (integration-started) runs. An app-started clean contributes nothing to the
per-job drain picture — so tonight's external run produces no per-job drain number at all.

**Why it matters:** if most cleans are app-started, the per-config drain aggregates stay
sparse / slow to converge. (The charge/cycle/health side is unaffected — the session engine
captures it regardless of job type, and the raw per-sample JSONL has the full discharge
curve, so the *true* discharge rate is always recoverable from the archive.)

**Likely intentional, but worth a decision:** external runs lack a reliable dispatched
`battery_start` / `battery_end` capture. Options:
- Capture `battery_start` / `battery_end` for external runs from the **recorder battery
  timeline** at the run-window edges (and fold in recharge per Item 1) so external runs feed
  the same per-config aggregates.
- Or explicitly **document** that per-job battery drain is a dispatched-run-only metric, and
  point users at the raw battery JSONL / session stats for external-run battery insight.

---

## Not affected (captured correctly regardless)

- **Cycle counter** — `cumulative_drain_pct` sums only drops; charging never decrements.
- **Charge-rate / zone / CC-CV / health** — driven by the battery sensor via charge sessions.
- **`mid_job_recharge_stats`** — a mid-job recharge from a deep low is the engine's
  gold-standard signal; a 9 → ≥90 recharge also spans both CC and CV, so it can seed/refresh
  the per-install health baseline.
- **Raw archive** — `battery/store.py` writes a per-sample JSONL + `sessions.csv`, so the true
  discharge (e.g. 100 → 9) and the charge curve are always reconstructable post-hoc.
