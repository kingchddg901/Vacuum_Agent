"""Integration tests for job_active_signal.py — presence probe + observation trace.

The module exists because ``is_job_active`` collapses three different situations
into ``False`` (exists-and-off / registered-but-stateless / never created) and
only the third is issue #46. These tests pin that distinction, and pin the
module's defining property: it OBSERVES and never decides.

Coverage targets
----------------
[JAS-1]  probe_presence: entity present in the state machine.
[JAS-2]  probe_presence: registered but stateless -> NOT never_created (restart window).
[JAS-3]  probe_presence: absent from both -> never_created (the #46 shape).
[JAS-4]  probe_presence: adapter declares nothing -> declared False, never_created False.
[JAS-5]  observation: native carries the binary's state; "absent" when it does not exist.
[JAS-6]  observation: the substitute signals are read when declared.
[JAS-7]  observe() is best-effort — a broken state machine cannot disturb a run.
[JAS-8]  observe() emits exactly one decision-log record, under the stable event id.
"""

from __future__ import annotations

import logging

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.job_active_signal import (
    observation,
    observe,
    probe_presence,
)

_VAC = "vacuum.ivy"
_BIN = "binary_sensor.ivy_cleaning"


def _register(**entities):
    register_adapter_config(_VAC, {
        "adapter_id": "test",
        "source": "test",
        "entities": {"job_active": _BIN, **entities},
        "completion": {"require_job_active_clear": True},
    })


def test_presence_state_machine_hit(hass):
    """[JAS-1]"""
    _register()
    hass.states.async_set(_BIN, "on")

    p = probe_presence(hass, _VAC)
    assert (p.declared, p.has_state, p.state) == (True, True, "on")
    assert p.never_created is False


def test_presence_registered_but_stateless_is_not_never_created(hass):
    """[JAS-2] the ordinary boot/restart window must NOT read as the #46 shape.

    A registered entity with no state yet is a device still materialising. Calling
    that "never created" would make the fallback engage during every restart.
    """
    from homeassistant.helpers import entity_registry as er

    _register()
    er.async_get(hass).async_get_or_create(
        "binary_sensor", "roborock", "ivy-cleaning-unique",
        suggested_object_id="ivy_cleaning",
    )
    assert hass.states.get(_BIN) is None

    p = probe_presence(hass, _VAC)
    assert (p.has_state, p.in_registry) == (False, True)
    assert p.never_created is False


def test_presence_absent_from_both_is_never_created(hass):
    """[JAS-3] THE #46 SHAPE: declared, but in neither the state machine nor the
    registry — HA 2026.7 simply never created it."""
    _register()
    assert hass.states.get(_BIN) is None

    p = probe_presence(hass, _VAC)
    assert (p.declared, p.has_state, p.in_registry) == (True, False, False)
    assert p.never_created is True


def test_presence_undeclared_is_not_never_created(hass):
    """[JAS-4] a brand that declares no job_active (Eufy) is not 'broken' — the
    guard is simply a no-op there, and must not trip the #46 branch."""
    register_adapter_config(_VAC, {
        "adapter_id": "test", "source": "test", "entities": {},
    })
    p = probe_presence(hass, _VAC)
    assert (p.declared, p.never_created) == (False, False)


def test_observation_native_is_ground_truth(hass):
    """[JAS-5] `native` is the label a healthy vacuum supplies for the tick —
    the reason a trace from working hardware can validate a rule for broken
    hardware. It reads "absent" (not "off") when the entity does not exist,
    because conflating those two is the original bug."""
    _register()
    hass.states.async_set(_VAC, "cleaning")

    hass.states.async_set(_BIN, "off")
    assert observation(hass, _VAC)["native"] == "off"

    hass.states.async_remove(_BIN)
    obs = observation(hass, _VAC)
    assert obs["native"] == "absent"
    assert obs["never_created"] is True


def test_observation_reads_substitute_signals(hass):
    """[JAS-6] the candidate discriminators are captured when the adapter
    declares them, so the trace can be scored offline against `native`."""
    _register(
        last_clean_end="sensor.ivy_last_clean_end",
        total_cleaning_count="sensor.ivy_total_cleaning_count",
        battery="sensor.ivy_battery",
        task_status="sensor.ivy_status",
    )
    hass.states.async_set(_BIN, "on")
    hass.states.async_set(_VAC, "docked")
    hass.states.async_set("sensor.ivy_last_clean_end", "2026-08-02T06:35:08+00:00")
    hass.states.async_set("sensor.ivy_total_cleaning_count", "326")
    hass.states.async_set("sensor.ivy_battery", "73")
    hass.states.async_set("sensor.ivy_status", "charging")

    obs = observation(hass, _VAC)
    assert obs["lce"] == "2026-08-02T06:35:08+00:00"
    assert obs["count"] == "326"
    assert obs["batt"] == "73"
    assert obs["task"] == "charging"
    assert obs["docked"] is True
    assert obs["state_s"] is not None


def test_observe_is_best_effort(hass, monkeypatch):
    """[JAS-7] a diagnostic that can abort a live clean is worse than none.

    Force the read path to raise and assert observe() still returns cleanly.
    """
    from custom_components.eufy_vacuum import job_active_signal as mod

    _register()

    def _boom(*a, **kw):
        raise RuntimeError("exploded")

    # a failure while READING state must not escape...
    monkeypatch.setattr(mod, "probe_presence", _boom)
    observe(hass, _VAC)

    # ...nor one while EMITTING the record
    monkeypatch.undo()
    monkeypatch.setattr(mod, "emit", _boom)
    observe(hass, _VAC)


def test_observe_emits_one_record_under_stable_id(hass, caplog):
    """[JAS-8] the event id is the contract and the test anchor (decision_log)."""
    _register()
    hass.states.async_set(_BIN, "on")
    hass.states.async_set(_VAC, "cleaning")

    with caplog.at_level(logging.DEBUG,
                         logger="custom_components.eufy_vacuum.decision_log"):
        observe(hass, _VAC)

    records = [r for r in caplog.records if "job_active.observe" in r.getMessage()]
    assert len(records) == 1
    assert '"native"' in records[0].getMessage()


def test_observe_never_gates_anything():
    """[JAS-8b] the module's defining property, pinned as a test rather than a
    comment: nothing in the completion path may import a decision from here.

    job_active_signal exposes no predicate — no is_active(), no should_finalize().
    If someone adds one, this fails and they have to justify it deliberately.
    """
    from custom_components.eufy_vacuum import job_active_signal as mod

    public = {n for n in dir(mod) if not n.startswith("_")}
    decision_shaped = {
        n for n in public
        if n.startswith(("is_", "should_", "can_", "must_")) or n.endswith("_verdict")
    }
    assert not decision_shaped, (
        f"job_active_signal grew a decision function: {decision_shaped}. It is an "
        "observation module; a rule that gates completion belongs behind a "
        "deliberate design change, not here."
    )
