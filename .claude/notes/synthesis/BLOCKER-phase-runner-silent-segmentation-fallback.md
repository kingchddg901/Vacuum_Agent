# BLOCKER — the group-phase segmentation fallback is SILENT, so the flight recorder captures nothing

**For whoever owns `jobs/phase_runner.py` + `learning/job_segmenter_engines.py`.**
Evidence and a requirement. **No patch is proposed here** — the RP-042 handoff's
suggested guard was inverted (`is None or level >= target` would have made a dead
sensor skip the charge entirely), so this note deliberately stops at "what is
true" and "what must become observable".

Raised 2026-08-03 from a live Alfred run, by Claude (execution session), which is
staying out of the file per the standing ownership split.

## 1. What the hardware run showed

`pj_2026-08-03T17-22-18` — `[Kitchen] → wait → [Entryway + Home Office]`, the same
group-phase shape and the SAME two rooms (8, 9) as the run that originally
reopened `#9:A3-REC-3`.

**The live path is fixed.** The card advanced Entryway ✓ (3.5 min) → Home Office ▶
inside the single group phase. RP-047 (a) (`6831ccd`) holds on hardware. Screenshot
evidence taken mid-phase.

**The write path did not move.** `job_2026-08-03T17-22-18.phase2.json` is not
similar to the failing record, it is identical in shape:

| field | 08-02 (the failure) | 08-03 (today) |
|---|---|---|
| `allocated` | `true` | `true` |
| `allocation_group_size` | `2` | `2` |
| `cleaning_seconds` | 195 / 195 | 195 / 195 |
| `boundary` | `"phase"` | `"phase"` |
| `cleaning_start` | shared | shared (`00:27:48`) |
| `cleaning_end` | shared | shared (`00:35:11`) |
| `cleaning_wall_seconds` | 443 / 443 | 443 / 443 |

Both members share ONE start and ONE end: the phase was recorded as a single
undivided block, then halved arithmetically (390 ÷ 2). The card meanwhile observed
Entryway at ~210s. **The boundary existed at runtime and was discarded at
finalize.** `has_attribution_disagreement` is `False`, so nothing flagged it.

So `_segment_group_room_timing` returned `None` and the caller apportioned.

## 2. What is already ruled OUT

- **Gate 1, `honors_clean_order`.** The unified predicate
  (`adapters/registry.py:658`, landed `408d562`) is default-True — only a literal
  `False` opts out — and the Eufy adapter declares no override. Gate 1 passed.
  `408d562` is NOT implicated.
- **Starved input.** `room_timings` carries `area_m2` 2.0 + 2.0, so the slice had
  area data. (Note separately: job-level `cleaning_area_m2` reads `0.0` while the
  room rows sum to 4.0 — those two disagree, which may be its own defect.)

That leaves **gate 2** (`len(segments) != n`), the **baseline check**
(`base_ct`/`base_area` None), or **gate 3** (reconciliation).

## 3. THE BLOCKER — it cannot be narrowed further, by construction

`_segment_group_room_timing` (`jobs/phase_runner.py:912-1035`) has **seven
`return None` paths and one log line**, and that line is `_LOGGER.exception`,
which fires only if the segmenter *raises*. Every gate bail-out is silent:

| line (abs) | bail-out | emits |
|---|---|---|
| 957 | gate 1 — `not adapter_honors_clean_order(...)` | nothing |
| 969-970 | segmenter raised | `_LOGGER.exception` ✅ |
| 972 | **gate 2** — `len(segments) != n` | nothing |
| 988 | baseline — `base_ct is None or base_area is None` | nothing |
| ~1023, ~1025 | **gate 3** — reconciliation | nothing |

**Consequence: triggering the debug flight recorder on a group-phase run will
capture nothing about this.** `debug_capture.py` is a log ring
(`_RingHandler` on the package logger tree) — it records log records and nothing
else. If the code does not emit, the recorder cannot capture. The only other raw
sample source, `eufy_current_room_probe_vacuum_alfred.jsonl`, is dead: no code
references it and it ends 2026-06-20.

A capture run today produces another 195/195 record with no explanation. That is
a wasted hardware cycle.

## 4. RESOLVED 2026-08-03 — `fabddc9`, and deployed

Chris directed the deferred trace system be applied to `phase_runner` +
`lifecycle` immediately, which lifts the ownership boundary for this work. The
requirement below is now **met**: `decision_log.emit()` records every gate. On a
capture run the log now answers "which gate, and by how much" directly —

```
[phase.capture.slice]   {"rooms":[8,9],"slice_samples":N,"usable":N,...}
[phase.segment.begin]   {"engine":"...","rooms":2,"samples":N}
[phase.segment.reject]  {"expected":2,"gate":"count","got":N}     <- the answer
[phase.timing.apportion]{"parts":[195,195],"whole_seconds":390}
```

`gate` is one of `order` / `engine_raised` / `count` / `baseline` /
`reconcile_seconds` / `reconcile_area` / `no_vacuum_id` — the last of which was
not even in the original count of silent paths; segmentation is skipped outright
when `vacuum_entity_id` is empty, and that was previously indistinguishable from
a gate rejection.

**Next group-phase run with the flight recorder on will name the cause.** Nothing
below needs doing; it is kept as the record of what was asked for and why.

## 4a. The original requirement

Before the next group-phase capture run, each silent bail-out needs to emit at
DEBUG, carrying the value that discriminates it:

- gate 2 — `len(segments)` **and** `n` (is it 1, 3, 0?)
- baseline — which of `base_ct` / `base_area` was `None`
- gate 3 — the reconciliation delta and both sides of it
- gate 1 — the resolved predicate value (cheap, and rules itself out permanently)

Message shape and placement are the owner's call. The only hard requirement is
that after a capture run, the log answers **"which gate, and by how much"**
without anyone re-deriving it from a 50/50 split.

## 5. Why the test suite is green through this

Core tests use a fake/stub segmenter by design (engine-agnostic core;
`tests/adapters/eufy/` holds the real CV/counter tests). So the **gates** are
exercised while the real `eufy_counter_v1` never meets a real counter stream.
The mock agrees with the caller. `_proof_group_allocation.py` reports 2 AFTER for
the same reason — it proves the apportioning arithmetic, not the observation.

## 6. Ledger impact — do not close on the strength of (a)

`#9:A3-REC-3` stays **REOPEN** and C4 stays **3/4**. C4's title is *"a multi-room
phase is recorded as ONE room"* — the RECORD is exactly the half that did not
move. AUDIT-2-CHARTER gate 2 already carries this instruction; this note is its
evidence.
