"""Integration tests — services/stall_capture.py.

Two services, two audiences. ``set_stall_capture`` is production — the rooms-card
switch calls it, and without it the capture feature is correct and unreachable.
``dev_inject_stall`` is the maintainer instrument that fires the CANONICAL stall
event so every downstream consumer runs for real.

Both were registered, documented and shipped with **no test reaching either handler**:
25 of 43 statements and 0 of 6 branches. Every refusal below — the managed-vacuum
gate and both injector preconditions — existed only as an unexercised `raise`, which
is the same shape as the guard that could never fire in issue #51.

Coverage targets
----------------
[SSC-1] set_stall_capture writes the flag for a MANAGED vacuum and persists it.
[SSC-2] set_stall_capture REFUSES an unmanaged vacuum rather than minting a record.
[SSC-3] ...and the refusal STILL leaves the `vacuums` container behind. That is the
        documented C12 divergence — `setdefault` mutates `manager.data` before the
        authorization decision — pinned here so repairing it is a deliberate change
        with a red test, not a silent one.
[SSC-4] dev_inject_stall refuses when there is no active map.
[SSC-5] dev_inject_stall refuses when the vacuum is not currently in a room, because
        a stall with no room has nothing to render and would look like a broken
        renderer rather than an honest absence.
[SSC-6] dev_inject_stall fires EVENT_STALL_DETECTED carrying the REAL room context
        and `injected: True`.
[SSC-7] ...and falls back to "Room <id>" when the room record carries no name.
[SSC-8] both services register with `supports_response="only"` — they are queries that
        return a payload, and a caller that cannot read the response cannot use them.
"""

from __future__ import annotations

from unittest.mock import create_autospec

import pytest

from homeassistant.core import ServiceCall
from homeassistant.exceptions import ServiceValidationError

from custom_components.eufy_vacuum.const import (
    DOMAIN,
    EVENT_STALL_DETECTED,
    SERVICE_DEV_INJECT_STALL,
    SERVICE_SET_STALL_CAPTURE,
)
from custom_components.eufy_vacuum.jobs.active_job import ActiveJobTracker
from custom_components.eufy_vacuum.services.stall_capture import register


_VAC = "vacuum.ivy"
_MAP = "1"


# WHY A NARROW FAKE RATHER THAN create_autospec ON THE MANAGER:
# the handlers reach for `.data`, which is an INSTANCE attribute set in __init__ and
# therefore absent from an autospec built from the class -- `spec_set=True` would
# refuse to let a test assign it. `active_job` IS autospec'd, because `get_active_job`
# is keyword-only and a typo there would otherwise return a MagicMock that every
# assertion below would happily accept.
def _fake_hass(*, managed=True, map_id=_MAP, current_room_id=7, rooms=None,
               save_raises=None):
    active_job = create_autospec(ActiveJobTracker, spec_set=True, instance=True)
    active_job.get_active_job.return_value = {"current_room_id": current_room_id}

    class _Manager:
        def __init__(self):
            # A managed vacuum is one that already has a record. The handler's gate is
            # membership in this dict, so this IS the fixture for "managed".
            self.data = {"vacuums": {_VAC: {}}} if managed else {}
            self.active_job = active_job
            self.saved = 0

        async def async_save(self):
            if save_raises:
                raise save_raises
            self.saved += 1

        def resolve_active_map_id(self, *, vacuum_entity_id):
            return map_id

        def get_managed_rooms(self, *, vacuum_entity_id, map_id):
            return {"rooms": rooms if rooms is not None else {"7": {"name": "Kitchen"}}}

    manager = _Manager()

    class _Services:
        def __init__(self):
            self.registered = []

        def async_register(self, domain, name, handler, **kwargs):
            self.registered.append((domain, name, handler, kwargs))

    class _Bus:
        def __init__(self):
            self.fired = []

        def async_fire(self, event_type, payload):
            self.fired.append((event_type, payload))

    class _Hass:
        pass

    hass = _Hass()
    hass.data = {DOMAIN: {"runtime": manager}}
    hass.services = _Services()
    hass.bus = _Bus()
    return hass, manager


