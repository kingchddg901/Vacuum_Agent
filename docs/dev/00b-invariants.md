# 00b — Invariant Registry

> **Scope:** every system-wide rule that must remain true, in the shortest form that
> answers *"does my change violate something?"* — and nothing more. The explanation lives
> elsewhere and is linked.

---

## What this is for

During a review or an audit you do not want three pages of subsystem history to find out
whether a change crosses a line. You want **the rule first**, in a sentence. Only if the
change gets near that boundary do you follow the pointer and load the expensive context.

So this file and the design docs are **not competing documents**. They are two indexes into
the same truth at different levels of abstraction — the distinction [00 §8](00-documentation-standard.md)
draws between duplicate *truth* and duplicate *cognition*:

| | Answers | Cost to read |
|---|---|---|
| **This registry** | *What must remain true?* | Seconds |
| **The linked design / subsystem section** | *Why does this rule exist, what failure created it, what breaks without it?* | Minutes |
| **The enforcement site in source** | *Where is it actually held?* | Whatever it takes |

This is deliberate duplication and it is allowed, because the second representation buys
comprehension rather than repeating it. A registry entry that tries to teach the whole
system has failed at its one job.

---

## How an entry works

Each invariant owns a **notation anchor** (`IN` + six Crockford characters — see
[design/shipped/notation-anchors.md](design/shipped/notation-anchors.md)). The anchor is a
permanent identity that carries no meaning, so the rule's wording, its explanation, and its
enforcement sites can all move underneath it without the identity changing.

```
IN<token> — <the rule, in one sentence, with its consequence>
   Why:      <link to the design or subsystem section that explains it>
   Enforced: <the site(s) that hold it>
   Cite:     any code site that takes the same dependency
```

Mint with `python scripts/doc_anchor.py --mint IN`.

**An entry names its enforcement site — or states that it has none, and why.**

**And a named site is a claim, not evidence.** Measured 2026-08-19: **33 entries name an
enforcement site; 3 named a test that pins it; 1 recorded an ablation.** Twenty-nine asserted
*"enforced at X"* with nothing establishing that X enforces anything — and an unproven guard
reads identically to a proven one, which is the same blindness as an unaudited subsystem
producing zero findings.

The proof is **ablation**: remove the named enforcement, run the suite, and something must go
red. Nothing going red has two causes and both are findings — the guard does not work, or it
works and nothing tests it. `SETUP-REJ-2` was the second kind, *"true of the CODE and false of
the SYSTEM."*

Naming a test is not enough either. `[UV-4]` and `[UV-6]` were written for `INKV8ZQD`, named
exactly the right behaviour, passed, and were **decorative** — both stayed green under ablation
and had to be rewritten. So an entry records **what went red when what was removed**, with a
date, and *"ablation left the suite green"* is a legitimate and valuable thing to record rather
than omit.

**The first eight came back 8/8, and the prediction was wrong.** `INC63FDF`, `IN40W49E`,
`IN5BRA39`, `IN1FX8EH`, `INT62M7A`, `IN2QDNB3`, `INZKT2QF` and the `INKV8ZQD` control all bite,
and the tests that redden are named for the RULE — `test_catalog_declared_empty_is_carried`,
`test_accuracy_rmw_refuses_on_unreadable`, `test_delete_core_theme_does_not_survive_restart`.
So the enforcement was real and tested all along; **only the record was missing.**

That also retires a metric: only 43 of 348 findings are named in a test, and that number measures
a NAMING CONVENTION, not coverage. `INKV8ZQD` scores 0% on it while carrying six purpose-built
tests. Traceability and coverage are different things, and the first is not evidence about the
second in either direction.

This is a campaign, not a gate: identifying the guard line is a judgement per invariant, so it
cannot run in CI. What can eventually be a gate is far weaker — that every entry names a test
id which still exists. The second
half is not a concession. *"This cannot be enforced in code, and here is what stands in
for it"* is a stronger claim than silence, and it separates a rule that is unenforceable
in principle from one that simply is not enforced yet. The first is a `PN` and belongs
below; the second is a gap and belongs under *Not yet registered*. `--check` verifies every cited anchor
resolves; `--orphans` finds anchors nothing references.

> **An invariant states a rule AND its consequence** — "do this, or this happens"
> ([00 §1.2](00-documentation-standard.md)). If you cannot name what goes wrong, you have a
> convention, not an invariant, and it does not belong here.

---

## The registry

### `INR2F03P` — an entity id we intend to ACT on is resolved through the ladder, never derived and frozen

Anything we will press, set, or call a service on goes through
`adapters/entity_resolve.py::resolve_action_entity` (derived id → sibling suffix →
upstream `translation_key`), and the result is one of **resolved / disabled / missing**.

**Why it is not obvious.** The rescue ladder was built for the READ path, where the failure
is loud-ish: a sensor reads nothing and someone notices. On the ACT path the same failure is
silent in a way that has bitten three separate times, because **Home Assistant does not
raise when a service call names a missing entity** — it logs `log_missing()` and returns.
So the call succeeds, nothing happens, and every guard wrapped in `except` is dead code.

**The counterfactual.** *You localize a Home Assistant install. Which breaks first, reading
the vacuum or controlling it?* The naive answer is "both, equally". The real answer on
2026-08-16 was that every maintenance **sensor** resolved to its German id while all four
dock **buttons** and all four consumable **reset buttons** were dead, and the mop-intensity
push named an entity that had never existed — silently, for the whole life of the feature.

- **Why:** [21 — adapter system](21-adapter-system.md);
  [22 — adapter config reference](22-adapter-config-reference.md) for `service.target_role`.
- **Enforced:** `dock/manager.py::_get_dock_action_entity`,
  `maintenance/manager.py::_get_replacement_reset_entity`,
  `dispatch/manager.py::_run_global_pre_calls` (which also refuses a missing target
  rather than warning).
- **Corollaries.** A frozen `target_entity_id` is the *pre-rescue guess*: these blocks are
  built before `resolve_declared_entities` runs, and no user override reaches them.
  **Disabled is not missing** — `er.async_entries_for_config_entry` returns disabled
  entries, so binding one offers a control that silently does nothing.
- **Cite `INR2F03P`** from any new site that needs a concrete entity id in order to act.

> Related but distinct: [[RNF2RCXP]] is the translation_key *decision*, deliberately
> written three times for three read consumers. `resolve_action_entity` is a CALLER of
> that decision, not a fourth copy — which is the whole point of keeping the set at three.

### `INKR1TW7` — an operation that reads another integration's entities must not assume they exist during setup

Defer it to `async_at_started`, or tolerate late availability. Otherwise it reads an empty
registry and a stateless vacuum, **caches that answer, and never looks again** — so a
restart repeats the race rather than repairing it.

- **Why:** [02 — HA integration](02-ha-integration.md); the failure is recorded at the
  anchor site itself in `custom_components/eufy_vacuum/__init__.py#INKR1TW7`.
- **Enforced:** the post-start re-detection hook in `__init__.py`, which re-runs brand
  registration and `refresh_vacuum_capabilities` once HA has started, writing only on change.
- **Cite `INKR1TW7`** from any site taking the same dependency.

> The instructive part is that **nobody lacked the knowledge**.
> `_schedule_vocabulary_migration` in the same file states the constraint correctly — that
> adapters "are registered from vacuum entities owned by OTHER integrations" which "on a
> cold boot often have not" set up. That was true of adapter registration itself and was
> never applied to it. A local comment is not a system property. This registry is what
> makes it one; before it existed, the anchor was a comment with an ID.

### `INC63FDF` — a stored room map is replaced only by positive evidence, never by absence

An empty discovery, an absent or stale discovery cache, `enabled_room_ids: null` or `[]`,
or a discovery smaller than what is stored must not become the new room map. Absence is not
a selection.

**The consequence.** A map's rooms carry everything the user configured: profile, floor
type, clean mode and passes, access-graph edges, rules, rejected-room state. Replacing the
map with an empty one destroys all of it permanently, with **no error, no refusal and no
undo** — the only signal is that the rooms are gone. Restoring them means re-importing and
re-configuring every room by hand.

**Why it is not obvious.** Every one of these paths is a legitimate write. `save_managed_rooms`
replacing `map_bucket["rooms"]` is what it is *for*; the bug is the precondition, not the
operation. And the destructive input is the *quiet* one — a discovery that returned nothing
because the vacuum was unavailable looks identical to a discovery that correctly found nothing.
Eight findings across five files landed on this same shape (`RP-005`), including three at
facades in `core/manager.py` that hold no logic of their own.

**Absent is not empty.** `enabled_room_ids: null` and `[]` reached the schema as valid
selections and coerced to "select nothing", which is the exact opposite of omitting the key.
That is why the guard is a loud schema error rather than a silent normalisation.

- **Why:** the failure and the five original call sites are recorded at the anchor site
  itself, `rooms/room_crud.py::_refuse_destructive_replace`.
- **Enforced:** `rooms/room_crud.py::_refuse_destructive_replace`, called from
  `save_managed_rooms` and `rebuild_map`; the empty-discovery cache-keep in
  `discover_rooms`; the minimum-evidence guard on `reconcile_room`'s migrate arm;
  and `_enabled_room_ids_validator` in both `services/rooms.py` and `services/setup.py`.
- **Corollaries.** The guard compares against the **stored** map, not the discovery input —
  a shrunk-but-non-empty discovery is the minimum-evidence guard's business, deliberately
  looser, because discovery legitimately returns partial lists. A genuinely-empty *first*
  discovery still writes normally: absent is not failed. The manager facades need no guard
  of their own; the rule binds behind them, and adding a second copy there would be the
  divergence this entry exists to prevent.
- **PROVEN by ablation, 2026-08-19.** Remove `_refuse_destructive_replace`'s refusal and the suite goes red:
  `test_save_managed_rooms_refuses_empty_replacement`,
  `test_rebuild_map_refuses_empty_replacement`,
  `test_setup_save_rooms_refuses_empty_replacement`,
  `test_save_managed_rooms_service_refusal_leaves_rooms_untouched`.
- **Cite `INC63FDF`** from any new site that replaces a stored room map wholesale.

> `_enabled_room_ids_validator` is currently written **twice**, in `services/rooms.py` and
> `services/setup.py`. The two agree today. That is a replica set and probably wants an `RN`
> anchor — the shorter copy is how this class of rule fails.

### `INT79PB7` — anything registered or spawned during setup joins a teardown ledger, and the teardown is DERIVED from the registration

Three clauses, all load-bearing:

1. **Every spawn or registration joins a ledger owned by whoever owns the thing** — not a
   central one. `core/manager.py`'s `_background_tasks` / `_timers` are the reference
   pattern, but bundled subsystems ledger their own (`phase_runner`'s dock pollers,
   `external_run`'s grace timers) and expose `cancel_all()` / `cancel_timers()`.
2. **The undo is pushed BEFORE the step that can fail**, not after, and walked LIFO. A step
   that starts a loop reads the same mutable object it is populating, so it unwinds
   correctly however far it actually got before raising.
3. **The teardown list is derived from the registration list**, never hand-maintained
   beside it.

**The consequence.** A reloaded entry's *previous* generation keeps running: timers firing
against a store it no longer owns, services answering as phantoms, listeners reacting for a
manager that is gone. Worse at the edges — **Home Assistant never calls
`async_unload_entry` for an entry whose setup failed**, so a mid-setup raise leaves
everything registered with no path to remove it. That is why `async_shutdown` is registered
*before* `async_initialize` and is idempotent.

**Why clause 3 is not pedantry.** `async_unregister_learning_services` was a hand-written
duplicate of the register list, and the two had already drifted **5 services out of 21** —
`set_learning_processing`, `process_pending_runs`, `confirm_external_run`,
`get_external_pending_runs`, `discard_external_run` — each leaking on every single
unload/reload. Twenty findings across eight files landed on this family (`RP-003`,
`RP-039`); the parallel-list ones are the ones nobody could see by reading either list.

- **Why:** the failure is recorded at the anchor site itself,
  `core/manager.py::async_shutdown`, and at the unload orchestration in `__init__.py`.
- **Enforced:** `core/manager.py::async_shutdown` (drains `_background_tasks` / `_timers`,
  idempotent, gated by `_closed`); `entry.async_on_unload(manager.async_shutdown)` wired
  before `async_initialize`; the LIFO undo ledger in `__init__.py`;
  `listeners/lifecycle.py::_JOB_LIFECYCLE_TASKS`; `listeners/discovery.py`'s per-vacuum
  keying; `debug_capture.py`'s shared auto-stop cancel handle;
  `core/water_amendment.py`'s join onto the entry ledger; and
  `learning/services.py::async_unregister_learning_services`, derived from `SERVICES`.
- **Corollaries.** *A never-initialized manager has empty ledgers and cancels nothing* — so
  idempotence and empty-safety are part of the rule, not defensive extras. And `R2-BUG-6`
  at the same site is [[INC63FDF]] at store scope: teardown must **never flush a store it
  never read**, or an early-setup raise writes `{}` over every managed room, map, learned
  profile and theme.
- **Cite `INT79PB7`** from any new site that registers a service, subscribes a listener,
  spawns a task, or starts a timer.

### `INFJXSM4` — an unreadable signal is INDETERMINATE, not a value: it satisfies no predicate, affirming or negating

`unavailable`, `unknown`, `none`, `""` and a not-yet-added entity are all the same thing —
*we do not know*. None of them may be read as `False`, as `off`, as "no job running", or as
a rule's negating side. Where a boolean is unavoidable, the **caller** declares what
indeterminate means in its context; the helper does not choose silently.

**The consequence, in one sentence from the enforcement site:** *a dying door-sensor
battery cancelled a live run.* A blocker sensor dropping to `unavailable` satisfied every
negating operator, so a Zigbee or cloud hiccup evaluated as "the path is clear" — or as
"the path is blocked" — and paused a clean that was going fine.

**Why it is not obvious.** Nothing here is a missing check. Each site *had* a predicate and
the predicate ran; the defect is that an absent input was fed to it as though it were a
reading. And the failure is invisible in normal operation, because the sentinel only appears
when something else has already gone slightly wrong — a reconnect, a restart, a battery, an
entity that has not been added yet. So the bug reports as "the vacuum randomly stopped".

**Escalate, do not resolve.** `listeners/_common.py::is_job_active` takes
`unavailable_is_active: bool = False` as an explicit keyword rather than hard-coding the
collapse: detection wants one answer, finalization wants the other, and the helper has no
business picking. That signature *is* the invariant, expressed in a type.

- **Why:** recorded at the anchor site, `listeners/path_blockers.py` (RP-008 step 3), and
  in `listeners/_common.py`'s module docstring.
- **Enforced:** `listeners/path_blockers.py` — sentinel transitions are logged and skipped
  before rule evaluation, with a defence-in-depth re-check before the irreversible step;
  `listeners/_common.py::is_job_active` (caller-declared) and its dock-cycle sentinel guard;
  `mapping/mapping_services.py` ("indeterminate != match"); `jobs/job_monitor.py`'s
  busy-branch reachability; `listeners/pose_sampler.py::_is_parked`.
- **Corollary — DISABLED IS NOT MISSING.** [[INR2F03P]] draws the same distinction on the
  ACT path: `er.async_entries_for_config_entry` returns disabled entries, so binding one
  offers a control that silently does nothing. Absent, unavailable, never-created and
  disabled all read alike and are four different facts.
- **Cite `INFJXSM4`** from any site that reads an entity state into a boolean or a rule operand.

> **Replica set, unresolved.** The sentinel vocabulary is written at least five times and
> the memberships disagree: `adapters/eufy/lifecycle.py::_active_cleaning_target_cleared` carries `"null"`,
> `adapters/roborock/vocabulary.py::NOT_ERROR_SENTINELS` does not, `core/error_tracker.py::_NOT_ERROR` omits `"none"`
> (its own comment calls it a deliberate last-resort scope), and
> `rooms/room_discovery.py::_ACTIVE_MAP_SENTINELS` is a fifth. Some of that divergence is
> almost certainly per-brand and correct. It wants an `RN` anchor and a read — not a
> unification, which is how this class of rule gets broken.

### `INJ7VXE7` — a delete or rename sweeps every back-reference from ONE enumeration, and a reference it cannot sweep is refused, not silently broken

Two clauses. **Sweep from a list, not a call sequence**: `maps/map_manager.py::PER_MAP_STORES`
names every per-`(vacuum, map_id)` bucket once, and both `remove_map` and the id-remap walker
walk it. **Refuse what you cannot repoint**: `delete_room_profile` refuses while referrers
exist unless the caller passes `force=True` — the destructive path still exists, but as an
informed choice rather than a silent default.

**The consequence.** A hand-maintained sweep drifts the moment a new bucket is added, and
the drift is invisible: *"exactly how `remove_map` missed `run_profiles` / `queue` /
`onboarding` for however long they existed."* The user deletes a map precisely to discard
its stale room identities, re-imports, and their saved run profiles are still listed —
pointing at room ids that no longer mean what they did.

**Why a dangling reference is worse than a broken one.** These references do not fail loudly;
they *re-resolve*. A deleted `profile_name` falls back silently, so a room the user set to a
custom profile quietly reports `vacuum_quick` and behaves that way. And ids are worse still:
`_generate_saved_zone_id` guaranteed uniqueness only against **live** ids, so a deleted id
came back around and a stale queue step pointed at a real, different zone — **the wrong
physical area cleaned, with no warning.** That is the failure mode this rule exists to stop,
and none of its symptoms look like an error.

**Renaming is a delete plus a create, and inherits both clauses.** `rename_room_profile`
moves the store key, so every room still holding the old name is orphaned unless the rename
repoints them; `learning/history_store.py::get_paths` derives its archive directory from the
entity's `object_id`, so renaming the vacuum entity orphans months of learned timings,
accuracy stats and trouble-room history — the same rule, with a filesystem path as the
reference.

- **Why:** recorded at the anchor site, `maps/map_manager.py::PER_MAP_STORES`, and at
  `profiles/manager.py::_find_rooms_referencing_profile`.
- **Enforced:** `PER_MAP_STORES` (8 buckets, `delete` vs `reset` per bucket — `active_jobs`
  resets rather than pops, because callers index a known vacuum/map pair without a presence
  check); `profiles/manager.py::_find_rooms_referencing_profile`, consumed by both
  `delete_room_profile` (refuses) and `rename_room_profile` (repoints);
  `rooms/room_crud.py`'s consumption of the same registry as the id-remap walker;
  `mapping/mapping_services.py`'s variant-clear on delete.
- **Corollaries.** The registry names the **bucket, not the default** — a `reset` bucket's
  blank value needs the manager's default-state builder, so the caller supplies it. And id
  generators must be unique against **history**, not against what is currently live;
  uniqueness-against-live is the same bug wearing a different hat.
- **Cite `INJ7VXE7`** from any new per-map bucket, any delete or rename of a referenced entity,
  and any id generator.

### `IN40W49E` — core holds no brand's vocabulary: an undeclared key resolves EMPTY, never to somebody else's words

Core owns **keys**; a brand owns its **words**. Any fallback in core that yields a concrete
brand value — a suction name, a water level, a profile key, a dispatch engine — is the bug,
even when no brand name appears anywhere near it.

**The consequence, from the enforcement site:** *"What used to sit here was Eufy's catalog
wearing a framework badge: a brand that declared nothing inherited `"Max"` and `"Boost"`,
the card matched no option, and **an unedited room applied no suction at all**."* The robot
ran and cleaned nothing properly, and every layer reported success.

**Clause (i) — no guess.** Undeclared yields `""` or `{}`, never a plausible value.
`no_water_value` reads the brand's own carpet entry as its no-water word and returns `""`
when undeclared, *"there is no framework word for this."*

**Clause (ii) — presence, not truthiness.** `_catalog_key` tests `key in block`, so a brand
declaring `builtins: {}` — "this brand ships no framework built-ins" — is honoured. The old
`block.get(key) or default` treated any falsy declared value as absent and injected Eufy's,
making the brand's explicit *"we have none"* unrepresentable.

**Clause (iii) — absent and declared-empty are the same at the RESOLVER and different at the
VALIDATOR.** `resolve_profile_catalog` deliberately does not distinguish them: its job is
resolution, not judgement. `registry._validate_adapter` reports a missing `builtins` as an
incomplete declaration and the brand-agnostic contract suite makes it a hard failure. *"Were
absence quietly equivalent to `{}` everywhere, 'this brand has no profiles' and 'the porter
forgot' would be the same state."*

**Why it keeps coming back.** Thirty-three findings, and none of them contains the word
Eufy in the failing expression. The vocabulary leaks through a *default value* — a bare
literal, an `or` fallback, a hard-coded key list — so a brand-word audit passes clean while
the brand's behaviour is still wired in. Two shapes recur: a **sibling that was missed**
(`no_water_value` was read correctly by `resolve_room_profile_for_room` and hard-coded as
the literal `"Off"` at three sites in `apply_capability_gate`; Roborock's word is `"off"`,
so dispatch filtered the setting out and mop intensity was never applied on a mop-settable
model), and a **question asked in two places that must agree** (`declared_profile_fields`
diverged once and *"the repair undid itself — the migration dropped `clean_intensity` from
ten Roborock rooms and the next save put it back as `""`, one room at a time"*).

- **Why:** recorded at the anchor site, `profiles/room_profiles.py::resolve_profile_catalog`;
  brand identity as data is [21 §6.1](21-adapter-system.md).
- **Enforced:** `resolve_profile_catalog` (seven keys, no framework default);
  `_catalog_key` (presence test); `no_water_value` and `declared_profile_fields` (read the
  brand's own declaration); `registry._validate_adapter` (incomplete declaration is a
  reported defect); the brand-agnostic contract suite.
- **Corollaries.** *Absence of an OPTION LIST is not absence of an AXIS* — Roborock withholds
  `water_level_options` on models whose mop is not settable, which is a **capability**
  statement, not a vocabulary one; only absence from the brand's own profiles means the axis
  does not exist. And `default_profile` is the one key that still carries a framework value,
  legitimately: it names WHICH profile a new room starts on, never what is inside it.
- **Still open.** `EufyBrandFacts` names a brand in core. And the capability projection in
  `core/manager.py::get_dashboard_snapshot` still defaults five adapter-config reads to
  Eufy's answers (`passes_max` 2, `zone_max` 10, `supports_water_control` / `supports_edge_mopping`
  / `supports_room_profiles` True) — the same clause-(ii) bug outside this subsystem's repair.
- **PROVEN by ablation, 2026-08-19.** Remove `_catalog_key`'s presence-not-truthiness test and the suite goes red:
  `test_catalog_declared_empty_is_carried`.
- **Cite `IN40W49E`** from any core site that reads a brand-declared block, and from any new
  adapter-config key.

### `INMKEHPQ` — a room's identity is its SLUG, scoped to its map; the numeric id is a device handle that renumbers

Carry-over, matching and history are **slug-led with id fallback**. The device's numeric
`room_id` is not identity — it is reassigned on any re-segment — and it is never valid
across maps.

**The consequence.** Match by id and *"after a re-segment the robot runs the wrong room's
settings on the wrong physical room — **carpet/mop decisions inverted**."* The settings
transplant is silent: every layer reports success while the machine wet-mops a carpet.
Treat the id as globally unique and a multi-floor install bleeds across maps — importing one
floor writes the other floor's rooms into it, and the setup tab reports rooms as removed
from the vacuum because a discovery on the active map was scored against every map's rooms.

**The `consumed_ids` guard is the non-obvious half.** A slug unique among the stored rooms
is the primary match, and its **old numeric id is then consumed** — so a *different* room
that now occupies that freed id via a renumber cannot inherit the settings through the id
fallback. Without it the fallback quietly reintroduces the bug the slug match just fixed.

**Map scope is part of the identity, not a detail.** The rejection set is
`rejected_room_ids_for(map)`, because *"the vacuum-wide union would drop a real room on one
map because an unrelated id was rejected on another."* Anything keyed by bare `room_id`
across maps is this bug: drift history, discovery scoring, and the single-map discovery
fallback all had it.

**Clause — a guard is not enforced until a production caller passes it.** From the site,
verbatim: *"that last sentence was true of the CODE and false of the SYSTEM until
2026-08-05 — `save_managed_rooms`, the only production caller, never passed the argument, so
the skip had never run."* At subsystem scale the same shape: reconciliation computed its
reviews into a payload with **no trigger, no schedule and no UI**, so stored ids stayed
permanently diverged from the device's. A correct guard with no call site passes every
audit ever run against it.

- **Why:** recorded at the anchor site, `rooms/room_manager.py::build_managed_rooms`, and
  at `maps/map_manager.py`'s mirror of it; identity itself is
  `rooms/reconciliation.py::_room_slug` (slug, else slugified name).
- **Enforced:** slug-led carry with consumed-id guard in **both** writers —
  `rooms/room_manager.py::build_managed_rooms` and `maps/map_manager.py`'s rebuild path;
  `rejected_room_ids_for` (map-scoped) in `setup/drift.py`;
  `rooms/reconciliation.py::compute_reconciliation`.
- **Corollaries.** A room with **no** existing match is enabled on a *first* import and
  **disabled + unconfirmed** on incremental discovery — *"it never silently joins an
  already-active queue."* And `floor_types` gates `is_configured`: a room arriving via
  `enabled_room_ids` without a floor-type entry is not auto-confirmed, because that gate
  exists to make the user declare carpet before the first clean.
- **Cite `INMKEHPQ`** from any site that matches, carries, or keys anything by room.

> **Replica set, acknowledged in the source.** The consumed-id guard is written twice —
> *"mirrors `build_managed_rooms`' own consumed_ids guard exactly (same bug, independently
> written in both writers, same fix)."* Two writers agreeing today. That is an `RN`, and the
> second-longest-standing example of the shape this registry keeps finding.

