# 17 — A Room's Identity

**Scope.** What a room *is*, where that identity is minted, how it survives the device
renumbering its segments, and the guards that stop a bad discovery erasing a configured map.
The access graph and the rules engine read this store and never write it — they are
[18 — The Access Graph](18-access-graph.md).

---

## 1. Identity is the slug; the id renumbers underneath

`rooms/room_manager.py#INMKEHPQ` states the rule the whole cluster follows: **a room's identity
is its slug, scoped to its map. The numeric segment id renumbers underneath it.**

Almost nothing else here is an independent decision. Slug-led carry-over, the reconciliation
reviews, the uniqueness suffix and the refusal of blank names are all consequences of putting
identity on a name the user chose rather than on a number the device owns.

**The rule is inherited, not chosen.** Before rooms were objects they were groups of HA helper
entities addressed as `{vacuum}_map_{map_id}_{axis}_{slug}` — the slug *was* the primary key,
because entity ids are strings, and the invariant's scoping is that entity name's scoping. The
numeric id only became available as an identity when rooms became records, and it was not taken.

The slug transform (`rooms/utils.py::slugify_room_name`) is **script-agnostic and NFC-normalised,
not ASCII-folded.** The alternative is named in its own docstring and rejected: an ASCII folder
turns any all-Cyrillic, Greek, CJK or emoji name into the empty string, so every such room
collapses into one identity — precisely the data loss reconciliation exists to catch. The
trailing NFC pass matters on its own: a brand returning NFD on one firmware and NFC on another
would otherwise re-derive a different slug for an unchanged room.

---

## 2. One admission boundary

`rooms/room_discovery.py#INCFMPP1` — the slug is derived once, and made unique **at discovery**,
not by the transform and not where it is consumed.

The transform cannot do it: it is a pure per-name function with no cross-room view. The consumers
cannot do it either — dispatch's slug-to-live-id map is first-wins, so it would resolve the same
physical segment for two rooms while reconciliation reported a phantom `id_changed` for whichever
one did not actually renumber.

**The lowest stable room id keeps the bare slug** and the others take a deterministic suffix, so
re-discovering the same physical rooms converges on the same answer rather than drifting.

**A name that slugifies to empty is refused admission** — skipped with a warning, not admitted
with a blank identity. The prior behaviour checked only the raw name for emptiness, which let an
all-punctuation name through: the transform deletes those characters, so the room would key
reconciliation, dispatch and learning on the empty string.

### Which map, and what to do when nothing says

`rooms/room_discovery.py::get_active_map_id` resolves against whether the declared `active_map`
entity **actually exists in the registry**, in three states — present, declared-but-absent, and
not declared. That check is load-bearing because `entities.active_map` is declared from a *naming
pattern* for every device, so "declared" never implies "exists". Collapse it and every restart
window forks a phantom implicit map.

The two no-selector fallbacks are deliberately narrow. `_single_cached_map_id` fires only for a
service-response source holding exactly one map; `_implicit_attribute_map_id` is the attribute-side
twin. Widening either to "fall back to the single map whenever the lookup misses" costs the
`RP-019`/`ID-2` failure both exist to prevent: **serving one map's rooms relabelled with another
map's id.**

> **The room-list SHAPE is declared independently of its SOURCE**, and the two axes are genuinely
> orthogonal. Source is attribute versus service response; shape is a flat list versus a per-map
> mapping. Assuming shape from source left the diagonal — a per-map mapping delivered as a live
> attribute — inexpressible, so it fell through to "missing or invalid", discovered zero rooms,
> and left every downstream config block inert. A `if brand == …` branch here was rejected on the
> same grounds it always is: core would be learning a brand.

`rooms/source_refresh.py` is what makes a service-response brand look like an attribute brand to
the *synchronous* discovery path. An async refresher runs at four async boundaries, flattens the
response into the same list-of-dicts shape, and caches it in `hass.data` keyed by **map name**.
The cache is ephemeral by design; nothing here is persisted.

---

## 3. What a new room contains

A new room's settings **are its brand's `default_profile`'s settings**, resolved through the
existing `room_profiles` declaration rather than through literals.

Four independent copies of those literals existed before this — in `build_managed_rooms`, in
`RoomConfig`'s dataclass defaults, in the map rebuild, and in the profile resolver's fallbacks.
Undoing the change re-opens two distinct failures, and the brand one is the sharper: Roborock
declares lowercase option values (`"max"`) while the framework wrote `"Max"`. The card's chip row
compares strictly, so nothing rendered as selected; `per_room_live_settings` filters on
`fan_speed_options`, so an unedited room applied **no suction at all**.

**A field the default profile does not declare is absent from the result**, and the caller keeps
its own field-level default. Roborock declares no `clean_intensity_options`, so its default
profile omits the key entirely. Inventing a framework value for every field would write a
meaningless one onto every Roborock room. **Silence from a brand is not a value.**

