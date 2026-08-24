"""Phase 7 integration tests — services/clean_order.py.

These services edit a PERSISTENT, MAP-LEVEL setting in the vendor app, gated on the
Override Order switch. The tests below guard the invariants that make that safe:

Coverage targets
----------------
[COS-1]  apply refuses when the adapter does not declare the write (`unsupported`).
[COS-2]  clear refuses when the adapter does not declare the write (`unsupported`).
[COS-3]  apply refuses when the switch is OFF (`refused/override_off`), no wire call.
[COS-4]  clear reaches the manager regardless of switch state (Clear is EXPLICIT).
[COS-5]  each registered service dispatches through its closure to the matching
         manager method (service-name -> handler wiring, mirrors DK-13).
"""

from __future__ import annotations

from unittest.mock import create_autospec

import pytest

from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.eufy_vacuum.clean_order.manager import CleanOrderManager
from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.services.clean_order import (
    SERVICE_APPLY_CLEAN_SEQUENCE,
    SERVICE_CLEAR_CLEAN_SEQUENCE,
    _handle_apply,
    _handle_clear,
    register,
)


_VAC = "vacuum.ivy"


# WHY create_autospec RATHER THAN MagicMock, EXPLICITLY:
# A bare MagicMock().apply_current_queue(vac) returns another MagicMock and does not
# care what you called it. Typo the method name and every test passes. `create_autospec`
# reads CleanOrderManager's real signature and blows up on any call that does not match
# it -- which is the whole point of the wire being a wire (COS-1..COS-4 test that the
# service dispatches to the right method with the right shape).
#
# `spec_set=True` also refuses NEW attributes, so a test cannot silently prop up a
# fake `manager.clean_order.new_method` that does not exist on the real class -- the
# exact drift `tests/mock_ratchet.py` was built to prevent (docs/testing/04).
def _fake_hass(*, can_write: bool = True, apply_result=None, clear_result=None):
    """A hass whose CleanOrderManager is an autospec, so a method typo blows up."""
    clean_order = create_autospec(CleanOrderManager, spec_set=True, instance=True)
    clean_order.can_write.return_value = can_write
    clean_order.override_enabled.return_value = False  # OFF unless a test opts in
    clean_order.apply_current_queue.return_value = (
        apply_result or {"status": "unconfirmed", "order": [27, 25]}
    )
    clean_order.async_clear.return_value = (
        clear_result or {"status": "unconfirmed", "order": []}
    )

    # The manager stub is deliberately narrow: the handlers only reach for
    # `.clean_order` off `hass.data[DOMAIN]["runtime"]`. A larger surface would
    # invite tests to grow past what the code actually depends on.
    class _Manager:
        pass

    manager = _Manager()
    manager.clean_order = clean_order

    class _Services:
        def __init__(self):
            self.registered: list[tuple] = []

        def async_register(self, domain, name, handler, **kwargs):
            self.registered.append((domain, name, handler, kwargs))

    class _Hass:
        pass

    hass = _Hass()
    hass.data = {DOMAIN: {"runtime": manager}}
    hass.services = _Services()
    return hass, manager


def _call(hass, **data) -> ServiceCall:
    # HA's ServiceCall signature is (hass, domain, service, data, ...).
    return ServiceCall(hass, DOMAIN, "x", dict(data))


async def test_cos1_apply_reports_unsupported_when_no_write_declaration():
    """[COS-1] RED IF THE HANDLER TRUSTS THE CALLER.

    A service call for a vacuum whose adapter omits the write half of
    device_clean_order (a Roborock Qrevo, an unknown model, or a non-Roborock brand)
    must NOT reach `apply_current_queue`. Reporting `unsupported` is what makes the
    service safe for the card to offer without first probing capabilities.
    """
    hass, manager = _fake_hass(can_write=False)
    result = await _handle_apply(hass, _call(hass, vacuum_entity_id=_VAC))

    assert result == {"status": "unsupported", "order": None}
    manager.clean_order.apply_current_queue.assert_not_called()


async def test_cos2_clear_reports_unsupported_when_no_write_declaration():
    """[COS-2] Symmetric to COS-1. The card can offer Clear speculatively too."""
    hass, manager = _fake_hass(can_write=False)
    result = await _handle_clear(hass, _call(hass, vacuum_entity_id=_VAC))

    assert result == {"status": "unsupported", "order": None}
    manager.clean_order.async_clear.assert_not_called()


async def test_cos3_apply_forwards_the_managers_verdict_including_refused():
    """[COS-3] RED IF THE HANDLER 'HELPFULLY' RE-CLASSIFIES.

    The manager's own gate (`apply_current_queue` -> override_off) is the deciding one;
    the service is a thin wire. Re-classifying a refused with a reason into a bare
    "ok" or an exception would hide the exact condition the card renders around.
    """
    hass, manager = _fake_hass(
        apply_result={"status": "refused", "order": None, "reason": "override_off"}
    )
    result = await _handle_apply(hass, _call(hass, vacuum_entity_id=_VAC))

    assert result == {"status": "refused", "order": None, "reason": "override_off"}
    manager.clean_order.apply_current_queue.assert_awaited_once_with(_VAC)


async def test_cos4_clear_reaches_the_manager_regardless_of_switch_state():
    """[COS-4] Clear is EXPLICIT. The whole point is that the user can wipe the saved
    sequence without first flipping the switch on (that would be a strange ceremony).
    So Clear only checks `can_write`, never `override_enabled`.
    """
    hass, manager = _fake_hass()
    result = await _handle_clear(hass, _call(hass, vacuum_entity_id=_VAC))

    manager.clean_order.async_clear.assert_awaited_once_with(_VAC)
    assert result["status"] in {"ok", "unconfirmed"}


async def test_cos5_service_names_and_wiring():
    """[COS-5] Every declared service registers with a schema and supports_response.

    Response support is load-bearing: the card reads `status` and `order` off the
    return value to render the correct row state. A register that forgets it would
    leave every call returning None and the card silently stuck on stale local state.
    """
    hass, _ = _fake_hass()
    register(hass)

    names = [name for (_, name, _handler, _kw) in hass.services.registered]
    assert set(names) == {SERVICE_APPLY_CLEAN_SEQUENCE, SERVICE_CLEAR_CLEAN_SEQUENCE}

    for (_, name, _handler, kwargs) in hass.services.registered:
        assert kwargs.get("supports_response") is True, (
            f"service {name!r} does not support_response"
        )
