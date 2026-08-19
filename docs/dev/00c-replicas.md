# 00c — Replica Sets

> **Scope:** every rule this codebase implements in more than one place **on purpose**, so
> that changing one copy sends you to the others. A listing, not an argument — the
> reasoning lives at the anchor site.

---

## Why this exists rather than a helper

The obvious fix for duplicated logic is to unify it. That is often wrong here: roughly
half the divergence in this repo is deliberate — each copy feeds a different consumer, or
derives its inputs differently, and forcing agreement would force it in cases where the
copies *should* differ. The ladder is `constant > derived > helper > inline exception`,
and the usual target is a helper — but "usual" is not "always".

So a replica set is **coordination without unification**. It does not merge the copies. It
records that they exist, and makes the others findable from any one of them.

**The failure it exists to prevent is specific and has already happened.** A fix landed in
two of three copies of the `translation_key` rescue; **4381 tests passed**, because each
copy carries its own passing tests and a green suite proves only that every copy is
self-consistent with itself. The third was caught by renaming a live vacuum's entities to
German — not by any gate.

> **A green suite cannot see a missing copy.** That is the whole argument for this file.

---

## How a set is recorded

An `RN` notation anchor ([design/shipped/notation-anchors.md](design/shipped/notation-anchors.md))
is **declared once** at the set's natural primary — the shared artifact the copies revolve
around, or the copy whose comment carries the reasoning — and **referenced** from every
other member.

```
# anchor: RNxxxxxx  <what the rule is> — the replica set     ← exactly one
# REPLICA RNxxxxxx — <the twin lives at …>                   ← one per other copy
```

`python scripts/doc_anchor.py --show RNxxxxxx` lists every site. `--check` enforces that
the declaration is unique.

> ⚠ **The declaration must live in SOURCE, not here.** `doc_anchor.py` scans
> `custom_components/`, `scripts/`, `src/` and `harness/` for declarations; documents can
> only *reference*. This file is therefore an index over anchors that live in code — the
> same relationship [00b](00b-invariants.md) has with its invariants.

Mint with `python scripts/doc_anchor.py --mint RN`.

---

## The sets

### `RNF2RCXP` — `translation_key` rescue · **3 copies**

The rescue function is shared; **the decision to call it is written out three times**, and
that decision is what must agree.

| Copy | Feeds |
|---|---|
| `entity_resolve.resolve_declared_entities` | the adapter's declared `entities` map |
| `capabilities._rescue_maintenance_source` | maintenance sources |
| `capabilities.augment_candidates_from_device` | the roles `detect_capabilities` probes |

Not unified because each takes its wanted-key from a different place and feeds a different
consumer. **Declared at** `adapters/entity_resolve.py::rescue_by_translation_key`.

*History: `ef810519` fixed two; `35ce560f` fixed the third, ten hours later.*

### `RNZM4AYY` — most-specific-declaration ownership test · **3 copies**

One rule: **a candidate belongs to the declaration that explains the most of its name.**
The longest declared suffix claims a sibling exclusively, so `_cleaning_area` cannot
swallow `_total_cleaning_area`.

| Copy | Applies to | "Most" means |
|---|---|---|
| `entity_resolve.py` (inside `resolve_declared_entities`) | the declared entity map | longest suffix |
| `capabilities.py` (inside `augment_candidates_from_device`) | the probe candidate lists | longest suffix |
| `entity_resolve.py::tokens_owned_elsewhere` | the button token sets | proper superset |

The third copy is the one that shows why this is a replica set rather than a helper: it is
the identical rule over a different vocabulary — **set** containment where the others use
**string** containment — so no single function can serve all three, and the failure is not
that they duplicate but that they can silently disagree.

If the first two disagree, a role resolves one way through the declared map and another
through the probe, and the wrong one binds a **lifetime counter** where a per-run value
belongs. On live hardware that is 2.9 m² against 11,814 m², and nothing throws. The third
was missing entirely until issue #49: `dry_mop`'s tokens are a subset of `stop_dry_mop`'s
button id, so it matched two siblings, abstained, and a user lost a working control.

