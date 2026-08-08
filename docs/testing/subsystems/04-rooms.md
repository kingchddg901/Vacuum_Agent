# 04 — Rooms — Subsystem Test Map

The rooms subsystem owns room discovery, the managed-room CRUD lifecycle, and the
**access graph** (which rooms grant cleaning access to which, plus the rule
engine that gates/modifies rooms at start). Covered by **288 tests across 11 files**.

Source: `custom_components/eufy_vacuum/rooms/`
Architecture reference: [docs/dev/08-rooms-system.md](../../dev/08-rooms-system.md), [docs/dev/09-room-rules-system.md](../../dev/09-room-rules-system.md)


### `vocabulary_migration.py` — the one-shot repair (added 2026-08-07)

Removing the framework's Eufy-shaped profile default is prophylactic: a stored
per-room field outranks the profile, so rooms already on disk keep the bad value
indefinitely. This module is the curative half, run once after adapter
registration (it needs each brand's DECLARATION, which does not exist until
then, so it cannot be a versioned store migration).

Two rules, both declaration-driven: **DROP** a field no declared profile carries,
**RESET** a value absent from the brand's declared options to that brand's
`default_profile` value. No nearest-match — the option lists are declared sets
with no ordering to be nearest in.

`test_vocabulary_migration.py` (18 tests) weights the refusals as heavily as the
repairs, because this rewrites real user rooms and an over-reach is silent:

| id | what it holds |
|---|---|
| `MIG-1` / `MIG-2` | DROP an undeclared axis; RESET an out-of-vocabulary value |
| `MIG-2b` | RESET takes the DECLARED default, never the lexically nearest option |
| `MIG-3` | a correct room comes through byte-identical |
| `MIG-4` | a vacuum whose adapter declares nothing is skipped, never guessed at |
| `MIG-5` | **the check that averted a destructive migration** — see below |
| `MIG-6` | a brand whose own default is invalid is reported, not worked around |
| `MIG-7` | idempotent; a user's deliberate re-edit is not "repaired" on next boot |
| `MIG-8` | planning is pure, so the change can be reviewed before it runs |
| `MIG-9` | the retired-value fold is subsumed with NO retired-value map |
| `MIG-10a` | a retired value the brand still ALIASES keeps its meaning, not the default |
| `MIG-10b` | with no alias it still falls back to the brand's default |
| `MIG-10c` | an alias pointing at an undeclared option is ignored, never written |
| `MIG-11` | **a run that could not evaluate every target does not latch** — see below |

**MIG-5 is the one to read.** An early draft keyed DROP on "the brand declares no
options for this field". That reads correct and would have stripped `clean_mode`
and `water_level` from every room on a Roborock S6 — which declares no options for
them because its mop is not settable, not because the axis does not exist. Absence
of an OPTION LIST means "cannot judge"; only absence from the brand's own PROFILES
means "no such axis". Caught by enumerating the live store before the rule was
written: a guard that newly activates over existing data must be measured against that
data first, because passing your own tests says nothing about what is already on disk.

**The DROP must also be durable, and originally was not.** Found on hardware
2026-08-08: the migration correctly dropped `clean_intensity` from all ten Roborock
rooms, and then a plain save of every room put it straight back as `""`.
`normalize_room_profile` always emits all nine `ProfileRecord` keys and
`_finalize_room_update` writes that result to the room, so the repair was being undone
one room at a time — inert (empty, never dispatched, no control rendered), which is
precisely why it would have gone unnoticed until the axis quietly existed everywhere
again. `_finalize_room_update` now strips undeclared axes on save using the SAME
discriminator (`room_profiles.declared_profile_fields`), so the two paths cannot
diverge again. Pinned by `PM-30` / `PM-30b` in `test_profiles_manager.py`, both
mutation-verified.

**MIG-11 separates "could not evaluate yet" from "completed", which the one-shot
originally conflated.** The flag was set unconditionally, so a run that repaired
nothing still burned the single opportunity. That is reachable on an ordinary cold
boot: adapters are registered from vacuum entities owned by OTHER integrations, and if
those have not finished setting up, every vacuum is skipped for want of a declaration —
the same branch MIG-4 exercises, which pinned the skip but never what the skip did to
the flag. Found on hardware 2026-08-08: two full restarts repaired nothing, and a
config-entry reload — by which point the vacuums existed — repaired all twenty rooms.

