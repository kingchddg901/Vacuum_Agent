# 03 — Queue — Subsystem Test Map

The queue subsystem turns the enabled-room set into an ordered clean queue: it
resolves room order, applies per-room overrides, and produces the
`queue_room_ids` / `queue_rooms` payload the job pipeline consumes. Covered by
**47 tests across 3 files**.

Source: `custom_components/eufy_vacuum/queue/`
Architecture reference: [docs/dev/07-queue-engine.md](../../dev/07-queue-engine.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `queue_engine.py` | 157 | 95% | `test_queue_engine.py` (unit), `test_manager_queue.py` | unit + int |
| `dispatch_engines.py` | 78 | 95% | `test_dispatch_engines.py` (unit) | unit |

(The `build_queue` / `clear_queue` service surface is in
[17 — services](17-services.md) via `test_services_queue.py`.)

---

## What's tested

- **Pure ordering** (unit) — the queue-engine builder: ordering by `order`,
  enabled-only inclusion, override merge, and the empty-input fallback.
- **Manager integration** — `build_queue` / `get_queue_state` / `clear_queue`
  against the real manager with seeded managed rooms; the queue payload shape and
  the round-trip through `data["queue"]`.

---

## How it's tested

The pure builder is exercised in isolation in `test_queue_engine.py` (no `hass`).
The manager-level path uses the `manager` fixture + `setup_map(...)` to seed
rooms, then asserts the resolved queue.

---

## Known gaps

`queue_engine.py` (95%) — the remaining uncovered lines are defensive:

- the `typing_extensions` `TypedDict` import fallback (lines 9-10), unreachable on
  the shipped Python (3.14 has `typing.TypedDict`);
- the `room_id <= 0` skip guard in `build_room_clean_payload` (line 256);
- the `elif queue_room_ids:` `current_room_id` fallback in `build_active_job_state`
  (lines 372-373), reached only when `resolved_rooms` is empty but the queue ids
  are present.

The two **capability-gated per-room write branches** in `build_room_clean_payload`
— `edge_mopping` (line 296, under `supports_edge` + mop mode) and `path_type`
(line 299, under `supports_path`) — are now covered by `test_dispatch_engines.py`'s
DE-11b (`test_edge_and_path_per_room_writes_when_caps_enabled`), which declares
edge/path as real wire fields and asserts both per-room writes land on the wire.
No shipped adapter declares these fields, so DE-11b is the only path that drives
them.

`dispatch_engines.py` (95%) leaves line 303 — the `if cfg is None: continue` skip
in `DreameSegmentEngine`'s array transpose, the path where a canonical field is
simply not declared in `room_fields` (Dreame omits most). Defensive; the declared
and `field_name: None` cases are both covered.