**Declared at** `adapters/entity_resolve.py` (the copy whose comment carries the reasoning).

### `RNWQ82XZ` — consult the save-refusal check before closing · **2 handlers**

The room editor's Save is bound on two different roots, and each must ask
`_roomEditorSaveWasRejected` before closing the modal.

| Copy | Root |
|---|---|
| `src/bindings/room-editor.js::_bindRoomEditorSave` | the main shadow root |
| `src/bindings/index.js::bindModalHostEvents` | the detached modal host |

**The check itself is already shared** — this set is the OBLIGATION TO CALL IT, the same
shape as `RNF2RCXP`, where the rescue is one function and the decision to invoke it is
written out three times. A handler that forgets to ask is indistinguishable from one that
asked and got a yes: the modal closes, and a backend refusal (`invalid_access_graph`)
reverts silently on the next snapshot.

**Already drifted once** before it was marked — the modal-host copy never gained
`setSkipRefreshOnClose`. That is what moved it from suspected to confirmed.

**Declared at** `src/bindings/room-editor.js::_roomEditorSaveWasRejected`.

### `RNXX8X11` — the room-fill palette SIZE · **2 copies** (of 3 sites)

How many room-fill colours exist. Three places care; only two can drift.

| Site | Kind |
|---|---|
| `src/cards/map-room-color.js::ROOM_FILL_N` | **derived** — `ROOM_FILL_PALETTE.length`, cannot be wrong |
| `src/theme-tokens/map.js` | **hand-enumerated** `--evcc-room-fill-N` token list — the copy |
| `src/state/theme.js` | derived: imports the palette and seeds in a loop — **NOT a member** |

The third row is the instructive one: it faces the same obligation and is immune to it,
because it imports rather than restates — which is what the second row could have done.
Currently 12 and 12.

**The failure is silent in both directions.** A 13th colour renders on the map with no
picker in the theme editor, so it can never be themed; a removed one leaves a swatch for a
token nothing reads. Neither errors, and nothing compares the counts.

**Declared at** `src/cards/map-room-color.js::ROOM_FILL_N` (the source of truth).

---

### `RNJ9YQF7` — the run-plan display helpers · **2 copies × 7 functions**

Every module-level helper the run-plan/dashboard display path uses, defined twice and
byte-identical in both.

| Site | Kind |
|---|---|
| `planning/run_plan.py` | **primary** — carries the reasoning and the audit header block |
| `core/manager.py` | the copy — same seven functions, verified identical 2026-08-18 |
| `maintenance/manager.py` | **third copy of `_display_label`**, missed on first recording |

**This entry was wrong when written, and the method caught it.** It was minted by hand
after diffing two files, and said "2 copies". `_relation_hunt.py shape` found
`_display_label` in a THIRD — `maintenance/manager.py` — 1.6 s of machine time against an
hour of careful reading. An under-recorded set is a wrong claim, not a partial one: someone
fixing both listed members would believe they were done.

**Disposition: SPLIT, and the split matters.** Four members (`_safe_int`, `_safe_float`,
`_iso_now`, `_display_label`) are leaf utilities — *dissolvable safely*, a shared util
module adds nothing any subsystem lacks. Three (`_profile_name_label`,
`_settings_profile_display`, `_room_surface_labels`) carry profile / water / carpet
vocabulary — hoisting those into a shared module puts **domain logic on a seam**, which is
manager-gravity by another route. Those are *dissolvable but shouldn't*.

`_display_label`, `_iso_now`, `_profile_name_label`, `_safe_float`, `_safe_int`,
`_settings_profile_display`, `_room_surface_labels`. Neither file imports the other.

**This set has already failed, and the failure is on record as a success.** `A5-PP-RP-8` —
the water-off suppression comparing the literal `"off"` instead of the brand's no-water
value — is live in **both** copies today, while the ledger recorded it closed by `RP-025`,
a packet whose commits never touched either file. So the set demonstrates the exact
`RNF2RCXP` shape *and* the mis-attribution shape at once.

