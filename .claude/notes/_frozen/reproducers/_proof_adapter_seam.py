"""Proof RP-033 (RF-32) — adapter-config seam hardened.

Two cases (of ten finding_ids -- setup.steps validation (SETUP-9), the
no-command envelope (DE-3), capability refresh probe-keys (VAC-3), and
tuning-value clamping (POSE-4/WD-5 halves) are NOT driven here; time-boxed,
left for a follow-up pass).

  save_adapter_config (services/adapter_config.py:57-94) checks exactly two
  keys before registering: config.get("adapter_id") and config.get(
  "dispatch", {}).get("template"). Nothing else is validated against
  ADAPTER_CONFIG_SCHEMA (confirmed: no reference to that schema anywhere in
  the handler) before _register(vacuum_entity_id, config) replaces whatever
  adapter was live -- every block the two-key config omits (entities,
  discovery, capabilities, vocabulary, ...) silently resolves through the
  registry's own Eufy-shaped fallbacks (the same fallback machinery visible
  in this session's own proof output: "adapter 'X' declares no 'mapping'
  block, so map segmentation falls back to eufy_cv_v1").
  delete_adapter_config (line 97-115) unregisters the live adapter
  (unregister_adapter_config) and never re-registers anything -- the vacuum
  is left with NO adapter at all, not even reverted to the code adapter
  that was live before any config was ever saved.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_adapter_seam.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import (   # noqa: E402
    register_adapter_config, get_adapter_config,
)
from custom_components.eufy_vacuum.const import DOMAIN, DATA_RUNTIME   # noqa: E402
from custom_components.eufy_vacuum.services.adapter_config import (   # noqa: E402
    _handle_save_adapter_config, _handle_delete_adapter_config,
)

VAC = H.VAC

_LIVE_CODE_ADAPTER = {
    "adapter_id": "eufy", "source": "code",
    "entities": {"task_status": "sensor.alfred_task", "dock_status": "sensor.alfred_dock"},
    "dispatch": {"template": "eufy_room_clean", "service_domain": "vacuum",
                 "service_name": "send_command", "command": "room_clean"},
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

    asyncio.run(_handle_save_adapter_config(hass, _Call()))
    after_save = get_adapter_config(VAC) or {}

    proof.case(
        "a two-key config (adapter_id + dispatch.template only) is saved",
        before=after_save.get("adapter_id") == "custom"
        and "entities" not in after_save,
        before_msg="the two-key config registers OVER the live 'eufy' code "
                   "adapter -- entities/discovery/capabilities are all "
                   "silently absent, so every consumer that reads them "
                   "falls through to the Eufy-shaped default regardless of "
                   "what this vacuum actually is",
        after=after_save.get("adapter_id") == "eufy",
        after_msg="ADAPTER_CONFIG_SCHEMA is applied at save time -- missing "
                  "required blocks raise ServiceValidationError, so the "
                  "live 'eufy' adapter is never shadowed by an incomplete "
                  "config",
        detail=f"registered config after save={after_save}",
    )

    # -------------------------------------------------------------------
    # Case 2: delete leaves NO adapter registered at all.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    register_adapter_config(VAC, dict(_LIVE_CODE_ADAPTER))
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2.async_save = H.async_noop()
    hass2.data.setdefault(DOMAIN, {})[DATA_RUNTIME] = mgr2
    # a stored (UI-saved) config must exist for delete to do anything --
    # save one for real first via the same handler as case 1.
    asyncio.run(_handle_save_adapter_config(hass2, _Call()))

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

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