### `INQ619A6` — "which rooms of this job are done" has exactly ONE answer, derived from structure and biased toward "missed"

A phased run has no single source that survives it. `completed_room_ids` holds the
**current phase only** — `advance_active_job_phase` empties it by design, because each
phase is a fresh atomic sub-job. Earlier phases are **derived from the phase index**, not
accumulated. And `room_timings` is the *only* witness for a single-room phase, which ends
by phase advance rather than by a rollover, so `record_completed_room` never fires for it.
`learning/utils.py::known_completed_room_ids` is the one place that reconciles all three.

**The consequence.** Ask the question in two places and the halves of a record disagree
about the same run: *"On alfred `job_2026-08-02T01-31-46` that put kitchen in the
incomplete-run log as completed and left the archived record's `queue.completed_room_ids`
empty"* — because the finalizer consumed all three sources and `build_completed_job_payload`
consumed only two. Downstream the damage is to learning itself: a group phase credits the
whole group's time and area to its first room (*"Kitchen — 34 min, 61 m²"* for Kitchen **and**
Hallway), phase 0's timing lands on the whole-run queue's first room even when that room is
not in phase 0, and *"a mop pass on the bathroom is learned as a kitchen vacuum."* At the
other end, a wrong "missed" set sends *"an unattended robot repeatedly [out] to re-clean a
room that is already clean, and each retry destroys"* the timing it should have taught.

**Derive, do not accumulate.** The stored `completed_room_ids_cumulative` was correct while
one merged record described a whole run; with a child per phase it became a second source of
truth *"that a child would union into itself, crediting itself with earlier phases' rooms."*
Reaching phase N is itself the evidence that phases 0..N-1 completed. Deriving is also
strictly more robust: *"the accumulator was written at the advance, so a failed write lost a
phase's rooms permanently, whereas **the phase index cannot disagree with itself**."*

**The bias is deliberate and asymmetric.** A timing counts only with **positive**
`cleaning_seconds`; synthesising completion is forbidden. *"Erring toward 'missed' costs a
redundant re-clean; erring toward 'completed' silently drops a room the user asked for."*
Those costs are not symmetric, so neither is the rule.

- **Why:** recorded in full at the anchor site,
  `learning/utils.py::known_completed_room_ids`.
- **Enforced:** that helper, consumed by `learning/job_finalizer.py` (twice),
  `learning/history_store.py` (archived record and completed payload), and
  `queue/queue_engine.py` — which notes its own former copy *"is gone:
  known_completed_room_ids now DERIVES the same facts from the phase [index]"*.
  `jobs/phase_runner.py` narrows a child's state to its own phase before it reaches here,
  so a child sees no earlier phases.
- **Corollary.** Break phases carry no `resolved_rooms` and contribute nothing — an empty
  `room_timing` on a charge / wait / zone phase is **not** a failed capture, and reading it
  as one degrades every stepped run's baselines.
- **Cite `INQ619A6`** from any site that asks what a job completed, or attributes time, area or
  battery to a room.

> This is the fifth family whose repair was *one enumeration / one question, many consumers*
> — after `SERVICES` ([[INT79PB7]]), `PER_MAP_STORES` ([[INJ7VXE7]]),
> `declared_profile_fields` ([[IN40W49E]]) and the consumed-id guard ([[INMKEHPQ]]). The
> source states the principle outright: *"the question is centralized, not the vocabulary."*

### `INYA5T84` — an adapter config is validated at runtime by the SAME walk the tests use, and the severity of a failure depends on its source

`adapters/config_schema.py`'s walker backs both `tests/adapters/test_adapter_contract.py`
and the live save path. A **stored** config — `source == "config"`, authored through the UI
or a service — **hard-raises** on any issue. A **code** config, the shipped brand adapters
registered at startup, degrades to a warning. A non-dict fails regardless of source.

**Why the asymmetry is deliberate.** User-authored input is untrusted and must be refused:
*"a broken stored config used to register cleanly and shadow the live adapter, with every
block it omitted silently resolving to that block's own absent-default (Eufy-shaped)
behaviour."* Shipped code is trusted and must stay available: *"a future code-adapter
regression must degrade to a warning, not take every install's startup down with it."*
Those are different risks, so they get different verdicts — availability for code, integrity
for input.

**The contract used to exist only in the test suite.** The schema was *"a documented contract
nothing at runtime ever actually enforced"* — `save_adapter_config` checked exactly two keys
by hand before registering a config over whatever adapter was live. The repair was not a
second validator but the **same walk** serving both: *"one implementation, not two that can
drift apart."* A contract enforced only in tests is enforced only against the configs the
tests happen to contain.

**Order matters at the save path.** Validate → register → persist. Persisting first writes a
config the registry will reject, leaving storage holding something that cannot load; and
`delete_adapter_config` must not unregister whatever is *currently* registered, because after
startup that is the code adapter, not the stored one it was asked to remove.

- **Why:** recorded at the anchor site, `adapters/config_schema.py`'s schema-walker header,
  and at `adapters/registry.py::register_adapter_config`'s docstring.
- **Enforced:** `adapters/config_schema.py::validate_adapter_config` (the shared walk);
  the source-based hard-raise in `adapters/registry.py`, at both the coordinator method and
  its sibling; `services/adapter_config.py::_handle_save_adapter_config`, which validates
  before persisting; `_warn_eufy_fallbacks` and `_warn_completion_gate_orphan` alongside.
- **Corollary — a declared value is still an input.** Adapter-declared `phase_timing`
  overrides are applied with no clamp, so `poll_seconds: 0` pins the event loop. Validating
  a config's *shape* is not validating its *values*.
- **Still open.** The walker enforces the schema, and the schema marks every card-facing
  capability key `"required": False` — `supports_water_control`, `supports_edge_mopping`,
  `supports_zone_clean`, `supports_mop_wash` — so an omitted capability passes validation and
  falls through to a default. `supports_base_station` is not in the schema at all. That is
  [[IN40W49E]] arriving through a hole this rule leaves open by design: the mechanism is
  correct, the declaration is incomplete.
- **Cite `INYA5T84`** from any new adapter-config key, and from any site that registers or
  persists a config.

### `IN5TNKMD` — an intent that must survive an await is re-read FROM THE STORE at the chokepoint, never carried across in a parameter

Cancel and pause are facts about the world that can change while a coroutine is suspended.
Check them once at the top of a function and the check is stale by the time it matters:
*"Four sequential awaits sit between the top-of-attempt check and the wire send with no
re-read in between — a cancel/pause landing anywhere in that window still reached the send."*
The re-read is of the **stored** job, immediately before the irreversible act, after the
last await. The parameter is this attempt's snapshot and is not evidence.

**The consequence.** *"User presses Cancel Run. The robot heads for the dock, then turns
around and cleans the next room."* *"The card shows Paused while the vacuum keeps cleaning —
the user's Pause visibly did nothing and no error is shown."* And the quiet half: a
cancelled or charge-timed-out run *"is recorded as a successful full completion and fed into
the learning set"*, so the wrong duration is taught for rooms that were never finished.

**Three parts, each with its own failure.**

*Re-read at the chokepoint.* The abort logs which of its three conditions fired, because
*"a missing record is a different bug from a live cancel."*

*Single-flight the intent.* A second cancel arriving inside the terminal-confirm window
used to run the whole body again and re-finalize with the exactly-once claim's **refusal**
dict, nulling `finalize_summary`. The latch is universal across atomic and phased jobs —
*"the strict-order guard below only ever covered phased jobs, so an atomic job had no latch
at all."*

*The intent owns finalization.* A cancel's own `return_to_base` docks the robot, and a dock
reads as phase completion — so a cancel that does not claim finalization is recorded as the
run finishing normally. Clearing `_phase_dispatch_pending` up front opens the very gate the
cancel is about to wait on.

**In-flight guards are part of the same rule.** `path_blockers` spawned unbounded concurrent
`_process` tasks, and the pause-timeout reap ticker runs every minute while each reap blocks
~35 s — so two reapable slots overlap by construction, and the auto-cancelled runs report as
completed.

- **Why:** recorded at the anchor site, `jobs/phase_runner.py`'s chokepoint comment, and at
  `jobs/active_job.py`'s single-flight latch.
- **Enforced:** the chokepoint re-read in `jobs/phase_runner.py::_dispatch_active_phase`;
  the `_cancel_in_flight` latch in `jobs/active_job.py` (set, checked, and cleared in exactly
  one place); `listeners/lifecycle.py` — *"a cancel in flight owns finalization for this
  [job]"*; `services/job_control.py`'s precondition on `start_zone_clean`, which previously
  *"bypassed every lifecycle gate, so it could stack a [second dispatch]"*.
- **Corollary — this class is invisible to the replay harness.** `tests/replay/harness.py`
  is deterministic by charter: *"sequences and gaps replay, await-interleavings do not; this
  is never race evidence."* Every failure in this family lives in an interleaving, so a green
  replay says nothing about it. It needs a targeted test or live hardware.
- **Cite `IN5TNKMD`** from any coroutine that reads an intent, awaits, and then acts on it.

### `IN76GE4W` — a declared limit is resolved ABOVE the branch and enforced on whichever branch runs

Which limits a brand declares and which code path handles its request are independent
facts. Resolve the declared bounds once, before the coordinate-space branch, and check them
in a shared function both branches call. Enforce limits by **what was declared**, never by
**which branch happened to run**.

**The consequence.** *"Previously area bounds only existed inside the `device_mm` branch and
side bounds only inside the else branch, so a bound declared on the 'wrong' branch for a
brand was **silently never checked**."* A brand declaring a side limit while taking the area
branch had no limit at all — the declaration was accepted, surfaced to the card, and
enforced nowhere. Same shape one field over: the zone pass-count clamp lived inside the
branch Eufy never takes, so `clean_times: 200` from an automation reached the device
unchallenged.

**The service layer had a comment where a check belonged.** `clean_times` was unbounded at
the service, *"defended by a sibling comment claiming dispatch enforces the per-brand
ceiling"* — and dispatch did not. This is the sharp edge of trusting comments: **prose about
its own line is evidence; prose about another module is a claim.** A comment asserting what
happens elsewhere drifts exactly like a document, because nobody editing *that* module ever
sees it.

**Refuse rather than approximate.** Where a zone must cross coordinate frames, the
conversion is validated against the live map's own projection and the dispatch is **refused**
if it cannot be — *"a wrong inverse cleans the wrong area."* Same asymmetry as
[[INQ619A6]]: the cost of refusing is a retry, the cost of guessing is the machine acting on
the wrong part of someone's home.

- **Why:** recorded at the anchor site, `dispatch/manager.py::_check_zone_bounds`, and at the
  hoisted bound-resolution block above the coordinate branch.
- **Enforced:** `_check_zone_bounds`, shared by both coordinate branches; bound resolution
  hoisted above that branch; the zone-count clamp against `zone_max`; the repeat cap read
  from `zone_passes_max` then `passes_max`, where an undeclared cap means **unsupported**
  on the branch that historically shipped the value verbatim.
- **Corollary.** A capability the card honours must also be consulted by the actuation path.
  `supports_zone_clean` was read by the card and never by dispatch, so a model declaring it
  `False` could still be sent a zone clean by an automation. A gate on the display surface is
  not a gate.
- **Cite `IN76GE4W`** from any adapter-declared limit, and from any branch that enforces one.

### `IN2QDNB3` — a read has THREE outcomes, and a destructive writer must refuse on UNREADABLE

`READ_OK` / `READ_ABSENT` / `READ_UNREADABLE`. **Absent** means no data has ever been
written, and seeding `{}` is correct. **Unreadable** means data exists and this read
failed — *"an RMW that proceeds will REPLACE the store with only its own delta."* Read-only
paths may treat both non-OK outcomes as "no data"; destructive read-modify-write callers
**must refuse**. A zero-byte file is a torn write, not a store that never existed.

**The consequence.** *"the conflation that let a corrupt 9-room `trouble_rooms` store be
rewritten as a 1-room store."* One `OSError` reading `accuracy_stats.json` overwrote the
whole accuracy history — 14 room keys and 60 graded samples, gone, from a single transient
failure. A network-share hiccup wiped the trouble-room record. A failed segmenter run
replaced good cached segmentation with an `available: False` envelope and every room polygon
vanished from the map.

