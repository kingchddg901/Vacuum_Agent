# CAL-23 Trim 2 — Removal Manifest (revision of Trim 1)

Target: `docs/dev/23-error-tracker.md` (475 lines) → Trim 1 candidate (409 lines,
verdict: D, one confirmed-C on the `acknowledged` field, provenance NEVER-PRESENT)
→ Trim 2 candidate (415 lines), this file.

Sections 1–23 below are unchanged from Trim 1 — same removals, same destinations,
same justifications. Round-2 work is additive: a **Round 2 Edits** section
documenting the three mandated surgical changes, and a new **ADDITIONS** section
(new protocol rule this round: log every sentence introduced with no counterpart in
the *original* 475-line doc, not just removals).

---

## Round 2 Edits (mandated)

**Edit 1 — §4.3, `error_label_key` conformance invariant (new, earned).** Appended
to the closing paragraph of §4.3, verbatim per the coordinator's wording: a declared
label is returned only for a non-empty stored string; any other stored value (a
number, an empty string, a nested structure) resolves to `None` exactly as an absent
entry does; a label is never manufactured from a non-conforming entry. Logged in
ADDITIONS below as A-1.

**Edit 2 — §6.2, `harvest_active_run` deprecation fix.** Trim 1 said the method
"remains a fully supported method independent of which caller currently uses it" —
wrong in spirit: the source marks it deprecated (docstring: "DEPRECATED in favour of
`peek_active_run` + `commit_active_run`... Do not add new callers — a single
destructive read cannot be made safe against a persistence failure"), and it has
zero production callers (confirmed by grep across `custom_components/` — see Trim 1
manifest entry 11 for the same verification). Trim 2 states: deprecated, zero
production callers, kept only because a legacy test asserts its exact destructive
semantic, and a one-shot destructive read can't be made safe against a persistence
failure — do not add new callers. Logged in ADDITIONS below as A-10.

**Edit 3 — §3.1, `acknowledged` field row — decision: KEEP, reworded.** The row is a
genuine addition (no counterpart in the original 475-line table — see ADDITIONS A-1
below, renumbered; the original `active_run_error` field table has no `acknowledged`
row at all). Adjudication found it induced a C: the field is real and
stored (verified: `error_tracker.py` writes `latch["acknowledged"] = True` in
`acknowledge()`), but is read by **nothing** repo-wide outside this module and its
own tests (`grep -rn '"acknowledged"'` across `custom_components/` and `tests/`
turns up only the write site, an unrelated same-named key in two other services'
*return dicts* — `core/manager.py:5402`, `services/errors.py:69,72` — which are a
different `acknowledged` entirely, and the two direct test assertions). Trim 1's
"Absent otherwise" phrasing implied a tidy presence/absence lifecycle the code
doesn't actually promise (nothing clears it back once set, short of the whole latch
being nulled) — that's almost certainly what a builder over-implemented into.

**Decision: kept, not dropped.** It's a real, persisted, directly-tested field
(`test_acknowledge_scopes`, `test_acknowledging_mid_external_run_marks_rather_than_
deletes` both assert `latch["acknowledged"] is True`); dropping it would guarantee
a miss on those two assertions instead of merely risking one. Reworded to remove
the lifecycle implication: states it's set only by `acknowledge()`, absent on a
freshly-formed latch, and is explicitly **write-only** — no behavior in this spec
depends on it, and its clearing behavior is unspecified. The write-only flag is the
fix: it tells a builder there is nothing to *implement* around this field beyond
storing it when told to, which removes the incentive that likely produced the C.

---

## Sections 1–23 (unchanged from Trim 1)

### 1. §3 Storage Layout, lines 46, 48–54 — private accessor/field names
`_ensure_record()`, `_persist_and_notify`, `_grace_cancels`, `_vacuum_entities` named
as the mechanism behind lazy record creation and persistence scheduling.
**Destination: discard.**
Justification: cardinal-rule (internal symbol names, no public caller). The
*behavior* — lazy default-key creation, thread-safe save scheduling via
`hass.loop.call_soon_threadsafe`, and the runtime-only/lost-on-restart field list —
is preserved in trimmed §2, with the private names stripped.

### 2. §4.1, lines 67–72 — external-run latch cross-module internals
Names `_finalize_external_run` (in `learning/external_run.py`, a different module)
and the "peeks the latch onto the pending record instead of the dispatched
finalizer doing it" detail, plus the cross-reference to `03-data-model.md §5a/§9b`.
**Destination: lore.**
Justification: true and useful for understanding *why* the external-run path is
shaped this way, but it describes a different module's internal flow, not a
requirement on `error_tracker.py` itself (whose only obligation is: form a latch
whenever a run — including external — is in flight). Not rebuild-critical here;
belongs with doc 28 (external-run ingestion) if kept anywhere.

