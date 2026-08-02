# Ownership adjudication + Chris's decisions, 2026-08-01

Two things the executing window must not re-litigate: who owns four
double-claimed findings, and four scope calls Chris made.

---

## Four findings claimed by two packets each — RESOLVED

Found by the RP-040 table cross-check. Each is decided from the packets' own
`problem` statements, three of which quote the finding almost verbatim.

### `#16:A4-STATE-3` → **RP-017** (not RP-020)

*trouble_rooms.json is keyed by raw room_id, so counters silently reattach to the
wrong physical room after a re-segment.*

RP-017's problem statement names it directly: *"id-keyed sidecar stores are never
remapped on re-segment (**trouble_rooms — the one store the reconcile-migrate
walker forgets**)"*. That is the finding's own wording. RP-020 is about rebuild
REACH — which stores a rebuild touches — which is a different axis.

The finding's impact does note *"no rebuild, service or UI action can correct
it"*, which is why RP-020 grabbed it. But that is a CONSEQUENCE of the id-keying,
not the defect. Fix the keying in RP-017 and the rebuild gap stops mattering;
fix the rebuild in RP-020 and the counters still reattach on the next re-segment.
**RP-020 should reference it, not own it.**

### `#13:A6-DIAG-6` → **RP-028** (not RP-031), with a rider

*set_dock_event_count overwrites a durable counter for ANY entity_id, no
managed-vacuum check, no undo.*

Genuinely split, so state both halves rather than pretending it is clean:
- *"silently seeds a phantom dock_events branch that persists forever"* — that is
  RP-028's family verbatim (phantom buckets minted by unaddressed writes).
- *"destroys the lifetime count with no confirmation and no undo"* — that is
  RP-031's destructive-before-authorization concern.

**RP-028 owns it**, because the managed-vacuum check is the entry point that
closes both halves: an addressed write cannot seed a phantom branch, and cannot
reach the wrong device's counters. **RIDER:** RP-031's response-shape convention
still applies to this service — it must not report success for a refused write.
Landing RP-028 does not exempt it from RP-031's sweep.

### `#13:A2-JOB-5` → **RP-032** (not RP-031)

*Break schemas do not enforce break_type→parameter dependency, and the two
sibling schemas disagree on which break types exist.*

Sibling schemas disagreeing about their own vocabulary IS declaration parity,
which is RP-032's entire subject. RP-031 governs how a failure is REPORTED, not
what a schema declares. Note the user-visible shape here is a service that
returns success and silently does nothing — tempting to file under RP-031 — but
the cause is the schema, and RP-031 cannot fix a schema that accepts the wrong
thing in the first place.

### `#13:A2-JOB-6` → **RP-032** (not RP-031)

*get_queue_steps returns `breaks` in a shape set_queue_breaks rejects — the
documented read-modify-write round trip fails validation.*

RP-032's problem statement already lists *"break-schema round trip fails
validation"* as one of its own members. Same reasoning as JOB-5.

**Sequencing is unaffected:** RP-032 is already `blocked_by RP-031`, so both
JOB-5 and JOB-6 land after RP-031 regardless.

---

## Chris's scope decisions, 2026-08-01

| # | question | decision |
|---|---|---|
| 1 | Battery: promote a tier before RF-36, or execute RP-042 alone? | **DEFER** — the whole RF-36 family stays parked, RP-042 included. |
| 2 | Hardware Run B (unblocks RP-013c) | **DEFER** |
| 3 | CARD-7 design session | **DEFER for now** |
| 4 | CARD-2(1) — is the VISUAL=1 harness repin in scope? | **YES — REPIN.** Do it. |
| 5 | CARD-6(3) — build the `zone_bounds` live readout? | **NOT IN SCOPE.** It is a feature, not a repair; it does not belong in a defect campaign. Drop the clause. |
| 6 | RP-040 — does the card get an unreject-rooms affordance? | **NO.** `setup_unreject_rooms` ships as a SERVICE only. Do not build a card control; do not ask again at review. |
| 7 | Four double-owned findings | **Adjudicated above.** |

### What the deferrals mean for the executing window

Do not treat a deferred item as available work because its blocker looks
mechanical. RP-013c, RP-042..045 and CARD-7 are **parked by decision**, not
waiting on discovery. If a stage's scope appears to touch one, stop and report
rather than proceeding.

CARD-6 clause (3) is now **dropped**, not deferred — remove it from the clause
list when CARD-6 is executed, and note in the commit that `zone_bounds` remains
a snapshot field with no consumer BY DECISION, so a future reader does not file
it as an oversight.