**A green suite cannot see the second copy.** Both are exercised, each is self-consistent,
and no test compares them. The verification that found this was a whitespace-normalised
diff of the two files' shared function names — cheap, and worth repeating rather than
trusting.

**Unification candidate, deliberately not done here.** Seven identical functions is the
`helper` rung of `constant > derived > helper > inline exception`, not a deliberate
divergence — there is no consumer-specific reason for two copies. Recording the set is
coordination *now*; extracting a shared module is the real fix and is a code change, not
a tagging one.

**Declared at** `planning/run_plan.py::_profile_name_label` (immediately above the block).

---

### `RNGSVFKN` — `clean_times` is deliberately UNBOUNDED · **3 schemas**

| Site | Kind |
|---|---|
| `services/job_control.py` (start_zone_clean) | **primary** — carries the reasoning |
| `mapping/mapping_services.py` ×2 | the copies — same `Range(min=1)`, no max |

All three are `vol.All(vol.Coerce(int), vol.Range(min=1))`. The absent upper bound is the
*decision*, not an omission: a schema cannot see which vacuum the call targets, so the real
per-brand ceiling is enforced at dispatch — `dispatch/manager.py` clamps to
`zone_passes_max` on one branch and normalizes to 1 where the brand declares no zone-repeat
support on the other.

**The drift that matters is someone "fixing" one.** Adding a max to a single schema would
make that path refuse values the other two accept and dispatch would have clamped anyway —
a per-entry-point difference in what the same field means. If one gains a bound, all three
must, and the dispatch clamp becomes redundant rather than authoritative.

**Declared at** `services/job_control.py`'s zone-clean schema.

---

### `RNSERK29` — the dock EVENT-TYPE keys · **3 sites, one file**

`last_mop_wash` / `last_dry_start` / `last_dust_empty`, hand-written three times in
`dock/manager.py` (the trigger-vocabulary block and two count-mapping dicts).

