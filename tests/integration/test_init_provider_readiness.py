"""Cold-start provider readiness in __init__.py — the defending test for INKR1TW7.

Sibling of test_init_setup.py, and separate from it for one reason: every test
there boots with `hass` ALREADY RUNNING, and this module needs the opposite.
`async_at_started` fires IMMEDIATELY when HA is already running, so a config
entry set up against a running `hass` cannot tell "deferred until the providers
are up" apart from "read inline at setup, and never again" — the two behaviours
are byte-identical in that harness, which is why 4,400 green tests said nothing
about this rule.

THE RULE (`custom_components/eufy_vacuum/__init__.py#INKR1TW7`): an operation
that reads entities owned by ANOTHER integration must not assume they exist
during cold-start setup — defer it to `async_at_started`, or tolerate late
availability. Otherwise it reads an empty registry and a stateless vacuum,
CACHES THAT ANSWER, AND NEVER LOOKS AGAIN, so a restart repeats the race
instead of repairing it.

Measured on a user's install (issue #49) and reproduced verbatim below: seven
`maintenance_sources` recorded as null beside 65 present companion entities,
and `supports_rooms` false beside a self-check reporting five readable rooms.

Coverage targets
----------------
[PROV-1] INKR1TW7: the vacuum's provider publishes NOTHING at config-entry
         setup — no companion sensors, no `segments` attribute — and finishes
         only after HA has started. Both halves of the post-start hook must
         run: re-registering the brand adapter re-derives the HINTS from live
         state (`has_attribute_rooms` -> `supports_rooms`), and refreshing
         capabilities re-runs the live registry sweep (`maintenance_sources`).
         Neither is repairable by the other, so both are asserted.
"""

from __future__ import annotations

# THE SDK IS IMPORTED HERE, AT COLLECTION, AND THE REASON IS A TEARDOWN FAILURE.
# [PROV-2] below makes the configured vacuum look like a Roborock, so setup calls
# `adapters/roborock/dock.py::load_dock_library` -- and python-roborock's
# module-level rate limiters start two daemon `PyrateLimiter's Leaker` threads on
# first import. Done inside a test body, HA's autouse `verify_cleanup` fixture
# fails that test's TEARDOWN while the test itself PASSES, which is what makes the
# symptom unreadable: "2 passed, 1 error", pointing at a test with nothing wrong
# with it.
#
# THIS IS THE FOURTH SITE. The full history is in
# tests/integration/test_vocabulary_catchup_wiring.py, whose note ends: "NOTHING
# ENUMERATES THESE SITES, and that is the open half" -- a census gate was
# considered there and deliberately not built, because the only discriminator
# available was `brands._vacuum_platform` and a future test might force a Roborock
# another way. [PROV-2] forces it by exactly that discriminator, so the gate that
# was deferred would have caught this module. Recorded, not re-proposed.
#
# A PLAIN import, never `importorskip`: this module fakes every SDK answer and must
# still run when the SDK is absent.
try:
    import roborock  # noqa: F401
    _ROBOROCK_SDK = True
except ImportError:
    _ROBOROCK_SDK = False

from unittest.mock import patch

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component

from custom_components.eufy_vacuum.adapters.eufy.maintenance_components import (
    MAINTENANCE_COMPONENTS,
)
from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN


_VAC = "vacuum.alfred"
_OBJECT_ID = "alfred"

#: The counter sensors the provider publishes LATE, derived from the brand's own
#: component catalog rather than retyped. A hand-written list would drift from
#: what the adapter actually declares and still pass.
_LATE_COUNTER_ENTITIES = {
    f"sensor.{_OBJECT_ID}_{meta['sensor_suffix']}"
    for meta in MAINTENANCE_COMPONENTS.values()
    if meta.get("sensor_suffix")
}

#: Rooms as an attribute-mode device publishes them — adapters/eufy/adapter.py
#: reads `segments` off the vacuum state to derive `has_attribute_rooms`, which
#: is what core turns into `supports_rooms`.
_LATE_SEGMENTS = [{"id": 1, "name": "Kitchen"}, {"id": 2, "name": "Hallway"}]


def _patch_frontend():
    """Patch the panel surfaces that need the frontend component.

    `autospec=True` rather than a bare AsyncMock: these stand in for real HA
    functions, so the signature the integration calls them with is checked
    rather than agreed with.
    """
    return [
        patch("homeassistant.components.panel_custom.async_register_panel",
              autospec=True),
        patch("homeassistant.components.frontend.async_remove_panel",
              autospec=True),
    ]


