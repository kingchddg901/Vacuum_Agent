"""Tests for Lever B — live current-room refresh during a contiguous run.

Roborock's live current_room + per-room fan are MAP-derived, refreshed only on the
upstream coordinator's ~30s IMAGE_CACHE_INTERVAL gate (status moves at ~15s). During a
CONTIGUOUS run the framework pulses an adapter-named service (vacuum.get_vacuum_current_
position) that refreshes map_content off that gate, so the rollover + fan track at the
adapter's interval (~15s) instead of ~30s. Entirely adapter-declared (dispatch.live_room_
refresh) — core stays brand-agnostic and Eufy (no block) is a no-op.

Coverage targets
----------------
[LRR-1] getter: defaults disabled; declared block parsed; interval coercion (bad/<1).
[LRR-2] no block declared -> no pulse (Eufy inert).
[LRR-3] LOCAL (no cloud_api_used repair issue) + cleaning -> pulse fires once.
[LRR-4] CLOUD (issue present) -> skipped (never hammer the cloud rate-limit).
[LRR-5] rate-limited per vacuum: 2 immediate calls -> 1 pulse; fires again after interval.
[LRR-6] unavailable/unknown vacuum state -> skipped.
[LRR-7] ServiceNotSupported (e.g. a non-V1 model) -> sticky-disabled for the session.
[LRR-8] transient HomeAssistantError (e.g. position_not_found) -> swallowed, NOT disabled.
[LRR-9] gate fail-safe: an entity with no linked device -> skipped.
[LRR-10] ServiceNotFound (pulse service not registered on this install, e.g. wrong
         domain vacuum.* vs roborock.*) -> sticky-disabled after the first call,
         not retried every interval (deploy regression).
[LRR-11] RP-039/RF-33: ServiceValidationError (a HomeAssistantError subclass) is
         classified PERMANENT (sticky-disable + one WARNING) like ServiceNotFound/
         ServiceNotSupported, not swallowed by the generic transient branch below
         it (which would retry forever, every pulse interval, silently).
[LRR-12] a declared block with NO local_gate is inert rather than fatal. The signal is
         the absence of a raise: `calls == []` is every skipped path's value.
[LRR-13] a gate naming an identifier domain the device does not carry reads as CLOUD.
         Here `calls == []` IS a differential -- ablated, a pulse fires.
[LRR-14] ...and so does a gate with no issue template or no issue domain. Two cases,
         because that guard is an `or` and one case would leave half of it unablated.
[LRR-15] a template that cannot be formatted is caught, not propagated -- three
         templates for the three exception types the `except` tuple names.
"""

from __future__ import annotations

import pytest

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    ServiceValidationError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import slugify

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

_VAC = "vacuum.ivy"
_DUID = "57R4LhSyBB7y24BiKWWGiI"

# Roborock registers get_vacuum_current_position under the ROBOROCK domain (not vacuum),
# SupportsResponse.ONLY -> the call must set return_response (returns_response).
#
# ⚠ C23 — THIS IS A HAND COPY, NOT THE SHIPPED BLOCK, AND IT PINS NOTHING.
# Nothing joins `_LRR` to the real declaration in adapters/roborock/adapter.py
# (`dispatch.live_room_refresh`), so the `returns_response` assertion in
# test_getter_defaults_and_overrides reads this literal back at itself. And every
# `hass.services.async_register` in this file registers SupportsResponse.OPTIONAL, not
# ONLY — under OPTIONAL a call that omits return_response still succeeds. Consequence:
# delete `"returns_response": True` from the SHIPPED adapter and this suite stays green,
# while on a real install core raises ServiceValidationError before the handler and
# sticky-disables Lever B for the session. Closing it needs a code change (register ONLY
# here, and assert against the shipped block), so it is recorded, not claimed fixed.
_LRR = {
    "enabled": True,
    "interval_s": 15,
    "service": {
        "domain": "roborock", "service": "get_vacuum_current_position",
        "returns_response": True,
    },
    "local_gate": {
        "device_identifier_domain": "roborock",
        "issue_domain": "roborock",
        "issue_id_template": "cloud_api_used_{duid_slug}",
    },
}