The invariant is that a migration is complete only when **every** target it is
responsible for has reached a terminal disposition; missing runtime information is
DEFERRED, never SUCCESS. `MIG-11` pins all three states, and the middle one is the
subtle one: with two vacuums on two providers, latching as soon as *any* declaration
appears repairs the ready brand and abandons the slower one permanently. A vacuum with
no stored rooms is not a target, so an empty install latches vacuously instead of
rescanning forever. Both wrong answers are mutation-verified — restoring the
unconditional latch reddens two of the three, and restoring "latch if any adapter
answered" reddens the partial-readiness case alone.

Deferral only helps if the work later happens, and HA offers no "after that
integration" hook to wait on. The call site therefore runs the repair from
`async_at_started` rather than inline in `async_setup_entry` — it fires once everything
has set up, and fires immediately when HA is already running, so a live reload still
repairs promptly. `listeners/discovery.py` already used that primitive for the same
reason (`get_maps` is not registered at setup time); this call site was its forgotten
sibling.

**MIG-9 is why `normalize_clean_intensity` could be deleted rather than moved.**
It folded the retired Eufy values `standard`/`normal` to `"Quick"` on every read,
from nine call sites, to repair data written before 2026-07-26 — and that data was
still on disk twelve days later, because rooms are only rewritten when edited. The
migration needs no retired-value map to subsume it: `Standard` is simply absent
from Eufy's declared `clean_intensity_options`, so the generic RESET catches it and
Eufy's own `default_profile` supplies `Quick`. Same answer, from a declaration.

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `access_graph.py` | 460 | 94% | `test_access_graph.py`, `test_manager_rooms.py` | integration | clean |
| `room_crud.py` | 153 | 97% | `test_room_crud.py`, `test_manager_rooms.py` | integration | **bare x1** |
| `room_discovery.py` | 125 | 93% | `test_room_discovery.py` | integration | clean |
| `reconciliation.py` | 148 | 78% | `test_rooms_reconciliation.py` (unit), `test_rooms_reconcile.py` | integration | **bare x1** |
| `source_refresh.py` | 139 | 88% | `test_rooms_source_refresh.py` (unit) | unit | clean |
| `room_manager.py` | 82 | 96% | `test_room_manager.py` (unit) | unit | clean |
| `room_defaults.py` | 21 | 96% | `test_room_manager.py` (unit) + `test_adapter_contract.py` | unit | clean |
| `utils.py` | 3 | 100% | `test_rooms_utils.py` (unit) | unit | clean |
| `vocabulary_migration.py` | 68 | — | `test_vocabulary_migration.py` (unit) | unit | clean |

(Room-facing services live in [17 — services](17-services.md):
`test_services_rooms.py`, `test_services_access_graph.py`.)

---

## What's tested

- **Access graph** (`AG`) — grants normalization (dedup, self-exclude, invalid),
  rule normalization, full validation across every structural issue type
  (cycle / duplicate / missing / self-reference / multiple-inbound), graph-state
  classification, the room-rule match operators (exists / on-off / in / numeric),
  health report, and the **editable-target selectability** builder
  (`get_room_access_editor`): a target whose edge would close a loop is
  not-selectable with a reason; an illegal-but-unnamed-here candidate falls back
  to the generic legality reason.
