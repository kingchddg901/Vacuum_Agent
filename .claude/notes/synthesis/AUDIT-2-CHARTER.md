# AUDIT #2 CHARTER — the post-repair hostile re-siege

**Status: SIGNED OFF — all four §6 decisions are DECIDED (Q1/Q3/Q4 on 2026-08-03, Q2 on
2026-08-02). The charter is now gated only on §2: fire when every gate goes green.** Written
2026-08-02 from live repo state (regenerated ledgers, not recollection).

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
   existed nowhere in code) — the packet was fully open, proven live by the Alfred group-phase
   run pj_2026-08-02T23-04-45 still pinning the card to room[0]. A `RP-XXX:`-prefixed subject
   can still be authoring — verify landings with `git show --stat` (code files changed), never
   by subject alone.
   UPDATE 2026-08-03: part **(a) has since landed** — `6831ccd` (`core/manager.py` +51,
   `test_manager_progress.py` +84), and `current_room_ids` is now live in the snapshot builder.
   The proof passes and is test-backed. The REMAINDER is gated on a fresh group-phase hardware
   run confirming the card no longer pins to room[0] — until that run is banked, do not credit
   the packet whole, and do not let gate 5 close `#9:A3-REC-3` on the strength of (a) alone.
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
   `headSha` manually — the `--commit` filter has lied before), and
   `python .claude/notes/_crossmatch_replays.py --check` (the delta-12 concordance baseline —
   catches lifecycle/schema/finalizer destabilization the suite cannot).
9. **Regenerate every derived ledger at the pin:** `_gen_repro_status.py`, `_gen_audit_doc.py` +
   `_gen_checklist.py`, closure matrix. Never carry a count forward in prose.
   **KNOWN UNCERTAINTY BAND — the open count is approximate, in BOTH directions.**
   `_gen_packet_closure.py` reads only `finding_ids:`, but wave-1 packets (SYNTH-04,
   RP-001..RP-009) declare the same thing as `findings_addressed:`. Those nine therefore
   resolve by `repair_family` alone, and the consumer picks family **or** explicit list, never
   both. Two consequences, each measured 2026-08-03 rather than reasoned:
   - **Under-credit.** A finding with no `repair_family` of its own is unreachable by a family
     match and stays open with its fix landed. `#12:A6-GUARD-2` is exactly that: RP-008 names it
     in `findings_addressed`, the single-flight guard is at `listeners/path_blockers.py:243`, and
     `[PB-9]` in `test_listeners_active.py` tests both its clauses (coalescing AND the
     double-cancel, via `assert_awaited_once`). It still renders open. C17 is really 4/4.
   - **Over-credit.** Family matching credits a wave-1 packet with its WHOLE family even where
     the packet's own `findings_not_closed:` says otherwise — RP-008 closes 2 of RF-13 and says
     so in writing.
   **Both naive repairs were tried and are WRONG; do not re-attempt without per-finding
   adjudication.** Teaching the generator `findings_addressed` flips those nine packets from
   family to explicit and **9 findings reopen** (A3-COMMON-3, A3-SNAP-1, A3-SNAP-3, A4-POSE-3,
   A6-PRE-1, DR-MNT-1, INF-4, INF-5, SN-2) with no evidence they are unfixed. Unioning family
   with the explicit list instead **closes 17**, including `#8:A4-PP-RP-4` — deliberately parked,
   and `_proof_profile_roundtrip.py` still reports it BEFORE — because the union re-widens
   wave-2 packets from their deliberately precise lists back to whole families, undoing the
   precision the exclusive preference exists to enforce.
   The real fix is per-finding adjudication of the nine, which is this gate's work, not a
   generator tweak.
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
13. **Reproducer corpus swept and harness v2 in place** (see §4 delta 6). Audit #2 reads
    reproducers as evidence that a repair holds; a stale proof therefore injects a FALSE
    "this is fixed" straight into the siege. Run `.claude/notes/_sweep_proofs.py` at the pin
    and adjudicate every non-`AFTER`/`BEFORE` bucket. Measured 2026-08-03 on 61 proofs:
    3 `UNEXPECTED` (stale), 12 `NO_TALLY`, 0 `ERROR`. Read `NO_TALLY` correctly — it means
    "printed no verdict line", NOT "broken": 8 of those 12 self-verify via `rc = 1` plus a
    literal `UNEXPECTED SHAPE` print and merely predate the `Proof` class, 1 is
    `_proof_harness.py` caught by the glob, and only 3 are genuinely unverifiable
    (`battery`, `onboarding`, `debug` — the last self-declared throwaway).