**Failure caching is the same bug held longer.** A failed read cached as `None` for the life
of the process means *"one unlucky read at startup makes the card report no learned data for
the whole HA session"* — and a cache-hit gate that tests truthiness serves a cached
**failure** envelope forever, so analysis stays broken with a stale reason after the cause
is fixed. An error is not a result and must not be cached as one.

**Blank-then-replay is a write of absence.** `rebuild_learning_stats` blanked
`accuracy_stats` before replaying it; any failure after the blank leaves the store empty,
turning a user-initiated *repair* into the destruction it was meant to undo. Build the
replacement, then swap.

- **Why:** recorded at the anchor site, `learning/history_store.py::read_json_outcome`.
- **Enforced:** `read_json_outcome`'s tri-state and its stated caller contract; the
  refuse-on-unreadable checks in the trouble-rooms and accuracy writers;
  `mapping/mapping_services.py`'s analyze cache, which must not serve a failure envelope as
  a hit.
- **This is the fourth face of one principle.** Absence has *causes*, and the cause decides
  whether you may act on it: [[INR2F03P]] separates resolved / disabled / missing for entity
  ids, [[INFJXSM4]] makes an unreadable entity state indeterminate rather than false,
  [[INC63FDF]] refuses to replace a stored room map with an empty one, and this entry
  separates absent from unreadable on disk. [[INT79PB7]]'s `R2-BUG-6` corollary is the same
  rule at whole-store scope: never flush a store you never read.
- **PROVEN by ablation, 2026-08-19.** Remove `read_json_outcome`'s UNREADABLE arm (all seven return sites collapsed to ABSENT) and the suite goes red:
  `test_read_json_outcome_tristate`,
  `test_trouble_rooms_rmw_refuses_on_unreadable`,
  `test_accuracy_rmw_refuses_on_unreadable`,
  `test_accuracy_unreadable_is_backed_off_not_permanent`.
- **Cite `IN2QDNB3`** from any read that precedes a write, and from any cache that can hold a
  failure.

### `IN4CW5Y9` — entity ownership is answered by FORWARD RECONSTRUCTION, never by prefix-scanning the registry

To find what a vacuum/map owns, re-**build** the exact `unique_id` set from stored facts and
take the complement. A live entity can then only be selected as stale if this run failed to
build it at all. Never ask the registry for ids starting with a string.

**The consequence, proven not theorised.** *"a prefix scan in setup/delete was PROVEN to
registry-delete every entity of a SIBLING vacuum whose entity_id was the scanned prefix plus
a suffix — `vacuum.alfred` deleting map "2" swept `vacuum.alfred_2`'s entities."* Home
Assistant's own default naming produces exactly that collision, so any multi-vacuum install
is one room edit away from permanently deleting another robot's entities. **Five** prefix
scans existed.

**A string prefix is not ownership.** It is a coincidence of naming, and naming is the
user's. The builder and the matcher are kept side by side so the answer comes from the same
facts that created the ids.

**The guard's own near-miss is the instructive part.** Where a prefix scan does survive, a
second test checks the remainder — and it was wrong in a way review could not see: *"Note
the missing leading underscore: the prefix has already consumed it, so `vacuum.alfred`
matching `vacuum_alfred_active_job_active_job_5` leaves the remainder `active_job_5`.
Testing for `_active_job_` there matches nothing and the guard **silently does not fire** —
caught by OAJ-3, not by review."* A guard against a prefix bug, containing a prefix bug, and
only an adversarial test found it. The functions are kept pure and side-effect free
precisely so those cases are testable without a registry.

- **Why:** recorded at the anchor site, `entity_helpers.py`'s forward-reconstruction builder
  and its orphan-sweep sibling.
- **Enforced:** `entity_helpers.py` (build the id set; the sweep takes the complement of a
  forward-built set); `sensor/__init__.py` — *"FORWARD RECONSTRUCTION, never a prefix scan
  of the registry"*, staleness by **absence from desired**; `switch.py` and `number.py` —
  stale means *owned by this vacuum/map*, read from live attributes.
- **Related.** [[RNZM4AYY]] is the same mistake in the other direction: string containment
  read as ownership, where `_cleaning_area` could swallow `_total_cleaning_area`. There the
  fix is longest-declared-suffix; here it is don't match on strings at all.
- **Cite `IN4CW5Y9`** from any code that decides which entities belong to a vacuum or a map.

### `INZKT2QF` — an exclusion from recovery is a LEASE, not a grant, and one item's failure must not end the sweep

Any flag that tells a reaper "leave this alone" carries a liveness signal and an age. When
the thing holding the flag dies, the exclusion lifts on its own. And every sweep isolates
its items, because a reaper that dies on one job stops protecting all of them.

**The consequence.** *"`_phase_dispatch_pending` … that state is **UN-REAPABLE BY DESIGN**"* —
so one transient service error mid-run left the job permanently `started`, and the guard that
was meant to protect the dispatch also blinded the only thing that could recover it. The
sweep half is worse: *"one raising finalize **permanently disables BOTH reapers for EVERY
managed vacuum**."* A single bad job, and nothing on the box can recover anything again until
a restart.

**Lift the exclusion, not the flag.** The repair does not clear `_phase_dispatch_pending`:
*"the phase may still start late; **only the reaper's exclusion should lift, not the
completion gate's**."* A shared flag with two consumers needs a per-consumer liveness
signal, not a clear — clearing it would answer the reaper by lying to the completion gate.
The stamp is guarded by phase index, so a watchdog that wakes after the job moved on writes
nothing.

**Unreachable-by-recovery is its own failure class.** A run that never observed an active
lifecycle cannot be judged by any ended-looking check — *"they all assume a real run
happened"* — so it needs a separate route out, on dispatch age alone. Without one, the
phantom persists and the **next** run's completion signals finalize it instead.

- **Why:** recorded at the anchor site, `jobs/job_monitor.py::_phase_pending_still_live`, and
  at `jobs/phase_runner.py::_mark_phase_watchdog_dead`.
- **Enforced:** `_phase_pending_still_live` (a dead watchdog's phase is reapable via
  `_phase_watchdog_dead` / `_phase_dispatch_pending_since`); `NEVER_STARTED_SECONDS` for runs
  that never began; per-slot `try`/`except` in the pause-timeout reaper — *"one slot's
  exception must not kill"* the tick — and the same guard around
  `async_finalize_stranded_job`; the mutable box rather than a closure variable so a reap
  in flight is visible to the next tick.
- **Corollaries.** An **errored** robot is reapable, which deliberately reverses the usual
  "wait for it to settle" reasoning. And the liveness margin has a module default that exists
  *only* to catch a caller who omits it — *"the real caller always computes and passes a
  margin derived from the resolved phase timing"* — so the constant is a backstop, not a
  policy.
- **Related.** [[IN5TNKMD]] keeps an *intent* alive across awaits; this keeps *recovery*
  alive across failures. Both fail the same way — silently, with the machine still moving.
- **PROVEN by ablation, 2026-08-19.** Remove the lease's liveness check in `_phase_pending_still_live` and the suite goes red:
  `test_stranded_when_pending_since_past_margin`.
- **Cite `INZKT2QF`** from any flag a reaper consults, and from any loop that sweeps items.

### `INGZFYXX` — resolve and authorize BEFORE mutating; a failed operation must leave the world as it found it

Work out whether an operation can succeed against current state **without touching
anything**, and only then mutate. The wipe runs once at least one element is confirmed to
apply — never as step one, on the assumption that the rest will work.

**The consequence.** *"it used to run unconditionally before this resolution, so a fully-failed
apply still destroyed the user's prior selection with no rollback."* Press a saved run profile
whose rooms were renumbered by a re-segment and every room on the map is deselected and
persisted, with the call reporting success. The automatic retry path is worse because nobody
is watching: *"a failed automatic retry silently and permanently reduces the user's cleaning
selection from 11 rooms to 2."*

**The physical half has no undo at all.** A global pre-call — fan or mop intensity pushed to
a device that carries them globally — is applied before the dispatch it exists to support.
When the dispatch then fails, *"a failed start silently reconfigures the robot's global mop
intensity and leaves it there"*, and the next clean the user runs from the vendor app
inherits it. A settings change that outlives the job it was made for. Ordering the pre-calls
after id resolution closed the known trigger; it did **not** make the sequence transactional,
and the site says so.

- **Why:** recorded at the anchor site, `profiles/manager.py`'s resolve-before-wipe block
  (RP-031/RF-05a), and at `core/manager.py::start_selected_rooms`'s pre-call ordering
  comment ([[IN5TNKMD]] covers the intent half of that same sequence).
- **Enforced:** `profiles/manager.py` — the profile's rooms are resolved against the current
  map first, and a resolution that matches nothing refuses rather than wipes; pre-calls
  ordered after live id resolution in `core/manager.py`.
- **Still open, verified by reading rather than inferred.** `services/job_control.py` places
  `await manager.async_save()` **after** the `except` that re-raises, with no `finally` and
  no rollback anywhere in the module. A raise arriving after the wire dispatch therefore
  leaves the robot cleaning while the active-job record exists only in memory — the store and
  the machine disagree, and the user sees a red error over a working clean. The same
  mutate-then-save ordering is reported in the three maintenance write services.
- **Cite `INGZFYXX`** from any handler that mutates persisted state or device settings before
  the operation it supports has succeeded.

> Closure data cannot adjudicate this family: no `RF-05` finding maps to a landed packet, yet
> the resolve-first repair is present in the code. Read the site, not the matrix.

### `INNJ6SGC` — every state has a reachable exit, placed at the TERMINAL CHOKEPOINT all paths reach — and an edge-triggered signal needs a final flush

If entering a state is possible from several paths, leaving it must be handled where those
paths converge. A `finally` is not a chokepoint: **it only covers the paths that entered its
`try`.**

**The consequence.** *"`end_job` has only ONE caller (successful finalize) — every
cancel/abort/strand path leaves the tracker permanently"* holding the job. And the latches
are worse than the misses: *"`resume_sampling` is **provably unreachable** — `_sampling_paused`
is a one-way latch, so all room attribution stops permanently"* the moment a run docks for an
unplanned recharge. Mid-job recharge *"NEVER ends: the recharge-end branch is unreachable
dead code."* None of these throw. The system simply stops doing something, forever, and the
only symptom is data that quietly stops arriving.

**Put the release where everything converges.** *"this is the terminal chokepoint every path
reaches — cancel, strand, success — so release the tracker's hold HERE, not only from the
lifecycle finalize path's own `finally` block (which a cancel/strand never goes through)."*

**An edge-triggered accumulator never fires for its last element.** `room_completed` fires on
a room **switch**, so *"the room the job actually finished IN would otherwise never get one"* —
every completed run silently missing dwell data for its final room. Any signal derived from
transitions needs an explicit terminal flush, and the flush must respect the same threshold
the edge did.

- **Why:** recorded at the anchor site, `jobs/active_job.py::mark_active_job_finalized`, and
  at `mapping/tracker.py::end_job`.
- **Enforced:** the tracker release in `mark_active_job_finalized` (reached by cancel, strand
  and success alike); `end_job`'s flush of the currently-held room; the mid-job recharge
  close-out in `jobs/active_job.py` and its lifecycle counterpart; per-vacuum cadence state
  and in-flight guards in `listeners/pose_sampler.py`, so one vacuum raising cannot cost the
  others their stream.
- **Corollary.** A HOLD state must stop accruing as well as stop firing. The hold path kept
  accumulating dwell and movement for a room the robot had already left, inflating the
  duration the learning store was then taught.
- **Related.** [[INZKT2QF]] is the same shape for *recovery* — a lease rather than a latch —
  and [[IN5TNKMD]] uses a chokepoint for *intent*. Three families, one mechanism.
- **Cite `INNJ6SGC`** from any state with more than one entry path, and any accumulator driven
  by transitions.

### `INPQ6ZE7` — a held value is DISPLAY-only: strip the fields that would be attributed, rather than flagging them

When a source drops out and the last-known-good result is re-served, the frozen frame may
still be **drawn** — but every field that describes motion is removed, not marked. A cache
keyed on a stable input must likewise not carry the volatile output: cache the geometry,
re-apply the pose on every read.

**The consequence.** *"a docked/idle robot kept attributing to wherever it was last seen, at
whatever cadence the attribution consumer polls, for the whole TTL window — **the stale flag
existed but nothing downstream read it**."* Every dock produced a stream of confident,
wrong room attributions that fed learning. And on the cache path, *"a cache hit re-serves
whatever position the robot was at when the file was last parsed"* — indefinitely, because
the store's write cadence is coarser than the in-memory pose it is meant to track.

**Removing the data beats adding a flag.** `stale` / `stale_since` / `stale_reason` were
written correctly and read by nothing. The repair does not make consumers check them; it
nulls `current_room`, `robot_anchor` and `path` on the held result, so there is no wrong
answer available to be trusted. A flag depends on every present and future consumer
remembering; an absent field cannot be misread.

