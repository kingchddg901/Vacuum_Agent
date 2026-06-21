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
"""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError, ServiceNotSupported
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import slugify

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

_VAC = "vacuum.ivy"
_DUID = "57R4LhSyBB7y24BiKWWGiI"

_LRR = {
    "enabled": True,
    "interval_s": 15,
    "service": {"domain": "vacuum", "service": "get_vacuum_current_position"},
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

    hass.services.async_register("vacuum", "get_vacuum_current_position", _h)
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
    cfg = manager._live_room_refresh(_VAC)
    assert cfg["enabled"] is False and cfg["service"] is None and cfg["local_gate"] is None

    _register(hass)
    cfg = manager._live_room_refresh(_VAC)
    assert cfg["enabled"] is True and cfg["interval_s"] == 15
    assert cfg["service"]["service"] == "get_vacuum_current_position"
    assert cfg["local_gate"]["issue_domain"] == "roborock"

    _register(hass, live_room_refresh={**_LRR, "interval_s": "oops"})
    assert manager._live_room_refresh(_VAC)["interval_s"] == 15  # bad -> default
    _register(hass, live_room_refresh={**_LRR, "interval_s": 0})
    assert manager._live_room_refresh(_VAC)["interval_s"] == 1  # clamped to >= 1


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
    assert isinstance(manager._live_room_pulse_at(), dict)  # in-memory, not persisted

    manager._live_room_pulse_at()[vid] -= 999  # simulate the interval elapsing
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
        raise ServiceNotSupported("vacuum", "get_vacuum_current_position", vid)

    hass.services.async_register("vacuum", "get_vacuum_current_position", _raise)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 1 and vid in manager._live_room_pulse_off()

    manager._live_room_pulse_at()[vid] -= 999  # even past the interval...
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

    hass.services.async_register("vacuum", "get_vacuum_current_position", _raise)
    hass.states.async_set(vid, "cleaning")

    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 1 and vid not in manager._live_room_pulse_off()

    manager._live_room_pulse_at()[vid] -= 999
    manager.maybe_pulse_live_room_refresh(vid)
    await hass.async_block_till_done()
    assert len(calls) == 2  # fired again — not sticky


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
