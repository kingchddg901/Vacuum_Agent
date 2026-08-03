"""Proof RP-033 (RF-32) — adapter-config seam hardened.

Six cases, all driven:

  1. save_adapter_config with a two-key config (adapter_id + dispatch.template
     only) shadows the live code adapter — every omitted block (entities,
     dispatch.service_domain/service_name, ...) silently resolves through the
     registry's own Eufy-shaped fallbacks.
  2. delete_adapter_config unregisters the live adapter and never re-registers
     anything — the vacuum is left with NO adapter at all, not even reverted
     to the code adapter that was live before any config was ever saved.
  3. (SETUP-9) setup.steps accepts any string — three places in this codebase
     already claim an unknown step id is "rejected at registration" while
     nothing did.
  4. (DE-3) dispatch.command being entirely ABSENT (the legacy/back-compat
     shape, distinct from an explicit null) silently resolves to the Eufy
     room_clean envelope with no signal the omission was ever decided.
  5. (VAC-3) core.manager.refresh_vacuum_capabilities claims to reuse "the
     same entity candidates ... as startup" but actually derives a REDUCED,
     one-candidate-per-persisted-entity set, dropping every probe-only,
     multi-candidate key (e.g. Eufy's wash_mop_button, which never makes it
     into the persisted `entities` dict at all).
  6. (POSE-4/WD-5) _validate_adapter already computes real issues for a
     non-positive room_attribution tuning value (existing check) and a
     non-positive dispatch.phase_timing value (new check) but the caller only
     ever logged them as warnings, registering the broken config anyway.

save_adapter_config (services/adapter_config.py:57-94, pre-fix) checked
exactly two keys before registering: config.get("adapter_id") and config.get(
"dispatch", {}).get("template"). Nothing else was validated against
ADAPTER_CONFIG_SCHEMA before _register(vacuum_entity_id, config) replaced
whatever adapter was live. delete_adapter_config (pre-fix, line 97-115)
unregistered the live adapter (unregister_adapter_config) and never
re-registered anything.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_adapter_seam.py
"""

from __future__ import annotations

import logging
import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from homeassistant.exceptions import ServiceValidationError   # noqa: E402
from homeassistant.helpers import entity_registry as er   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import (   # noqa: E402
    register_adapter_config, get_adapter_config,
)
from custom_components.eufy_vacuum.const import DOMAIN, DATA_RUNTIME   # noqa: E402
from custom_components.eufy_vacuum.services.adapter_config import (   # noqa: E402
    _handle_save_adapter_config, _handle_delete_adapter_config,
)

VAC = H.VAC


class _EmptyEntityRegistry:
    """Inert stand-in for HA's entity registry: knows nothing about anything.

    Same pattern as _proof_inflight_askers.py's _EmptyEntityRegistry — a plain
    class (not SimpleNamespace, which is unhashable) stashed into
    ``hass.data[er.DATA_REGISTRY]`` so HA's ``singleton``-decorated
    ``er.async_get(hass)`` returns this instead of constructing/loading a real
    EntityRegistry (which needs a full async_setup this harness doesn't run).
    Cases 2 and 5 exercise the real adapter-builder / capability-detection
    code, which resolves entities through the registry as a fallback after
    the state-machine lookup.
    """

    def async_get(self, _entity_id):
        return None

_LIVE_CODE_ADAPTER = {
    "adapter_id": "eufy", "source": "code",
    "entities": {"task_status": "sensor.alfred_task", "dock_status": "sensor.alfred_dock"},
    "dispatch": {"template": "eufy_room_clean", "service_domain": "vacuum",
                 "service_name": "send_command", "command": "room_clean"},
}

# A genuinely schema-complete stored config — distinct from the deliberately
# incomplete two-key config in Case 1 — used wherever a case needs save to
# actually SUCCEED (Case 2's delete round-trip needs something real to delete).
_VALID_STORED_CONFIG = {
    "adapter_id": "custom",
    "dispatch": {
        "template": "generic_room_ids",
        "service_domain": "vacuum",
        "service_name": "send_command",
    },
    "entities": {"task_status": "sensor.custom_task"},
}


