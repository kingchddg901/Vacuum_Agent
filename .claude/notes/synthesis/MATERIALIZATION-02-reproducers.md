# MATERIALIZATION-02 — tranche-2 reproducers (wave 2)

**Main agent, 2026-08-01, against master `1b32515`+.** Tranche 2 needs **35**
reproducer artifacts (33 new, 2 extensions) against tranche 1's 5, so the stubs
were consolidated first.

## The harness

`.claude/notes/_proof_harness.py` — fake hass (states/services/bus/loop),
`ManagerStub` with a REAL `data` dict and inert unknown-attribute no-ops,
fixture builders (`active_job`, `room_phase`, `break_phase`, `managed_rooms`,
`seed_map`, `learning_store`, `corrupt`), and the `Proof` verdict reporter.

**The inertness rule** (stated in the module docstring, load-bearing): the
harness provides scaffolding ONLY — it must never implement, emulate or
normalize production behaviour. Every proof drives the real production
function. A harness that "helpfully" corrected something would make all 33
proofs pass for the wrong reason at once: the tranche-1 battery lesson
multiplied by 33.

**The verdict contract**: each case declares mutually-exclusive BEFORE and AFTER
shapes. Anything else is `UNEXPECTED SHAPE` and exits 1 — a proof that tolerates
a third state proves nothing. Both-true is also UNEXPECTED (the shapes must be
exclusive), so a sloppy proof reports itself.

## Wave 2 — 8 of 8 DONE, 23 cases

Verdicts as of `6598b0c` (RP-010/011/012 repaired and landed; the rest awaiting
assignment):

| proof | packet | cases | verdict now |
|---|---|---|---|
| `_proof_cancel_chokepoint.py` | RP-010 | 3 | 3 AFTER ✅ |
| `_proof_watchdog_wedge.py` | RP-011 | 3 | 3 AFTER ✅ |
| `_proof_tracker_lifecycle.py` | RP-012 | 4 | 4 AFTER ✅ |
| `_proof_phase_validity.py` | RP-013a | 2 | 2 BEFORE (blocked — see below) |
| `_proof_completed_evidence.py` | RP-013c + **013d** | 3 | 3 BEFORE |
| `_proof_group_allocation.py` | RP-013b | 2 | 2 BEFORE |
| `_proof_recorder_scope.py` | RP-013e | 3 | 3 BEFORE |
| `_proof_inflight_askers.py` | RP-014 | 3 | 3 BEFORE |

Every packet's `expected_before` fragment reproduces verbatim, including
RP-014's three (`no tick for external` / `dock action allowed mid-external` /
`sensor: none`) and RP-013e's two (`finished bucket absorbed sample` /
`battery=None`).

Notable confirmations:

- **RP-011 case 3** drives the REAL captured tick closure; the `RuntimeError`
  traceback in its output IS the evidence — production's `_process` task died on
  slot 1 and never reached `vacuum.ivy`.
- **RP-012 case 2** confirms `#9:A4-AJ-1` (HIGH) exactly as the corpus states
  it: the recharge-end branch is unreachable because the early
  `if not is_charging(): return` guarantees charging is True, so the same pure
  state read can never be False. Seconds stay 0, the flag stays set, the sampler
  stays paused for the rest of the run.
- **RP-013a** shows the record keeps the real 120s/180s per-room timings while
  `transit_capture_valid=False` tells every consumer not to trust them.
- **RP-013e case 3** drives the REAL `job_metrics.register()` subscription set
  and prints it: `['sensor.alfred_cleaning_area', 'sensor.alfred_cleaning_time']`
  — the adapter-declared battery entity is simply not there. `last_battery_percent`
  has **no writer anywhere in the integration**, so every counter sample has
  carried `battery: None` since the key was introduced. That is OBS-B-3's null
  per-room `battery_delta` located at source, not inferred.
- **RP-014 case 2** is the actuating one: with an app-started run in flight and
  the robot at the dock (mid-run recharge or wash), `get_dock_action_status`
  returns `allowed=True, reason='ready'` for wash / dry / empty.

## Three mis-models caught by the UNEXPECTED arm

Recorded so the next author does not repeat them:

1. **RP-010 double-cancel** — first draft stubbed finalize as `None` for both
   cancels; the summary then survived and the case reported UNEXPECTED. The real
   mechanism is that the second cancel receives a REFUSAL dict, and
   `mark_active_job_finalized` only rewrites `finalize_summary` when it gets a
   dict — so the summary is overwritten with Nones.
2. **RP-012 phase advance** — first draft asserted `current_room_id` is cleared;
   `advance_active_job_phase` actually MOVES it to the next phase's room. The
   real divergence is sharper: `current_room_id=2` while
   `_native_current_room_id=1`, i.e. the two pointers actively disagree.
3. **Harness, Python 3.14** — `asyncio.get_event_loop()` no longer auto-creates
   a loop for a sync caller. Fixed once in the harness (idle-loop fallback);
   would otherwise have broken every sync proof.

## Two more harness fixes, both found by wave 2's last proofs