def _register(hass, *, live_room_refresh=_LRR):
    dispatch = {
        "template": "roborock_segment_clean", "service_domain": "vacuum",
        "service_name": "send_command", "command": "app_segment_clean",
    }
    if live_room_refresh is not None:
        dispatch["live_room_refresh"] = live_room_refresh
    register_adapter_config(_VAC, {
        "adapter_id": "rb", "source": "code", "entities": {}, "dispatch": dispatch,
    })


def _link_device(hass, mock_config_entry, *, duid=_DUID, object_id="ivy"):
    """Link vacuum.{object_id} to a ('roborock', duid) device — the chain the local gate
    walks (entity -> device_id -> identifier -> issue_registry)."""
    mock_config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("roborock", duid)},
    )
    er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", f"uid-{object_id}",
        device_id=device.id, suggested_object_id=object_id,
    )
    return f"vacuum.{object_id}"


def _capture(hass):
    calls: list[dict] = []

    async def _h(call):
        calls.append(dict(call.data))
        return {"x": 1, "y": 2}  # SupportsResponse service returns a value

    # ⚠ C23: OPTIONAL, where the real roborock service is ONLY — see the note on `_LRR`.
    # This registration cannot fail a caller that forgets return_response.

    hass.services.async_register(
        "roborock", "get_vacuum_current_position", _h,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return calls


def _make_cloud_issue(hass, *, duid=_DUID):
    ir.async_create_issue(
        hass, "roborock", f"cloud_api_used_{slugify(duid)}",
        is_fixable=False, severity=ir.IssueSeverity.WARNING,
        translation_key="cloud_api_used",
    )


# --- [LRR-1] getter ----------------------------------------------------------


async def test_getter_defaults_and_overrides(hass, manager):
    """[LRR-1]"""
    _register(hass, live_room_refresh=None)
    cfg = manager.live_room_refresh._resolve_config(_VAC)
    assert cfg["enabled"] is False and cfg["service"] is None and cfg["local_gate"] is None

    _register(hass)
    cfg = manager.live_room_refresh._resolve_config(_VAC)
    assert cfg["enabled"] is True and cfg["interval_s"] == 15
    assert cfg["service"]["domain"] == "roborock"  # NOT vacuum.* (see services.py)
    assert cfg["service"]["service"] == "get_vacuum_current_position"
    assert cfg["service"]["returns_response"] is True  # SupportsResponse.ONLY
    assert cfg["local_gate"]["issue_domain"] == "roborock"

    _register(hass, live_room_refresh={**_LRR, "interval_s": "oops"})
    assert manager.live_room_refresh._resolve_config(_VAC)["interval_s"] == 15  # bad -> default
    _register(hass, live_room_refresh={**_LRR, "interval_s": 0})
    assert manager.live_room_refresh._resolve_config(_VAC)["interval_s"] == 1  # clamped to >= 1


# --- behavior ----------------------------------------------------------------


async def test_no_block_is_noop(hass, manager, mock_config_entry):
    """[LRR-2] a brand that omits the block (Eufy) never pulses."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass, live_room_refresh=None)
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert calls == []


async def test_pulse_fires_when_local(hass, manager, mock_config_entry):
    """[LRR-3] no cloud_api_used issue -> local -> pulse fires once."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert calls == [{"entity_id": vid}]


async def test_pulse_skipped_when_cloud(hass, manager, mock_config_entry):
    """[LRR-4] the cloud_api_used repair issue present -> cloud -> never pulse."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls = _capture(hass)
    _make_cloud_issue(hass)
    hass.states.async_set(vid, "cleaning")
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert calls == []


async def test_rate_limited_per_vacuum(hass, manager, mock_config_entry):
    """[LRR-5] + [LRR-9] one pulse per interval; the limiter lives in-memory on the manager."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    manager.maybe_pulse_live_room_refresh(vid)  # within interval -> coalesced
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert isinstance(manager.live_room_refresh._pulse_at, dict)  # in-memory, not persisted

    manager.live_room_refresh._pulse_at[vid] -= 999  # simulate the interval elapsing
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_skipped_when_unavailable(hass, manager, mock_config_entry):
    """[LRR-6]"""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls = _capture(hass)
    hass.states.async_set(vid, "unavailable")
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert calls == []


async def test_unsupported_service_sticky_disables(hass, manager, mock_config_entry):
    """[LRR-7] a model that raises ServiceNotSupported is dropped for the session."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls: list[int] = []

    async def _raise(call):
        calls.append(1)
        raise ServiceNotSupported("roborock", "get_vacuum_current_position", vid)

    hass.services.async_register(
        "roborock", "get_vacuum_current_position", _raise,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 1 and vid in manager.live_room_refresh._disabled

    manager.live_room_refresh._pulse_at[vid] -= 999  # even past the interval...
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 1  # ...sticky-off, never called again


async def test_transient_error_swallowed_not_disabled(hass, manager, mock_config_entry):
    """[LRR-8] position_not_found / map_failure are transient — the off-gate refresh already
    ran; do NOT sticky-disable (the no-dock S6 often has no position mid-transit)."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls: list[int] = []

    async def _raise(call):
        calls.append(1)
        raise HomeAssistantError("position_not_found")

    hass.services.async_register(
        "roborock", "get_vacuum_current_position", _raise,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 1 and vid not in manager.live_room_refresh._disabled

    manager.live_room_refresh._pulse_at[vid] -= 999
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 2  # fired again — not sticky


async def test_service_not_found_sticky_disables(hass, manager, mock_config_entry):
    """[LRR-10] regression: the service not registered on this install (ServiceNotFound, e.g.
    the wrong domain or an older Roborock integration) must sticky-disable, NOT retry every
    interval forever. This is the live bug the first deploy surfaced (vacuum.* vs roborock.*)."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)  # declares the service, but we register NO handler for it
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert vid in manager.live_room_refresh._disabled  # disabled after the first ServiceNotFound


async def test_service_validation_error_sticky_disables(
    hass, manager, mock_config_entry, caplog
):
    """[LRR-11] ServiceValidationError -- a HomeAssistantError subclass -- must be
    caught by its OWN branch (ordered before the generic HomeAssistantError catch)
    and classified PERMANENT, exactly like ServiceNotFound/ServiceNotSupported:
    sticky-disable + one WARNING. Before the fix Python's in-order except
    matching meant this landed in the generic branch, which just logs at DEBUG
    and retries every interval forever."""
    vid = _link_device(hass, mock_config_entry)
    _register(hass)
    calls: list[int] = []

    async def _raise(call):
        calls.append(1)
        raise ServiceValidationError("bad target")

    hass.services.async_register(
        "roborock", "get_vacuum_current_position", _raise,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.states.async_set(vid, "cleaning")

    with caplog.at_level("WARNING"):
        manager.maybe_pulse_live_room_refresh(vid)
        await hass.async_block_till_done()
    assert len(calls) == 1 and vid in manager.live_room_refresh._disabled
    assert "rejected the call" in caplog.text

    manager.live_room_refresh._pulse_at[vid] -= 999  # even past the interval...
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 1  # ...sticky-off, never called again


async def test_gate_failsafe_no_device(hass, manager, mock_config_entry):
    """[LRR-9] an entity with no linked device -> gate can't confirm local -> skip."""
    mock_config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "vacuum", "roborock", "uid-nodevice", suggested_object_id="ivy",
    )
    _register(hass)
    calls = _capture(hass)
    hass.states.async_set(_VAC, "cleaning")
    manager.maybe_pulse_live_room_refresh(_VAC)
    await hass.async_block_till_done()
    assert calls == []


# ---------------------------------------------------------------------------
# [LRR-12]..[LRR-15] the local-gate walk. EVERY guard here returns False and False
# means "skip", so `calls == []` is the value [LRR-2]/[LRR-4]/[LRR-6]/[LRR-9] already
# assert. Each test below therefore names what ELSE distinguishes it, and [LRR-3] --
# same device, same gate, pulse FIRES -- is the positive control for all of them.
# ---------------------------------------------------------------------------

async def test_lrr12_a_block_with_no_local_gate_is_inert_not_fatal(hass, manager, mock_config_entry):
    """[LRR-12] An adapter may declare the refresh block and omit `local_gate`.

    The gate is what decides local-vs-cloud; with none declared there is nothing to
    decide on, and the module's choice is to treat that as "not local" and skip rather
    than to pulse blindly. Skipping is the safe direction -- pulsing a cloud-connected
    vacuum is what the whole gate exists to prevent.

    THE DISCRIMINATOR IS THE ABSENCE OF A RAISE, not the empty call list. The walk
    continues to `gate.get("device_identifier_domain")`, so without this guard it
    dereferences None and raises AttributeError out of `maybe_pulse_live_room_refresh`.
    The device IS linked here deliberately: with no linked device the walk would return
    at the entity check two lines earlier and never reach the dereference, so the test
    would pass against the ablation.
    """
    vid = _link_device(hass, mock_config_entry)
    gate_less = {k: v for k, v in _LRR.items() if k != "local_gate"}
    _register(hass, live_room_refresh=gate_less)
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()

    assert calls == []


async def test_lrr13_a_gate_naming_an_unknown_identifier_domain_reads_as_cloud(
    hass, manager, mock_config_entry
):
    """[LRR-13] No device identifier in the declared domain means no duid to check.

    The gate walks entity -> device -> identifier -> issue registry, and the identifier
    domain is adapter-declared. If it names a domain this device does not carry there is
    no duid, so no issue id can be built and localness cannot be established -- which
    must read as "not local", not as "local by default".

    HERE `calls == []` IS A REAL DIFFERENTIAL, unlike [LRR-12]: with this guard removed
    the walk continues with `duid=None`, the template formats, the issue lookup misses,
    and a pulse FIRES. So the empty list distinguishes the guard working from the guard
    absent, which is why no extra observable is needed.
    """
    vid = _link_device(hass, mock_config_entry)
    wrong_domain = dict(_LRR, local_gate=dict(_LRR["local_gate"],
                                              device_identifier_domain="not_roborock"))
    _register(hass, live_room_refresh=wrong_domain)
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()

    assert calls == []


@pytest.mark.parametrize("gate_override", [
    {"issue_id_template": ""},
    {"issue_domain": None},
], ids=["no_template", "no_issue_domain"])
async def test_lrr14_a_gate_missing_either_issue_field_reads_as_cloud(
    hass, manager, mock_config_entry, gate_override
):
    """[LRR-14] Both halves of `if not template or not issue_domain`.

    The issue id is built from the template and looked up in the declared domain; with
    either missing there is no lookup to make, so localness is unestablished and the
    pulse is skipped.

    TWO CASES BECAUSE THE GUARD IS AN `or`. A single case would leave the other half
    unablated -- dropping `not template` would still be caught by `not issue_domain` and
    the test would stay green. As with [LRR-13] the empty call list is a differential:
    ablated, each of these fires a pulse.
    """
    vid = _link_device(hass, mock_config_entry)
    _register(hass, live_room_refresh=dict(
        _LRR, local_gate=dict(_LRR["local_gate"], **gate_override)))
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()

    assert calls == []


@pytest.mark.parametrize("template", [
    "cloud_api_used_{wrong_field}",
    "cloud_api_used_{0}",
    "cloud_api_used_{",
], ids=["KeyError", "IndexError", "ValueError"])
async def test_lrr15_an_unformattable_issue_template_is_caught(
    hass, manager, mock_config_entry, template
):
    """[LRR-15] A declared template is adapter data, so it can be wrong.

    `template.format(duid_slug=...)` raises three different ways depending on how the
    declaration is wrong: an unknown placeholder (KeyError), a positional one
    (IndexError), and an unclosed brace (ValueError). All three are adapter-authoring
    mistakes that must not take down a pulse attempt on a live run.

    THREE CASES FOR THREE EXCEPTIONS, because the `except` names a tuple: narrowing it
    to any one of them would leave the other two propagating, and a single-template
    test would not notice. The discriminator is again the ABSENCE of a raise out of
    `maybe_pulse_live_room_refresh` -- the empty call list is the fallback.
    """
    vid = _link_device(hass, mock_config_entry)
    _register(hass, live_room_refresh=dict(
        _LRR, local_gate=dict(_LRR["local_gate"], issue_id_template=template)))
    calls = _capture(hass)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()

    assert calls == []
