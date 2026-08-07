# Semantic Flight Recorder — Compact Receipts, Replayable Prose

## Purpose

Vacuum Agent already has the enabling mechanism: a silent, bounded, per-operation flight recorder.

The next step is to stop treating that recorder as a container for human-written DEBUG prose and instead let it carry **semantic receipts**: tiny, stable identifiers plus only the variable facts needed to explain what happened.

The runtime records compact evidence.

Later, the trace is fed back into Vacuum Agent.

Vacuum Agent resolves the identifiers through a semantic catalog and reconstructs the execution as readable prose — including localized prose if desired.

The core model is:

> **Runtime records facts.  
> Catalog preserves meaning.  
> Replay reconstructs the story.  
> Localization chooses the language.**

This makes comprehensive success-path instrumentation practical without turning ordinary Home Assistant logging into a flood.

---

# 1. Why the Existing Flight Recorder Makes This Practical

The existing flight recorder already solves the operational problem that would otherwise make semantic instrumentation unreasonable.

It can:

- capture only Vacuum Agent's DEBUG output;
- keep that output out of `home-assistant.log`;
- store it in a bounded in-memory ring;
- arm only when needed;
- scope capture to one service, a family of services, or a broader run;
- use an operation correlation context so unrelated concurrent polling does not contaminate the trace;
- keep child asyncio tasks created inside the operation associated with the same capture;
- dump the bounded capture on demand;
- redact secrets and truncate pathological records.

That means Vacuum Agent does **not** need to emit permanent verbose narration during every normal run.

The semantic receipts are only captured when the recorder is armed.

The existing recorder already demonstrated the value of this scoping: an operation that produced a multi-megabyte global DEBUG capture could collapse to only the few lines causally associated with the selected service.

Semantic receipts make the scoped trace even smaller.

---

# 2. The Unlocking Change

Do not record this at runtime:

```text
Queue resolution completed successfully for map 1 with three selected rooms
after applying the effective run configuration.
```

Record something conceptually like:

```text
7Kp3aQ91Lm2XcRf | P | m=1 | n=3
```

Where:

- `7Kp3aQ91Lm2XcRf` is a stable semantic identifier;
- `P` means the checkpoint completed successfully;
- `m=1` and `n=3` are the variable facts required by that semantic event.

The prose lives elsewhere.

When the capture is replayed, the semantic catalog resolves the identifier:

```text
7Kp3aQ91Lm2XcRf
→ queue_resolution_completed
→ "Queue resolution completed successfully for map {map_id}
   with {room_count} selected rooms."
```

The imported trace can then render:

> Queue resolution completed successfully for map 1 with three selected rooms.

The raw capture remains tiny.

---

# 3. Stable Semantic IDs

A semantic ID should be:

- opaque;
- stable;
- immutable once published;
- unique;
- independent of English wording;
- cheap to store;
- cheap to compare.

A 15-character token provides vastly more namespace than this system can realistically exhaust.

Example:

```text
7Kp3aQ91Lm2XcRf
```

The token is not required to be human-readable.

It is an address into the semantic catalog.

## Do not hash the prose itself

If the identifier is literally derived from the English sentence, an editorial rewrite changes the ID.

That is undesirable.

The semantic identity should survive wording changes.

Therefore:

> **The ID identifies meaning, not wording.**

If the meaning changes materially, mint a new semantic ID or an explicit new semantic-contract revision.

---

# 4. Success Is Not Allowed to Be Silent

This is the key rule.

A conventional log often records errors while allowing successful intermediate steps to disappear.

That creates an ambiguity:

```text
A
B
D
```

Did `C`:

- execute successfully but remain silent;
- fail to instrument;
- get legitimately bypassed;
- never execute?

For every checkpoint declared causally important:

> **Success emits a receipt too.**

Expected:

```text
A → B → C → D
```

Observed:

```text
A → B → D
```

Now `C` is a bounded investigation target.

Its absence is evidence.

It is not automatically proof of a production defect — the route may legitimately bypass it, or instrumentation may itself be wrong — but the system can no longer hide successful execution behind silence.

---

# 5. Why Success Receipts Are Affordable

