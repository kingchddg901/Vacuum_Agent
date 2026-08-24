# 16 — The Battery Record

**Scope.** Two evidence streams meeting in one per-vacuum record under
`battery.vacuums.<vacuum_entity_id>`, the four questions they answer between them, the twelve
sensors that publish the answers, and two raw files on disk that nothing reads back.

The package is brand-neutral core. Which entity carries the level and which carries the
charging flag both come from `adapters/registry.py::get_adapter_config`; the only Eufy string
in the subsystem is a fallback entity id used when an adapter has not registered yet.

---

## 1. Two evidence streams, one record

Battery answers four questions, and they do not come from one place. **Two independent feeds
enter through different doors, on different threads, and meet in the record.**

The **live stream** is a `(level, charging, timestamp)` triple taken whenever either the
battery entity or the vacuum entity fires a state change. It enters at
`battery/manager.py::BatteryHealthManager._process_sample`, on the event loop.

The **completed-job stream** enters at `battery/manager.py::BatteryHealthManager.record_job_metrics`,
from the JobFinalizer's executor pool. `battery/job_metrics.py::compute_job_battery_metrics`
never consults the sampler: it takes `battery_start`, `battery_end`, `duration_minutes`,
`cleaning_area_m2` and `resolved_rooms` from the completed-job payload, and attributes across
rooms using learning estimates.

| question | stream | derived from |
|---|---|---|
| how much has the pack cumulatively drained | live | negative deltas |
| how does it charge | live | positive deltas |
| how does this charge compare with the install baseline | live | a whole qualifying session |
| what did one dispatched run cost | completed job | the job payload's own readings |

**The two feeds observe the same battery and never each other.** That is why a mid-job recharge
makes `end > start` in the job payload — yielding a `None` drain and a run that counts toward no
mean — while the sampler's cycle counter, which sums negative deltas only, is untouched by the
same event. It is also why the threading differs at each door: `_process_sample` is already on
the loop and pushes file I/O out to the executor, while `_schedule_save` arrives from a worker
thread and must post back with `run_coroutine_threadsafe`.

**Only the session lifecycle consults `charging` at all.** Rates come from a positive battery
delta, cycles from a negative one — so on an adapter that declares no `entities.charging`,
`core/charging.py::is_charging` returns False forever and the subsystem stays *partly* alive:
cycles, cumulative drain and all three rate stats keep accumulating, while no session ever
opens and there is therefore no session history, no CSV row, no regime attribution, no
baseline and no health figure. The inverse also follows — firmware that reports a rising level
off-dock feeds the rate stats.

**Every sample with a valid level ends in an immediate full-store disk write.**
`battery/manager.py::BatteryHealthManager._process_sample` returns early only when the level is
`None` or outside 0–100; every other path reaches `_schedule_save`, which calls
`core/manager.py::EufyVacuumManager.async_save` → `core/storage.py::EufyVacuumStorage.async_save`,
documented as *"Save stored data immediately."*

> ⚠ **The debounced save path exists and this subsystem does not use it.**
> `core/manager.py::EufyVacuumManager.async_save_delayed` is the coalescing one. Both the module
> docstring ("benefits from the existing debounced save loop") and `_schedule_save`'s own
> ("rapid-fire calls just coalesce in the storage layer") describe a mechanism on the other
> method. Anyone sizing write amplification, or deciding whether one more `_schedule_save` call
> is cheap, is told the wrong thing by the two comments written to answer that question.

### The record is repaired forward, never migrated

`battery/manager.py::BatteryHealthManager.ensure_record` setdefaults missing keys at the top
level and inside `stats` and `baseline`. **It does not descend into `job_aggregates`**, and
there is no storage migration for the battery slice. A key added to a bucket schema therefore
starts at zero on an existing install while its older siblings keep every value they have
accumulated — see §5.

---

## 2. What counts as a datum

