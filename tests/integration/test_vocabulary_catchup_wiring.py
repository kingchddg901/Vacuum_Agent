"""The live-vocabulary catch-up, wired end to end (issue #71).

THE DEFECT THIS COVERS WAS FOUND ON HARDWARE AND WAS INVISIBLE TO 5113 PASSING TESTS,
twice, in two different places. Both are the same shape — a correct value that never
reaches the user.

1. `async_at_started` guarantees every integration has SET UP, which is what the
   post-start capability re-detection needs. An adapter reading an entity's ATTRIBUTES
   needs the provider's coordinator to have POLLED, which is later and not guaranteed
   at all. So the adapter kept its DECLARED option lists.

2. Then, once that was fixed, the adapter config was right and the CARD WAS STILL
   WRONG: room entities compute their attributes from the config but only when they
   WRITE state, and they had already written ~15 seconds into the boot from the
   fallback lists. Measured on the live box — the config served
   `quiet/balanced/turbo/max/gentle` while every room switch served
   `gentle/quiet/balanced/turbo/max`.

So there are two hops, and each needs its own nudge: re-register when the data lands,
then tell the room entities to look again. `[VCW-2]` is the second one, and it is the
one a unit test of either piece alone cannot see.

Coverage targets
----------------
[VCW-1] a provider that publishes LATE still gets its vocabulary read — the listener
        backstop fires on the publish and re-registers.
[VCW-2] the room entity's ATTRIBUTES change too, not just the config.
[VCW-3] a provider that was ready on time arms nothing and changes nothing.
[VCW-5] the vendor SDK is imported at COLLECTION, so its daemon threads cannot
        fail the teardown of whichever test forces a Roborock first.
"""

from __future__ import annotations

import threading

# THE SDK IS IMPORTED HERE, AT COLLECTION, AND THE REASON IS A TEARDOWN FAILURE.
# This module makes the configured vacuum look like a Roborock, so setup calls
# `adapters/roborock/dock.py::load_dock_library` -- and python-roborock's
# module-level rate limiters start two daemon `PyrateLimiter's Leaker` threads on
# first import. Done inside a test body, HA's autouse `verify_cleanup` fixture then
# fails that test's TEARDOWN while the test itself PASSES, which is what made the
# symptom unreadable: `4 passed, 1 error`, pointing at a test with nothing wrong
# with it.
#
# ⚠ THIS WAS THE FORGOTTEN THIRD SITE. `b6a85f6f` diagnosed this precisely and
# swept only `tests/adapters/roborock/test_adapter.py` and `test_dock_sdk.py`. Its
# `[RBSDK-1]` guard is PER-MODULE, so it is structurally unable to see a third site,
# and this file was already on disk -- failing since `6b3f2997` (2026-10-24) and
# invisible to CI, because under `pytest tests` the alphabetically earlier
# tests/adapters collection warms the threads first. The error only appears when
# tests/integration is selected on its own.
#
# NOTHING ENUMERATES THESE SITES, and that is the open half. A census gate was
# considered and NOT built: the only discriminator available today is
# monkeypatching `brands._vacuum_platform`, this is its one user, and a future test
# could force a Roborock another way -- so the gate would carry weak recall while
# its PRESENCE read as coverage. Chris's call, recorded rather than pre-empted.
#
# A PLAIN import, never `importorskip`: this module fakes every SDK answer and must
# still run when the SDK is absent.
try:
    import roborock  # noqa: F401
    _ROBOROCK_SDK = True
except ImportError:
    _ROBOROCK_SDK = False

#: Snapshotted at COLLECTION, which is what makes [VCW-5] able to fail -- by the
#: time any test body runs, an in-body import would already have polluted it.
_LEAKER_THREADS_AT_IMPORT = sorted(
    t.name for t in threading.enumerate() if "Leaker" in t.name
)

import pytest

from homeassistant.config_entries import ConfigEntryState

from custom_components.eufy_vacuum.adapters.registry import get_adapter_config

from .test_init_setup import _VAC, _setup

_FAN_LIVE = ["quiet", "balanced", "turbo", "max", "max_plus"]


