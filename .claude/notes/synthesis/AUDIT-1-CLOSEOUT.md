# AUDIT-1 CLOSEOUT — the hostile audit campaign, written up

**Window:** 2026-07-30 → 2026-08-04 · **Status: CLEARED 2026-08-04** — the closing commit
(`4fbb530`) landed the last three worked findings, and the reconciled OPEN-FIX-CHECKLIST
records the campaign as cleared with a short, fully-enumerated remainder (§8). This document
is the narrative record; every number in it was regenerated from the ledgers on 2026-08-04,
not recalled. Companion documents: `.claude/notes/corpus/audit-findings-report.md` (the
frozen corpus), `SYNTH-05-executive-and-registers.md` (synthesis), `AUDIT-2-CHARTER.md`
(what happens next).

---

## TL;DR

Over six days, the entire integration was subjected to a hostile, evidence-driven,
multi-agent audit — 18 heavyweight audits, a targeted-agent tier, and a direct-read tier,
covering every subsystem in the tree. The campaign produced a frozen corpus of **516
records**: 484 verified open findings, 22 killed false leads, 9 carried obligations, 1
acknowledged wontfix. Synthesis collapsed the 484 into **33 repair families** resting on
**eight structural invariants**, was itself adversarially reviewed (which found 14 defects
in the synthesis), and was executed as **60 repair packets** that closed **455 findings**.
The campaign cleared on 2026-08-04. What remains open is not a backlog — it is a named,
typed, triggered remainder of five items, each of which is open *because closing it requires
something specific* (a hardware run, a bench session, a scheduled design pass).

| | |
|---|---|
| Corpus records / verified open findings | 516 / 484 |
| Severity at freeze | 18 CRITICAL · 88 HIGH · 173 MEDIUM · 205 LOW |
| Killed as false or overstated | 22 (kept as negative evidence) |
| Repair families (accepted / rejected) | 33 / 6 |
| Repair packets landed | 60 (RP-001…RP-047 + CARD-1…9) |
| Findings closed by landed packets | 455 |
| Reproducer proof scripts | 61 |
| Packets hardware-validated (Eufy T2351 + Roborock S6) | 5 |
| Measured audit spend (discovery + verification, `claude-opus-5[1m]`) | ~29M subagent tokens |
| Commits in the window | 416 |

---

## 1. Why it ran

The integration had grown fast — multi-brand adapters, live maps, learning/ETA, theming,
zone cleaning, i18n at 18 languages — and the documentation had been hardened to the point
where a disaster-recovery rebuild from docs alone was ~90% viable. The audit was the
adversarial test *of* that claim: assume the docs may be wrong, the code may be wrong, the
tests may encode the wrong contract, or all three may agree on the same flawed assumption.

Mid-campaign, the stakes changed in kind, not degree: on 2026-08-01 the integration was
**accepted into the HACS default store**. "Works on Chris's two vacuums" stopped being the
bar. The field made the point immediately — the first two stranger bug reports (#46, #48)
arrived within 72 hours of the listing, both in the entity-resolution/setup seam, both on
install topologies the builder's own setup never exercises. That seam is now a named
first-class scope in the AUDIT-2 charter.

## 2. Shape of the campaign

- **07-30** — Calibration: one 8-agent hostile audit of the highest-blast-radius subsystem
  (active-job lifecycle + exactly-once finalization). Purpose: measure the real cost of
  auditing one subsystem to completion. Result: ~1.9M tokens / 41 min, and the discovery
  that a full-depth repo siege (~14–18M) was only feasible as a campaign, never one run.
- **07-30 → 07-31** — Audits #2–#6 by behavioural contract (learning persistence, external
  ingestion, adapter contract, error tracker, card/frontend), plus a forgotten-sibling
  sweep. Fixes for these shipped as they were found.