- **CRUD** (`RC`) — `discover_rooms` (runs discovery, caches payload, points the
  runtime at the active map), `save_managed_rooms`, `get_managed_rooms`,
  `rebuild_map`, and `remove_map` including the cleanup tail (history / rule-status
  / active-job slots cleared, remaining maps' grant lists walked).
- **Discovery** (`RD`) — adapter-config-driven room extraction: active-map id
  resolution, normalize + dedup + skip-bad-row, payload wrapping.
- **Reconciliation** (`RR`) — `compute_reconciliation` slug-vs-id identity-shift
  detection (`id_changed` when a known slug carries a new segment id;
  `renamed` when a known id carries a new name/slug), int-coercion and
  slug-derivation guards, and `plan_migration` producing the data move a
  confirmed review applies (the manager owns the dict mutation; this module is
  pure). New/removed rooms are deliberately out of scope (owned by
  `setup/drift.py`).
- **New-room defaults** (`room_defaults.py`, via `test_room_manager.py` +
  the adapter contract suite) — `resolve_new_room_defaults` is THE single
  answer for what a freshly-created room starts with (it replaced four
  independently hand-maintained copies of the Eufy literals), resolved through
  the adapter so a Roborock room is not created with Eufy display vocabulary;
  `build_managed_rooms` takes the result as a **required** `new_room_defaults`
  argument (a permissive default there would re-open the hole).
- **Source refresh** (`SR`) — the `service_response` discovery source (Roborock
  `get_maps`): `flatten_maps_response` normalizes `{segment_id: name}` into the
  same list-of-dicts shape the attribute source carries (keyed by map name),
  `async_refresh_room_source` calls the service at the async boundaries and
  caches it, and `get_cached_room_source` is what the sync discovery path reads
  instead of an entity attribute.

---

## How it's tested

`AccessGraphManager(data, hass)` over a hand-built `data["maps"]` tree with
`_room(...)` / `_rooms(...)` helpers; `RoomMapManager` against a MagicMock
manager for pure CRUD and the real `manager` fixture where discovery needs live
`hass` states.

---

## Known gaps

`reconciliation.py` (78%) is currently the thin spot in this subsystem — well
below the others. Its uncovered branches (missing lines 44-45, 93, 118, 123,
175-177, 190-192, 226, 258, 262, 295-305, 317, plus the paired branch misses at
those same sites) are concentrated in three real behavior arms, not defensive
plumbing:
- the `renamed_and_renumbered` single-unmatched-pair review (the
  `len(unmatched_existing) == 1 and len(unmatched_discovered) == 1` branch
  around line 175),
- the matching single-pair settings **carry-forward** in `plan_migration`
  (the `leftover_existing_slugs`/`unmatched_discovered` single-match branch
  around line 295 — the old id's durable settings moving onto the new id),
- and the dismissed-plan-token short-circuit (`dismissed_at is not None and
  reviews and dismissed_plan_token is not None`, line 190).
These are the natural next tests for this subsystem — run
`--cov-report=term-missing` on `rooms/reconciliation.py` for the current line
list before adding them, since the exact numbers will keep moving as the file
changes.

`access_graph.py` (94%) and `room_discovery.py` (93%) leave mostly
type-coercion fallbacks and duplicated skip-bad-row branches — the `(TypeError,
ValueError)` `except` blocks themselves are covered; what is not is the
*fallback* arms that replace a non-list / non-dict input with `[]` / `{}` and
the `continue` skip-bad-row guards repeated across the graph walkers
(`access_graph.py` missing lines 154, 160, 211, 246, 287, 290, 500, 503, 521,
849, 852, 858, 864, 1100, 1112; `room_discovery.py` missing lines 147, 235,
240, 248, 252, 264, 280, 286). These are normalization plumbing, not behavior.

One genuine but minor behavior branch remains untested:
`access_graph.py` around lines 685-698 — the per-issue-type editable-target
reason strings (duplicate / missing / self-reference / multiple-inbound) in
`get_room_access_editor`. The editor is tested for the loop reason and the
generic legality fallback (see "What's tested"); the four named per-type reason
strings are deliberately left unexercised — they are unreachable elif-arms
already covered by the generic-fallback test. Also uncovered: one
effectively-unreachable cycle-DFS artifact (`access_graph.py` ~964, the
`cycle_chain = [room_id]` else branch) and the `_single_cached_map_id`
non-list-of-dicts-segments guard (`return None`) in `room_discovery.py`
(147) — part of the issue-#46 single-map anchor fallback, not
pragma-excluded.

(Exact line numbers above are from a fresh coverage run against this
worktree's revision and will drift as the modules change — treat the
*shape* of each gap, not the line number, as the durable fact.)
