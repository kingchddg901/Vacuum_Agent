# Sonnet stage prompts — closing out the campaign

**Written 2026-08-01 by the authoring window.** Each `## Stage` below is a
self-contained prompt: paste it into a fresh Sonnet session. They are ordered,
but only S0 → M1 is a hard edge; the rest can run in any order that suits the
calendar.

Every prompt assumes: repo `C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager`,
docker test image `eufy-vacuum-test`, nothing deployed unless the prompt says so.

**Read `MATERIALIZATION-03-HANDOFF.md` first in every session.** The prompts
below deliberately repeat its §1 licence, because that is the one instruction
that must not be skimmed.

---

## Stage S0 — build the closure mechanism (one-off, do this first)

```
Build the ledger closure mechanism. This is a SMALL ENGINEERING TASK, not
bookkeeping -- read the whole prompt before starting, because the obvious
interpretation is wrong.

Repo: C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager (nothing deployed).

THE SITUATION. docs/dev/maintenance/highly-aggressive-audit.md is GENERATED --
never hand-edit it -- from .claude/notes/_gen_audit_doc.py and _gen_checklist.py.
The ledger describes itself as "every finding NOT yet applied", and the checklist
emits "- [ ] applied [ ] tested [ ] hardware-checked" per finding.

THE PROBLEM. No input carries applied state. _open_findings.json rows are
{run, id, sev, orig, file, line, title, brands, impact} -- no closure field. So
the ledger cannot currently distinguish a finding fixed three weeks ago from one
nobody has touched, and RP-001..RP-012 have landed without the ledger knowing.

THE DERIVATION THAT ALREADY EXISTS. .claude/notes/synthesis/closure-matrix.json
maps each canonical finding id -> its owning family/packet (484 rows,
{canonical_id, finding_id, severity, families, owner}). Each packet in
SYNTH-03/04/06..12 carries finding_ids. So: finding -> packet is already known.
The ONLY missing input is which packets have landed.

FOUR THINGS ALREADY CHECKED FOR YOU -- do not re-derive them, and do not
contradict them without evidence.

(a) _open_findings.json IS AN OUTPUT, NOT A SOURCE. _gen_checklist.py line ~19
    REGENERATES it from the audit JSONs on every run. Put closure state there and
    the next regeneration silently wipes it.

(b) THERE IS ALREADY A PRECEDENT -- MIRROR IT, DO NOT INVENT A SECOND ONE.
    _gen_checklist.py already carries a `wontfix` mechanism: rows with that key
    are filtered out of the fix list and tracked separately, with the reasoning
    "an unmarked wontfix just gets re-litigated". Shape `applied` the same way.
    A parallel mechanism with different semantics is how the next person gets it
    wrong.

(c) COMMIT NUMBERING LIES -- VERIFY AGAINST SOURCE. RP-007's rollback_plan named
    three commits and git log shows only "(1/3)" and "(2/3)". It is NOT
    incomplete: step 7 (the freshness gate) landed folded INSIDE the 2/3 commit
    and is visible at dispatch/manager.py:291, labelled "RP-007 step 7". Had you
    inferred from the numbering you would have flagged a landed packet as open.

(d) EVERY LANDED PACKET LEAVES IN-SOURCE MARKERS. Use this as the cross-check:
    `grep -rl "RP-NNN" custom_components/` returns >0 files for all twelve.
    Baseline counts (files, as of 47a664f) --
      RP-001:1  RP-002:5  RP-003:6  RP-004:1  RP-005:8  RP-006:8
      RP-007:5  RP-008:3  RP-009:9  RP-010:5  RP-011:8  RP-012:7
    Non-zero is NECESSARY, not sufficient (a partial application still leaves
    marks). Where the commit log and the source disagree, READ THE CODE and
    report what you found.

VERIFIED PACKET -> COMMIT MAP (mined and hand-checked; use it, don't re-mine):
  RP-001 3ddcc1c | RP-002 ca6dc75,c2569bf,3875f62 | RP-003 76d92fc
  RP-004 27824be | RP-005 6989031,4217c3c | RP-006 e598e3e,b0967eb,e35b961
  RP-007 4c42482,4bdd3f8 (3 planned, 2 commits -- see (c))
  RP-008 8d244dc | RP-009 6ab1b20
  RP-010 3e9e969,de835ef,d3e6139 | RP-011 365f90b,4cdcf51,7f6b969
  RP-012 7269020,47f9a25,a02fd19,6598b0c
Nothing beyond RP-012 has landed. RP-013a..f, RP-014..041, CARD-1..9 and
RP-042..045 are all OPEN.

WHAT TO BUILD.
1. .claude/notes/_landed_packets.json -- {packet_id, commits[], landed_at, note}.
   Seed from the map above. If you believe a packet landed that is not on it,
   say so with the evidence rather than adding it silently.
2. Teach _gen_checklist.py and _gen_audit_doc.py to derive applied state: a
   finding is APPLIED when its owning packet (via closure-matrix.json) appears in
   _landed_packets.json. Render applied findings DISTINCTLY -- a checked box and
   the commit sha -- rather than removing them. The ledger's value is the audit
   trail, and a disappeared finding is indistinguishable from one never found.
3. THE SAFETY GATE, do not skip it: copy the CURRENT generated
   docs/dev/maintenance/highly-aggressive-audit.md and OPEN-FIX-CHECKLIST.md
   aside BEFORE touching the generators. After regenerating, diff against the
   copies and confirm the ONLY changes are applied-markings. Any other diff means
   you changed the generator's behaviour by accident -- stop and investigate.
   Report the before/after open counts.

PIPELINE ORDER IS LOAD-BEARING: _gen_corpus.py reads from _frozen/, so the
sequence is FREEZE -> GENERATE -> FREEZE AGAIN. Running generate after editing a
live source silently emits the OLD corpus with VALIDATION PASS. Run
`python .claude/notes/_freeze.py` on the HOST (it shells out to git; it fails
inside the container).

Gate: docker pytest tests --no-cov -p no:cacheprovider (expect 3094+).
Commit as "audit: derive ledger closure state from landed packets".
Do NOT hand-edit the generated ledger. Do NOT mark anything landed that you
cannot point at a commit for.
```

