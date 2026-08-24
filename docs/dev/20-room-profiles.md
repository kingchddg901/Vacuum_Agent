# 20 — Room Profiles and the Brand-Neutrality Contract

**Scope.** What a room profile is, where its vocabulary comes from, and the contract that keeps
one brand's words out of another brand's rooms. The saved **run** profiles — a different store
with a different scope — are [21 — Run Profiles](21-run-profiles.md).

**The store is GLOBAL.** `data["profiles"]["room_profiles"]` is keyed by profile name alone — no
vacuum, no map, no brand. That is why it appears in neither `PER_MAP_STORES` nor
`VACUUM_KEYED_BUCKETS`: a global store has nothing to delete when a map goes away.

---

## 1. Core owns the keys; the adapter owns every value

The split is the whole subsystem:

| owned by core | owned by the adapter |
|---|---|
| the profile **key** space — `vacuum_quick`, `vacuum_deep`, `vacuum_mop_quick`, `vacuum_mop_deep` | every **value** behind those keys |
| the `clean_mode` canonical token space — `vacuum` / `mop` / `vacuum_mop` | the display words for every other axis |

**There is no framework catalog, and nothing inherits one.**
`profiles/manager.py::ProfileManager._catalog_for` is the single funnel every resolution passes
through, and an undeclared axis resolves to `""` — *nobody said* — never to another brand's word.

That is not the original design; it is a repair. Until 2026-08-07,
`profiles/room_profiles.py::resolve_profile_catalog` returned Eufy's dictionary by default. The
recorded live failure: a Roborock room stored `fan_speed: "Max"`, the card's strict-equality chip
row matched nothing, `per_room_live_settings` filtered the value out, and an unedited room applied
**no suction at all**.

The protected-name set moved to core in the same change. Sourced from a brand catalog, one brand's
dict decides what every user is allowed to rename — and core cannot protect a name at all if that
brand stops shipping.

### Declared-empty is a value, not an absence

`profiles/room_profiles.py::_catalog_key` tests `key in block`, **not truthiness**. So
`builtins: {}` and `legacy_aliases: {}` are honoured as declarations of *we have none*.

Write it as `block.get(key) or default` and a brand's explicit "none" becomes unrepresentable —
any falsy declared value reads as absent and the in-code default is injected in its place.

> ⚠ **The validator gates the BLOCK, not the key — and its own docstring says so.**
> `adapters/registry.py::_validate_room_profiles` fails exactly three states: `room_profiles`
> absent, not a dict, or `{}`. It never inspects `builtins`.
>
> So `room_profiles: {legacy_aliases: {}}` is non-empty, passes validation, and resolves nothing —
> which is precisely the state the validator's stated rationale exists to catch ("a brand with zero
> profile vocabulary can resolve nothing, so it is never a working declaration"). The convention
> the module banner describes is real; enforcement is one granularity coarser than it reads.

---

## 2. Axis existence is a separate question from option availability

`profiles/room_profiles.py::declared_profile_fields` decides which axes a brand *has*, and it
derives that from the brand's **profiles**, not from its option lists.

The distinction is load-bearing and a sibling subsystem gets it wrong. A missing
`{field}_options` list is a **capability** statement — Roborock withholds `water_level_options` on
models whose mop is not settable. A field absent from the profile vocabulary is an **axis**
statement. Deriving axis existence from option lists conflates them and strips `water_level` and
`clean_mode` from every room on an S6.

`profiles/manager.py::ProfileManager._finalize_room_update` strips undeclared vocabulary fields on
every room save, using that same discriminator — deliberately the same one the one-shot store
repair uses, so the repair cannot be undone one room at a time. Without it, the migration that
dropped `clean_intensity` from ten Roborock rooms was reversed by the next save putting it back
as `""`.

> ⚠ **The strip is also where the seam leaks.** It makes a Roborock room's `clean_intensity` key
> **absent**, while the resolver's candidate always emits nine keys including `clean_intensity: ""`.
> `_match_profile_from_fields` compares them, `None != ""`, and so on a brand with no intensity
> axis **no room can ever match any preset** — every save stamps `profile_name: "custom"`. The
> file's own header records this as `DQ-Q-2`, marked closed.