Three independent guards reject samples, by three different criteria, with three deliberately
different downstream reaches. The asymmetry is the design; it is spread across one long
function and is the single hardest thing here to see from the code.

| guard | rejects by | what still happens |
|---|---|---|
| `MAX_DELTA_PCT` (3.0, inclusive) | magnitude of the level change | anchor advances; session lifecycle runs; magnitude parked in `rejected_delta_pct` |
| `MAX_RATE_INTERVAL_SEC` | gap since the last sample | delta and cycles still count; only the rate is dropped |
| `MAX_PLAUSIBLE_RATE_PCT_PER_MIN` (2.5) | the computed rate's value | delta and cycles still count; **every** charging derivative for that interval is lost |
| out-of-order (`elapsed_sec <= 0`) | timestamp order | session lifecycle still runs; only two anchor fields are withheld |

**The implausible-rate artefact is caught by VALUE, not by a minimum interval floor at source.**
Because the battery reports whole percent, a single 1% tick 18 s after the previous sample reads
as 3.33 %/min no matter what the pack is doing — on a dock measured at roughly 0.45 %/min. An
interval floor was the obvious alternative and it does not work, because the device's own
cadence is what produces the short interval.

A rate rejected here costs more than the rate. Everything downstream sits under
`if rate_per_min is not None`: the three record-level rate stats, the session's zone
accumulators, and the whole CC/CV attribution block. The rejected figure is parked in
`stats.rejected_rate_per_min`, which nothing reads and nothing — including `rebaseline` — ever
clears.

### The out-of-order guard holds two fields, and says so

`elapsed_sec <= 0` withholds `last_battery_level` and `last_sample_ts` only. `_update_session`
has already run, and `last_charging` is written unconditionally on the next line, so a stale
sample can still **open or close** a charge session carrying its own stale timestamp and level.
That can write a `session_history_recent` entry, and a `sessions.csv` row, whose `end_ts`
precedes its own `start_ts`. Nothing repairs those.

This is the registered, accepted violation of `IN3ASEP8` — *a rejected datum is rejected for
every purpose* — not an example of it. It is left open on evidence rather than oversight:
`elapsed_sec <= 0` requires the wall clock to step backwards, because the timestamp is minted
per-sample and never inherited from a state object, so two co-timed samples cannot collide.

**Closing half of it is worse than closing neither.** Moving `_update_session` inside the guard
without `last_charging` makes every repeated stale sample re-open the session; moving
`last_charging` without `_update_session` makes the next genuine sample see a false transition
and restart a live one.

> ⚠ **A scan of `samples.jsonl` for backwards time returns hits, and they are not clock steps.**
> `battery/store.py::append_sample` is dispatched to the executor pool without awaiting, so two
> closely-spaced samples can land in the file in the opposite order they were taken. Measured on
> the live archive: 79 inversions in 2,194 samples, every one between 0.16 ms and 15.9 ms. The
> discriminator is magnitude — thread-pool jitter is sub-100 ms, a real clock step is seconds.
> Anything sequential over `samples.jsonl` must sort by `ts` first.

### Charge ETA

`compute_time_to_target_pct` prices the remaining span in three tiers: the open session's own
zone accumulators, then the cross-session `stats.rate_*_zone_per_min`, then the baseline.

**Tier 2 is skipped entirely when a session is open but has not yet produced its own sample for
that zone** — rather than divided against. A cold start returns `{minutes: None, source: None}`
and the caller shows a live wall-clock "charging…" instead of a fabricated ETA; it self-heals
within a sample or two as the accumulators fill. `source` reads `baseline` only when *every*
span used the baseline, because the informative half of that answer for the card is whether the
estimate is still anchored to a frozen reading.

> ⚠ `_span_minutes` resolves tier 2 as `stats.get(zone_key) or stats.get("rate_overall_per_min")`.
> When the zone stat is absent it falls back to the unzoned rate, so a CV span can be priced off
> a rate measured in the CC region — understating the taper. The docstring names only the zone key.

---

