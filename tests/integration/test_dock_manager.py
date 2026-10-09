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
[DOCK-1] record_dock_event: a debounced event leaves the raw timestamp untouched too
        (not just the counter) -- the whole record is a no-op.
[DOCK-2] record_dock_event: an unknown event_type is refused outright, mirroring
        set_dock_event_count's own validation -- no write at all.
[DOCK-3] set_dock_event_count: resetting a counter also clears its debounce marker
        so a legitimate post-reset event isn't suppressed by a stale window.
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
[DK-17] _get_dock_action_entity: token_sets fallback resolves a drift-named button.
[DK-18] gating: job_active also covers an app-started (external) run.
[DK-19] _get_dock_action_entity: all four actions resolve on a device whose buttons
        do not share the vacuum's stem, including dry_mop against the stop_dry_mop
        token collision (issue #49) -- the CALLER arms the ownership guard.
[DK-20] A GERMAN Roborock dock switch resolves, from a real capture: the entity id
        shares nothing with the declared English suffixes and only the upstream
        translation_key rung can bind it.
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
    """[DK-2b] with a NON-ZERO debounce configured, an unparseable stored
    ``*_last_counted_at`` makes ``datetime.fromisoformat`` raise; the except
    branch swallows it, leaves ``should_count`` True, and still counts the
    event (rather than crashing or silently dropping the count).

    The non-zero debounce is load-bearing: without it ``debounce == 0`` skips
    the whole try/except, so this case must register one to actually reach the
    malformed-timestamp recovery path.
    """
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"debounce_seconds": {"last_mop_wash": 60}},
    })
    # Seed an unparseable last-counted timestamp so the debounce comparison
    # (which only runs because debounce > 0) hits the except branch.
    manager.data.setdefault("dock_events", {})[_VAC] = {
        "last_mop_wash_last_counted_at": "not-a-timestamp",
        "mop_wash_count": 0,
    }
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    events = dock.get_dock_events(vacuum_entity_id=_VAC)
    assert events["mop_wash_count"] == 1
    # the recovery rewrote last_counted_at to a parseable value, so a second
    # immediate event is now genuinely debounced (proves we took the count path,
    # not that debounce was a no-op).
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


def test_record_event_unknown_type_no_write(dock):
    """[DOCK-2] record_dock_event validates event_type against the same
    counter_map its sibling set_dock_event_count already validates against
    -- an unknown type is refused outright: no timestamp write at all."""
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="not_a_real_type")
    assert dock.get_dock_events(vacuum_entity_id=_VAC) == {}


