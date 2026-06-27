# 04 — Rooms — Subsystem Test Map

The rooms subsystem owns room discovery, the managed-room CRUD lifecycle, and the
**access graph** (which rooms grant cleaning access to which, plus the rule
engine that gates/modifies rooms at start). Covered by **187 tests across 9 files**.

Source: `custom_components/eufy_vacuum/rooms/`
Architecture reference: [docs/dev/08-rooms-system.md](../../dev/08-rooms-system.md), [docs/dev/09-room-rules-system.md](../../dev/09-room-rules-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `access_graph.py` | 404 | 94% | `test_access_graph.py`, `test_manager_rooms.py` | integration |
| `room_crud.py` | 116 | 99% | `test_room_crud.py`, `test_manager_rooms.py` | integration |
| `room_discovery.py` | 96 | 94% | `test_room_discovery.py` | integration |
| `reconciliation.py` | 112 | 86% | `test_rooms_reconciliation.py` (unit), `test_rooms_reconcile.py` | integration |
| `source_refresh.py` | 94 | 91% | `test_rooms_source_refresh.py` (unit) | unit |
| `room_manager.py` | 40 | 100% | `test_room_manager.py` (unit) | unit |
| `utils.py` | 3 | 100% | `test_rooms_utils.py` (unit) | unit |

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

`access_graph.py` (94%) and `room_discovery.py` (94%) leave mostly
type-coercion fallbacks and duplicated skip-bad-row branches — the `(TypeError,
ValueError)` `except` blocks themselves are covered; what is not is the
*fallback* arms that replace a non-list / non-dict input with `[]` / `{}`
(`access_graph.py` 120, 126, 177, 687) and the `continue` skip-bad-row guards
repeated across the four graph walkers (`access_graph.py` 212, 246/249, 430/433,
678/681/693; `room_discovery.py` 152, 158, 163, 165, 172). These are normalization plumbing,
not behavior. Also uncovered: a defensive missing-room-id skip
(`access_graph.py` 451), one effectively-unreachable cycle-DFS artifact
(`access_graph.py` 793, the `cycle_chain = [room_id]` else branch), and the
`# pragma: no cover` missing-entity return in `room_discovery.py` (133).

One genuine but minor behavior branch remains untested:
`access_graph.py` 573/575/577/579 — the per-issue-type editable-target reason
strings (duplicate / missing / self-reference / multiple-inbound) in
`get_room_access_editor`. The editor is tested for the loop reason and the
generic legality fallback (see "What's tested"); the four named per-type reason
strings are deliberately left unexercised — they are unreachable elif-arms
already covered by the generic-fallback test. (The full-entity-id room-list
resolution path in `room_discovery.py` 126–130 — an adapter declaring a
`room_list_entity` other than `"vacuum_entity"` — is now covered by RD-6 in
`test_room_discovery.py`.)
