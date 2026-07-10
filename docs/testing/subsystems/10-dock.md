# 10 — Dock — Subsystem Test Map

The dock subsystem owns mop-wash / mop-dry / dust-empty actions: it resolves the
upstream button entity per action, **gates** each action against capability,
dock state, and job state, dispatches the gated action, and records dock-event
timestamps + debounced counters. Covered by **26 tests in 1 file**.

Source: `custom_components/eufy_vacuum/dock/`
Architecture reference: [docs/dev/14-dock-manager.md](../../dev/14-dock-manager.md)

---

## Coverage map

| Source module | Stmts | Cov | Test file | Layer |
|---------------|------:|----:|-----------|-------|
| `manager.py` | 167 | 97% | `tests/integration/test_dock_manager.py` | integration |

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
  with `entity_suffixes`); an action absent from that map resolves to `None`. A
  token-fallback test [DK-17] also exercises resolution of a differently-named
  button via the adapter's `token_sets` when no `entity_suffix` matches
  (firmware-naming drift).

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

`manager.py` (98%) has one uncovered line, a narrow fall-through branch:

- **Line 94** — inside `_get_dock_action_entity`, the registry-only arm of the
  `entity_suffixes` loop (`registry.async_get(entity_id)` matches an entity that
  is in the registry but not in `hass.states`). The states-present arm and the
  `token_sets` fallback are both covered ([DK-15], [DK-17]).

The `except Exception:` in `record_dock_event`'s debounce timestamp-parse
(malformed `*_last_counted_at`, line 392) is now covered:
`test_record_event_malformed_debounce_timestamp` [DK-2b] registers a non-zero
`debounce_seconds` and seeds an unparseable stored timestamp, so
`datetime.fromisoformat` raises and the recovery branch is genuinely exercised
(its `_LOGGER.debug` log body remains `# pragma: no cover`).

The remaining gap is a defensive recovery branch; the gating, dispatch,
entity-resolution (suffix + token fallback), and event-counting logic
(including malformed-timestamp recovery) are covered.