## 3. Charge sessions, and the third close that destroys

A session opens when `charging` goes true, and closes when charging goes false or the level
reaches 100. A third path ends a session without closing it.

**`SESSION_MAX_HOURS` (12) discards.** `_update_session` sets `current_session = None` directly,
logs *"discarding stale session"*, and never calls `_close_session` — so no summary is built,
no `sessions.csv` row is written, nothing reaches `session_history_recent`, and no health
sample is produced. The local variable is named `session_was_discarded`.

The consequence lands where it is least wanted: a genuinely long charge — a deeply drained pack
on a slow dock, or a charging sensor stuck on while docked — is exactly the kind of session a
health proxy wants, and it contributes nothing. `DR-BAT-3` then re-opens a new session on the
next sample (`if charging and (not prev_charging or session_was_discarded)`) whose
`start_battery` is the *current* level, so the replacement will usually fail
`_session_cc_qualifies`, which needs a start at or below 50.

**Session kind is decided at open time and never revisited.** `_classify_session_kind` asks
whether a job is in flight; `mid_job`, `post_job` and `idle` follow from that alone.
`_attach_post_job_charge_if_pending` links a post-job charge back to the run it followed, from
`_pending_post_job` — an in-memory dict that is never persisted. A restart between the job
finalizing and the vacuum docking loses the link and the session classifies as `idle`.

Ordering inside `_process_sample` is load-bearing in two more places. The CC/CV attribution
block runs **before** `_update_session` so the closing sample is still attributed to the open
session; the cost is that the *opening* sample is never attributed, which is correct, because
its delta crosses a non-charging gap of unknown duration. And `_update_session` reads
`last_charging` to detect the transition while `_process_sample` writes it afterwards — swap
those and every sample looks like a transition.

---

## 4. The health proxy: two regimes that age in opposite directions

CC (50→80, constant current) is a capacity proxy; CV (80→90, taper) is a resistance proxy. Both
are stored as **minutes per percent**, and both are turned into an index by the one formula in
`_compute_regime_pct`: `baseline / current * 100`.

**They move in opposite directions, and the file's own constants say so** — *"capacity loss
raises %/min in CC, resistance rise lowers %/min in CV"*. Following that through the shared
formula:

| regime | ages toward | min/pct | index |
|---|---|---|---|
| CC | more %/min | falls | **rises above 100** |
| CV | less %/min | rises | falls below 100 |

`health_pct` is an alias of the CV index, so the headline sensor reads the conventional
direction: lower is worse. The separately-exposed CC index does not, and nothing in the code
converts it.

> ✅ **CORRECTED 2026-08-23.** The docstring now states both directions and says plainly that higher is WORSE
> for CC. What it said before: **`_update_health`'s docstring had the CC half backwards.** It states that the CC ratio
> *"falls below 100"* with age and that *"higher = healthier"*. Both are true of CV and inverted
> for CC. The CV bullet beside it is correct, and the two cannot both fall below 100 through one
> shared formula. `battery/sensors.py` states the same physics and pointedly stops short of
> drawing the conclusion.
>
> The same inversion undercut the `REGIME_PCT_MAX` justification — now annotated in place,
> with the bound deliberately left at 150% (far outside real ageing, so it still clips CC
> implausibility even though the sentence only justifies CV). The trap recorded there is
> *do not tighten it toward 100 on the strength of that sentence*, which would reject true
> CC readings. Originally: — *"charging measurably faster
> than when the baseline was taken is something a cell cannot do"* holds for CV and is precisely
> what an aged pack does in CC.

### One anchor, two decoupled comparison sets

The baseline is a **per-install** anchor set by the first fully-qualifying session and never
re-anchored automatically. Anchoring requires start ≤ 50 **and** end ≥ 90 **and** both regime
values populated; the per-regime comparison sets require only one side each
(`_session_cc_qualifies`, `_session_cv_qualifies`). The 50→90 window still spans the 80→90
taper, so the rate cannot be gamed by skipping the slow part.

