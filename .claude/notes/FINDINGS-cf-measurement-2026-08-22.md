# The counterfactual measurement — RESULT

**Run 2026-08-22 on `06-job-lifecycle.md` (1,473 lines). 7 counterfactuals measured.**
This is the measurement `STATE-documentation-restructure.md` §6 recorded as *"built, not yet
run"* and §7 listed as open item 1. It has now been run.

---

## The number

### The document answered 2 of 7. It failed 5.

| | count |
|---|---:|
| **Source-only control** | **7/7 CORRECT** |
| doc CORRECT | 2 |
| doc PARTIAL | 2 |
| doc SILENT | 3 |
| doc WRONG | 0 |
| **DOC_GAP** (doc failed, source succeeded) | **5** |
| **AGENT_MISS** (both failed — question too hard) | **0** |
| protocol breaches | 0 |

**ZERO AGENT_MISS IS WHAT MAKES THIS A MEASUREMENT AND NOT NOISE.** The source-only control
answered every question correctly, so every document failure is attributable to the document —
not to a question that was too hard or an agent that was too weak. That was the design's
central worry ("miss attribution"), and it came out clean.

## The shape of the failures matters more than the count

**The document is never confidently wrong.** Zero WRONG across 7 questions. It is
either right, or it is silent. On the three SILENT questions the doc-agent said so plainly
rather than assembling a plausible answer from general competence — which is the behaviour the
test was designed to reward, and the graders verified the silence by grepping the file
themselves.

**Where it succeeded, it succeeded emphatically, and for one reason.** Both DOC_OK answers
come from passages that record *why*, not *what*:

> CF-5 grader: *"the answer is in the doc almost verbatim, in a paragraph written specifically
> to pre-empt this exact hoist."*

CF-1 is the same shape — §6f states the clause ordering AND the two reasons for it. **Neither
passage is mechanism narration. Both are a recorded decision with its defeated alternative.**
That is the single clearest signal in the run about what earns its place.

**Quantifier creep on the reading side too: 2 of 7 (CF-3, CF-7).**
The authoring pass showed 6 of 9 answers inflated their scope. The same failure now shows up
in answers *derived from the document*: mechanism right, scope wrong. It is not an artifact of
one agent population.

## ⚠ A pointer to a document that does not answer either

CF-9 is the sharpest single failure. The doc does not describe the mechanism and forwards the
reader onward — *"See 30-phase-runner §4a for the full per-phase recording mechanics"*. I
checked: `30-phase-runner.md` does not carry the epsilon or decrease-test material either.
**A pointer to a place that does not answer is worse than silence** — it spends a reader's hop
and still fails, while reading like coverage.

## ⚠ AND THE MEASUREMENT INVALIDATED ONE OF ITS OWN ORACLES

**CF-6 is excluded, because its oracle rotted in six days.** The oracle asserts
`_detect_cancel_likely_run` bails whenever `len(resolved_rooms) != 1`. Verified in the tree:
the guard now reads `if not isinstance(resolved_rooms, list) or not resolved_rooms:` — it bails
only on EMPTY. Commit `078ca634` (*"two guards that never fired — zone-clean in-flight,
multi-room cancel"*) fixed the very defect that counterfactual was written to probe. The
doc-agent was graded WRONG against behaviour that no longer exists.

> **This is the adversarial review's own thesis, demonstrated by accident.** The review said the
> tagged-corpus proposal had *"a strong theory for preventing valuable prose from being DELETED;
> no theory for keeping that protected prose TRUE"*, and closed with: *"A durable identity
> protects important reasoning from accidental deletion; a dependency edge tells us when that
> reasoning must be reconsidered. **We need both.**"*
>
> The oracle set is exactly the protected reasoning that design was meant to preserve, and one
> eighth of it was silently invalidated in six days. We now hold the identity half — 177 `BN`
> anchors, `00b`, `00c`. **The staleness edge is still missing, and this run priced it.**

## What this does NOT establish

- **n is small.** Seven questions on one file. The control being 7/7 makes the attribution
  sound, but the ratio is not a corpus-wide precision figure.
- **It measured ONE FILE, by design.** For CF-2 and CF-4 other retired docs at least *mention*
  the subject (3 files and 2 files respectively); whether they ANSWER the counterfactual is
  unmeasured. CF-9's gap is the one confirmed to survive a corpus check.
- **The questions were selected to be hard** — authored specifically so general competence gives
  the wrong answer. A document that answers 2 of 7 of THOSE is not a document that answers 2 of
  7 questions generally.
- **`06` was chosen as the hardest file** (1,473 lines, the most interleaved lifecycle in the
  corpus). It is a floor, not an average.

## What it does establish, for the standard

1. **The acceptance test discriminates.** It separated 2 passages from 5 with a clean control
   and no ambiguous attributions. Whatever else is decided, the test works.
2. **What passes it is recorded DECISIONS, not narration.** Both passes were "here is the
   alternative we rejected and why". Neither was a description of what the code does.
3. **Silence is cheap and wrongness is expensive, and this corpus is mostly silent.** That is a
   better starting position for a rewrite than a corpus full of confident stale claims —
   there is little to un-teach.
4. **Identity without a staleness edge decays measurably.** Six days, one eighth.

---

## Per-question detail

| id | doc | source | attribution | note |
|---|---|---|---|---|
| CF-1 | CORRECT | CORRECT | **DOC_OK** |  |
| CF-2 | SILENT | CORRECT | **DOC_GAP** |  |
| CF-3 | PARTIAL | CORRECT | **DOC_GAP** | quantifier creep |
| CF-4 | SILENT | CORRECT | **DOC_GAP** |  |
| CF-5 | CORRECT | CORRECT | **DOC_OK** |  |
| CF-7 | PARTIAL | CORRECT | **DOC_GAP** | quantifier creep |
| CF-9 | SILENT | CORRECT | **DOC_GAP** |  |
| ~~CF-6~~ | — | — | **EXCLUDED** | oracle stale — fixed by `078ca634` |

### Why each one landed where it did

**CF-1 — DOC_OK.** Both agents land the oracle in full. Oracle claims: (1) the clause becomes unreachable dead code; (2) an errored robot fails BOTH the job_active/mid-run gate and the docked/idle gate by construction, because `vacuum_errored` is derived from `vacuum_state == "error"` and upstream keeps the cleaning binary ON while errored; (3) the trapped-robot strand returns permanently — stays `started` with `stranded_since` never stamped; (4) the "it may recover" protection is not lost by keeping the clause high, because it lives in the caller's ~5-minute grace with stamp-clearing. DOC-AGENT: hits all four. Headline is "kills the error-reap rule outright... unreachable, not merely late"; it names both gate

**CF-2 — DOC_GAP.** DOC: correctly SILENT, and unusually well-behaved about it. The doc-agent's characterization of the document matches my own independent grep exactly (two bare pointers, lines 1242 and 1305). It also explicitly named and refused the two nearest available traps — carrying §8's "single-overwrite file — only the most recent incomplete run is kept" over from `incomplete_run.json` (which would have yielded "one finalization", wrong), and carrying §4's read-modify-write note about the Phased Jobs parent record over from `history_store.py` (which would have yielded "never" — the oracle's answer, but from evidence about a different file). Declining to guess "never" off an unrelated file is the correc