def _fan_options(hass, vacuum=_VAC):
    return [
        str(o.get("value"))
        for o in ((get_adapter_config(vacuum) or {}).get("vocabulary") or {}).get(
            "fan_speed_options"
        ) or []
    ]


def _roborock(hass, monkeypatch, *, fan_list=None):
    """Make the configured vacuum look like a Roborock, optionally mid-publish."""
    from custom_components.eufy_vacuum.adapters.roborock import adapter as rb

    class _Dev:
        manufacturer = "Roborock"
        model = "roborock.vacuum.a147"

    monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _Dev())
    # Brand resolution keys on which INTEGRATION owns the vacuum entity, not on the
    # device record — so patching the device alone leaves this a Eufy and the whole
    # test silently exercises the wrong adapter.
    from custom_components.eufy_vacuum.adapters import brands

    monkeypatch.setattr(brands, "_vacuum_platform", lambda h, v: "roborock")
    attrs = {"supported_features": 30524, "fan_speed": "max"}
    if fan_list is not None:
        attrs["fan_speed_list"] = fan_list
    hass.states.async_set(_VAC, "docked", attrs)


async def test_vcw_1_a_late_provider_still_gets_its_vocabulary_read(
    hass, mock_config_entry, monkeypatch
):
    """[VCW-1] THE BACKSTOP. Set up with the provider publishing nothing, then let it
    publish, and the adapter must end up holding the DEVICE's list.

    Without the listener this stays on the declared transcript until something reloads
    the config entry — which on a real install means every restart serves the wrong
    vocabulary, and issue #71's reporter would have seen the fix silently not apply.
    """
    _roborock(hass, monkeypatch, fan_list=None)
    assert await _setup(hass, mock_config_entry) is True
    await hass.async_block_till_done()

    before = _fan_options(hass)
    assert "max_plus" not in before, "the fallback should be the declared transcript"

    # The coordinator finally polls.
    _roborock(hass, monkeypatch, fan_list=_FAN_LIVE)
    await hass.async_block_till_done()

    assert _fan_options(hass) == _FAN_LIVE, (
        "the provider published and the adapter never looked again"
    )


async def test_vcw_2_the_room_entity_attributes_change_too(
    hass, mock_config_entry, monkeypatch
):
    """[VCW-2] A CORRECTED CONFIG IS NOT A CORRECTED CARD.

    This is the hop that was missed after the first fix landed: the config was right
    and every room switch still served the fallback, because entities only recompute
    their attributes when they write state and they had already written. The card shows
    the state machine, not the config, so this asserts the state machine.
    """
    _roborock(hass, monkeypatch, fan_list=None)
    assert await _setup(hass, mock_config_entry) is True
    await hass.async_block_till_done()

    # The entry fixture carries no rooms, and a room switch is the only surface that
    # can show this hop — so seed one and let the platform build its entities.
    from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN

    from .conftest import setup_map

    _manager = hass.data[DOMAIN][DATA_RUNTIME]
    setup_map(_manager, _VAC, "1", count=1)
    _manager._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="1")  # noqa: SLF001
    await hass.async_block_till_done()

    room_switches = [
        s for s in hass.states.async_all("switch")
        if s.attributes.get("fan_speed_options") is not None
    ]
    # A SKIP HERE WOULD MAKE THIS TEST WORTHLESS — it is the only one watching the hop
    # that was missed, so it must fail rather than quietly not run.
    assert room_switches, (
        "no room switch exposed fan_speed_options; this test cannot observe the hop "
        "it exists for"
    )

    _roborock(hass, monkeypatch, fan_list=_FAN_LIVE)
    await hass.async_block_till_done()

    after = hass.states.get(room_switches[0].entity_id)
    assert [str(o.get("value")) for o in after.attributes["fan_speed_options"]] == (
        _FAN_LIVE
    ), "the config was corrected but the entity never re-wrote its state"