Qualifying sessions live in `health_qualifying_sessions` (cap 500, de-duped on the
`(start_ts, end_ts)` pair), separate from the 50-item display ring — so a baseline's own anchor
session cannot rotate out from under it. Promotion happens inside `_update_health` rather than
only at session close, which is why an older on-disk record still computes.

**`rebaseline` must clear that store too, and does.** Leaving it would let the next
`_update_health` re-anchor off a pre-swap session. Its scope is exactly: the four baseline
fields, five `stats` fields, and the retained set. It does not touch cycles, cumulative drain,
session history, job aggregates, mid-job stats, or either `*_rejected_pct` key.

> ⚠ **`CURRENT_WINDOW_DAYS` (14) is a preference, not a bound.** When the window is empty,
> `_compute_regime_pct` falls back to the most recent qualifying session carrying that regime at
> *any* age. The retained store holds 500 sessions and is never age-pruned, so `current` can be a
> single session years old and `health_pct` will read as a confident number derived from it. The
> 25–150 plausibility band is the only thing between that and a nonsense figure.

---

## 5. A ratio's two halves must count the same population

This is the subsystem's recurring defect and its clearest repair. Within one session dict the
discipline is applied three times and missed once:

| accumulator pair | incremented | true mean |
|---|---|---|
| `low_zone_rate_sum` / `low_zone_rate_samples` | same branch | yes |
| `high_zone_rate_sum` / `high_zone_rate_samples` | same branch | yes |
| `cc_duration_min` / `cc_delta_pct` (and CV) | same branch | yes |
| `rate_sum` / `rate_samples` | same branch | yes — *repaired, `C54`* |

The fourth row is the one that was missed, and the shape of the miss is worth keeping because it
is how this class hides. `samples` counts every charging sample; `rate_sum` accumulated only the
samples that produced a positive rate; `avg_rate_per_min` divided one by the other. **The numerator
and denominator counted different populations**, so the opening sample contributed 1 to the count
and 0.0 to the sum *by construction* — the session-opening branch returns before any rate exists —
as did every sample where the integer percentage did not tick and every sample dropped by the
interval or plausibility guards.

The tell was visible in the same row: **`avg_rate_per_min` could sit below `min_rate_per_min`**,
because min and max are taken over observed rates only, and a mean below its own minimum is
arithmetically impossible. Reproduced against the real code (60→70% over 21 minutes at a one-minute
cadence): `samples` 21, `rate_sum` 10.0, average 0.4762 against a stated minimum of 1.0 — 52% low.
Because the opening sample alone is enough, *every* session was affected, not only ragged ones.

The value was never confined to the CSV. It reaches `last_job.post_job_charge.avg_rate_per_min`,
which the card renders, and `mid_job_recharge_stats.rate_mean_per_min` — the sensor documented as
the cleanest health signal available.

`battery/manager.py::_close_session` now divides by a partnered `rate_samples`, incremented in the
same branch as `rate_sum`, and publishes it alongside the mean so a reader can tell a ten-interval
mean from a one-interval one. The CSV is unaffected: `battery/store.py::_SESSION_HEADER` is a fixed
tuple and the writer reads named fields from the summary, so an added key is ignored.

> ⚠ **A session already in flight when this shipped closes with `avg_rate_per_min` `None`.**
> Its `rate_sum` survives the restart but the population it should be divided by does not, and
> falling back to `samples` would reinstate precisely the value being removed. `None` reads as
> *not measured*; the old number read as a measurement and was not one. At most one session per
> vacuum is ever in that state, and the mid-job health stat is gated on `avg is not None`, so an
> unmeasured session contributes nothing rather than crashing.

### The repair that landed, and the one it did not reach

`_update_aggregate_bucket` now gates each drain mean's numerator **and** denominator on both
fields being present, so a job reaches a mean only when it carried both halves.
`count` is explicitly not the sample size of any mean; `samples_duration` and `samples_area` are.

