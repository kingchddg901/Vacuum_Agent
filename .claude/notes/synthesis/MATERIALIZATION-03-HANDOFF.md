# Materialization handoff — waves 3–7 (26 + CARD)

**Written 2026-08-01 by the authoring window, FOR the executing window.** Fable
authored the packets and is closed out; the campaign is now per-artifact
write-run-fix work, which is Sonnet-shaped. This file carries the judgment that
does not survive in a packet.

Read alongside: `MATERIALIZATION-01/-02` (what exists and why),
`TRANCHE2-AUTHORING-INPUTS` (7 execution lessons), `REVIEW-03` (dependency
edges). Do not re-read the audit corpus — the packets are the spec.

---

## 1. YOU ARE LICENSED TO STOP AND SAY THE PACKET IS WRONG

This is the most important instruction in the file, so it is first.

A reproducer **inherits its packet's authority**. Once written, it *is* the
closure evidence — the same command before and after, the output diff proving
the repair. That means a proof written faithfully from a WRONG packet
**certifies the wrong packet**, and nothing downstream will catch it.

This is not hypothetical. **RP-013d specified a fix that was a no-op.** Its
`required_behavior` said "job-frozen snapshot wins; live queue only when the job
carries none" — but on a phased job `advance_active_job_phase` has already
overwritten the job's own top-level `queue_room_ids` with the phase it moved
into, so preferring it changes nothing. A faithful from-spec proof would have
asserted the specified AFTER, passed once the no-op landed, and closed a finding
that was still broken.

So: when materializing, if the packet's stated fix would not actually produce
the stated AFTER — **stop, write up why, and escalate.** Do not encode it. Do
not "make it work". You are not a transcription layer; the act of writing the
proof is what tests the spec, and it is the last point where a wrong spec is
cheap to catch.

Escalation target: main agent → Chris.

## 2. Six packets need this scrutiny specifically

Packets whose `required_behavior` DELEGATES — "mirror X", "parity with Y",
"matching the Z" — are where RP-013d hid its no-op. The delegation is only
correct if the thing being mirrored does what the packet assumes, and a from-spec
author has no reason to check. **Read what X actually does before writing the
proof:**

| packet | wave | what it delegates to |
|---|---|---|
| RP-016 | 3 | "mirror upload's layout-awareness" |
| RP-021a | 4 | "mirror phase_runner's existing zone branch" |
| RP-022 | 4 | "parity with the mm branch's existing refusal" |
| RP-026 | 5 | "mirror `_commit_result`'s" map_id equality check |
| RP-028 | 5 | "mirror upload's contract" |
| CARD-6 | 7 | "matching the backend's explicit normalization note" |

For each: open the referenced mechanism, confirm it does what the packet claims,
and state in the proof docstring that you checked. If it does not — §1 applies.

## 3. Every proof gets an adversarial review before its packet is assigned

Non-negotiable, and the reason is measured rather than cautious: a review pass
over the nine wave-2 proofs — **all written by the expensive window** — found
defects in **four of them**, including one that could never have flipped at all
(it asserted on a frozen historical record, which no source change can rewrite).
Model tier does not substitute for this gate.

Review each proof against:

1. **Can it flip?** Does the thing being asserted actually change when the source
   changes? A proof reading a frozen artifact, a hardcoded constant, or a value
   the repair does not touch is dead on arrival.
2. **Is the AFTER what the packet requires — no more?** `_proof_inflight_askers`
   demanded a Lever B pulse the packet never specified; a correct repair would
   have reported UNEXPECTED and invited someone to "fix" the proof.
3. **Are the shapes mutually exclusive?** Both-true is UNEXPECTED by design, but
   only for states actually exercised. Reason about the third state.
4. **Does any message claim more than the proof observes?** `_proof_phase_validity`
   said a run "is learned as an even wall-time split" while observing only the
   record. Faithful where it actuates, unfaithful where it qualifies.
5. **Does another packet depend on an unasserted property?** RP-013f's phase-sum
   needs RP-013b's split to preserve totals; RP-013b's proof computed the sums in
   its `detail` line and asserted only the entry count. Two correct-looking
   repairs, one wrong number.

## 4. Order of work — cheapest first, and NOT by wave

Wave order exists for **repair** sequencing (REVIEW-03). Materialization has no
such constraint: every proof runs against current master, so write them in any
order. Cost tracks **finding count**, not subsystem spread — RP-034 and RP-030
are single-subsystem and carry 21 findings each.