---

## Stage M1 — materialize reproducer batch 1 (rooms cluster)

```
Materialize five reproducers for the eufy_vacuum audit campaign.

Repo: C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager (nothing deployed).

FIRST: read .claude/notes/synthesis/MATERIALIZATION-03-HANDOFF.md in full, then
MATERIALIZATION-02 (worked examples) and TRANCHE2-AUTHORING-INPUTS (7 lessons).
Do NOT read the audit corpus -- the packets are the spec.

YOUR PACKETS (in .claude/notes/synthesis/SYNTH-07-packets-wave3.md):
  RP-015 (4 findings) · RP-018 (6) · RP-019 (8) · RP-017 (8) · RP-020 (7)
They cluster on rooms/, so read that source once and reuse it across all five.

FOR EACH: write .claude/notes/_proof_<name>.py using the shared harness
(.claude/notes/_proof_harness.py). It must print the packet's expected_before
fragments against current master, declare a mutually-exclusive AFTER shape, and
exit 1 on UNEXPECTED SHAPE. Run it:

  docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace"
    -w /workspace -e PYTHONPATH=/workspace eufy-vacuum-test
    python .claude/notes/_proof_<name>.py

YOU ARE LICENSED TO STOP AND SAY THE PACKET IS WRONG. A reproducer inherits its
packet's authority -- written faithfully from a wrong packet it CERTIFIES the
wrong packet, and nothing downstream catches it. RP-013d specified a fix that was
provably a no-op; a from-spec proof would have passed once the no-op landed and
closed a still-broken finding. If a packet's stated fix would not produce its
stated AFTER: STOP, write up why, escalate. Do not encode it, do not make it work.

THE HARNESS RULE: it supplies inert scaffolding only -- never implements,
emulates or normalizes production behaviour. Every proof drives the REAL
production function. If you find yourself writing an `if` that decides a DOMAIN
question in the harness, it belongs in the proof.

WHEN ALL FIVE REPRODUCE, review them against handoff §3 before committing:
can each actually flip? does the AFTER assert what the packet requires and no
more? are the shapes exclusive? does any message claim more than the proof
observes? Fix what the review finds and say what it found.

Commit as "audit: wave-3 reproducers RP-015/017/018/019/020" with the
Co-Authored-By line, then run `python .claude/notes/_freeze.py` on the HOST and
commit the freeze. Do NOT close ledger findings.
```

---

## Stage M2 — reproducer batch 2

