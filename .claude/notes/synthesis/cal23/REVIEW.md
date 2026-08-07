# CAL-23 — Review Agent adjudication (round 1)

Adjudicator: review agent. Subject: `trim1/section.md` (trimmed doc 23) vs.
`sandbox-b1/.../core/error_tracker.py` (blind reconstruction), judged against
`custom_components/eufy_vacuum/core/error_tracker.py` at repo HEAD.

**Headline: 1 D, 3 C, 0 A, 0 B.** The single D's provenance is **NEVER-PRESENT** —
the trim burned no confirmed meaning in this round. Three of the four reds pin
incidental original behavior with no consumer, no invariant and no stated design
behind them; they are the tester-side exploit this protocol exists to catch.

---

## 0. What I checked (beyond reading the four artifacts)

Adjudicating C required leaving the ablation bubble and checking the real system:

- **Consumer grep, whole repo** (`custom_components/`, `src/`, `docs/`) for
  `acknowledged`, `current_message`, `error_label_key` / `label_key`,
  `get_active_run_latch`, `active_run_error`.
- **`_validate_adapter`** (`adapters/registry.py:298+`) — to establish whether
  malformed `error_tracking` values are *reachable*.
- **`adapters/config_schema.py`** — the declared type of each key at issue.
- **The card's own fault renderer** (`src/state/faults.js::faultLabel`) — to
  establish whether a coerced label is observable downstream.
- **`learning/manager.py::_run_error_rows`** — the one production consumer of
  `error_label_key`.
- **The frozen legacy suite** (`tests/integration/test_core_error_tracker.py`) —
  whether any pinned behavior was already asserted.
- **`git log -2 -- docs/dev/23-error-tracker.md`** and the diff `31edf3b..e649b9e`
  — to see what the trimmer actually held in its hands (the pre-correction §7.2).
- **`sandbox-b1/MANIFEST.json` + `BUILD-BRIEF.md`** — the sandbox boundary, for
  the B question. `docs/`, `src/`, `tests/` excluded; the whole
  `custom_components/` tree minus the target present.

**No B verdict is available in this round.** Every divergence traces to prose
silence, not to a denied dependency. The excluded `docs/` tree is the experiment's
premise (doc 23 is the spec), not a boundary error; and nothing the builder needed
from `custom_components/` was missing — RECONSTRUCTION-NOTES' call-site
cross-checks all resolved.

---

## 1. Verdicts

| # | Red | Verdict | Provenance | Pays? |
|---|-----|---------|-----------|-------|
| 1 | `acknowledged` survives a fresh extending rising edge | **C** | n/a | no |
| 2 | negative `grace_window_seconds` clamps to ~0 | **C** | n/a | no |
| 3 | `error_label_key` must not `str()`-coerce a non-string value | **D** | **NEVER-PRESENT** | yes |
| 4 | primary-channel message stored VERBATIM | **C** | n/a | no |

---

## 2. RED 1 — `acknowledged` survives a fresh rising edge → **C**

**The divergence is real.** Original `_record_rising_edge` never touches the key on
the extend branch; the reconstruction runs `latch.pop("acknowledged", None)` on
every rising edge (recon line 629). Certification (m1_ack) is honest.

**Load-bearing test — fails on all three prongs.**

- *Consumer*: **none**. Repo-wide, `acknowledged` on the latch is **written by
  `acknowledge()` and read by nothing.** It rides out to HA as an attribute
  (`sensor/error.py:141`, `attrs = dict(latch)`) and into the durable job record
  (`outcome["errors"]` is the full latch verbatim), but no code in
  `custom_components/` or `src/` branches on it. The post-finalize auto-clear
  (`sensor/__init__.py:504`) keys on `current_message`, not on `acknowledged`.
  The active-run sensor's `native_value` and the binary sensor's `is_on` key on
  `current_message` / `errors` / `error_count` — all preserved by the
  reconstruction, so **every shipped surface behaves identically under both
  implementations.**
