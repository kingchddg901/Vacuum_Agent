# 17 — Services — Subsystem Test Map

The services subsystem is the HA service-call layer: thin async handlers that
resolve call data, delegate to the manager, and wrap failures as
`HomeAssistantError` / `ServiceValidationError` (the HA Silver action-exception
contract). Covered by **158 tests across 14 files**.

Source: `custom_components/eufy_vacuum/services/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file |
|---------------|------:|----:|-----------|
| `job_control.py` | 115 | 100% | `test_services_job_control_read.py`, `test_services_job_control_write.py` |
| `run_profiles.py` | 89 | 100% | `test_services_run_profiles.py` |
| `adapter_config.py` | 96 | 94% | `test_services_adapter_config.py` |
| `setup.py` | 85 | 90% | `test_services_errors_setup.py` |
| `dock.py` | 80 | 100% | `test_services_dock.py` |
| `room_profiles.py` | 80 | 100% | `test_services_room_profiles.py` |
| `rooms.py` | 62 | 97% | `test_services_rooms.py` |
| `maintenance.py` | 47 | 100% | `test_services_maintenance_reset.py` |
| `queue.py` | 43 | 100% | `test_services_queue.py` |
| `snapshots.py` | 40 | 100% | `test_services_snapshots.py` |
| `errors.py` | 37 | 95% | `test_services_errors_setup.py` |
| `access_graph.py` | 25 | 100% | `test_services_access_graph.py` |
| `_common.py` | 35 | 89% | `test_services_common.py`, `test_services_misc.py` |

---

## What's tested

- **Read services** — snapshots, job-control read, access-graph, saved profiles,
  dashboard snapshot: returned-shape assertions through the registry.
- **Write services** — job-control write, run-profile + room-profile + maintenance
  CRUD, queue build/clear, adapter-config set: side effects + persistence.
- **Error contract** — a manager-layer failure surfaces as `HomeAssistantError`
  (run-profile save/apply/rename/overwrite/delete, maintenance reset, set-interval
  save path), and not-found conditions raise `ServiceValidationError`.
- **Call-data resolution** (`_common`) — `resolved_call_data` map-id defaulting.

---

## How it's tested

The `manager_with_services` fixture registers the full service set (same path as
`async_setup_entry`). Tests call `hass.services.async_call(DOMAIN, name, data,
blocking=True, return_response=True)`. Error-contract tests `monkeypatch` a
manager method to raise and assert the wrapped exception type.

---

## Known gaps

The remaining misses are almost all defensive, not untested behavior:

- **`manager is None` early-returns (defensive)** — `setup.py:147, 174, 204, 232`
  and `adapter_config.py:64-65, 103` are runtime-not-available guards that return
  a `{"status": "error"}` stub or log-and-return. Unreachable in the
  fixture-registered service set, intentionally uncovered.
- **Parse / shape fallbacks (defensive)** — `errors.py:84-85` (`limit` int-parse
  `except` → default 20), `_common.py:96` (non-dict `completed_job` guard) and
  `:101` (alternate `finalize_result`-shaped `job_path` extraction).
- **Registered-wrapper closure (trivial)** — `rooms.py:165`, the `discover_rooms`
  inner async wrapper; the `_handle_discover_rooms` it delegates to is exercised
  directly.

Note `adapter_config.py:68-78` (missing `adapter_id` / missing `dispatch.template`
guards) are `# pragma: no cover` by design and so are excluded from the miss list.

Module coverage: `setup.py` 90%, `adapter_config.py` 94%, `_common.py` 89%,
`errors.py` 95%, `rooms.py` 97%; the remaining eight modules (including
`run_profiles.py`, now at 100%) are at 100%. The handler success + error contracts
are covered.