async def test_vcw_3_a_punctual_provider_changes_nothing(
    hass, mock_config_entry, monkeypatch
):
    """[VCW-3] The no-op case. A provider ready at setup time needs no catch-up, and
    the install must not pay for one — no listener, no re-registration, no churn.

    EVERY source has to be published for this, not just the fan: a first draft
    published only `fan_speed_list` and failed with `['select.alfred_mop_mode']` still
    pending — which was the code being right and the test being wrong, and a useful
    reminder that "nothing pending" means nothing is pending.
    """
    _roborock(hass, monkeypatch, fan_list=_FAN_LIVE)
    hass.states.async_set(
        "select.alfred_mop_mode", "standard",
        {"options": ["standard", "deep", "deep_plus"]},
    )
    hass.states.async_set(
        "select.alfred_mop_intensity", "off",
        {"options": ["off", "mild", "standard", "intense"]},
    )
    hass.states.async_set("binary_sensor.alfred_water_box_attached", "on")
    assert await _setup(hass, mock_config_entry) is True
    await hass.async_block_till_done()

    assert _fan_options(hass) == _FAN_LIVE
    assert (get_adapter_config(_VAC) or {}).get("_pending_live_reads") == []


async def test_vcw_4_the_entry_still_unloads_after_the_catch_up_completes(
    hass, mock_config_entry, monkeypatch
):
    """[VCW-4] THE BUG THAT COULD TAKE THE INTEGRATION DOWN, caught by the pre-release
    audit and invisible to every other test.

    The catch-up handle had TWO owners: the callback that disarms when the last vacuum
    catches up, and config-entry unload. Home Assistant's state-change unsubscribe is
    NOT idempotent — the second call raises `ValueError: list.remove(x): x not in
    list`. That escapes `_async_process_on_unload`, which does not catch, so the entry
    lands in FAILED_UNLOAD. That state is non-recoverable: `async_reload` skips the
    re-setup and the integration stays down until Home Assistant itself is restarted.

    Reaching it needs the catch-up to COMPLETE first, which is why nothing saw it: every
    other test either never arms the listener or never unloads afterwards.
    """
    _roborock(hass, monkeypatch, fan_list=None)
    hass.states.async_set(
        "select.alfred_mop_mode", "standard",
        {"options": ["standard", "deep", "deep_plus"]},
    )
    hass.states.async_set(
        "select.alfred_mop_intensity", "off",
        {"options": ["off", "mild", "standard", "intense"]},
    )
    hass.states.async_set("binary_sensor.alfred_water_box_attached", "on")
    assert await _setup(hass, mock_config_entry) is True
    await hass.async_block_till_done()

    # The provider finally publishes the one source that was missing, which empties the
    # watch set and disarms the listener.
    _roborock(hass, monkeypatch, fan_list=_FAN_LIVE)
    await hass.async_block_till_done()
    assert (get_adapter_config(_VAC) or {}).get("_pending_live_reads") == [], (
        "the catch-up must have completed, or this test is not exercising the bug"
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id), (
        "unload raised — the handle was unsubscribed twice"
    )
    await hass.async_block_till_done()
    assert mock_config_entry.state is not ConfigEntryState.FAILED_UNLOAD


def test_vcw5_the_vendor_sdk_is_imported_during_collection():
    """[VCW-5] The SDK's daemon threads must predate every test in this module.

    Not a vocabulary claim -- a HYGIENE one, and it is here because the three tests
    above all passed while this module reported an ERROR. `verify_cleanup` asserts
    that nothing new survives teardown, so the test that happens to trigger the
    first `import roborock` is blamed for threads it merely woke.

    RED: delete the module-level `import roborock` above. The snapshot is then empty
    whenever this file is run on its own, which is exactly the configuration that
    was failing -- and is the configuration CI never exercises, because
    tests/adapters is collected first under `pytest tests` and warms the threads.

    ⚠ THE RED INPUT IS SELECTION-DEPENDENT, and saying so is the point. Run beside
    tests/adapters this assertion holds with the import deleted, because a sibling
    module already warmed the threads. That is not a weakness of this test; it is
    the property that hid the defect for fifteen days.
    """
    assert _ROBOROCK_SDK, (
        "python-roborock is pinned in requirements_test.txt but did not import; "
        "this guard cannot measure anything without it"
    )
    assert _LEAKER_THREADS_AT_IMPORT, (
        "the SDK's daemon threads did not exist when this module was collected, so "
        "something imports it inside a test body -- HA's verify_cleanup will fail "
        "the teardown of whichever test gets there first"
    )
