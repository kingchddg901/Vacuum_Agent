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

Adding one is cheap. Leaving one here is also fine — a listed candidate is honest; an
anchored set nobody verified is not.
