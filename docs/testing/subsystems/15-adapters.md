# 15 — Adapters — Subsystem Test Map

The adapter subsystem is the brand-abstraction boundary: a registry maps each
vacuum entity to an adapter config (entities, vocabulary, water/upkeep models,
maintenance components), loaded from storage and validated against a schema.
Two concrete adapters now live behind this boundary — **Eufy**
(`adapters/eufy/`) and **Roborock** (`adapters/roborock/`) — each with its own
focused suite, plus `adapters/brands.py` (which registrar runs for a given
vacuum) and the brand-agnostic conformance harness that runs every contract
test once per shipped brand. Covered by **205 framework tests across 11 files**
(`test_adapters.py`, `test_adapter_contract.py` — parametrized over both
brands — and `test_brand_selection.py`), plus **212 Eufy-adapter tests** and
**37 Roborock-adapter tests**.

A third adapter directory, `adapters/dreame/`, holds **data only and is deliberately
not wired** — it has no `BRAND_REGISTRARS` row, so the conformance harness above does
not reach it and none of those counts include it. Its 37 tests live in
`tests/adapters/dreame/` and are documented below; they exist precisely because nothing
else in the tree can fail on that directory.

<!-- The three bold counts above are HAND-MAINTAINED. update_test_docs.py's
single-header model can't compute the framework/Eufy/Roborock split, so it WARNs
and skips this doc's headline (the WARN is expected, not a bug). Update them by
hand on adapter test changes — collect-only case counts:
  framework  = tests/integration/test_adapters.py + tests/adapters/test_adapter_contract.py + tests/adapters/test_brand_selection.py
  Eufy       = tests/adapters/eufy/
  Roborock   = tests/adapters/roborock/
tests/adapters/dreame/ is NOT part of this split and must not be added to it — Dreame
is unwired data, and folding it into a "Roborock-adapter tests"-style count would read
as a third shipped brand. -->

Source: `custom_components/eufy_vacuum/adapters/`
Architecture reference: [22 — The Adapter Contract](../../dev/22-adapter-contract.md)

### `test_dock_sdk.py` — optional SDK loading and unknown dock codes

These 12 cases exercise the real `python-roborock` enum and feature classes. Unknown codes that map to the SDK's `unknown` member retain their original integer and disable unconfirmed wash/dry/collect controls; an enum that raises `ValueError` follows the same policy. Known dock features pass through the vendor implementation. A synchronous profile lookup cannot import an unprepared SDK. The registry-selected preparation hook runs imports in an executor, retries after a missing provider package, and leaves other providers alone.

The SDK is a test-only pin in `requirements_test.txt`, so the local Docker image and CI both install it — when it is absent this whole file `importorskip`s away at collection and nothing goes red. The pin matches Home Assistant 2026.10.1; the production manifest continues to defer dependency ownership to the Roborock integration. SDK modules initialize process-lifetime rate-limiters, so the SDK tests import their classes during collection rather than introducing those daemon threads inside an individual Home Assistant test's cleanup boundary.