def _handler(hass, service_name):
    """The closure registered under `service_name`.

    The handlers are closures inside `register()`, not module-level functions, so the
    registration list is the only way to reach them -- which also means these tests
    exercise the real registration path rather than a hand-picked callable.
    """
    for _domain, name, handler, _kw in hass.services.registered:
        if name == service_name:
            return handler
    raise AssertionError(f"{service_name} was never registered")


def _call(hass, **data) -> ServiceCall:
    return ServiceCall(hass, DOMAIN, "x", dict(data))


async def test_ssc1_set_stall_capture_arms_a_managed_vacuum():
    """[SSC-1] the switch the rooms card actually calls.

    ABLATION: drop the `stall_capture_enabled` assignment and this goes red. The
    capture consumer treats absent as OFF, so without the write the feature is
    unreachable and nothing else reports that.
    """
    hass, manager = _fake_hass()
    register(hass)

    result = await _handler(hass, SERVICE_SET_STALL_CAPTURE)(
        _call(hass, vacuum_entity_id=_VAC, enabled=True)
    )

    assert manager.data["vacuums"][_VAC]["stall_capture_enabled"] is True
    assert result == {"vacuum_entity_id": _VAC, "enabled": True}
    assert manager.saved == 1, "the flag is persisted, not just set in memory"


async def test_ssc1b_set_stall_capture_disarms():
    """[SSC-1] the other half — `enabled: False` must persist a False, not skip."""
    hass, manager = _fake_hass()
    register(hass)
    hass.data[DOMAIN]["runtime"].data["vacuums"][_VAC]["stall_capture_enabled"] = True

    result = await _handler(hass, SERVICE_SET_STALL_CAPTURE)(
        _call(hass, vacuum_entity_id=_VAC, enabled=False)
    )

    assert manager.data["vacuums"][_VAC]["stall_capture_enabled"] is False
    assert result["enabled"] is False


async def test_ssc2_set_stall_capture_refuses_an_unmanaged_vacuum():
    """[SSC-2] the authorization gate, which had never been executed.

    ABLATION: remove the membership check and this goes red -- the handler would
    create a record for a vacuum this integration does not manage, which is the
    phantom-bucket defect this gate exists to prevent.
    """
    hass, manager = _fake_hass(managed=False)
    register(hass)

    with pytest.raises(ServiceValidationError, match="not a managed vacuum"):
        await _handler(hass, SERVICE_SET_STALL_CAPTURE)(
            _call(hass, vacuum_entity_id=_VAC, enabled=True)
        )
    assert _VAC not in manager.data.get("vacuums", {}), "no record is minted"
    assert manager.saved == 0, "a refusal must not persist"


async def test_ssc3_the_refusal_still_leaves_the_container_behind():
    """[SSC-3] PINS A KNOWN DIVERGENCE RATHER THAN ASSERTING IT IS CORRECT.

    `setdefault` runs BEFORE the authorization decision, so a refused call leaves
    `data["vacuums"] = {}` behind. The module's own comment records this as C12, still
    open, and says replacing it with `require_managed_vacuum` is a code change made
    elsewhere. The behaviour is harmless -- an empty container, no per-vacuum record --
    but it is the reason `is_managed_vacuum` is non-mutating on purpose, because "a
    gate cannot be built on a dict its own read path writes to".

    This test exists so that repair arrives WITH a red test instead of silently. If
    you are here because it failed: that is the fix landing, and the right move is to
    delete this test in the same commit, not to restore the setdefault.
    """
    hass, manager = _fake_hass(managed=False)
    register(hass)
    assert "vacuums" not in manager.data, "the premise: nothing there before the call"

    with pytest.raises(ServiceValidationError):
        await _handler(hass, SERVICE_SET_STALL_CAPTURE)(
            _call(hass, vacuum_entity_id=_VAC, enabled=True)
        )

    assert manager.data.get("vacuums") == {}, (
        "documented C12 divergence: the container is created before the gate decides"
    )