### 3. §4.4, lines 128–134 — provenance note on config being newly consulted
"this config **is** read (it was once advertised in doc 22 §9 but never consulted;
that is fixed...)" and the per-entity-loop hoisting note.
**Destination: audit.**
Justification: describes a fixed doc/code drift (a config key that was documented
but dead), not a current behavioral requirement — the current, correct behavior
(ordered attribute-name lookup, resolved once per vacuum) is stated plainly in
trimmed §4.1 without the "it used to be broken" framing.

### 4. §4.4, lines 136–151 — "Brand reality, and the second capture route" essay
The full explanatory paragraph contrasting Eufy's numeric attribute vs. Roborock's
enum-string state, including the extended "gate is a declaration, never a sniff"
rhetoric.
**Destination: lore.**
Justification: the operative rule (message_is_code gate, attribute-wins-when-present,
no sniffing) is retained verbatim as a requirement in trimmed §4.1; only the
extended rationale/rhetoric explaining *why* a sniff would be wrong is cut as
restatement of the same point already made concisely.

### 5. §4.4, lines 152–157 — "This resolves live:RB-ERR-2" incident narrative
Bug-history paragraph: all five Roborock tables were unreachable at runtime before
this fix; legacy records keep `code = None` and are not migrated.
**Destination: audit.**
Justification: real production-bug provenance, valuable for the audit trail, but not
something a blind reconstruction needs to reproduce — the *current* required
behavior (message-is-code capture, §4.1) is unaffected by knowing the bug existed.

### 6. §4.5, lines 161–188 — `_code_key`/`_code_set`/`_int_set` names + RB-ERR-1 story
The `_code_key(value) -> int | str | None` signature heading, the "WHY THIS EXISTS
(live:RB-ERR-1)" discovery narrative, and the `_int_set()` / `_code_set()` private
helper distinction.
**Destination: audit** (the RB-ERR-1 narrative — real bug provenance) **+ discard**
(the private symbol names themselves; cardinal-rule).
Justification: the normalization *algorithm* (bool→None, int passthrough, numeric
string→int, other string→lowercased key, empty→None, float→None) is fully preserved
as trimmed §4.2 — that's the only part any caller (the three classification seams)
can observe. `_int_set()` specifically has no external caller or observable effect
distinct from `_code_set()` and was dropped as internal-only trivia.

### 7. §4.5, lines 181–188 — "Read-time fault naming" paragraph
Describes `learning/manager.py::_run_error_rows`, `_RUN_ERROR_ROW_LIMIT = 12`, and
the frontend locale-pack consumption of `error_label_key`'s output.
**Destination: lore.**
Justification: entirely about a different module's (`learning/manager.py`)
consumption pattern. The one fact `error_tracker.py` itself must guarantee —
`error_label_key` is resolved fresh on every call and nothing is persisted — is kept
as the closing sentence of trimmed §4.3 (and is now sharpened by Edit 1 above).

### 8. §5.1, lines 199, 208–210 — HA API name + concrete per-brand sentinel examples
`async_track_state_change_event` named as the source of attribute-only
re-emissions; the literal Eufy (`{"", "unknown", "unavailable", "none", "normal"}`)
and Roborock (`{"", "unknown", "unavailable", "none"}`) declared sentinel sets.
**Destination: discard.**
Justification: the framework-function name adds nothing beyond the kept behavioral
fact ("a repeated value... counts as its own rising edge"). The concrete per-brand
sets are redundant with the adapters' own `vocabulary.py` files, which are part of
the surrounding integration code already visible to the builder — restating them in
doc 23 duplicates data owned elsewhere.

