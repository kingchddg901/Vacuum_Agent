"""The ``eufy_vacuum.battery_rebaseline`` service handler in __init__.py.

[INIT-REBASE] Boots the integration through the real config-entry setup path
(reusing the test_init_setup harness), swaps in a fake battery manager exposing
a spy ``rebaseline``, then drives the registered service through
``hass.services.async_call``. Asserts the handler read the call data, looked the
battery manager up out of ``hass.data[DOMAIN][DATA_BATTERY]``, and delegated to
``rebaseline(vacuum_entity_id)`` — the observable contract of the service.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.const import DATA_BATTERY, DOMAIN

from .test_init_setup import _VAC, _setup


class _FakeBatteryManager:
    """Stand-in battery manager that records rebaseline() calls.

    The real BatteryHealthManager.rebaseline returns a bool (True when a record
    was cleared, False when none existed). We mirror that contract so the
    handler's ``if not ok`` branch sees a real return value, and record the
    arguments so the test can assert the delegate actually fired.
    """

    def __init__(self, result: bool = True):
        self.result = result
        self.calls: list[str] = []

    def rebaseline(self, vacuum_entity_id: str) -> bool:
        self.calls.append(vacuum_entity_id)
        return self.result


async def test_battery_rebaseline_service_delegates(hass, mock_config_entry):
    """[INIT-REBASE] the service handler delegates to bm.rebaseline()."""
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})
    ok = await _setup(hass, mock_config_entry)
    assert ok is True

    # The service must have been registered during setup.
    assert hass.services.has_service(DOMAIN, "battery_rebaseline")

    # Swap the live battery manager for a spy so we observe the delegation
    # without depending on the real manager's persisted state.
    fake = _FakeBatteryManager(result=True)
    hass.data[DOMAIN][DATA_BATTERY] = fake

    await hass.services.async_call(
        DOMAIN,
        "battery_rebaseline",
        {"vacuum_entity_id": _VAC},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Observable: the handler read the entity id from call.data and delegated
    # exactly once to rebaseline() with it.
    assert fake.calls == [_VAC]

    # The False return drives the handler's "no record found" branch without
    # raising — the handler swallows the result either way.
    fake.result = False
    await hass.services.async_call(
        DOMAIN,
        "battery_rebaseline",
        {"vacuum_entity_id": _VAC},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert fake.calls == [_VAC, _VAC]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
