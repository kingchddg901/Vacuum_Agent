# 03 — Queue — Subsystem Test Map

The queue subsystem turns the enabled-room set into an ordered clean queue: it
resolves room order, applies per-room overrides, and produces the
`queue_room_ids` / `queue_rooms` payload the job pipeline consumes. Covered by
**44 tests across 3 files**.

Source: `custom_components/eufy_vacuum/queue/`
Architecture reference: [docs/dev/07-queue-engine.md](../../dev/07-queue-engine.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `queue_engine.py` | 157 | 93% | `test_queue_engine.py` (unit), `test_manager_queue.py` | unit + int |
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

`queue_engine.py` (90%) leaves a couple of defensive `(ValueError, TypeError)`
coercion guards and an empty-branch fallback — defensive normalization, low
value to drive with crafted bad input.
