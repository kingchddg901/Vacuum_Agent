# 04 — Rooms — Subsystem Test Map

The rooms subsystem owns room discovery, the managed-room CRUD lifecycle, and the
**access graph** (which rooms grant cleaning access to which, plus the rule
engine that gates/modifies rooms at start). Covered by **276 tests across 10 files**.

Source: `custom_components/eufy_vacuum/rooms/`
Architecture reference: [docs/dev/08-rooms-system.md](../../dev/08-rooms-system.md), [docs/dev/09-room-rules-system.md](../../dev/09-room-rules-system.md)

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
