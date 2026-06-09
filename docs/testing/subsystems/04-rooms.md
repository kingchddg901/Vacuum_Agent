# 04 — Rooms — Subsystem Test Map

The rooms subsystem owns room discovery, the managed-room CRUD lifecycle, and the
**access graph** (which rooms grant cleaning access to which, plus the rule
engine that gates/modifies rooms at start). Covered by **116 tests across 6 files**.

Source: `custom_components/eufy_vacuum/rooms/`
Architecture reference: [docs/dev/08-rooms-system.md](../../dev/08-rooms-system.md), [docs/dev/09-room-rules-system.md](../../dev/09-room-rules-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `access_graph.py` | 404 | 94% | `test_access_graph.py`, `test_manager_rooms.py` | integration |
| `room_crud.py` | 88 | 97% | `test_room_crud.py`, `test_manager_rooms.py` | integration |
| `room_discovery.py` | 68 | 92% | `test_room_discovery.py` | integration |
| `room_manager.py` | 40 | 100% | `test_room_manager.py` (unit) | unit |
| `utils.py` | 2 | 100% | `test_rooms_utils.py` (unit) | unit |

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

---

## How it's tested

`AccessGraphManager(data, hass)` over a hand-built `data["maps"]` tree with
`_room(...)` / `_rooms(...)` helpers; `RoomMapManager` against a MagicMock
manager for pure CRUD and the real `manager` fixture where discovery needs live
`hass` states.

---

## Known gaps

`access_graph.py` (94%) and `room_discovery.py` (90%) leave defensive
`(TypeError, ValueError)` coercion guards and a few `continue` skip-bad-row
branches — normalization plumbing, not behavior.
