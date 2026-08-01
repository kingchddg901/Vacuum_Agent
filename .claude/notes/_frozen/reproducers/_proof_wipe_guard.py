"""Proof (RP-005 / RF-02): the five wipe paths — companion to _proof_setup.py.

Two demonstrations, both state-dependent (before-fragments pre-repair, after-
fragments post-repair):

  1. THE REAL SERVICE SCHEMA vs enabled_room_ids: None / [] — corpus precedent:
     cv.ensure_list(None) == [], so "no selection" silently became "delete every
     room" (ROOMS-2). Post-repair both are loud vol.Invalid errors.
  2. save_managed_rooms driven with a NON-EMPTY stored map and an EMPTY discovery
     cache — pre-repair the store is replaced wholesale ("rooms after save: 0");
     post-repair the guard refuses before any mutation.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_wipe_guard.py
"""
import sys
from types import SimpleNamespace

import voluptuous as vol

from custom_components.eufy_vacuum.services.rooms import _SAVE_MANAGED_ROOMS_SCHEMA
from custom_components.eufy_vacuum.services.setup import _SETUP_SAVE_ROOMS_SCHEMA
from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager

VAC, MAP = "vacuum.alfred", "12"


def check_schema(name, schema, payload):
    try:
        out = schema(payload)
        return f"{name}: ACCEPTED -> enabled_room_ids={out.get('enabled_room_ids')!r}"
    except vol.Invalid as err:
        return f"{name}: rejected by schema ({err})"


def main() -> int:
    rc = 0

    # --- 1. the real schemas ---------------------------------------------------
    for label, schema in (("rooms._SAVE_MANAGED_ROOMS_SCHEMA", _SAVE_MANAGED_ROOMS_SCHEMA),
                          ("setup._SETUP_SAVE_ROOMS_SCHEMA", _SETUP_SAVE_ROOMS_SCHEMA)):
        for val, tag in ((None, "None"), ([], "[]")):
            msg = check_schema(f"{label} <- {tag}", schema,
                               {"vacuum_entity_id": VAC, "map_id": MAP,
                                "enabled_room_ids": val})
            print(msg)
            if "ACCEPTED" in msg and "=[]" in msg.replace("'", ""):
                print(f"  ^ {tag} coerced to [] — 'no selection' became 'delete every room'")

    # --- 2. the save path ------------------------------------------------------
    stored = {"1": {"room_id": 1, "name": "Kitchen", "enabled": True},
              "2": {"room_id": 2, "name": "Den", "enabled": True}}
    class ManagerStub:
        """data is real; every unknown attribute is a swallow-anything no-op, so the
        pre-repair code path (which continues PAST the wipe into derived-state
        refresh / notify) runs to completion instead of crashing on the stub."""
        def __init__(self):
            self.data = {
                "maps": {VAC: {MAP: {"map_id": MAP, "metadata": {},
                                     "rooms": dict(stored), "summary": {}}}},
                "discovery": {VAC: {MAP: {"rooms": []}}},  # glitched/empty discovery
            }
            self._room_history_cache_ready = set()   # accessed as a set post-save

        def ensure_runtime(self, *_a, **_kw):
            return SimpleNamespace()                  # attribute-writable runtime

        def __getattr__(self, name):
            return lambda *a, **kw: None

    manager = ManagerStub()
    rm = RoomMapManager(manager)
    result = rm.save_managed_rooms(vacuum_entity_id=VAC, map_id=MAP)

    rooms_after = manager.data["maps"][VAC][MAP].get("rooms", {})
    print()
    print(f"save result reason: {result.get('reason')!r}  saved={result.get('saved')!r}")
    print(f"rooms after save: {len(rooms_after)}")

    if result.get("reason") == "empty_replacement_refused" and len(rooms_after) == 2:
        print("empty_replacement_refused — stored rooms untouched")
    elif len(rooms_after) == 0:
        print("the empty discovery REPLACED the stored map — both rooms and their "
              "settings, learning links and confirmations are gone")
    else:
        print(f"UNEXPECTED SHAPE: {result}")
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
