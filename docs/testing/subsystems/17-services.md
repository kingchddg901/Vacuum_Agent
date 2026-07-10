# 17 — Services — Subsystem Test Map

The services subsystem is the HA service-call layer: thin async handlers that
resolve call data, delegate to the manager, and wrap failures as
`HomeAssistantError` / `ServiceValidationError` (the HA Silver action-exception
contract). Covered by **189 tests across 14 files**.

Source: `custom_components/eufy_vacuum/services/`
Architecture reference: [docs/dev/02-ha-integration.md](../../dev/02-ha-integration.md)

**Scope.** This doc covers only the `services/` package — the handlers wired by
`async_register_services`. The integration registers many more `eufy_vacuum.*`
services from sibling packages, and those are tested under their own subsystem
docs, not here:

- Map/segment/layout/live-pose services in `mapping/mapping_services.py`
  (registered via `async_register_mapping_services`) — see
  [07-mapping.md](07-mapping.md).
- Learning + external-run services in `learning/services.py` — see
  [06-learning.md](06-learning.md).
- Theme services in `themes/services.py` — see [14-themes.md](14-themes.md).

---

## Coverage map

| Source module | Stmts | Cov | Test file |
|---------------|------:|----:|-----------|
| `job_control.py` | 127 | 95% | `test_services_job_control_read.py`, `test_services_job_control_write.py` |
| `run_profiles.py` | 103 | 98% | `test_services_run_profiles.py` |
| `adapter_config.py` | 96 | 94% | `test_services_adapter_config.py` |
| `setup.py` | 128 | 91% | `test_services_errors_setup.py` |
| `dock.py` | 80 | 100% | `test_services_dock.py` |
| `room_profiles.py` | 80 | 100% | `test_services_room_profiles.py` |
| `rooms.py` | 95 | 96% | `test_services_rooms.py` |
| `maintenance.py` | 47 | 100% | `test_services_maintenance_reset.py` |
| `queue.py` | 43 | 100% | `test_services_queue.py` |
| `snapshots.py` | 43 | 100% | `test_services_snapshots.py` |
| `errors.py` | 37 | 95% | `test_services_errors_setup.py` |
| `access_graph.py` | 25 | 100% | `test_services_access_graph.py` |
| `_common.py` | 35 | 100% | `test_services_common.py`, `test_services_misc.py` |

---

## What's tested

- **Read services** — snapshots, job-control read, access-graph, saved profiles,
  dashboard snapshot: returned-shape assertions through the registry.
- **Write services** — job-control write, run-profile + room-profile + maintenance
  CRUD, queue build/clear, adapter-config set: side effects + persistence.
- **Input validation** — the `update_room_fields` color validator normalizes raw
  frontend input to canonical `#rrggbb` (`#rgb` expansion, hash-prepend, lowercase,
  empty → clear) and rejects non-hex values at the service-schema boundary.
- **Error contract** — a manager-layer failure surfaces as `HomeAssistantError`
  (run-profile save/apply/rename/overwrite/delete, maintenance reset, set-interval
  save path), and not-found conditions raise `ServiceValidationError`.
- **Call-data resolution + job-finished payload** (`_common`) — `resolved_call_data`
  map-id defaulting (incl. the no-active-map pass-through), and
  `job_finished_event_payload` built from a `finalize_result`-wrapped result.

---

## How it's tested

The `manager_with_services` fixture registers the full service set (same path as
`async_setup_entry`). Tests call `hass.services.async_call(DOMAIN, name, data,
blocking=True, return_response=True)`. Error-contract tests `monkeypatch` a
manager method to raise and assert the wrapped exception type.

---

## Known gaps

The remaining misses are almost all defensive, not untested behavior:

- **`manager is None` early-returns (defensive)** — the runtime-not-available
  guards at the top of `setup.py`'s `setup_get_map_rooms` / `setup_save_rooms` /
  `setup_reject_rooms` / `setup_force_remove_room` / `setup_set_panel_title` /
  `setup_set_map_camera` handlers, plus `adapter_config.py`'s
  `_handle_save_adapter_config` / `_handle_delete_adapter_config`, return a
  `{"status": "error"}` stub or log-and-return. Unreachable in the
  fixture-registered service set, intentionally uncovered.
- **Parse / shape fallbacks (defensive)** — `errors.py:84-85` (`limit` int-parse
  `except` → default 20). (`_common.py`'s non-dict `completed_job` guard and its
  `finalize_result`-shaped `job_path` extraction are now both covered.)
- **Registered-wrapper closures (trivial)** — `rooms.py:234`/`246`, the
  `discover_rooms` / `reconcile_room` inner async wrappers; the `_handle_*` they
  delegate to are exercised directly. (The two remaining `rooms.py` branch edges are
  the `vol.Required` `vacuum_entity_id` false-arms the registered service can't reach.)

Note `adapter_config.py:68-78` (missing `adapter_id` / missing `dispatch.template`
guards) are `# pragma: no cover` by design and so are excluded from the miss list.

Module coverage: `setup.py` 90%, `adapter_config.py` 94%, `errors.py` 95%,
`rooms.py` 96%; the remaining nine modules (including `run_profiles.py` and
`_common.py`, now at 100%) are at 100%. The handler success + error contracts
are covered.
