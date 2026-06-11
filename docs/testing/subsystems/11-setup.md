# 11 — Setup — Subsystem Test Map

The setup subsystem owns the integration lifecycle around a config entry: the
guided setup workflow + progress, start-protection state, map deletion, and the
room-drift detector (new/removed segments since last check). Covered by **95 tests across 9 files**.

Source: `custom_components/eufy_vacuum/setup/` (+ `__init__.py` entry wiring)
Architecture reference: [docs/dev/15-setup-system.md](../../dev/15-setup-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer |
|---------------|------:|----:|------------|-------|
| `drift.py` | 181 | 88% | `test_setup_drift.py`, `test_setup_drift_deep.py` | integration |
| `workflow.py` | 56 | 97% | `test_setup_workflow.py`, `test_setup_workflow_deep.py` | integration |
| `status.py` | 61 | 93% | `test_setup_status.py` | integration |
| `delete.py` | 47 | 97% | `test_setup_delete.py` | integration |
| `protection.py` | 36 | 100% | `test_setup_protection.py` (unit) | unit |
| `__init__.py` | 0 | 100% | `test_init_setup.py`, `test_manager_setup.py` | integration |

---

## What's tested

- **Workflow** (`SW`) — `add_vacuum` (managed / blocked / already-done /
  no-manager) and `import_active_map` (discover + save). These are the only two
  functions in `workflow.py`.
- **Start protection** — the protection-status surface and its block reasons.
- **Drift** — new-segment / removed-segment detection vs the last recorded room
  set, including the deep threshold/guard branches.
- **Delete** — map deletion teardown and its remove summary.
- **Entry wiring** (`SD`) — `run_discovery_pass` and the manager-side setup
  helpers reachable without a full boot.

---

## How it's tested

The `manager` / `manager_with_services` fixtures plus `test_init_setup.py` for
the entry-level wiring. `protection.py` is pure and unit-tested.

---

## Known gaps

The top-level integration entry file `custom_components/eufy_vacuum/__init__.py`
(193 stmts, **90%**) is the largest remaining gap and is **integration-boot
territory**: `async_setup_entry` orchestration (battery-rebaseline service
registration, mapping-tracker position registration, subsystem wiring) only runs
under a full config-entry boot — a different test class than this suite. Note this
is *not* the setup-package `setup/__init__.py` shown in the table above, which is a
docstring-only file (0 stmts, 100%).

Within the subsystem package itself, the only real gap is `drift.py` (88%): its
missing lines are all defensive coercion guards — `isinstance(...)` bucket/room
type checks and `except (TypeError, ValueError): continue` room-id coercions in
`_list_configured_room_ids`, `_room_lookup`, `reject_rooms`, and
`run_discovery_pass`, plus the stale-history-pop cleanup line. These are
intentionally uncovered (defensive-by-design; covering them would mean feeding
malformed storage dicts purely to exercise the guard). `status.py` (93%) and
`workflow.py` (97%) likewise leave only a defensive `isinstance` bucket guard, a
multi-vacuum drift branch, and the no-manager-available early return. `delete.py`
(97%) and `protection.py` (100%) have no remaining gaps.