Normally, "log every successful step" is a terrible idea.

Human prose is large.

It creates noisy files, repetitive strings, and permanent logging volume.

This design changes the economics.

A success checkpoint can cost roughly:

```text
semantic ID + tiny status + only changing fields
```

The same prose is not repeated thousands of times.

It exists once in the catalog.

Because the existing flight recorder is:

- silent when unarmed;
- bounded when armed;
- scopeable to an operation;
- isolated from the main HA log;

Vacuum Agent can afford much denser semantic instrumentation during a targeted reproduction.

This is what makes "everything important speaks" operationally reasonable.

---

# 6. The Semantic Catalog

Each stable ID resolves to a catalog entry.

Conceptually:

```yaml
id: 7Kp3aQ91Lm2XcRf
family: queue.resolve
meaning: queue_resolution_completed
outcomes:
  P: pass
required_fields:
  m: map_id
  n: room_count
english: >
  Queue resolution completed successfully for map {map_id}
  with {room_count} selected rooms.
localization_key: semantic.queue.resolve.completed
contract_revision: 1
```

The catalog can also declare:

- subsystem ownership;
- severity;
- expected predecessor/successor relationships;
- optional fields;
- field types;
- whether a checkpoint is required on a given route;
- deprecation/supersession information;
- links to DR/test/audit references.

The raw recorder does not need any of that prose.

It needs only the semantic ID and facts.

---

# 7. Replay Back Into Vacuum Agent

The intended debugging loop becomes:

1. A service or job misbehaves consistently.
2. Arm the flight recorder.
3. Choose scope:
   - one service;
   - service family;
   - whole job;
   - broad temporary capture when the boundary is unknown.
4. Reproduce the failure.
5. Dump the compact trace.
6. Feed the trace back into Vacuum Agent.
7. Vacuum Agent resolves each semantic ID through the correct catalog.
8. The decoder reconstructs the execution in order.
9. Inspect the first missing, contradictory, failed, or unexpected checkpoint.
10. Build the regression test around the actual causal seam.
11. Re-run and compare the corrected execution story.

The system becomes capable of writing its own incident witness statement.

---

# 8. Three Views of One Capture

One raw trace can support multiple views.

## Raw forensic view

```text
004812|18:41:22.031|J2f91|7Kp3aQ91Lm2XcRf|P|1,3
004813|18:41:22.047|J2f91|mN8vT2Za04Qr1Hs|P|3
004814|18:41:22.083|J2f91|b6Lq92XeR4sW0Jp|C|1
```

## Engineer view

```text
QUEUE.RESOLVE.COMPLETE   PASS   map=1 rooms=3
START.GATES.COMPLETE     PASS   eligible=3
DISPATCH.BEGIN           CALL   room=1
```

## Human narrative

> The queue resolved successfully for map 1 with three selected rooms. All three selected rooms passed the start gates. Dispatch then began for room 1.

Same evidence.

Different rendering.

---

# 9. Translation Falls Out Naturally

The capture itself is language-neutral.

It contains:

- semantic identity;
- outcome;
- canonical structured facts.

Therefore the same trace can be rendered through Vacuum Agent's localization layer after capture.

A replay requested in English can produce English prose.

A replay requested in another supported locale can produce that language.

The execution evidence does not change.

## Translation must never be in the recording path

Recording must not depend on:

- a translation bundle;
- a UI;
- successful prose lookup;
- network access;
- rendering code.

The runtime records the semantic receipt first.

Translation happens only when somebody asks to interpret the trace.

Fallback should preserve forensic usefulness:

1. requested locale;
2. appropriate locale-family fallback;
3. English catalog prose;
4. raw semantic ID + raw structured fields.

A broken localization system must never destroy the evidence.

---

# 10. Correlation and Causality

Chronology alone is insufficient once concurrent work exists.

Where needed, semantic records should carry compact correlation data such as:

- job ID;
- service-call ID;
- vacuum ID;
- map ID;
- phase ID;
- room ID;
- queue-step ID;
- parent/span ID.

The recorder's existing operation context already provides a natural starting point for this.

A replay should be able to answer:

- Which events belonged to this operation?
- Which child work was caused by this service call?
- Which dispatch belonged to this queue step?
- Which persistence event followed this decision?
- Which event was emitted because of this state transition?

The important distinction is:

> **Chronological order tells what happened near each other.  
> Correlation tells what belonged together.**

---

# 11. Async Context and the Existing Recorder

The current per-operation recorder uses operation context to exclude unrelated concurrent work.

That is especially valuable here.

A semantic trace for `start_selected_rooms` should not accidentally fill with:

- unrelated polling;
- another service call;
- background activity that merely overlapped in wall-clock time.

Child asyncio tasks created inside the traced operation inherit the operation context, so follow-through work can remain associated with the same capture.

Executor-thread work is a known boundary because context does not automatically cross into thread-pool execution.

Semantic instrumentation must explicitly account for that boundary where causally important executor work needs to remain in the same trace.

---

# 12. Missing Events Become First-Class Evidence

The catalog may eventually express allowed semantic transitions.

For example:

```text
QUEUE_RESOLVED
    →
    PAYLOAD_BUILT
    OR
    RUN_BLOCKED
```

If a replay contains:

```text
QUEUE_RESOLVED
```

but neither valid successor, the decoder can report:

> Queue resolution completed, but no permitted next semantic checkpoint was recorded.

Possible causes include:

- real production route skipped;
- missing instrumentation;
- undocumented legitimate branch;
- trace truncation/corruption.

The decoder should not manufacture a verdict.

It should identify the semantic discontinuity.

---

# 13. Semantic Coverage

Traditional coverage asks:

> Did this line or branch execute?

Semantic coverage asks:

> Did each important causal transition produce evidence that it occurred?

That creates a different test surface.

Useful obligations include:

- every emitted semantic ID exists in the catalog;
- every required checkpoint emits on success;
- failure paths emit the appropriate semantic outcome;
- required event fields are present;
- fields use canonical units/types;
- removed instrumentation causes the corresponding instrumentation test to fail;
- expected route relationships are exercised;
- historical traces can still decode;
- unknown IDs degrade to raw evidence instead of crashing.

A subsystem can have high line coverage and still be semantically dark.

The flight recorder makes that darkness measurable.

---

# 14. Relationship to Behavioral Tests

The recorder does not replace tests.

It shortens the path from symptom to the correct test.

```text
symptom
  ↓
arm recorder
  ↓
reproduce
  ↓
semantic replay
  ↓
find wrong/missing checkpoint
  ↓
identify causal seam
  ↓
write regression pin
  ↓
prove pin bites
  ↓
fix
  ↓
replay again
  ↓
corrected story
```

Tests prove the behavior.

The semantic recorder tells the maintainer where the behavior departed from the expected causal path.

---

# 15. Relationship to Audit

A semantic trace is useful audit evidence because it can show the actual runtime path without requiring an auditor to infer that path from scattered ordinary logs.

It can support:

- verifying a service actually reached a subsystem;
- identifying missing delegation;
- comparing provider routes;
- validating ordering claims;
- preserving hardware reproduction evidence;
- showing which guard fired;
- proving which successful checkpoints occurred before failure;
- comparing pre-fix and post-fix runs.

The audit record can preserve the decisive semantic trace without preserving megabytes of unrelated logs.

---

# 16. Relationship to Disaster Recovery

DR documentation says:

> **This is how the system is supposed to work.**

The semantic flight recorder says:

> **This is what this execution actually did.**

Together they let a future maintainer compare intended causal structure against observed execution.

The semantic catalog itself also becomes reconstructive knowledge:

- important execution checkpoints;
- their meanings;
- their required fields;
- possible outcomes;
- subsystem ownership;
- expected relationships.

That is useful both for debugging and for future resurrection of the system.

---

# 17. Relationship to the Documentation Quartet

## Design — this is why

Why semantic recording exists. Why success must speak. Why identity is separated from prose.

## DR — this is how

Recorder schema, catalog contract, replay behavior, versioning, correlation, failure handling.

## Dev — this is what I am changing right now

Instrumentation being added, new checkpoints, unresolved semantic gaps, decoder changes.