The zero-guard on the division never prevented the original defect — it fires only when *no* job
in the bucket had area, so one measured job was enough for the ratio to proceed over mismatched
populations. Measured: 200/60 = 3.333 %/m² where the honest figure over the six measured jobs
was 2.0, 67% high.

> ⚠ **The repair is correct for buckets that start empty**, and an upgraded bucket does not start
> empty: it keeps a `duration_min_sum` accumulated under the old rule while the new partnered
> numerator starts at 0.0, so the mean reads *new drain over all-time duration*. It does not wash
> out — both sums grow together from that point, so the historical denominator is never diluted
> away. Measured against the real function (a bucket at count 50, `duration_min_sum` 1000.0, plus
> one post-upgrade job): 0.0059 where the honest figure over all 51 jobs is 0.30.
> All three C17 tests construct an empty bucket, so none of them can see this.

### The migration that closes it

`core/battery_aggregates_migration.py` replays the aggregates from the job archive once, keyed in
`data["migrations"]` alongside the three repairs that already use that mechanism. It runs the
existing `battery/manager.py::rebuild_job_aggregates` rather than a second implementation.

**A bucket is a target when it has accumulated into a denominator and carries no partnered
numerator** — absence, not a zero value. A numerator present and 0.0 against a populated
denominator is the same arithmetic, but it is also what an honest run of drain-less jobs produces
under the new rule, so keying on the value would fire on correct data. An empty bucket is not a
target at all: starting both halves of a ratio at 0.0 is exactly right.

Two properties are worth stating because neither is free:

- **`count` can fall, and that is the poison leaving rather than history being discarded.**
  `record_job_metrics` takes a `job_id` and uses it only for the `last_job` snapshot — it never
  deduplicates — so a duplicate finalize was counted twice and stayed counted, and a run excluded
  later through `exclude_learning_job` stayed counted too. The replay gate admits neither.
  Measured on a live install: one vacuum replayed 47 against a stored 47, the other 23 against 48.
  The migration logs the before and after for every vacuum it touches.
- **The previous aggregates are snapshotted to `job_aggregates_pre_c17` first.** The accumulated
  sums exist nowhere else, so a replay is otherwise one-way over a user's own derived history.

Seeding the missing numerator from the stored `drain_pct_sum` was the alternative, and it is the
tempting one: it preserves every published mean exactly and needs no disk. It is also the defect
itself. `drain_pct_sum` totals every job that reported a drain including the ones with no area, so
seeding it as the area numerator re-creates the mismatched population C17 removed and freezes the
old inflated figure in permanently. The same live install shows the difference: replaying moved
`drain_per_m2_mean` from 0.8325 to **0.7225**, because only 35 of the 47 jobs carried an area at
all — the twelve without one had been contributing drain to that numerator and nothing to its
denominator.

---

## 6. Per-job drain: what `job_metrics` refuses to do

`battery/job_metrics.py::compute_job_battery_metrics` is pure — one completed job in, one drain
block out, no I/O. Its central decision is a refusal.

**Drain is never attributed to individual rooms.** `_bucketed_share` writes `share`, `rooms` and
`area_m2` into each bucket and never drain; the per-config question is deferred to a
single-bucket gate downstream. A mixed-mode job therefore contributes to job-level stats and to
`all_jobs`, but to no per-config bucket at all. Per-mode means stay unbiased over many runs, at
the cost of converging slowly. Undoing it would make every per-mode mean a function of the
proration heuristic rather than of measurement.

**Absence is `None`, never zero.** `_safe_drain` returns `None` when the battery ended *higher*
than it started; `_positive_float` returns `None` for zero as well as negative. A run that
recharged mid-job yields `battery_used_pct: None`, all three derived rates go `None`, all three
last-job sensors read `unknown`, and the job increments `count` while incrementing neither
`samples_*`. That is the concrete, common source of the divergence in §5 — not a hypothetical.

