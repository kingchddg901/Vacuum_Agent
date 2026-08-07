# 11 — Setup — Subsystem Test Map

The setup subsystem owns the integration lifecycle around a config entry: the
guided setup workflow + progress, start-protection state, map deletion, and the
room-drift detector (new/removed segments since last check). Covered by **140 tests across 9 files**.

Source: `custom_components/eufy_vacuum/setup/` (+ `__init__.py` entry wiring)
Architecture reference: [docs/dev/15-setup-system.md](../../dev/15-setup-system.md)

---

## Coverage map

| Source module | Stmts | Cov | Test files | Layer | Mocking |
|---------------|------:|----:|------------|-------|-------|
| `drift.py` | 305 | 84% | `test_setup_drift.py`, `test_setup_drift_deep.py` | integration | clean |
| `workflow.py` | 67 | 91% | `test_setup_workflow.py`, `test_setup_workflow_deep.py` | integration | **bare x1** |
| `status.py` | 82 | 96% | `test_setup_status.py` | integration | clean |
| `delete.py` | 59 | 95% | `test_setup_delete.py` | integration | clean |
| `protection.py` | 37 | 96% | `test_setup_protection.py` (unit) | unit | clean |
| `__init__.py` | 0 | 100% | `test_init_setup.py`, `test_manager_setup.py` | integration | **bare x4** |

---

## What's tested

- **Workflow** (`SW`) — `add_vacuum` (managed / blocked / already-done /
  no-manager) and `import_active_map` (discover + save). These are the only two
  functions in `workflow.py`.
- **Start protection** — the protection-status surface and its block reasons.
- **Drift** — new-segment / removed-segment detection vs the last recorded room
  set, including the deep threshold/guard branches and the configured-vs-discovered
  exclusion gate (a room in a bucket with `is_configured=False` is not drift-tracked).
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
(317 stmts, **92%**) is the largest remaining gap and is **integration-boot
territory**: `async_setup_entry` orchestration (battery-rebaseline service
registration, mapping-tracker position registration, subsystem wiring) only runs
under a full config-entry boot — a different test class than this suite. Note this
is *not* the setup-package `setup/__init__.py` shown in the table above, which is a
docstring-only file (0 stmts, 100%).

Within the subsystem package itself, `drift.py` (84%, grown from 193 to 305
statements this campaign) is now the largest gap — its missing lines
(239-240, 247, 250, 384-446, 524-529, 606-614, 689-731, 795-894; run
`--cov-report=term-missing` for the current mapping to specific checks) are
substantially more numerous than the previously-described defensive coercion
guards alone, and have not been re-triaged line-by-line this pass; treat the
"defensive-by-design" characterization as directional, not exhaustive.
`status.py` (96%, missing 128, 263) and `workflow.py` (91%, missing 159, 164,
170, 204) still leave only a small handful of lines each — a defensive
`isinstance` bucket guard, a multi-vacuum drift branch, and the
no-manager-available early return. `delete.py` (95%, missing 163) and
`protection.py` (96%, missing 42) likewise have essentially no remaining gap.