These are **framework keys, not brand words** — core owning them is correct
([[feedback_eufy_is_not_the_default]]: core owns KEYS, never a brand's WORDS), so
"derive them from the adapter" would be the wrong fix and is worth stating because the
original finding (`A6-DIAG-8`) proposed exactly that. The state STRINGS these keys look up
*are* correctly adapter-derived via `_vocab_set`, with a documented no-brand-fallback.

**What is actually wrong is the copying**, and a module-level constant is the real fix —
the `constant` rung, the top of the ladder. This records the set until then.

**Declared at** `dock/manager.py`'s trigger-vocabulary block.

---

## Finding sets: four ways to ask, and three axes to judge

Derived 2026-08-18 and **tested before being written down** — five mixed candidates run
through it, three correctly rejected, one new set found, one rule refined by the run.

### The question is not "where is the duplication"

It is **how is this code related** — and there is no single way to ask. Each mode is blind
by construction, which is why no one of them is sufficient:

| ask | finds | blind to |
|---|---|---|
| **shape** — structural fingerprint | copies, the day they are made | cross-language; **absences**; derived-vs-enumerated |
| **history** — git co-change | cross-language and cross-artifact obligations | copies never yet co-edited — the **dormant** ones |
| **data** — who writes the same durable key | multi-writer state coupling | anything not routed through the store |
| **vocabulary** — shared literals | *not built* — recorded so the gap is visible | — |

`shape` and `history` are complementary **in risk**, not just coverage: a set `shape` finds
and `history` misses has never been co-edited, so nobody has learned it is coupled, and the
first edit is the one that breaks it silently. `_display_label` ×3 was exactly that.

It is **not combinatorial** — fingerprint-and-group is O(N). 1,261 functions in 1.6 s,
794,430 comparisons never performed. Loosening three steps moved cross-file candidates
16 → 58, so over-finding is affordable *at this repo's size*. That is a fact about 218
files, not about the method.

`.claude/notes/_relation_hunt.py` runs the first three.

### Membership: does changing one OBLIGE changing the others?

Already the register's one question. Two things discharge the obligation, and a discharged
obligation means **there is no set**:

1. **A mechanism already guarantees it.** The two built bundles co-change 192 times and are
   not a set — a build moves both. `guide-translations.js` says *"GENERATED — do not
   hand-edit"* and is not a set either. The palette's third site "imports rather than
   restates" and is explicitly not a member.
2. **The consumer genuinely absorbs the change.** A tolerant reader is not obliged. But
   note the trap: a consumer that tolerates **silently** is the worst case, not the safe
   one — `A6-PP-EST-LBL-1` `.get()`s a key its producer stopped emitting and yields `None`
   for every room, forever, with no test failing.

> **Discharge relocates the risk, it does not delete it.** A generator turns a replica
> obligation into a *staleness* obligation — and `check_generated_docs.py`'s own header is
> the record of that failing: *"Nothing was wrong with the generator. Nothing ran it."*
> Different hazard, different guard.

And obliged-together is not the same as bound-by-a-rule: `remove()` ×4 across the listeners
are byte-identical and all bound by [[INT79PB7]], which obliges each to satisfy it
**independently**. That is an `IN` relation, not an `RN` one.

### Severity: observational or mutation?

Unchanged — see below. Mutation sets produce divergent STATE and no test sees it.

### Disposition: load-bearing, or dissolvable?

**New, and it is the axis that says what to DO.** It also decides whether the entry is
permanent or is scaffolding awaiting an extraction.

| | |
|---|---|
| **load-bearing** | cannot be dissolved — a runtime boundary (Python ↔ card), an **absence** (you cannot extract "no upper bound"), or copies that must be able to differ |
| **dissolvable safely** | the destination is a leaf utility with no domain knowledge; extraction adds a dependency that travels with the subsystem |
| **dissolvable but shouldn't** | extraction is possible and would put **domain logic on a seam that must stay cuttable** — duplication is the correct terminal state |

That third row exists because the register's whole purpose is to make deliberate duplication
affordable. Without it duplication is a silent hazard, so the only safe response is to
unify — and unifying welds. An extraction that makes a subsystem depend on something it did
not depend on before is a **coupling decision**, not a cleanup; it belongs to
`design/core-minimality.md`, not to a tidy-up pass.

A set can split across dispositions. `RNJ9YQF7`'s seven members are four leaf utilities and
three functions carrying profile/water/carpet vocabulary — same set, opposite correct
actions.

### Classify after finding, never during

A disposition-blind census is the point. Classify while hunting and you skip candidates that
look dissolvable — but a dissolvable set is a live hazard until someone actually extracts
it, and *"we could unify that someday"* is precisely how `_display_label` sat in three files
unrecorded.

---

### `RNRVXK51` — the path-block ACTION vocabulary + its normalizer · **2 copies**

| Site | Kind |
|---|---|
| `core/manager.py` | **primary** — carries the reasoning |
| `jobs/active_job.py` | the copy — `frozenset` and `_normalize_path_block_action`, byte-identical |

Two levels duplicated at once: the closed vocabulary *and* the function that validates
against it. **Nothing discharges it** — no shared import, no generator, no constant in
`const.py`.

**MUTATION class.** This decides what the system *does* when a path is blocked. Add a policy
to one site and it is honoured there while the other silently maps it to `"event_only"` —
divergent behaviour, no test failing, because each copy is self-consistent.

**Disposition: dissolvable safely.** The natural destination is a shared constant; both
modules already sit inside core and neither gains a dependency it lacks. This is a leaf
vocabulary, not domain logic on a cuttable seam.

**Found by method, not by reading** — `_relation_hunt.py shape`, 2026-08-18, in the same
1.6 s pass that showed `RNJ9YQF7` was recorded one member short.

**Declared at** `core/manager.py`'s `_PATH_BLOCK_ACTIONS`.

---

### `RNY1AHMD` — the canonical clean-mode ALIAS TABLE · **2 copies, 2 languages**

| Site | Kind |
|---|---|
| `profiles/room_profiles.py::canonical_clean_mode` | **primary** |
| `src/clean-mode.js` | the copy — alias for alias |

**Load-bearing.** Backend and card are separate languages and cannot share code; the block
says so and names its own guard: *"pinned to each other by test instead: if you add an alias
to one, add it to the other."* Severity **mutation** — the fold decides which mode a room
dispatches as. `ISSUE #48` is what the halves disagreeing cost.

---

### `RN4T4MPV` — run-profile STEP normalization · **3 sites, 2 languages**

`profiles/manager.py::normalize_run_profile_steps` (**primary**), `src/state/steps-order.js`
`::sanitizeStepsForSave`, and `steps-order.test.mjs` which pins the card half.

The card sanitizes before save so the service receives already-clean data. Diverge and the
card ships what the backend then silently rewrites — the user sees their edit change shape
after saving, with nothing reporting a refusal.

---

### `RNC6DK2S` — the queue-steps INTERLEAVE · **2 copies, 2 languages**

`core/manager.py::get_queue_steps` (**primary**) and `src/state/steps-queue-order.js`.

"A break with `after_index` K sits after the K-th room." Rederived card-side so the editor
previews without a round trip. **Observational**, but the preview is what the user commits.

---

### `RN538E27` — the live-pose OVERRIDE precedence · **2 copies, 2 languages**

`mapping/map_source.py::apply_live_pose_override` (**primary**) and `src/state/map.js`.

The live pose OWNS `current_room` + `path`; the stale snapshot values must be **cleared
first**, in that order. The card repeats the sequence. Diverge and the *"stale in the
kitchen"* ghost returns — a live anchor in a catch-all cell leaving the previous room lit
and a lagged trail drawn. That ghost is the feature's whole reason for existing.

---

### `RN9N6NVB` — "is this run SEQUENCED, or a flat queue?" · **2 copies, 2 languages**

`profiles/manager.py::_enrich_saved_run_profile`'s `has_stops` gate (**primary**) and
`src/state/run-profiles.js::_deriveHasStops`.

**Both halves were wrong on the same day**: a rooms→zone profile reported itself as a flat
queue in each. Two independent answers to one question, and they agreed — on the wrong
answer. `step_types.py` carries the companion warning that the two vocabularies *inside* it
must NOT be merged; this set is the backend↔card pair, not those.

---

### `RN9Y5N84` — the profile DISPLAY LABEL composition · **2 copies, 2 languages**

`learning/manager.py::_settings_profile_label` (**primary**) and
`src/renderers/metrics.js::_localizedProfile`, which recomposes it in the user's language
and falls back to the English one.

**Diverge and the two disagree only for non-English users** — the half nobody testing in
English ever sees. Related: [`RNJ9YQF7`](00c-replicas.md) covers the *Python* duplication of
display logic, so this rule is expressed in **three** places across two languages.

---

### `RNHW3BKZ` — the shipped OPTION LISTS · **2 copies, 2 languages**

`adapters/eufy/adapter.py`'s option lists (**primary**) and `harness/fixtures/cards.js`,
which mirrors them **verbatim — values and order**.

A fixture agrees with the **caller**, not the callee. Let this drift and every harness shot
renders chips no real install shows, in an order it does not use — and the shots are what
the README and the docs site publish. Silent, and self-confirming.

---

### `RNCCB8J2` — the SEMANTIC DEFAULT palette · **2 copies, 2 languages**

`src/styles/foundation.js`'s `--evcc-sem-*` declarations (**primary**) and
`harness/cvd/report.mjs`, which hard-copies the four hexes as RGB triples to run the
colour-vision contrast floor against them.

**The failure is a green result about a palette that does not ship.** Change a default here
and the CVD report still PASSES — it is measuring the old colours. An accessibility claim
that cannot notice it is stale is worse than no claim.

---

### `RNH0W1RK` — the theme ENVELOPE SPLIT · **2 copies, 2 languages**

`themes/manager.py`'s tokens / colors / alpha split (**primary**) and
`harness/fixtures/theme-library.mjs`, which rebuilds it so the editor's swatch and opacity
rail render populated rather than empty. A drifted fixture shows an editor state no real
theme produces.

---

### `RNF6XB1P` — the LOCALE LOAD PATH · **2 copies**

`harness/shoot-locales.mjs` (**primary**) and `harness/tests/i18n-rtl.spec.mjs`, which
repeats the sequence — parse the shipped nested JSON, flatten against the English manifest —
because Playwright's loader treats a typeless `.js` as CJS and rejects the ESM modules.

**Load-bearing:** the spec cannot import the real path, so it must restate it. Change the
load order and the spec validates a model nothing uses.

---

### `RNNPSKT7` — the composer's 2dp CORNER ROUNDING · **2 copies**

`src/state/map.js::composeToSegments` (**primary**) and
`map-compose-and-viewport.test.mjs`'s own `r2()` helper.

A test that reimplements the arithmetic it is checking cannot fail when that arithmetic
changes — it asserts against its own stale copy and stays green. The narrowest possible
example of why a fixture agrees with the caller, not the callee.

---

## Observational vs MUTATION replicas

A replica set that decides **what to display or bind** is bad when it diverges: someone
sees a wrong answer. A replica set that decides **what to write** is worse: the copies
produce divergent STATE, permanently, and no test sees it because each copy is
self-consistent with its own.

Both sets recorded above are observational — they decide which entity a role binds to.
The dangerous kind is under Candidates below, and it has already cost real data.

## The one question the register has to answer

The families have useful names — twins, semi-twins, adopted family, cousins — but naming
is vocabulary for talking, not a field to fill in. The tooling needs one distinction with
consequences:

> **Does changing one member OBLIGE changing the others?**

Twins, semi-twins and adopted family all answer yes; cousins answer no. "Estranged twins"
is not a category — it is *obliged and currently violated*, which is a defect with an owner,
not a classification.

## Census first. Helpers later, and only if they earn it

When mapping a suspected family, agents describe **behaviour and relationships** and are
forbidden from proposing unification. Asking twenty agents to "find places that want a
helper" returns twenty helpers; the search designs the answer.

> ⚠ This was violated on 2026-08-16, in the run that produced `resolve_action_entity`. The
> mapping lane was told "propose the smallest seam, and do NOT propose a fourth copy" —
> which pre-loaded the conclusion. It happened to be right, and that is the problem: there
> was no way for that agent to tell me otherwise. The two lanes framed as open questions
> both returned findings that contradicted the brief, and one refuted the maintainer's
> hypothesis and mine together.

Roughly half the divergence in this repo is deliberate ([[feedback_centralize_question_not_vocabulary]]),
so a syntactic duplicate-finder gets this almost exactly backwards: two 90%-identical
functions are often cousins, while two that look nothing alike are twins because both
enforce "change X while preserving Y".

## The harvest — 71 unclassified candidates

`python scripts/replica_census.py` reads back the replica notices ALREADY WRITTEN in
source comments — "its twin", "the same predicate written twice", "these two handlers
already drifted apart once". **114 notices across 73 files, 71 of them carrying no `RN`
anchor at all**, 14 with a strong notice.

That is why populating this register was never really a bootstrap problem. The noticing
had already happened, dozens of times, by whoever was standing there when a fix landed in
one copy and not its twin — it was simply never indexed. The first census needed no new
insight, only a harvest.

The pile lives in **[00c-h — replica harvest](00c-h-replica-harvest.md)**, deliberately a
separate file: this one is the REGISTER (confirmed sets, each anchored in source), that
one is the working list it gets reduced from. A suspicion filed next to a ruling starts
looking like one.

> ⚠ **The tool finds RECORDED knowledge, not unrecorded structure.** A family nobody ever
> remarked on is invisible to it and stays that way until a bug convicts it — which is the
> argument for recording one AT THE FIX, where the evidence is strongest and the mental
> model is already built. The three candidates below all came from fixing bugs, not from
> reading code.

## Candidates — not yet recorded

Suspected replica sets. Each needs confirming as *deliberate* before it earns an anchor;
an accidental duplicate wants a helper, not an entry here.

- **`reserved_suffixes` at the capability probe** — both adapters pass `ALL_SUFFIXES`
  (`CN2X0DN6` Eufy, `CNXD5V8Q` Roborock). Two anchors already, and no link between them:
  the sibling problem surviving inside the scheme meant to fix it.
- **Brand vocabulary tables** — every adapter declares its own state sets. Almost certainly
  correct divergence rather than a replica set, but unverified.
- 🔴 **MUTATION — "did this run cover these rooms?"** Decided independently at
  `job_finalizer._detect_cancel_likely_run`, `job_finalizer._write_incomplete_run_log` and
  `_update_trouble_rooms_log`. They disagreed on 2026-08-16: a three-room run aborted from
  the vendor app archived as `completed` / `used_for_learning: True`, credited EVERY queued
  room with a fresh `last_cleaned_at`, and trained the learning store on a 30-second
  "clean". Divergent state, not a wrong display — and the strongest candidate here.
- **"does this item need attention?"** — `maintenance/manager.py` counts
  `{warning, replace_soon, replace_now}` into `attention_count`; the card's
  `_maintenanceItemNeedsAttention` adds a `remaining_percent <= 20` rule the backend does
  not have. Issue #51 showed both halves of the contradiction on one screen: "ATTENTION 0 /
  No upkeep items need attention" above a populated Needs Attention list.
- **"is the job_active signal real?"** — `is_job_active` (state is `on`) vs
  `completion_secondary_satisfied` (which tested only that the KEY was declared, until #51).
  Same question, two answers, and the weaker one gated completion.
- 🔴 **MUTATION — the consumed-id guard.** Slug-led carry with id fallback, written twice:
  `rooms/room_manager.py::build_managed_rooms` and `maps/map_manager.py`'s rebuild path.
  The source already says so — *"mirrors `build_managed_rooms`' own consumed_ids guard
  exactly (same bug, independently written in both writers, same fix)"*. Both are WRITERS of
  the persisted room store, and the subtle half is identical in each: a slug match consumes
  the room's OLD numeric id so a renumbered neighbour cannot inherit its settings through the
  id fallback. Drop that in one copy and the settings transplant returns silently on
  whichever write path skipped it. Obliged-to-change looks near-certain; unverified.
  Rule: [[INMKEHPQ]].
- 🔴 **MUTATION — `_enabled_room_ids_validator`.** `services/rooms.py:86` and
  `services/setup.py:109`, identical refusal messages today. Both gate the same destructive
  write — `null` and `[]` are rejected as loud schema errors rather than coerced to "select
  nothing", which would wipe every managed room. Two service surfaces, one rule, no shared
  symbol. Rule: [[INC63FDF]].
- **The sentinel vocabulary** — what counts as "no reading". Five sites, and the memberships
  already disagree: `adapters/eufy/lifecycle.py:67` carries `"null"`,
  `adapters/roborock/vocabulary.py:31` does not, `core/error_tracker.py:89` omits `"none"`
  (its own comment calls that a deliberate last-resort scope), `listeners/path_blockers.py`
  has its own set inline, and `rooms/room_discovery.py::_ACTIVE_MAP_SENTINELS` is a fifth.
  Probably NOT one set: the brand files are declaring brand vocabulary, which is correct
  divergence, while the core ones are answering "is this a reading?" and may be twins with
  each other. Needs splitting before it can be classified. Rule: [[INFJXSM4]].

Adding one is cheap. Leaving one here is also fine — a listed candidate is honest; an
anchored set nobody verified is not.