`_apply_metrics_to_aggregates` is the single definition of which buckets a job feeds, shared by
the live path and the archive replay. **Eligibility is deliberately not shared**, and the
divergence is wider than the intended axis:

| | live (`learning/job_finalizer.py`) | rebuild (`learning/manager.py::collect_archived_battery_metrics`) |
|---|---|---|
| status | `completed` or `interrupted` | `completed` only |
| learning flag | `used_for_learning`, defaulting True | `bool(...)`, no default |
| exclusions | — | `LearningHistoryStore.is_learning_job`, so `exclude_learning_job` bites |

The exclusion axis is intended and stated. The `interrupted` axis and the default are not
documented either way — the certain part is the behaviour: **a rebuild moves the drain means on
any vacuum that has interrupted runs.**

Two more gates sit outside what the flags suggest. `single_ok = not metrics["mid_job_recharge"]`
excludes a recharged run from all three per-config buckets regardless of being single-mode, and
`mid_job_recharge` is not computed in `job_metrics.py` at all — `learning/job_finalizer.py` bolts
it on afterwards. And `_prorate_weights` prefers `estimated_minutes` on a **sum > 0** test, not
on completeness: a job where one room has an estimate and three do not takes that branch and
gives the other three weight 0.0. What stops a zero-weight room being treated as absent is that
`_bucketed_share` accumulates `share` and `rooms` unconditionally, so it still creates its bucket
and still flips the single-bucket gate.

`canonical_clean_mode` is applied at the call site for `clean_mode` only. Without it, the actual
key distribution found across 103 live job records — `vacuum` and `vacuum and mop` — makes a
genuinely single-mode run look like two modes and drops it out of per-mode learning entirely.

---

## 7. The published surface

`build_battery_sensors` builds **twelve** entities per vacuum: cycles, three zone rates, last
charge duration, health, two regime indices, three last-job metrics, and the mid-job recharge
rate. (`sensor/__init__.py` still calls it six.)

`battery/sensors.py` computes almost nothing — the 100% clamp and the `_bucket_means` projection,
and otherwise `float(x) if x is not None else None`. The decisions are all about honesty under
partial data.

**`extra_state_attributes` returns a dict on all twelve and never `None`**, so attributes are
published even when the state reads `unknown`. Undoing that makes *never computed* and *computed
and rejected* indistinguishable — the confusion RP-045 exists to undo. The reason is a paired
stable code plus plain-English fallback, mirroring the learning manager's convention so the card
can localize from the code and fall back to the backend's English.

**`sensor.<obj>_battery_health` is a clamped alias of the CV index, not its own computation** —
`min(float(health_pct), 100.0)` over a value the manager stores uncapped. Because
`_compute_regime_pct` rejects anything outside 25–150, the disagreement between the headline and
the CV sensor is bounded at exactly 50 points and both read unknown above that. The alias exists
for continuity: removing it orphans the history and automations of every pre-split install.

> ⚠ **`_battery_health`'s stated reason is slightly off its own premise.** The baseline is
> per-install — *your battery as it was when you started measuring* — not factory-fresh, so a
> reading above 100 is not literally "healthier than new". It is usually a young baseline anchored
> under worse conditions, which is why the uncapped value is kept rather than discarded.

**`MidJobRechargeRateSensor` is fed by session kind, not by battery level.** The only gate is
`kind == "mid_job"` plus a positive average and delta. The tight 15→75 window its docstring
describes is a property of Eufy firmware's auto-recharge behaviour that the integration assumes
and never checks — and the stored stats keep only count, sum, mean and last reading, not the
start and end levels, so it cannot be verified after the fact either. The mean is lifetime,
unweighted and un-resettable: after a battery swap, `battery_rebaseline` re-anchors the health
sensor while this one keeps averaging the dead cell permanently.

---

## 8. The raw files are write-only