- *Invariant*: none inside doc 23. The nearest statement is in a **sibling** doc
  (`03-data-model.md:2116`, "`acknowledged` is written **only** by
  `acknowledge(...)`"), which is out of ablation scope and in any case speaks to
  who writes `True`, not to who may delete the key.
- *Stated design*: doc 23 §7.3's entire rationale for marking-instead-of-clearing
  is **preserving `errors[]` / `error_count` / `had_errors` for the finalizer** and
  its idle-wall exemption. The reconstruction preserves all of that exactly. The
  design statement does not reach the flag's persistence.

**The original's behavior here is an omission, not a decision.** There is no
comment on it, no legacy test on it (the two legacy assertions at
`test_core_error_tracker.py:261` and `:768` check the flag *immediately after*
`acknowledge()`, never after a subsequent edge), and no caller. The
reconstruction's choice is defensible on its own terms and arguably better — a
brand-new fault arriving pre-acknowledged is the more surprising state. When both
directions satisfy every consumer and every stated design, the pin is asserting a
**non-contract**.

**Verdict: C.** The pin certified that it *detects* the change; it never
established the behavior as contract. Note the honest half: the builder's
declared low-confidence #1 was a **real gap** — it just is not a *demonstrated
missing invariant*. The correct disposition is a **product decision** ("what does
this flag mean across a re-latch?"), recorded and then pinned in doc 03 + doc 23
together — not DR prose retro-fitted to an accident.

*Contingency, if the campaign overrules C → D*: provenance would be
**NEVER-PRESENT**. The original doc 23's §4.1 field table does not list
`acknowledged` at all; it appears only in §7.3 prose, which is equally silent on
the lifecycle.

---

## 3. RED 2 — negative `grace_window_seconds` → **C**

**The divergence is real.** Original: `max(0.0, _grace_s)` → `async_call_later(0)`
→ fires next tick. Reconstruction: `if seconds < 0: seconds = 5.0`.

**Load-bearing test — fails.**

- The original's `max(0.0, …)` is a **defensive floor on the scheduling
  primitive** (don't hand `async_call_later` a negative). "Fires immediately on a
  negative declaration" is a *side effect* of that floor, not a designed semantic
  for negative input. Nothing in the module, the docs, or the adapters treats a
  negative window as meaningful.
- *Reachability*: technically yes — `_validate_adapter` performs **no validation
  of the `error_tracking` block at all** (it checks only `mapping`,
  `job_segmenter`, `room_attribution` engines), so a UI/service-authored stored
  config could carry `-10`. Both shipped adapters declare `5`.
- *Consumer consequence*: a placeholder edge lands ~0 s vs ~5 s after the
  secondary channel fires. No consumer distinguishes; no invariant is broken
  either way. If anything the reconstruction's choice (fall back to the documented
  default) is the more conservative reading of §5.5's *purpose* — the window
  exists to give the real message a chance, and a ~0 window disables it.
- *Stated design*: §5.5 / §7 flag exactly two deliberate non-configurables (the
  vacuum-state hardcode, and `0`-is-honored). Negatives are named nowhere, in
  either doc version.

**Verdict: C.** Codifying "a declared negative fires immediately" into DR prose
would enshrine an implementation artifact and instruct future rebuilds to honor a
nonsensical configuration. *Optional, non-owed*: if the project wants the input
closed at all, the cheap line is "a declared window below zero is treated as
zero" — offered as a DECISION, not as a demonstrated-missing invariant.

---

## 4. RED 3 — `error_label_key` value coercion → **D** (provenance NEVER-PRESENT)

**The divergence is real.** Original: `return value if isinstance(value, str) and
value else None`. Reconstruction: `return str(value) if value is not None else
None` — so `{"70": 12345}` resolves to the fabricated key `"12345"` and
`{"71": ""}` resolves to `""`.

**Load-bearing test — passes on the *stated design* prong.**

- *Stated design*: the function's declared return is **"an i18n key, or `None`"**
  (trimmed §4.3; the original adds the shape `fault.<brand>.*` and "`None` means
  the card renders the raw code — honest and searchable"). `"12345"` is **neither
  an i18n key nor `None`** — the reconstruction violates the seam's own declared
  return contract, which is a different class of thing from REDs 1/2/4, where no
  statement is contradicted. `adapters/config_schema.py:686` independently types
  the map as `dict[int|str, str]`, so the original is enforcing a declared type at
  the read seam and degrading to "no label".
- *Reachability*: yes, same route as RED 2 — the `error_tracking` block is
  unvalidated at registration, so a malformed stored config reaches this code.
- *Consumer consequence today*: **latent, not observable.** The one production
  consumer, `learning/manager.py::_run_error_rows`, hands `label_key` to the card,
  and `src/state/faults.js::faultLabel` independently requires the
  `fault.<brand>.<slug>` shape (`parts.length >= 3 && parts[0] === "fault"`) before
  translating — so `"12345"` and `""` both fall through to the raw-code path,
  exactly as `None` would. I record this honestly: **the card's own defensiveness
  means no user-visible harm today.** It makes the seam's guard a first line of
  defense rather than the only one; it does not make the declared return contract
  optional, and any second consumer of `label_key` (a template, a future
  renderer) gets a fabricated key.

**Misreading artifact (required for D).** From the trimmed prose alone:

1. §4.3's signature row reads `error_label_key(vacuum_entity_id, code) -> str | None`.
2. The same row specifies **only the key side** of the lookup: reads
   `error_label_keys` (`dict`; looked up by both the normalized key and its string
   form). The map's **value** type is never stated — `dict`, unqualified.
3. §7's registry table repeats the key as `error_tracking.error_label_keys`,
   default `{}` — again no value type.
4. A competent builder implements the two-step key lookup, then reads the declared
   `-> str | None` as an **obligation on the return type** and satisfies it the
   obvious way: `str(value) if value is not None else None`. Coercion *looks like*
   conformance to the stated signature.
5. Nothing in the trimmed prose says a non-conforming entry must resolve to "no
   label", and BUILD-BRIEF explicitly instructs the builder **not** to "pad
   defensively to cover meanings you cannot find stated" — so adding an
   `isinstance` filter would have been the *rule-violating* move.

That chain is reproducible from the trimmed text alone. **D confirmed.**

**Provenance: NEVER-PRESENT.** I searched the original doc for the *concepts*, not
just keywords — value validation, malformed/non-conforming map entries, coercion,
non-string values. `error_label_keys` appears in exactly three places at HEAD:
§4.5's seam table (line 179), §4.5's read-time-fault-naming paragraph (181-188),
and §9's registry table (line 454). All three speak only about **keys** ("string
keys tolerated — JSON round-trip") and about the *consumer's* behavior when the
answer is `None` ("the card renders the raw code — honest and searchable"). The
original's extra `fault.<brand>.*` shape hint (dropped by the trim) is suggestive
but does not determine "reject a non-conforming entry" — a builder handed the
untrimmed doc faces the same silence. **The ablation discovered pre-existing
underspecification in a truth-passed DR doc; this invariant is new knowledge
earned by the loop.**

**Candidate invariant (ledger-ready):**

> `error_label_key` returns a declared label only when the adapter's label map
> stores a non-empty string for that code; any other stored value — a number, an
> empty string, a nested structure — resolves to `None`, exactly as an absent
> entry does. A label is never manufactured from a non-conforming entry.

*Misreading it prevents*: reading the `-> str | None` return type as an obligation
to coerce whatever the map holds, which turns a malformed adapter declaration into
a fabricated i18n key on a durable read path.

---

## 5. RED 4 — primary-channel message stored verbatim → **C**

**The divergence is real.** Original stores `str(new_state)`; the reconstruction
stores `str(new_state.state).strip()`, so `"  Stuck in dock  "` persists as
`"Stuck in dock"`.

**Load-bearing test — fails.** This was the closest call of the four; I walked
every path the message text reaches.

- *Consumers*: `sensor/error.py` (`current_message` → attributes + the derived
  `message` attribute), `binary_sensor.py:140` (attribute passthrough),
  `core/manager.py:3424` (`lifecycle_message` for the card), the `recent_errors`
  service, and the durable job record. **Every one is display or passthrough.** No
  code anywhere compares the stored message to anything.
- *The one equality comparison in the module* — the §5.5 re-arm guard,
  `current_message == unknown_error_message` — compares against the **adapter's
  placeholder**, a value never sourced from the primary channel, so stripping the
  primary message cannot reach it.
- *Code capture is unaffected*: the `message_is_code` path normalizes through the
  §4.2 rules, which strip anyway — identical codes under both implementations.
- *Rendering is unaffected*: the card renders into HTML, where leading/trailing
  whitespace collapses.
- *Stated design*: §3.1 types `current_message` as "Latest error text"; the
  stripped text **is** the latest error text. §5.1's stripped/lowercased rule is
  scoped to the predicate, which scopes normalization *for detection* — it does
  not assert that storage is unnormalized. Nothing is contradicted. The pin's own
  docstring concedes "no stated normalization step": it is pinning an **absence of
  behavior**, which is the shape most prone to over-pinning.

**Verdict: C.** The original simply never normalized; that is not the same as a
contract that it must not. *Optional, non-owed*: if the project wants raw-evidence
fidelity guaranteed (it is a real house instinct — archive raw inputs, don't
launder evidence), the honest route is a DECISION plus one clause in §3.1
("stored exactly as the channel reported it"), not a red paid against the trim.

*Contingency, if the campaign overrules C → D*: provenance would be
**NEVER-PRESENT** — the original §4.1 is equally silent ("Latest error message
(`""` after recovery)"), and §5.1's strip is scoped to detection there too.

---

## 6. Green-pin sample check (3 of 8) — incidental vs. contract

Sampled for the same judgement, since a green pin asserting incidental behavior is
quiet over-pinning entering the apparatus.

### PIN 2b — `test_pin_zero_valued_entity_does_not_stop_the_code_scan` → **CONTRACT. Keep.**
§4.1 states the search *order* ("first against the `error_message` entity's
attributes, then the vacuum entity's") and the win condition ("the first attribute
holding a **non-zero int** wins"). Together those determine continuation past a
zero — the builder's declared "ambiguity #2" is actually resolvable from the
trimmed text. Strongly load-bearing in production: for Eufy the real code lives on
the **vacuum** entity while the **message** entity is searched first, so a
scan-stopper on any zero would return `code = None` brand-wide and make all five
classification tables unreachable at runtime — precisely the `live:RB-ERR-2`
failure class. Good pin, correctly green.

### PIN 9 — `test_pin_harvest_active_run_ignores_a_job_id_mismatch` → **CONTRACT BY DECLARATION, but pinned on a surface the source doc calls DEPRECATED.**
The tolerance itself is stated outright in §6.2, so the pin is not incidental. The
problem is upstream of the pin: the trimmed §6.2 says `harvest_active_run`
"**Remains a fully supported method** independent of which caller currently uses
it", while the corrected source doc at HEAD says it is "**DEPRECATED** with zero
production callers … Do not add callers." The pin therefore enforces a live
contract on a deprecated, zero-caller surface. Keep the pin (it guards a stated
behavior the legacy tests also assert), but fix the trimmed prose — see §7.

### PIN 11 — `test_pin_read_accessors_never_schedule_a_save` → **BORDERLINE: contract by consequence, not by declaration.**
Nothing in either doc version states this; §2 says only that *mutations* schedule
a save. The pin asserts an **absence**, authored from the builder's
RECONSTRUCTION-NOTES #8 rather than from prose. It survives the incidental test
only on consequence: `get_active_run_latch` is called on **every** entity state
read (three entities, plus the lifecycle snapshot), so a save scheduled from a read
is a write-amplification storm, not a cosmetic difference. That is real, but it is
an implementation-quality property, and the reconstruction matched it unprompted —
so **no invariant is owed and none should be added.** Flagging it as the sample's
weakest pin: this is the shape (pin-the-absence) that would let a future tester
farm reds without contract closure. Recommend the apparatus require, for any
absence-pin, a named consequence — as this one happens to have.

---

## 7. Trim-fidelity findings (independent of the reds)

Two things the reds did not surface but the evidence set does. Both matter for
revision round 2.

**(a) The trim is not purely subtractive — it ADDED a field row, and that addition
is the sentence most likely to have induced RED 1.** The original doc 23's §4.1
field table has **no `acknowledged` row at all**; the flag appears only in §7.3
prose. The trimmed §3.1 adds one: *"Present and `True` only after `acknowledge()`
marks (rather than clears) the latch mid-run — §6.3. **Absent otherwise.**"* The
statement is accurate about the original, but "Absent otherwise" is exactly the
clause a builder can read as "the flag describes the latch's *current* state, so a
brand-new edge makes it no longer apply" — i.e. a licence to pop it. A trimmer that
authors new content is running a second, unlogged experiment inside the first: the
manifest has no entry for this addition, because the manifest only logs removals.
**Recommendation: the manifest must log ADDITIONS and REWRITES, not just removals.**

**(b) The §7.2 correction overshot on `harvest_active_run`'s status.** The trimmer
worked from the pre-correction doc (475 lines, `31edf3b`), independently detected
that §7.2 described a `harvest_active_run` injection that does not exist, and
corrected it to the real peek/commit two-closure contract (manifest entries 11 and
23). That is the trim's best moment in this round — a confidently-wrong passage
caught and fixed before the repo's own correction (`e649b9e`) landed. But the
replacement sentence, "Remains a fully supported method independent of which caller
currently uses it," inverts what the corrected source now says (DEPRECATED, zero
production callers, do not add callers). **Minimal fix: restore the deprecation
status in trimmed §6.2** — one clause, no reinstated paragraphs.

---

## 8. Fitness of the trimmed candidate for revision round 2

**It proceeds.** On the evidence of this round the trim is in materially better
shape than the red count suggests: of four certified reds, exactly one is a
specification failure, and its provenance is **NEVER-PRESENT** — meaning **the trim
burned zero confirmed meaning.** Every removal the manifest justifies under the
cardinal rule (private symbol names) or as content owned by another file survived
contact with a blind builder: the reconstruction got the peek/commit split, the
identity-gated commit, the deep-copy guarantee, the re-arm guard, the
replaces-not-merges sentinel rule, the honored explicit `0`, the `limit=0`
edge case, the listener arity and the thread-safe save scheduling all correct from
prose alone, with the private names gone. That is a strong result for a 475→409-line
trim, and it is the result the campaign should record — not "four reds". The three
C verdicts are the calibration's first real precedent, and it should be stated
plainly: **a pin certified by mutation proves detection, not contract; a red pays
only when a consumer, an invariant, or a stated design changes behavior under the
reconstruction.** By that bar, `acknowledged`-across-a-re-latch, negative-grace
clamping, and message whitespace are all incidental original behavior with zero
consumers between them. Round 2's edits are therefore small and surgical: add the
one earned invariant (§4.3, label-value discipline), restore the deprecation
status of `harvest_active_run` (§6.2), and — the finding with the longest reach —
close the manifest's blind spot for *added* and *rewritten* prose, since the one
sentence the trimmer wrote himself (§3.1's `acknowledged` row) is also the sentence
that most plausibly steered the builder into the round's loudest non-defect.
