# 30 — External Runs

**Scope.** Runs the user started from the vendor's app, which this integration did not dispatch:
how one is detected and captured, why it finishes into a *pending review* rather than a completed
job, and what the review wizard is allowed to change. The normal dispatched path ends at
[06 — How a Run Ends](06-run-end.md); what a confirmed run then becomes is
[26](26-learning-record-store.md) onward.

An external run is the case where the system has good measurements and **no idea what it was
measuring.** Counters, areas and settings are all observable; the room identity is not, because
nobody told it which rooms were queued. Every design below follows from that one asymmetry.

---

## 1. Capture first, ask later

`jobs/active_job.py::start_external_capture` opens a slot with `status="external"` and a start
time, and nothing else. There is no queue and no payload — the run was not dispatched, so there is
nothing to copy from.

That status is what makes the metrics listener treat the run as in-flight, so counter samples and
setting-select values buffer into the slot exactly as they would for a dispatched job. The
measurement path is shared; only the identity is missing.

`learning/external_run.py::maybe_handle_external_run` is the detector, called from the lifecycle
listener: cleaning, with no dispatched job, means somebody started this elsewhere.

---

## 2. The finalize waits for the dock, and keeps waiting through station cycles

An external run has no completion signal of its own — no queue to exhaust, no dispatch to match
against. What it has is the robot arriving at the dock and **staying** there.

The grace machinery defers the finalize until that hold is satisfied, and re-checks while the task
status still reports a mid-run station cycle. A wash or a dry after docking is not the end of the
run, and finalizing on first-dock would cut the record short and book the station time as though
the run were over. `learning/external_run.py::_external_grace_finalize` is what eventually runs,
and mid-run docks are booked as overhead rather than treated as boundaries.

---

## 3. It finishes into a pending record, not a job

`learning/external_ingest.py::build_pending_record` produces a review record under its own
directory. It is **not** a completed job, and nothing about it reaches the learned baselines.

This is the load-bearing decision in the subsystem. The alternative — segment it, guess the rooms,
and file it as a normal completed job — would let the system train on runs whose room identity it
invented. Given that identity is precisely the thing it cannot observe, that would be learning
noise with full confidence.

Graduation to a real completed-job record happens only through
`learning/external_run.py::confirm_external_run`, after a person has supplied what the machine
could not: which rooms these segments were, and whether edge mopping was on.

---

## 4. Every boundary is offered; only the confident ones are chosen

The record bakes in the **full candidate pool** — every boundary the segmenter found, including the
weak and transit cuts an earlier filter used to discard — so the review card can offer "split here"
at any of them.

The **default** segmentation is deliberately narrower. Only confident cuts are on: a long wash
plateau, or a per-room settings flip across the boundary. `learning/external_ingest.py::_mark_candidate_confidence`
makes that call. An uncertain cut — a short area rise with no settings flip, which is as likely to
be an edge-to-fill turn as a new room — defaults **off** and surfaces as a candidate.

The split between these two is the whole interaction design: **the machine proposes what it can
defend and exposes everything else rather than deciding it.** A discarded candidate cannot be
recovered by the user; an offered one that defaults off costs nothing.

Each segment also carries a ranked shortlist of likely rooms, scored on area and settings and
scoped to the map with carpet filtering (`learning/external_ingest.py::_rank_shortlist`) — the
system's best guess at identity, presented as a suggestion rather than applied as an answer.

---

## 5. The raw samples ride along, then are stripped

The pending record **embeds the raw counter and settings samples**, so
`learning/external_run.py::resegment_external_run` can re-cut the run server-side at any room count
or boundary set — not just re-filter the cuts chosen the first time.

`learning/external_ingest.py::strip_samples` removes them on the way out to the card. The card gets
segments; the server keeps the evidence.

Keeping the raw input is what makes the review genuinely re-runnable. A record that stored only its
own conclusions could be edited but never re-derived, and every re-segmentation would compound the
first pass's mistakes.

---

## 6. Identity reconciliation, and when a shift blocks learning

`learning/external_ingest.py::build_attributed_job` applies the identity a user confirmed;
`learning/external_ingest.py::reconcile_dispatched_identity` handles the case where a dispatched
job's own identity has to be squared with what was observed.

`learning/external_ingest.py::attribution_shift_blocks_learning` is the guard: if the attributed
room sequence shifted relative to the observed timings, the run is not used for learning. A
consistent off-by-one in attribution is worse than missing data — every room would be trained on
its neighbour's measurements, and the resulting statistics would be confidently wrong for the whole
map rather than absent for one room.

Pending job ids are validated by `learning/external_run.py::_is_valid_pending_job_id` on the same
reasoning as [26 §6](26-learning-record-store.md): they arrive from a service call, they are
interpolated into a path, and a malformed one can never name a real record — so reject rather than
sanitise.

---

## 7. One slot, and where the collision window actually is

There is exactly **one** active-job slot per vacuum and map, and both paths write it.

**The capture cannot clobber a dispatched run.** `learning/external_run.py::maybe_handle_external_run`
scans every known map first and returns immediately if any of them holds a `started` or `paused`
job — *internal owns this run*. Detection is defined as "cleaning with no dispatched job", so the
overwrite in `jobs/active_job.py::start_external_capture` is only ever reached when there is
nothing to overwrite.

**A dispatched start cannot happen mid-clean either**, but not for a reason local to this
subsystem: during an external run the robot is by definition cleaning, and the start gate consults
`jobs/job_monitor.py::evaluate_job_lifecycle`, which refuses on an active vacuum state. The guard
is physical, not bookkeeping — nothing anywhere tests for `status == "external"` on the start path.

**That leaves the grace window**, and it is now closed. Between the robot docking and
`learning/external_run.py::_external_grace_finalize` firing, the slot is still open with a pending
timer while the vacuum reports `docked` or `idle` — which is precisely the state the lifecycle
check admits. A dispatched start in that window wrote the same slot, and the buffered counter and
settings samples the pending record is built from went with it. Nothing on the start path tested
for `status == "external"`, so the capture disappeared with no error and nothing left to review.

`learning/external_run.py::ExternalRunManager.flush_pending_capture` closes it, and
`core/manager.py::EufyVacuumManager.start_selected_rooms` calls it once the start is committed: an
open capture is finalized into `external_jobs/` exactly as the grace timer would have left it, and
its pending timer is cancelled so it cannot later fire against a slot that now belongs to the
dispatched run.

**Finalize rather than refuse**, deliberately. The slot is being taken either way, and refusing a
start the user just asked for — to preserve a record they have not seen yet and did not ask for —
is the worse trade. Two placement rules follow from that, and both are pinned by tests: the flush
runs **after** the refusals, so a blocked start never gives up a capture it is not taking; and it
matches **only** a `status="external"` slot, so a leftover dispatched job is never filed into the
external review queue as though the user had started it from the app.

A dedicated audit of this subsystem is still **planned and has not been performed**. What is closed
is the specific window the reading identified; the audit's broader concern is not discharged by
it.

⚠ **Do not begin that audit during a live external run.** The audit's own note is that starting it
mid-capture silently destroys the capture it was meant to observe.

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