`battery/store.py` appends `samples.jsonl` and `sessions.csv` under
`config/eufy_vacuum/battery/<object_id>/`. **Nothing in the tree reads either back** — the
manager keeps its own aggregates in `eufy_vacuum.storage`. A corrupt, truncated or missing raw
file therefore cannot break the integration.

**Both files archive the live stream only** — `store.py` never sees a job metric. The
recoverability runs the opposite way to what that suggests: the stream with a durable raw
archive cannot be replayed, because nothing reads it back, while the stream with no raw archive
can, because `learning/manager.py::LearningManager.collect_archived_battery_metrics` replays
stored `battery_metrics` out of the learning archive into
`battery/manager.py::BatteryHealthManager.rebuild_job_aggregates`. That replay is the only
repair for a poisoned bucket or an unmigrated one; the sample stream has no equivalent.

The cost is that nothing validates them. Both writers catch `OSError` only, log at DEBUG and
swallow, and both call sites dispatch to the executor without awaiting the future — so a full
disk produces nothing at default log level, and a non-`OSError` raised inside is swallowed twice
over. The JSONL path is protected from that class by `json.dumps(..., default=str)`; the CSV path
has only `_format_csv_value`, which handles datetime, float and `None` and passes everything else
through unchanged.

**`_SESSION_HEADER` is an 11-column projection frozen before the regime split.** It omits `kind`
and all six CC/CV fields the summary carries — exactly the columns needed to audit a health
number by hand. The fix is not free: the header is written once per file, so appending columns
leaves every existing `sessions.csv` with an 11-column header and wider rows from that point on,
in a file nothing reads and no test validates. Growing it requires a rotate-or-migrate step,
which is why it is effectively frozen.

---

## 9. Common wrong assumptions

| assumption | actually |
|---|---|
| `_update_health`'s docstring tells you which direction means an aged pack | it has the CC half inverted, and "higher = healthier" is wrong for that index |
| saves coalesce, per the module docstring and `_schedule_save` | that is `async_save_delayed`, which this subsystem never calls; every sample is a full-store write |
| a session that times out is summarized and persisted like any other | it is discarded — no summary, no CSV row, no history entry, no health sample |
| `avg_rate_per_min` is the average of the rates observed in that session | numerator and denominator count different populations; it can read below the row's own minimum |
| `all_jobs_count` is the sample size of `all_jobs_mean` | it is `count`, incremented for every job including those that fed no mean; the honest denominators exist on the bucket and are not published on the all-jobs pair |
| the C17 `samples` fix reached the card | the mean is fixed at the producer; the card still renders `count` under the "Jobs" header, and `samples` is read nowhere |
| `health_unavailable_reason` explains an unknown reading to the user | `implausible_regime_ratio` can never be displayed — it requires an anchored baseline, and the card's chip short-circuits on `baseline_session_count` before reaching it. It also has no i18n key |
| `health_pct` is None only while the baseline is seeding | at least three states produce None, including a figure computed and rejected as implausible |
| `BASELINE_SAMPLE_COUNT = 1` controls how many sessions anchor the baseline | it is read nowhere; `_update_health` hard-codes the value |
| the attributes on the low/high zone rate sensors describe the reading beside them | all three rate sensors share one attribute block reading the *latest* sample; the pairing is only coherent for the overall sensor |
| `completed_sessions` counts every session this vacuum has completed | it is the length of a ring trimmed to 50, so it pins at 50 forever while cycles keep climbing |
| a post-job charge always links back to the job before it | the pending link is in-memory only; a restart between finalize and dock loses it and the session classifies as `idle` |
| `metrics['by_clean_mode']` and the sensor's `by_clean_mode_mean` are the same bucket | same name, different owner — one is a per-job share dict with no drain in it, the other a cross-job running mean; the only bridge is the bucket *name* |
| the rejected diagnostics are visible somewhere | `rejected_rate_per_min` and both `*_charge_speed_rejected_pct` keys are written and read by nothing, and are absent from the record schema |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
