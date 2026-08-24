# 43 — Observing a Run Without Geometry

**Scope.** Four modules that answer *where is the robot and what is it doing* using counters and
signals rather than position: counter-plateau segmentation, the pose ring that outlives a job, the
off-cadence room refresh, and the job-active trace that deliberately decides nothing. What consumes
these is [28](28-learning-statistics.md) and [30](30-external-runs.md).

The premise they share is that **coordinates are not trustworthy across sessions.** On some
firmware raw positions drift between runs, so anything derived from them is comparable only within
one session. Everything here is built to be frame-invariant instead.

---

## 1. Counters, not coordinates

`counter_segmentation.py::segment_counters` turns two cumulative progress counters — a clean clock
and unique area covered — into ordered per-room segments **with no geometry consulted at all.**

A counter is comparable across sessions in a way a coordinate is not: fifteen square metres is
fifteen square metres regardless of where the origin landed this time. So a *plateau* in area with
the clock still running is a boundary signal that survives the frame drift that makes position
useless.

The pipeline is **three pure stages**, and the purity is the feature:

| stage | answers |
|---|---|
| `counter_segmentation.py::find_candidates` | every boundary the samples contain, ranked and kinded |
| `counter_segmentation.py::select_active` | which of them to use — by count, explicitly, or by default |
| `counter_segmentation.py::build_segments` | the segments that follow from that selection |

Splitting detection from selection is what lets a run be **re-segmented from the same frozen
samples at any granularity**, which is exactly what the external-review wizard does when a user
sets a room count or toggles a boundary ([30 §5](30-external-runs.md)). A single function that
found and chose in one pass would force a re-run of the detection — over samples that no longer
exist — every time a user changed their mind.

---

## 2. The pose ring exists because the live buffer is job-scoped

The pose sampler already buffers what it needs into the active job, where the attribution engines
read it live. That buffer lives until the next run on the same map overwrites it, and it never
reaches the finalized record.

> The moment a run ends, the fine-grained history of what the robot actually did is gone.

`pose_store.py` is a **24-hour rolling, chunked record** that outlives the job, written in parallel
and read by nothing in the live path. Being purely additive is the point: no existing consumer
changes behaviour, so the ring cannot break a run by existing.

This is [`archive cheap raw data`](26-learning-record-store.md) as a design stance — the samples
are small, the questions they answer later are not predictable in advance, and a summary computed
now can only answer the question somebody thought to ask now.

---

## 3. Pulsing a signal that lags its own poll

A brand whose live current-room signal is derived from a map refreshed on a slow cache gate, while
its status moves faster, reports a stale room for most of each interval.
`live_refresh/manager.py::LiveRoomRefreshManager` pulses an adapter-named service to refresh that
signal off-cadence during a contiguous run.

Core stays brand-agnostic in a strict sense: **both** the service to call and the
local-connection gate that avoids a cloud rate limit are adapter-declared data, and a brand that
omits the block gets a no-op rather than a default.

It is deliberately **excluded for strict-order runs**, and the reason is that they do not need it:
those dock between rooms, so every room start is already a state flip that forces a free refresh.
Pulsing there would spend requests to learn something the run was about to be told anyway.

---

## 4. A module that decides nothing, on purpose

`job_active_signal.py` ships **wired to nothing**, and that is its design rather than its state.

The problem is real and live: an upstream release stopped creating the cleaning binary sensor on
some devices. A brand that declares that entity as its job-active signal and requires it to clear
for completion can then never arm the completion gate — so the stranded-run reaper force-closes the
job as interrupted roughly fifteen minutes after dispatch, possibly mid-clean. A real user is in
that state.

Replacing the binary needs a rule for *is this dock a recharge or the finish?*, and the module's
first decision is that **it does not have one it can justify**:

> a wrong rule is worse than the bug: finalizing early writes a truncated learning sample, which is
> silent and permanent, whereas the current failure is at least visible.

So `job_active_signal.py::probe_presence` reports whether the signal exists, and
`job_active_signal.py::observe` writes a record. **Nothing consults either** — no completion gate,
no reaper, no dispatch path — and the module states that adding a caller is a design change rather
than a refactor.

### Why raw inputs rather than a verdict

The obvious shape is to compute what a candidate rule *would* say and log whether it agreed with
the real binary. The module rejects it, and the reasoning is the transferable part:

**That bakes one rule into the evidence.** It answers "is rule R right?" and nothing else, so every
later candidate needs another live run to evaluate.

Recording the raw **inputs** instead makes the trace rule-agnostic. Any number of candidate
classifiers can be scored against it offline, long after the run — *including ones nobody has
thought of yet.*

And the trace is **self-labelling** on hardware where the binary still works: the native signal is
the ground truth for that tick, so a candidate is scored by replaying the trace and comparing.
Evidence gathered on working hardware is what will validate a rule for broken hardware.

### What is deliberately absent, and why each is

| omitted | reason |
|---|---|
| stored state | dock dwell comes from the state object's own last-changed, so there is nothing to persist, invalidate, or leak across runs — and no new failure mode on restart |
| a forced-absence override | while nothing consumes the fallback the trace would be **byte-identical**; it earns its keep the day a classifier gates on this, and should land with that classifier |
| translation | these are maintainer-facing debug records, never rendered to a user |

That table is the discipline worth copying. Each absence is a decision with a stated trigger for
when it stops being right — which is the difference between *not built yet* and *deliberately not
built*.

---

## 5. Common wrong assumptions

| assumption | reality |
|---|---|
| room boundaries come from position | position drifts between sessions; boundaries come from counter plateaus — §1 |
| segmentation is one pass | detection and selection are separate so a run can be re-cut from frozen samples — §1 |
| the pose sampler's data is kept | its buffer is job-scoped and overwritten; the ring is a separate additive copy — §2 |
| every brand needs the live refresh | it is adapter-declared, off by default, and skipped for strict-order runs — §3 |
| `job_active_signal` fixes the missing binary | it is wired to nothing and decides nothing; a caller would be a design change — §4 |
| the trace records whether the rule was right | it records the rule's **inputs**, so future rules can be scored on old runs — §4 |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
