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

- `augment_candidates_from_device` (`core/capabilities.py:182`), called by
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
| load-order between the two rescues | both run in ONE function, `adapters/eufy/adapter.py:237` and `:314` |
| vacuum absent from registry at setup | `resolve_declared_entities` read `config_entry_id` off the SAME lookup and succeeded |
| diagnostics recomputing one half | both halves are stored setup-time state, `diagnostics.py:485-497` |
| stale caps surviving the upgrade | adapter registration runs from `async_setup_entry` (`brands.py:189`); caps rebuild every start |
| the failing entities are disabled | census says `disabled=false` for all ten — but see §2.2 |

**Still unknown:** `entry.device_id` empty at setup, no siblings at that instant, or the bare
`except Exception` (`capabilities.py:232`) swallowing on **HA 2026.8.1** (we pin 2026.5.3 and
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

`except Exception: return dict(cands)` (`capabilities.py:232`) logs nothing, so a field rescue
failure is indistinguishable from "ran and found nothing" — the exact silent-failure shape the
function's own docstring calls the worst outcome. Log at WARNING with the exception, and record
in diagnostics: `augmentation: {ran, siblings_seen, merged, error}`.

**This is what would have made #49 answerable from the first dump.**

---

## 3. P1 — companion-stem derivation (PRE-FILL, never auto-applied)

**RULED 2026-08-14: pre-fill.** The derived stem proposes; the user confirms. It does NOT
silently become the resolution.

**State the consequence plainly:** a #49-class install therefore still needs ONE user action —
open the options step and accept the pre-filled values. This design does not self-heal such an
install, by choice. What it buys instead is that the heuristic can never silently resolve a role
to the wrong entity on an install we have never seen, which matters because the evidence behind
it is n=1 (below). The user acts once, on a screen where every field is already filled in
correctly.

Derive the companion stem by majority vote across the device's entity object_ids, then use
`f"{domain}.{stem}{suffix}"` as the pre-filled suggestion for each unresolved role.

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

`brand_overrides` already establishes the shape (`adapters/brands.py:56`,
[21-adapter-system](../21-adapter-system.md) §6.1): a per-vacuum user override in config-entry
`data`, read by core, *"nothing writes this key yet; the read path exists so the planned UI has
somewhere to land."* This is the same pattern one level down:

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

A step on the existing `EufyVacuumOptionsFlow` (`config_flow.py:82` — today a single
`async_step_init`, already using `selector.EntitySelector`). Add a step, not a subsystem.

Default the screen to the **unresolved roles only** (already computed as
`entity_resolution_summary.unresolved`), with a "show all" toggle for correcting a wrong
resolution. Picker defaults to the vacuum's own device entities, ranked; plain entity selector
as the escape hatch, since the different-device case is precisely who needs this.

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
`_device_entity_census` (`diagnostics.py:406`) records only `entity_id`, `disabled`, `platform`.
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
| Augmentation telemetry + WARNING | `core/capabilities.py:232` + `diagnostics.py` |
| Companion-stem derivation | `core/capabilities.py` (new helper, brand-agnostic) |
| Override read path | `augment_candidates_from_device`, key mirroring `adapters/brands.py:56` |
| Override UI step | `config_flow.py` `EufyVacuumOptionsFlow` + 18 locale files |
| Census enrichment | `diagnostics.py:406` `_device_entity_census` |
| Trait scorer | core (traits) + `adapters/*/vocabulary.py` (vocabularies) |

**Testing:** core tests stay engine-agnostic with a fake/stub adapter; the real Eufy collision and
stem cases belong in `tests/adapters/eufy/`. `pytest tests --no-cov` is the behaviour gate.

---

## 8. Decisions — RULED 2026-08-14

| # | Question | Ruling |
|---|---|---|
| 1 | §4.4 precedence | **Override wins** — "it's a user choice". Consulted first, ahead of all derived and sibling candidates. Falls through if unresolvable, but reports `override_unresolved` rather than failing silently. |
| 2 | §3 stem: automatic or suggested | **Pre-fill.** The stem proposes, the user confirms. Never auto-applied. A #49-class install still needs one user action — accepted knowingly (§3). |
| 3 | Stage gate | **Ship as one set.** P0 + P1 + P2 + §5 census enrichment release together; P0 does NOT go out alone. P3 stays blocked. |

### 8.1 Consequences of ruling 3

Shipping as a set means the wrong-data collision fix (§2.1) waits for the override UI and its 18
locale files. That is the accepted trade: one coherent release rather than a correctness patch
followed by a feature that changes the same code paths again.

The set is therefore gated on the slowest item — the options-flow step and its translations —
so that is the schedule risk to watch, not the core logic.