## 2b. Ledger state model — partial completion is first-class (Chris, 2026-08-03)

**The flaw this fixes:** in the #1 campaign's ledgers, a packet with ANY blocked subcomponent
stayed "open" — undifferentiated and vague — until everything landed. That single bit failed in
both directions: RP-047 read as plain "open" while its snapshot half was landed and test-backed
(only the hardware confirmation is outstanding); RP-016 read as "landed" while ZONE-C-2/IO-6
float unlisted; and #9:A3-REC-3 was the inverse — one closed half CREDITED as the whole, the
campaign's most expensive reopen. Binary state cannot express partial truth, so it alternately
hides progress and manufactures false closure.

**The model — mandatory for every #2 ledger, and applied to the #1 carry-over ledgers when
regenerated at the pin (gate 9):**

- The unit of closure is the SUB-ITEM (clause / finding_id / named follow-up), never the packet.
  Every multi-clause packet enumerates its sub-items once, and the header is DERIVED:

  `RP-047 — OPEN, 1 of 2 complete · blocked → hardware: [group-phase run confirming card unpin]`
  `RP-016 — OPEN, 6 of 8 complete · open: [ZONE-C-2 referrer pruning], [IO-6 rename detection]`
  `RP-017 — OPEN, 0 of 3 complete · was blocked → packet: [RP-016 registry] until 2feb9e0 landed`

