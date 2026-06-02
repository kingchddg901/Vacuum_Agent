"""Integration tests for dock/manager.py — DockManager.

Constructed against the real `manager` fixture. The gating engine
(get_dock_action_status) depends on three manager methods + the entity
resolver, all monkeypatched so each gate branch can be driven deterministically.

Coverage targets
----------------
[DK-1]  _safe_int / _display_label helpers.
[DK-2]  record_dock_event: timestamp + counter increment; debounce blocks double-count.
[DK-3]  record_dock_event: dry_start stores last_dry_duration.
[DK-4]  set_dock_event_count: overwrites; unknown event_type → error.
[DK-5]  get_dock_events: stored events; {} for unknown vacuum.
[DK-6]  get_dock_action_status: ready (docked, idle, supported, entity present).
[DK-7]  gating: unsupported_feature.
[DK-8]  gating: missing_action_entity.
[DK-9]  gating: job_active.
[DK-10] gating: not_docked.
[DK-11] gating: already_washing / already_drying / not_drying / already_emptying.
[DK-12] gating: dock_busy via adapter hard_service_states.
[DK-13] async dispatch: allowed → presses the button (performed=True).
[DK-14] async dispatch: gated → performed=False with the gate reason.
[DK-15] _get_dock_action_entity resolves a present button by candidate id.
[DK-16] async_dry_mop / async_empty_dust / async_stop_dry_mop delegate.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.dock.manager import (
    DockManager,
    _display_label,
    _safe_int,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
def dock(manager) -> DockManager:
    return DockManager(manager)


def _ready(dock, manager, hass, monkeypatch, *, supports=True, dock_status="",
           active_status="idle", docked=True, entity="button.alfred_wash_mop"):
    """Wire a baseline 'ready' gating context; callers override one field."""
    monkeypatch.setattr(manager, "get_vacuum_capabilities", lambda **kw: {
        "supports_mop_wash": supports, "supports_mop_dry": supports,
        "supports_empty_dust": supports})
    monkeypatch.setattr(manager, "get_lifecycle_state", lambda **kw: {
        "dock_status": dock_status, "lifecycle_state": "ready", "message": "ok"})
    monkeypatch.setattr(manager, "get_active_job", lambda **kw: {"status": active_status})
    monkeypatch.setattr(dock, "_get_dock_action_entity", lambda **kw: entity)
    hass.states.async_set(_VAC, "docked" if docked else "cleaning")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (5, 5), ("3.9", 3), (None, 0), ("", 0), ("unknown", 0), ("x", 0)])
def test_safe_int(value, expected):
    """[DK-1]"""
    assert _safe_int(value) == expected


def test_display_label():
    """[DK-1]"""
    assert _display_label("already_washing") == "Already Washing"
    assert _display_label(None) is None


# ---------------------------------------------------------------------------
# event recording
# ---------------------------------------------------------------------------

def test_record_event_counts_with_debounce(dock, manager):
    """[DK-2]"""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"debounce_seconds": {"last_mop_wash": 60}},
    })
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    events = dock.get_dock_events(vacuum_entity_id=_VAC)
    assert events["last_mop_wash"]  # timestamp set
    assert events["mop_wash_count"] == 1
    # immediate second event is debounced → no increment
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    assert dock.get_dock_events(vacuum_entity_id=_VAC)["mop_wash_count"] == 1


def test_record_event_malformed_debounce_timestamp(dock, manager):
    """[DK-2b] an unparseable last-counted timestamp falls through the debounce
    (except branch) and still counts, rather than crashing."""
    manager.data.setdefault("dock_events", {})[_VAC] = {
        "last_mop_wash_last_counted_at": "not-a-timestamp",
        "mop_wash_count": 0,
    }
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    assert dock.get_dock_events(vacuum_entity_id=_VAC)["mop_wash_count"] == 1


def test_record_event_dry_duration(dock):
    """[DK-3]"""
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_dry_start", dry_duration="2h")
    assert dock.get_dock_events(vacuum_entity_id=_VAC)["last_dry_duration"] == "2h"


def test_set_event_count(dock):
    """[DK-4]"""
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_dust_empty")
    result = dock.set_dock_event_count(
        vacuum_entity_id=_VAC, event_type="last_dust_empty", count=10)
    assert result["updated"] is True
    assert result["new_count"] == 10
    bad = dock.set_dock_event_count(vacuum_entity_id=_VAC, event_type="bogus", count=1)
    assert bad["updated"] is False


def test_get_events_unknown(dock):
    """[DK-5]"""
    assert dock.get_dock_events(vacuum_entity_id="vacuum.ghost") == {}


# ---------------------------------------------------------------------------
# gating
# ---------------------------------------------------------------------------

def _wash_reason(dock):
    status = dock.get_dock_action_status(vacuum_entity_id=_VAC, map_id=_MAP)
    return status["actions"]["wash_mop"]


def test_gate_ready(dock, manager, hass, monkeypatch):
    """[DK-6]"""
    _ready(dock, manager, hass, monkeypatch)
    wash = _wash_reason(dock)
    assert wash["allowed"] is True and wash["reason"] == "ready"
    full = dock.get_dock_action_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert full["can_wash_mop"] is True and full["docked"] is True


def test_gate_unsupported(dock, manager, hass, monkeypatch):
    """[DK-7]"""
    _ready(dock, manager, hass, monkeypatch, supports=False)
    assert _wash_reason(dock)["reason"] == "unsupported_feature"


def test_gate_missing_entity(dock, manager, hass, monkeypatch):
    """[DK-8]"""
    _ready(dock, manager, hass, monkeypatch, entity=None)
    assert _wash_reason(dock)["reason"] == "missing_action_entity"


def test_gate_job_active(dock, manager, hass, monkeypatch):
    """[DK-9]"""
    _ready(dock, manager, hass, monkeypatch, active_status="started")
    assert _wash_reason(dock)["reason"] == "job_active"


def test_gate_not_docked(dock, manager, hass, monkeypatch):
    """[DK-10]"""
    _ready(dock, manager, hass, monkeypatch, docked=False)
    assert _wash_reason(dock)["reason"] == "not_docked"


def test_gate_action_specific(dock, manager, hass, monkeypatch):
    """[DK-11]"""
    # Per-action service-state gating reads dock_events.triggers from the
    # adapter (core has no brand fallback), so register them like the real
    # Eufy adapter does.
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "dock_events": {"triggers": {
            "last_mop_wash": ["washing"],
            "last_dry_start": ["drying"],
            "last_dust_empty": ["emptying dust"],
        }},
    })
    _ready(dock, manager, hass, monkeypatch, dock_status="washing")
    status = dock.get_dock_action_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert status["actions"]["wash_mop"]["reason"] == "already_washing"

    _ready(dock, manager, hass, monkeypatch, dock_status="drying")
    status = dock.get_dock_action_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert status["actions"]["dry_mop"]["reason"] == "already_drying"
    # stop_dry is the inverse — only useful while drying, so '' → not_drying
    _ready(dock, manager, hass, monkeypatch, dock_status="")
    status = dock.get_dock_action_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert status["actions"]["stop_dry_mop"]["reason"] == "not_drying"

    _ready(dock, manager, hass, monkeypatch, dock_status="emptying dust")
    status = dock.get_dock_action_status(vacuum_entity_id=_VAC, map_id=_MAP)
    assert status["actions"]["empty_dust"]["reason"] == "already_emptying"


def test_gate_dock_busy(dock, manager, hass, monkeypatch):
    """[DK-12] adapter hard_service_states gates non-stop actions as dock_busy."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test",
        "vocabulary": {"hard_service_states": ["servicing"]},
    })
    _ready(dock, manager, hass, monkeypatch, dock_status="servicing")
    assert _wash_reason(dock)["reason"] == "dock_busy"


