"""The spec'd stand-in must actually REFUSE what a bare MagicMock accepted.

`spec_manager` exists to catch two specific failure modes, both of which reached
hardware green earlier in this project while the suite stayed fully green:

  - a manufactured ATTRIBUTE — `mgr.learning`, which the real manager does not
    have (it is `_get_learning_manager()`); a bare MagicMock invented it, so the
    test exercised a path production could never take.
  - a wrong CALL SIGNATURE — `_collect_finalization_inputs` invoked without three
    required keyword-only args; the permissive stub swallowed the TypeError and
    two live runs wrote no child records at all.

These tests are the guard on the guard. Without them a future refactor could
quietly turn `spec_manager` back into a permissive mock and nothing would fail.

Coverage targets
----------------
[SPEC-1] an attribute the real manager does not carry raises AttributeError.
[SPEC-2] a real method called with a bad signature raises TypeError.
[SPEC-3] a real method called correctly works and records the call.
[SPEC-4] instance attributes the class assigns at runtime are present.
[SPEC-5] the hand-maintained instance-attribute list is not STALE.
[SPEC-6] a bare MagicMock accepts all of the above — the control.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests._factories import _MANAGER_INSTANCE_ATTRS, spec_manager

_MANAGER_SRC = (
    Path(__file__).resolve().parents[2]
    / "custom_components" / "eufy_vacuum" / "core" / "manager.py"
)


def test_unknown_attribute_is_refused():
    """[SPEC-1] `learning` is THE name that bit — the real manager has no such
    attribute, and inventing it made a dead path look exercised."""
    mgr = spec_manager()
    with pytest.raises(AttributeError):
        mgr.learning
    with pytest.raises(AttributeError):
        mgr.method_that_does_not_exist


def test_wrong_call_signature_is_refused():
    """[SPEC-2] the failure mode that cost three deploy-and-run cycles."""
    mgr = spec_manager()
    with pytest.raises(TypeError):
        mgr.get_active_job("positional", "args", "the", "real", "one", "rejects")


def test_correct_call_is_allowed_and_recorded():
    """[SPEC-3] the guard must not be so tight that ordinary stubbing breaks."""
    mgr = spec_manager()
    mgr.get_active_job.return_value = {"status": "started"}
    out = mgr.get_active_job(vacuum_entity_id="vacuum.alfred", map_id="1")
    assert out == {"status": "started"}
    mgr.get_active_job.assert_called_once_with(
        vacuum_entity_id="vacuum.alfred", map_id="1"
    )


def test_runtime_instance_attributes_are_present():
    """[SPEC-4] `data` / `hass` / the subsystem handles are assigned in __init__ and
    async_initialize, so autospec cannot see them on the class. They are attached
    explicitly — production code reads them constantly."""
    mgr = spec_manager()
    assert mgr.data is not None
    assert mgr.hass is not None
    assert mgr.active_job is not None
    assert mgr.phase_runner is not None


def test_explicit_attrs_win_over_the_defaults():
    """[SPEC-4] a caller's own value is not clobbered by the default wiring."""
    sentinel = {"active_jobs": {}}
    mgr = spec_manager(data=sentinel)
    assert mgr.data is sentinel


def test_instance_attribute_surface_is_scraped_not_listed():
    """[SPEC-5] The surface is derived from the real module, so it cannot go stale.

    The first draft of this helper carried a hand-written list and omitted
    `_room_history_cache_ready` plus 15 others — 17 tests failed with nothing
    wrong in either the tests or production. A second source of truth about a
    class's own attributes is exactly the defect class this project keeps paying
    for, so there isn't one.
    """
    src = _MANAGER_SRC.read_text(encoding="utf-8")
    assert len(_MANAGER_INSTANCE_ATTRS) > 25, (
        f"the scrape found only {len(_MANAGER_INSTANCE_ATTRS)} attributes — it has "
        "probably stopped matching the source's assignment style"
    )
    for name in _MANAGER_INSTANCE_ATTRS:
        assert re.search(rf"^\s+self\.{re.escape(name)}\s*[:=][^=]", src, re.MULTILINE)
    # The names production depends on most, spot-checked so a regex that silently
    # matches nothing useful still fails.
    for essential in ("data", "hass", "active_job", "phase_runner"):
        assert essential in _MANAGER_INSTANCE_ATTRS


def test_scrape_does_not_invent_the_name_that_bit():
    """[SPEC-5] The scrape must not widen the surface back to permissive: the whole
    point is that `learning` is NOT among the names production assigns."""
    assert "learning" not in _MANAGER_INSTANCE_ATTRS


def test_async_methods_are_async_and_their_coroutines_are_consumed(recwarn):
    """[SPEC-7] autospec turns the manager's `async def` methods into AsyncMocks —
    which is the point (a caller that forgets to await now fails) but also means
    `hass.async_create_task(mgr._async_save_logged())` builds a REAL coroutine.

    A MagicMock `async_create_task` only records the call, so nothing consumes it
    and Python warns at GC time — attributed to whatever test was running then,
    not the one that caused it. The stand-in closes it, as production's scheduler
    effectively does.
    """
    import gc

    mgr = spec_manager()
    mgr.hass.async_create_task(mgr._async_save_logged())
    gc.collect()
    assert not [w for w in recwarn if "never awaited" in str(w.message)]


def test_bare_magicmock_accepts_everything_control():
    """[SPEC-6] The control that gives the tests above meaning: a bare MagicMock
    invents the attribute AND takes the bad call without complaint. Every
    assertion below is the behaviour we are moving away from."""
    mgr = MagicMock()
    assert mgr.learning is not None                      # invented
    assert mgr.method_that_does_not_exist is not None    # invented
    mgr.get_active_job("wrong", "arity", "entirely")     # accepted