Same prompt as M1, substituting:

```
YOUR PACKETS: RP-021b (5 findings, SYNTH-08) · RP-038 (7, SYNTH-10) ·
RP-027 (8, SYNTH-09) · RP-016 (8, SYNTH-07) · RP-041 (8, SYNTH-10)

EXTRA SCRUTINY -- RP-016 DELEGATES ("mirror upload's layout-awareness"). Open
what upload actually does and confirm it does what the packet assumes BEFORE
writing the proof; state in the docstring that you checked. Delegation is where
RP-013d hid its no-op.
```

## Stage M3 — mid-weight batch

```
YOUR PACKETS: RP-022 (10) · RP-033 (10) · RP-028 (11) · RP-023 (11) ·
RP-029 (12) · RP-036 (12)

EXTRA SCRUTINY -- RP-022 ("parity with the mm branch's existing refusal") and
RP-028 ("mirror upload's contract") both DELEGATE. Read the referenced mechanism
first; confirm in the docstring.

RP-026's VERIFY-FIRST GATE IS ALREADY CLEARED -- do not re-run it and do not
treat the packet as blocked. Resolution is recorded inline in the packet
(2026-08-01, against the live install): fork robovac_mqtt 1.13.1 carries
EufyCleanCoordinator.device_id (coordinator.py:85), and the device registry gives
the deterministic key -- vacuum.alfred -> ("robovac_mqtt", "AFC96X0F33201054"),
matching coordinator.device_id, published by the coordinator itself at
coordinator.py:200. Roborock has the identical shape
(vacuum.ivy -> ("roborock", "57R4...")), so use ONE identity mechanism for both
halves rather than a Eufy lookup plus a separate Roborock one.
```

## Stage M4 — heavy tail (one or two per session, not six)

```
YOUR PACKETS: pick ONE or TWO of --
  RP-031 (41 findings) · RP-025 (31) · RP-039 (29, extends _proof_manager_reload)
  RP-030 (21) · RP-034 (21) · RP-035 (20) · RP-032 (16) · RP-021a (14) ·
  RP-024 (13) · RP-026 (13)

These carry 3-5x batch-1's finding load. Do not attempt more than two in one
session; a rushed proof that cannot flip is worse than no proof.

EXTRA SCRUTINY -- RP-021a ("mirror phase_runner's existing zone branch") and
RP-026 ("mirror _commit_result's map_id equality check") DELEGATE.

RP-035 is sensor/-only and RP-032 is services/-only: single-subsystem does NOT
mean cheap here, it means one file with twenty findings in it.

NOTE on RP-035: sensor/ WAS covered -- by the campaign's direct-read tier plus a
1-agent "sensor leftovers" pass (see the coverage table in
corpus/audit-findings-report.md). It carries 14 direct-read findings including
three HIGH (SN-1, SN-2, SN-3), which live in _direct_reads.json -- a SEPARATE
index from _open_findings.json, never merged. Check BOTH before concluding
anything is untracked.
```

## Stage M5 — CARD reproducers (frontend gates differ)

```
YOUR PACKETS: CARD-1..CARD-9 in
.claude/notes/synthesis/SYNTH-11-packets-wave7-card.md

CARD-7 is EXCLUDED -- it needs a design session with Chris, not a model. Skip it
and say so in your summary.

Frontend work edits src/, never the built bundle. Extra gates beyond the python
suite: `npm run test:units`, `npm run check:i18n`, `npm run build:deploy`.
Every user-facing string routes through i18n AT CREATION, all 18 locale packs --
no exceptions, and check:i18n will fail the build otherwise.

EXTRA SCRUTINY -- CARD-6 DELEGATES ("matching the backend's explicit
normalization note"). Read the backend note first.
```

---

## Stage M6 — RP-040, the closing batches (75 members, 37 files)