# ---------------------------------------------------------------------------
# async dispatch
# ---------------------------------------------------------------------------

async def test_dispatch_performed(dock, hass, monkeypatch):
    """[DK-13]"""
    pressed: list = []
    hass.services.async_register("button", "press", lambda call: pressed.append(call.data))
    monkeypatch.setattr(dock, "get_dock_action_status", lambda **kw: {
        "actions": {"wash_mop": {"allowed": True, "entity_id": "button.alfred_wash_mop"}},
        "dock_status": "idle", "lifecycle_state": "ready"})
    result = await dock.async_wash_mop(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["performed"] is True
    assert pressed and pressed[0]["entity_id"] == "button.alfred_wash_mop"


async def test_dispatch_gated(dock, monkeypatch):
    """[DK-14]"""
    monkeypatch.setattr(dock, "get_dock_action_status", lambda **kw: {
        "actions": {"wash_mop": {"allowed": False, "reason": "not_docked",
                                 "message": "dock first"}},
        "dock_status": "idle", "lifecycle_state": "ready"})
    result = await dock.async_wash_mop(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["performed"] is False
    assert result["reason"] == "not_docked"


def test_get_action_entity_resolves(dock, hass):
    """[DK-15] a present button entity is resolved by its adapter suffix."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"action_buttons": {
            "wash_mop": {"entity_suffixes": ["wash_mop", "mop_wash"], "token_sets": []},
        }},
    })
    hass.states.async_set("button.alfred_wash_mop", "idle")
    assert dock._get_dock_action_entity(
        vacuum_entity_id=_VAC, action="wash_mop") == "button.alfred_wash_mop"
    assert dock._get_dock_action_entity(vacuum_entity_id=_VAC, action="bogus") is None


def test_get_action_entity_token_fallback(dock, hass):
    """[DK-17] when no entity_suffix matches, the token_sets registry fallback
    resolves a differently-named button (firmware-naming drift)."""
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"action_buttons": {
            # named suffix is absent; only the token fallback can match
            "wash_mop": {"entity_suffixes": ["wash_mop"], "token_sets": [["wash", "mop"]]},
        }},
    })
    # A registry button whose id carries the tokens but not the named suffix.
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_station_wash_mop_now",
        suggested_object_id="alfred_station_wash_mop_now",
    )
    assert dock._get_dock_action_entity(
        vacuum_entity_id=_VAC, action="wash_mop") == "button.alfred_station_wash_mop_now"


@pytest.mark.parametrize("method,action", [
    ("async_dry_mop", "dry_mop"),
    ("async_empty_dust", "empty_dust"),
    ("async_stop_dry_mop", "stop_dry_mop"),
])
async def test_dispatch_wrappers(dock, monkeypatch, method, action):
    """[DK-16] each wrapper routes to _async_run_dock_action with its action."""
    monkeypatch.setattr(dock, "get_dock_action_status", lambda **kw: {
        "actions": {action: {"allowed": False, "reason": "not_docked", "message": "m"}},
        "dock_status": "idle", "lifecycle_state": "ready"})
    result = await getattr(dock, method)(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["action"] == action
    assert result["performed"] is False
