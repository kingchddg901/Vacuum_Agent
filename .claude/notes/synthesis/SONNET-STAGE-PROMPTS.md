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

WHAT TO BUILD.
1. .claude/notes/_landed_packets.json -- a list of {packet_id, commit, landed_at,
   note}. Seed it from git history with the packets that HAVE landed: RP-001
   through RP-009 (tranche 1), RP-010, RP-011, RP-012 (a/b/c/d). Find each
   commit with `git log --oneline --all --grep="RP-0"`. Do NOT guess -- if a
   packet id has no commit, leave it out and report it.
2. Teach _gen_checklist.py and _gen_audit_doc.py to derive applied state: a
   finding is APPLIED when its owning packet (via closure-matrix.json) appears in
   _landed_packets.json. Render applied findings distinctly -- a checked box and
   the commit sha -- rather than removing them; the ledger's value is the audit
   trail, and a disappeared finding is indistinguishable from one never found.
3. Regenerate both documents and confirm the counts move by the expected amount.

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

NOTE on RP-035: sensor/ (1,595 lines) has ZERO audit findings and no review doc
-- it is genuinely uncovered. Treat anything you notice there as a potential new
finding and report it rather than assuming it is known.
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
| RP-042..045 (SYNTH-12) | `battery/` had one targeted 2026-06 review that CLEARED the exact areas all four defects live in. Audit `battery/` + `sensor/` first, or these become spot-fixes over an unexamined 3,700 lines. |
| CARD-7 | design session with Chris. |
| HC batches | hardware windows, not model work. |