```
Execute RP-040 for the eufy_vacuum audit campaign -- the closing batches.

Repo: C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager (nothing deployed).

WORK FROM THE GENERATED TABLE, NOT THE PACKET'S finding_ids:
  .claude/notes/synthesis/RP-040-batch-table.md
It carries the mechanism, file, line and impact for all 75 members, grouped by
file -- which IS the commit grouping the packet's rollback_plan calls for. The
packet's own finding_ids field is prose pointing at this table; it was generated
2026-08-01 precisely so you never open the audit corpus. Read the packet in
SYNTH-10 for required_behavior and stop_conditions, then work the table.

Regenerate it if you suspect drift: python .claude/notes/_gen_batch_table.py

NOT EVERY MEMBER GETS A PROOF. The table's gate column is authoritative:
  BATCH:SMALL-CORRECTNESS (48) + -2 (11) -> behaviour-bearing; these are the
    ones that belong in a table-driven _proof_closing_batch.py
  BATCH:DOC-ONLY (8)   -> mkdocs --strict, NO proof case
  BATCH:DEAD-CODE (8)  -> the evidence is the full suite still passing after
    the deletion, NO proof case
Adding a proof case for a doc correction is noise that makes the real cases
harder to read.

THE PACKET'S OWN STOP CONDITION, which matters more here than anywhere else:
"any batch member's one-line fix turns out to need design -- eject it to a named
follow-up, do NOT improvise." A6-PRE-1 was already ejected this way (to RP-041,
per Q20) and is deliberately absent from the table. Expect one or two more; a
batch of 75 one-liners that all stay one-liners would be surprising. Ejecting is
success, not failure.

Q10 is the one PRODUCT item in here and is spelled out verbatim in the packet:
setup_reject_rooms requires map_id and routes through the same protection/
confirmation standard as the other destructive setup actions, plus a
setup_unreject_rooms service that reverses it, registered and unregistered
symmetrically. Any user-facing string is i18n AT CREATION, all 18 locale packs.

Q8 is a deletion: repairs.py and its references go.

Gates: docker pytest tests --no-cov -p no:cacheprovider, mkdocs --strict for the
doc members, frontend gates only if you touch src/.
Commit BY FILE. Do NOT close ledger findings.
```

---

## Stage X — EXECUTION RELEASE: the five packets whose reproducers already exist

**This is the ready-to-run execution work. Everything here has a materialized,
reviewed reproducer in hand — no materialization needed first.** Run the packets
in the order below; the order is chosen to respect file contention and the one
hardware block, not the packet numbering.

| # | packet | reproducer | files it edits | why here |
|---|---|---|---|---|
| 1 | **RP-013b** | `_proof_group_allocation.py` | `jobs/phase_runner.py` | no contention with anything; unblocks #2 |
| 2 | **RP-013f** | `_proof_job_cleaning_total.py` | `learning/job_finalizer.py`, `learning/utils.py` | its phase-sum DEPENDS on RP-013b preserving group totals — must follow it |
| 3 | **RP-013e** | `_proof_recorder_scope.py` | `jobs/active_job.py`, `listeners/job_metrics.py` | no contention |
| 4 | **RP-013a** | `_proof_phase_validity.py` | `step_types.py`, `planning/run_plan.py`, `learning/history_store.py` | hardware precondition SATISFIED by stepped Run A; first of the history_store ladder |
| 5 | **RP-013d** | `_proof_completed_evidence.py` (cases 3–4) | `learning/history_store.py` | rebases on #4's edits |

**RP-013c is NOT in this list** — it needs stepped Run B and stays held. When
Run B lands it rebases on #4 and #5's `history_store` edits.

**RP-014 is NOT in this list** — its reproducer exists and passes, but its
per-site adjudication table names 5 hand-inlined `{"started","paused"}` sites
when there are 17. Widen the table before executing, or 12 sites ship
unadjudicated and look blessed.

### The gotcha that will otherwise look like a failure

**RP-013c and RP-013d SHARE one proof file.** `_proof_completed_evidence.py`
carries four cases: 1–2 belong to RP-013c, 3–4 to RP-013d. So after you land
RP-013d correctly the file reports **2 BEFORE · 2 AFTER**, not 4 AFTER. That is
the CORRECT outcome. Do not "fix" the two BEFORE cases — they are RP-013c's, and
RP-013c is blocked on hardware. Read each case's name before concluding anything
failed.

Case 4 is also the load-bearing one for RP-013d: case 3 (atomic job) would have
been satisfied by the packet's ORIGINAL — and wrong — required_behavior. Case 4
(phased, post-advance) is the one that only passes with the union-of-all-phases
ladder the packet now specifies. If case 4 does not flip, the fix is the old
no-op and you should stop.

### Per-packet, use the Stage E template below

