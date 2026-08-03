# AUDIT #2 CHARTER — the post-repair hostile re-siege

**Status: PREP — awaiting Chris's sign-off on the open decisions in §6. Do not fire until every
gate in §2 is green.** Written 2026-08-02 from live repo state (regenerated ledgers, not
recollection).

## 1. What this is and why it exists

Audit #1 (audits #1–#18 + calibration) tore the pre-repair system down and produced the 484-finding
corpus. Since then: ~25+ repair packets landed, the Phased Jobs subsystem is being rebuilt from
scratch, and a full doc-reconciliation pass is planned. Audit #2 is the **verification siege that
the Phoenix Release (v2.0.0) claims are true**: the repaired seams actually hold, the fixes did not
mint new defects, and the updated docs describe the system that now exists. The audience stakes
changed mid-campaign — the integration is in the **HACS default store** — so "works on Chris's
vacuums" is no longer the bar.

Audit #2 is NOT a rerun of audit #1. It is a **differential siege**: the attack surface is
(a) every repaired seam and its blast radius, (b) the fix diffs themselves, (c) code that is new
since the #1 snapshot, and (d) doc-vs-source across the freshly updated docs. Unrepaired,
unchanged, previously-clean areas get a targeted look, not a second full excavation.

## 2. Readiness gates — ALL must be green before firing

Verified state as of 2026-08-02 (regenerate everything before firing; an audit is a snapshot, not
a ledger):

1. **Open fix packets landed.** Still open today: RP-017 (unblocked by RP-016), RP-021b, RP-023,
   RP-033, RP-035, RP-036, RP-038, RP-039, RP-041 (Tier 3), and RP-043/044/045 (battery — only
   RP-042 of the RF-36 family has landed; `623372a` is the *authoring* commit, not a fix).
   Check with `git log --oneline --all -E --grep="^RP-XXX[ :(]"` — the colon-only anchor misses
   titles like `RP-042 (RF-36 part 1): …`, and an `audit:` prefix means authoring, not landing.
2. **RP-047 executed AND its named proof written** (`_proof_group_live_progress.py`).
   CORRECTION 2026-08-02: `a193eae` is SPEC-ONLY (only SYNTH-12 changed; `current_room_ids`
   exists nowhere in code) — the packet is fully open, proven live by the Alfred group-phase
   run pj_2026-08-02T23-04-45 still pinning the card to room[0]. A `RP-XXX:`-prefixed subject
   can still be authoring — verify landings with `git show --stat` (code files changed), never
   by subject alone.
3. **RP-016 follow-ups closed or visibly deferred:** ZONE-C-2 (delete_saved_zone referrer pruning)
   and IO-6 (get_paths rename-detection). Same for every landed packet's documented partial-slice
   remainders — read each packet's own landing commit message.
4. **Held items adjudicated** (land / defer-visibly / wontfix-with-reasoning): RP-013c stepped
   Run B, RP-014 (site table widening 5→17), CARD-7 *implementation* (only the design sign-off
   `8cdd3ef` exists in the log — verify whether code landed).
5. **Ledger reconciliation:** the REOPENED finding `#9:A3-REC-3` in OPEN-FIX-CHECKLIST.md may be
   closed by RP-047 (`a193eae` is exactly its "record the phase as a phase" half) — reconcile
   before the audit snapshots the ledger, or the audit inherits a stale reopen.
6. **Phased Jobs / `learning/` disposition declared** — see decision Q1 in §6. Either Chris
   declares the rebuild COMPLETE (then it enters scope as its own heavyweight) or it is
   hard-excluded and the exclusion is named in every coverage report.
7. **The doc update has landed** and `python -m mkdocs build --strict` is green. Firing the
   doc-vs-source dimension before the reconciliation pass just rediscovers known drift and drowns
   the verifiers.
8. **All gates green at a pinned SHA:** docker `pytest tests --no-cov` (the real gate; bare pytest
   skips `tests/adapters/`), `npm run test:units` (check the tally, not the exit code),
   `npm run check:i18n`, `npm run build:deploy`, mkdocs `--strict`, CI green on that SHA (match
   `headSha` manually — the `--commit` filter has lied before).
9. **Regenerate every derived ledger at the pin:** `_gen_repro_status.py`, `_gen_audit_doc.py` +
   `_gen_checklist.py`, closure matrix. Never carry a count forward in prose.
10. **Clean audit checkout.** Two sessions share this working tree and the other session's
    uncommitted files are routinely present. The audit MUST run against a dedicated
    `git worktree add` at the pinned SHA — never against the shared tree — or the evidence is
    contaminated by in-flight edits.