## Audit — this is what happened and what it cost to learn

Incidents where traces exposed false assumptions, missing calls, wrong ordering, bad instrumentation, or unexpected routes.

---

# 18. Catalog and Trace Versioning

Old traces must remain interpretable.

A capture header should preserve enough identity to choose the correct decoder/catalog generation.

Conceptually:

```text
format: VA-FR
schema: 1
catalog: 2026.08.06.1
app_version: ...
capture_started: ...
```

Rules:

- semantic IDs never silently change meaning;
- prose may be rewritten;
- translations may improve;
- formatting may improve;
- decoder presentation may improve;
- old semantic meanings remain available for historical replay.

If a meaning changes materially, create a new semantic identity or revision rather than rewriting history.

---

# 19. Recorder Safety

The compact format must not become an excuse to dump arbitrary runtime state.

Each semantic event should have an explicit field allowlist.

Avoid:

- credentials;
- bearer tokens;
- API keys;
- passwords;
- full state objects when a few canonical values are sufficient;
- giant map/image payloads;
- arbitrary exception locals.

The existing recorder's redaction and truncation controls remain defense-in-depth.

The semantic layer should reduce the amount of sensitive or huge data that ever reaches the recorder in the first place.

---

# 20. Instrumentation Must Tell the Truth

A semantic receipt is a claim.

Therefore it must be emitted at the boundary it claims.

Bad:

```text
DISPATCH_ACCEPTED
```

emitted when the dispatch function is merely entered.

Good:

```text
DISPATCH_ATTEMPTED
```

on call entry.

Then:

```text
DISPATCH_ACCEPTED
```

only after the provider boundary actually reports acceptance.

Otherwise the semantic recorder becomes a confident liar.

Each checkpoint needs precise placement semantics.

---

# 21. Testing the Recorder

The semantic recorder must be tested under the same evidence doctrine as the rest of the system.

For an important checkpoint:

1. exercise the guarded behavior;
2. assert the semantic receipt appears;
3. assert its required facts;
4. deliberately remove or bypass the emission;
5. prove the instrumentation test fails;
6. restore it;
7. return green.

Decoder tests should prove:

- unknown IDs remain inspectable;
- malformed traces fail safely;
- catalog lookup failure preserves raw evidence;
- translation failure falls back;
- event order is preserved;
- correlation grouping is deterministic;
- historical catalog generations remain decodable.

The recorder is not trustworthy merely because it emits output.

Its pins must bite.

---

# 22. Why This Unlocks the System

The existing flight recorder already makes targeted capture cheap:

> arm it only when needed, scope it to the operation, keep the main HA log clean, and bound the memory.

Semantic receipts remove the remaining cost:

> stop repeating human prose at runtime.

That makes dense success-path instrumentation realistic.

The result changes the debugging question from:

> Which debug line might explain this?

to:

> What did the system say it did, in what causal order, and where did that story stop matching the expected one?

It also changes the artifact from a disposable debug log into a compact semantic execution record that can be:

- replayed;
- translated;
- compared;
- audited;
- tested;
- interpreted by agents;
- preserved as historical evidence.

The runtime does not need to write the story.

It only needs to leave enough semantic receipts for the system to reconstruct the story later.

---

# Governing Invariants

1. **Runtime records semantic facts, not human prose.**
2. **Every important semantic checkpoint has a stable immutable identifier.**
3. **Semantic identity is independent of wording.**
4. **Important successful execution is not allowed to be silent.**
5. **The existing scoped flight recorder is the capture boundary that makes dense receipts practical.**
6. **Unarmed operation does not produce a permanent semantic-debug flood.**
7. **Translation never sits in the evidence-recording path.**
8. **Raw evidence remains readable when catalog or localization lookup fails.**
9. **Semantic events carry only explicitly permitted variable facts.**
10. **A semantic receipt is emitted only when the boundary it claims has actually occurred.**
11. **Missing expected receipts are evidence, not automatic proof of a defect.**
12. **Correlation distinguishes causal work from merely concurrent work.**
13. **Historical traces remain decodable.**
14. **Recorder and decoder tests must prove their pins bite.**
15. **The recorder explains execution; behavioral tests still establish correctness.**

