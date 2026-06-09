"""Shared test factories — behaviour-preserving builders for the duplicated
setup the suite has accreted.

These are *extractions*, not behaviour changes: each helper produces exactly the
data or effect the inline code it replaces produced, so a refactored test asserts
the identical thing. Conventions:

  - Defaults cover fields a test does NOT assert on. A test that asserts a field
    passes it explicitly, so "what's under test" stays visible at the call site.
  - Every entry point documents the inline snippet it replaces.

Importable from any test as ``from tests._factories import ...`` (``tests`` is a
package and the repo root is on ``sys.path`` the same way ``custom_components``
is).

Pilot scope: the room-scoped platform-entity helpers (used by ``test_switch_entity``
and ``test_number_entity``), a stub-manager builder (used by ``test_button_entity``),
plus the suite's standard identifiers. More builders are added per wave.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

# The suite's standard identifiers — `vacuum.alfred` is the canonical test
# vacuum (docs/testing/04), map "1", a fixed config-entry id.
VAC = "vacuum.alfred"
MAP = "1"
ENTRY_ID = "test_entry_id"


def get_room_data(
    manager: Any, room_id: int | str, *, vac: str = VAC, map_id: str = MAP
) -> dict:
    """Return the managed-room dict for one room, or ``{}`` when absent.

    Replaces the copy-pasted lookup chain (``test_switch_entity._make_switch``,
    ``test_number_entity._make_order_number``, …)::

        manager.data.get("maps", {}).get(VAC, {}).get(MAP, {})
               .get("rooms", {}).get(str(room_id), {})
    """
    return (
        manager.data.get("maps", {})
        .get(vac, {})
        .get(map_id, {})
        .get("rooms", {})
        .get(str(room_id), {})
    )


def set_room_field(
    manager: Any,
    room_id: int | str,
    *,
    vac: str = VAC,
    map_id: str = MAP,
    **fields: Any,
) -> dict:
    """Set field(s) on an existing managed room; return the room dict.

    Replaces inline writes such as::

        manager.data["maps"][VAC][MAP]["rooms"]["1"]["enabled"] = False

    The room must already exist (seed it via ``setup_map`` first); this mutates
    it in place exactly as the inline assignment did — it does not create rooms.
    """
    room = manager.data["maps"][vac][map_id]["rooms"][str(room_id)]
    room.update(fields)
    return room


# ---------------------------------------------------------------------------
# Manager mocks — for platform tests that drive entities against a stubbed
# manager rather than the real one (buttons, and later some sensors).
# ---------------------------------------------------------------------------

def make_manager_mock(*, run_profiles: dict | None = None, **attrs: Any) -> MagicMock:
    """Build a stub manager exposing the call surface platform entities touch.

    Faithful extraction of ``test_button_entity._make_manager``::

        manager = MagicMock()
        manager.async_save = AsyncMock()
        manager.reset_maintenance = MagicMock()
        manager.start_run_profile = MagicMock()
        manager.get_saved_run_profiles.return_value = {"library": run_profile_data or {}}

    ``async_save`` is an ``AsyncMock`` so ``await`` + ``assert_awaited_once`` work;
    ``run_profiles`` preloads the saved-run-profile library. Extra keyword args are
    set as attributes on the mock, so the wired defaults stay constant while a test
    makes its own additions explicit at the call site.
    """
    manager = MagicMock()
    manager.async_save = AsyncMock()
    manager.reset_maintenance = MagicMock()
    manager.start_run_profile = MagicMock()
    manager.get_saved_run_profiles.return_value = {"library": run_profiles or {}}
    for name, value in attrs.items():
        setattr(manager, name, value)
    return manager
