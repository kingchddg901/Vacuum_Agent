# 23 — The Eufy Adapter

**Scope.** How the Eufy X10 Pro Omni answers [the contract](22-adapter-contract.md): what the
adapter computes as opposed to transcribes, the declarations that look like mistakes and are not,
and the surfaces that no longer do what they say. The CV segmenter is a separate subsystem and is
not covered here. The per-field schema is generated, not written — see
`.claude/generated-docs/adapter-config/ADAPTER-CONFIG.generated.md` in the repo.

This adapter was the reference implementation before there was a contract to implement. That
ordering is the single most useful thing to know about it, and most of what follows is downstream
of it.

---

## 1. The adapter computes five things and transcribes the rest

`adapters/eufy/adapter.py::register_eufy_adapter_for_vacuum` runs once per managed vacuum and
builds one dict of about thirty top-level blocks. Fourteen sibling modules supply the data; the
assembler adds almost nothing of its own. What it genuinely computes:

1. **The model code** — device registry first, the vacuum's `detected_model` attribute second.
2. **The model family** — via `adapters/eufy/model_catalog.py::MODEL_CODE_FAMILIES`.
3. **`has_attribute_rooms`** — read from the live `segments` attribute at registration.
4. **The entity-candidate lists.**
5. **Two rescue passes** over declared entity ids (§4).

Everything else is transcription. That matters when reading it: a block that looks like logic is
usually a literal that was measured somewhere else, and the interesting question is almost always
*which file owns the value*, not what the assembler does with it.

**The registry-first model read is not a preference.** The code previously read the attribute
alone, which works because the novel-API path mirrors the model onto it — and silently fails
everywhere else. The registry carries `T2351` on every `robovac_mqtt` transport; the attribute does
not. Reverting re-pins every scalar and Tuya-transport Eufy to family `generic`, which drops all
five model-based capability hints. The lookup helper is kept local rather than imported from core,
a knowingly-accepted duplicate in exchange for a self-contained adapter.

---

## 2. Eufy is the residual default, and it lives in literals

The retired pattern guide stated the norm plainly:

> The framework hard-codes no brand knowledge. […] If you find yourself wanting to special-case a
> brand in core, the value belongs in the adapter instead.

By imports, this holds. Core reaches into this package in exactly three statements against two
targets: `adapters/eufy/const.py` (twice, for values that are *persisted* and so cannot be
derived) and `adapters/eufy/segmentor.py` (once, flagged in place as a deliberate deviation because
the optional numpy/Pillow stack makes lazy adapter-side registration awkward). None of the eight
pure-data modules is imported from outside the package.

**The residue is in literals, and it survives every import-graph check.** Core's fallbacks are
Eufy's declared values character for character — the completion value `"completed"`, the
not-error sentinel set, the `cleaning`/`returning`/`paused` triple. A brand that declares nothing
does not get a neutral default; it gets Eufy's answer wearing the framework's name.

Two concrete instances a reader should not have to discover by accident:

- `adapters/eufy/const.py::SUPPORTED_TESTED_MODEL` is `"Eufy X10 Pro Omni"`, and it is the config
  flow's default for the `tested_model` field on **every** install, including a Roborock-only one.
  Roborock's equivalent constant has no reader at all. This is the invariant in its most literal
  form: a fallback that yields a brand's word.
- The same file's `VERSION` is imported into core and read by nobody, while `manifest.json` is the
  version that ships. Six of that file's constants are the *integration's* identity filed under a
  brand folder.

### The comments that describe the removed fallback

Until the room-profile catalog moved into the brand package, the framework catalog *was* Eufy's
catalog, because Eufy was first. Two core comments still describe that world —
`queue/queue_engine.py` and `profiles/room_profiles.py` each state that an absent catalog falls
back to in-code defaults "byte-identical for Eufy."

There have been no in-code defaults since the move. `profiles/room_profiles.py::resolve_profile_catalog`
returns empty for every undeclared key and `profiles/room_profiles.py::get_room_profile` raises.
Both comments sit next to code doing the opposite, in the two places a reader most likely checks.

---

## 3. Declarations that look like mistakes

Four of these read as bugs on first contact. Each is load-bearing, and each has a named failure
mode if undone.

### Clean intensity is value-mapped onto *different* words