**A coordinate frame is part of a value.** A live-pose lookup projected a **memory-frame**
robot pixel through **storage-frame** geometry — two frames that diverge exactly during a
re-segmentation, which is when the answer matters most. A position without its frame is not
a position, and the mismatch produces a plausible room id rather than an error.

- **Why:** recorded at the anchor site, `mapping/map_source_coordinator.py`'s hold path
  (clause 1) and its geometry cache (clause 3).
- **Enforced:** the hold path strips the moving fields and stamps `held_static`;
  `_apply_inmem_pose_to_result` re-runs on every cache hit against the map data cached
  alongside, rather than re-reading the file.
- **Corollary — display tolerance and attribution strictness are different bars.** The card
  may keep a frozen map with a stale badge; the learning path may not be given a frozen room.
  [[IN76GE4W]] is the mirror: a gate that exists only on the display surface is not a gate.
  One value, two consumers, two standards.
- **Cite `INPQ6ZE7`** from any last-known-good hold, any TTL cache, and any pose or geometry
  that crosses frames.

### `IN5ATBW9` — a write that changes a source must reach EVERY artifact derived from it, and "rebuild" must not name a partial operation

Rebuild the derived files, rebuild the incremental accumulators that live outside them,
invalidate the in-memory cache, and repopulate it. All four, or the operation is lying about
what it did.

**The consequence.** *"`rebuild_all` only reaches the four derived files … the incremental
accumulators outside it (learned zones, battery drain aggregates) kept whatever the excluded
job had already contributed … exclude/restore silently didn't, **despite both claiming
'stats rebuilt'**."* The user's one tool for removing a known-bad run was partial, reported
success, and left the bad data influencing estimates. Same shape one layer up: accuracy is
written to disk and the in-memory cache is never invalidated, so the caller gets a success
payload containing the new mean while the card keeps showing the old one.

**Invalidation must beat work already in flight.** Invalidate-then-preload is a no-op when a
preload is already running, so a load that started before the change repopulates the cache
with pre-change data — the invalidation happened and achieved nothing.

**An accumulator with no rebuilder can only ever be wrong.** `trouble_rooms` is a raw-counter
store with no rebuild path, no clear service, and a denominator that only advances when a
room is queued — so a room wrongly badged *"chronically missed, 67%"* stays badged until
someone deletes the file by hand. If a value must be accumulated rather than derived
([[INQ619A6]]), the rebuilder is part of the feature, not a follow-up.

- **Why:** recorded at the anchor site, `learning/services.py`'s exclude/restore handlers.
- **Enforced:** `async_rebuild_learning_accumulators` + `_invalidate_learning_stats_cache` +
  `async_preload_learning_stats`, called together after both `exclude_learning_job` and
  `restore_learning_job`.
- **Still open.** `trouble_rooms.json` has no rebuilder or clear service, and both it and
  `incomplete_run.json`'s `missed_room_ids` are keyed by **raw room_id** — so they survive a
  re-segment and reattach to whichever room now holds that number ([[INMKEHPQ]]). Acting on
  a stale missed-set destroys the user's current selection.
- **Cite `IN5ATBW9`** from any write that feeds a derived artifact, and from any accumulator.

### `IN5BRA39` — a refusal is not a success: success is proven by carrying its payload, and ONE predicate answers it

`finalize_result_succeeded` is the single source of truth for *"did this finalize actually
run"*. It is a **positive** test — the result must carry a `completed_job` dict — not a
check that nothing went wrong.

**The consequence.** The exactly-once claim refuses with `{"finalized": False, "reason": …}`,
and **a dict is truthy**, so `if result:` treats a refusal as a completed finalize. That fired
a duplicate `eufy_vacuum_job_finished` — a **documented public automation trigger** — and the
stranded-job path went further, firing it *"with a FABRICATED status 'completed'"*. Users
received two completion events for one run, one carrying real data and one carrying an
invention, and any automation keyed on that trigger ran twice.

**Why a positive test.** Absence of an error is not evidence of work. A refusal, a timeout, a
partially-built result and a genuine success are all "not an exception"; only one of them has
the payload. Testing for what success *produces* collapses the other three into the same
correct answer, and it cannot be defeated by a new refusal shape.

**One predicate, not three.** It replaced *"three open-coded siblings that each re-derived the
same check"* — two finalize outcome extractions and the accuracy guard. A refusal must not
fire completion events, mark a slot finalized, or feed accuracy and zone learning, and those
are three different consumers who must not each decide for themselves.

- **Why:** recorded at the anchor site, `learning/manager.py::finalize_result_succeeded`.
- **Enforced:** that predicate, consumed by `listeners/lifecycle.py`,
  `learning/services.py`, and `jobs/active_job.py`'s stranded-finalize path — which also
  suppresses a repeat WARN for a job id already reported as refused.
- **Related — truthiness is the recurring trap.** [[IN40W49E]] clause (ii) tests **presence,
  not truthiness**, so a brand's declared-empty block survives; [[IN2QDNB3]] rejects a
  cache-hit gate that serves a cached **failure envelope** as valid. Same mistake, three
  subsystems: a container that exists is not an answer that means yes.
- **PROVEN by ablation, 2026-08-19.** Remove the positive `completed_job` test in `finalize_result_succeeded` and the suite goes red:
  `test_stranded_finalize_in_flight_leaves_slot_reapable`,
  `test_stranded_already_finalized_marks_the_slot`,
  `test_finalize_learning_job_empty_state`,
  `test_finalize_service_refusal_raises_service_validation_error`,
  `test_lifecycle_refusal_fires_no_event`.
- **Cite `IN5BRA39`** from any consumer of a finalize result, and from any operation whose
  refusal is a value rather than an exception.

### `INJSETB0` — a service contract is ONE thing declared in three places, and the write must accept what the read emits

The voluptuous schema, the `services.yaml` descriptor and the documentation describe the same
contract. They are three copies, and they drift. Two obligations follow: **round-trip
closure** — whatever a read service emits is valid input to the corresponding write — and
**enforce constraints the schema language cannot express**, at the boundary, rather than
letting them fall through.

**The consequence.** *"`services.yaml` advertises required fields that the voluptuous schemas
reject — three services fail outright"*; `map_id` is documented optional on eight mapping
services whose schemas require it, and required on three the docs call optional. An
automation written from the documentation does not run. Sixteen services documented as public
API have no descriptor at all, and ten `setup_*` services have neither descriptor nor
translation — so they exist, work, and are undiscoverable.

**A validation gap does not vanish; it relocates.** Without the post-check, a `wait` break
missing its `wait_minutes` *"validated cleanly, then silently normalized to nothing downstream
and came back as a refusal the caller had to notice in the response."* That is worse than a
schema error, because it is not an error — it is a success-shaped reply containing a refusal,
and callers do not read those.

**Round-trip closure is a contract, not a convenience.** `get_queue_steps` returned each break
as `{after_index, step: {type, …}}` while `set_queue_breaks` accepted only the flat
`{after_index, break_type, …}`, so the documented *read → edit one field → write* cycle was
impossible without the caller reshaping the payload by hand. A read whose output the write
rejects means the pair has no usable API, however correct each half is alone.

- **Why:** recorded at the anchor site, `services/queue.py::_require_break_params` and
  `_flatten_break_entry`.
- **Enforced:** `_require_break_params` (a post-check after per-key coercion, expressing the
  `break_type` → parameter dependency); `_flatten_break_entry` (the write accepts the read's
  nested shape as well as the flat one).
- **Still open.** The three declarations are not reconciled by anything mechanical, and the
  drift above is the evidence. This is a replica set at contract level — schema,
  `services.yaml`, docs — and it belongs in [[00c-replicas]] as a candidate rather than being
  fixed by unifying, since each copy serves a different consumer (validation, the HA UI, the
  reader).
- **Cite `INJSETB0`** from any service schema, and from any read/write pair meant to round-trip.

### `INJW5J2A` — the event loop does no filesystem work and no per-pixel work; unavoidable setup is memoized once per process

Anything on the loop that touches disk, or walks a raster, or rewrites a whole store, blocks
**every** integration on the box — not just this one. Warm paths must be warm all the way
down, and setup that genuinely has to run gets memoized, keyed the same way the thing it
guards is keyed.

**The consequence.** *"`ensure_dirs` is reached from **13 path-getter call sites**"* — so the
caches that exist precisely to keep an estimate off disk still paid four `mkdir` syscalls on
every hit, three times per `estimate()` call, on every dashboard snapshot. On a network-mounted
config that is *"sustained blocking filesystem I/O on the HA event loop whenever a card is
open."* The extremes are worse: a per-pixel `O(width × height)` pure-Python loop means
*"downloading diagnostics stalls the entire HA event loop"*, and a theme draft saving the whole
integration dict per keystroke means *"typing a 25-character font stack issues **25 full-store
writes** back to back."*

**Key the memo the way the guarded thing is keyed.** The `ensure_dirs` memo is keyed on the
vacuum **slug**, not the raw entity id, *"so 'vacuum.alfred' and any differently-cased caller
collapse onto the same entry — `get_paths` already does the same normalization."* A memo whose
key is finer than its subject's key misses silently and reads as a memo that works.

**Compose once.** The same rule without disk: composing an expensive payload twice inside one
response can also let the two copies **disagree**, so the fix is a single compose handed to
both consumers, not a faster one — see [[IN5ATBW9]] for the sibling case where the copies
diverged.

**The inverse is also a defect.** An executor hop kept alive *"on the strength of a comment
describing disk I/O that"* no longer happens is a cost paid for a cause that is gone, and the
comment is what keeps it there. Cheap to remove, invisible until someone checks.

- **Why:** recorded at the anchor site, `learning/history_store.py::ensure_dirs` and its
  memo in `__init__`.
- **Enforced:** the per-`(process, vacuum-slug)` memo on `ensure_dirs`.
- **Still open.** The raster scans (`zone_membership`'s pre-bbox per-cell normalize,
  `raster_room_bboxes` in the diagnostics path) and the per-keystroke full-store theme write
  are recorded but not repaired here.
- **Cite `INJW5J2A`** from any loop-bound path that resolves storage, and any raster walk.

### `IN96V4SA` — an edge requires a KNOWN prior state: arriving at a value is not a transition

Three refusals, in order, any one of which means *not an edge*: no current reading; no
**known** prior reading — missing entirely (HA restart, genuinely first sighting) or
`unavailable`/`unknown`; or the prior normalizes to the same value. Only then is it an edge,
and only if the new value is in the **caller-supplied** trigger vocabulary.

**The consequence.** Count arrivals instead of transitions and the counters only ever go up:
*"maintenance data drifts upward silently and permanently — dry-start / dust-empty / mop-wash
counts inflate"*, and *"every HA restart during a dry or wash cycle adds a"* phantom cycle.
Nothing errors, nothing looks wrong, and the numbers the user relies on to schedule real
maintenance are quietly inflated by their own reboots.

**Not knowing the prior is not the same as the prior being different.** *"We don't know what
the device was actually doing before, so a fresh sighting after a restart or a reconnect must
not be recorded as a brand-new dock cycle."* This is [[INFJXSM4]] applied to the **previous**
value rather than the current one — an indeterminate prior cannot support any claim about a
transition, in either direction.

**One definition, and the vocabulary is a parameter.** The edge test is shared *"so there is
exactly one definition of 'is this actually a dock event' instead of two independently-drifting
ones"* — the inline mop-wash detector had already diverged from the dedicated dock-events
listener, and had hard-coded Eufy's wash words while doing so. `trigger_vocabulary` arrives as
an argument, which is [[IN40W49E]] expressed in a signature rather than a rule.

- **Why:** recorded at the anchor site, `listeners/_common.py`'s shared edge test.
- **Enforced:** that predicate, delegated to by `listeners/dock_events.py::_handle_dock_event`
  and `listeners/lifecycle.py`'s mop-wash detection.
- **Still open.** `dock_events.register()` does not read the adapter's `dock_events.enabled`
  flag, so a brand that declares `enabled: False` to opt out gets the opposite of what it
  asked for — a declaration accepted and inverted ([[INYA5T84]]).
- **Cite `IN96V4SA`** from any counter driven by a state change, and any transition detector.

### `INTCWVFM` — an observability path must not perturb what it observes, nor overwrite its own evidence

Diagnostics, dumps, snapshots and capability reads are **inert**. They perform no detection,
no write, no event, and they cannot destroy an earlier capture. A witness that changes the
scene is not a witness.