---

## 3. Matching a room back to a profile

`_match_profile_from_fields` resolves the candidate **under the room's own `floor_type`**, so
floor-driven invariants apply to both sides of the comparison.

Resolve the candidate from a bare profile name and the asymmetry returns: the candidate picks up
the hardwood water default (`"Low"`) while the room's protected water is forced `"Off"`, so a
plain vacuum room on hardwood never matches its own profile.

**`canonical_clean_mode` is applied to the clean-mode leg only.** The other five legs stay on the
case-folding-only normalizer. Widening it would have core assert a framework opinion about words
like `"Max"` and `"Quick"` that belong to the adapter — the fallback-catalog problem rebuilt in
the comparison layer.

---

## 4. The resolution ladder, and what a missing catalog actually yields

`profiles/room_profiles.py::resolve_room_profile_for_room` walks profile → room → default.

> ✅ **CORRECTED 2026-08-23.** Three, in fact — `normalize_room_profile` carried a surviving fragment of the same
> sentence. All now state that an absent catalog yields NOTHING rather than a fallback.
> What they said before: **two docstrings still describe the pre-2026-08-07 world.**
> `resolve_room_profile_for_room` says `catalog=None` "uses the in-code constants"; there are none
> left. `None` flows through `get_room_profile` → `get_default_room_profiles(None)` → `{}`, the
> merge yields `{}`, both lookups miss.
> `apply_room_profile_to_config` says the catalog supplies `normalize_defaults` "so a non-Eufy
> brand's rooms do not get Eufy defaults". With no catalog it does not produce Eufy defaults — it
> produces **empty strings**. `brand_defaults = {}`, so fan speed, water level and clean intensity
> all come out `""`.
>
> The behaviour is correct and it is what the contract wants. Only the prose is stale, and it is
> stale in the direction that describes a fallback the repair removed.

**`get_room_profiles(vacuum_entity_id=None)` returns the saved library alone**, flagged
`built_ins_included: False`. The argument is optional rather than required because a shipped
no-argument service depends on it — and the flag is what keeps the smaller answer honest. Serving
whichever brand core happened to carry would hand a caller somebody else's vocabulary presented as
available profiles.

---

## 5. Rename, delete, and the cost of a global store

`_find_rooms_referencing_profile` scans **every vacuum and every map**. That scan is where the
global store's blast radius becomes visible: one profile name is shared across every vacuum on the
install.

**`delete_room_profile` refuses while rooms still reference the profile**, unless `force=True`.
Unconditional delete was the shipped behaviour, and `force` reinstates it exactly — as an informed
choice rather than a default. Without the refusal the referring room's `profile_name` points at
nothing, and the resolver falls back silently, so the record is orphaned with no signal.

**`rename_room_profile` repoints every referrer in place** rather than leaving them dangling.

---

## 6. Common wrong assumptions

| assumption | actually |
|---|---|
| an adapter that declares no profiles inherits a framework catalog | there is no framework catalog; undeclared resolves to `""` |
| `builtins: {}` is the same as omitting `builtins` | `_catalog_key` tests membership, so declared-empty is a real declaration |
| the registry refuses an adapter that declares no `builtins` | it gates the block only — `{legacy_aliases: {}}` passes and resolves nothing |
| a brand with no `water_level_options` has no water axis | that is a capability statement; axis existence comes from the profile vocabulary |
| `catalog=None` falls back to in-code constants | there are none left; it yields `{}` and every field comes out `""` |
| a room whose settings equal a preset will match it | not on a brand missing an axis — absent vs `""` never compares equal, so every save stamps `custom` |
| `get_room_profiles()` with no vacuum returns the built-ins too | it returns the saved library alone, and says so with `built_ins_included: False` |
| deleting a profile is safe because rooms fall back | the fallback is silent; the refusal exists so the orphaning is not |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