- Sub-item states: `complete` · `open` · `blocked → <TYPE>: <named object>` ·
  `wontfix (reasoning)`. A blocker is always NAMED — "blocked" with no object is the vagueness
  this section abolishes — **and always TYPED, because the type decides how it gets scheduled
  (Chris, 2026-08-03). Closed vocabulary:**
  - `hardware: <which capture/run>` — needs a physical run; DECAYS; all hardware blocks batch
    into one capture session (feeds gate 12 directly).
  - `packet: <RP-xxx / clause>` — depends on a previous fix landing; forms the dependency
    graph; flips to `open` AUTOMATICALLY when the named clause completes, so regeneration
    unblocks these without anyone remembering to.
  - `design: <decision needed + owner>` — queued on a Chris decision or design session
    (CARD-7's whole history is this type).
  - `upstream: <external dep, e.g. fork PR #150, HA core release>` — outside this repo's
    control; unschedulable, must be WATCHED not waited on.
  - `deferred: <decision ref + revisit trigger>` — a deliberate deferment is only valid WITH a
    revisit trigger (a date, a release, an event); an untriggerd deferment is how carried items
    rot into invisible wontfixes.
  The ledger rolls these up (`blocked by hardware: n · by packet: n · …`) so planning reads
  straight off the table — e.g. the gate-12 hardware session's worklist IS the `hardware:` rows.
- The header stays `OPEN, x of y` until x = y (wontfix counts as adjudicated, shown separately:
  `x of y complete, z wontfix`). **No packet is ever written as bare "LANDED" while y > x** —
  that is the A3-REC-3 forgery — and never as bare "OPEN" while x > 0 — that is the RP-047 fog.
- Derived, not declared, per the delta-6 philosophy: the generators compute x/y from the packet's
  own enumerated clause list + per-clause evidence (commit, proof case, hardware capture),
  so under-enumeration is loud (a packet with no clause list renders `?/?` and fails the sweep).
- **Generator work owed before gate 9 can satisfy this:** `_gen_repro_status.py`,
  `_gen_checklist.py`, and the closure matrix all currently emit packet-granular state; they
  need the clause column. Until that lands, any hand-written status line MUST carry the x-of-y
  form anyway.

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
  own cheap session. Scope now includes `docs/user-guide/` (delta 9) and `docs/advanced/`.

  **`docs/advanced/` is a SCRIPT, not a reading pass.** It is the contract surface — service
  parameters, event names, and 700+ lines of automation YAML users copy verbatim — and it is
  structurally diffable: `03-services.md` heads each section with the literal service name over
  a `| Parameter |` table, `02-events.md` heads each with the literal event name, and the
  examples are executable. `.claude/notes/_check_advanced_doc_drift.py` checks all four in about
  a second and exits 1 on a BREAK. Do NOT spend agent time reading these 4,495 lines; run the
  script. Measured 2026-08-03: **0 breaks** — nothing documented is missing or misnamed, so no
  user can copy a snippet and hit "service not found".

  **FOR THE DOC PASS — the 10 open GAPS (real, undocumented, none user-breaking):**
  - no section in `03-services.md`: `acknowledge_map_frame`, `add_queue_zone`, `battery_rebaseline`
  - parameter accepted but never mentioned in its section: `delete_room_profile.force`,
    `get_learning_history_snapshot.origin`, `reconcile_room.force`, `reconcile_room.plan_token`,
    `save_managed_rooms.floor_types`, `set_custom_segments.layout_id`
  - fired but undocumented event: `eufy_vacuum_boundary_saved`
  Re-run the script after the doc pass; it should report 0/0. Ten services are exempt from GAPS
  by design (flight-recorder tooling, and the queue-break surface while Phased Jobs is rebuilt) —
  that list lives in the script and is the thing to revisit if either decision changes.
- Battery/charge family re-read once RP-043..045 land (1 agent; the family was found by live
  observation, not audit — a known blind spot to re-check).
- Per-map store registry (RP-016) + its consumers — new infrastructure since #1.
- Small subsystems from the #1 direct-read tier: re-read ONLY those touched by fix diffs since.

### Exclusions (named in every report)

- **CV segmentor** — correctness is empirical, not textual; this method produces unfalsifiable
  noise the verifiers cannot kill (#1's banked lesson).
- **`learning/` + Phased Jobs from S1–S3** (Q1 DECIDED: they are IN scope, as S4's exclusive
  territory) — S4 fires only after the rebuild is declared complete; auditing a moving target
  wastes the siege, and the other sessions name the carve-out in their coverage reports.
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
   mechanism (a proof case can be structurally unable to flip — RP-016 case 3; the four ways this
   happens are enumerated in delta 6), (d) is the packet only HALF the finding (#9:A3-REC-3 had
   two halves; RP-013c closed one and the ledger credited the whole).
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
6. **Reproducers go stale silently — the HARNESS must derive the check, never the author.**
   Audit #1's rule was "run the reproducer, not just pytest". #2 needs the other half: *is the
   reproducer still measuring production?* A 61-proof sweep on 2026-08-03 found four that were
   not, in four distinct ways — and three of the four broke because something ELSE was fixed
   correctly. Batch-landing several findings against shared code is exactly when this happens,
   and #2 will do a lot of that.

   **The four staleness classes — hunt these by name:**
   - **Moved call site.** The proof stubs a symbol production no longer calls
     (`_proof_inflight_askers.py`: SNAP-2 moved the ticker to `apply_job_progress_tick`, so a
     CORRECT repair reported `UNEXPECTED`).
   - **Sibling-fix precondition.** A *different* finding in the same batch added an early return,
     so the fixture no longer reaches the subject (`_proof_flip_y_disagreement.py`: ROBORO-1's
     `if not decoded.get("room_ids")` guard; ROBORO-5 itself is correctly fixed).
   - **Retired mechanism.** The proof asserts a mechanism deliberately replaced, with IDENTICAL
     output structure (`_proof_completed_evidence.py`: accumulated field → derived index; both
     yield a set of completed room ids). The hardest class — **design changed without structure
     changing**, so nothing textual fails.
   - **Earlier refusal.** A later change made a branch refuse sooner, so the case never reaches
     the check it asserts (`_proof_zone_caps.py`).

   **Build the v2 harness BEFORE firing (gate 13). Requirements:**
   - **Stub-invocation tracking.** Make `H.patch()` the only sanctioned stub path and fail any
     proof where a registered stub was never invoked. Catches the moved-call-site class for
     free, with zero author declaration.
   - **No proof without a verdict.** The sweep hard-fails any `_proof_*.py` that emits no tally,
     and the glob excludes `_proof_harness.py`. Audit #1's 12 `NO_TALLY` files exist only
     because the harness postdated them; with the harness first, the class cannot recur.
   - **Quarantine rendering in `finish()`.** Never print a bankable `3 AFTER · 1 UNEXPECTED` —
     render `0 of N admissible` so no case in a compromised file counts as evidence. Fire on
     `UNEXPECTED`/`ERROR` ONLY, **never on `BEFORE`**: healthy partially-landed packets
     legitimately report mixed `BEFORE · AFTER` (three do today), and quarantining those would
     make the signal read as noise on day one.
   - **Contract version, mechanism-sensitive proofs only.** A proof asserting a *mechanism*
     rather than an outcome declares the contract it was written against; production holds the
     constant; bumping it makes the stale proof recuse itself loudly. Narrow by design — this is
     the one place a declared premise earns its cost, and it is the only handle on the
     retired-mechanism class.

   **Why harness-derived and not author-declared:** a declared premise that can invalidate a
   whole file is a liability, so under deadline the rational move is to declare fewer — which
   returns the corpus to exactly today's state while *looking* rigorous. Derive it and there is
   nothing to under-declare. Already correct and worth preserving: `proof.case()` exposes only
   `before=`/`after=` with no third accepting arm, so tolerant "correct either way" branches
   (which the pre-harness proofs do contain) cannot be written.

7. **Route evidence, not just outcome evidence — the trace_route instrument.** Design banked
   2026-08-03 (three-agent convergence): `DESIGN-trace-route-tool.md`. A green outcome proves
   success; only the executed ROUTE proves the success used the intended mechanism — the
   campaign's recurring enemy was "false agreement about which code actually ran." Two probe
   stages for #2 discovery agents, both zero-source-modification (coverage.py-based, scoped to
   the integration, run in the pinned worktree):
   - **Fallback census:** run the suite/scenario green, then report every executed degraded
     branch (swallowed exception, fired fallback, rescue path under a passing assertion) —
     mechanizes the prompt's "silent degradation paths that conceal failures".
   - **Three-path fix review:** for landed packets in scope, diff the scenario's route at the
     BEFORE and AFTER SHAs against the expected repaired route — catches partial closure
     ("output appears fixed, named defect not proven fixed", the A3-REC-3 class) that outcome
     assertions certify as fixed.
   Limits stated wherever used: proves what executed, never what SHOULD execute; not
   admissible for race findings (races stay uninstrumented). Complementary to delta 6, not a
   substitute: the harness derives per-proof admissibility; trace_route is the discovery
   instrument for routes nobody declared.

8. **Mock-failure ledger — a REQUIRED #2 output, separate from the defect ledger (Chris,
   2026-08-03: mock failures may be systemic, but the rebuild is HELD until #2 rules).**
   Discovery agents classify every mock/stub/fixture finding into this taxonomy (one class
   per finding, banked verbatim from the three-agent review):
   - accepted an impossible signature
   - replaced the wrong production boundary
   - was never consumed
   - encoded intended behavior instead of actual callee behavior
   - bypassed validation or an earlier refusal
   - returned a shape production could never return
   - hid async/lifecycle behavior
   - asserted output without proving its origin

   **Every entry also carries a COHORT: authorship era (pre-campaign · campaign-era loops ·
   harness-v2-era) + subsystem.** Without the denominator, "same class dominates" cannot
   distinguish a systemic factory problem from one bad historical cluster already cured by
   harness v2 — and the cohort axis is what makes the verdict actionable.

   **Pre-registered decision rule (set BEFORE evidence, apply mechanically at synthesis):**
   if 2–3 classes dominate ACROSS cohorts → global test-generation rules change (prefer real
   production collaborators; mock only external uncertainty; bind fakes to production
   signatures; fail when an expected fake is unused; prove the intended path produced the
   asserted result). If failures are scattered or cohort-concentrated → targeted hardening
   only; a wholesale rewrite costs more than it returns. No third option gets invented after
   seeing the data.

   Mechanical pre-seeding (don't wait for findings): harness v2's stub-invocation tracking
   auto-populates "was never consumed"; trace_route's census populates "asserted output
   without proving its origin". Known seed entries: the four stale-reproducer classes
   (delta 6), the six wave-1 probe defects, RP-014's proof-only in-flight sites (`9095968`).

   *(Delta 9 — read the user guide before assigning severity — sits as its own subsection
   after §5.)*

10. **Premise ledger — findings share PREMISES, and a retired premise fells every dependent
    finding at once (GPT-proposed, adopted 2026-08-03).** The measured failure: A3-IMAGE--1,
    A2-POLYGO-5, and A4-CUSTOM-6 all rest on ONE empirical claim ("CV segment ids can be
    reassigned by a re-analysis"). It was disproved once, on-device, and the ruling sat in
    `_adjudicated_findings.json` — but only one of five verification groups was told to read
    it, so four agents spent ~1.4M tokens re-deriving a premise retired the day before.
    Findings were deduped by root cause of DEFECT (4.5:1 fan-in); nobody deduped by root
    cause of BELIEF. Mechanism, kept small:
    - `_premises.json`: `{id, statement, status: established|retired|open, evidence,
      retired_by}` — e.g. `cv-ids-unstable`, `card-can-retune-cv`, `one-map-per-vacuum`.
    - Findings carry the premise ids they rest on; an adjudication that retires a premise
      auto-flags every dependent finding for re-check, carrying the RETIRING EVIDENCE with
      the flag (the 30-re-analyses observation travels; no agent re-derives from source).
    - Symmetric in reverse: a re-established premise reopens everything built on it.
    - This is [[feedback_centralize_question_not_vocabulary]] applied to audit evidence.
    **Not in conflict with §7's rejected author-declared premises:** that mechanism made
    authors declare liabilities at proof-writing time (inviting under-declaration); this one
    records disproofs at adjudication time, and tagging BENEFITS the tagged finding — the
    incentive runs the right way.
    **Hard rule regardless: every verification agent reads `_adjudicated_findings.json`
    unconditionally** — in the shared inventory, never a per-group hint. Costs nothing and is
    the fix for the actual failure observed.

11. **Route by ANSWERABILITY: code-answerable vs device-answerable (adopted 2026-08-03).**
    Before fanning out on any finding, classify the disputed premise: if it is disprovable by
    OBSERVATION ("what does the device do"), ask Chris / bank one hardware observation FIRST —
    30 re-analyses settled in one sentence what 1.4M tokens of code-reading could not, because
    the question was never "what does the code say". Measured pattern: three of the day's real
    defects came from live observation (the upkeep crash, both #46 halves); the two biggest
    wrong answers came from reading code without a device. #1 had NEEDS-LIVE-HARDWARE as an
    *output* class — #2 makes answerability an *input* routing decision. Guard the reverse
    too: device-answerable routes the DISPUTED PREMISE to observation; it is not an excuse to
    skip reading the code around it. Banked observations become premise evidence
    (`_premises.json`), per [[feedback_archive_cheap_raw_data]].

12. **Recorder-replay corpus — Chris feeds REAL runs from the HA recorder as test fodder
    (offered 2026-08-03).** Labeled exports of actual Alfred/Ivy runs (entity-state streams
    for the adapter's entity set, with Chris's ground-truth annotation: "kitchen, then
    entryway+hallway as a group, one recharge pause"). Four consumers:
    - **Mock replacement (delta 8's cure, not just its ledger):** replay through the PUBLIC
      seam (state-change events, production code unmodified) — a fixture recorded from the
      device cannot encode intended-instead-of-actual behavior.
    - **Premise evidence (deltas 10/11):** a library of recorded runs makes device-answerable
      questions GREPPABLE ("does task_status ever emit X before docked?") — one query instead
      of a fan-out, and the answer banks straight into `_premises.json`.
    - **Probe scenarios:** discovery agents run reproducers against real streams, including
      the ugly ones (missing entities, stale pushes, mid-run recharge).
    - **trace_route fodder:** three-path fix review replays the SAME recorded run at BEFORE
      and AFTER SHAs — identical stimulus, route diff is pure signal.
    Practical rails: export SOON after interesting runs (recorder purge window eats them);
    websocket history rows come in COMPACT format (`s`/`a`/`lu`/`lc` keys, float seconds —
    [[reference_ha_history_compact_format]]); recorder stores state CHANGES with real
    timestamps, so replay uses virtual time. Honest boundary: replay is deterministic — it
    reproduces sequences and gaps, NEVER await-interleavings; race findings stay with the
    uninstrumented race methodology (delta 6/7 limits). Complements gate 12, does not
    replace it: baselines still need fresh LIVE captures at the pinned build.

    **CONCORDANCE BASELINE — a standing destabilization detector for lifecycle / record-
    schema / finalizer changes (measured 2026-08-04, corpus banked `e8d380a`).** The frozen
    recorder window and the learning archive were cross-matched: **57/57 Alfred + 11/11 Ivy
    episodes matched a learned job record, ZERO true orphans in either direction**; room-
    boundary deltas (episode start vs learned `room_timings.cleaning_start`): **Ivy max 1s**
    (native current_room — now bankable premise evidence), **Alfred max 138s** (all worst
    cases are the run's FIRST room — reads as dock-exit transit + attribution lag; one
    adjudication look owed, not a defect claim). The device's account and the system's
    account of the same 68 runs agree completely.

    Two Chris-settled facts about the corpus (device/user-answerable, closed without
    agent spend — delta 11 working as intended): the worst-delta rooms all being "kitchen"
    is USAGE SKEW, not a signature — it is his standard test room (close to the dock,
    short, sequences well), so it opens most test runs; the owed adjudication is about
    first-room transit attribution generally, not kitchen. Corollary caveat for every
    replay consumer: **the corpus over-represents short kitchen-first quick-profile test
    runs** — fine for lifecycle/finalize concordance, NOT a representative workload
    distribution for estimator or coverage claims ([[feedback_builder_usability_blindspot]]
    applies to data, not just settings).

    **The rule this buys:** after ANY change to job lifecycle, record schema, or the
    finalizer, run `python .claude/notes/_crossmatch_replays.py --check` (exit 1 on
    regression; thresholds = baseline + headroom: zero unmatched, zero orphans, Ivy ≤5s /
    Alfred ≤180s). The frozen window never changes — so lost concordance means the change
    destabilized finalize behavior or broke old records in migration, **even while the
    whole pytest suite stays green**. This is route-evidence thinking (delta 7) applied at
    system level: outcome tests can stay green while finalization drifts; concordance
    against the device's own record cannot. S1 (lifecycle re-siege) includes the check in
    its probe kit, and it joins gate 8's green-at-the-pin list.

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

### Method delta 9 — READ THE USER GUIDE BEFORE ASSIGNING SEVERITY

Audit #1 based itself on `docs/dev/` and the code. It never read `docs/user-guide/`.
That is **22 files of intended-use documentation invisible to the entire campaign**, and
this charter inherited the blind spot — before this entry it referenced `docs/dev` exactly
once (the doc-vs-source sweep) and the user guide nowhere.

The two trees answer different questions and only one of them was consulted:

- `docs/dev/` says **how it works** — data model, services, storage, contracts.
- `docs/user-guide/` says **how it is meant to be used** — which operations are manual
  versus automatic, what the documented recovery path is, what the user is told to do when
  something goes wrong.

Severity is a claim about USE. Derived from mechanism alone it systematically overstates:
any code path reachable in principle reads as a live hazard, because nothing in the dev
docs says how often — or whether — a user actually walks it.

**Worked example, `#18:A3-IMAGE--1` (HIGH, adjudicated OVERSTATED 2026-08-03).** It assumed
routine re-analysis silently rebinding room links. `docs/user-guide/16-making-your-own-maps.md`
"Option A" describes Auto (CV) as a one-time SETUP step — capture a prepared screenshot,
upload, analyse, link each shape, then fine-tune **card-side** with Translation / Edges /
Vertices ("adjustments save as you go"). Re-analysis is not a workflow at all. When detection
is wrong the documented answer is not retuning, it is *"that's the cue to try a custom layout
instead"*, and *"trying a custom layout never destroys your Auto (CV) result; they live side
by side."* Nothing auto-runs at runtime. One page of the user guide would have downgraded the
finding at authoring time — and a fix built on the mechanism alone was written, tested, and
would have deleted hand-made room links on the one path users DO walk (a fresh upload).

The same page also explains why the CV tuning holds and must not be "improved": the input is
deliberately controlled — floor types cleared, 2D, all overlays off, tight crop, matched
dark/light pair at identical orientation. The hard work is in the CAPTURE, not the algorithm.

**Requirement for every #2 session:** before assigning severity to a finding in a
user-facing subsystem, read that subsystem's user-guide page and quote the sentence that
establishes intended use. A finding whose harm depends on a workflow the guide does not
describe is MEDIUM at most, and its trigger must be stated explicitly. Add `docs/user-guide/`
to the doc-vs-source sweep's scope — the drift that matters there is not "is this accurate"
but "does the code assume a workflow the guide never documents".

## 6. Decisions — ALL DECIDED, none open

- **Q1 — Phased Jobs / `learning/`: DECIDED (Chris, 2026-08-03) — IN SCOPE as session S4.**
  S4 is confirmed, not conditional. Sequencing unchanged: gate 6 still requires the rebuild
  declared COMPLETE before S4 itself fires (audit a finished subsystem, not a moving target),
  and the standing hard boundary on touching `learning/`/phased-job code remains in force for
  everyone but the rebuilding session until that declaration. S1–S3 do not wander into it.
- **Q2 — Model: DECIDED (Chris, 2026-08-02) — mixed-tier fleet per the §5 table.** Fable
  orchestrator + inline synthesis, Sonnet/Opus discovery, top-tier high-effort verifiers; S1 is
  the mixed-fleet calibration session and the envelope re-scales from its actuals.
- **Q3 — Doc update ordering: DECIDED (Chris, 2026-08-03) — docs first, of course.** The doc
  reconciliation pass runs as its own cheap pass BEFORE the audit (it is gate 7's precondition),
  so #2's doc-vs-source dimension tests the reconciliation instead of rediscovering known drift.
- **Q4 — Trigger: DECIDED (Chris, 2026-08-03) — MANUAL.** Sessions fire by hand as gates go
  green: gate 12 (hardware baseline) and gate 10 (clean worktree on a shared tree) both want a
  human-timed start, and the scheduled-task model trap (gate 11) already bit once.

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
- **Retrofitting audit #1's 61-proof corpus with premises:** rejected (Chris, 2026-08-03) —
  "we're deep enough in that we build better harnesses. Next time for the second audit, which is
  gonna run anyway." The 3 stale + 3 unverifiable proofs stay as-is: known, documented, packets
  mostly landed. The learning goes into §4 delta 6 instead.
- **Author-declared premises as the admissibility mechanism:** rejected — it creates a perverse
  incentive to declare fewer premises (every one becomes a liability that can void a file; a
  21-case proof exists in this repo). Superseded by harness-derived checks. Note the measured
  fact that decided it: the EXISTING sweep detected 4/4 of the observed stale proofs, so premises
  were never the *detection* mechanism, only a diagnosis accelerator. Counter-argument on the
  record — this corpus's `after=` expressions are unusually tight, so 4/4 is partly a property of
  authoring discipline rather than of the sweep; if #2's proofs are written looser, revisit.
- **Per-case (rather than per-file) invalidation:** rejected as the *default*, but the reasoning
  matters — a file is a packaging boundary, not an epistemic one. Quarantining the whole
  executable is a conservative default under unproven locality, NOT proof that its cases share
  fate. Where dependency is genuinely encoded, narrowing is legitimate. Suppressed results are
  never retroactively banked: repair, re-run, and count only the fresh results.