**The consequence.** *"`get_vacuum_capabilities(refresh=False)` still calls
`refresh_vacuum_capabilities` (full detection + a **WRITE** to `self.data`) in three cases
despite `refresh=False`: no stored snapshot yet, a stored snapshot missing `detected_model`,
or an adapter model-family self-heal mismatch — **exactly the scenario where a user pulls
diagnostics WHILE something is wrong**."* The act of collecting evidence rewrote the state
being investigated, and only in the broken cases — so the healthy path looked fine and the
diagnosis was destroyed on contact. The dashboard snapshot is excluded from diagnostics for
the same reason: *"computing it can advance room timing and fire room-transition events during
a live clean."*

**A parameter that lies is worse than a missing one.** `refresh=False` reads as a promise.
The fix is a separate accessor with no other behaviour — `get_vacuum_capabilities_snapshot`,
which *"reads whatever is in `self.data["capabilities"]` as-is (`{}` if nothing has been
detected yet) and never calls `refresh_vacuum_capabilities`"* — rather than another flag on
the impure one.

**Evidence must survive collection.** Dump filenames were second-precision, so *"two dumps
within the same second silently overwrote each other"* — the observer deleting its own record,
most likely while chasing something fast. A millisecond component plus a monotonic
`itertools.count()` (a single GIL-atomic op, so it holds across concurrent executor threads)
makes every name unique.

- **Why:** recorded at the anchor site, `core/manager.py::get_vacuum_capabilities_snapshot`,
  and at `debug_capture.py::_write_dump`.
- **Enforced:** `get_vacuum_capabilities_snapshot` (read-only accessor, used by
  `diagnostics.py` and by `maintenance/manager.py`'s upkeep collector, which threads
  capabilities through so the per-component loop cannot re-open the non-inert path);
  the dump-name sequence in `debug_capture.py`; every collector's failure surfacing in the
  diagnostics warnings list rather than aborting the dump.
- **This is the runtime half of a structural property.** The observability estate imports
  nothing from the integration — `harness.py` has zero domain references, `harvest.py` is
  stdlib and sqlite3 only, `debug_capture.py` is a drop-in with none — and `harvest.py` says
  why: *"here ON PURPOSE. If the harvester imported the production helper, a bug in"* it would
  be invisible. Structural independence stops the witness agreeing with the accused; this
  rule stops it moving the furniture.
- **Cite `INTCWVFM`** from any diagnostic collector, capability read, or capture writer.

---

### `INT62M7A` — a mutation reports what it DID: refuse with a reason, or succeed carrying what was applied

A service that changes stored state has two honest endings. It **refuses** — returning a
failure flag and a machine-readable `reason`, which the registration layer turns into a raised
`ServiceValidationError` — or it **succeeds**, and the response carries what it actually
applied. Callers gate on the **flag** (`ok` / `saved` / `performed` / `applied`), never on a
reason literal: a literal matches one failure and falls through every other.

**The consequence.** A write that did not happen, reported as one, is invisible. There is no
exception, no log the user reads, and the card goes on rendering the value it optimistically
sent. Three paths shipped exactly that, and each is now a refusal:

- **A disabled upstream button.** `dock/manager.py` resolved a dock button that existed in the
  entity registry but was disabled, returned `performed: True` and `"Dock action sent."`, and
  the dock did nothing. The control was offered as Ready, the tap returned success, and *"the
  only trace is an HA core log line the user is not looking at."*
- **A throwaway dict.** In custom mode with no active layout, `_resolve_active_scope` returned
  fresh literals bound to nothing. `set_companion_anchor` and `set_segment_room_link` mutated a
  dict the garbage collector took on the next line and reported `saved: True`, so a dragged
  mascot held its position for the session and *"silently snaps back on the next page load —
  repeatedly, with no error and no way for the user to tell the write failed."*
- **Unreadable image dimensions.** An upload on a Pillow-less install persisted `width` and
  `height` as `None` and still reported `saved: True`, putting every downstream consumer into
  the state that makes segment authoring report a missing backdrop.

**A refusal leaves nothing behind.** The upload is the shape to copy: when the dimensions
cannot be read it deletes the PNG it just wrote, because *"a saved PNG whose variant record
never lands is a leak."* A refusal that abandons half its work on disk is a second bug wearing
the first one's clothes.

**Partial success is the residue, and it is still open.** The rule above splits cleanly into
refuse-or-succeed because those three writes either happened or did not. A write that *partly*
happened satisfies both halves and reports the success one: `themes/manager.py::set_theme_tags`
drops every tag past the 16th and every tag longer than 32 characters, then returns `ok: True`
with no record of what it discarded — so `_raise_if_failed` has nothing to fire on, and the
same silent truncation runs on the import path. The honest ending is a third one: **succeed,
and say what was not applied.** The limits themselves are undefended — `_MAX_THEME_TAGS = 16`
is a preference with no stated consequence and no test that can go red, which is why it
survived the audit ([[feedback_claim_must_be_able_to_bite]], and the same shape as the retired
floor-type table).

- **Why:** recorded at each anchor site — `dock/manager.py::build_action_status`,
  `mapping/mapping_services.py::_resolve_active_scope` (whose docstring states the
  write-must-check-`resolved` contract) and its `_write_and_measure` sibling.
- **Enforced:** `themes/services.py::_raise_if_failed`, which gates on the flag across seven
  handlers and raises with a translated key rather than a bare string; and the two
  `if not scope["resolved"]: return {"saved": False, …}` guards, which are identical copies on
  purpose — [[feedback_partial_guard_blind_spot]] is how the shorter copy becomes the bug.
- **Related.** [[IN5BRA39]] is the same rule read from the other end: *success carries its
  payload*, so a truthy refusal dict is not a completion. [[INJSETB0]] governs the declaration
  of the response this invariant governs the contents of.
- **PROVEN by ablation, 2026-08-19.** Remove `_raise_if_failed`'s flag gate and the suite goes red:
  `test_overwrite_theme_service_raises_for_unknown`,
  `test_rename_theme_service_raises_for_unknown`,
  `test_delete_theme_service_raises_for_unknown`,
  `test_set_active_theme_service_raises_for_unknown`,
  `test_export_theme_service_raises_for_unknown`,
  `test_import_theme_service_raises_for_missing_name`.
- **Cite `INT62M7A`** from any service handler that can decline, and from any helper that
  returns a store a caller will write into.

### `IN11T0FS` — settings resolve in ONE order, and the only thing above it is a safety clamp that omits rather than invents

Every settings axis resolves the same way: **room-explicit, then profile, then absent.**
`resolve_room_profile_for_room` writes that ladder once per axis and nothing re-derives it.
**Absent means absent** — it is omitted from the wire, never sent as `""` or `None`. Exactly
one rule sits above the ladder, the carpet clamp, and it reads the *brand's own* word for
"no water" rather than assigning a literal.

**The consequence.** An axis with a second, differently-ordered resolution path does not read
as a precedence bug; it reads as a value bug, one surface at a time. A hidden arm applied
per-surface water defaults *over* an already-resolved profile value, so a mop room on granite
did not merely lack a default — it had a perfectly good profile value **replaced with `""`**
and shipped to the device. `_write_room_field` passes values through unchanged, so the empty
string reached the wire verbatim. Two floor types were selectable in the picker and present in
**neither** brand's table, and the only symptom was a bad wire value (`DQ-PAY-2`, HIGH).

**Absent is not "off".** The queue engine gates on the value — `if supports_water and is_mop
and water_level:` — matching its `path_type` sibling one line below. An undeclared axis means
*no opinion*, and the device keeps its own setting. Without that gate, removing a default
table does not restore user control; it ships `""` to every room that used to inherit one.

**The clamp's two halves rest on different arguments, and the difference is load-bearing.**
Carpet forces water off because wetting a carpet is physical harm that changing a setting
afterwards does not undo — that one overrides an explicit user choice and should. Carpet also
boosts the fan, which is *convergence*, not safety: most vacuums do it in firmware, so the
framework is meeting an expectation rather than imposing one. Both currently override an
explicit choice. Do not extend the clamp to a third axis by treating those as one argument —
per-surface *water* defaults were retired for precisely this reason
(`docs/dev/history/floor-type-cleaning-defaults.md`), and the surviving carpet rows are the
residue that earned their place, not the start of a table.

**The residue is profile IDENTITY, and it is still open.** The ladder governs an axis's
*value*; two live defects govern which profile the value came from, and both report success:

- `profiles/manager.py::save_user_room_profile` defaults an omitted `profile_name` to the
  literal `"user_1"`, while its sibling `save_room_profile_from_room` forty lines away mints
  `_generate_room_profile_id()`. Two saves without a name collide: the second silently replaces
  the first, both return `saved: True`, and every room stored as `user_1` resolves through the
  replacement (`A5-FACADE-4`).
- `_settings_profile_display` receives the store **key**, never the label the user typed, so a
  saved profile renders as `User 20260730T142530` (`A6-PP-EST-DSP-1`). The record carries
  `label`; the caller does not pass it. Its `"custom"` half **is** fixed — `custom` and `user_1`
  are now explicitly in the is-custom set instead of being re-labelled as the brand default.

- **Why:** recorded at the anchor site, `profiles/room_profiles.py::resolve_room_profile_for_room`,
  whose block comment states what the retired hard-floor arm did and the three reasons not to
  restore it from memory.
- **Enforced:** that resolution block; `queue/queue_engine.py`'s value gate, pinned by
  `[DE-W1]` (an explicitly-empty level is omitted), `[DE-W2]` (carpet still sends the brand's
  no-water word — it exists to fail if the gate ever swallows the guarantee) and `[DE-W3]` (an
  explicit level still ships); and `[RP-10]`, which fails if a hard-floor row is re-added.
- **Related.** [[IN40W49E]] owns the other half: the clamp's word is the brand's, read from its
  carpet entry, because core holds no brand's vocabulary. [[INT62M7A]] is why the identity
  residue is invisible — both defects report success.
- **Cite `IN11T0FS`** from any code that resolves a settings axis, and from anything that adds
  a rule keyed on `floor_type`.

### `INSJM6KC` — a gate judges only the DELTA, and the state it judges carries a VERDICT

A structural gate refuses **what this edit breaks that was not already broken.** It captures a
baseline from the same validator *before* the mutation, compares, and refuses only the new
issues. And the state it reads exposes an explicit verdict, so "nothing is configured" and
"everything is blocked" are distinguishable rather than inferred.

**The consequence of an absolute gate.** One stored violation anywhere becomes a lock on
everything. A Roborock re-segment plus migrate could leave two rooms granting access to the
same room — reconciliation rewrites grants through an id remap and de-dupes only *within* one
room's list, never re-checking the cross-room constraint — and from then on **changing a room's
fan speed, colour, or enabled flag failed** with *"The requested access links would make the
graph invalid"*, naming a feature the user had not touched. The message pointed at the wrong
subsystem, so the real cause was unfindable. The same absoluteness greyed out **every**
unselected target in **every** room's editor with the contentless *"Not selectable due to graph
legality."*

**The consequence of a state with no verdict.** A blank graph (every run allowed) and a partial
one (every run refused) produced **byte-identical** payloads from the documented diagnostic —
both carrying exactly `[{'type': 'missing_dock_room'}]`, empty `dock_room_ids`, empty
`missing_rooms`. The one service a user calls to ask *"are my runs blocked?"* could not answer
it. Worse, **following its single instruction moved the user from the first state into the
second**: marking a dock room on a fresh map flips blank to partial and silently disables all
cleaning. A report whose remediation is a trap is worse than no report.

**Three corollaries, each learned the hard way:**

- **Name the rooms.** `access_graph_block_rooms` exists because the refusal named no room on a
  map that may have eleven, and told the user to "complete it or clear all access settings".
  Issues that name no room yield an empty list rather than a placeholder — the caller has a
  sentence for that.
- **Publish the cost of the advice.** `unlinked_room_ids` is the set that becomes
  `missing_dependency` the moment a dock room is set. Naming it up front is what stops the
  remediation being a trap.
- **A graph-scoped issue reaches every room's view.** An issue carrying no `room_ids` is a
  property of the whole graph; the old membership test dropped it from every room, so a user
  opening a room editor on an unusable map saw a clean panel. The `is not None` filter there is
  load-bearing, not tidiness: a `[None]` list is truthy and would read as "scoped to some room".

- **Why:** recorded at the anchor site, `rooms/access_graph.py::access_graph_block_code`, which
  also names why this is the de-dup ladder's **helper** rung — the QUESTION gets one owner
  rather than two copies that can drift ([[feedback_centralize_question_not_vocabulary]]).
- **Enforced:** that helper and `access_graph_block_rooms`; `get_access_graph_health`'s
  `state` / `runs_blocked` / `block_code` (additive, so existing consumers are unaffected); the
  `baseline_keys` delta in `get_room_access_editor`; and the pre-mutation baseline in
  `core/manager.py`'s room-update gate, which fires **only when `grants_access_to` is not None**
  so an unrelated field is never this rule's business.