...with one addition specific to this batch: after EACH packet lands, re-run the
OTHER four proofs. They touch overlapping subsystems and a repair that quietly
breaks a sibling's reproducer is exactly what the batch ordering exists to
surface. All five must remain in a declared shape (BEFORE or AFTER); any
UNEXPECTED anywhere means stop.

Run all five at once with the committed batch runner (do NOT hand-write a bash
-c one-liner — PowerShell mangles the quoting):

  docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace"
    -w /workspace -e PYTHONPATH=/workspace eufy-vacuum-test
    bash .claude/notes/_proof_run_batch.sh

It prints one verdict line per proof and exits non-zero if any proof crashed or
reported UNEXPECTED. Pass proof names as arguments to run a different set.

VERIFIED BASELINE, 2026-08-01 at master (nothing in this batch landed yet) —
this is the exact output, so any difference before you start means something
moved and you should find out what:

  [rc=0] === RP-013b: 2 BEFORE (2 cases) ===
  [rc=0] === RP-013f: 3 BEFORE (3 cases) ===
  [rc=0] === RP-013e: 3 BEFORE (3 cases) ===
  [rc=0] === RP-013a: 2 BEFORE (2 cases) ===
  [rc=0] === RP-013c/d: 4 BEFORE (4 cases) ===

Expected at the START of this batch (nothing landed yet):
  RP-013b 2 BEFORE · RP-013f 3 BEFORE · RP-013e 3 BEFORE
  RP-013a 2 BEFORE · RP-013c/d 4 BEFORE
Expected at the END (all five landed, RP-013c still held):
  RP-013b 2 AFTER · RP-013f 3 AFTER · RP-013e 3 AFTER
  RP-013a 2 AFTER · RP-013c/d 2 BEFORE · 2 AFTER

---

## Stage E — execution template (one packet, one session)

```
Execute packet <RP-NNN> for the eufy_vacuum audit campaign.

Repo: C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager (nothing deployed).

Read the packet in .claude/notes/synthesis/<its SYNTH file>. It is the spec:
required_behavior, prohibited_changes, rollback_plan (respect the commit split --
it exists so a bad landing is revertable in one piece), tests_to_add_or_modify.

VERIFY WITH THE REPRODUCER -- same command before and after; the output diff IS
the closure evidence:

  docker run --rm -v "C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager:/workspace"
    -w /workspace -e PYTHONPATH=/workspace eufy-vacuum-test
    python .claude/notes/<its _proof_*.py>

  Before: the packet's expected_before fragments.
  After:  every case reports AFTER.
  Exit 1 / UNEXPECTED SHAPE means STOP and report -- DO NOT EDIT THE PROOF.
  Editing a proof to make a repair pass is how a bad fix gets laundered, and it
  is the one failure this whole apparatus exists to prevent.

superseded_tests: where the packet changes an ASSERTED contract, update the named
tests WITH the decision recorded in the docstring. That is distinct from a
fixture asserting fiction -- there, fix the fixture, never weaken the assertion,
and report which caller it modelled.

Full gate: docker pytest tests --no-cov -p no:cacheprovider (bare pytest SKIPS
tests/adapters -- use --no-cov). Frontend gates if src/ is touched.
Commit per the rollback_plan with the Co-Authored-By line.
Do NOT close ledger findings -- S0's mechanism does that from landed packets.
```

Sequence execution by REVIEW-03's dependency edges. Known edges: RP-013a →
RP-013c → {RP-013b, RP-013d, RP-013e}; RP-013f rebases on RP-013b (its phase-sum
depends on allocation preserving totals); RP-028 → RP-029.

---

## Held — do NOT stage these

| item | blocked on |
|---|---|
| RP-013c | stepped Run B (cancel mid-phase-2 after the charge). Arm capture `size: 50000` -- the default 3000 evicted most of Run A. Include a `[room, room]` group phase so RP-013b gets hardware coverage the same session. |
| RP-014 | its site table says 5 hand-inlined `{"started","paused"}` sites; there are 17. Widen before assigning. |
| RP-042..045 (SYNTH-12) | `battery/` was covered by the direct-read tier, which found 2 LOW while live observation found 4 more incl. a HIGH. Promote it a tier before executing, so the packets are written against depth the read could not reach. RP-042 alone is defensible first — its accumulator takes fresh damage on every dropout. |
| CARD-7 | design session with Chris. |
| HC batches | hardware windows, not model work. |