`dispatch.room_fields` maps VA's `Narrow` → wire `normal` and `Deep` → wire `narrow`. Passing the
canonical names through unmapped — the identity rename every other room field uses — is wrong,
because upstream's extent map collapses `narrow` and `deep` onto the same enum value. Unmapped,
Narrow and Deep were the same clean, and the middle density (the app's "Medium") was unreachable
from this product entirely.

The cost is a genuine foot-gun that no amount of naming discipline removes: canonical `Narrow` and
wire `narrow` are **different densities**, and canonical `Deep` **is** wire `narrow`.

### `path_type` is deliberately not declared

Declaring it puts the same physical property on the wire twice in one room object. The verified
live payload read `{"clean_intensity": "Quick", "path_type": "None"}`, and the only reason the
device never had to choose between them is that the stored value was the invalid string `"None"`.
An undeclared canonical field is simply omitted.

The provenance is what makes this non-obvious: `path_type` appears in the initial release commit,
three weeks before adapters or a second brand existed. It was invented here as a duplicate — it
merely *reads* today as Roborock's word.

### Four dock actions are declared where only three are probed

`dock_events.action_buttons` iterates the union of candidates and tokens, so it declares four while
`entity_candidates` probes three. Removing the fourth is not a tidy-up.
`adapters/eufy/buttons.py::DOCK_ACTION_TOKENS` substring-matches, and the dock manager builds rival
token sets from every *other* action's tokens to stop one action binding a button another owns.
Drop `stop_dry_mop` from the declaration and `dry_mop` binds the **stop** button.

### The floor-type tables were split, not retired together

The non-carpet rows of `adapters/eufy/room_profiles.py::FLOOR_TYPE_WATER_DEFAULTS` were removed
while `adapters/eufy/room_profiles.py::FLOOR_TYPE_FAN_DEFAULTS` was kept whole. Applying one
reasoning mechanically to both is the trap, and the file says so.

The distinction is **preference vs expectation vs safety**. Floor type is collected for the map
render and the onboarding gate; nothing told the user it would also pick a water level, so
hardwood, laminate, tile and marble came out. Carpet-is-water-off stays because it is core's only
source for `profiles/room_profiles.py::no_water_value` on this brand — a safety property. Carpet
boosts suction stays because firmware does it anyway, so it meets an expectation rather than
imposing a taste.

---

## 4. The rescue pass, and the fourth copy of the naming assumption

Declared entity ids assume Eufy's naming. On an install that names entities differently, that
assumption fails silently, and `adapters/entity_resolve.py::resolve_declared_entities` exists to
recover: an id that resolves is returned untouched, and only an unresolvable one reaches a
domain-scoped sibling search.

`settings_selects` was the fourth place the naming assumption appeared and the only one with no
rescue at all. Adding one is the only deliberate behaviour change in that pass, and its effect is
that **a broken install starts working**: previously every id in the block resolved to nothing, the
setting entities came back empty, and the zone-clean panel had no controls — while the matching
*sensors*, which were rescued, read fine. That asymmetry is the whole bug: `sensor.…_water_level`
bound and `select.…_water_level` did not.

Two properties keep this from being a blunt instrument. Overrides are pinned before the rescue runs
and address roles rather than setting selects, so `overrides=None` is correct here. And the rescue
is domain-scoped, which is why `select.…_water_level` can never be rescued onto
`sensor.…_water_level`.

---

## 5. The fault table has two axes, and "unknown" is a real answer

Error seconds are subtracted from a job's cleaning time, so misclassifying a fault corrupts the
learning record rather than merely mislabelling a screen.

`adapters/eufy/vocabulary.py` splits codes on two independent axes — source, and whether the fault
invalidates cleaning evidence — and a code in **neither** evidence set is unclassified and
preserved. A single set, or a default that treats unknown faults as evidence-invalidating, means a
fault added after the table was written can zero a productive run. That is not hypothetical: five
dock-side pump faults once charged 455 s against a 360 s clean, the job recorded zero cleaning
time, and it was still marked usable for learning — so the model learned that 4 m² takes no time.

**The runtime alternative was drafted and rejected in source.** Asking the run timeline "was the
robot cleaning when this fired?" fails at its base, because the fault timestamp is when Eufy
*surfaced* the fault, not when it occurred. It also fails when the timeline is absent, and trades a
deterministic lookup for an unauditable heuristic.

`adapters/eufy/vocabulary.py::EUFY_EVIDENCE_INVALIDATING_ERROR_CODES` is **derived** (robot-sourced minus
`adapters/eufy/vocabulary.py::EUFY_EVIDENCE_SAFE_ROBOT_CODES`), which is only sound because Eufy's table
is closed — the full error enum was captured. Roborock hand-declares the same set instead, and its
file records that copying this derivation was checked and would be wrong. Same concept, two
justified shapes.

Upstream's own labelling is overridden where Eufy's protos contradict it. One battery-shutdown code
was mirrored from upstream into the dock set, and therefore into evidence-safe on the reasoning
that "the robot can be cleaning normally throughout" — which it cannot, because the run ended when
the pack died. Its evidence is truncated by definition.

`adapters/eufy/vocabulary.py::NOT_ERROR_SENTINELS` is a genuine brand-forced declaration, and the
cross-brand check proves it: core's fallback holds only the three HA-standard values, and Roborock
deliberately excludes `normal` because a Roborock code could legitimately contain it. Drop the
Eufy declaration and every idle reading is latched as a live fault.

---

## 6. Where this adapter instructs the next porter, and is wrong

This package was written as the pattern guide, so several comments address a future porter
directly. Three of those instructions have now been tested by a second brand and failed.

| The instruction | What Roborock did | Consequence of following it |
|---|---|---|
| `map_render` is Eufy-specific; a brand whose HA-core render is already frame-matched omits it | Declares it — the core render was **not** sufficient, because the parser reads the pixel layer to colour rooms and then discards it | A porter concludes a genuine two-brand axis is single-brand |
| Brands with always-on map exposure should drop `import_active_map` from `setup` | Has always-on exposure and **keeps** the step, as the brand-agnostic "discover + create bucket" op | Drop it and Configure Rooms opens empty |
| `adapters/eufy/entities.py::build_entity_id` keeps a `strategy` parameter that raises for its one unimplemented value, so "the gap is visible rather than silent" | Dropped the parameter entirely and kept only the suffix constants | A seam maintained for a case that has never arrived |

The `strategy` parameter is the honest one of the three: making a gap visible is a reasonable
instinct, and only a genuinely differently-named integration would test it. Both shipped brands use
the same object-id-suffix convention.

Two more places where this adapter's own prose contradicts its own data:

- `adapters/eufy/maintenance_components.py` states that `sensor_suffix` is `None` for components
  that source via `proxy_for`. The single component using `proxy_for` declares both, four lines
  below the prose. **The data is right and the prose is wrong** — core resolves the proxy first and
  falls back to the component's own suffix, so declaring both buys a real fallback on firmware that
  exposes a dedicated counter. A porter following the header nulls out a working fallback.
- `adapters/eufy/entities.py::ALL_SUFFIXES` is described as covering every suffix this adapter
  knows, derived rather than hand-listed, so that a new constant joins automatically. It covers
  every suffix *that module* knows. The assembler builds at least fourteen more as inline
  f-strings, which never enter the reserved-suffix universe — and they include the most recently
  added entity names, which is the half a reader would rely on the guarantee for.

---

## 7. Surfaces that do not do what they say

Everything in this section is live code or live prose that a reader would reasonably trust.

> ✅ **CORRECTED 2026-08-23.** Every prose defect below has been annotated AT ITS SITE — the section is kept as
> written because it is the record of what was found and why it read as trustworthy, not
> because the comments still say these things. Three items carry a behavioural remainder that
> was deliberately NOT changed in a prose pass and is named at the site instead: the third
> hardcoded copy of the robot-position ids in core (a signature change), `FAN_SPEED_ALIASES`
> pointing outside the declared options (removing an alias changes what a stored value
> migrates to), and `_safe_int`'s missing code guards (narrowing it would change two unrelated
> call sites). The zone-clean hint is closed — see D18 in [24 §8](24-roborock-adapter.md).