**CF-3 — DOC_GAP.** SOURCE-ONLY = CORRECT. It matches the oracle on every load-bearing point and independently bounds the scope the way the oracle does: the two consumers of `current_room_overdue`, the `if current_room_overdue and current_room_id is not None:` gate in `detect_run_anomalies`, the dead `stall_detected`/`stall_elapsed_minutes`/`stall_expected_minutes`/`stall_ratio` and the timing-trigger event, the opposite-sense `_honors_clean_order` gating of `running_long`/`skipped_room_ids` so all three outputs die at once, the `26c4b2d7` tombstone, the card banner fed only by `progress.stall_detected` at `src/renderers/learning.js:469`, and Roborock as the only declarer of `honors_clean_order: False`. Crucial

**CF-4 — DOC_GAP.** SOURCE = CORRECT, and unusually so. It lands the oracle's load-bearing insight verbatim in structure: `keep_entry` gates whether an interval OPENS (job_finalizer.py:153) while the implicit CLOSE boundary is searched over unfiltered `raw_entries[index + 1:]` (line 161) — I confirmed both line numbers match the oracle's 153/161 exactly. It gets the arithmetic right (60 s → 1800 s deduction; 1500 − 1800 → `max(0, …)` clamp → `cleaning_time_seconds = 0`; headline 1440 → 0) and the used_for_learning consequence right via `evaluate_idle_wall_hold`'s `had_errors` exemption. Critically, it independently anticipates all three oracle corrections rather than committing them: (1) it states the outcome i

**CF-5 — DOC_OK.** Both agents landed the oracle's mechanism and its scope. Oracle core: hoisting silently stops rooms advancing *inside* a phase on brands with no native current-room signal (Eufy / `native_transition_source` at its False default), because an Eufy `room_group` phase dispatches N rooms in one command and the counter-plateau / timing paths are the only things that advance `current_room_id`, record completed rooms, and fire the room-finished/started pair inside the group; nothing errors, the card just never strikes rooms out; the guard cannot be generalised because the 0.55-min phantom completion is structurally native-branch-only; a secondary casualty is the phase-scoped sample slice becoming de

**CF-7 — DOC_GAP.** SOURCE-ONLY = CORRECT, and it is a superset of the oracle. It has the oracle's core (dispatch clears selections at manager.py:7016 → 1101-1128; queue re-derived per call; therefore a `started` run reports `no_rooms_selected` and the reorder flips it to `active_job_running`/`mid_job_service`/`vacuum_busy` on every tracked run and the dock service after it). It independently states both of the oracle's scope corrections: (1) "Not 'every moment of a run': a mid-run recharge or inter-phase dock reads `ready` through `evaluate_job_lifecycle` (manager.py:3757-3760), so in those windows both orders return the queue/payload refusal" — the oracle's docked/idle-is-non-active fallthrough; and (2) pause

**CF-9 — DOC_GAP.** DOC: SILENT, and honestly so. The question has two halves — what happens, and on which installs — and the doc-agent answered neither. On direction it explicitly refused: "The direction of the resulting error I cannot determine ... If a reset means 'keep what's accumulated and treat the current value as fresh progress', the phase over-counts ...; if it means 'restart the accumulator here', it under-counts. Both are consistent with everything the document says." Naming both branches is not getting the mechanism right; the oracle's whole first clause is that it fails in the INFLATING direction. On scope it likewise declined to name the exposed population, and correctly refused to convert §5's u