**Batch 1 (open here)** — low on both axes, clusters on `rooms/`:
RP-015 (4 findings) · RP-018 (6) · RP-019 (8) · RP-017 (8), optionally +RP-020 (7).

**Batch 2** — RP-021b (5) · RP-038 (7) · RP-027 (8) · RP-016 (8) · RP-041 (8).

**Batch 3+ — one or two per session:** RP-031 (41) · RP-025 (31) · RP-039 (29) ·
RP-030 (21) · RP-034 (21) · RP-035 (20) · RP-032 (16) · RP-021a (14).

Realistic throughput: **6–8 clustered per fresh window**, 3–4 from the heavy
tail. The full set is 5–6 sessions.

## 5. Harness rules (non-negotiable, `_proof_harness.py`)

- **INERTNESS.** The harness supplies scaffolding only — never implements,
  emulates, or normalizes production behaviour. Every proof drives the REAL
  production function. A harness that "helpfully" corrected something would make
  every proof pass for the wrong reason at once.
- Add typed attributes to `ManagerStub` explicitly, not via `__getattr__`.
  `async_noop()` is assigned per-collaborator on purpose, so every awaited
  collaborator is visible in the proof.
- Already solved, do not rediscover: Python 3.14 idle-loop fallback; `FakeHass`
  must stay hashable-by-identity (HA's `@singleton` lru_caches on hass);
  `H.drain_idle_loop()` runs rather than discards scheduled saves.
- Capture real closures by patching the module's `async_track_*` and invoking
  what production registered (see `_proof_watchdog_wedge`, `_proof_job_progress`
  usage in `_proof_inflight_askers`). Do not reimplement the closure.
- Frozen hardware records are **guards, not subjects** — assert the fixture still
  matches them, then drive production for the flip (`_proof_job_cleaning_total`).

## 5b. FRONTEND REPRODUCERS ARE CI-GATED — the flip contract does NOT transfer

**This gap cost three red CI runs on 2026-08-01 and it was a handoff omission,
not an executor error.**

The Python reproducers live in `.claude/notes/_proof_*.py`: outside the test
suite, run by hand, gitignored, frozen only as evidence. That is WHY they may sit
red until their fix lands — the flip contract depends on it.

A frontend reproducer has none of that freedom. Anything matching
`src/**/*.test.mjs` runs in `npm run test:units` and gates CI on every push.
Committing one red turns the repo red for everyone until the fix ships.

**So when a packet's reproducer is a frontend test, mark each failing case
`todo`:**

    test("[XX-1] the thing that should happen",
      { todo: "CARD-N clause (M) not yet executed - drop this flag as part of the fix" },
      () => { ... });

Node reports a todo failure without failing the run. **Removing the flag is part
of the fix commit**, so the flip appears in the same diff as the repair — which
is stronger evidence than a separate proof file changing verdict.

Leave passing CONTROL cases unflagged; they are what proves the reproducer is
discriminating rather than simply broken.

## 6. Done, per artifact

- Runs in the docker test image with `-e PYTHONPATH=/workspace`.
- Prints the packet's `expected_before` fragments on current master.
- Exits 1 on any UNEXPECTED SHAPE.
- Docstring states the mechanism, and for a §2 packet, that the delegation was
  checked.
- Reviewed per §3 before its packet is assigned.
- Committed and `_freeze.py` re-run (it needs git — run on the HOST, not in the
  container).

Do **not** close ledger findings. Do **not** edit a proof to make a repair pass —
that is how a bad fix gets laundered, and it is the one failure this whole
apparatus exists to prevent.

## 7. Held / out of scope for this phase

- **RP-013c** — blocked on stepped Run B. CORRECTED profile:
  `[room 1] -> charge_wait -> [room 2, room 3] -> [room 4]`, cancel during the
  FINAL phase -- cancelling during the GROUP loses RP-013b's evidence, since a
  phase only captures timing when it FINISHES. Arm `size: 50000`.
- **RP-014** — assignable only after its site table is widened from 5 to 17.
- **RP-042..045 (SYNTH-12, battery)** — hold. `battery/` had one targeted review
  in 2026-06 that CLEARED the exact areas all four defects live in; recommend a
  hostile audit of `battery/` + `sensor/` before executing, or the packets will
  be spot-fixes over an unexamined 3,700 lines.
- **CARD-7** — needs a design session with Chris, not a model.