Recorded because both are one-line-class fixes that would each have cost an
author an iteration to rediscover:

4. **`hass` must be HASHABLE.** HA's `@singleton` decorator — used by *every*
   registry accessor (`entity_registry.async_get`, device, area, issue) — wraps
   its lookup in `functools.lru_cache`, which hashes the hass argument.
   `SimpleNamespace` defines `__eq__`, so Python sets `__hash__ = None` and the
   lookup dies with `TypeError: unhashable type`. `make_hass` now returns a
   `FakeHass` subclass restoring identity hash **and identity equality** — value
   equality would let the lru_cache hand one proof's registry to another.
5. **Sync proofs must drain the idle loop.** Production schedules its saves with
   `hass.async_create_task`; in a sync proof those land on the never-run idle
   loop and Python prints `Task was destroyed but it is pending` for each at
   exit — noise that would bury a real signal. `H.drain_idle_loop()` (called from
   `H.run`) RUNS them. Cancelling or swallowing was rejected: that would make the
   harness decide the task didn't matter, and a proof depending on a scheduled
   save would silently lose it.

## ✅ CLOSED — the RP-012 repair defect the proof found

`RP-012(b)` moved recharge-end resolution into `resolve_mid_job_recharge_resumed`
but dropped the commanded-dock guard, so a job parked on a `charge_wait` phase
accrued `recharge_seconds_accumulated=300` for a PLANNED dock. Proof case 4
caught it; **`6598b0c` (RP-012(d))** ported the `is_dock_polled_phase`
early-return across with the original's reasoning referenced in-comment, plus a
regression test. `_proof_tracker_lifecycle.py` now reports **4 AFTER**.

Worth keeping: the defect existed only *because* the repair worked. Pre-repair
the accrual branch was dead code, so the missing guard had nothing to guard. A
repair can make a latent second defect reachable, and only a reproducer that
asserts the post-repair invariant catches it.

## ⚠ TWO FINDINGS FOR THE PACKET AUTHOR — RP-014 is under-scoped

**1. RP-014 names five sites; there are seventeen.** Grepping the literal set:

| module | count |
|---|---|
| `core/manager.py` | 6 |
| `jobs/active_job.py` | 6 |
| `dock/manager.py`, `listeners/job_progress.py`, `listeners/lifecycle.py`, `learning/external_run.py`, `planning/run_plan.py` | 1 each |

The packet's per-site adjudication table must either cover all 17 or state
explicitly which are deliberate queue questions and why. Shipping the table at 5
would leave 12 unadjudicated sites looking blessed.

**2. The repair campaign propagated an eighteenth.** `RP-012(b)` (`47f9a25`)
added `if active_job.get("status") not in {"started", "paused"}` to the new
`resolve_mid_job_recharge_resumed`. That is the sibling-sweep pattern exactly —
vocabulary spreading by hand-copied literal — and it happened *inside the audit
that exists to stop it*, three commits before the packet that would have caught
it. Whatever RP-014 lands must include a gate, not just a sweep, or the
population regrows.

## ✅ STEPPED RUN A CAPTURED — 2026-08-01, `job_2026-08-01T13-49-21` (Ivy)

Profile `[Kitchen 27] → charge_wait 100% → [Hallway 25]`, completed, auto-finalized
14:08:50. Persisted record:
`config/eufy_vacuum/learning/ivy/jobs/job_2026-08-01T13-49-21.json`.

**Use the persisted job record, not the debug log.** The capture was armed at the
DEFAULT ring size (3000), so the log holds only 14:02:12–14:11:54 of a job that
started 13:49:21 — phase 0, the phase advance and most of the charge hold were
evicted. The finalize payload survived by luck. The job JSON is not subject to
the ring and carried everything. Arm Run B with `size: 50000`.

### Confirmed as predicted

| packet | evidence |
|---|---|
| **RP-013a** ✅ | `transit_capture_valid: false` while BOTH room phases captured cleanly — kitchen 255 s / 4.1 m², hallway 302 s / 1.2 m². Exactly the predicted shape: honest per-room data, marked untrustworthy by the charge phase between them. |
| **RP-013e** ✅ | `battery_delta: null` on both rooms. OBS-B-3 observed, not inferred. |
| **RP-012(d)** ✅ | AFTER-picture: `recharge_seconds_accumulated: 0`, `mid_job_recharge_observed: false`, `overhead.recharge_minutes: 0.0`. The commanded ~9 min hold was correctly NOT booked as an unplanned recharge. The guard works on hardware. |

**RP-013b was NOT exercised** — all three phases were single-room. The group
defect needs a `[room, room]` group in ONE phase; add it to Run B's profile.

### ⚠ RP-013d confirmed on hardware — AND THE PACKET IS INSUFFICIENT

The record contradicts itself exactly as the proof shows:
`queue.queue_room_ids: [25]` vs `resolved_rooms: [27, 25]`. The Kitchen — 255
seconds of it — is absent from the queue half, so every missed/trouble-room
consumer believes this run was only ever about the Hallway.

