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
        manager.start_run_profile = AsyncMock()
        manager.get_saved_run_profiles.return_value = {"library": run_profile_data or {}}

    ``async_save`` and ``start_run_profile`` are ``AsyncMock`` so ``await`` +
    ``assert_awaited_once`` work — the latter is a coroutine on the real manager, so a
    caller that forgets to ``await`` it (issue #42) must fail the test, not silently pass;
    ``run_profiles`` preloads the saved-run-profile library. Extra keyword args are
    set as attributes on the mock, so the wired defaults stay constant while a test
    makes its own additions explicit at the call site.
    """
    manager = MagicMock()
    manager.async_save = AsyncMock()
    manager.reset_maintenance = MagicMock()
    manager.start_run_profile = AsyncMock()
    manager.get_saved_run_profiles.return_value = {"library": run_profiles or {}}
    for name, value in attrs.items():
        setattr(manager, name, value)
    return manager


# ---------------------------------------------------------------------------
# Spec'd stand-ins for classes WE own
# ---------------------------------------------------------------------------
# A bare MagicMock agrees with the CALLER, not the callee: it answers to any
# attribute the test asks for and accepts any argument list. That concealed four
# defects in one session, every one of which reached hardware green — the worst
# being `_collect_finalization_inputs` being called without three REQUIRED
# keyword-only args, where a permissive stub swallowed the TypeError and the run
# silently wrote no child records.
#
# `create_autospec` fixes the half that matters most: CALL SIGNATURES are checked
# against the real function, so a call production would reject is rejected here.
# It also refuses attribute names the class does not carry.
#
# What it does NOT know about is instance state — attributes assigned in
# `__init__` / `async_initialize` / lazily in a method are invisible on the class.
# Those are read straight out of the real module's source rather than listed by
# hand: a hand list is a second source of truth that goes stale silently, and the
# first draft of this helper proved it by omitting `_room_history_cache_ready`
# and 15 others, failing 17 tests that had nothing wrong with them.
#
# Scraping keeps the stand-in's surface EXACTLY the set of names production
# assigns — which is still a real guard, because a name production never assigns
# (`learning`, verified absent) is still refused.


def _scraped_instance_attrs(module_relpath: str) -> tuple[str, ...]:
    """Every ``self.<name> =`` assigned anywhere in one of our modules."""
    import re
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "custom_components" / "eufy_vacuum"
        / module_relpath
    ).read_text(encoding="utf-8")
    return tuple(sorted(set(
        re.findall(r"^\s+self\.([A-Za-z_][A-Za-z0-9_]*)\s*[:=][^=]", src, re.MULTILINE)
    )))


_MANAGER_INSTANCE_ATTRS: tuple[str, ...] = _scraped_instance_attrs("core/manager.py")


def spec_manager(**attrs: Any) -> Any:
    """A manager stand-in that rejects wrong call signatures and unknown names.

    Prefer this over ``MagicMock()`` wherever the mock is handed to production
    code as a manager — that is where a signature mismatch does damage. Use
    ``make_manager_mock`` instead when the subject is a platform ENTITY being
    driven against a deliberately partial stub.

    Note ``learning`` is absent from the scraped surface because the real manager
    genuinely never assigns it (it is ``_get_learning_manager()``), and a bare
    MagicMock manufacturing it is one of the four defects above. Reading
    ``mgr.learning`` off this stand-in raises, as it should.
    """
    from unittest.mock import create_autospec

    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    manager = create_autospec(EufyVacuumManager, instance=True)
    for name in _MANAGER_INSTANCE_ATTRS:
        if name not in attrs:
            setattr(manager, name, MagicMock())
    if "hass" not in attrs:
        manager.hass.async_create_task.side_effect = _consume_coroutine
    for name, value in attrs.items():
        setattr(manager, name, value)
    return manager


def _consume_coroutine(target: Any, *_args: Any, **_kwargs: Any) -> Any:
    """Close a coroutine handed to a mocked ``hass.async_create_task``.

    autospec makes the manager's ``async def`` methods AsyncMocks, so
    ``hass.async_create_task(self._manager._async_save_logged())`` now builds a
    REAL coroutine object. A MagicMock ``async_create_task`` only records the
    call, so nothing ever consumes it and Python emits "coroutine ... was never
    awaited" at garbage-collection time — attributed to whichever test happened
    to be running when the GC fired, not the one that caused it.

    Closing it here matches what production does (it really is scheduled) and
    keeps the suite's warning output empty, so the NEXT un-awaited coroutine is
    visible instead of lost in known noise.

    Deliberately does not run the coroutine: these are fire-and-forget saves, and
    executing them would give a stand-in side effects the test never asked for.
    """
    if hasattr(target, "close"):
        target.close()
    return MagicMock()