**`adapters/eufy/lifecycle.py` is fully superseded and says the opposite.** Its docstring tells a
porter to replace its three functions and to preserve their return shapes exactly, "because the
framework lifecycle listener depends on them." All three are callerless in production. The live
path is `listeners/_common.py::completed_finalize_signals`, which reads entity ids from the
registered config — and the shape has already diverged, so a porter who preserves this contract
implements the wrong dict for a function nothing calls. Worse for a live install, this version
re-derives ids by f-string, bypassing both user overrides and the rescue in §4. Roborock has no
counterpart. `adapters/eufy/vocabulary.py` carries a loud banner over *its* superseded functions;
this file, which is superseded in full, carries none.

**Two vocabulary keys have no consumer.** `blocked_work_mode_states` and
`blocked_task_status_states` are declared here with real values, and nothing reads either. Only
`blocked_dock_status_states` has a live reader. They are also the only vocabulary entries written
as inline literals in the assembler rather than sourced from `adapters/eufy/vocabulary.py`, which
is plausibly why they were missed when their consumer went away. The full history — this was a live
gate, orphaned in a window version control cannot see — is in
[22 §5](22-adapter-contract.md#5-declarations-nothing-reads).

**Most of `constants.py` is unreachable, and its live values are unlinked copies elsewhere.** The
file presents itself as the measured-constant surface and instructs a porter to re-measure and
replace. Eight of its fifteen constants have no importer. The values that *are* live are restated
as literals in two other files — the wash-interval bounds in the assembler, the water rates in
`adapters/eufy/water_config.py` — and nothing makes the pairs agree. Re-measuring the documented
constant changes nothing.

**The `cleaning_intensity` entity role is never bound.** The assembler sources it from the
capability probe's `entities` dict, which has ten fixed keys and does not include it, so the
expression is unconditionally `None` and the key is stripped. The role *is* probed — from the
candidate list, as a boolean feeding path-control support — so the schema's description is true of
the candidate, not of the slot it annotates. The value is discarded, so the remedy is the comment
rather than the code; but the sentence currently reads as authority that the role is bound.

**Raw robot position is named in three places, one of them core.** The entities module states that
the position entities are excluded because the mapping subsystem manages them. They are hardcoded
in the assembler, and read in core by a third hardcoded copy that bypasses the declared role, the
rescue, and any user override. Because those suffixes are not constants, they are excluded from
`ALL_SUFFIXES` and therefore from the guard that stops sibling matching handing one role's entity
to another. On an install where the rescue was needed, the declared role would resolve and the core
copy would still return nothing — the shorter copy is the bug.

**One capability hint has nowhere to be declared.** A comment explains that zone-clean support is
read from capabilities rather than hardcoded "so a model catalog entry can declare it False and be
believed." The core mechanism is real and the capability is in
`core/capabilities.py::KNOWN_CAPABILITY_HINTS` — but on this brand the hints are built from five
fixed model-family membership tests, and `adapters/eufy/model_catalog.py` maps codes to family
*names* with no capability fields at all. Roborock's catalog does carry per-model capability rows,
which is presumably where the sentence came from. Declared here today, it would be ignored.

**The three model catalogs do not describe the same device set.** A code can appear in
`adapters/eufy/model_catalog.py::MODEL_CODE_FAMILIES` and in
`adapters/eufy/upkeep_catalog.py::UPKEEP_MODEL_NAMES` while having no row in
`adapters/eufy/upkeep_catalog.py::UPKEEP_MODEL_GUIDE_FAMILIES` — a model name with no guide behind
it. Nine of twenty-two codes have no upkeep name at all, and
`adapters/eufy/water_config.py::WATER_MODEL_CONFIGS` contains exactly one model, so every other
Eufy takes core's generic flow rate. Every degradation is reported honestly rather than faked; the
hazard is that a catalog comment reading "dock-action entities confirmed" reads as *supported*
when one of three catalogs was updated.

**A retired premise is cited under the live name.** A comment in `adapters/eufy/room_profiles.py`
explains that two retired cleaning-path values need no alias because the store repair resets them
to the brand default. That is the pre-fix behaviour, and it is the exact defect
`adapters/eufy/vocabulary.py` was later written to condemn — the fold moved every affected room
from the middle density to the fastest one. `rooms/vocabulary_migration.py::_alias_target` now
resolves the alias first. The comment predates the fix by one day, and it sits in the file that
owns the values.

**`FAN_SPEED_ALIASES` still points at a value no option list contains.** It maps the BoostIQ
spellings onto a canonical `boost` that was removed from the shipped options once it was
established that `boost` is not a suction level at all — it is the auto carpet-boost switch, and
the payload resolves fan speed by index, so the chip silently applied no suction. The alias map was
never swept. Live effect splits by consumer: the learning and card path still emits the code, while
`rooms/vocabulary_migration.py::_alias_target` ignores an alias pointing outside the declared
options — and its docstring calls exactly that shape an adapter defect. The brand declares an alias
core is documented to refuse.

**The "dock is servicing" question has three answers.** `adapters/eufy/vocabulary.py::HARD_SERVICE_STATES`
(seven strings, both spellings of the recycling state, all three dust-empty variants) gates job
start; `blocked_dock_status_states` (two strings, one spelling, no dust-empty) gates the stranded-run
reaper; and `external_mid_run_statuses` is a hand-copied duplicate of
`adapters/eufy/vocabulary.py::CANCEL_SERVICE_EXCLUSION_STATES` in a different case, declared inline
in the assembler. The shorter copy is the exposed one: a dock status using the second spelling
blocks a start but is invisible to the reaper's dock channel. The task-status channel usually
compensates, which is why this reads as working.

**One coercion guard is short.** The dead adapter helper
`adapters/eufy/vocabulary.py::_exact_error_code` documents the rule — never `int()`, because
`int(3.7)` is a real code, and `bool` is an `int` subclass so `True` resolves to code 1 — and
`core/error_tracker.py::_code_key` preserves both guards verbatim. But
`core/error_tracker.py::_safe_int`, which reads the code before either sees it, is a bare `int()`
with neither guard. Both of those coerced values land on codes that are robot-sourced and not
evidence-safe, so their seconds are deducted — the exact arithmetic the fault table exists to
protect. No non-integer has been observed arriving there, so this is a guard asymmetry with a named
input rather than a confirmed field failure.

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