async def test_ssc4_inject_refuses_without_an_active_map():
    """[SSC-4] no map means nothing to stall on, and nothing to render.

    ABLATION: drop the `map_id is None` check and this goes red downstream -- the
    handler would call get_active_job with map_id "None" and fire an event naming a
    map that does not exist.
    """
    hass, _manager = _fake_hass(map_id=None)
    register(hass)

    with pytest.raises(ServiceValidationError, match="no active map"):
        await _handler(hass, SERVICE_DEV_INJECT_STALL)(_call(hass, vacuum_entity_id=_VAC))
    assert hass.bus.fired == [], "no event escapes a refusal"


async def test_ssc5_inject_refuses_when_not_cleaning_a_room():
    """[SSC-5] refusing is the honest failure, and the message has to say why.

    A stall with no current room has no room to render, and the pose ring is empty at
    the dock by design -- an injected one would exercise the ABSENCE path and look
    like a broken renderer. The instrument must not hand anyone that.

    ABLATION: drop the `room_id is None` check and this goes red -- the payload would
    carry `room_id: None` and `room_name: "Room None"`.
    """
    hass, _manager = _fake_hass(current_room_id=None)
    register(hass)

    with pytest.raises(ServiceValidationError, match="not currently cleaning a room"):
        await _handler(hass, SERVICE_DEV_INJECT_STALL)(_call(hass, vacuum_entity_id=_VAC))
    assert hass.bus.fired == []


async def test_ssc6_inject_fires_the_canonical_event_with_real_context():
    """[SSC-6] the instrument's whole purpose: a real event, real downstream consumers.

    ABLATION: change the event name off EVENT_STALL_DETECTED and this goes red. The
    injector is only useful because it fires the SAME event production fires; a
    private event would exercise nothing.
    """
    hass, _manager = _fake_hass()
    register(hass)

    payload = await _handler(hass, SERVICE_DEV_INJECT_STALL)(
        _call(hass, vacuum_entity_id=_VAC)
    )

    assert len(hass.bus.fired) == 1
    event_type, fired = hass.bus.fired[0]
    assert event_type == EVENT_STALL_DETECTED
    assert fired is payload, "the returned payload IS the fired payload"
    assert fired["injected"] is True, "the one flag that marks the stimulus synthetic"
    assert fired["room_id"] == 7
    assert fired["room_name"] == "Kitchen", "the REAL room record, not a placeholder"
    assert fired["map_id"] == _MAP
    # The timing fields are deliberately absent-valued: an injected stall has no
    # elapsed/expected to report, and inventing them would make the capture lie.
    assert fired["elapsed_minutes"] is None
    assert fired["expected_minutes"] is None
    assert fired["stall_ratio"] is None


async def test_ssc7_inject_falls_back_to_a_generated_room_name():
    """[SSC-7] the `or` fallback, which no other test reaches.

    A room id with no record (or a record with no name) still has to produce a usable
    label -- the capture renders it. Two inputs, because they are different branches:
    a MISSING room record, and a record present but nameless.

    ABLATION: drop the `or f"Room {room_id}"` and this goes red with None.
    """
    hass, _manager = _fake_hass(rooms={})           # no record at all
    register(hass)
    payload = await _handler(hass, SERVICE_DEV_INJECT_STALL)(
        _call(hass, vacuum_entity_id=_VAC)
    )
    assert payload["room_name"] == "Room 7"

    hass2, _m2 = _fake_hass(rooms={"7": {}})        # record present, no name
    register(hass2)
    payload2 = await _handler(hass2, SERVICE_DEV_INJECT_STALL)(
        _call(hass2, vacuum_entity_id=_VAC)
    )
    assert payload2["room_name"] == "Room 7"


async def test_ssc8_both_services_return_a_response():
    """[SSC-8] `supports_response="only"` — both are queries that answer.

    A caller that cannot read the response cannot use either service: the arming one
    confirms what it set, and the injector returns the payload it fired so a maintainer
    can see the context without digging through the event bus.

    ABLATION: drop `supports_response` from either registration and this goes red.
    """
    hass, _manager = _fake_hass()
    register(hass)

    by_name = {name: kwargs for _d, name, _h, kwargs in hass.services.registered}
    assert set(by_name) == {SERVICE_SET_STALL_CAPTURE, SERVICE_DEV_INJECT_STALL}
    for name, kwargs in by_name.items():
        assert kwargs.get("supports_response") == "only", name
        assert kwargs.get("schema") is not None, f"{name} must validate its input"