11. **Model verified in the session that runs it.** The #1 calibration was accidentally measured on
    `claude-opus-5[1m]` because a scheduled task took the configured default, not the interactive
    `/model` choice. Set/verify the default before any scheduled run.
12. **Hardware baselines banked post-fix:** at least one fresh captured run per brand (Alfred,
    Ivy) at the pinned build, stored under `_frozen/`, so "holds on hardware" claims have
    evidence and the release gate is fed. This is the only gate that decays — do it last.

## 3. Scope — enumerated, tiered, diffed against the tree

Coverage is claimed from SCOPES, never from findings counts (an unaudited subsystem yields 0
findings and reads identically to a clean one). The final report must contain a scope table
diffed against the actual source tree, with every exclusion named.

### Heavyweight re-siege sessions (one per session, never two)

| session | scope | why |
|---|---|---|
| S1 | Active-job lifecycle + phase runner + exactly-once finalization | Most-repaired subsystem (RP-007/010/011/013x/047…), worst blast radius, and the #1 calibration target — direct before/after comparability |
| S2 | Dispatch + queue + public services, with a full **call-site reachability sweep** | The card-Cancel-bypassed-the-seam class lives here; registered-services-vs-callers is a whole dimension #1 under-weighted |
| S3 | Card/frontend seams: refusal surfacing, run-profiles, steps manifest, CARD-3/4/8 regression surface | Tier-2 repairs + heavy concurrent src/ churn |
| S4 *(conditional on Q1)* | Phased Jobs + learning integration | Newest critical-path code; already hostile-probed mid-build (6 probes → 6 repairs), but never sieged as a finished subsystem |

### Mid-weight / targeted

- Doc-vs-source sweep across ALL updated docs/dev (the reusable drift-audit pattern:
  fan-out audit → verify → by-doc fix → mkdocs --strict). Runs AFTER the doc update, can be its
  own cheap session.
- Battery/charge family re-read once RP-043..045 land (1 agent; the family was found by live
  observation, not audit — a known blind spot to re-check).
- Per-map store registry (RP-016) + its consumers — new infrastructure since #1.
- Small subsystems from the #1 direct-read tier: re-read ONLY those touched by fix diffs since.

### Exclusions (named in every report)