But the MECHANISM is not the one the packet describes. RP-013d says *"job-frozen
snapshot wins; live queue only when the job carries none."* **That would not fix
this run.** On a PHASED job `advance_active_job_phase` overwrites the job's own
top-level `queue_room_ids` with the phase it moved into, so the "job-frozen"
value is itself `[25]`. Preferring it changes nothing.

The queue block needs the **union-of-all-phases** ladder that `resolved_rooms`
already uses (and whose in-code comment explains exactly why the top-level list
cannot be trusted after an advance — the same reasoning, never applied to the
queue). Two corrections follow:

1. **RP-013d's `required_behavior` must be rewritten** to the phase-union ladder
   before assignment. As written it ships a no-op for stepped runs.
2. **`_proof_completed_evidence.py` case 3 under-models it** — it drives an
   ATOMIC job whose top-level queue survives, so it proves the live-vs-frozen
   precedence but not the post-advance clobber. Add a phased variant.

### 🆕 NEW HIGH — job-level `cleaning_time_seconds` is the LAST phase's counter

Not in any packet; found only because this was a stepped run.

`job_finalizer.py:567` takes `cleaning_time_seconds` from
`last_cleaning_time_seconds` — the last-seen device counter. **Every dispatched
phase resets that counter**, so a stepped run records only its final phase:

    recorded  cleaning_time_seconds = 302
    measured  255 (kitchen) + 302 (hallway) = 557
    under-reported by 46 %

The cascade is worse than the number. `learning/utils.py:203` computes
`total_overhead_minutes = duration − cleaning_minutes`:

    19.48 − (302/60) = 14.45   ← matches the record exactly
    truth:  19.48 − (557/60) = 10.19

So overhead is inflated by the same 255 s, and `stats_rebuilder.py:316` averages
`total_overhead_minutes` across jobs — **every stepped run poisons the learned
overhead model**. This job carried `used_for_learning: true`,
`learning_blockers: []`. It is already in.

Note the asymmetry, because it constrains the fix: `cleaning_area_m2` recorded
5.8 against a per-room sum of 5.3 — area accumulated across phases while time did
not. The same `last_*` read yields a cumulative answer for one counter and a
per-phase answer for the other, because the device resets them differently. So
the fix cannot be "trust the other counter" — it must **sum per-phase deltas**,
and it must not assume either counter's reset behaviour is brand-stable.

Suggested id: **RP-013f** (RF-11 part 6), HIGH, `learning/job_finalizer.py` +
`learning/utils.py`. Reproducer: a 2-phase job whose phases measure 255 and 302 —
assert the job total is 557 and overhead is the residual against 557.

## ⏳ STILL BLOCKED — RP-013c hardware precondition (RP-013a now UNBLOCKED)

**RP-013a's hardware precondition is unmet.** The packet requires a stepped-run
(charge_wait + 2-room group) BEFORE capture and says to capture it if tranche-1's
HC batch lacked one. It did — HC-0/1/2 covered cancel, reload and re-segment, all
single/simple runs. **A stepped-run baseline is a decaying item and must be
captured before RP-013a lands.** RP-013c additionally wants a cancelled stepped
run (one extra Alfred cancel mid-phase-2, same session).

> **HELD 2026-08-01 (Chris).** The stepped-run capture is deferred; work
> continues around it. **RP-013a and RP-013c are therefore BLOCKED from
> assignment** — not because their reproducers are missing (both are materialized
> and reproducing) but because landing them without a before-picture destroys the
> only chance to tell "we broke it" from "it always did that". This is the one
> item in the plan that decays: the longer the repair waits, the more the
> pre-repair behaviour is a memory rather than an artifact. Everything else in
> wave 2 (RP-013b, RP-013d, RP-013e, RP-014) is unaffected and may proceed.
>
> **Capture recipe when it resumes** (two runs, one session, ~1h mostly
> unattended): build a profile `[room] → charge_wait 90% → [room, room]`, start
> below 90% so the charge step actually waits, arm
> `eufy_vacuum.debug_capture_start` with `size: 50000, max_minutes: 120`.
> **Run A** — let all three phases finish (HC-2b). **Run B** — same profile,
> cancel from the card during phase 2, after the charge (RP-013c's exact shape).
> Expect in run A: `transit_capture_valid=False` despite both room phases
> capturing cleanly. In run B: the incomplete-run log listing phase 1's finished
> room as missed.

**Ride-along, free when that session happens:** RP-013e's hardware gate wants a
non-null per-room `battery_delta` in a post-repair capture (closes OBS-B-3
observably). Same run, no extra work — worth pinning to the same session rather
than costing a second one.

## Next

1. Hostile review pass over the 8 wave-2 proofs before waves 3–6 (recommended —
   tranche 1's review caught two mis-models).
2. Assign RP-013b / RP-013d / RP-013e / RP-014 (unblocked). RP-014 needs its
   site table widened to 17 first — see above.
3. Waves 3–6: ~27 more artifacts.
4. Ledger/corpus closure marking for tranche-1's ~40 findings, plus RP-010..012.
