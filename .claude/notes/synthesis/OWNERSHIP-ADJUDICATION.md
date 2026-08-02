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
| 1 | Battery: promote a tier before RF-36? | **REVERSED 2026-08-01 — NO promotion, EXECUTE.** What live observation found is enough to run the fixes; the mechanism is known, not suspected. RF-36 is UNPARKED. |
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

---

## Three later decisions, same day

### RP-042 — `unreadable` is **null**, not a tri-state

The packet left one choice open: *"an explicit UNKNOWN result (None, or a tri-state
mirroring RP-006 — pick one)"*. **Chris: null.**

Right call, and the reason is worth keeping: RP-006 needed three states because
`read_json` must distinguish ABSENT from CORRUPT from PRESENT — each drives a
different recovery. A battery reading has only two states that matter, KNOWN and
UNKNOWN, so a tri-state would add a branch nobody can act on differently.

The consumer rule follows directly: **a `None` sample is a GAP, not a delta.** The
drain accumulator and the session recorder SKIP it. They must not difference
against it, and must not carry the previous reading forward as if it were
observed.

The RF-36 promotion question is also closed — no audit first. Execute the four
packets from what the live evidence already proves.

### Run B — the recipe was WRONG, and Chris caught it

The held recipe said "cancel during phase 2 after the charge" and separately "add
a `[room, room]` group so RP-013b gets hardware coverage". Chris read that as two
merged runs, and he is right — worse, **as written it would have collected
RP-013c's evidence and silently missed RP-013b's.**

`_capture_finishing_phase_timing` runs when a phase FINISHES. Cancel during the
group phase and the group never finishes, so no timing entry is written and
RP-013b's whole point — one entry crediting only `room[0]` — is unobservable.

**CORRECTED PROFILE — four phases, one run, both packets:**

    [room 1] -> charge_wait -> [room 2, room 3] -> [room 4]
                                ^ group COMPLETES   ^ cancel HERE

The group finishes (RP-013b captured), then the cancel lands during the final
single-room phase (RP-013c captured). Arm with `size: 50000`; the default 3000
evicted most of Run A.

If four phases is too long a sit, run them separately — RP-013b's needs no cancel
at all and is short.

### CARD-7 — NOT a new pane; extend the setup surface

CARD-7's `files` says `src/ (new pane)`. **Chris: rooms are already discovered and
surfaced in setup — a separate review pane is redundant.** Checked and he is
right on both halves:

- the gap is REAL: `rooms/reconciliation.py:141` returns
  `{"reviews": [...], "has_changes": bool}` and there are ZERO card consumers
  (the only "review" in `src/renderers/setup.js` is a docstring mention of drift
  review, a different thing);
- but setup ALREADY owns the room surface, so the fix is to surface the four
  review kinds (renamed / id_changed / removed / new) THERE, not to build a
  parallel place for rooms to live. Two surfaces for the same objects is how they
  drift apart.

That resolves the first and largest of CARD-7's design questions. Remaining for
the design session: entry point / does a pending review announce itself, how the
four review kinds render (removed and renamed are not symmetric decisions), and —
not in the packet — **what happens to a partially-accepted set when `plan_token`
goes stale mid-review.** The packet specifies the `plan_changed` refusal but not
the recovery.

CARD-7 stays `blocked_by RP-019` regardless.

---

## RP-032 `no_yaml_entry` — 24 services adjudicated (Chris, 2026-08-02)

Sonnet correctly refused to self-approve these (packet rule: the allowlist is
Chris-reviewed). Ruled and written into the packet — full table in
`SYNTH-10-packets-wave6.md`, section "RP-032 — `no_yaml_entry` ruling".

**The rule:** a service earns a `services.yaml` entry if a human calling it by
hand is coherent; it stays internal if it is a handshake (opaque payload the
card/panel builds, or a response only the card consumes). **Destructive services
get an entry regardless** — the yaml entry *is* the documentation.

**Five get entries:** `delete_map_image` (destructive override),
`set_dock_event_count`, `get_incomplete_run_log`, `get_trouble_rooms_log`
(all three: forgotten-override-sibling — their siblings have entries),
`resegment_external_run` (mutates learning data; the EXT-1 repair lever).

**Nineteen internal:** the 10 `setup_*` wizard steps, 5 `adapter_config`
handshakes, 4 `mapping_services` blob/geometry calls.

Three of the five are the sibling-omission class already tracked in
[[project_eufy_ism_core_sweep]] — closing them here is not scope expansion.

The rule goes in the **gate's module docstring**, not only the packet: it is the
question a future service author has to answer, and centralizing the question
(not a hand-maintained name list) is the standing preference
[[feedback_centralize_question_not_vocabulary]].

**Count discrepancy flagged, not resolved:** Sonnet said 26 (setup 9 / learning 6),
main-agent extraction says 24 (setup 10 / learning 3). Probable cause: nine
`learning/services.py` constants live outside `const.py` and a `const.py`-only
resolver misreports them as missing. Sonnet reconciles first; any name outside
both tables = STOP and escalate.

**The 8 `map_id` requiredness entries stay ejected** as `blocked_by RP-028`.
Confirmed correct: a narrow requiredness fix that RP-028's `require_map_bucket`
resolver then has to unpick is worse than the bug. RP-032 lands with those 8 still
listed; emptying the allowlist is scoped to the `no_yaml_entry` class only.
