# Sonnet handoff — 2026-08-02

Written by the Opus window that closed out materialization. Supersedes the "what's next"
sections of `SONNET-STAGE-PROMPTS.md`; the stage prompts themselves still stand.

**Do not copy counts out of this file into other docs.** Regenerate:
`python .claude/notes/_gen_checklist.py` and `python .claude/notes/_gen_repro_status.py`.
Two docs already drifted by hardcoding numbers — see "rules that changed" below.

## Standing (generated 2026-08-02)

| | |
|---|---|
| Packets landed | **20 of 60** |
| Findings applied | **166** |
| Findings open | **285 singles** + 17 open clusters (12 fully applied) + 9 carried |
| Reproducers named by packets | 44 — **all present, 0 missing** |
| Landed packets missing a reproducer | **0** |
| Hardware-validated | 5 of 20 (RP-013a/b/d/e/f) |

**Materialization is DONE.** Every packet that names a reproducer has it. Nothing shipped
without evidence. What remains is execution.

## Ready now — 30 packets, no unmet blocker, reproducer present

Do the UNBLOCKERS first: each one releases a CARD packet or another RP that is otherwise
stuck. Ordered by downstream fan-out, then by self-containment.

**Tier 1 — unblockers (each releases something):**

| packet | releases |
|---|---|
| RP-031 | CARD-1 |
| RP-020 | CARD-5 |
| RP-021a | CARD-6 |
| RP-019 | CARD-7 (also needs Chris's design session) |
| RP-034 | CARD-9 |
| RP-026 | RP-027 → then CARD-2 |
| RP-024 | RP-025 |
| RP-028 | RP-029, and the 8 `map_id` rows RP-032 left listed |
| RP-015 | RP-018 |

**Tier 2 — trivial wins, take them whenever a session has spare room:**
CARD-4 (three untranslated strings), CARD-3, CARD-8.

**Tier 3 — self-contained, no dependents:** RP-014, RP-016, RP-017, RP-022, RP-023,
RP-030, RP-033, RP-035, RP-036, RP-037, RP-038, RP-039, RP-041, RP-021b.

**Tier 4 — the battery family (RF-36).** All four proofs exist. Sequence matters:
RP-042 → RP-043 → RP-044 (RP-044 extends RP-043's function and its proof). RP-045 is
independent. RP-042's evidence_live carries a CORRECTION — do not restore the deleted
repair-pass clause; MAX_DELTA_PCT already protects the accumulator and the live numbers
are honest.

## Blocked — 10, each with its named unblock

| packet | waiting on |
|---|---|
| CARD-1 | RP-031 |
| CARD-2 | RP-027 (its RP-013 half is now satisfied — all RP-013x landed) |
| CARD-5 | RP-020 |
| CARD-6 | RP-021 |
| CARD-7 | RP-019 **+ a design session with Chris** — not schedulable by you |
| CARD-9 | RP-034 |
| RP-018 | RP-015 |
| RP-025 | RP-024 |
| RP-027 | RP-026 |
| RP-029 | RP-028 |

## Not packets — open work that has no home yet

1. **RP-032's last 8 rows.** The `map_id` requiredness entries stay ejected as
   `blocked_by RP-028`. RP-032 cannot empty its allowlist until RP-028 lands. Expected,
   not a gap.
2. **DOCK-fault finding** — `FINDING-error-seconds-zeroes-runs.md`. Five station faults
   zeroed a productive run's `cleaning_time_seconds` while `used_for_learning: true`.
   Needs a packet. Chris: "not a scope expansion, a new bug to fix later."
3. **Card-cancel finding** — `FINDING-card-cancel-bypasses-seam.md`. The card fix LANDED
   (`7f1f462`), but three items are still open and written up there: `cancel_detection`
   receives `expected_room_minutes: 0.0` while the estimate says 1.4 in the same record;
   Dock-during-an-active-job reproduces the same bad record by another route (design
   call, not a repair); `pause_active_job`/`resume_active_job` have no callers in `src/`
   and nobody has checked whether that is a defect.
4. **RP-013c hardware.** Landed and confirmed for clauses 2/3 on
   `job_2026-08-02T01-31-46`, but clause 4 (overlap-only clear) is untested and clause 1
   needs a re-run after `6419254`. Chris runs these; do not mark RP-013c
   hardware-validated until he does.

## Rules that changed this session — read before executing

- **RUN THE REPRODUCER, NOT JUST PYTEST.** RP-013c's fix-up shipped an over-credit bug
  that marked never-run rooms completed. The full suite (3146 tests) stayed GREEN;
  `_proof_completed_evidence.py` reported `UNEXPECTED SHAPE`. A passing suite would have
  shipped it. The proof is the gate.
- **Check the ORPHANS list in `REPRODUCER-STATUS.md` before writing anything.** Several
  packets name a file that already exists under another name, and several existing
  proofs are deliberate PARTIAL slices that declare what they do not drive.
- **Centralize the QUESTION, not the vocabulary.** RP-013c's fix-up had two sites compute
  "which rooms are complete" with different ladders; they disagreed on real hardware.
  Fixed by one shared `known_completed_room_ids()`. If you find yourself writing the same
  derivation twice, stop.
- **`cancelled` in CI means superseded, NOT failed.** All workflows run
  `cancel-in-progress: true`. Only `failure` is red. Your local suite is the green
  signal; push once per packet if you want an uncancelled run.
- **Reachability is not covered by any audit.** Two 8-agent audits passed
  `cancel_active_job` as correct; nothing called it. Before trusting that a service
  works, grep for its call sites.
- **Never hardcode a count in prose.** `MATERIALIZATION-03-HANDOFF.md` said "26
  reproducers" when the real number was 10, and `OPEN-FIX-CHECKLIST.md` asserted "no
  hardware validation" while the captures sat in `_frozen/baseline/`. Both now derive.