> **`roborock/test_adapter.py` was the forgotten sibling of that last sentence, until
> 2026-11-08.** It did the same `import roborock` **inside a test body**, so
> `python-roborock`'s two `PyrateLimiter's Leaker` daemon threads appeared during that
> test's own window and HA's `verify_cleanup` failed its TEARDOWN — while the test
> itself passed, which is what made the symptom hard to read. **The full suite hid it
> entirely**: `test_dock_sdk.py` is collected alongside, and its collection-time
> `importorskip` had already warmed the threads, so they predated every snapshot. The
> defect was reachable only in a subset excluding that module
> (`pytest tests/adapters/dreame/ tests/adapters/roborock/test_adapter.py` → "162
> passed, 1 error"), reproduced on a pristine `c9240694` checkout. The import now
> happens at collection in both files, and `[RBSDK-1]` guards it by asserting a
> **module-scope** snapshot of those thread names — the only formulation that can fail,
> since by the time a test body runs an in-body import would already have created
> them. Ablation-verified in both scopes: putting the import back reddens `[RBSDK-1]`
> and brings the teardown error with it. The same test's docstring also claimed the SDK
> was absent from the image and that its `ImportError` branch was the one the suite
> runs; both were false from the moment the pin landed, and are corrected.

### `test_disabled_action_warn_once.py` — advice that repeats is noise with a severity

`resolve_action_entity` can answer **disabled**, which is a toggle in the user's own UI
rather than a fault of ours. Both consumers — `maintenance/manager.py` for consumable
reset buttons and `dock/manager.py` for dock actions — decline to return a disabled
entity and say so in the log, because pressing one is the silent `log_missing` no-op that
`INR2F03P` exists to prevent.

They resolve on **every** upkeep/snapshot rebuild, a few seconds apart, and neither
throttled. A Roborock owner with all four consumable reset buttons disabled got four
identical WARNING lines every few seconds, indefinitely (reported 2026-10-05, with the log
pasted; issue #57 had closed on the same symptom, so this was the half left behind).

`warn_disabled_action_once` is keyed `(vacuum, kind, name)` — bounded by construction,
never per value — and is cleared on a clean resolution, so the user enabling the entity
and later disabling it again is reported afresh. A warn-once that never forgets is
indistinguishable from a warning somebody deleted.

What the tests pin, beyond the count: the throttle is **per component** (four disabled
buttons must yield four warnings, not one — throttling per vacuum would have told that
reporter about one and hidden three), **per vacuum**, and the message names both the
entity and the remedy. [WOD-5] does not depend on the throttle, so it stays green when the
throttle is ablated — which is how you tell the other four are testing the throttle and
not the text.

### `test_entity_resolve.py` — when a DERIVED entity id does not match the install

Adapters build companion entity ids from the vacuum's object_id
(`build_entity_id` → `sensor.{object_id}{suffix}`). That assumes one device per vacuum,
and two shipping cases break it: **Eufy's dock is a separate device**, so its entities are
named for that device (declared `sensor.alfred_total_cleaning_area`, actual
`sensor.dining_room_alfred_total_cleaning_area` — four dock-owned roles unresolved on live
hardware), and **a renamed device or entity** breaks every derived id at once.

Both failed SILENTLY, and a declared-but-absent entity reads as "this brand does not report
that" — the capability leak this project keeps removing. HA 2026.8 removed `battery_level`
from the vacuum entity, deleting the fallback that used to hide a missed battery sensor, so
the derived id is now load-bearing alone (issue #49).

`adapters/entity_resolve.py` rescues an id that FAILS to resolve by searching the vacuum's
own config entry for a domain + suffix match. Nine tests, and most pin what it REFUSES to
do, because the refusals are what make it safe to run on every install:

| id | what it holds |
|---|---|
| `ER-1` | **a working id is never touched** — the property that makes this unable to break a healthy install, asserted even when a same-suffix sibling exists |
| `ER-2` | the live Eufy dock case is rescued, and the remap is REPORTED rather than silently applied |
| `ER-3` | two candidates it cannot disambiguate → leave the declared id; a wrong remap aims the framework at another device and is worse than the absence |
| `ER-4` | ambiguity broken only by the vacuum's own object_id — what makes `<area>_<vacuum>_<suffix>` resolvable |
| `ER-5` | domain must match; a `select.*_active_map` is never served for a declared `sensor.*_active_map` |
| `ER-6` | no config entry → no-op. Config-entry scoping IS the safety boundary, so without it we search nothing |
| `ER-7` | **the documented LIMIT** (issue #46 shape): registered-but-stateless is not a naming problem, so it resolves to nothing and reports no repair |
| `ER-8` | a raising registry degrades to the declared ids — adapter config assembly is never breakable by this |
| `ER-9` | an id not derived from this vacuum has no suffix to match on, so nothing is guessed |

### `test_adapter_isolation.py` — the boundary, not the declarations

`test_adapter_contract.py` asserts what a brand must DECLARE. Nothing asserted
what a brand may TOUCH, so `test_adapter_isolation.py` (5 tests, added
2026-08-07) fences the dependency direction: a brand package translates VA's
meaning into one provider's vocabulary, and that substitutability is only real if
it cannot reach inward.

| id | what it holds |
|---|---|
| `ISO-1` | no brand package imports outside the declared adapter SDK |
| `ISO-2` | the known-leak allowlist is SHRINK-ONLY (same discipline as `mock_allowlist.json`) |
| `ISO-3` | no dynamic import (`importlib` / `__import__` / `sys.modules`) escapes ISO-1's static read |
| `ISO-4` | no runtime reach into a passed-in object's privates — the reach an import graph cannot see |
| `ISO-5` | the detector is exercised against a MANUFACTURED leak (positive + negative), so it cannot silently stop working |

**The SDK is two entries, both adjudicated from measurement:**
`core.capabilities` (BOTH brands call `detect_capabilities` — a facility every
adapter needs is API that happens to live in `core/`) and
`mapping.segment_primitives` (brand-neutral geometry — `rdp`, `polygon_area`,
`mask_iou`; any brand shipping a map IMAGE needs it, and Roborock supplies
segments directly so imports none of it).

**The ledger is now EMPTY.** It held one entry — `profiles.room_profiles` in
`eufy/adapter.py`, because the framework's in-code profile catalog *was* Eufy's.
That import was cut on 2026-08-07: Eufy's vocabulary moved to
`adapters/eufy/room_profiles.py`, core kept only the KEY space, and the framework
fallback was deleted rather than relocated. As predicted, it was a STORED-DATA
change and not a refactor — those values were already written onto existing rooms,
so a one-shot repair ships with it (`rooms/vocabulary_migration.py`).

ISO-5 changed shape with it. It used to assert the real leak was still detected,
and instructed whoever fixed it to delete the ledger entry and ISO-5 together.
Deleting the self-test would have left the detector unexercised — the exact failure
it exists to prevent — so it now manufactures its own leaky and clean modules in a
tmp dir. The instrument stays proven with the ledger empty, which is the state it
should stay in.

### `tests/test_vocabulary_invariant.py` — the standing invariant

**Core owns the KEY space. It does not own any brand's WORDS.** Enforced (14 tests,
added 2026-08-07) by taking two signals together, because either alone is useless:

1. **Syntactic** — the literal is bound to a provider-owned field (`fan_speed`,
   `water_level`, `clean_intensity`): assigned to it, used as its `.get()` default,
   compared against it, or passed as it.
2. **Lexical** — the literal is a value an adapter actually DECLARES, and is not in
   the explicit `CORE_OWNED` set.

Lexical alone reports every `max`, `off` and `low` in the repo — `wash_frequency_bounds["max"]`
is a structural key, `confidence == "low"` is a confidence level, `state == "off"` is an
HA entity state. A gate that screams at those gets ignored. Syntactic alone cannot tell a
canonical key from a brand's word. `VI-3` pins both classes with a positive and a
negative row each, so the detector stays proven while `VI-1` sits green.

`BVL-1` is the second half, added 2026-11-07, and it exists because `VI-1` can only
see a brand WORD in core — not the sites DISAGREEING. `clean_intensity` is part of the
learned-room match key and `learning/manager.py` builds that key in five places. Two
of them defaulted the field to `"standard"` while the other three used `""`, so a room
that never had an intensity was recorded under one bucket and looked up in another —
and `"standard"` is a word Eufy itself RETIRED, which `rooms/vocabulary_migration.py`
exists to repair, so core was re-injecting what the migration removes. All five now
default to `""`: core holds no brand word for an absent setting ([`IN40W49E`](../../dev/00b-invariants.md)).

The same defect had already been fixed once, in a renderer —
`profiles/room_profiles.py::default_setting_values` records it: `"standard"` was
*"right for two brands by luck and wrong for Eufy"*. Presentation was repaired and
learning was missed, which is `f/eufy_ism_leak_layers` with the layers reversed.

> **Why NOT the brand's declared default**, which was the other candidate and the one
> that sounds more correct. `default_setting_values` would supply it (eufy declares
> `Quick`), but these sites are MATCH KEYS and the reader has no room data to derive
> from, so it answers `""`. Writing a declared value while reading `""` buckets a room
> that never had an intensity together with rooms explicitly set to the brand's
> default — a permanent mismatch penalty manufactured out of a fix. `BVL-1`'s own
> ablation confirms it: hardcoding eufy's declared `Quick` at one site reddens both
> `VI-1` and `BVL-1`.

`CORE_OWNED` is the load-bearing declaration: the written statement of what the framework
owns (the canonical water estimator keys `off/low/medium/high`, the canonical
`clean_mode` and `path_type` values, and `""` for "nobody said"). Growing it to silence
a finding is how the gate dies.

**Case-sensitive on purpose.** Folding case would merge Eufy's `"Off"` with the canonical
`"off"`, so `"Off"` would be swallowed by `CORE_OWNED` and the five real leaks in
`apply_capability_gate` and `_protected_room_config` would be invisible. `"Off"` vs
`"off"` IS the bug. The accepted blind spot is RETIRED values, which no adapter declares —
that is the store migration's job.

It found seven leaks on its first run, after the manual sweep was thought complete:
`.get(field, "Max"/"Off"/"Quick")` defaults in `overwrite_room_profile_from_room`,
`_snapshot_room_for_run_profile`, and the learning ingest path (whose default was
`"standard"` — a Eufy word Eufy itself had retired). The ledger is empty.

**A second gate was measured and rejected.** "Every test-registered adapter must declare
a catalog" sounds like the natural sibling, but 208 registrations across 51 test files
declare none and the suite is green — so those tests provably never resolve a room, and
the rule is not required. Shipping it would have meant a 208-row allowlist or 51 files of
churn. What actually covers the hazard is the runtime failure: resolution raises
`UndeclaredProfileCatalogError` naming the missing declaration, so a test that reaches it
cannot get a quietly wrong answer.

### `tests/unit/test_i18n_alias_vocab_keys.py` — an accepted spelling needs a card key

The axis above is also where an adapter's **display-slug aliases** come from, and they
have a card-side obligation that nothing used to enforce. A room's stored setting is an
un-normalized display string, and the surfaces that render it untouched (the rooms-view
chips, the standalone room card, the map selection bar's per-room summary, the
external-run summary) slug *that* — so `vocab.clean_mode.vacuum_mop` does not cover a
room whose stored value is `"Vacuum and mop"`. Nine spellings across the four Eufy alias
maps had no key when this landed, which is why sinks that **do** call `tVocab` still read
English for them: a correct call against a missing key falls back silently to the
backend's word (4 tests + 4 parametrized, added 2026-10-27).

| case | what it holds |
|---|---|
| `AVK-1` | every statically declared alias spelling has a `vocab.<field>.<slug>` key |
| `AVK-2` | the mutation control — the same function, over a map with one invented spelling, names it |
| `AVK-3` | **scoped to `clean_mode`, and the scope is the finding.** A first draft asserted it for every axis and went red correctly: `clean_intensity.standard` reads "Standard" while its canonical target `narrow` reads "Narrow". That is deliberate — an alias spelling on the suction / water / path axes *is* the brand's own app word, and replacing it with core's internal key word would show "Narrow" to an owner whose app says "Standard". `clean_mode` is the exception because all three brands name that axis with one phrase, so its aliases are loose spellings of one word rather than competing app terms. |
| `AVK-4` | the Roborock exemption is anchored to the code that causes it — `build_positional_aliases` derives its spellings from the device's live option list, so they are not knowable ahead of time and cannot be pre-keyed. Localizing those is part of the per-install vocabulary question in `SCOPE-71`, not of this contract. |

The slug rule is **mirrored** from `src/cards/_shared.js::vocab`, not imported — the owner
is JavaScript. A divergence there aims this gate at keys the card never looks up, which is
why the mirror is one function with the source named in its docstring.

### `tests/adapters/eufy/test_intensity_wire_mapping.py` — three chips, three densities

VA declares three cleaning intensities. The device has three. They were not reaching
each other (5 tests, added 2026-08-08).

robovac_mqtt resolves the payload string through `CLEAN_EXTENT_MAP`, where
`"narrow"` and `"deep"` are the SAME value — `deep` is a legacy alias:

| payload word | CleanExtent | Eufy app |
|---|---|---|
| `quick` / `fast` | QUICK (2) | Low (widest spacing) |
| `normal` / `standard` | NORMAL (0) | Medium |
| `narrow` / `deep` | NARROW (1) | High (densest) |

Sending VA's own names unmapped collapsed `Narrow` and `Deep` onto NARROW and left
NORMAL unreachable — three chips in the card, two pass densities on the floor, and
the middle one impossible to select. The fix is a `dispatch.room_fields` value_map
(`{"Narrow": "normal", "Deep": "narrow"}`), so VA's names are unchanged and no stored
room moves.

**Verified against hardware**, not inferred: the Eufy app was set to each intensity
and `select.<vac>_cleaning_intensity` read back, cross-checked against the protobuf
enum (`clean_param_pb2`: NORMAL=0, NARROW=1, QUICK=2). Note the enum is an ARBITRARY
ENUM, not an ordinal — 0 is the middle setting — so nothing may interpolate on it.
That is also why `CIW-3` pins the declared option ORDER: fastest→slowest exists only
in the declaration and cannot be recovered from the device.

`CIW-1b` is the mutation control — with the value_map removed, two of the three
collide — because `CIW-1` would otherwise pass if the map were a silent no-op. The
card carries the matching half in `_profileIntensityToEditorIntensity`; both halves
must agree or the editor shows a density the wire does not send.

### `test_declaration_contract.py` — the declaration, in all three of its states

`test_adapter_isolation.py` fences what a brand may TOUCH. This one (12 tests,
added 2026-08-07) pins what happens when a brand DECLARES — or fails to.

| id | state | what it holds |
|---|---|---|
| `DC-1` | declared + populated | every shipped brand's real config resolves ITS words |
| `DC-1b` | — | Eufy and Roborock actually DIFFER, the premise every relational test rests on |
| `DC-2` | not declared | resolution RAISES, naming the missing declaration |
| `DC-2b` | not declared | negative control: the catalog is empty, not another brand's |
| `DC-2c` | not declared | registration rejects it, so the failure lands on the porter |
| `DC-3` | declared empty | a declared-empty key is carried, not treated as absent |
| `DC-3b` | partially declared | undeclared keys resolve EMPTY; the block is the gate, not each key |
| `DC-3c` | wholly empty block | rejected — a brand with no vocabulary can resolve nothing |
| `DC-4` | — | the same validator that rejects the bad ACCEPTS every shipped brand |
| `DC-5` | — | end to end: the REGISTERED config is what resolution actually reads |
| `DC-20` | — | `BRAND_BLOCKS` covers the shipped `BRAND_REGISTRARS`, both directions |
| `DC-21` | — | `ADAPTER_BUILDERS` covers it too — a brand with no builder never runs this suite |

`DC-20`/`DC-21` fence replica set [`RN7WK2CX`](../../dev/00c-replicas.md), and they
exist because the failure mode is **silence, not failure**: a brand missing from either
table does not break anything, it just never appears in a parameterization. Measured —
`dreame` shipped in `BRAND_REGISTRARS` on 2026-09-13 and `BRAND_BLOCKS` never got its
row, so for eight weeks the vocabulary suite and the `brand` fixture ran over two of
three brands while their docstrings said every shipped one, and the brand-leak gate's
corpus — built from the same two blocks — could not report a Dreame word at all. The
row landed 2026-11-07, and adding it exposed a second copy: this suite's own
`_no_water` helper duplicated `profiles/room_profiles.py::no_water_value` and raised
`KeyError` for a brand that declares no carpet water default, where the shipped
function correctly yields `""`. Dreame's water ladder has no `off` rung, so it is that
brand. Twelve cases failed the instant the row existed; the copy was the bug.

### `roborock/test_live_water_ladder.py` — the mop ladder read off the device (#71)

11 test functions, added 2026-10-19. `WATER_LEVEL_OPTIONS` was a transcript of ONE
machine — the maintainer's S6, `off/low/medium/high` — declared for every Roborock since.
A Saros 10 owner's own Developer Tools output settled it: that model's
`select.<obj>_mop_intensity` offers `off / mild / standard / intense / extreme /
smart_mode / custom`, and **not one of `low`, `medium`, `high` exists there.** The global
water pre-call was pushing three words the mop rejects; water is a best-effort entry
("caught + logged, never aborts"), so it failed into the log on every run while the robot
kept whatever the vendor app last set. A control the owner CAN see and change that
silently does nothing — the mirror of #66's route, which they could not see and we set
anyway.

The adapter already declared that select as a ROLE (so a localized install is rescued)
and already read a live entity at registration for the route axis. The only missing move
was asking for `options` instead of `state`.

**`options` is an ATTRIBUTE, not a STATE, and that is the load-bearing difference.**
`_route_usable` demands a usable VALUE because entity PRESENCE is worthless on this brand
— the select exists on every V1 Roborock. But `options` is published with the entity
regardless of whether it ever reports, so the read succeeds on an observe-only mop too:
`select.ivy_mop_intensity` sits at `unknown` and still carries its four rungs. `LW-9`
pins that, because reusing the route gate's test here would read nothing on exactly the
hardware that proved the route gate necessary.

| id | what it holds |
| --- | --- |
| `LW-1` | the Saros ladder, from the reporter's own pasted tokens, becomes the picker AND the rank — and `low`/`medium`/`high` are gone |
| `LW-2` | **the no-regression guard** — a device publishing our declared ladder comes through byte-identical |
| `LW-3`/`LW-4`/`LW-5` | every empty read falls back to the DECLARATION, never to `[]` — §E1: an empty list *disables* the guard (`if valid and ...`) instead of tightening it, and the cold-boot window before the provider sets up is the common case |
| `LW-6` | **picker and rank are one sequence**, asserted over every shape the read can produce. They are a replica pair and the failure is silent: a picker value the rank does not know makes `_any_rankable` False, so the safest-water pre-call pushes *nothing* and a batch with a dry room proceeds on whatever the app set — #51's wet-mop, reopened |
| `LW-7` | an unknown token is humanised, not left raw |
| `LW-8` | a declared label beats humanisation (`deep_plus` → "Deep+", not "Deep Plus") |
| `LW-9` | an `unknown`/`unavailable` state still yields options — the ivy case |
| `LW-10` | blanks and duplicates from the device are dropped |

**Two tokens are deliberately excluded from both lists.** `smart_mode` ("the robot
decides") and `custom` ("whatever the app last set") are real device options and real
answers, but not positions on a ladder. Excluding them keeps picker and rank identical —
one derivation, nothing to drift.

**The open-set problem, and why this ships without 18 language packs.** The set of words
a Roborock can emit is not knowable: a firmware update adds a rung and a table cannot
have anticipated it. So the backend supplies a `label` per option, humanised from the
token where no declared word exists, and the card resolves `vocab.<field>.<value>` first
and falls back to that label (`src/i18n/en.js`:120 states the contract; the three
`RN6F7RW6` members all implement it identically). An untranslated rung degrades to
readable English instead of breaking, and `check:i18n` stays green because no new static
key template is added.

⚠ **DO NOT REUSE THIS DERIVATION FOR FAN.** Rank order is read order, which is only safe
because water is published ascending on both machines we can see. Fan is not: the Saros
publishes `quiet, balanced, turbo, max, max_plus, off_raise_main_brush, …`, where the
WEAKEST rung is listed sixth. Rank fan by read order and `off_raise_main_brush` becomes
the strongest suction. Roborock declares no fan pre-call today, so that is a trap set for
whoever adds one rather than a live bug.

Nine of the eleven claims are ablation-verified. The two that are not are `LW-2`, which
correctly cannot detect a label ablation (humanising `off/low/medium/high` yields the
identical declared labels, so nothing changes for that device), and `LW-8`, which is the
test that covers it.

### `roborock/test_vocabulary_catchup.py` — existing is not published (#71)

5 test functions, added 2026-10-19. **This is the defect the live-differential check
caught and the whole green suite could not.**

`async_at_started` guarantees every integration has SET UP — enough to ask whether an
entity exists, which is what the post-start capability re-detection needs. An adapter
reading an entity's ATTRIBUTES needs something later: the provider's coordinator has to
have POLLED. Measured on the maintainer's box, 150 seconds after a restart, the
registered adapter still held the DECLARED suction list while `vacuum.ivy` was plainly
publishing `fan_speed_list`; a config-entry reload immediately produced the device's
own lists, and ivy's real route ladder turned out to be two rungs where we were
offering three.

So on every restart a user got the old vocabulary. Issue #71's Saros 10 owner would
have seen the fix silently not apply, with `low`/`medium`/`high` still pushed at a mop
that rejects them. **Every unit test passed throughout** — they set the states before
calling register, which is exactly the ordering a real boot does not give you.

The adapter now NAMES the entities whose read came back empty (`_pending_live_reads`)
and core watches them, re-registering on the first publish and dropping each vacuum as
it completes. Deliberately not a timer: "how long does a coordinator take" has no right
answer, and the state machine already says when the data arrived.

| id | what it holds |
| --- | --- |
| `VCU-1` | the cold-boot shape — nothing published, every unread source is named |
| `VCU-2` | **the no-wait guard** — a fully published device names nothing, so no listener is armed and a healthy install pays nothing |
| `VCU-3` | a partial read names only what is still missing (coordinators do not all land at once, so this is the common case) |
| `VCU-4` | the water select is not awaited on a mopless model — there is no water vocabulary to wait for, so the listener would never disarm |
| `VCU-5` | the names are full entity ids, not object ids — core hands them to `async_track_state_change_event`, and a wrong id waits forever and looks exactly like a device that never publishes |

All four behavioural ablations redden it. `VCU-5` cannot detect "nothing is named" —
its loop body never runs — which is `VCU-1`'s job; the ablation report saying so is the
check working, not a gap.

`tests/integration/test_vocabulary_catchup_wiring.py` covers the same work END TO END,
and it earned its place: it found a bug the adapter-level tests could not see.

| id | what it holds |
| --- | --- |
| `VCW-1` | a provider that publishes LATE still gets its vocabulary read — the listener backstop re-registers on the publish |
| `VCW-2` | **the room entity's ATTRIBUTES change too**, not just the config |
| `VCW-3` | a provider ready on time arms nothing and changes nothing |

**`VCW-2` found a real defect in the first version of the fix.** The refresh was placed
in the "nothing left pending" branch, which looks tidy and strands the common case: a
device that publishes its suction list but never publishes a mop select — a vacuum-only
model — would get a corrected config and a card showing the fallback *forever*, because
the pending set never empties. Every other test passed. The refresh now follows any
vocabulary CHANGE, which is the same rule the post-start re-detection uses.

Two smaller things that test taught, both recorded in it: brand resolution keys on
which INTEGRATION owns the vacuum entity, not on the device record, so patching the
device alone silently exercises the Eufy adapter; and `VCW-2` asserts rather than skips
when no room switch exists, because it is the only surface watching that hop and a skip
would make it worthless.

### `roborock/test_live_fan_ladder.py` — suction read off the vacuum entity (#71)

6 test functions, added 2026-10-19. The third complaint on #71 was *"there is a MAX+
suction power mode beyond MAX. MAX+ is currently missing."* It was missing because
`FAN_SPEED_OPTIONS` is a transcript of the maintainer's S6 — which has `gentle` and no
`max_plus` — declared for every Roborock. The reporter's Saros publishes `quiet,
balanced, turbo, max, max_plus, off_raise_main_brush, smart_mode, custom`: neither
`gentle` nor our spelling of that slot. Both halves of the mismatch disappear by reading
`vacuum.<obj>`'s own `fan_speed_list`.

**This is the EASY half of the live-vocabulary work, and the reason is structural.**
`fan_speed` is a `per_room_live_settings` entry filtered by `options_key`, not a ranked
global pre-call. Nothing orders it, so the trap that makes read-order-as-rank unsafe
simply does not apply here — the order is chip display order, and the device's own order
is the one the owner already sees in the Roborock integration's fan menu, which is the
surface they compared ours against.

| id | what it holds |
| --- | --- |
| `FLR-1` | the Saros list becomes the picker — `max_plus` in, `gentle` out, non-rungs dropped |
| `FLR-2` | the no-regression guard: a device publishing our declared five yields those five |
| `FLR-3` | no entity / no attribute / only non-rungs → the declared list, never `[]` |
| `FLR-4` | the device's own ORDER is preserved, not sorted — it is also the only honest order, since we cannot know where an unseen rung belongs |
| `FLR-5` | **no rank is introduced** — asserted as an ABSENCE, because adding one is the single way to get this axis wrong |
| `FLR-6` | an unknown rung is humanised; a declared label still wins |

**`FLR-5` is the one to read.** `off_raise_main_brush` is the weakest rung and the device
lists it *sixth*. Any max-wins or safest-wins resolve built on read order would make the
raised brush the strongest suction. Fan is safe only because it has no rank at all, so
the test asserts the absence — that is the property a future change would quietly take
away while every other test stayed green.

All six are ablation-verified, including adding a rank to the per-room entry.

### `roborock/test_roborock_upkeep_keys.py` — Roborock on the shared regime → key guide

7 test functions, added 2026-09-12 with the Roborock port. Replaces the three authored guide
families and the hand-assigned maintenance TIER that chose between them.

| id | what it holds |
| --- | --- |
| RUK-1 | 41 models, not one new authored key — its whole washing-cloth line emits Dreame's SimuMop card sets, because `SimuMop` normalises to `cloth` at generation. |
| RUK-2 | declared ↔ emitted components, both directions. |
| RUK-3 | **seven components, not fourteen** — and the eight that went are Chris's rulings, named. |
| RUK-4 | every model is both named and routed; 41 either way. |
| RUK-5 | **the walk-back, pinned.** The old tier was wrong on 8 of 41 in BOTH directions, and two of the assertions this replaced were holding the defect in place. |
| RUK-6 | **`RNARRS0S` rehoused.** Twin flat cloths are `cloth`/`pad`, never `roller`. Was a replica anchor across two files the port deleted; it is a measurement now, and one that can go red. See `docs/dev/00c-replicas.md`. |
| RUK-7 | 41 models → 6 regimes → 4 card sets. |

### `eufy/test_eufy_upkeep_keys.py` — Eufy on the shared regime → key guide

6 test functions, added 2026-09-12 with the Eufy port. It **replaces**
`eufy/test_upkeep_guides_i18n.py`, which checked five authored families across seventeen
language packs; there are no families and no Eufy-authored prose any more, so what is worth
asserting changed with them.

| id | what it holds |
| --- | --- |
| EUK-1 | **Eufy adds no key Dreame has not authored.** The claim the whole port rests on, and the one that can go quietly wrong: an unauthored key renders as its own name, and every count in EUK-5 would still be green. |
| EUK-2 | declared components ↔ emitted components, both directions. An emitted-but-undeclared panel gets no entity binding; a declared-but-unemitted one can never render. Neither raises. |
| EUK-3 | the canonical ids are used (`mop`, `omnidirectional_wheel`), with Eufy's word kept as `label_key` — and `mop` deliberately carries none, because "Mopping Cloth" is wrong on its five roller and pad models. |
| EUK-4 | the family system is *gone* — no `UPKEEP_GUIDE_LIBRARY`, no `UPKEEP_GUIDE_TRANSLATIONS`, no family maps. A leftover import would keep it alive unnoticed. |
| EUK-5 | 13 models → 6 regimes → 4 card sets. |
| EUK-6 | the vacuum-only machines carry no mop panel, no tray and no 2-in-1 water clause. **Eufy is the only brand whose data can hold this case** — Dreame ships no mop-less model. |

### `core/test_maintenance_component_rename_migration.py` — the interval carry-over

9 test functions, added 2026-09-12. Maintenance state is keyed by component id, so renaming one
orphans what it held. `reset_at` self-heals on the next reset; `interval_hours` does not — it is
a preference, nothing prompts its restoration, and the old value lives only in `.storage`.

| id | what it holds |
| --- | --- |
| MCR-1 | a custom interval moves to the new key; the legacy row is left in place, inert. |
| MCR-2 | reset timestamps are **not** carried — faking them forward claims a service under a name that did not exist. |
| MCR-3 | a value already on the new key is never overwritten; it is the user's later choice. |
| MCR-4 | **a rename CHAIN takes the most recently reset row.** Pinned from a real defect: `swivel_wheel` → `caster_wheel` → `omnidirectional_wheel` left two dead rows aimed at one destination, and applying both in order let a 65h value dead since May overwrite a 30h one set an hour earlier. |
| MCR-5 | the tie-break from the other side — a row with no `reset_at` is the weaker claim. |
| MCR-6 | a reset-only legacy row carries no preference, so there is nothing to rescue. |
| MCR-7 | idempotent; the second call is a no-op, not a re-apply. |
| MCR-8 | malformed storage is survived, not raised — this runs during setup on every install. |
| MCR-9 | **the table holds only 1:1 renames.** An absorption has no single destination (two sources, one panel), so those drop to default by design. A future edit adding one is what this catches. |

**[MSK] — the THIRD store, found on a clone and not by the suite (2026-09-14).** A component id
keys three things: the interval in `data["maintenance"]`, the entity in HA's registry, and the
RESOLVED SOURCE in `data["capabilities"][vacuum]["maintenance_sources"]`. The platforms read the
third with `refresh=False`, so after a rename they look up `main_brush` in a dict still keyed
`rolling_brush`, get None, and create **no entity at all**. Measured on a real upgrade from
v2.1.0: three components had no entities until a SECOND restart happened to refresh the snapshot,
while the registry rename and the interval carry had both worked perfectly.
`migrate_maintenance_source_keys` runs before `async_forward_entry_setups` for the same reason
the registry pass does, and deliberately carries NO latch — it is a pure key-rename over a
derived cache, and a latch would make it un-runnable on exactly the boxes that later need it.

| id | what it holds |
| --- | --- |
| MSK-1 | cached source keys are re-keyed. Red if only storage is migrated — which is what shipped. |
| MSK-2 | a canonical key already present wins; the legacy key still goes. |
| MSK-3 | retired components are dropped from the cache. |
| MSK-4 | idempotent WITHOUT a latch — a second pass must plan nothing, not merely be harmless. |
| MSK-5 | malformed snapshots are survived; this runs during setup on every install. |

⚠ **`MIGRATION_KEY` must be bumped whenever a row is added** (now `_v2`, 2026-09-14). It is a
one-shot latch, so a row added under a key already `True` can never run on a box that has
migrated — the author's included, which is where it would be verified. That is not theoretical:
`washboard` → `cleaning_tray` was renamed on 2026-09-12 (f9cfed39) and no row was ever added, so
the miss sat undetected behind a latched `_v1`. Re-running is safe by construction — the planner
skips any destination that already holds a value. The same commit added `RETIRED_COMPONENTS`,
the outright-removals list that has no destination and so cannot live in this table; MER-10
guards it.

### `integration/test_maintenance_entity_registry_migration.py` — the entity half of the same rename

10 test functions, added 2026-09-14. The sibling above carries the user's INTERVAL; this carries
the ENTITY. A component id is half of a `unique_id`
(`vacuum_alfred_swivel_wheel_maintenance_interval`), so the same rename that orphans a storage
row also orphans three registry rows — a reset button, an interval number and a remaining
sensor.

**Why nine green tests next door could not see it.** MCR imports nothing from `homeassistant`:
it builds a dict and asserts on a dict. That purity is why it is fast, and exactly why it was
blind here — there was no registry in the room to be wrong. Measured cost on a real box: 15
orphan rows sitting permanently `unavailable`, 3 frozen long-term-statistics series, and three
`_2` entity ids, because Eufy keeps its own display word via `label_key` so the friendly names
collide exactly. These tests drive a real registry; nothing is mocked.

**The ordering is the fix.** The pass runs before `async_forward_entry_setups`, because the
platforms are what mint the canonical rows. First, and the legacy row is still the only holder
of that `unique_id`, so the rename keeps the entity id, the history and every automation bound
to it. After, and every component collides — which is precisely how the author's box reached
fifteen-for-fifteen.

| id | what it holds |
| --- | --- |
| MER-1 | a free destination is **renamed in place** — same entity id, so history and automations survive. Red if the registry is left untouched. |
| MER-2 | a taken destination does not raise. `async_update_entity` raises `ValueError` on a used `unique_id`, and mid-loop that leaves a box half-migrated — worse than either end state. |
| MER-3 | two legacy ids naming one destination: exactly one wins (table order), the other is pruned. The wheel really did go `swivel_wheel` → `caster_wheel` → canonical. |
| MER-4 | all three platforms move together. A number-only pass leaves two thirds of the orphans behind while looking like it worked. |
| MER-5 | idempotent via its own latch. |
| MER-6 | **that latch is independent of MCR's.** Every box that has run this version already has `maintenance_component_renames_*` set, so a pass sharing it could never run there — including the author's, the one place it would be verified. |
| MER-7 | an unrenamed component is untouched — red if matching goes substring or prefix. |
| MER-8 | the planner writes nothing, so a release's effect on real users is reviewable first. |
| MER-9 | **a RETIRED component is pruned.** Of the eight the Roborock 14→7 cut removed, only `cleaning_brush` and `strainer` ever minted entities — both declared a suffix a wash-dock machine publishes. Absorptions have no destination, so the rename table excludes them and they would otherwise stay `unavailable` forever. No machine in this house can show it. |
| MER-10 | **the safety guard, and the only way this pass could destroy a live entity.** `RETIRED_COMPONENTS` drives an unconditional delete; if an id on it reappears in a brand catalog, the migration would delete entities the platforms recreate every startup. Also refuses an id that is both renamed and retired, where loop order alone would decide. |

Ablation, recorded: removing the collision guard reddens MER-2 and MER-3; reusing MCR's latch key
reddens MER-6; migrating only the number platform reddens MER-4; ignoring `RETIRED_COMPONENTS`
reddens MER-9; re-declaring `dustbin` in the Roborock catalog reddens MER-10.

### `test_adapter_contract.py::test_the_projection_drops_no_catalog_field`

**A brand's projection is an EXPLICIT FIELD LIST, so a catalog key it does not name is silently
dropped between the adapter and core.** The declaration stays valid, the schema keeps accepting
it, and the consumer simply never sees it.

THIS SHIPPED. `proxy_for` was restored to Eufy's catalog and to `ADAPTER_CONFIG_SCHEMA`
(02a229ca) but not to `eufy/adapter.py`'s projection, so `_detect_maintenance_sources` read
`meta.get("proxy_for")` as None, the borrow never happened, and `omnidirectional_wheel` had NO
source — the one component of seven still `unavailable` after a live upgrade on a clean box.

Why 4903 green tests could not see it: `test_core_capabilities` hands
`_detect_maintenance_sources` synthetic component dicts that already carry `proxy_for`, so they
never travel through the projection. The fixture agreed with the CALLER rather than with what the
system produces (`f/test_discipline`). This test runs the other way round — it derives its
expectation from the real catalog and checks the real config, once per shipped brand.

Ablation: deleting the `proxy_for` line from the projection reddens it with
`['omnidirectional_wheel.proxy_for']`, which is the exact shipped defect.

### `test_model_gate.py` — does THIS MODEL have this component?

8 test functions / 10 collected cases, added 2026-09-14. Covers the shared predicate in
`adapters/upkeep_keys.py` that the three entity platforms and the card's upkeep snapshot all
call. Contract written up as [doc 41 §1b](../../dev/41-maintenance-and-the-dock.md).

| id | what it holds |
| --- | --- |
| MGT-1 | **the core five are universal** — measured as the intersection of all 754 models' emitted sets, not read off a catalog. Red if any regime omits one, which would mean the gate could strip a filter card off a model we recognise. |
| MGT-2 | **a resolved regime gates a SENSOR-BACKED component.** The contract change. The old gate exempted anything declaring a `sensor_suffix` and defended that as keeping Eufy unaffected — but Eufy's tray declares one, so the gate could never reach it, and the exemption rested on a premise measured false (`robovac_mqtt` gates on protocol, not hardware). Pins all 8 tray-less Eufy models. |
| MGT-3 | routed but THIS model unresolved → guide-only drops, own-counter stands. Red if unresolved returns an empty set, which would also take the filter and brushes. |
| MGT-4 | **an adapter with no regime table keeps everything — THE THIRD STATE.** Not a defensive case: collapsing it into "unresolved" reddened six `test_maintenance_manager` cases on this gate's first run. |
| MGT-5 | no model falls below the core five, per brand, per model. |
| MGT-6 | the two live phantoms pinned by model id — `roborock.vacuum.s6` (a tray it has no station for) and the 685 non-Matrix10 Dreames (`mop_pad_holders_dock`). |

Ablation, recorded: restoring the `sensor_suffix` exemption reddens MGT-2; collapsing
`NOT_REGIME_ROUTED` into `REGIME_UNRESOLVED` reddens 7 cases across MGT-4 and
`test_maintenance_manager`; returning an empty frozenset for an unresolved model reddens MGT-3
and `test_an_unresolved_model_gates_the_cleanables_closed`.

### `dreame/test_dreame_upkeep_keys.py` — the only gate on an UNWIRED adapter

9 test functions / 48 collected cases (DUK-3, DUK-6 and DUK-9 fan out over the 15
regimes), added 2026-09-11 with the key system. Every other suite on this page reaches an
adapter through its `BRAND_REGISTRARS` row. The Dreame adapter has no such row —
deliberately, since that row *is* the release — so none of them touch it, and without
this file the whole guide system could be emptied, renamed, or quietly disconnected from
the card with the suite staying green throughout.

It replaces `test_dreame_upkeep_guides.py` (below), which tested the retired family
system and was deleted with it.

| id | what it holds |
|---|---|
| `DUK-1` | there is NO `BRAND_REGISTRARS` row for Dreame — the release switch, still off (inherited from `DUG-1`) |
| `DUK-2` | every model routes to a regime the key library actually holds — an unrouted regime is a KeyError waiting for the switch (`DUG-8` re-expressed) |
| `DUK-3` | every component in every regime has a step, and no step or note is an empty string |
| `DUK-4` | every component the key library emits has a `maintenance_components` row |
| `DUK-5` | every declared component is reachable — in some regime, or sensor-backed |
| `DUK-6` | the regime gates hardware: no washboard on a dockless robot, no track mop on a pad robot, exactly one mop panel per model (`DUG-5` re-expressed, now derived) |
| `DUK-7` | every key the backend can emit is in the shipped English pack, and nothing ships that nothing emits |
| `DUK-8` | the collapse holds — 700 models, 15 regimes, 7 distinct cards, 51 keys |
| `DUK-9` | every panel's steps END on a closer, exactly one |

**`DUK-4`, `DUK-5` and `DUK-7` are the reason this file exists, and they guard a failure
mode the old system did not have.** Prose travelled with its own routing key, so a family
guide was either present or absent. A key guide is a JOIN across three tables — regimes,
key lists, and the `maintenance_components` rows that give a guide somewhere to render —
and any two of them can drift while each stays internally valid and fully populated.
`DUK-4` is written from a real miss: the emitter named a panel `dust_bin_and_filter` while
the card's component was `filter`, so a correct, translated guide resolved to nothing on a
card that looked entirely healthy. Nothing in the guide library could see it, because
nothing in the guide library was wrong.

`DUK-6` replaces thirteen per-family assertions with one derived rule, which is the whole
argument for the regime system in miniature: the old `DUG-5` had to name each absent part
on each family by hand, so it only ever covered the families someone thought to list.

`DUK-8` is a tripwire, not a law. If a regime change legitimately splits or merges a card,
the number is meant to be updated deliberately — the point is that it cannot drift
silently, because the 700-to-7 collapse is the entire justification for replacing ~280
authored families with 51 keys.

### `dreame/test_dreame_upkeep_guides.py` + `_i18n.py` — ⛔ DELETED 2026-09-11

Both are gone, with the ~280-family Dreame guide library and its 17 language packs that they
guarded. Retrievable from git history; nothing in the tree routes through that system.

They held `DUG-1`..`DUG-13` and `DI18N-1`..`DI18N-5`. Three of those questions were real
independently of the family model and were carried over rather than dropped: the release
switch (`DUG-1` → `DUK-1`), routing that resolves (`DUG-8` → `DUK-2`), and absent hardware
getting no guide (`DUG-5` → `DUK-6`, now derived from the regime instead of asserted per
family). The other ten were assertions ABOUT families — which two share a body, which
eleven of thirteen components match — and have no referent once families are gone.

Two lessons from them are worth keeping, because both are about testing, not about Dreame:

* **`DUG-4` guarded a defect the data had already shipped**: a shared `_BASE` was factored
  out of several families because their component NAMES lined up, which put X60 prose on
  five other platforms. Presence of a part and sameness of its PROCEDURE are different
  claims, and only the second was ever checked.
* **`DI18N-1..5` were rewritten once when the premise under them changed.** They asserted
  strict structural equality with English, which was correct while the packs were translated
  FROM English and became wrong the moment they were lifted from Dreame's own per-language
  manuals — vendors localize structure, not only words, and only 8.6% of lifted vendor cells
  matched the English shape. "Fixing" the failures would have meant overwriting real manual
  content with an English skeleton. A test can be correct and still be resting on a premise
  that has expired underneath it.

Provenance scoring lived outside the suite in `scripts/verify_dreame_guide_provenance.py`
(bigram overlap against the source manual — it could catch an invented step at ~8% and a
swapped part at ~47%, but never a single swapped word at ~93%). Deleted with the library it
scored. The key system's equivalent is authored and checked in the fixture, outside git.

### `dreame/test_dreame_adapter_config.py` — the native current-room wires

3 tests (`DAC-*`). Dreame publishes the live room on `sensor.<id>_current_room`
(`active_cleaning_target`), and THREE subsystems must ride that one signal: the map
current-room highlight, the pose sampler's attribution, and the room rollover that writes
`completed_rooms`. Each was a declared-but-unwired gap at some point — the same shape as
the map-highlight fix one layer over. `DAC-1` pins `live_transition.native_transition_source:
True` so the rollover follows the native signal instead of Eufy's `counter_plateau` (which,
on Dreame, mis-attributed the whole run's area to the first room and dropped the LAST room —
"Not reached", observed live twice). `DAC-2` pins `room_attribution.source:
native_current_room`. `DAC-3` asserts both together — a brand that declares the native
attribution source but not the native rollover splits its signal across subsystems, the exact
drift these guard.

### `dreame/test_dreame_model_catalog.py` — the lowest-covered file in the package

14 tests (`DMC-*`), added 2026-11-08. `adapters/dreame/model_catalog.py` measured
**76.19%**, the lowest of 157 files carrying ten or more units and an outlier by 7.5
points — but the shape of the gap mattered more than the number. The only path any
test exercised was (3), the conservative fallback for a model the catalog has never
heard of. **Both paths that decide real behaviour had never executed**: the
hardware-verified override, and the regime-derived profile covering all 700 catalogued
models. The Roborock catalog's twin `profile_for_model` is tested for its override
path, so this was the forgotten sibling. Now **100%**.

| id | what it holds |
|---|---|
| `DMC-1` | the hardware-verified override wins over the regime, and returns the AUTHORED capability set |
| `DMC-2` | `display_name` is injected from `DREAME_MODEL_NAMES`, never stored per-profile |
| `DMC-3` | a catalogued model's `family` is its measured regime composite, not `generic` |
| `DMC-4` | `charge_only` FAILS CLOSED — **and a wash tier does not** |
| `DMC-5` | `auto_empty` reduces the station to collect-only |
| `DMC-6` | an uncatalogued model, `""` and `None` get the conservative baseline |
| `DMC-7` | `has_path_control` fails CLOSED for every one of the 700 catalogued models |
| `DMC-8` | every authored override has a real display name |

**`DMC-1` asserts the fields that DIFFER from the default, and that is the whole
design.** `dreame.vacuum.r2469a` — the maintainer's own L10s Ultra Gen 2 — is in the
regime table too (the module asserts that at import), so it would resolve perfectly
happily down path (2). `has_path_control` and `supports_zone_clean` are True in the
override and False in `DEFAULT_PROFILE`, and a regime-derived profile inherits both
from the default, so those two are what distinguish "took path (1)" from "took path (2)
or (3)". Asserting `has_mop` would pass on all three.

**`DMC-4`'s wash-tier half is not decoration.** `_TIER_STATION.get(dock_tier, {})`
means an *empty* `_TIER_STATION` yields the default for every tier, so "a wash tier has
a station" passes against a table that was emptied — only the contrast with
`charge_only` shows the table is consulted at all. 551 of the 700 models sit on a tier
the table does not name, which is why this is easy to get wrong.

**`DMC-8` closes a drift the module's own import-time assert cannot see.** That assert
checks `MODEL_PROFILES ⊆ DREAME_MODEL_REGIMES`, but `display_name` is single-sourced
from `DREAME_MODEL_NAMES`, which nothing checked. A verified model missing from the
name table does not raise — it silently renders as the generic `"Dreame"`, which for
the one authored entry means the maintainer's own vacuum shows up unnamed on his card.

No expected value here is computed the way the source computes it: the regime
composites are hand-written literals, because building them with the source's own
`"%s|%s|%s"` would make the test agree by construction and survive the separator
changing.

### `eufy/adapter.py` — 84.29% → 91.43%, and an honest ceiling below 95%

Only 60 of its 1123 lines are statements — the file is mostly one declaration dict —
so its nine uncovered units sat in three small clusters. **Five were testable, four
are unreachable by construction**, which puts the ceiling at **91.43%** and makes this
the third file in the campaign where 95% is not reachable with honest tests (after
`core/vacuum_identity.py` at 93.75% and `services/setup.py` at 94.46%).

**The testable five were a REPLICA with no tests at all.**
`_registry_model_code` is a deliberate copy of `core/manager._get_registry_model_code`
— its docstring says "Mirrors core/manager._get_registry_model_code (kept local to
keep the adapter self-contained)". The original had three tests; the copy had none,
and its **device-lookup half had never executed** — every call in the suite returned
`None` at the first guard. That is the half that matters: the copy exists because the
scalar/Tuya transport does not set the `detected_model` attribute, so reading only the
attribute "pinned scalar devices to model_family generic". The fix for that bug was
the untested part.

`CMR-4`–`CMR-7` live in `../integration/test_core_manager_registry.py`, beside the
original and its `_link_vacuum_to_device` helper, because **the claim is that the two
copies agree** — every assertion compares them. Four ablations, four at the predicted
verdict, and each one checks that the *original's* tests stay green, which is the only
way to catch having edited the wrong copy.

**The four unreachable units, each measured rather than argued:**

| guard | why it cannot be reached |
|---|---|
| `_build_button_block`'s `return None` | `_build_button_blocks` iterates `set(candidates) \| set(tokens)`, so every key it passes is in one of them; the other caller passes a `component_id`, and **all 7 components carry reset data** (both reset maps hold exactly those 7 keys — set difference measured empty both ways) |
| `_registry_model_code`'s `device_entry is None` | HA's entity registry **validates the device link on write** — `async_update_entity` with an unknown `device_id` raises `ValueError: Device ... does not exist` — and removing a device cleans up its entities rather than orphaning them. `CMR-7` pins exactly that, so if a future HA stops validating, the test goes red and the arm becomes a real gap |
| `_rescue_select_block`'s `if not ids` | its single call site passes a literal dict whose every entry carries an `entity_id` f-string, so `ids` is never empty |

Recorded rather than `pragma: no cover`'d, since the programme admits a pragma for
logger lines only — and because an unreachable guard with no written reason is the one
that gets "simplified" later.

### `../unit/test_adapter_config_parity.py` — the schema is a FLOOR, not the contract

3 tests, added 2026-08-15. `test_declaration_contract.py` above pins what happens
when a brand declares or fails to. This one pins something one level up: that
`ADAPTER_CONFIG_SCHEMA` **agrees with the other two authorities on the same config**,
because it is not the only one.

| id | holds |
|---|---|
| `ACP-1` | a key `registry._validate_adapter` rejects the ABSENCE of must not read `required: False` in the schema |
| `ACP-2` | a config field documented in a doc-22 field table must exist in the schema |
| `ACP-3` | the `SCHEMA_ABSENT_BY_DESIGN` allowlist does not rot in either direction |

Both directions were live defects, found on 2026-08-15 by a doc generator that
trusted the schema as the whole truth:

- **`room_profiles`** was `required: False` in the schema while `_validate_room_profiles`
  rejected its absence outright (`DC-2c` above is that rejection). Only the CONFIG path
  was bitten — `validate_adapter_config()`, behind the `save_adapter_config` service,
  honoured the flag and SAVED, then registration refused the stored config. The failure
  landed at registration instead of at save, which is the exact outcome
  `registry._validate_adapter`'s own docstring says it exists to prevent. Code adapters
  never noticed: they bypass the schema walk.
- **`low_clean_water_margin_ml`** was read at `planning/run_plan.py::estimate_job_water_usage` and documented
  in doc 22 with a worked example, while absent from `water_model_configs.entry_fields`.
  `entry_fields` IS enforced, unknown-key rejection included — so a porter following the
  doc wrote that key and got "key(s) not declared in the schema" on save.

**What it deliberately does NOT check**, and why the limit is in the file rather than
in someone's memory: "every key the code reads is declared" was *measured* before it was
designed — a scan of `.get("literal")` on receivers named `config`/`cfg`/`model_config`
finds 141 distinct keys, 61 of them undeclared, and nearly all 61 are room configs,
estimator internals or map-source sub-dicts rather than adapter config. A gate needing a
61-entry allowlist hides real findings instead of surfacing them. Doc 22's field tables
are the tractable proxy, and they caught the real one.

Sibling: `tests/unit/test_service_declaration_parity.py` does the same job for the
service surface.

---

State 2 is the one a normal suite never reaches, and it is why this file exists.
Before the fallback was removed it was indistinguishable from state 1 — an adapter
declaring nothing silently received Eufy's catalog. DC-5 closes the original
defect specifically: four call sites in `profiles/manager.py` resolved rooms
without ever consulting the registry, and the fallback covered for them.

**Why four checks and not one.** A `^from`-anchored grep reported the Roborock
adapter as reaching nothing; it reaches `core.capabilities` through a DEFERRED
import inside a function, deferred to dodge an import cycle. Hence AST over every
node in every file. And an import graph cannot see a runtime reach at all, hence
ISO-4. Both ISO-1 and ISO-4 were mutation-verified when added — a fresh
non-SDK import and a planted `hass._private_thing` each turn their own check red.

### `../unit/test_clean_order.py` — the shape filter that makes a log-scraped read trustworthy

18 tests, added 2026-08-20. Roborock exposes a per-map cleaning SEQUENCE, declared by
the adapter under `device_clean_order`. Reading it is the awkward part:
`vacuum.send_command` is `SupportsResponse.NONE`, so the reply never returns through
the service call — it is captured off a DEBUG log line that does **not say which
command it answers**. Everything therefore rests on `is_clean_order` telling a real
reply apart from routine poll traffic. A wrong filter reports confident nonsense,
which is the worst failure available here, because it looks like a reading.

The inputs are REAL decoded results captured from Ivy on 2026-08-19 — every distinct
shape observed across 53 replies — not invented ones.

| id | what it holds |
|---|---|
| `CO-1` | each of the ten real decoded shapes classifies correctly |
| `CO-2` | ABLATION: `[0]` arrives every ~15s poll tick and a naive "flat list of ints" filter accepts it; the known-room-id check is what rejects it. The test also asserts the ABLATED form still passes, so the ablation cannot quietly stop meaning anything |
| `CO-3` | `isinstance(True, int)` is True in Python, so `[True]` must not read as room id 1 |
| `CO-4` | one unknown id invalidates the reading whole — a dropped room would silently reorder the rest |
| `CO-5` | an unparseable payload yields `None` (→ `unavailable`), never an exception on a path a live run can touch |
| `CO-6` | with no known room ids the manager declines to read at all, rather than accept a list it cannot check |
| `CO-7` | an unread vacuum must not present as "no order saved": `[]` is a legitimate ORDER value, so the STATUS field is what carries "we have not looked yet" |

**`CO-2` is the load-bearing one.** `[0]` arrives roughly every fifteen seconds, so a
filter weakened to a type check would report it as a clean order continuously.

---

### `diagnostics.py` — 89.32% → 95.48% (2026-11-09)

**Two functions held 23 of the 36 uncovered statements, and both hid the same
way: an early return that every existing test takes, so the guard was covered and
the work was not.**

- `_device_entity_census` returned `reason: vacuum_entity_not_in_registry` in every
  test, because none of them put the vacuum IN the registry. The census that exists
  to tell "the device has no such entity" from "we looked in the wrong place"
  (`DIAG-1`, issues #48 and #49) had therefore never been POPULATED.
- `_pattern_resolution` returned `{}` because no test declared
  `live_map_image_entity_pattern`.

> ⚠ **`DIAG-14` IS NAMED FOR A DISTINCTION IT DOES NOT ASSERT**, and that is why
> this sat uncovered through two campaigns. It carries four `isinstance` checks —
> shape, not vocabulary — and its only substantive assertions sit under
> `if summary["likely_naming_mismatch"]:`, which is False in its own fixture. A
> conditional assertion that never fires. It is kept as the shape-and-degradation
> test it really is, and its docstring now says so; `DIAG-24` produces the
> populated census and asserts the distinction unconditionally.

| id | what it holds |
|---|---|
| `DIAG-24` | live:ENT-1 / #48 — a POPULATED census beside failed resolutions IS the naming mismatch; both sweep scopes are reported APART (live:ENT-5, #49: the device search found nothing while the config-entry search rescued battery on the same box) |
| `DIAG-25` | live:ENT-9 — `translation_key` and `state_class`, the two fields that separate `cleaning_area` from `total_cleaning_area` when `entity_id`, `platform` and `disabled` cannot; plus `disabled`, the OTHER silent cause |
| `DIAG-26` | an empty sweep NAMES itself rather than reading as a device that exposes nothing |
| `DIAG-27` | live:ENT-2 — `derived_exists` False beside `override_exists` True, which is "exactly what hid this for so long" |
| `DIAG-28` | an unformattable adapter pattern costs its own block, not the dump |
| `DIAG-29` | the on-device decode validator is wired in, and ONLY for the memory backend that can answer it |
| `DIAG-30` | ISSUE #55 — the last room-source refresh outcome is READ, and its absence means "never asked" rather than "nothing wrong" |

**`DIAG-29`/`DIAG-30` are CALL-SITE tests for engines covered the same day**, which
is `feedback_audit_callsite_reachability` pointed at my own afternoon:
`geometry_drift` went to 98.03% in `roborock_raw_map.py` and `source_refresh.py` to
100%, while the dump's wiring of BOTH stayed dark. A correct engine with an
untested call site passes every audit. They also happen to be what cleared 95% —
written because they were right, not to reach a number.

#### Three of my own tests did not test what they said

All three were caught by running or ablating, none by reading:

- `DIAG-27` assumed `_FakeManager` exposes `.data`. It does not — it is a pure stub,
  so `_pattern_resolution`'s read falls into its own pragma'd `except` and
  `override` is ALWAYS None. That is part of why the block was uncovered at all.
  Fixed by giving the fake a `data` attribute in the test rather than widening a
  fixture fifty other tests share.
- `DIAG-26` was called `a_vacuum_with_no_siblings_says_so` while its own docstring
  explained why it could not produce that case, then asserted something weaker —
  leaving `no_entities_on_device_or_config_entry` uncovered. The same shape as
  `DIAG-14` above, written an hour after flagging it. The case IS reachable: a
  registry entry with NEITHER a device NOR a config entry empties both scopes,
  because the vacuum otherwise counts as its own sibling.
- `DIAG-24`'s sort assertion was an IDENTITY. With two entities the sweep's natural
  order is the exact reverse of sorted order, so `ids == sorted(ids)` holds whether
  the census sorts or REVERSES — measured DEAD. A third companion breaks the
  coincidence. Fourth identity of the session, same family as `BE-17`'s
  `_emitted = None`, `% 360` asserted with `270`, and a map label asserted with a
  value equal to the fallback. **The cure is always the input, never the assertion.**

**9 ablations, 9 at the predicted verdict**, one declared SUBSUMED and confirmed:
`DIAG-24` asserts `config_entry_entity_count` is an `int` rather than a value, and
in its fixture everything is on the device, so collapsing that scope to 0 changes
nothing. Recorded rather than discovered.

**The remaining 22 units are a scattered tail** — twelve one-line alternate
branches across five functions in a 1322-line dump builder, no block larger than
two lines, plus two partial arcs. 95.48% (465/487) is where the behaviour-shaped
work ends; the rest would be tests written to a number.

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `registry.py` | 236 | 97% | `test_adapters.py` | integration | clean |
| `config_loader.py` | 33 | 100% | `test_adapters.py` | integration | clean |
| `config_schema.py` | 64 | 96% | `test_adapters.py` | integration | clean |
| `brands.py` | 53 | 100% | `test_brand_selection.py` | integration | clean |
| `entity_resolve.py` | 228 | 95% | `tests/unit/test_entity_resolve.py` + `tests/adapters/test_entity_resolve.py` + `tests/unit/test_disabled_action_warn_once.py` | unit + adapter | clean |
| `eufy/segmentor.py` | 868 | 95% | `tests/adapters/eufy/` | adapter | - |
| `eufy/adapter.py` | 60 | 97% | `tests/adapters/eufy/` + `../integration/test_core_manager_registry.py` | adapter | - |
| `eufy/entities.py` | 29 | 100% | `test_buttons_entities.py` + `test_suffix_vocabulary.py` | adapter | clean |
| `eufy/lifecycle.py` | 21 | 100% | `test_lifecycle.py` | adapter | clean |
| `eufy/constants.py` | 15 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/model_catalog.py` | 12 | 100% | `test_model_catalog.py` | adapter | clean |
| `eufy/vocabulary.py` | 42 | 100% | `test_error_source.py` + `tests/adapters/eufy/` | adapter | clean |
| `eufy/const.py` | 9 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/buttons.py` | 4 | 100% | `test_buttons_entities.py` | adapter | clean |
| `eufy/upkeep_catalog.py` | 1 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/water_config.py` | 3 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/maintenance_components.py` | 1 | 100% | `test_maintenance_config.py` | adapter | clean |
| `eufy/eufy_upkeep_guides.py` | 1 | 100% | `tests/adapters/eufy/` | adapter | - |
| `eufy/upkeep_guides_i18n/*.py` (17 languages) | 19 | 100% | `test_upkeep_guides_i18n.py` | adapter |
| `roborock/adapter.py` | 108 | 99% | `roborock/test_adapter.py` | adapter | - |
| `roborock/model_catalog.py` | 7 | 100% | `roborock/test_adapter.py` | adapter | - |
| `dreame/model_catalog.py` | 17 | 100% | `dreame/test_dreame_model_catalog.py` | adapter | - |
| `roborock/vocabulary.py` | 62 | 97% | `roborock/test_adapter.py` | adapter | - |
| `roborock/entities.py` | 27 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/const.py` | 7 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/upkeep_catalog.py` | 3 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/roborock_upkeep_guides.py` | 8 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/maintenance_components.py` | 2 | 100% | `roborock/test_adapter.py` | adapter | - |
| `roborock/upkeep_guides_i18n/*.py` (17 languages) | 121 | 100% | `roborock/test_adapter.py` | adapter |

`eufy/discovery.py` no longer exists as a separate module — model detection now
lives in `eufy/adapter.py` (`_registry_model_code`, which reads the device
registry) and `eufy/model_catalog.py` (`detect_model_family`); there is no
`test_discovery.py` file to reference for it anymore.

The Eufy adapter also pins two pluggable **engine seams** that live under
`learning/` (the adapter *declares* the engine; the engine itself is
brand-agnostic — see [06 — learning](06-learning.md)):

| Engine seam (under `learning/`) | Test file | Layer |
|---------------------------------|-----------|-------|
| `room_attribution_engines.py` (`SweptAreaWindingAttributor`) | `test_room_attribution.py` | adapter |
| `job_segmenter_engines.py` (`CounterPlateauSegmenter`) | `test_job_segmenter_config.py` | adapter |

(Adapter-config *services* are in [17 — services](17-services.md) via
`test_services_adapter_config.py`.)

---

## What's tested

- **Registry** — register / get adapter config, the module-level shims
  (`get_adapter_config`, `get_adapter_value`), coordinator wiring, and the
  all-configs accessor.
- **Config loader** — loading stored adapter configs from `hass_storage` and
  registering them (incl. the per-config skip-one-on-error resilience).
- **Brand selection** (`brands.py`, `test_brand_selection.py`, `BR-1..BR-7`) —
  which registrar runs for a given vacuum: positive detection wins in table
  order; no match reaches the DECLARED default arm and reports
  `source="default"` (distinct from a positive `"detected"` match, so a log
  line can say the brand was *assumed*, not identified); an explicit
  per-vacuum override (the UI-selector seam) outranks detection; a malformed /
  unknown / absent override degrades to detection rather than raising, but an
  unknown override id is still logged, never silently dropped; a detector that
  throws is skipped rather than taking setup down; and the real Roborock
  detector resolves end-to-end against the shipped table (an unrecognised
  device — blank manufacturer/model — still resolves to the Eufy default, the
  behaviour the old `if/else` had, now reported as `"default"` instead of
  being indistinguishable from a positive match).
- **Eufy adapter** (separate suite, `tests/adapters/eufy/`) — `model_catalog`
  resolution (code + hint matching), `lifecycle` helpers, the
  `buttons`/`entities` candidate-data shape, the CV `segmentor` wrapper +
  splitter helpers, per-component `maintenance_only` flag survival through the
  adapter's explicit-key config reconstruction (`test_maintenance_config.py`,
  issue #38 regression), the localized upkeep-guide data (`test_upkeep_guides_i18n.py`,
  17 languages, subset-of-English + non-empty-and-different-steps invariants),
  and the dock-vs-robot error-SOURCE classification
  (`test_error_source.py`, `EUFY_DOCK_SOURCED_ERROR_CODES` /
  `EUFY_EVIDENCE_INVALIDATING_ERROR_CODES` in `vocabulary.py` — exists because
  `total_error_seconds` is subtracted from `cleaning_time_seconds`, so a fault
  that never stopped the robot cleaning would otherwise silently zero a
  productive run). (Charging reads are brand-agnostic now and tested in
  `tests/unit/test_charging.py` — see [01 — core](01-core.md).)
- **Roborock adapter** (separate suite, `tests/adapters/roborock/`) — the
  brand-SPECIFIC wiring: model detection, brand auto-detect (device-registry
  manufacturer/model), and the key grounded config values, verified against
  the captured `vacuum.ivy` states + a run trace. The device-registry lookup is
  monkeypatched so the tests don't depend on HA registry plumbing. The
  brand-agnostic contract (schema conformance, dispatch shape, registry
  validation, entity-id format) for Roborock is covered separately, by
  `test_adapter_contract.py` via its `ADAPTER_BUILDERS` entry — adding a brand
  there runs the whole conformance suite against it with no new test code.
- **The dock lookup** (`RD-1`–`RD-3`, `roborock/test_adapter.py`) — `find_dock_device`
  against a **real** device registry, holding the shape upstream creates: one config
  entry, two devices, `(roborock, duid)` and `(roborock, duid_dock)`. Added with
  ISSUE #69. It is the exception to the monkeypatched-registry note above, and
  deliberately so: every other dock test stubs `find_dock_device` out and asserts on
  what `dock_profile` does with the result, so the lookup itself had **no** test and
  the registry walk the deprecation warning named was never executed by the suite —
  which is why replacing it broke nothing and proved nothing. `RD-2` carries the
  scoping claim the old docstring credited to config-entry filtering, with both
  robots in the same entry.
- **Eufy engine seams** (also in `tests/adapters/eufy/`) — the two pluggable
  engines the Eufy adapter declares. `test_room_attribution.py` pins the ported
  `SweptAreaWindingAttributor` (`learning/room_attribution_engines.py`) against
  the 3 adversarial external-run fixtures (the 9/9 dwell + spread + winding +
  swept-area attribution, dock-trap exclusion included). `test_job_segmenter_config.py`
  asserts the Eufy adapter declares `job_segmenter.engine = "counter_plateau_v1"`,
  that its `job_segmenter.tuning` equals `CounterPlateauSegmenter.DEFAULT_TUNING`
  (no threshold drift after the move out of `live_transition`), and that the
  declared engine resolves and validates clean.
- **Brand-aware diagnostics self_check** (`DIAG-*`, integration,
  `tests/integration/test_diagnostics.py`) — `_self_check` reads a native-integration
  brand (Roborock: rooms from its own integration, no `active_map` sensor, no Eufy
  `segments` attribute) as rooms/map WORKING and brand-named, driven by the
  `roborock_geometry_drift` decode-drift block in the dump, rather than the Eufy-shaped
  "unknown / unavailable / no" the transport-only heuristic produced (`DIAG-9`); and
  degrades to a generic "native integration" + map-"pending" summary when the raw map
  hasn't decoded yet and the brand string is absent (`DIAG-10`).
- **Dock detection provenance** (`DD-1`–`DD-4` in `roborock/test_adapter.py`, `DIAG-22`
  / `DIAG-22b` in `test_diagnostics.py`) — ISSUE #69 follow-up. `DD-3` is the load-bearing
  one and the reason the block has `resolved`/`source` at all: it asserts that a live
  probe resolving a dockless machine stays distinguishable from a probe that DECLINED
  and fell back to a catalogue default saying the same thing, *while asserting every
  outcome matches* — identical `supports_mop_wash` and no `action_controls` on both
  sides. Recording only the dock type would make both `{None, None}` and that test goes
  red. `DIAG-22b` pins the absent-vs-empty distinction: a brand that records nothing
  gets no key, because `{}` claims we looked.
- **Every adapter test file needs `hass`** for the config-registration seam —
  see [01 — overview](../01-overview.md) for which files and why.

---

## The adapter coverage boundary

`adapters/eufy/*` and `adapters/roborock/*` are **counted in the coverage
number** — we always test the adapters we ship, so the figure includes both.
The Eufy adapter is well covered: `model_catalog`, `lifecycle`, and the
`buttons`/`entities` data shape sit at or near 100%. The CV `segmentor` is
**91%** — the splitter helpers, recovery / scoring / issue-tag paths, and (via
two map fixtures) the localized-bins SPLIT + child-handling are all covered;
its remaining tail is the splitter-internal *alternative* sub-branches (see
Known gaps), the natural place a second-brand effort would invest. `adapter.py`
(85%) is missing 5 lines (124, 156-159): the `return None` guard in the small
helper `_build_button_block` when a button key is absent from both candidates
and tokens maps (124), and inside `_registry_model_code` — the
device-registry model lookup that replaced the old standalone
`discovery.py` — the device-registry `.get()` call itself (156), its
None-guard early return (157-158), and the successful resolved-model
`return` (159): the whole device-registry happy path is untested, not just
an early-return guard. (The earlier entity-registry/no-device-id guard,
154-155, is covered.) The Roborock adapter is well covered too:
`adapter.py` sits at 96%, and every other Roborock module (model catalog,
vocabulary, entities, const, upkeep) is at 100%. See
[01 — overview](../01-overview.md) for the three-layer split.

---

## Known gaps

`registry.py` (91%) leaves mostly defensive validator arms uncovered — the
`append`-an-issue branches that reject a malformed stored adapter config
(missing lines 180, 287, 378, 387, 407, 411, 424, 433, 453, 467, 489, 523, 589,
618, 651 — `--cov-report=term-missing` for the current mapping to specific
checks). The `job_segmenter` engine-validation arms (not-a-dict / missing /
unknown engine) are covered — `test_adapters.py` asserts that contract so an
unknown engine can't silently fall back. The rest are error paths for invalid
storage, not real behavior holes. `adapter.py` (85%, see above) is missing the
one defensive button-block guard plus the entire device-registry-lookup
happy path in `_registry_model_code` (156-159, see above) — that path is
untested outright, not merely a defensive early return. `config_schema.py`
(94%) is missing 3 lines
(1866, 1893, 1958) in schema-validation branches not yet re-triaged this pass.

✅ **SUPERSEDED 2026-11-11, and the retirement matters more than the figure.** A paragraph
here called CV `segmentor` depth "the one remaining thin spot" at 91%, said what was left
was "splitter-internal *alternative* sub-branches … each geometry-sensitive or
best-effort", and closed "held here on purpose, a known thin spot rather than a framework
miss". It sat directly above the section that contradicts it, which is the defect being
fixed — a reader cites whichever account they reach first. Three of its claims were
measured false:

- the "geometry-sensitive" sub-branches are reachable from the public entry point with
  constructed PNGs, and 16 tests now drive them;
- "held on purpose" described a belief about reachability, not a decision;
- "diagnostic-confirmed as the **only** input that hits localized-bins accept" was wrong —
  a 700² canvas with a 450² block in six equal vertical stripes of `(255, x, x)` accepts
  with six candidates, no fixtures and no assist image.

What was true and is kept: the history (91% up from 70%, via the splitter/recovery/scoring
tests and the `_prune_localized_siblings` extraction), and that `[ECV-8]`
(`adversarial_map.png`) can only make localized-bins run-and-reject while `[ECV-9]` (the
real dark+light pair) reaches accept. The current account is immediately below.

### `eufy/segmentor.py` — 92.38% → 95.43%, against a ceiling of 95.59%

Measured 2026-11-10: 868 statements and 378 branches, of which **53 statements and 42
partial branches are uncovered — 1151/1246 = 92.38%.** The paragraph above says 91% and
calls what remains "splitter-internal *alternative* sub-branches … each geometry-sensitive
or best-effort." Both halves are wrong, and the second one mattered: it reads as a
statement that the rest is unreachable, and **95% is reachable here with honest tests.**

**EVERY UNCOVERED UNIT IS NOW CLASSIFIED, and the arithmetic closes exactly:** 53
statements partition into 23 pipeline-reachable, 7 unit-tier-only and 23 unreachable; the
42 partial branches into 36 paired with an uncovered statement (they close together with
it, so they are not separate units) and 6 orphan arcs whose uncovered arm jumps to an
already-covered line.

| | units | coverage |
|---|---|---|
| before | — | 1151/1246 = 92.38% |
| **built — `[ECV-21]`…`[ECV-37]`** | **+38** | **1189/1246 = 95.43%** |
| ceiling (the one remaining reachable unit) | +2 | 1191/1246 = 95.59% |
| if unit-tier tests were allowed too | +15 | 1206/1246 = 96.79% |

**The module is over 95%.** 16 tests closed 38 of the 40 reachable units; the 2 that
remain are `:446`, which is reachable but **unassertable** — see `[ECV-30]`'s note in
`test_segmentor.py`, which is why the achieved figure sits 0.16 pp under the ceiling
rather than at it.

The last row is weaker evidence and is recorded only for completeness: those tests assert
against states the production caller cannot produce — a disconnected `component_mask`, a
`(h, w, 0)` channel array, an `ndarray` subclass whose `nonzero()` lies — so they would
raise the number without pinning any behaviour a user can reach.

**15 OF 15 ABLATIONS REDDENED THEIR TEST**, each a single named source edit, with the file
verified byte-identical after every restore. Two tests make no bite claim and say so in
their own docstrings rather than letting their coverage imply one: `[ECV-29]` covers a
defensive guard whose removal changes no observable, and `[ECV-25]` discriminates against
its control but survived three different ablations because the refusal it asserts is
over-determined three layers deep.

Every reachable claim below was produced by one agent and then **rebuilt from its recipe
alone by a second**, which is why the recipes are recorded rather than the probes: 10 of 10
reproduced, and where a verifier re-derived something the recipe omitted, the recipe was
corrected here. What is settled:

**TEN STATEMENTS ARE PIPELINE-REACHABLE — verified, with recipes.** Each reaches its line
through `detect_room_segments()` on a synthetic PNG, with nothing patched. Synthetic
fixtures are already this file's convention (`_l_shape_map_png`, and `adversarial_map.png`
itself). Every recipe below was reproduced from scratch before being written here, and
each one's control does *not* fire, so the probes discriminate.

Line numbers are given with their enclosing symbol, because the lines move: the existing
note's `:1111` had already rotted to `:1225` by the time this pass read it, and three
separate line mappings in this pass were off by four before being checked against
`segmentor.py::_detect_room_segments_pipeline` directly.

| symbol · line | what it refuses | the input that reaches it |
|---|---|---|
| `segmentor.py::_split_component_via_local_support` `:446` | `supported` empty after the 3×3 opening | 300² blob, three colours all in hue bin 6; sat p42 selects 60%, value p38 selects 80%, and the `score >= 2` intersection is **2-px stripes** the opening erases. A 5-row period of 2 Z / 1 X / 2 Y gives Z=40%. The 3-px control does not fire |
| `segmentor.py::_split_component_via_color_distance` `:565` | a grown mask below the area floor | 170² PNG, 78² `(254,50,50)` block with an **enclosed** 20×40 `(50,50,254)` island |
| …same function `:567` | a grown mask above `active*0.84` | same image — the carrier grows to 4676 of 5476 |
| …same function `:569` | the ≥0.72 overlap dedup | 330² concentric squares: carrier `(84,254,254)`, mid ring `(118,220,254)` lying inside **both** centres' `allowed` sets, core `(169,169,254)`; shared ring 11040/14884 = 0.7417 |
| …same function `:581`, `:582` | `used_area < active*0.38` | 600² PNG, 300² block whose interior is a mosaic of eight sub-floor bands, so only two 10000-px islands rank |
| `segmentor.py::_localize_oversized_component` `:667` | `opened` empty | 500² PNG, one hue bin, six chromaticity sub-bins; a **checkerboard** bin whose pixels have no 8-neighbour |
| …same function `:681` | a candidate above `active*0.22` | same recipe, a single connected 37240-px bin — admitted by the `max_bucket` gate (`<= active*0.24` = 38400) and then rejected here (`> active*0.22` = 35200). A 3200-px window between two constants in one function |
| …same function `:709`, `:710` | fewer than two candidates | one in-range bin, or a plain solid block where the closure is never entered at all |

The mechanism that makes four of these possible is worth keeping: **`binary_fill_holes` at
`:1182` re-absorbs an enclosed island of a different hue**, which is how one component ends
up carrying two far-apart chromaticities despite 16-wide hue binning. Without that, the
colour-distance arms look unreachable.

Covering those ten and the eight branches they close is **+18 units → 93.82%**. That is a
measured *lower bound* on the ceiling, not the ceiling.

**FOURTEEN STATEMENTS ACROSS TEN GUARDS ARE UNREACHABLE BY ANY REAL INPUT.** Four fire only
under injection — monkeypatching an intermediate so the guard sees a value the real path
cannot produce — which is not a refutation.

| symbol · guard | why it cannot be reached |
|---|---|
| `_split_component_via_color_distance` — `insufficient_feature_values` `:506/507` | its own active-area floor already requires `active >= max(m*2, 3200)` and `len(feature_values) == active`; `max(m*1.2, 1800) < max(m*2, 3200)` for every `min_area_pixels` in 0…20000, swept |
| `_split_component_via_local_support` — empty sat/value `:420` | same shape against that function's own floor; the two clauses differ — the first is a caller contract, the second a numpy one |
| `_split_component_via_color_distance` — empty `active_distances` `:550`; `_localize_oversized_component` — `no_feature_values` `:622/623`; `_split_component_via_assist_hue` — `no_active_hue_values` `:746/747` | `len(...) == 0` after each function's own upstream `active_area` floor of 3200 / 120000 / 3500 |
| `_reclaim_localized_child_mask::_trim_sparse_top_rows` — empty `baseline_rows` `:205` | the ≥6-occupied-rows floor holds, and the baseline index is itself drawn from `occupied_rows`, so `row_counts[lower_start] > 0` is always inside the slice |
| `_reclaim_localized_child_mask` — empty after trim `:229` | `_trim_sparse_top_rows` retains ≥68% or returns the mask untouched |
| `_split_component_via_color_distance` — `center_distance_too_small` `:537/538` | the two ranked bin centres cannot land within 0.09 of each other on any real palette |
| `_localize_oversized_component` — `count <= 0` `:670`, `label_slice is None` `:675` | scipy's contract: `label()` on a non-empty mask returns `count >= 1`, and `find_objects` returns exactly one slice per label |

**`:229` IS ONE NUMBER FROM LIVE, AND TWO OF THESE ARE NOT SAFE TO DELETE.** Lower `:221`'s
0.68 to ≤0.16, or `:197`'s 6 to 1, and `:229` becomes reachable — these are the thresholds
most likely to be retuned. Deleting it then lets `:230`'s `int(ys.min())` raise
`ValueError`, which escapes to `mapping/segmenter_engines.py:313` and fails the **whole
run** as `engine_unavailable`, where the guard loses one room and `:1285`'s
`if local_area <= 0: continue` absorbs it. Deleting `:205` is worse than it looks for a
different reason: `np.median([])` is `nan`, and `max(6.0, nan * pass_strength)` returns
**6.0** — because `nan > 6.0` is False — so the trim rule silently degrades into a fixed
threshold, and the `RuntimeWarning` is invisible (`pytest.ini` sets no
`filterwarnings = error`). Both are classified **keep-with-comment**: they read today as
evidence their state can occur, which is the false half a comment has to fix.

**`touches_border` CANNOT FIRE AT ALL, AND FIVE SITES DEPEND ON IT.** The note at
`test_segmentor.py:622-629` already records `:1226` as uncovered on purpose, with a stale
line reference (`:1111`) and an inset of "~6px"; measured across 5 configurations and 225
samples, the inset is **4px on all four sides**, invariant to crop depth — cropping 120px
into the rooms moves the frame but the morphology rebuilds the gap. `min_x` never goes
below 4 and the predicate needs `x <= 1`. `local_touches_border` (`:1305`) is never True
either. So `_issue_quality`'s `"usable"` downgrade (`:95`) is unreachable via this tag,
`:971`'s `not touches_border` is always True, `:1455`'s drop never fires, and `:1528`
always passes False. The *intent* is live — the capture guide's step 8 is "Do not clip any
part of the map itself" — so the predicate is defeated rather than redundant, and the
fix would be a tolerance above 4.

✅ **RULED 2026-11-11: LEAVE IT ALONE.** Not deferred, not awaiting a decision — decided.
Do not re-raise it, and diff a fresh code walk against this paragraph, because the walk
WILL find it again: five sites read a tag that can never be set, which looks exactly like
a bug worth fixing. The reason it is not worth fixing is the blast radius, not the
diagnosis. Raising the tolerance makes the tag start firing into
`_component_should_keep`, so regions that are kept today could start being dropped — and
users have linked rooms to those segments, so a dropped region orphans a link on an
install that was working. The tag being inert is the behaviour users have, and it is
harmless; making it live is a change to what the segmenter keeps.

**THIRTEEN MORE STATEMENTS AND THREE ARCS IN THE PIPELINE BODY ARE ALSO REACHABLE**, which
is what moves the ceiling over 95%. Same standard — produced, then rebuilt from the recipe
by a second agent.

| symbol · line | what it refuses | the input that reaches it |
|---|---|---|
| `segmentor.py::_detect_room_segments_pipeline` `:1123`, `:1124` | the assist-registration `except` | **an assist path that does not resolve.** A truncated PNG works (the boundary is tight: 99% of the bytes decodes, 95% raises `OSError: image file is truncated`), as does a forged IHDR (`DecompressionBombError`), but the cheap route needs no corrupt file at all — see the defect note below |
| …same function `:1418`, `:1419` | `low_saturation_large_parent` | 400² white canvas, a 240² block of `(255,230,230)`. The saturation ladder is sharp: mean sat 30/31 keeps the segment, 29/25/21/19 drops it, and at 17 the room gate discards the block entirely |
| …same function `:1423`–`:1425` | `localized_child_too_small` | a localized-bins accept whose child is under both `area_percent < 0.0025` and `max(1100, min_area*0.9)` |
| …same function `:1427`–`:1429` | `localized_child_sparse` | the `elif` arm — a child that is sparse (`fill_ratio < 0.12`) but **not** tiny, so a large bounding box holding few pixels |
| …same function `:1510` | `break` once the deficit closes | recovery must actually succeed first, then leave another candidate behind it |
| …same function `:1518` | a deferred candidate over 20% of frame | — |
| …same function `:1533` | `_component_should_keep` refusing in `recovery_mode` | — |
| arcs `532→529`, `646→658`, `854→856` | three orphan branch arms | the uncovered arm jumps to an already-covered line, so only the arc is missing |

**A DEFECT FOUND BY ASKING HOW `:1123` IS REACHED.** The cheapest real route to that handler
is a **stale `assist_image_path`**, and it is a live user path, not a probe artifact:
`mapping/mapping_services.py` writes `tuning["assist_image_path"]` **only when the light
variant is on disk**, so deleting the light variant leaves the previous path persisted;
`mapping/segmenter_engines.py` reads it straight into the `detect_room_segments` kwargs; and
`validate_tuning` accepts the key as a known tuning key with no existence check. So a user
who removes their light variant keeps a dangling path, the registration raises
`FileNotFoundError`, and the run silently degrades to single-image mode with the error
buried in the registration dict. Not fixed here — it is a mapping-services defect, not a
test gap.

**THREE MORE GUARDS JOIN THE UNREACHABLE SET**, and one is an architectural finding:

| symbol · guard | why it cannot be reached |
|---|---|
| `_split_suspicious_component` — `opening_split` accepted `:894`, `:895` | **strategy 7 of 7 is unreachable because strategy 6 subsumes it.** Erosion is tried first and regrows seeds the same way under the same lower-area floor, so any mask that opening can split, erosion already split |
| `_detect_room_segments_pipeline` — `assist_hue_child_rejected` `:1415`, `:1416` | `_split_component_via_assist_hue`'s own `grown_area > active*0.82` guard means it can never return a child bad enough to be rejected downstream |
| `_detect_room_segments_pipeline` — degenerate polygon `:1302`, `:1303` | `segment_primitives.py::mask_to_polygon` unconditionally restores the best loop when simplification drops below 4 points, so the `< 4` test downstream can never see one |
| `_detect_room_segments_pipeline` — empty cluster mask `:1177` | exact duality: `active_bins` is built *from* `hue_bin[room_mask]`, so every bin in it has at least one pixel |
| `_detect_room_segments_pipeline` — `label_slice is None` `:1189` | `ndimage.label` relabels to a consecutive 1…n set, so `find_objects` never returns a `None` entry. It *can* for a gapped label array, so the guard defends against a producer other than `label()` |

Seven statements (`:186`, `:236`, `:277`, `:465`, `:874`, `:875`, `:886`) and two arcs
(`430→434`, `436→440`) fire **only** when a helper is called directly with a state its sole
caller cannot produce. `:874/:875` are the clearest case: `_split_component_via_local_support`
can never *accept* on a connected mask, because `binary_propagation` re-floods the whole
component and every grown mask then trips the upper-area guard — and the pipeline's
`component_mask` is connected by construction.

**AN INSTRUMENT WORTH KEEPING.** The fixture pair was thought to be the only input that makes
`localized_bins` accept. It is not: a 700² white canvas with a 450² block painted as six equal
vertical stripes of `(255,x,x)` for `x` in {0,40,80,120,160,230} accepts with 6 candidates and
no assist image at all. That makes the localized child geometry *chosen* rather than inherited,
which is the right instrument for the `_reclaim_localized_child_mask` arms.

**WHAT THE REMAINING 31 STATEMENTS ARE.** 23 unreachable by any input, 7 reachable only by
handing a helper a state its caller cannot produce, and 1 (`:446`) reachable but with no
observable to assert on. Nothing is unaccounted, and nothing is waiting to be tried.

The recipes stay in this section even though they are now tests, because the GEOMETRY IS
THE CLAIM: each dimension solves for one threshold, and a reader who adjusts a number
without reading the arithmetic will silently stop testing the arm. Recorded rather
than `pragma: no cover`'d, since the programme admits a pragma for logger lines only — and
because an unreachable guard with no written reason is the one that gets "simplified" later.

The Roborock adapter has no comparable known gap — it is a much smaller,
declarative-config module (no CV pipeline), and every source file except
`adapter.py` is at 100%.