- **CV segmentor** — correctness is empirical, not textual; this method produces unfalsifiable
  noise the verifiers cannot kill (#1's banked lesson).
- **`learning/` + Phased Jobs IF Q1 says the rebuild is still in flight** — Chris is rebuilding it;
  auditing a moving target wastes the siege.
- Dead code already adjudicated dead (boundary.py etc.) — cite the prior adjudication.

## 4. Method deltas from audit #1 — bake the learned failure modes into the prompts

Everything that made #1 work is retained: shared pre-built inventory, narrow explicit file lists,
mandatory "guards I checked that did NOT rescue this" field, mandatory "areas where I found NO
defect" section, single-event-loop rule stated up front, verifiers told they are scored on false
positives killed, evidence-not-patches, zero repo modifications, orchestrator-side spot-checks
(~2% of spend, always worth it), synthesis done inline by the orchestrator.

New, learned since — these become explicit attack instructions in every discovery prompt:

1. **Fix-diff as first-class attack surface.** For every landed packet in scope: (a) does the fix
   hold at its seam, (b) did it mint an adjacent defect, (c) does its proof actually exercise the
   mechanism (a proof case can be structurally unable to flip — RP-016 case 3), (d) is the packet
   only HALF the finding (#9:A3-REC-3 had two halves; RP-013c closed one and the ledger credited
   the whole).
2. **Call-site reachability.** A correct service with zero callers passes every textual audit.
   Grep registered-services-vs-call-sites; hunt enter-through-the-seam / exit-outside-it
   asymmetry (card Cancel bypassed `cancel_active_job` entirely).
3. **Partial-guard shoulders.** A guard that EXISTS reads as complete. Check the moment just AFTER
   its window closes (a correctly-cleared latch is the trap), and diff every predicate against its
   copies — the shorter copy is the bug.
4. **Executable probes, not just reading.** Design review found 8; probes then found 6 more in 8
   tries. Discovery agents may write and run probe scripts via the test image against a READ-ONLY
   checkout — probes live outside the repo (scratch), never modify repo files, and their transcripts
   are evidence.
5. **Re-verify staleness at the start of every session.** Fixes land between audit sessions; #1's
   RC-3/RC-7 were substantially stale by the time they were worked. Each session re-pins and
   re-diffs its scope before spending.

## 5. Cost, model, and session plan

Calibration (measured on `claude-opus-5[1m]`, single-tier): one heavyweight ≈ 1.9M subagent
tokens / ~41 min / 8 agents (6 discovery + 2 verifiers, verifiers non-negotiable — if forced to
cut, cut discovery to 4–5, never the verifiers). Root-cause fan-in 4.5:1 — assign a cluster to
ONE agent and tell the others it's covered.

**Fleet is MIXED-TIER (decided, Chris 2026-08-02 — this resolves Q2).** Per-agent model/effort
overrides are set at spawn time:

| role | tier | why |
|---|---|---|
| Orchestrator + inline synthesis | Fable (the session itself) | wide-read/whole-corpus shape; synthesis inline bought a 2nd verifier in #1 — repeat |
| Discovery agents | Sonnet (promote a slot to Opus when its scope's *decisions* are consequential or conceptually dense) | collection work — reading a subsystem, gathering call sites, comparing schemas, producing candidates — is well inside Sonnet's reasoning AND its ~967k window; promotion buys judgment, not memory |
| Verifiers | top tier available, HIGH effort — never economized | 22% of #1 spend, killed 17 over-reaches, moved 7 severities; discovery-only output was confidently wrong in both directions |
| Orchestrator spot-checks | inline (orchestrator's own tokens) | ~2% of spend, always worth it |

**The tier premium is a REASONING premium, not a memory premium (Chris, 2026-08-02).** Sonnet's
~967k window is essentially the same working-memory scale as the calibration run's 1M for this
job — context capacity is never the reason to promote a slot. The expensive tier earns its place
where raw observations become repository truth, i.e. wherever someone must decide:

- whether six findings are one root cause or six separate defects;
- whether a reproducer actually proves the stated claim;
- whether a contradiction is code drift, stale documentation, or a deliberate exception;
- whether a proposed repair preserves the old invariants;
- whether two agents agreeing is corroboration or the same seductive mistake.

Those decisions concentrate in the verifiers and the orchestrator's synthesis — which is exactly
why those two roles never economize while discovery does. Promote a discovery slot only when its
scope forces that kind of judgment *during* collection, and say so in the assignment.

Second caveat: the single-tier calibration numbers do not transfer to a mixed fleet — **the first
heavyweight session (S1) doubles as the mixed-fleet calibration**: it reports actuals in the
#1-style cost report and the envelope below re-scales before S2 fires.

Differential re-siege should run cheaper per heavyweight than #1 (~1–1.5M est. pre-recalibration,
likely lower with Sonnet discovery) because the inventory, docs, and prior synthesis are pre-built
inputs. Planning envelope (treat as ceiling until S1 recalibrates):

- S1, S2, S3 heavyweights: ~3.5–5M total
- S4 (if in scope): ~1.5–2M (newest code, least prior synthesis to lean on)
- Doc-drift sweep + targeted re-reads: ~1–1.5M
- **Total: ~6–8.5M subagent tokens across 4–6 sessions, one heavyweight per session, never two.**

Each session ends with the #1-style cost report so the estimate self-corrects.

## 6. Open decisions for Chris — answer before firing

- **Q1 — Phased Jobs / `learning/`:** in scope or out? *Recommendation: IN as session S4, but only
  once you declare the rebuild complete; until then hard-excluded and named.* It will be the
  newest least-aged critical-path code at release time — exactly what a pre-Phoenix siege is for.
- **Q2 — Model: DECIDED (Chris, 2026-08-02) — mixed-tier fleet per the §5 table.** Fable
  orchestrator + inline synthesis, Sonnet/Opus discovery, top-tier high-effort verifiers; S1 is
  the mixed-fleet calibration session and the envelope re-scales from its actuals.
- **Q3 — Doc update ordering:** the doc reconciliation pass is a *precondition* here (gate 7), not
  part of the audit. *Recommendation: run it as its own cheap pass first* so audit #2's
  doc-vs-source dimension tests the reconciliation instead of rediscovering known drift.
- **Q4 — Trigger:** fire the sessions manually as gates go green, or schedule them?
  *Recommendation: manual* — gate 12 (hardware baseline) and gate 10 (clean worktree while two
  sessions share the tree) both want a human-timed start; and the scheduled-task model trap
  (gate 11) already bit once.

## 7. Rejected alternatives (so reviewers don't re-litigate)

- **Full repo re-siege at #1 depth (~14–18M):** rejected — most of the tree is unchanged since #1
  and the corpus already adjudicates it; differential coverage + targeted re-reads buys the same
  release confidence for ~half the spend.
- **Folding the doc update INTO the audit:** rejected — it inverts the test. The audit must judge
  the reconciled docs, not produce them.
- **Auditing Phased Jobs mid-rebuild:** rejected — moving target, and the hard scope boundary on
  `learning/` stands until Chris lifts it.
- **Skipping re-audit of "clean" #1 areas entirely:** rejected in favor of *targeted* re-reads of
  any clean area a fix diff touched — a fix can mint a defect in a previously-clean file.