---

# Final Principle

> **Everything important speaks, but it does not need to speak in prose while it is happening.**

The existing flight recorder decides **when and what to capture**.

The runtime emits **tiny semantic receipts**.

The catalog remembers **what those receipts mean**.

The replay decoder reconstructs **what the system did**.

The localization layer decides **how to say it**.

A failing job can then be reproduced once, its compact trace dumped back into Vacuum Agent, and the system can answer:

> **Tell me exactly what you did.**

---

# REVIEW NOTES (coordinator, 2026-08-06) — for the later design round

Status: DESIGN PARKED by Chris ("for more design work later"). Do not implement. This
resolves both blockers that deferred Semantic Trace (2026-07-02) and the prose
instrumentation style (2026-08-02): prose mass -> catalog-once; untranslatable -> replay-time
localization out of the recording path.

Open design questions for the round:

1. ALWAYS-ON RING — EMPIRICAL, DECIDE IN PRACTICE (Chris, 2026-08-06). Always-on is
   "really iffy"; flushing is the concern. Working sketch: AUTO-ARM AT JOB START, flush
   the job's receipts to a file stored alongside job history (a persisted sibling of the
   job JSON — covers the class where the real losses happened, e.g. the 2026-08-01
   stepped run); continuous capture for non-job activity remains open. FACT (verified
   debug_capture.py:280-284): unarmed installs intercept NOTHING — DEBUG level +
   propagate=False + handlers exist only between start() and stop(); dormant receipt call
   sites cost a level check. True always-on = holding armed config forever: technically
   trivial, but converts zero-cost-for-everyone into small-nonzero-for-everyone.
2. RUNTIME EXPECTATIONS AS FACTS — RESOLVED (Chris, 2026-08-06): the expectation is just
   ANOTHER RECEIPT whose payload is a catalog ID: `EXPECT | <id of job_started> | n=1`.
   Static grammar (sec 12: what MAY follow) and runtime expectations (what SHOULD follow
   this run) share one vocabulary; the decoder reconciles both with the same matcher.
   `EXPECT room_transition n=0` IS the brand-model statement in three tokens; an EXPECT
   with no matching receipt before its correlation scope closes is loud by construction
   (`0/1 observed`). Emission split keeps invariant 10 honest: the expectation is emitted
   by the boundary holding the model (dispatch), fulfillment by the boundary observing it
   — disagreement between two code sites is what makes the signal mean something.
3. NEVER-INSTRUMENTED NEW CODE — DECIDED (Chris, 2026-08-06). Two rules, enforced in
   LOCAL tests (keep CI lean, sole-maintainer discipline):
   (a) MECHANICAL: any DEBUG emission without a catalog key fails locally — no bare
       prose debug lines once the system exists.
   (b) AUTHORING: writing a causally-important item requires writing its debug/receipt —
       a review-checklist rule (not mechanically lintable; "causal" is a judgement).
4. ID SHAPE — DECIDED (Chris, 2026-08-06). The opaque 15-char hash was illustrative for a
   quick dump only. IDs must be SOMEWHAT VIEWABLE in the raw dump (readable dotted keys,
   i18n-key style); full details come from catalog lookup or passing the dump through the
   tool. Stability by discipline + the check script, not by opacity. Named constants in
   code stand.
5. DECODER HOME — DECIDED (Chris, 2026-08-06). LOCAL repo tool only for now — he is the
   sole maintainer. Promote to a CLI (and possibly a card surface) only if more
   maintainers appear.
6. PILOT SCOPE — DEFERRED (Chris, 2026-08-06). The 2026-08-02 testbed ruling
   (phase-advance -> child-finalize chain; success = dump alone localizes the
   missing-child bug) carries forward unchanged; whether the pilot builds minimal catalog
   machinery or fakes the decoder first is specifically not decided yet. Naming: avoid
   trace_* (taken by pose capture).

Related: memory project_debug_flight_recorder + project_semantic_trace_deferred (treat as
ONE item — this doc is now that item's design). The forum post remains the only durable
spec for debug_capture.py itself; this doc does not change that.