def test_record_event_debounced_leaves_timestamp_untouched(dock, manager):
    """[DOCK-1] a debounced (should_count=False) event is a complete no-op --
    the raw last-seen timestamp must not move either, or the timestamp and
    counter fields end up disagreeing about whether a wash actually
    happened."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"debounce_seconds": {"last_mop_wash": 300}},
    })
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    first = dock.get_dock_events(vacuum_entity_id=_VAC)
    first_ts = first["last_mop_wash"]
    assert first["mop_wash_count"] == 1

    # immediate second event -- well inside the 300s debounce window.
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    events = dock.get_dock_events(vacuum_entity_id=_VAC)
    assert events["last_mop_wash"] == first_ts
    assert events["mop_wash_count"] == 1


def test_reset_clears_debounce_marker(dock, manager):
    """[DOCK-3] set_dock_event_count's reset also clears the debounce
    marker (f"{event_type}_last_counted_at") -- otherwise a legitimate
    event right after the reset can still be suppressed by a debounce
    window measured from BEFORE the reset."""
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"debounce_seconds": {"last_mop_wash": 300}},
    })
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    assert dock.get_dock_events(vacuum_entity_id=_VAC)["mop_wash_count"] == 1

    dock.set_dock_event_count(vacuum_entity_id=_VAC, event_type="last_mop_wash", count=0)
    assert "last_mop_wash_last_counted_at" not in dock.get_dock_events(vacuum_entity_id=_VAC)

    # a legitimate wash immediately after the reset -- inside what WOULD
    # have been the old (pre-reset) debounce window -- must still count.
    dock.record_dock_event(vacuum_entity_id=_VAC, event_type="last_mop_wash")
    assert dock.get_dock_events(vacuum_entity_id=_VAC)["mop_wash_count"] == 1


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


def test_gate_job_active_external(dock, manager, hass, monkeypatch):
    """[DK-18] RP-014 / #12:A6-VAC-1 — the robot is docked MID app-started run.

    The realistic trigger is a mid-run dock visit (recharge or mop wash) where
    vacuum.state is "docked" and the user presses Empty Dust from the card. The
    gate asked the QUEUE's question ({"started", "paused"}) about the robot, so
    an app-started run read as no run at all and a wash/dry/empty could actuate
    under a live run. This one fires hardware.
    """
    _ready(dock, manager, hass, monkeypatch, active_status="external")
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
        "dock_events": {"action_controls": {
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
        "dock_events": {"action_controls": {
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


def test_get_action_entity_dry_mop_survives_the_stop_dry_mop_collision(
    dock, hass, manager, monkeypatch
):
    """[DK-19] issue #49, reproduced at ptruman's shape and through the real caller.

    His vacuum is `vacuum.robovac_x10_pro_omni` while its buttons carry the
    `living_room_eufy_clean_x10_pro_omni` stem, so the derived-suffix lookup misses
    every action and the token fallback is what resolves them. Three resolved.
    `dry_mop` did not -- its `["dry", "mop"]` also matches `_stop_dry_mop`, two
    siblings matched, and it abstained. The button existed and was enabled the
    whole time.

    The vocabulary here is the REAL `buttons.py` data through the REAL adapter
    builder, not a hand-written block: this bug IS the vocabulary, so a fixture
    that invents its own tokens can only prove the guard runs, never that it
    covers the shipped token sets.
    """
    from homeassistant.helpers import entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    from custom_components.eufy_vacuum.adapters.eufy.adapter import _build_button_blocks
    from custom_components.eufy_vacuum.adapters.eufy.buttons import (
        DOCK_ACTION_CANDIDATES,
        DOCK_ACTION_TOKENS,
    )
    from custom_components.eufy_vacuum.core import manager as _mgr

    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"action_controls": _build_button_blocks(
            DOCK_ACTION_CANDIDATES, DOCK_ACTION_TOKENS)},
    })

    stem = "button.living_room_eufy_clean_x10_pro_omni"
    siblings = [f"{stem}_wash_mop", f"{stem}_dry_mop",
                f"{stem}_stop_dry_mop", f"{stem}_empty_dust_bin"]
    monkeypatch.setattr(_mgr, "sweep_siblings", lambda reg, entry: (siblings, 1))
    # Faithful to his registry: the vacuum resolves, `button.alfred_*` does not --
    # which is precisely why the token fallback is reached at all.
    monkeypatch.setattr(
        er.async_get(manager.hass), "async_get",
        lambda eid: object() if eid == _VAC else None, raising=False)

    assert dock.get_dock_action_entities(vacuum_entity_id=_VAC) == {
        "wash_mop": f"{stem}_wash_mop",
        "dry_mop": f"{stem}_dry_mop",
        "stop_dry_mop": f"{stem}_stop_dry_mop",
        "empty_dust": f"{stem}_empty_dust_bin",
    }


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


# --- the dock is DECLARED, not assumed to be buttons (issue #66 seam) --------


def _declare_controls(controls):
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
    register_adapter_config(_VAC, {
        "adapter_id": "eufy_test", "source": "code",
        "dock_events": {"action_controls": controls},
    })


def test_dc_1_a_switch_driven_control_resolves_in_its_own_domain(dock, hass):
    """[DC-1] THE RED INPUT. A dock whose controls are SWITCHES, not buttons.

    Roborock publishes no dock button at all — wash/dry/empty are switches
    (mop_washing / mop_drying / dust_emptying). Resolution was hardcoded to the
    button domain, so such a control could not be found no matter what an adapter
    declared.

    ABLATION: put `domain="button"` back in the resolver and this goes red — the
    entity is a switch, so the button-prefixed id does not exist.
    """
    _declare_controls({
        "wash_mop": {"entity_suffixes": ["mop_washing"], "domain": "switch",
                     "service": "turn_on"},
    })
    hass.states.async_set("switch.alfred_mop_washing", "off")
    assert dock._get_dock_action_entity(
        vacuum_entity_id=_VAC, action="wash_mop") == "switch.alfred_mop_washing"


def test_dc_3_an_undeclared_domain_still_means_a_button_press(dock, hass):
    """[DC-3] THE NO-REGRESSION GUARD. Every brand that shipped before this declared
    neither domain nor service, and must keep resolving exactly as it did.

    Defaults are button/press, so Eufy and Dreame are byte-identical. If this goes
    red, the rename broke the two brands that already had dock support.
    """
    _declare_controls({
        "wash_mop": {"entity_suffixes": ["wash_mop"], "token_sets": []},
    })
    hass.states.async_set("button.alfred_wash_mop", "idle")
    assert dock._get_dock_action_entity(
        vacuum_entity_id=_VAC, action="wash_mop") == "button.alfred_wash_mop"


def test_dc_4_the_token_fallback_stays_button_only(dock, hass):
    """[DC-4] The registry fallback scans `button.{object_id}_`, so running it for a
    non-button control could only ever return a wrong entity or nothing.

    A switch control with ONLY token_sets resolves to nothing — deliberately. The
    honest path for a non-button control is entity_suffixes, which go through the
    act-path ladder and survive a localized install.
    """
    from homeassistant.helpers import entity_registry as er
    _declare_controls({
        "wash_mop": {"entity_suffixes": [], "token_sets": [["wash", "mop"]],
                     "domain": "switch", "service": "turn_on"},
    })
    er.async_get(hass).async_get_or_create(
        "button", "eufy_vacuum", "alfred_station_wash_mop_now",
        suggested_object_id="alfred_station_wash_mop_now",
    )
    assert dock._get_dock_action_entity(vacuum_entity_id=_VAC, action="wash_mop") is None


def test_dc_5_a_non_button_domain_without_a_service_is_refused_not_guessed():
    """[DC-5] "switch" alone does not say turn_on or turn_off, and DC-2's pair uses
    BOTH on one entity — so a default here would be a coin flip on physical hardware.

    The helper returns no service, and the dispatch refuses rather than pressing
    something. Guessing turn_on would, on the dry pair, be a 50% chance of starting
    a dryer the user asked to stop.
    """
    from custom_components.eufy_vacuum.dock.manager import _dock_control
    cfg = {"dock_events": {"action_controls": {
        "wash_mop": {"entity_suffixes": ["mop_washing"], "domain": "switch"},
    }}}
    control = _dock_control(cfg, "wash_mop")
    assert control["domain"] == "switch"
    assert control["service"] is None, "a service was guessed for a non-button domain"

    # ...while the button default is still supplied, because it is unambiguous.
    cfg_btn = {"dock_events": {"action_controls": {"wash_mop": {"entity_suffixes": ["w"]}}}}
    assert _dock_control(cfg_btn, "wash_mop")["service"] == "press"


def test_dk20_a_german_dock_switch_resolves_on_the_translation_key(
    dock, hass, mock_config_entry
):
    """[DK-20] REAL-WORLD INPUT, from the history export on issue #62 (a Roborock
    Saros 20 Sonic on a German install).

    Home Assistant builds an entity id from the TRANSLATED name, so the dock switches
    there are `dock_moppwasche` / `dock_mopp_trocknung` / `dock_staubentleerung`. The
    adapter declares English suffixes (`dock_mop_washing`, `mop_washing`), which share
    no substring with those, and no token_sets -- so rungs 1 and 2 cannot bind and
    neither can the token fallback. Only rung 3, matching the upstream
    `translation_key`, speaks German.

    That rung exists (issue #51) and the second declared suffix doubles as the key --
    the harness recorded `switch.<obj>_dock_mop_washing` carrying
    `translation_key: "mop_washing"`. This pins that the two halves still line up: a
    rename of either the declaration or the upstream key breaks a localized install
    silently, because the failure mode is a button that never appears.

    ABLATION: drop "mop_washing" from entity_suffixes and this goes red.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from custom_components.eufy_vacuum.adapters.registry import register_adapter_config

    # Roborock's own declaration, verbatim.
    register_adapter_config(_VAC, {
        "adapter_id": "roborock", "source": "code",
        "dock_events": {"action_controls": {
            "wash_mop": {
                "entity_suffixes": ["dock_mop_washing", "mop_washing"],
                "domain": "switch", "service": "turn_on",
            },
        }},
    })

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    if mock_config_entry.entry_id not in hass.config_entries.async_entry_ids():
        mock_config_entry.add_to_hass(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("roborock", "saros20")},
    )
    # The vacuum must be in the registry: rungs 2 and 3 sweep siblings from it.
    ent_reg.async_get_or_create(
        "vacuum", "roborock", "saros20_vac",
        suggested_object_id="alfred", device_id=device.id,
    )
    # The German switch -- id shares nothing with either declared suffix.
    german = ent_reg.async_get_or_create(
        "switch", "roborock", "saros20_mop_washing",
        suggested_object_id="saros_20_sonic_complete_dock_moppwasche",
        device_id=device.id,
        translation_key="mop_washing",
    )
    assert german.entity_id == "switch.saros_20_sonic_complete_dock_moppwasche"
    for _suffix in ("dock_mop_washing", "mop_washing"):
        assert not german.entity_id.endswith(_suffix), (
            "the fixture must not be resolvable by suffix, or it proves nothing"
        )
    hass.states.async_set(german.entity_id, "off")

    resolved = dock._get_dock_action_entity(vacuum_entity_id=_VAC, action="wash_mop")

    assert resolved == german.entity_id, (
        "a localized dock switch must bind through its upstream translation_key; "
        "without that rung the user sees no dock buttons at all and nothing in the log "
        f"says why (got {resolved!r})"
    )