- **Related.** [[INT62M7A]] — the refusal now carries the formatted new issues rather than one
  sentence. [[IN5BRA39]] — a verdict is a positive answer, not the absence of an error.
- **Cite `INSJM6KC`** from any validator that gates an edit, and from any diagnostic whose
  payload is the same in a healthy and a broken state.

### `INNPA4ZV` — a user-facing message is a CODE plus PARAMS; the sentence belongs to the locale

Backend code emits `{code, params}`. The **card** owns the sentence, and the locale owns
everything about how it reads — including its punctuation. Params are the interpolated values
as strings, **never pre-joined**: a list stays a list so the locale picks its own separator.

**The consequence.** The room-access modal composed ten English sentences in Python and the
card rendered `issue.message` verbatim. That made it the one place in an 18-locale product
where the user is told *what is wrong* and the one place that bypassed i18n — including for
AR and HE, where English prose was injected into an RTL layout.

**The English string does not get deleted.** `message` stays exactly as it was, because it is
the documented response-service surface that automations and non-card consumers read. It
becomes the **last fallback** in the resolution chain, reached only when there is no translate
function. Adding the seam beside the prose, rather than replacing it, is what made this
shippable without breaking a published contract.

**Pre-joining is the subtle half.** `", "` is an English convention. Emitting a joined string
bakes it into every locale, so the packs carry their own `list_separator` and the card assembles
the list. A translated sentence with an untranslatable comma is still not translated.

- **Why:** recorded at the anchor site, `rooms/access_graph.py::_format_access_graph_issue`, and
  at `src/state/access-issue-label.js`, whose header explains the SCOPED lookup — the same code
  can mean different things depending on who raised it, so card-raised issues resolve
  `room_access.issue.card.*` first and fall back to the shared key only where the meaning is
  genuinely the same.
- **Enforced:** `scripts/check-i18n.mjs` (`npm run check:i18n`) — every used key defined in all
  18 packs, plus an English-identical ratchet; and `src/i18n/card4-untranslated-strings.test.mjs`.
  The packs are **nested**; `src/i18n/en.js` is flat and dotted. Grepping a dotted key against a
  pack finds nothing and looks exactly like a missing translation — that false alarm was raised
  and withdrawn on 2026-08-18, and the gate is what caught it.
- **Related.** [[feedback_no_string_without_i18n]] — every user-facing string routes through
  i18n *at creation*. [[INT62M7A]] — a refusal must carry a reason, and this is the rule for
  what that reason is made of.
- **Cite `INNPA4ZV`** from any code that builds a sentence a human will read.

### `IN1FX8EH` — a seeder must respect deletion: absence is not a gap to fill, and a TOMBSTONE is what tells them apart

Anything that re-seeds bundled content on every construction must distinguish **"the user
never had this"** from **"the user removed this"**. An existence check cannot: both look like
absence. The removal is recorded as a tombstone the seeder consults, and shipped content is
immutable in place — copy-on-write to edit, refuse-or-tombstone to delete.

**The consequence.** `ensure_preloaded_theme_library` re-added every spec id not currently in
the library. A user curating their themes — deleting the bundled ones they did not want, past
a confirm dialog implying it stuck — found **all of them back in the picker after the next
restart**, silently and with no error. The delete survived exactly until the next reload. If
the deleted theme had been the global default, `default_theme_id` was silently re-pointed too.

**Why the confirm dialog makes it worse.** The user was asked to confirm, so they believe the
system recorded a decision. It recorded a *state*, and the seeder's job is to restore state.
Nothing was lost that the user could see until a restart, which is the longest possible gap
between the action and its reversal — long enough that the two are not obviously connected.

**Re-pointing the default is correct, and is not the defect.** Once the tombstone holds the
deletion, a stored `default_theme_id` naming a theme that is genuinely gone must resolve
somewhere; falling back to `theme_follow_ha` is right. The defect was re-pointing as a
*consequence of resurrection*, not the fallback itself.

- **Why:** recorded at the anchor site, `themes/preloaded.py::ensure_preloaded_theme_library`,
  and at `themes/manager.py::delete_theme`, which records the tombstone and explains that
  without it the delete *"survives exactly until the next restart."*
- **Enforced:** `deleted_core_ids` — written by `delete_theme` only for `source == "core"`
  entries, read by the seeder before it re-creates any spec. The seeder's migration arm
  backfills `source` on pre-existing bundled entries so provenance is answerable, and
  deliberately leaves a user theme's provenance alone rather than guessing it.
- **Related.** [[INC63FDF]] — a stored map is replaced only by positive evidence, never by
  absence. Same mistake in a different subsystem: absence is not an instruction.
- **PROVEN by ablation, 2026-08-19.** Remove the `deleted_core_ids` tombstone check in the seeder and the suite goes red:
  `test_delete_core_theme_does_not_survive_restart`.
- **Cite `IN1FX8EH`** from any code that seeds, re-seeds, or restores bundled content.

### `INKV8ZQD` — durable per-vacuum state is minted only for a MANAGED vacuum; a write refuses, a read answers empty

`cv.entity_id` validates the **shape** `domain.object_id`. It does not check that the entity
exists, and it certainly does not check that this integration manages it. Every per-vacuum
store keyed off an unchecked id therefore mints a durable bucket for whatever string an
automation happened to pass — and then reports success.

**The consequence, and why it never surfaced.** Minting is invisible: the call succeeds, the
store grows, and nothing is wrong until someone asks a question the phantom answers. Worse, it
is **irreversible as evidence** — once a bucket exists, *"never configured"* and *"configured
and empty"* are byte-identical forever after, which is the same loss [[INC63FDF]] and
[[IN2QDNB3]] each describe in their own subsystem. Four services did this: `get_recent_errors`
(a **read**, via a `get_record` whose own docstring says *"Public read accessor (creates if
absent)"*), `_get_vacuum_theme`, the queue mutators, and the snapshot services.

**The authority could not gate anything until it stopped writing.** `data["vacuums"]` is what
`get_managed_vacuums()` reads to decide what is managed — and `get_pause_timeout_settings`, a
**registered read service** (`services.yaml:755`), did
`data.setdefault("vacuums", {}).setdefault(vacuum_entity_id, {})`. One read call with a typo'd
id minted a managed vacuum, so a guard built on that dict would have been defeated by the very
call it was meant to catch. Fixing that read is a **prerequisite**, not a cleanup: *an authority
a read can write into cannot gate anything.*

That line also carried the comment **"A READ MUST NOT WRITE"**, describing the half of itself
that had been fixed — an earlier pass removed the persisted fallback and left both
`setdefault`s. It is the cleanest example in the tree of
[[feedback_partial_guard_blind_spot]]: the guard that exists reads as complete, and the prose
above it is what makes the survivor invisible.

**Writes refuse; reads answer empty with a `reason`.** A write to a vacuum we do not manage is
always a mistake, and [[INT62M7A]] gives the refusal somewhere to surface. A read is how a card
discovers state, and making discovery throw trades a blank panel for a red toast. The split is
**inspectable per handler** — does it mutate — rather than a judgement per service, which is
what keeps it from becoming the kind of split that causes this class of bug. The family record
draws the same line: display-preference services may keep documented fallbacks, actuating and
durable writers may not.

- **Why:** recorded at the anchor site, `services/_common.py::is_managed_vacuum` /
  `require_managed_vacuum`, and at `core/manager.py::get_pause_timeout_settings`, which states
  why that read is the site the whole family turns on.
- **Enforced:** `require_managed_vacuum` on the mutating handlers;
  `unmanaged_vacuum_read_result` on the reading ones, which carries `reason` so a consumer can
  tell *"nothing here"* from *"not ours"*.
- **PROVEN, by ablation — 2026-08-18.** Each guard was removed and the suite re-run; each
  reddens its own test and nothing else:
  | remove | goes red |
  |---|---|
  | `require_managed_vacuum` in `services/queue.py` | `[UV-1]`, `[UV-2]` |
  | the read guard in `services/errors.py` | `[UV-3]`, `[UV-4]` |
  | the read-must-not-write fix in `core/manager.py` | `[UV-6]` |

  **Naming a test is not the same as the test biting**, and this entry is the proof: `[UV-4]`
  and `[UV-6]` were written first, passed, and were **decorative** — `[UV-4]` asserted against a
  path made unreachable by an unloaded `ErrorTracker`, and `[UV-6]` was masked by the
  service-layer guard hiding the manager-level fix it existed to prove. Both stayed green under
  ablation and were rewritten. Without the ablation this entry would name two tests that
  proved nothing.

  `[UV-5]` deliberately stays green under all three — it asserts the MANAGED case still works,
  so a guard that refused everything would pass `[UV-1..4]` and fail only here.
- **Safe to activate, and this was measured rather than assumed.** Every per-vacuum store on
  the reference install (`theme.vacuums`, `error_tracker`, `queue`, `snapshots`, `maps`,
  `setup_progress`) keyed **only** on the three managed vacuums — zero phantoms — so the guard
  rejects nothing that already exists. [[feedback_adversarial_self_break]] requires that
  enumeration before a guard newly activates over existing data; `SETUP-REJ-2` is what happens
  without it.
- **Out of scope, deliberately.** Recovering buckets orphaned by a vendor-app map rename is a
  migration feature, not this rule. This stops the growth.
- **Cite `INKV8ZQD`** from any handler that takes a `vacuum_entity_id`, and from any store keyed
  by one.

### `INJBNQ2Q` — dispatch sends only ids resolved against a LIVE source, and a total miss refuses

Stored room ids are a device handle. Before dispatch they are re-resolved against the live
source, and the two miss cases are **not** the same: a *partial* miss skips the rooms it could
not resolve and runs the rest; a *total* miss **refuses the dispatch with a user-visible
reason**. "Resolved live" must be a fact, not a belief.

**The consequence.** The total-miss branch used to return the **stale payload** — so the
documented safety inverted exactly when it mattered most. A full re-segment renumbers every
segment, which is precisely when nothing resolves, and precisely when shipping the previous
numbering sends the robot to the wrong rooms. A safety net that holds for small failures and
lets go of large ones is worse than none, because it is trusted.

**Why the two misses stay different behaviours.** Refusing on a total miss can strand a run
mid-sequence, so per-room phase dispatches skip-and-advance while a job dispatch refuses to
start. Different consumers, one invariant, deliberately **not** unified into a single
behaviour — unifying them would trade a wrong-room clean for a stranded run or the reverse.

- **Why:** recorded at the anchor site, `dispatch/manager.py`'s live-resolution block
  (RP-007 step 5, DQ-ACT-1/DQ-DE-1).
- **Enforced:** the `slug_to_live_id` resolution and its total-miss refusal.
- **Related.** [[INMKEHPQ]] — the slug is the identity a live id is resolved *from*.
  [[INT62M7A]] — the refusal carries a reason rather than reporting success.
- **Cite `INJBNQ2Q`** from any code that turns a stored room reference into a wire id.

### `IN6VSBJ1` — the robot question and the queue question are different questions, each with ONE owner

*"Is the robot cleaning?"* and *"is one of our dispatched jobs in flight?"* are not the same
question. `run_is_in_flight` answers the first (and counts an app-started **external** run);
`dispatched_job_is_in_flight` answers the second. Each has one owner, and the helpers'
docstrings prescribe which callers ask which.

**The consequence.** Five-plus sites hand-inlined `{"started", "paused"}` — the **queue** set —
and used it to answer the **robot** question. An app-started run holds the slot at
`status="external"`, so every one of them read a cleaning robot as idle: the progress ticker
skipped external runs entirely, the active-job sensor reported `none` mid-clean, and the dock
gate fired **during** an external run — pressing a dock button on a robot that was cleaning.

**A literal is not the bug; asking the wrong question is.** The queue set is correct *for the
queue question*, and several inline uses of it are right. What must not happen is the robot
question being answered from it. That is why the fix is two named predicates rather than one
shared constant: a constant makes the sets agree, and these sets are **supposed** to differ.

**One deliberate divergence, preserved.** The pose-sampler predicates were **not** re-pointed —
doing so would add `paused` to sampling. Recorded as intentional, not overlooked.

- **Why:** recorded at the anchor site, `jobs/active_job.py`'s two predicates and their
  docstrings, which name the distinction and their intended callers.
- **Enforced:** those two helpers, consumed across `dock/manager.py`, `listeners/job_progress.py`,
  `sensor/lifecycle.py`, `core/error_tracker.py`, `battery/manager.py`.
- **Related.** [[feedback_centralize_question_not_vocabulary]] — centralize the QUESTION, not
  the vocabulary; this is the case where two questions must stay two.
- **Cite `IN6VSBJ1`** from any code branching on whether a clean is happening.

### `INCFMPP1` — one slug derivation, at one admission boundary, with a stable uniqueness guarantee

