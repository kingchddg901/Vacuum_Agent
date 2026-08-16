# 17 — Services — Subsystem Test Map

The services subsystem is the HA service-call layer: thin async handlers that
resolve call data, delegate to the manager, and wrap failures as
`HomeAssistantError` / `ServiceValidationError` (the HA Silver action-exception
contract). Covered by **229 tests across 14 files**.

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

| Source module | Stmts | Cov | Test file | Mocking |
|---------------|------:|----:|-----------|-------|
| `job_control.py` | 142 | 98% | `test_services_job_control_read.py`, `test_services_job_control_write.py` | **bare x10** |
| `run_profiles.py` | 104 | 98% | `test_services_run_profiles.py` | **bare x1** |
| `adapter_config.py` | 101 | 96% | `test_services_adapter_config.py` | clean |
| `setup.py` | 183 | 75% | `test_services_errors_setup.py` | **bare x2** |
| `dock.py` | 80 | 100% | `test_services_dock.py` | **bare x5** |
| `room_profiles.py` | 81 | 100% | `test_services_room_profiles.py` | clean |
| `rooms.py` | 108 | 98% | `test_services_rooms.py` | **bare x1** |
| `maintenance.py` | 47 | 100% | `test_services_maintenance_reset.py` | clean |
| `queue.py` | 121 | 100% | `test_services_queue.py` | **bare x1** |
| `snapshots.py` | 43 | 100% | `test_services_snapshots.py` | clean |
| `errors.py` | 37 | 95% | `test_services_errors_setup.py` | **bare x2** |
| `access_graph.py` | 34 | 88% | `test_services_access_graph.py` | clean |
| `_common.py` | 43 | 96% | `test_services_common.py`, `test_services_misc.py` | clean |
| `stall_capture.py` | 43 | 37% | — | - |
| `debug.py` | 8 | 100% | `test_services_misc.py` | clean |

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

`queue.py` (77%) is now the real gap in this subsystem, not a defensive tail —
this campaign added the queue **breaks/steps** service handlers
(`_handle_get_queue_steps`, `_handle_add_queue_break`,
`_handle_remove_queue_break`, `_handle_clear_queue_breaks`,
`_handle_set_queue_breaks`, `_handle_add_queue_zone`, missing lines 202-244)
and their `register()` closures (missing lines 266-281) — none of them are
exercised by `test_services_queue.py`. The handler bodies are thin delegators
to the manager (`get_manager(hass).<method>(**resolved_call_data(...))` +
`async_save()`), so this is closer to an untested wrapper than untested logic,
but it is a real gap, not a documented-defensive one — flagged here rather
than characterized as intentional. (Line 62 is a genuinely defensive
`isinstance` guard in a payload-normalization helper, unrelated to the above.)

The remaining misses elsewhere are still almost all defensive, not untested
behavior, though line numbers have shifted with the campaign's growth:

- **`manager is None` early-returns (defensive)** — the runtime-not-available
  guards at the top of several `setup.py` handlers (missing lines 64, 114,
  187, 190, 237, 264, 303, 335-338, 344-345, 356, 375, 425), plus
  `adapter_config.py`'s missing lines 67, 116. Unreachable in the
  fixture-registered service set, intentionally uncovered.
- **`access_graph.py` (88%)** — missing lines 89-91, 104: defensive guards,
  not yet re-itemized by name this pass.
- **Registered-wrapper closures (trivial)** — `rooms.py` missing line 270 (a
  wrapper/`vol.Required` false-arm the registered service can't reach).
- **`_common.py` (96%)** — missing line 138, a single defensive guard.

Module coverage: `queue.py` 77% (see above), `setup.py` 86%,
`access_graph.py` 88%, `adapter_config.py` 96%, `_common.py` 96%,
`errors.py` 95%, `rooms.py` 98%; `dock.py`, `room_profiles.py`,
`maintenance.py`, and `snapshots.py` are at 100%.