@pytest.fixture(autouse=True)
def _vacuum_registered_as_a_real_eufy(hass):
    """Put `vacuum.alfred` in the entity registry, owned by `robovac_mqtt`.

    A real Eufy vacuum entity is created by that integration and carries its
    `platform`; brand resolution matches on it. Without a registry entry the
    vacuum is UNSUPPORTED, no adapter registers, and there are no capabilities
    to get wrong. MUST run before the state is set — HA will not generate an
    entity_id that already exists in `hass.states`.
    """
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_get_or_create(
        "vacuum", "robovac_mqtt", "alfred_unique_id", suggested_object_id="alfred"
    )


async def _setup_on_a_cold_boot(hass, entry):
    """Set the entry up with HA NOT yet started — the window the rule is about."""
    await async_setup_component(hass, "http", {})
    entry.add_to_hass(hass)
    hass.set_state(CoreState.not_running)
    patches = _patch_frontend()
    for p in patches:
        p.start()
    try:
        ok = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        for p in patches:
            p.stop()
    return ok


async def test_capabilities_are_redetected_once_the_provider_is_up(
    hass, mock_config_entry
):
    """[PROV-1] INKR1TW7 — the cold-boot answer must not be the final answer.

    Sets the entry up while the vacuum's own integration has published nothing,
    then lets it finish and fires EVENT_HOMEASSISTANT_STARTED. The capability
    snapshot must be REPAIRED IN PLACE; caching the setup-time read is the
    failure this invariant names.
    """
    # The provider is up enough to have an entity, and nothing more: no
    # companion sensors, no `segments`. This is a cold boot, not a broken one.
    hass.states.async_set(_VAC, "docked", {"supported_features": 0})

    assert await _setup_on_a_cold_boot(hass, mock_config_entry) is True

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    cold = manager.data["capabilities"][_VAC]

    # THE RACE, REPRODUCED. Without this half the assertions below could pass on
    # a snapshot that was never wrong, and the test would prove nothing.
    assert set(cold["maintenance_sources"]) == set(MAINTENANCE_COMPONENTS)
    assert all(src is None for src in cold["maintenance_sources"].values()), (
        f"expected every maintenance source unresolved on a cold boot, got "
        f"{cold['maintenance_sources']}"
    )
    assert cold["supports_rooms"] is False

    # The provider finishes: its counter sensors appear and the vacuum starts
    # reporting its room list.
    for entity_id in sorted(_LATE_COUNTER_ENTITIES):
        hass.states.async_set(entity_id, "90")
    hass.states.async_set(
        _VAC, "docked", {"supported_features": 0, "segments": _LATE_SEGMENTS}
    )

    # HA finishes starting. Everything the integration deferred runs now.
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    warm = manager.data["capabilities"][_VAC]

    # Half 1 — the capability refresh re-ran the LIVE REGISTRY SWEEP, so every
    # component the brand declares now names a companion that really exists.
    sources = warm["maintenance_sources"]
    assert set(sources) == set(MAINTENANCE_COMPONENTS)
    # ⚠ SCOPED TO COMPONENTS THE INTEGRATION ACTUALLY COUNTS, 2026-09-12. A component with no
    # `sensor_suffix` has no companion to find — Eufy publishes no swivel-wheel counter at all
    # — so it resolves to None until the user picks a clock for the vacuum, and that is the
    # correct answer rather than a cold-boot cache miss. Asserting over ALL components would
    # make this test red for a reason it was never about, and it would stay red forever.
    # It previously passed because `proxy_for` borrowed the filter's counter, which silently
    # reset the wheel whenever the filter was reset.
    countable = {c for c, meta in MAINTENANCE_COMPONENTS.items() if meta.get("sensor_suffix")}
    unresolved = sorted(
        c for c, src in sources.items() if src is None and c in countable
    )
    assert not unresolved, (
        f"maintenance sources still unresolved after the provider came up: "
        f"{unresolved} — the cold-boot answer was cached (INKR1TW7)"
    )
    # `None` is a legitimate value here now — a component the integration counts nothing for
    # has no companion to resolve to. What this guards is unchanged: anything that DID resolve
    # must name an entity this install actually published.
    resolved = {src for src in sources.values() if src is not None}
    assert resolved <= _LATE_COUNTER_ENTITIES, (
        f"resolved to entities this install never published: "
        f"{sorted(resolved - _LATE_COUNTER_ENTITIES)}"
    )
    assert resolved, "nothing resolved at all — that is a cache miss, not an uncounted part"
    # Named verbatim, so no degenerate snapshot can satisfy this.
    assert sources["filter"] == "sensor.alfred_filter_remaining"
    assert sources["cleaning_tray"] == "sensor.alfred_cleaning_tray_remaining"

    # Half 2 — the brand adapter was RE-REGISTERED, so the hints were re-derived
    # from live state. A capability refresh alone cannot fix this: it replays the
    # adapter's stored hints, and the stored hint says no rooms.
    assert warm["supports_rooms"] is True
    assert warm["supports_segments"] is True

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_prov2_the_started_hop_refreshes_the_ROOM_ENTITIES_too(
    hass, mock_config_entry, monkeypatch
):
    """[PROV-2] A corrected config is not a corrected card -- on THIS hop as well.

    Issue #71 has two hops and each needs its own nudge:

      hop 1  EVENT_HOMEASSISTANT_STARTED  -> this test
      hop 2  the late provider's state change -> [VCW-1]/[VCW-2]

    Both end at the same place and both were broken the same way. The code comment
    on this one records the measurement: room entities compute their attributes
    from the adapter config, but only when they WRITE state -- and they had
    already written, ~15 seconds into the boot, from the DECLARED lists. The
    re-registration fixed the config and nothing asked them to look again, so the
    config held the device's own suction list while every room switch still served
    the fallback. "The feature was correct and invisible."

    So the assertion is on the STATE MACHINE, not the config: the card reads
    states. A test that checked `get_adapter_config` would pass on exactly the
    build this exists to catch.

    A MAP WITH A ROOM IS SEEDED because the refresh loops over the vacuum's stored
    maps -- with none, the loop body never runs and there is no room switch to
    observe. [VCW-2] needed the same thing for hop 2 and says so.
    """
    from custom_components.eufy_vacuum.adapters.eufy import adapter as _eufy
    from custom_components.eufy_vacuum.adapters.registry import get_adapter_config
    from custom_components.eufy_vacuum.adapters.roborock import adapter as rb
    from custom_components.eufy_vacuum.adapters import brands

    from .conftest import setup_map

    _FAN_LIVE = ["quiet", "balanced", "turbo", "max", "max_plus"]

    class _Dev:
        manufacturer = "Roborock"
        model = "roborock.vacuum.a147"

    def _as_roborock(fan_list=None):
        """Make the configured vacuum look like a Roborock, optionally mid-publish."""
        monkeypatch.setattr(rb, "_device_for_vacuum", lambda h, v: _Dev())
        # Brand resolution keys on which INTEGRATION owns the vacuum entity, not on
        # the device record -- patching the device alone leaves this a Eufy and the
        # whole test silently exercises the wrong adapter.
        monkeypatch.setattr(brands, "_vacuum_platform", lambda h, v: "roborock")
        attrs = {"supported_features": 30524, "fan_speed": "max"}
        if fan_list is not None:
            attrs["fan_speed_list"] = fan_list
        hass.states.async_set(_VAC, "docked", attrs)

    def _fan_options():
        return [
            str(o.get("value"))
            for o in ((get_adapter_config(_VAC) or {}).get("vocabulary") or {}).get(
                "fan_speed_options"
            ) or []
        ]

    _as_roborock(fan_list=None)
    assert await _setup_on_a_cold_boot(hass, mock_config_entry) is True

    manager = hass.data[DOMAIN][DATA_RUNTIME]
    setup_map(manager, _VAC, "1", count=1)
    manager._notify_rooms_updated(vacuum_entity_id=_VAC, map_id="1")  # noqa: SLF001
    await hass.async_block_till_done()

    before = _fan_options()
    assert "max_plus" not in before, (
        "the cold-boot config already holds the live list; there is no catch-up "
        "left to observe: %r" % (before,)
    )

    room_switches = [
        st for st in hass.states.async_all("switch")
        if st.attributes.get("fan_speed_options") is not None
    ]
    assert room_switches, (
        "no room switch exposed fan_speed_options -- this test cannot observe the "
        "hop it exists for, and a skip here would make it worthless"
    )

    # The provider's coordinator finally polls, then HA finishes starting.
    _as_roborock(fan_list=_FAN_LIVE)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert _fan_options() == _FAN_LIVE, (
        "the re-registration did not pick up the device's own list"
    )

    after = hass.states.get(room_switches[0].entity_id)
    assert [
        str(o.get("value")) for o in after.attributes["fan_speed_options"]
    ] == _FAN_LIVE, (
        "the config was corrected and the room switch still serves the fallback -- "
        "correct and invisible, which is the shape of the original defect"
    )