- **07-31** — Audits #7–#18 by subsystem file-scope (dispatch/queue, profiles+planning,
  jobs, rooms, map lifecycle, listeners, services, core hub, integration script, learning
  consumers, themes, mapping services), a 3-scope targeted-agent tier, and 11 direct reads
  of small subsystems (8,709 LOC). Coverage was claimed from **scopes diffed against the
  source tree**, never from findings counts — an unaudited subsystem yields zero findings
  and reads identically to a clean one.
- **07-31 20:38** — Corpus frozen at `5be0931`: 31 SHA-256-digested artifacts committed,
  including the raw agent journals (which later paid for themselves when post-processing
  dropped audit #18's per-finding verdicts and they were recovered from the journal layer).
- **07-31 → 08-01** — Synthesis (484 findings → 33 families), then a hostile review *of the
  synthesis* (REVIEW-01…07), then Gate 4: seventeen product questions put to Chris, all
  answered.
- **08-01 → 08-03** — Execution in waves: 60 packets, reproducer-first, direct to master
  with CI on every push, deployed live to the production HA as testable slices landed.
- **08-04** — Reconciliation and close: the checklist was audited against the code, the
  last five worked findings landed, and the campaign cleared.

Two sessions ran concurrently on the same working tree for most of the window — a
design/authoring session and an execution session — with model tier assigned by **phase
shape**: wide-read synthesis and packet authoring in the expensive window; per-artifact
fix/test loops in the cheap one. The campaign's own rule held: spend capability on
*discovery* (only the strong window can find these), execute repairs from the written spec.

## 3. The method, compressed

Every audit ran the same discipline:

- **Five-dimensional attack model** — static structure, runtime behaviour, time/concurrency,
  topology/environment, evidence-and-user-trust. The last dimension is why findings like
  "unknown is converted into an invented value" rank alongside crashes.
- **Non-negotiable evidence standard** — exact paths, symbols, the contract claimed, the
  behaviour observed, a concrete execution path, the consequence, confidence, independent
  confirmation. A plausible theory is not a finding.
- **Two adversarial verifiers per audit, never economized.** Verifiers were ~22% of spend
  and earned it: in the calibration alone they killed 17 over-reached consequence claims,
  moved 7 severities, and found 2 harms no discovery agent named. Discovery-only output was
  confidently wrong in both directions.
- **Mandatory negative-space reporting** — every agent lists "guards I checked that did NOT
  rescue this" and "areas where I found NO defect". The first suppresses speculation; the
  second is what makes a clean verdict credible.
- **Root-cause dedup** — measured fan-in was 4.5:1 on the worst cluster. One architectural
  problem is not fifteen findings because it surfaces in fifteen services.
- **A killed register, kept forever.** The 22 killed findings are negative evidence — each
  one is a lookalike boundary that stops a repair family from absorbing a finding that only
  resembles it.

Honest bound on evidence depth: 36 of 484 findings (7%) carry *executed* evidence; the rest
were verified by two independent source-reading passes. Raising execution depth is a named
method delta for AUDIT-2 (probes, replay corpus, route tracing), not a retrofit.

## 4. What it actually found — eight invariants, not 484 bugs

The corpus's center of gravity is eight structural invariants violated repeatedly across
subsystems:

1. **Protected windows that don't cover their gate** — the finalize claim window; the
   campaign's hardware-proven CRITICAL.
2. **Absence of evidence consumed as evidence of absence** — empty discovery wipes stores;
   failed reads erase history; unavailable entities satisfy negating rules.
3. **Ownership by string prefix over a non-injective join** — proven cross-vacuum registry
   deletion.
4. **Refusals invisible to callers** — refusal dicts computed and then dropped at
   service/entity/card boundaries; the user sees success.
5. **Identity carried by unstable keys** — numeric segment ids through re-segmentation,
   slugs without uniqueness.
6. **Stale data served as live** — stored ids on a total resolution miss; sticky-hold pose
   with an unread stale flag.
7. **Vocabulary owned by literals instead of the declared catalog** — the brand-ism seam.
8. **Setup without teardown** — loop-lifetime work orphaned across reloads.

Representative single findings, for flavour: a cancel flag read once and then never
re-checked across four awaits, so a cancelled robot returned to base *and then drove back
out*; a dispatch guard with no try/finally, so any raise made the job permanently
un-reapable and blocked every future start; a group-phase run attributing an entire
multi-room phase's time, area and battery to `room[0]`; profile round-trips where one field
used the opposite precedence of every sibling field, so mop profiles failed to match on
every floor except tile.

## 5. The synthesis was audited too

484 findings became 33 families + 3 batch groups + 5 explicit deferrals, with **zero
unassigned findings** (machine-checked in `closure-matrix.json`). Six candidate families
were **rejected by design** — most importantly, no global absent-vs-empty helper and no
vocabulary-constants module: the campaign's own rule is to centralize the *question*, never
the vocabulary, and about half of apparent divergence is deliberate.

Then the synthesis itself went under hostile review — and the review found **14 real
defects in the synthesis**, including two HIGH (a refusal-handling amendment that would have
looped the reaper forever; a slug-migration edge that would have reintroduced a fixed
finding). Verdict: *approve with named amendments*. The 84 findings that carried two
conflicting severities were re-graded by a frozen consequence-based rule, not averaged.

Gate 4 put seventeen numbered product questions to Chris — precedence semantics, collision
suffixes, migration appetite, which hardware runs were worth staging. Every packet
downstream carries those answers instead of a guess.

## 6. Execution: packets, proofs, hardware

Repairs shipped as **specification packets** — each naming its findings, its required
behaviour, its seam, and its reproducer. The rules that mattered:

- **A proof must fail on frozen source for the intended reason before its packet is
  worked.** An adversarial pass over the first nine proofs found defects in four — one of
  which was structurally unable to flip (it hand-simulated the mutation without calling
  production code). Reviewing proofs is not optional at any model tier.
- **A reproducer inherits its packet's authority** — written from a wrong packet it
  certifies the wrong packet. Escalate, never edit a proof to make a fix pass.
- **Landing is proven by `git show --stat`, never by commit subject.** An `RP-047:`-prefixed
  commit turned out to be spec-only; the finding it "closed" was proven still live on
  hardware the same night.

Five packets were validated on physical hardware across both brands, with before/after
captures banked under `_frozen/baseline/`. Hardware validation is deliberately thin here —
it is the *release* gate (fresh per-brand baselines at the pinned build), and the decaying
item is scheduled last by design.

Some findings did not get fixes at all — they got **designs**. The access-graph findings
(A5/A6-AGX) grew into a full design-and-build (a pure graph model, an atomic replace-all
write, the dock gate Chris believed he already had). The group-phase display finding
(#9:A3-REC-3) exposed that a multi-room job pausing to charge had never been *designed*,
and became the Phased Jobs rebuild — held outside this campaign behind a hard scope
boundary, to be sieged as its own subsystem (S4) when declared complete.

## 7. The ledger war — counting turned out to be the hard part

The campaign's most repeated lesson was not about code. It was that **closure state rots in
both directions**, and every failure of the campaign's own bookkeeping got the same
treatment as a code defect:

- A finding was **credited as fixed when only half of it was** (#9:A3-REC-3 — the record
  half landed, the live-display half didn't; a hardware run caught it). That one reopen
  produced the campaign's ledger reform: closure is per *sub-item*, never per packet;
  headers are derived (`OPEN, x of y complete`); blockers are named AND typed
  (hardware/packet/design/upstream/deferred), because the type decides how the item gets
  scheduled.
- The inverse hit on close-out day: of 27 "open" entries, **19 were already fixed** and
  never ticked. A stale ledger manufactures phantom work exactly the way an unaudited scope
  manufactures false health. And the first reconciliation pass was itself wrong twice —
  it used "does the code cite the finding id?" as the test, and two fixes don't. The rule
  that survived: *check the code, not the count, and not the marker either.*
- The generated ledgers still carry a measured uncertainty band (family-credit vs
  explicit-list crediting; both naive repairs were tried and are provably wrong in opposite
  directions). Per-finding adjudication of that band is AUDIT-2 gate-9 work, on purpose —
  not a reason to hand-edit a number today.

## 8. The honest remainder — everything still open, and why

Nothing below is forgotten; each item is open because closing it requires a specific thing:

| Item | State | What closing it takes |
|---|---|---|
| **#9:A3-REC-3** (group-phase live display) | REOPENED; mechanism landed (`6831ccd`, snapshot presents the phase) | one fresh group-phase hardware run confirming the card no longer pins to room[0] |
| **RP-047 remainder** | 1 of 2 complete | same hardware run as above |
| **A4-SETUP-6** (map-scoped rejection) | deferred by decision | scheduled with the multi-map work; fix shape already in the adjudication |
| **ENT-1** (HIGH) / **DIAG-1** (MEDIUM) | ~~banked, release-gating~~ **BOTH LANDED** — see the v2.0.0 addendum below | — |
| **A7-ROBORO-4** | landed narrower than filed | offset is preserved but not applied; applying it is pose registration and needs the S6 on a bench |
| **DR-ONB-2** | fixed, but the method has zero production callers | should be deleted, not maintained as a correct answer nobody asks for |
| **CV segmentor** | excluded by design | correctness is empirical, not textual; this method cannot falsify it |
| **RF-09 multi-device proof** | gate recorded unsatisfied | needs a second Eufy on the fleet or an external tester |

Two findings deserve their asterisks in print: A7-ROBORO-4 and DR-ONB-2 are recorded as
*narrower than filed* rather than as clean fixes — the campaign's value depends on the
ledger saying what actually happened, not what reads best.

### 8b. Addendum — state at the v2.0.0 ship, 2026-08-08

The table above is the state **at campaign close (`4fbb530`, 2026-08-04)** and is left as
written: §1–§7's numbers are a frozen-corpus record, re-verified for this addendum against
`corpus/audit-findings-canonical.jsonl` (516 records / 484 verified / 22 killed — unchanged,
as a frozen corpus should be). What moved is the open list.

| Item | Then | Now (verified for this addendum) |
|---|---|---|
| **ENT-1** (HIGH) | banked, release-gating | **LANDED** `9a37ad6` — companions resolve by DEVICE as well as by derived name |
| **DIAG-1** (MEDIUM) | banked, release-gating | **LANDED** `20c0ab1` — a failed resolution is now distinguishable from an absent capability |
| **RF-36** (battery/charge) | worked during the campaign | **CLOSED**, hardware-verified on two real recharges 2026-08-05; one LOW follow-up (`BATT-CV-1`) open |
| **DR-ONB-2** | fixed, callerless, "should be deleted" | **still callerless** — `check_for_new_rooms` and its manager delegator have zero production callers. Unchanged, and still the right call to delete. |
| #9:A3-REC-3 / RP-047 remainder · A4-SETUP-6 · A7-ROBORO-4 · CV segmentor · RF-09 | — | **unchanged**, each still open for the reason stated above |

Two defects found *after* close deserve recording here, because both are the campaign's own
lesson pointed back at itself:

- **A one-shot store migration conflated "could not evaluate yet" with "completed."** It set
  its done-flag unconditionally, so a cold boot where the vacuum's own integration had not
  finished loading burned the single repair opportunity on zero rooms — silently, since the
  skip logged at DEBUG. This is §4's *"absence of evidence consumed as evidence of absence"*
  invariant in a place the campaign did not look. Found by accident on hardware: two full
  restarts repaired nothing, a config-entry reload repaired all twenty rooms.
- **One physical property was declared under two names and dispatched twice** —
  `clean_intensity` and `path_type`, the second carrying an invalid value on every stored
  room since the initial release. §4's *vocabulary-owned-by-literals* invariant, surviving
  the family that was written to close it (RF-18) because the duplicate predated the
  framework it leaked through.

Neither was reachable from the campaign's scopes as written. Both are AUDIT-2 input.

## 9. What the campaign taught about auditing itself

The most durable output may be methodological. All of it is baked into the AUDIT-2 charter
as explicit attack instructions, not advice:

- **Reproducers go stale silently, in four distinct ways** (moved call site, sibling-fix
  precondition, retired mechanism, earlier refusal — plus a fifth found later: deeper reach
  after repair). Three of the four happen *because something else was fixed correctly*.
  Answer: harness v2 derives admissibility (stub-invocation tracking, no-verdict-fails,
  quarantine rendering, contract versions) — the harness checks, never the author's
  declared diligence.
- **Findings share premises, and a retired premise fells every dependent finding at once.**
  Four verification groups spent ~1.4M tokens re-deriving an empirical claim that had been
  disproved on-device the day before. Findings were deduped by root cause of defect;
  nobody deduped by root cause of *belief*. Answer: a premise ledger, seeded and live.
- **Route by answerability.** If the disputed premise is about what the *device* does, one
  banked observation beats any amount of code reading — 30 re-analyses settled in one
  sentence what 1.4M tokens could not. The reverse guard holds too: observation routes the
  premise, it doesn't excuse skipping the code around it.
- **Read the user guide before assigning severity.** A HIGH finding was adjudicated
  overstated because its harm required a workflow the user guide explicitly does not
  describe — and the fix built from mechanism alone would have deleted hand-made room
  links on the one path users *do* walk. Severity is a claim about use.
- **A green outcome is not route evidence.** The recurring enemy was false agreement about
  which code actually ran. Answers now exist as instruments: trace_route (fallback census +
  three-path fix review) and the recorder-replay corpus — 57 Alfred + 11 Ivy real runs,
  cross-matched 68/68 against the learning archive with zero orphans, now a standing
  concordance gate (`_crossmatch_replays.py --check`) that catches finalizer
  destabilization the whole green test suite cannot.

## 10. What happens next

**The order here was written ambiguously and is corrected as of 2026-08-08.** One audit
closes one epoch, and the release is what closes it — not what follows the next audit:

| | closes | ships as |
|---|---|---|
| **AUDIT-1** (this campaign) | **Epoch 1** | **v2.0.0 — the Phoenix Release**, 2026-08-08 |
| **AUDIT-2** (chartered) | **Epoch 2** | a later release, scope decided at its close |

So Phoenix does **not** wait on AUDIT-2; it is AUDIT-1's shipping point, and AUDIT-2's
attack surface is what Phoenix ships.

**AUDIT-2 — the differential re-siege — is chartered and signed off** (all four decisions
decided; mixed-tier fleet, docs-first, manual trigger, Phased Jobs in scope as S4). It fires
when the 14 readiness gates go green, and its attack surface is precisely this campaign's
output: every repaired seam, every fix diff, everything new since the freeze, and the
reconciled docs. The audit that tore the system down gets audited by its successor.

The release framing was already banked, because it is simply true of the last six days:

> This release was not built by polishing the old system.
> It was built by auditing it, disproving parts of it, preserving the evidence,
> tearing out unsafe assumptions, and rebuilding the critical paths from verified behavior.
> What survived earned its place.
> What failed was replaced.
> What could not be proven was made visible.

The changelog unit is the repair family — ~33 lines of "where it bled → how it's armored,"
each expandable to its packets and commits, generated from the corpus counts themselves.

One line says what the campaign was, in the owner's words:
**"We found everywhere we can see it bleed and armored it."** The bound is honest — *can
see* — and the exclusions, open gates, and deferrals above are that bound, printed.