### 9. §5.4, lines 229–239 — literal `_is_in_secondary_error` code block
Python method body naming `self._vacuum_entities`, showing the exact OR'd
two-channel check as code.
**Destination: discard.**
Justification: cardinal-rule — a private method's exact name/signature/internal
field, not derivable from the public contract. The identical logic is preserved as
prose (trimmed §5.2/§5.3, "combined: ... whenever either channel currently reads as
an error").

### 10. §6, line 248 — literal `async_call_later(...)` code line
Names `_ERROR_MESSAGE_GRACE_SECONDS` and the private callback `_on_grace_expired`.
**Destination: discard.**
Justification: cardinal-rule. The scheduling behavior (duration, cancel-on-real-edge)
is fully stated as prose in trimmed §5.5.

### 11. §7.2, lines 300–304 — wrong description of the finalizer's injection
"`learning/manager.py::_make_error_source(hass)` builds a closure `error_source(...)
-> tracker.harvest_active_run(...)` and injects it into
`LearningJobFinalizer(error_source=…)`."
**Destination: discard.**
Justification: **confidently wrong** — verified against current
`learning/manager.py` (`_make_error_source` calls `tracker.peek_active_run`,
`_make_error_commit` calls `tracker.commit_active_run`; both closures — `error_source`
*and* `error_commit` — are injected into `LearningJobFinalizer`).
`harvest_active_run` has zero production callers. Per DR standard §5.1 ("never be
confidently wrong"), this is corrected rather than merely trimmed: trimmed §6.2
describes the real peek/commit two-closure contract (see ADDITIONS A-7/A-8).

### 12. §7.2, lines 304–310 — completed-job `outcome` payload contract
The four-key `outcome` fold (`had_errors`, `error_count`, `errors` verbatim,
`total_error_seconds`) and the half-open-interval merge rule for computing
`total_error_seconds`.
**Destination: lore.**
Justification: this is `job_finalizer.py`'s own output schema, not
`error_tracker.py`'s. The only part that *is* this module's contract — that
`errors[].captured_at`/`recovered_at` must be precise, since a downstream consumer
treats each edge as a half-open interval — doesn't require restating the consumer's
schema, so it was dropped; the field-level precision requirement itself is already
implicit in trimmed §3.1's exact field table.

### 13. §7.2, lines 312–322 — RF-DOCK deduction-split paragraph + live incident
The `deductible_error_seconds`/`_by_source` split computed by the finalizer, and the
"five dock-side pump faults charged 455 s against a 360 s clean" incident.
**Destination: audit** (the incident — real, disprovable production provenance)
**+ lore** (the deduction-split mechanics — true, valuable, but implemented in
`job_finalizer.py`, not `error_tracker.py`).
Justification: `error_tracker.py`'s only obligation here is that `classify_error_code`
(§4.3) return the right bucket for a given code — which is fully specified. How a
*different* module then sums/deducts seconds using that classification is out of
this module's scope.

### 14. §7.3, lines 337–357 — acknowledge mid-run rationale essay
"The natural order of operations makes this the common case..."; the idle-wall-guard
second-order-effect paragraph (`extreme_idle_wall` blocker, "unexplained idle"
report); "Acknowledging is a UI intent... the post-finalize auto-clear then collects
it."
**Destination: lore** (the general UI-intent framing) **+ audit** (the idle-wall
guard consequence, which documents a real fixed regression in a *different* module,
`job_finalizer.py`'s blocker logic).
Justification: the *requirement* — mark rather than clear mid-run, setting exactly
three fields and leaving `errors[]` intact — is stated plainly and completely in
trimmed §6.3. The extended justification for *why* that requirement exists belongs
to the audit trail / the job-finalizer's own doc, not to a blind rebuild of this
module.

### 15. §7.3, lines 356–357 — `_lookup_active_job` name
"...both this check and `_lookup_active_job` ask `run_is_in_flight`, so they cannot
drift apart."
**Destination: discard.**
Justification: cardinal-rule (private method name). The guarantee itself (the
mid-run-mark rule uses the same in-flight question as latch formation, §3.1) is kept.

### 16. §7.3, line 361 — full acknowledge-service schema restatement
`SERVICE_ACKNOWLEDGE_ERROR`, `_handle_acknowledge_error` in `services/errors.py`,
parameter/selector detail, `supports_response=True`, return shape, "no panel/frontend
caller."
**Destination: discard.**
Justification: redundant — this is `services/errors.py`'s own contract, a file the
blind builder can read directly (it is not part of `error_tracker.py`). Restating
its full schema here duplicates content owned elsewhere without adding anything
`error_tracker.py` itself must implement. Trimmed §8's Integration Points table
keeps the one-line fact that a service calls `acknowledge`.

### 17. §7.5, lines 391–404 — ReadOnlyDict/HA-internals deep-copy rationale
The extended explanation of why a shallow copy fails (HA wraps a State's attributes
in a `ReadOnlyDict` but doesn't copy nested values), naming the private method
`_record_falling_edge`, plus "`get_record` is deliberately not copied — it is the
internal mutation seam" framing.
**Destination: lore** (the HA-internals explanation — true, useful for a maintainer,
not required to satisfy the requirement) **+ discard** (the private method name,
cardinal-rule).
Justification: the *requirement* — these two accessors must return a true deep copy,
because the module continues mutating nested latch state in place after handing out
a snapshot — is stated as a flat requirement in trimmed §6.5, which is sufficient to
implement correctly without knowing HA's `ReadOnlyDict` internals or the private
method's name.

### 18. §7.6, lines 406–412 — full get_recent_errors service schema restatement
Entire subsection duplicating the `recent_errors()` signature plus
`SERVICE_GET_RECENT_ERRORS`, `_handle_get_recent_errors`, the exact number-selector
config (range/default/mode), `supports_response=True`, and the service's return
shape.
**Destination: discard.**
Justification: redundant on two counts — the accessor signature/behavior is already
fully specified once in trimmed §6.5, and the service-layer schema is
`services/errors.py`'s own contract (directly readable by the builder), not
`error_tracker.py`'s.

### 19. §8, lines 416–420 — "Buffer Limits" section
Restates that `active_run_error` is a single dict (cap applies to its nested
`errors[]`), `last_device_error` is a single dict replaced wholesale, and
`recent_errors` is capped at 50.
**Destination: discard.**
Justification: redundant — every one of these facts is already established once,
precisely, in trimmed §3 (record shapes) and the §1 buffer-cap callout. A standalone
restatement section added no new information.

### 20. §9, lines 443–445 — cross-reference to doc 22 + `_code_set`/`_code_key` names
"The five classification tables accept ints AND enum strings (`_code_set` /
`_code_key`, §4.5)... Full per-brand values and counts: doc 22 §9 and each adapter's
`vocabulary.py`."
**Destination: discard.**
Justification: the substantive fact (both int and enum-string codes accepted) is
already stated in trimmed §4.3; the private names are cardinal-rule violations; the
doc-22 cross-reference points to a document not guaranteed to be part of the blind
builder's input for this experiment.

### 21. §9, lines 446–447 — "were once advertised here but not read" note
"`grace_window_seconds` and `error_code_attribute_names` were once advertised here
but not read by the tracker; both are genuinely consulted now."
**Destination: audit.**
Justification: historical doc/code-drift provenance, not a current behavioral
requirement — the current, correct behavior (both keys genuinely read, with stated
defaults) is what trimmed §7's table already asserts.

### 22. §9, lines 449–452 — `_error_tracking_cfg()` helper name
Names the module-level helper and describes its never-raises/`{}`-default
behavior.
**Destination: discard.**
Justification: cardinal-rule (private helper name). The behavior — a missing block
or key never raises, each caller applies its own default — is kept as the opening
sentence of trimmed §7.

### 23. §10, line 470 — wrong Integration Points row for job finalization
"`learning/job_finalizer.py` (via injected `error_source`, wired in
`learning/manager.py`) | `tracker.harvest_active_run(vacuum_entity_id, job_id)` |
Job finalization — folds the latch into `outcome.errors` / `had_errors` /
`error_count` / `total_error_seconds`."
**Destination: discard.**
Justification: same confirmed factual error as entry 11 — corrected in trimmed §8's
Job Finalization row to describe the real two-closure `peek_active_run` /
`commit_active_run` contract (ADDITIONS A-8).

---

## ADDITIONS (new this round — every sentence with no counterpart in the original)

Scope/method: I re-walked the trimmed candidate against the original 475-line doc
and logged every sentence asserting a fact or requirement the original never stated
in any form (prose, table row, or code block). Excluded: pure reformatting of a fact
the original already conveyed somewhere (e.g., turning a code block into equivalent
prose, or reorganizing an existing table) — those aren't new information, just a
different container for the same one. Everything below is a genuine addition,
sourced by reading `core/error_tracker.py` / its callers directly (a privilege the
blind builder does not have), so each carries real risk of drifting from what a
blind reconstruction would independently produce.

**A-1. §3.1 `acknowledged` field-table row.** Original's `active_run_error` field
table (9 rows) has no `acknowledged` row at all. *This round's finding*: adjudicated
C, decided KEEP+reword — see Round 2 Edits above. Justification for keeping: it's a
real, persisted, directly-tested field; dropping it trades a likely single-field miss
for a guaranteed one on two test assertions.

**A-2. §3.1 falling-edge stamping target.** "stamps `recovered_at` on the single
newest entry in `errors[]` that doesn't already have one (search newest→oldest, stop
at the first hit)." Original only says `recovered_at` is "stamped when this edge
recovers," never which entry when more than one is unstamped (possible: a second
rising edge can extend the latch — appending a new unstamped entry — before the
first one ever recovers). Justification: necessary and correct (source-verified),
but a blind builder without it could plausibly stamp *all* unstamped entries, or the
oldest one, instead — an untested-but-real divergence risk.

**A-3. §3.1 "A falling edge never touches `last_device_error` or `recent_errors`."**
Not stated as its own sentence in the original, though it's a direct corollary of
two facts the original *does* state separately (`last_device_error` "overwritten on
every rising edge"; `recent_errors` "append-only ring buffer of the last 50 rising
edges"). Low risk — logged for completeness since it is technically new phrasing of
an already-forced conclusion, not free-standing new information.

**A-4. §4.3 "Reads (in order)" column + explicit check order.** States
`evidence_invalidating_error_codes` is checked before `evidence_safe_error_codes`,
and `dock_sourced_error_codes` before `robot_sourced_error_codes`. Original's seam
table has no explicit ordering claim. Justification: only observable if an adapter
declares a code in both lists of a pair (a misconfiguration) — low real-world risk,
but a genuine behavioral fact not in the original.

**A-5. §5.4 "If a timer is already pending, re-entering is a no-op."** States
idempotency explicitly. The original doc never states this; it's implied by the
"grace timer" being spoken of as singular per-vacuum state throughout, but never
asserted as a rule. Justification: necessary to prevent a builder from stacking
multiple timers per vacuum, which nothing in the original explicitly forbids.

**A-6. §6.1 explicit constructor host contract.** "`runtime_manager` must expose a
`.data` dict (§2) and an async `.async_save()`." The original doc has no
`§7.1`-equivalent constructor-parameter-contract sentence — it opens directly with
`tracker.start(...)`/`.stop()` and only says the class is "constructed... after the
runtime `EufyVacuumManager` is loaded" (source docstring, not the doc). Justification:
DR standard §4.4 requires an explicit host contract; the original doc's omission of
one was itself part of the collapse-zone pattern the standard calls out.

**A-7. §6.2 the full `peek_active_run` / `commit_active_run` behavioral spec.**
Signatures, deep-copy-on-peek, identity check by `first_seen_at` + `error_count`
equality, moved-on handling (leave latch untouched, return `False`), and the
return-`True`-only-when-actually-cleared rule. The original doc mentions
`peek_active_run` exactly once, in passing, inside the deep-copy rationale for a
different pair of methods ("`peek_active_run` deep-copies for the same reason and
says so") — it never gives either method a signature, a behavior spec, or even its
own subsection. This is the single largest addition in the candidate. Justification:
directly replaces removal entry 11 (a confirmed-false passage) — without it, the
document would state no correct contract at all for how the finalizer actually
harvests errors, which is worse than a large but source-verified addition. Highest
residual risk in this candidate if any part of my read of `peek_active_run`/
`commit_active_run`'s behavior is subtly wrong.

**A-8. §8 Integration Points "Job finalization" row (peek/commit two-closure
description).** Companion to A-7; replaces removal entry 23 (also a confirmed-false
row in the original).

**A-9. §7 Adapter Registry Dependencies table's literal `Default` column values**
for `message_is_code` (`False`), the four code-list configs (`[]` each), and
`error_label_keys` (`{}`). The original conveyed these defaults only as prose
consequences ("a brand that omits this deducts nothing," "a code in neither table is
unattributed") scattered across §4.5/§9, never as a typed default value in a table
cell next to the config path. Justification: makes an already-true fact
machine-checkable at a glance; low risk since it's a direct restatement of prose the
original did contain, just reshaped into a table cell.

**A-10. §6.2 `harvest_active_run` deprecation clause (this round, Edit 2).** "kept
only because a legacy test asserts this exact semantic; a one-shot destructive read
can't be made safe against a persistence failure... do not add new callers." Zero
counterpart in the original, which instead wrongly implied the method is what the
finalizer actively calls (removal entry 11). Justification: mandated this round;
verified true (deprecation docstring + zero-caller grep, both cited in Round 2 Edits
above).

**A-11. §4.3 `error_label_key` conformance invariant (this round, Edit 1).** No
counterpart in the original at all — a wholly new, earned invariant supplied
verbatim by the coordinator this round, not authored by the trim agent.

---

## Tag counts (removals, sections 1–23, unchanged from Trim 1)

| Tag | Count |
|---|---|
| discard | 13 |
| audit | 5 |
| lore | 7 |

(Entries 6, 13, 14, 17 are double-tagged, so tag counts sum to more than 23.)

## ADDITIONS count: 11 (A-1 through A-11)