def main() -> int:
    proof = H.Proof("RP-033", "adapter-config seam hardened")
    import asyncio

    # -------------------------------------------------------------------
    # Case 1: a two-key config shadows the live code adapter.
    # -------------------------------------------------------------------
    hass = H.make_hass()
    register_adapter_config(VAC, dict(_LIVE_CODE_ADAPTER))
    mgr = H.ManagerStub(hass=hass)
    mgr.async_save = H.async_noop()
    hass.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr

    class _Call:
        data = {
            "vacuum_entity_id": VAC,
            "config": {"adapter_id": "custom", "dispatch": {"template": "generic"}},
        }

    try:
        asyncio.run(_handle_save_adapter_config(hass, _Call()))
        _save_raised = False
    except ServiceValidationError:
        _save_raised = True
    after_save = get_adapter_config(VAC) or {}

    proof.case(
        "a two-key config (adapter_id + dispatch.template only) is saved",
        before=(not _save_raised)
        and after_save.get("adapter_id") == "custom"
        and "entities" not in after_save,
        before_msg="the two-key config registers OVER the live 'eufy' code "
                   "adapter -- entities/discovery/capabilities are all "
                   "silently absent, so every consumer that reads them "
                   "falls through to the Eufy-shaped default regardless of "
                   "what this vacuum actually is",
        after=_save_raised and after_save.get("adapter_id") == "eufy",
        after_msg="ADAPTER_CONFIG_SCHEMA is applied at save time -- missing "
                  "required blocks raise ServiceValidationError, so the "
                  "live 'eufy' adapter is never shadowed by an incomplete "
                  "config",
        detail=f"save raised={_save_raised} · registered config after save={after_save}",
    )

    # -------------------------------------------------------------------
    # Case 2: delete leaves NO adapter registered at all.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    # delete's restore path calls register_brand_adapter -> the REAL Eufy
    # adapter builder, which resolves device-registry model via the entity
    # registry as a fallback — see _EmptyEntityRegistry above.
    hass2.data[er.DATA_REGISTRY] = _EmptyEntityRegistry()
    register_adapter_config(VAC, dict(_LIVE_CODE_ADAPTER))
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2.async_save = H.async_noop()
    hass2.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr2

    class _ValidSaveCall:
        data = {"vacuum_entity_id": VAC, "config": dict(_VALID_STORED_CONFIG)}

    # a stored (UI-saved) config must exist for delete to do anything -- save
    # one for real first. Uses the schema-COMPLETE config (not Case 1's
    # deliberately incomplete one) since this save must actually succeed.
    asyncio.run(_handle_save_adapter_config(hass2, _ValidSaveCall()))

    class _DeleteCall:
        data = {"vacuum_entity_id": VAC}

    asyncio.run(_handle_delete_adapter_config(hass2, _DeleteCall()))
    after_delete = get_adapter_config(VAC)

    proof.case(
        "the stored adapter config is deleted",
        before=after_delete is None,
        before_msg="delete_adapter_config unregisters the live adapter and "
                   "never re-registers anything -- the vacuum now has NO "
                   "adapter at all until the next full HA restart",
        after=after_delete is not None and after_delete.get("source") == "code",
        after_msg="delete_adapter_config removes the stored row AND "
                  "re-registers the code adapter, so the vacuum keeps "
                  "working immediately",
        detail=f"registered config after delete={after_delete}",
    )

    # -------------------------------------------------------------------
    # Case 3 (SETUP-9): setup.steps carries an unrecognized step id.
    # -------------------------------------------------------------------
    setup9_config = {
        "adapter_id": "setup9_test",
        "source": "config",
        "setup": {"steps": ["add_vacuum", "made_up_step", "save_rooms"]},
    }
    try:
        register_adapter_config(VAC, dict(setup9_config))
        _setup9_raised = False
    except ServiceValidationError:
        _setup9_raised = True
    _setup9_after = get_adapter_config(VAC)
    _setup9_registered = (
        isinstance(_setup9_after, dict)
        and _setup9_after.get("adapter_id") == "setup9_test"
    )

    proof.case(
        "a stored config declares setup.steps=['add_vacuum','made_up_step','save_rooms']",
        before=(not _setup9_raised) and _setup9_registered,
        before_msg="three places in this codebase already claim an unknown "
                   "setup step id is 'rejected at registration' "
                   "(config_schema.py's own field description, "
                   "setup/drift.py:52-53 and :102-104's docstring) while "
                   "nothing here actually did that -- the bogus step id "
                   "registers cleanly",
        after=_setup9_raised and not _setup9_registered,
        after_msg="_validate_adapter now flags an unknown setup.steps id "
                  "(reading the canonical set from ADAPTER_CONFIG_SCHEMA "
                  "itself) and a STORED config's issues are hard-raised, so "
                  "the three prose claims are finally true",
        detail=f"raised={_setup9_raised} · registered after={_setup9_after}",
    )

    # -------------------------------------------------------------------
    # Case 4 (DE-3): dispatch.command entirely ABSENT (not null) -- the
    # legacy/back-compat shape that silently resolved to room_clean with
    # no signal the omission was ever actually decided.
    # -------------------------------------------------------------------
    from custom_components.eufy_vacuum.dispatch.manager import DispatchManager

    hass4 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "de3_test", "source": "code",
        "dispatch": {"service_domain": "vacuum", "service_name": "send_command"},
    })
    mgr4 = H.ManagerStub(hass=hass4)
    dm4 = DispatchManager(manager=mgr4)

    class _LogCapture(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.messages: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.messages.append(record.getMessage())

    _cap = _LogCapture()
    _dispatch_logger = logging.getLogger(
        "custom_components.eufy_vacuum.dispatch.manager"
    )
    _prev_level = _dispatch_logger.level
    _dispatch_logger.addHandler(_cap)
    _dispatch_logger.setLevel(logging.WARNING)
    try:
        asyncio.run(
            dm4._dispatch_clean_payload(vacuum_entity_id=VAC, payload={"rooms": []})
        )
    finally:
        _dispatch_logger.removeHandler(_cap)
        _dispatch_logger.setLevel(_prev_level)

    _de3_warned = any(
        "dispatch.command" in m and "does not declare" in m for m in _cap.messages
    )
    _de3_sent = hass4.services.sent("vacuum", "send_command")
    _de3_used_default = bool(_de3_sent) and _de3_sent[0]["data"].get("command") == "room_clean"

    proof.case(
        "an adapter's dispatch block never declares 'command' at all",
        before=_de3_used_default and not _de3_warned,
        before_msg="an absent dispatch.command silently resolves to the "
                   "Eufy room_clean wrapped envelope with zero signal that "
                   "the omission was ever decided (vs. an EXPLICIT null, "
                   "which correctly and intentionally produces the "
                   "direct-merge envelope)",
        after=_de3_used_default and _de3_warned,
        after_msg="the resolved envelope is byte-identical (zero behaviour "
                  "change) but a deprecation-style warning now names the "
                  "vacuum and tells the adapter author to declare command "
                  "explicitly -- a string for wrapped, null for direct-merge",
        detail=f"warned={_de3_warned} · dispatched={_de3_sent}",
    )

    # -------------------------------------------------------------------
    # Case 5 (VAC-3): a capability REFRESH must re-supply the SAME FULL
    # entity_candidates dict startup used, not a reduced one-candidate-
    # per-persisted-entity version that drops every probe-only,
    # multi-candidate key.
    # -------------------------------------------------------------------
    from custom_components.eufy_vacuum.core.manager import EufyVacuumManager

    hass5 = H.make_hass()
    # detect_capabilities' _any_present() checks the entity registry as a
    # fallback after the state-machine lookup — see _EmptyEntityRegistry above.
    hass5.data[er.DATA_REGISTRY] = _EmptyEntityRegistry()
    # Only the SECOND firmware-naming guess is actually present.
    hass5.states.async_set("button.alfred_mop_wash", "unknown")

    register_adapter_config(VAC, {
        "adapter_id": "vac3_test", "source": "code",
        "entities": {"task_status": "sensor.alfred_task"},
        # Hint deliberately False so the outcome depends purely on entity
        # presence via entity_candidates, not the model-based hint.
        "capability_hints": {"supports_mop_wash": False},
        "_entity_candidates": {
            "wash_mop_button": ["button.alfred_wash_mop", "button.alfred_mop_wash"],
        },
    })

    mgr5 = H.ManagerStub(hass=hass5)
    mgr5.ensure_vacuum_record = lambda **kw: {}

    # Unbound call against a ManagerStub standing in for `self` -- same
    # technique _proof_reachability.py uses for EufyVacuumManager.update_room_fields.
    payload5 = EufyVacuumManager.refresh_vacuum_capabilities(mgr5, vacuum_entity_id=VAC)

    proof.case(
        "a capability refresh runs for a vacuum whose wash_mop_button is ONLY "
        "present under its second firmware-naming variant",
        before=payload5.get("supports_mop_wash") is False,
        before_msg="refresh derives entity_candidates from the reduced "
                   "`entities` dict (one candidate per already-resolved "
                   "entity) -- wash_mop_button is probe-only and never makes "
                   "it into `entities` at all, so refresh probes NOTHING "
                   "for it and the capability is lost",
        after=payload5.get("supports_mop_wash") is True,
        after_msg="refresh reads the adapter's stashed _entity_candidates -- "
                  "the SAME full, multi-guess dict startup used -- so the "
                  "second naming variant is probed and found",
        detail=f"payload.supports_mop_wash={payload5.get('supports_mop_wash')}",
    )

    # -------------------------------------------------------------------
    # Case 6 (POSE-4/WD-5): a stored config carries a non-positive tuning
    # value in TWO places -- an EXISTING check (room_attribution.tuning.
    # interval_s, already correctly computed by
    # EufyAnchorWindingV1.validate_tuning) and a NEW one
    # (dispatch.phase_timing.poll_seconds). Both used to be
    # logged-and-registered-anyway.
    # -------------------------------------------------------------------
    pose4_wd5_config = {
        "adapter_id": "pose4_wd5_test",
        "source": "config",
        "room_attribution": {
            "engine": "eufy_anchor_winding_v1",
            "tuning": {"interval_s": -1},
        },
        "dispatch": {"phase_timing": {"poll_seconds": 0}},
    }
    try:
        register_adapter_config(VAC, dict(pose4_wd5_config))
        _pose4_wd5_raised = False
    except ServiceValidationError:
        _pose4_wd5_raised = True
    _pose4_wd5_after = get_adapter_config(VAC)
    _pose4_wd5_registered = (
        isinstance(_pose4_wd5_after, dict)
        and _pose4_wd5_after.get("adapter_id") == "pose4_wd5_test"
    )

    proof.case(
        "a stored config declares room_attribution.tuning.interval_s=-1 AND "
        "dispatch.phase_timing.poll_seconds=0",
        before=(not _pose4_wd5_raised) and _pose4_wd5_registered,
        before_msg="_validate_adapter already computes both issues "
                   "correctly but the caller only ever LOGGED them as "
                   "warnings -- a stored config with either a nonsensical "
                   "attribution interval or a busy-looping phase watchdog "
                   "poll registered cleanly and ran",
        after=_pose4_wd5_raised and not _pose4_wd5_registered,
        after_msg="register_adapter_config now raises for a STORED "
                  "(source='config') config when _validate_adapter's issues "
                  "list is non-empty, so both the pre-existing attribution "
                  "check and the new phase_timing check refuse registration "
                  "instead of degrading silently",
        detail=f"raised={_pose4_wd5_raised} · registered after={_pose4_wd5_after}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
