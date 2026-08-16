# Entity Resolution Reliability — recognise, don't derive

**Status:** design **APPROVED 2026-08-14** (Chris ruled all three open decisions — see §8).
Not built yet. Written after issue
[#49](https://github.com/kingchddg901/Vacuum_Agent/issues/49) field data disproved the diagnosis
this project was carrying. Staged deliberately: *"features are nice, working system is better"*.

**SHIPS AS ONE SET** — P0 + P1 + P2 + the §5 census enrichment go out together, not
incrementally. P3 remains blocked and out of scope for this release.

> **Scope note.** This is a delta on [21-adapter-system](../21-adapter-system.md) §5.2 step 4
> and §6, not a parallel design. Every seam it uses already exists.

---

## 1. What the field data actually proved

Issue #49: a reporter whose vacuum is `vacuum.robovac_x10_pro_omni` while its 65 companion
entities are named `sensor.living_room_eufy_clean_x10_pro_omni_*` — **two unrelated stems on
one device.** Twelve roles unresolved.

**The diagnosis this project carried was wrong.** It said the per-candidate rescue "was never
wired into `entity_candidates`". It is wired in:

- `augment_candidates_from_device` (`core/capabilities.py::augment_candidates_from_device`), called by
  `detect_capabilities` at `:310` — already documented at
  [21-adapter-system](../21-adapter-system.md) §5.2 step 4.
- Landed in `9a37ad6c` (2026-08-04); **in v2.0.0** by `git merge-base --is-ancestor`. The
  reporter runs 2.0.1, so they have it.
- Run against the reporter's exact ids it rescues **every probed role**. The matcher is
  correct.

Eliminated, each by a specific check — **do not re-walk these**:

| theory | killed by |
|---|---|
| not shipped / older build | commit is an ancestor of both v2.0.0 and v2.0.1 |
| load-order between the two rescues | both run in ONE function, `adapters/eufy/adapter.py::register_eufy_adapter_for_vacuum` and `:314` |
| vacuum absent from registry at setup | `resolve_declared_entities` read `config_entry_id` off the SAME lookup and succeeded |
| diagnostics recomputing one half | both halves are stored setup-time state, `diagnostics.py::_vacuum_diagnostics` |
| stale caps surviving the upgrade | adapter registration runs from `async_setup_entry` (`brands.py::register_brand_adapter`); caps rebuild every start |
| the failing entities are disabled | census says `disabled=false` for all ten — but see §2.2 |

**Still unknown:** `entry.device_id` empty at setup, no siblings at that instant, or the bare
`except Exception` (`capabilities.py::augment_candidates_from_device`) swallowing on **HA 2026.8.1** (we pin 2026.5.3 and
cannot introspect theirs). P0-3 exists to make this answerable instead of inferable.

Battery — the issue's headline — **is** resolved on their 2.0.1 dump
(`sensor.living_room_eufy_clean_x10_pro_omni_battery`, state `100`). What remains broken is the
ten roles that tell the card what the vacuum is *doing*.

### 1.1 Two defects confirmed on real hardware

**Suffix collision — silently wrong data, not missing data.** Both
`..._cleaning_area` and `..._total_cleaning_area` exist on that device, and both satisfy
`endswith("_cleaning_area")`. Same for cleaning_time. Which one wins depends on entity-registry
ordering, so `cleaning_area` can resolve to the **lifetime total**. This is the strongest
argument in the whole document: name matching *provably cannot* separate these two, because one
declared suffix is a substring of another.

**"Absent" and "present but switched off" render identically.** Five entities on that device are
disabled, including both `..._robot_position_x_raw` and `..._robot_position_y_raw`. They exist
with exactly the ids we derive; a disabled entity has no state, so `_find` returns `None` and the
role reads as missing. Same output, opposite fixes — one is our bug, the other is a toggle in the
user's UI. This is [21-adapter-system](../21-adapter-system.md) §5.2's DIAG-1 argument one level
deeper.

---

## 2. P0 — correctness (small, independently shippable)

Nothing here needs approval on the later stages. These are bug fixes.

### 2.1 Exclusive, longest-suffix-wins sibling matching

`endswith(suffix)` is not a safe test when one declared suffix is a substring of another.

Fix: build the claim set from **all** declared suffixes across roles, and let the **longest**
matching declared suffix claim a sibling. `..._total_cleaning_area` ends with a longer declared
suffix (`_total_cleaning_area`) than `_cleaning_area`, so it belongs to `total_cleaning_area` and
must not be offered to `cleaning_area`. Exclusivity is the property, not a heuristic.

Regression test must use the real colliding pair, not a synthetic one.

### 2.2 Distinguish absent / disabled / resolved

`_find` returning `None` currently erases *why*. Carry a reason
(`resolved` | `disabled` | `absent`) and surface it in `entity_resolution`. A disabled companion
is user-actionable immediately and costs us nothing to report.

### 2.3 Break the silence in the swallow

`except Exception: return dict(cands)` (`capabilities.py::augment_candidates_from_device`) logs nothing, so a field rescue
failure is indistinguishable from "ran and found nothing" — the exact silent-failure shape the
function's own docstring calls the worst outcome. Log at WARNING with the exception, and record
in diagnostics: `augmentation: {ran, siblings_seen, merged, error}`.

**This is what would have made #49 answerable from the first dump.**

---

## 3. P1 — companion-stem derivation

**RULED 2026-08-14, refined same day: pre-fill ONLY for ambiguous roles that do not resolve
today.** Three cases, and the boundaries are what matter:

| case | behaviour |
|---|---|
| role resolves today | **UNTOUCHED.** No suggestion, no prompt, no change. Non-negotiable — this is the ENT-1 safety property and it is what keeps every working install byte-identical. |
| does not resolve, exactly one candidate | **AUTO-APPLY.** The install self-heals with no user action. |
| does not resolve, candidates compete | **PRE-FILL and ask.** Confirmation is spent only where there is a real choice. |

> **CORRECTION, made while building this (2026-08-14).** The framing above — stem derivation as
> the thing that fixes a #49-class install — is **wrong**, and the code proved it. Deriving the
> stem from device siblings requires reading device siblings, which is precisely the step
> suspected of failing on that install; the derivation inherits the failure it was meant to
> route around. Circular.
>
> **What actually closes the gap is SCOPE, not stems.** `resolve_declared_entities` searched the
> vacuum's CONFIG ENTRY and rescued battery on that very install; `augment_candidates_from_device`
> searched only its DEVICE and rescued nothing. Same instant, same registry. Searching both
> (live:ENT-5) is the fix with field evidence behind it, and it retires "device_id absent at
> setup" as a suspect rather than diagnosing it.
>
> The stem keeps a real but smaller job: **breaking ties** when several siblings match one role
> (live:ENT-6). It never synthesises an entity id — a majority vote is evidence about naming, not
> proof that an entity exists.

> ⚠ **SUPERSEDED — the majority-stem vote was never shipped, and `2c1d847f` deleted it.**
> Competing candidates are settled by the FOUR-RUNG CONTEST LADDER instead
> (`_narrow_competing`, `capabilities.py::_narrow_competing`): `object_id` → `translation_key` →
> `state_class` → `magnitude`, strongest evidence first, each rung DECISIVE or the next is
> tried, and no rung deciding leaves the role unresolved. §4.5.1 of this same document
> describes the ladder; this section is kept for the reasoning that led there — the
> tie-is-not-a-majority insight below is what became "an undecidable contest leaves the
> role UNRESOLVED rather than guessing". Do not implement the paragraph that follows.
>
> Why the ladder won: a stem vote is evidence about NAMING, and the first three ladder
> rungs read the entity REGISTRY (`translation_key`, `state_class`), which is the upstream
> integration's own declaration and is available before any entity has a state.

Derive the companion stem by majority vote across the sibling object_ids (strip each one's owning
suffix; what remains is its stem), and use it ONLY to rank competing candidates. **A tie is not a
majority** — two vacuums on one config entry produce a dead heat, and that must stay ambiguous
rather than resolve to whichever stem was inserted first.

### 3.1 "Unambiguous" is a predicate, not a judgement

Auto-apply requires ALL of:

1. exactly one surviving candidate after §2.1's exclusive longest-suffix claiming;
2. that candidate is enabled and has a state (a disabled match is §2.2's case, not this one);
3. its stem IS the device-majority stem.

Anything else is ambiguous and goes to the user. Worked example from #49: `cleaning_area` has two
raw `endswith` matches, but exclusive claiming assigns `_total_cleaning_area` to its own role,
leaving exactly one — so it auto-applies. That is the collision fix and the self-heal being the
same mechanism.

**Evidence limit stays on the record:** the stem rule is n=1. Auto-apply is bounded by the
predicate above rather than by confidence in the heuristic — a second install that disagrees
produces ambiguity and a prompt, not a silent wrong answer.

**Verified against the reporter's real census: 65/65 companions share
`living_room_eufy_clean_x10_pro_omni`, and stem + declared suffix hits a real entity for every
failing role.** (An earlier 64/65 count was a scrape artifact — the outlier was the *derived*
`select.robovac_x10_pro_omni_scene`, which does not exist.)

Safety is the ENT-1 argument unchanged: candidates are **appended**, derived stays first, so an
install where derivation already works resolves byte-identically.

**Evidence limit — state it plainly:** n=1 install. Ship P2's record first if we want this
confirmed before it becomes automatic (§6).

---

## 4. P2 — user entity override (the escape hatch)

Unblocks a user regardless of how good our resolution ever gets, and reaches the cases
prefix-rescue *provably* cannot: `scene` (declared `_scene`, actual `_scene_task` — a suffix
mismatch, not a stem one) and a companion on a **different device**.

### 4.1 Mirror the existing precedent — do not invent a mechanism

> ⚠ **PRECEDENT WITHDRAWN, 2026-08-16.** This section rested on `brand_overrides` as an
> established shape. That key has been **removed**: brand support is a statement about a
> tested upstream integration, so a rename is ours to follow and an unsupported system
> wants an adapter — there was never going to be a writer for it, and a read path with no
> writer is a declaration defended by a comment rather than by a reader.
>
> The design below is **unaffected in substance**: entity overrides are a genuinely
> different question. Which entity fills a role IS install-specific (two device slugs on
> one vacuum, a renamed companion) and no amount of adapter maintenance can know it from
> here — which is exactly why `entity_overrides` has writers and `brand_overrides` never
> would have. Read "mirror the existing precedent" below as "this is the shape we chose",
> not as "another key already does it".

The shape is a per-vacuum user override in config-entry `data`, read by core
(see [21-adapter-system](../21-adapter-system.md) §6.1 for how brand selection resolves
now that no such override exists):

```
data["entity_overrides"][vacuum_entity_id] = {role: entity_id}
```

### 4.2 THE TRAP — do not store this as an adapter config

[21-adapter-system](../21-adapter-system.md) §6: stored configs load first, then
`register_brand_adapter` **overwrites** them — *"code adapters always win"*. An override
persisted as a stored adapter config would be silently clobbered at every startup. It must be
read **inside** the code-adapter path.

### 4.3 Where it plugs in — one place, both brands free

`augment_candidates_from_device` already speaks role → candidate list. Feeding the override in
there means Roborock and Dreame inherit it with **zero adapter changes**, and core stays owner
of the mechanism with no brand vocabulary in it.

### 4.4 Precedence — RULED: OVERRIDE WINS

**Chris, 2026-08-14: "override wins — it's a user choice."** The override is consulted FIRST,
ahead of every derived and device-sibling candidate. Not a last-resort fallback.

Rationale on the record: fallback-only cannot correct a *wrong* auto-resolution (§1.1's
collision succeeds and is wrong), and a user who sets an override and sees nothing change is
the same silent failure this document exists to remove.

**Fall-through, and it is NOT silent.** If the override does not resolve — the entity was
renamed or deleted after it was set — resolution continues to the normal candidates rather than
pinning a dead id. But it reports `override_unresolved` through the §2.2 reason field. A user
choice that has quietly stopped working must be visible; silently substituting our own guess for
their stated intent would reintroduce exactly the failure mode being fixed.

### 4.5 UI

A step on the existing `EufyVacuumOptionsFlow` (`config_flow.py::EufyVacuumOptionsFlow` — today a single
`async_step_init`, already using `selector.EntitySelector`). Add a step, not a subsystem.

Default the screen to the **unresolved roles only** (already computed as
`entity_resolution_summary.unresolved`), with a "show all" toggle for correcting a wrong
resolution. Picker defaults to the vacuum's own device entities, ranked; plain entity selector
as the escape hatch, since the different-device case is precisely who needs this.

### 4.5.1 The "System" sub-tab — WHAT WE ARE READING (surface 2)

**Name provisional** (Chris, 2026-08-14: *"System for now, I can pick a better name
before we ship"*). Rejected: "System settings and configuration" — `settings` and
`configuration` are the same word twice, and the label lives in the Setup tab strip, which is
the tightest horizontal space in the panel at 360px. It measures 31 characters in English and
German pushes it past 40; the theme editor's sub-tab strip already had to be rebuilt for exactly
that. Frontend string, so it routes through the project's own i18n pipeline — not the 18-file
HA-side path.

**Its DEFAULT view is the FULL binding table, not a filtered one.** This is the whole point and
the easiest thing to get wrong. Every surface built so far renders only roles that FAILED, and a
failures-only view is structurally blind to the defect that motivated this document: the §1.1
collision resolves *successfully* — a real, existing, enabled entity — it is simply the WRONG
one, off by ~4000x. That user's screen looks perfectly healthy. A view that lists problems
cannot show them a problem that does not look like one.

One row per role: **role · entity id · HOW IT WAS CHOSEN**, with editing as the exception on a
row rather than the purpose of the screen.

The provenance column is the part with no home today. All of it is already computed and lands
only in a diagnostics dump, which is a file you download and paste into an issue:

| shown as | source |
|---|---|
| derived name | the adapter's own candidate resolved |
| device sibling / config-entry sibling | live:ENT-5, and `entity_augmentation` reports the split |
| translation_key / state_class / magnitude | live:ENT-9, which rung of the ladder decided |
| your override | `overrides_applied` |
| disabled · absent · override_unresolved | live:ENT-2 `entity_resolution_reasons` |

Two reasons beyond the collision. The ENT-9 ladder now makes AUTOMATED choices between competing
candidates, and the magnitude rung is the least certain of them — a human should be able to
sanity-check it. And issue #49's battery is not a naming bug at all: the reporter could see we
ARE bound to `sensor.living_room_..._battery` at state 100, which moves their question from
"what is broken" to "why is it not drawing".

This also carries the removal path the options flow cannot offer (§4.5: that screen merges and
never clears, because its fields disappear once a role is fixed).

Per-vacuum, inheriting the Setup tab's existing per-vacuum iteration. The container name is
deliberately broad. (It was originally worded so a *brand* override could land beside it
later; that idea has since been ruled out — see the §4.1 note.)

#### Two levels, and the CURRENT VALUE on the summary row

Refined after an external review (ChatGPT, 2026-08-14), which was right on all three counts.

**Summary row** — role · entity id · **current value** · how it was chosen · [Change].

The value is the cheapest sanity check that exists, and it needs no engineering literacy:

```
Cleaning time         sensor.robin_cleaning_time         0 min
Total cleaning time   sensor.robin_total_cleaning_time   166 min
```

A reader confirms that in under a second. It also separates the two failure modes that look
identical from outside — issue #49's battery resolves to a real entity reading `100` while the
card draws nothing, so seeing the value instantly moves the question from "the resolver picked
wrong" to "the resolver picked right and the consumer is broken".

**Expanded row** — the forensic trail: every rung, the traits behind it, and the alternatives
with WHY each was rejected.

**THE TRAIL MUST NOT MANUFACTURE AGREEMENT.** The ladder short-circuits on the first decisive
rung, so a role decided by `translation_key` never evaluated `state_class` or magnitude. Those
render as **not evaluated**, never as concurring. Showing unrun rungs as corroboration would
produce exactly the confident-and-wrong artifact this surface exists to catch — the review's
sketch had magnitude as "supporting" on a row where it was never computed.

`augment_candidates_from_device` now records this (`report["decisions"]`), verified on live
hardware:

```
ivy    cleaning_area -> by=translation_key  rejected {ivy_total_cleaning_area: translation_key=total_cleaning_area}
alfred cleaning_area -> by=state_class      rejected {..._total_cleaning_area: state_class=total}
robin  task_status   -> by=translation_key  rejected {robin_status: translation_key=status}
```

Provenance is a first-class enum, not prose (`BY_OBJECT_ID`, `BY_TRANSLATION_KEY`,
`BY_STATE_CLASS`, `BY_MAGNITUDE`, plus derived / sibling / override / recorder). Six months from
now "chosen by: magnitude" sends you somewhere completely different from "chosen by: manual
override" — one is a resolver bug to chase, the other is the user's own decision and not a bug
at all.

When the recorder pass lands it renders in the same human register — *"Observed reset behaviour
across 3 cleaning runs"*, never `recorder_reset_behavior`.

### 4.6 One override generalises to the whole device

Diff declared against chosen: the **suffix is identical**, so the stem is the only variable.
Learn it from one pick and pre-fill the other unresolved roles for confirmation. The user fixes
one role, not eleven.

### 4.7 Costs to accept before coding

- **New persisted key** — trips the large-change rule; that is why this is a spec.
- Config-flow labels are **HA-side**: a new `translation_key` means **all 18 locale files by
  hand** (see the HA-side translations ruling — services are names and are never localized).
- No user-facing string may be added without routing through i18n at creation.

---

## 5. P3 — trait scorer (recognise, don't derive) — BLOCKED on data

The endgame Chris named: stop *generating* names, start *recognising* entities. Score each
device entity per role on traits the registry already holds:

| role | discriminating trait |
|---|---|
| `battery` | `device_class: battery` — nothing to guess |
| `cleaning_area` | unit ft²/m² **and not** the token `total` (the §1.1 collision, solved by shape) |
| `water_level` | a `select` whose options match a known water vocabulary — the options list is a fingerprint |
| `task_status` vs `work_mode` | both plain string sensors, so name is useless; only their **state vocabularies** separate them — already in `adapters/eufy/vocabulary.py` |

Brand-agnostic by construction: core owns the traits (HA-standard `device_class`/unit), each
brand supplies only its vocabulary. One mechanism, three jobs — auto-resolve when confident,
rank the P2 picker when not, and P2's record scores the scorer.

**BLOCKER — build the census enrichment first, and let it ship alone.**
`_device_entity_census` (`diagnostics.py::_device_entity_census`) records only `entity_id`, `disabled`, `platform`.
None of the traits above are in any dump we hold, so a scorer built today would be tuned against
Alfred and called general. Add device_class, unit, select options and state to the census, then
validate against dumps that come back.

---

## 6. Learning — what is honest, and what is not

**Local generalisation (§4.6) needs no collection at all** and is where the value is.

**Cross-user learning means telemetry. Not proposed. Do not add silently.** The honest channel is
the dump: put the before/after record (candidates considered, siblings seen, what the user picked
instead) in diagnostics, and every filed issue hands us the pattern with no consent problem.

That record is also P0-3's instrumentation — **one artifact, both jobs.**

---

## 7. Implementation map (proposed)

| Piece | Where |
|---|---|
| Exclusive longest-suffix matching | `core/capabilities.py` `augment_candidates_from_device` |
| absent/disabled/resolved reason | `core/capabilities.py` `_find*` + `diagnostics.py` `entity_resolution` |
| Augmentation telemetry + WARNING | `core/capabilities.py::augment_candidates_from_device` + `diagnostics.py` |
| Companion-stem derivation | `core/capabilities.py` (new helper, brand-agnostic) |
| Override read path | `augment_candidates_from_device`, keyed by `custom_components/eufy_vacuum/const.py::ENTITY_OVERRIDES_KEY` |
| Override UI step | `config_flow.py` `EufyVacuumOptionsFlow` + 18 locale files |
| Census enrichment | `diagnostics.py::_device_entity_census` `_device_entity_census` |
| Trait scorer | core (traits) + `adapters/*/vocabulary.py` (vocabularies) |

**Testing:** core tests stay engine-agnostic with a fake/stub adapter; the real Eufy collision and
stem cases belong in `tests/adapters/eufy/`. `pytest tests --no-cov` is the behaviour gate.

---

## 8. Decisions — RULED 2026-08-14

| # | Question | Ruling |
|---|---|---|
| 1 | §4.4 precedence | **Override wins** — "it's a user choice". Consulted first, ahead of all derived and sibling candidates. Falls through if unresolvable, but reports `override_unresolved` rather than failing silently. |
| 2 | §3 stem: automatic or suggested | *(The RULING stands; the MECHANISM it ruled on does not — the stem vote was replaced by the contest ladder, see the banner in §3.)* **Pre-fill ONLY for ambiguous roles that do not resolve today.** A role that works is never touched; an unresolved role with exactly one candidate auto-applies (self-heals); only competing candidates prompt. "Unambiguous" is the three-part predicate in §3.1, not a confidence call. |
| 3 | Stage gate | **Ship as one set.** P0 + P1 + P2 + §5 census enrichment release together; P0 does NOT go out alone. P3 stays blocked. |

### 8.1 Consequences of ruling 3

Shipping as a set means the wrong-data collision fix (§2.1) waits for the override UI and its 18
locale files. That is the accepted trade: one coherent release rather than a correctness patch
followed by a feature that changes the same code paths again.

The set is therefore gated on the slowest item — the options-flow step and its translations —
so that is the schedule risk to watch, not the core logic.
