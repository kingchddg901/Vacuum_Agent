# Dock — Subsystem Test Map

The dock subsystem owns mop-wash / mop-dry / dust-empty actions: it resolves the
upstream button entity per action, **gates** each action against capability,
dock state, and job state, dispatches the gated action, and records dock-event
timestamps + debounced counters. Covered by **18 tests in 1 file**.

Source: `custom_components/eufy_vacuum/dock/`
Architecture reference: [docs/dev/14-dock-manager.md](../../dev/14-dock-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `manager.py` | 165 | 97% | `tests/integration/test_dock_manager.py` | integration |

(`__init__.py` is trivial; the dock *services* layer is covered separately by
`tests/integration/test_services_dock.py`.)

---

## What's tested (`DK`, integration)

- **Helpers** — `_safe_int`, `_display_label`.
- **Event recording** — `record_dock_event` (timestamp + counter increment, with
  the per-event debounce that blocks a double-count), the `last_dry_start`
  duration field, `set_dock_event_count` (overwrite + unknown-type error), and
  `get_dock_events`.
- **The gating engine** — `get_dock_action_status` across every branch:
  `ready`, `unsupported_feature`, `missing_action_entity`, `job_active`,
  `not_docked`, the action-specific `already_washing` / `already_drying` /
  `not_drying` / `already_emptying`, and `dock_busy` (adapter
  `hard_service_states`).
- **Dispatch** — `_async_run_dock_action` + the four `async_*` wrappers: an
  allowed action presses the button (`performed=True`), a gated action returns
  `performed=False` with the gate reason.
- **Entity resolution** — `_get_dock_action_entity` resolves a present button
  from the adapter's `dock_events.action_buttons` (the test registers a config
  with `entity_suffixes`); an action absent from that map resolves to `None`.

---

## How it's tested

`DockManager(manager)` against the real `manager` fixture. The gating engine
calls three manager methods (`get_vacuum_capabilities`, `get_lifecycle_state`,
`get_active_job`) plus `_get_dock_action_entity`; a `_ready(...)` helper
**monkeypatches all four** to a baseline "ready" context, and each test overrides
one field to drive a single gate branch. Dispatch tests register a fake
`button.press` service and assert it was (or wasn't) called.

---

## Known gaps

`manager.py` (92%) leaves the token-fallback path in `_get_dock_action_entity`
(`manager._find_button_entity_by_tokens`) and one debounce edge branch. Both are
reachable with more setup; the gating + dispatch + event logic is covered.