A room's slug is derived in exactly one place — the discovery emit — and it is **unique within
its map**. `slugify_room_name` is a pure per-name transform with no cross-room guarantee, so
uniqueness is imposed at the boundary: the **lowest stable `room_id` keeps the bare slug**, and
every colliding sibling becomes `{slug}_r{room_id}`.

**The consequence.** Two rooms named "Bathroom" produced one slug. Dispatch's first-wins
`slug_to_live_id` then resolved **both to the same live segment**, so one room was cleaned twice
and the other never — and reconciliation reported a phantom `id_changed` for the room that had
not renumbered. The docstring claimed uniqueness the code did not provide, which is why it read
as settled.

**Deterministic, not merely unique.** Suffixing by `room_id` rather than by encounter order is
what makes re-discovery of the same physical rooms converge on the same identities. A counter
would produce a different assignment on a different traversal and silently re-point every
stored reference.

- **Why:** recorded at the anchor site, `rooms/room_discovery.py`'s disambiguation block, and at
  `rooms/utils.py::slugify_room_name`, whose Unicode handling keeps Cyrillic/CJK/emoji names
  distinct and non-empty rather than folding them all to `""`.
- **Enforced:** that block, and the empty-slug refusal at the same boundary.
- **Related.** [[INMKEHPQ]] — identity is the slug scoped to its map; this is where that slug
  comes from and why two rooms can never share one.
- **Cite `INCFMPP1`** from any code that derives, stores or resolves a room slug.

### `IN3ASEP8` — a rejected datum is rejected for every purpose

A sample a guard rejects may be **recorded**, but must not update any state that later
samples are measured against. Half-rejecting it corrupts every measurement that follows.

**The consequence.** A rejected datum is one the system has already decided it cannot
trust. If it is still allowed to move a baseline, an anchor, a flag or a lifecycle, then
every *accepted* sample after it is measured against something the system itself refused.
The corruption is silent and it compounds: nothing downstream can tell that its reference
point came from a discarded observation.

**Why it is not obvious, and this is the whole difficulty.** The guard EXISTS. A site that
rejects a datum for its headline purpose reads as handled, and the fields it *does* protect
are exactly what stops anyone looking for the ones it does not. The failure is never a
missing guard — it is a guard whose predicate covers less than its comment claims. Every
individual write is legitimate in isolation; the defect is the set of them.

- **Why:** the mechanism, the measured evidence and the accepted exception are recorded at
  the anchor site itself, `battery/manager.py::_process_sample` (the `DR-BAT-2` block).
- **Enforced:** PARTIALLY, deliberately, and the gap is named below. `advance_anchor`
  (`battery/manager.py::_process_sample`) holds `last_battery_level` and `last_sample_ts`
  for an out-of-order sample.
- **Bite.** Feed a sample the guard rejects, then assert that **no state a later sample
  reads** has changed — enumerated from the function, not from memory. Not "the anchor is
  unchanged": the anchor is whatever the next sample measures against, which is more than
  the fields named *anchor*.
- **⚠ THE BITE IS WIDER THAN THE ONE THIS RULE WAS DRAFTED WITH, ON PURPOSE.** The draft
  said *assert `last_battery_level` and `last_sample_ts` are unchanged* — two of the three
  fields — and **that assertion passes on the code at its own cited site.** A rule whose
  stated bite cannot detect its own violation is the same partial-guard shape one level up,
  and it would have shipped as enforcement. Anywhere this rule is applied, enumerate the
  writes; do not name the ones you remember.
- **⚠ ACCEPTED VIOLATION at the primary site — `battery/manager.py`, ledger C15.** The
  anchor is three fields and the guard holds two. `_update_session` has already run when
  `if advance_anchor:` is reached, and `last_charging` is written below it unconditionally,
  so a rejected sample still opens or closes a charge session carrying its own stale
  timestamp and level — which can leave a `session_history_recent` entry and a
  `sessions.csv` row whose `end_ts` precedes its `start_ts`. Nothing repairs those.
  **Left open on evidence, not oversight:** `elapsed_sec <= 0` requires the wall clock to
  step backwards (`ts` is minted per-sample from `datetime.now()`, never inherited from a
  state object, so co-timed samples cannot collide), and 104 vacuum-days of `samples.jsonl`
  across two live machines contain no such step, with 387 archived sessions containing no
  inverted row. Mechanism certain, occurrence unobserved.
- **⚠ IF THE EXCEPTION IS EVER CLOSED, BOTH STATEMENTS MOVE TOGETHER.** Guarding
  `_update_session` alone makes each repeated stale sample RE-OPEN the session; guarding
  `last_charging` alone makes the next genuine sample read a false transition and RESTART a
  live one. Either half alone is worse than neither — which is also why this rule is stated
  as *every purpose* rather than as a list of fields.
- **Cite `IN3ASEP8`** from any guard that rejects an observation while other state at the
  same site keeps updating.

> **Pairs with, and is not, the report-the-reason rule at the same guard.** `_process_sample`
> captures `rejected_delta_pct` for the audit trail *while* `delta_pct` stays `None`. That is
> the separate rule that a rejection must be visible; this one is that a rejection must not
> leak into the baseline. Two rules, one guard, worth keeping apart — a site can satisfy
> either while breaking the other.
## Rules with no code site — `EN`

> **⚠ RECLASSIFIED 2026-08-22 — these three were `PN` until now.** `PN` means what the
> specification always said it meant: *a pointer to where the deep canonical explanation
> lives*. This section had been using it for something else — *a rule whose enforcement
> lives outside the code* — and the divergence mattered because this is the document you
> consult to answer "is this an `IN` or a `PN`?". The tooling had drifted the same way
> (`doc_anchor.py`'s prose-declaration comment defined `PN` as the no-code-site class),
> so two of the three places PN was written down agreed against the third.
>
> The three rules were **re-minted, not re-prefixed**: `PN1E8AZT` → `ENMKYC3F`,
> `PNWJZYYR` → `ENFV9F37`, `PNN14JRN` → `ENQZV7VH`. Swapping only the class would have
> left the old tokens still *looking* well-formed while resolving to nothing, which is
> the stale-citation failure `[RR-4]` exists to catch. Dated records keep the old tokens
> deliberately — they record what was true when written.
>
> **The discriminator is now positive, and it is one question: WHO BREAKS IT?** A person
> doing something — editing `.storage` by hand, calling a service that moves a robot — is
> an `EN`. The program doing something is an `IN`. Each entry below used to carry a *"why
> this can never be an `IN`"* paragraph, defining the class by what it lacks; that form
> loses the moment someone argues a bite exists and promotes the row.

Some rules bind and can never have an enforcement site, because they are not about code.
They are decisions: what the system must not do, or what the product is for. An `IN` anchor
would be a lie — there is nothing to point at — so these carry an **`EN`** (enforcement
notation),
declared here rather than in source, because **here is where the reasoning lives**.

**A citation cannot make something an `EN`.** The order is one-way and the tooling sits at
the end of it:

> a human rules that this is genuinely a prose-only obligation → mint → declare here →
> attach citations from live artifacts → the ratchet proves the relationship stays present

Reversing any step lets link topology decide ontology — "three files mention it, so it must
be a rule" — which is how a register fills with things nobody decided. The checker proves
**reachability, not correctness**: a decorative citation passes it, and only review catches
that. Same division as every other gate here.

The integrity question inverts. For an `IN`, ask *"is it declared at a site?"* — a rule with
no site is suspect. An `EN` has no site by definition, so the meaningful question is the
reverse: **does anything cite it?** An `EN` nothing references is a document with a token on
it. Each one below therefore names where it is cited from.

**And the citation must be LIVE.** `docs/dev/history/` and `maintenance/` are as-of-their-date
records, and the repo's citation and index gates already exclude them for that reason. An `EN`
kept alive by a mention in a dated note is attached to nothing current — the prose equivalent
of a green test bound to the wrong thing. `[RR-4]` excludes them.

### `ENMKYC3F` — never edit `.storage` directly

> `anchor: ENMKYC3F` — **declared here.** This section is the site; there is no code one.
> *(was `PN1E8AZT` before the 2026-08-22 reclassification.)*

Home Assistant owns `.storage`. It rewrites the file on shutdown from its own in-memory
state, so an external edit is not merged — it is **overwritten**, and HA moves the file it
could not reconcile to a `.corrupt` backup. The edit is lost and the store may be too.

**Why this can never be an `IN`.** The rule governs what a *person or an agent* does with a
file this integration does not own. There is no branch to guard: our code always goes through
HA's `Store` helper, which is correct. The failure happens outside the process.

**What stands in for enforcement:** the UI is the supported path for every stored value, and
every service that mutates durable state exists precisely so nothing has to hand-edit. If a
value can only be changed by editing `.storage`, that is a missing service, not a licence.

- **Cited from** `core/storage.py`, the one place the `Store` helper is constructed.

### `ENFV9F37` — a service call moves real hardware

> `anchor: ENFV9F37` — **declared here.** This section is the site; there is no code one.
> *(was `PNWJZYYR` before the 2026-08-22 reclassification.)*

`hass.services.async_call` on a vacuum domain moves a robot in someone's home. It is not a
read, it is not idempotent, and it cannot be undone by calling something else.

**Why this can never be an `IN`.** The rule binds *anything that can reach a service call* —
a doc example, a test fixture, an agent exploring the API, a copied snippet. Most of those
are not code we own, and the ones that are cannot tell a deliberate dispatch from an
accidental one by inspection.

**What stands in for enforcement:** the dispatch chokepoint is single and named, so a call
that moves hardware is always visible in a diff at one place rather than scattered. Tests use
the container and never a live entity. Documentation shows payloads, not invocations.

- **Cited from** `dispatch/manager.py`'s send chokepoint.

### `ENQZV7VH` — the card is a glance surface

> `anchor: ENQZV7VH` — **declared here.** This section is the site; there is no code one.
> *(was `PNN14JRN` before the 2026-08-22 reclassification.)*

The card answers *"what is happening, and what do I press"* in a few seconds on a phone.
Analysis — history, comparisons, anything read column-by-column — belongs in the CSV export.

**Why this can never be an `IN`.** It is a product decision about scope, not a property of
any function. Nothing is *wrong* if a panel grows a data table; it is just no longer the
thing the card is for, and that degrades continuously rather than breaking.

**What stands in for enforcement:** the CSV export exists so there is somewhere for the
analysis to go. A request for more density on the card is usually a request for the export,
and answering it there keeps both surfaces good at their own job.

- **Cited from** `src/actions/review.js`, the export path.

---

## Not yet registered

Rules that behave like invariants and are currently held only in prose or in a single
subsystem doc. Each needs a consequence stated before it earns an entry.

- **Every map/pose payload is bound to (device identity, map identity, content identity), and
  every reader checks the binding.** `RF-09`, 13 findings, and it is **unenforced** — stated at
  the site: `mapping/map_source.py` records that `transform`/`viewport` carry no map-geometry
  version stamp and that *"there is no map-geometry-version stamping mechanism in this codebase
  to compare against here."* `eufy_version_of` is a content hash for client-side caching, not an
  identity binding. Consequences already filed: the Eufy candidate walk takes no vacuum identity
  (first coordinator wins), the Roborock walk no device and no map binding, one cache is keyed
  without `map_id`, and the content hash covers only the room raster while the cached value
  carries mutable geometry. Single-vacuum installs mask most of it, which is why it has survived.
- **A seam is correct at its OWN boundary; a caller's coincidence is not correctness.** Three
  live `RF-35` findings share one shape — an input accepted and not honoured, masked by
  something true of today's only caller. `_SinglePhaseMixin.build_phases` takes `strict_order`
  and discards it, and cannot express refusal, so nothing downstream can tell honoured from
  ignored. The engine phase envelope omits `queue_room_ids`/`queue_rooms`, which is harmless
  only because `included_room_ids` currently happens to equal the union of the groups' rooms.
  `build_room_clean_payload` folds an explicit empty `queue_room_ids` into "no filter" and
  returns every enabled room, which is harmless only because the live caller derives the ids
  fresh in the same call. The consequence is that **no test can catch the regression**: every
  test reaches the seam through the same coincidence, so the day a second caller arrives, three
  green suites say nothing. This has no enforcement site anywhere, which is why it is here and
  not above.
- **Presence, not truthiness** — the general form. [[IN40W49E]] clause (ii) states it, but
  scoped to adapter catalogs (`_catalog_key`: `if key not in block or block[key] is None`),
  and the rule did not travel. `queue_engine.py`'s `set(queue_room_ids or [])` is the same
  construct that clause was written to kill: an explicit empty value is unrepresentable,
  silently folded into "absent". A general rule filed under a specific invariant does not fire
  at the general site.

Adding one is cheap: mint an anchor, write the rule and its consequence, link the
explanation, name the enforcement site. Leaving one here is also fine — an unregistered
rule is honest; a registered rule with no consequence is not.