`rooms/room_manager.py::build_managed_rooms` takes `new_room_defaults` as a **required** keyword
with no default. A permissive `= None` is the shape that keeps producing Eufy display vocabulary
on non-Eufy brands; a `TypeError` at a forgetful call site is the cheaper failure.

**A room brand-new to a discovery pass is enabled on a first import and disabled on an incremental
one.** Enabling unconditionally puts a room the user has never seen into an already-active
cleaning queue.

> ⚠ `path_type` is stored as `""`, never `None`, and its key is **dropped** from the persisted
> dict when empty — the only axis `as_dict` drops. `as_dict` is `asdict`, so `None` was written to
> storage on every brand and read back through `str()` as the literal `"None"`: in no vocabulary,
> and truthy. Every "did this room set a path?" test answered yes and put it on the wire.

---

## 4. Carrying settings across a re-discovery

Carry-over is **slug-led with an id fallback**, and the id fallback cannot reclaim an id that a
slug match already used — the claimed id goes into `consumed_ids`.

Without that, a re-segment transplants one room's settings onto whichever room now holds its old
number. The recorded case: Kitchen moves 16 → 21 and a new Bedroom takes 16, so Kitchen carries
correctly *via slug* and Kitchen's settings are **also** stamped onto Bedroom *via id 16*.

**A slug that is not unique among the stored rooms is excluded from the slug-led map entirely**,
and that room falls back to id-led carry. Picking one of the two candidates first-wins would
collapse two rooms' identities on a guess — and a store predating the uniqueness suffix can still
hold such a pair.

> ⚠ **That exclusion is implemented in two of the three copies of this algorithm.**
> `rooms/reconciliation.py`'s two builders still `setdefault`, i.e. first-wins. The rule reads as
> a property of the cluster and is a property of two functions in it.

---

## 5. When identity shifts: reconciliation

`rooms/reconciliation.py` is pure — no `hass`, no manager. It compares a fresh discovery against
the saved rooms **by slug** and reports shifts as **reviews the user confirms**, never as
automatic changes. New and removed rooms are deliberately not its business; drift handling owns
those.

`rooms/room_crud.py::RoomMapManager` is its only caller.

**A dismissal is fingerprinted, not timestamped.** `reconcile_room(action="ignore")` stores a
`plan_token` of exactly what was dismissed, and a later review is suppressed only while the
recomputed token still matches. A bare timestamp gives you one of two failures: the same review
re-firing on every pass, or a genuinely new identity shift suppressed forever.

**Confirming a migration recomputes the token fresh** from the current discovery and stored rooms.
The plan on screen is not necessarily the plan that would apply.

`plan_migration` builds the new id-keyed map **fresh from the discovered set** rather than
re-keying the stored map in place. Discovered ids are unique, so building fresh is collision-free
by construction; re-keying is not, when a re-segment reuses ids across rooms.

> ⚠ **A 1-and-1 leftover is paired unconditionally, and the pairing is not an identity.**
> After the slug and id passes, `compute_reconciliation` takes any single unmatched stored room
> and single unmatched discovered room and emits a `renamed_and_renumbered` review. **There is no
> similarity test of any kind** — no name or slug comparison, no geometry, no area.
>
> A stored room deleted plus an unrelated room added in the same re-map produces exactly that
> shape. `plan_migration` mirrors the pairing and acts on it: `carried = dict(source)` copies every
> durable setting onto the new id, and `id_remap` rewrites `grants_access_to` across the access
> graph so the new room inherits the old one's position in it.
>
> The comment above the branch states the justification as a guarantee — *"they can only be each
> other"* — which the code cannot support. What limits the damage is that this is a review the
> user confirms; what the review does is present a fabricated identity **as a determination**.
> Open as ledger `C55`; the remedy is not obvious, because refusing to pair loses the genuine
> rename-and-renumber this branch exists to catch.

---

## 6. Repairing what is already stored

`rooms/vocabulary_migration.py` is a one-shot, declaration-driven DROP/RESET pass over
`data["maps"]`, latched in `data["migrations"]`.

**It acts only on a declaration being present, and the two absences mean different things.**
Absence of a `{field}_options` list is a *capability* statement; absence of the field's whole
vocabulary is an *axis* statement. Roborock withholds `water_level_options` on models whose mop is
not settable — conflating the two strips `water_level` and `clean_mode` from every room on an S6.

**RESET consults the brand's declared alias table before falling back**, and refuses to pick a
nearest option. The predecessor folded the retired Eufy values `standard`/`normal` to `"Quick"`
from a hard-coded map, on every read, from nine call sites. `"Quick"` is the *fastest* density and
`"Standard"` was the *middle* one, so the fold silently moved every affected room to a different
density — invisibly, because the result was a valid value.

An alias pointing at a value the brand does not declare is **ignored rather than written**, and a
brand whose own `default_profile` value is not in its own declared set is left alone. Both are
adapter defects; writing through them puts an undeliverable value on a room and hides the defect
that produced it.

**The latch is set only when every target reached a terminal disposition** — a target being a
vacuum that has stored rooms. Two alternatives were tried and both are in the history: an
unconditional latch, and latching as soon as a single declaration was found. The unconditional
one fails on a normal cold boot, where the vacuums' own integrations have not finished setting up:
every vacuum is skipped for want of a declaration, the pass marks itself done, and the rooms it
existed to heal keep bad values permanently — silently, because the skip logs at DEBUG.

---

## 7. Guards on the write path

Three, and they guard different things.

| guard | refuses | why not wider |
|---|---|---|
| `rooms/room_crud.py::_refuse_destructive_replace` | an **empty** map replacing a non-empty stored one | discovery legitimately returns partial lists — blank segments are skipped at admission — so refusing every shrink refuses normal operation |
| the empty-discovery cache keep | overwriting a good discovery cache with zero rooms | `save_managed_rooms` reads *from* that cache, so an empty cache propagates into an empty stored map on the next save |
| map-scoped rejections | a rejection that does not know its map reaching a write | the vacuum-wide union would let a rejection on floor 1 drop a real room on floor 2 |

The shrunk-but-non-empty case is delegated to a second, looser guard inside `reconcile_room`. And
`_refuse_destructive_replace` compares against the **stored** map, not the discovery input.

**A rejection refuses a room's creation; it never deletes one.** The skip is gated on
`not existing.get("is_configured")`. A live install carried `rejected_rooms=[10]` beside a
configured room 10 on a *later* map, because the exclusion had never been wired — turning it on
without the gate converts a dormant stale entry into an active room-deleter.

**`is_configured` is stamped only on calls that pass `enabled_room_ids`.** Approval and floor type
arrive together from one wizard submission, so "approved but no floor type" is a real gap there; a
call not passing `enabled_room_ids` is not asking an approval question at all, and a
previously-confirmed room stays confirmed.

> ⚠ **This was ASPIRATIONAL until 2026-08-24.** The `enabled_room_ids is None` branch stamped
> `is_configured = True` unconditionally, so a room the user had never seen was approved by a bare
> re-sync — `save_managed_rooms` with the key omitted, which `services.yaml` and
> [the service reference](../advanced/03-services.md) both document as the way to keep the current
> selection unchanged. Because `is_configured` is the entity-creation gate AND the input to
> `compute_room_drift`'s new-room candidates, the room got entities and could never appear in the
> "new room found" review. **RULED (Chris, 2026-08-24): a re-sync approves nothing new.** A
> genuinely-new room on an incremental save is now left unconfirmed; a carried room keeps its
> approval unchanged.

---

## 8. Removing a map

`remove_map` clears per-map stores by iterating `PER_MAP_STORES` rather than a hand-written
sequence — which is what it was, and which silently missed `run_profiles`, `queue` and
`onboarding` for as long as those existed. `active_jobs` is **reset** to a default state rather
than deleted, because callers index a known vacuum/map pair without a presence check.

**It performs no cross-map access-graph cleanup, and that is correct.** `grants_access_to` holds
bare room ids scoped to a single map — identity is vacuum + map + room — and every consumer
resolves them only against that same map's room set. A grant on a surviving map cannot reach a
deleted map's rooms, so there is nothing to sweep.

---

## 9. Common wrong assumptions

| assumption | actually |
|---|---|
| room-history is invalidated because it re-ingests under the new ids | the ingest keys on the raw numeric id from the job file and never reads the slug |
| `PER_MAP_STORES` has a second consumer — an id-remap walker | there is no such walker; `remove_map` is its only consumer, and the two id-remap sites are hand-written |
| `rebuild_map` is a live CRUD operation alongside `save_managed_rooms` | it has zero production callers — a delegate, tests and comments only, and it is in no service |
| passing `None` for new-room defaults resolves a framework catalog | there is no framework catalog; `None` yields a single `profile_name` and nothing else |
| every room returned by `save_managed_rooms` carries `is_configured: True` | not since CRUD-3 — a selected room with no matching floor-type entry and no prior confirmation gets `False` |
| a call with no `enabled_room_ids` is always a re-sync of an already-approved map | the first import of a map — before any user has seen the room list — is also one |
| an ambiguous slug is never guessed at, anywhere in the cluster | true in two of the three copies; reconciliation's two builders are still first-wins |
| the numeric `room_id` is the room | it is the device's segment number and it renumbers; the slug is the identity |

---

## Registries

[00b-invariants.md](00b-invariants.md) · [00c-replicas.md](00c-replicas.md)
