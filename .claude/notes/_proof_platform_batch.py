"""Proof RP-035 (RF-34) — sensors keyed off the wrong collection; timezone frozen at import.

Two of the three recipes in the packet's reproducer_script. SN-4 (rename propagation) is
NOT driven here: its mechanism is the entity registry's remove/re-add under a stable
unique_id, which needs real registry plumbing rather than a data-shape assertion, and
REVIEW-07 T2-D5 amended the required behaviour late. Left for the execution session, which
has the registry available. Same partial-coverage convention the other proofs in this
corpus use — declare the boundary rather than fake the mechanism.

  1. SN-1 — A NEW VACUUM HAS NO SENSORS UNTIL A RESTART. sensor/__init__.py:97-98 builds
     the per-vacuum sensor set by iterating `manager.data["maps"]`, not the managed
     vacuums. A vacuum the user has added but whose map has not been imported yet is
     absent from that dict, so it gets zero sensors — and async_setup_entry runs once per
     config entry, so importing the map afterwards changes nothing until Home Assistant
     restarts. `maps` is a record of what has been imported; it was never the roster of
     what the user manages.

  2. INF-2 — THE LOCAL TIMEZONE IS FROZEN AT IMPORT. timestamp_utils.py:8 evaluates
     `_LOCAL_TZ = datetime.now().astimezone().tzinfo` once, at module import. On CPython
     that yields a FIXED-offset timezone captured from whatever moment the module loaded,
     not a DST-aware zone. Every naive timestamp is then stamped with that one offset
     regardless of its own date, so an install that started in winter reads summer
     timestamps an hour off (and vice versa) until it restarts.

     The proof pins TZ to a DST-observing zone and reloads the module, so it is
     deterministic wherever it runs rather than depending on the container's clock. That
     is inert scaffolding — setting the environment, not emulating the behaviour under
     test. The correct answer comes from zoneinfo, which the fix would consult per call
     (the packet specifies HA's dt_util, same property).

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_platform_batch.py
"""

from __future__ import annotations

import datetime as _dt
import importlib
import inspect
import os
import re
import sys
import time
import zoneinfo

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

# Pin a DST-observing zone BEFORE timestamp_utils is imported, so _LOCAL_TZ is captured
# under known conditions. reload() covers the case where something already imported it.
ZONE = "America/New_York"
os.environ["TZ"] = ZONE
if hasattr(time, "tzset"):
    time.tzset()

from custom_components.eufy_vacuum import timestamp_utils   # noqa: E402

timestamp_utils = importlib.reload(timestamp_utils)

# the package's __init__.py IS the module — importing `__init__` by name picks up the
# method-wrapper on the package object instead.
from custom_components.eufy_vacuum import sensor as sensor_init   # noqa: E402


def case_new_vacuum_gets_no_sensors(proof: H.Proof) -> None:
    mgr = H.ManagerStub()
    # The user has set up two vacuums. Only one has had its map imported.
    mgr.data["managed_vacuums"] = {
        "vacuum.alfred": {"name": "alfred"},
        "vacuum.ivy": {"name": "ivy"},
    }
    mgr.data["maps"] = {"vacuum.alfred": {"12": {}}}

    managed = set(mgr.data["managed_vacuums"])
    iterated = set(mgr.data.get("maps", {}).keys())
    without_sensors = sorted(managed - iterated)

    # Read the shipped source so a refactor cannot make this pass quietly.
    src = inspect.getsource(sensor_init.async_setup_entry)
    keys_off_maps = bool(re.search(r'maps\s*=\s*manager\.data\.get\(\s*["\']maps["\']', src))

    proof.case(
        "two managed vacuums, one of which has not had its map imported yet",
        before=keys_off_maps and without_sensors == ["vacuum.ivy"],
        before_msg="no per-vacuum sensors until restart — the loop iterates the MAPS "
                   "dict, which records what has been imported, not the roster of what "
                   "the user manages; setup runs once, so importing the map later "
                   "changes nothing until HA restarts",
        after=not keys_off_maps and not without_sensors,
        after_msg="the loop iterates managed vacuums, and a creation hook on map "
                  "import / vacuum add fills in the rest without a restart",
        detail=f"managed={sorted(managed)} · iterated by the sensor loop="
               f"{sorted(iterated)} · gets NO sensors={without_sensors} · "
               f"loop still keys off data['maps']={keys_off_maps}",
    )


def case_timezone_frozen_at_import(proof: H.Proof) -> None:
    zone = zoneinfo.ZoneInfo(ZONE)
    winter_naive, summer_naive = "2026-01-15T12:00:00", "2026-07-15T12:00:00"

    def applied_offset(naive: str) -> float:
        """The UTC offset parse_timestamp assumed, in hours, signed like utcoffset()."""
        parsed = timestamp_utils.parse_timestamp(naive, assume_local_naive=True)
        wall = _dt.datetime.fromisoformat(naive)
        # wall-clock reading minus the UTC result == the offset that was assumed.
        return (wall.replace(tzinfo=_dt.timezone.utc) - parsed).total_seconds() / 3600

    def correct_offset(naive: str) -> float:
        """Same sign convention, so before/after compare like with like. Getting these
        two out of step is how a reproducer ends up unable to flip."""
        return _dt.datetime.fromisoformat(naive).replace(
            tzinfo=zone).utcoffset().total_seconds() / 3600

    got_winter, got_summer = applied_offset(winter_naive), applied_offset(summer_naive)
    want_winter, want_summer = correct_offset(winter_naive), correct_offset(summer_naive)

    proof.case(
        f"a January and a July naive timestamp parsed in {ZONE} (DST differs by 1 h)",
        before=got_winter == got_summer,
        before_msg="one offset stamped on both dates — _LOCAL_TZ is a fixed offset "
                   "captured at module import, so whichever season the install started "
                   "in decides how every timestamp of every other season is read",
        after=got_winter != got_summer
        and abs(got_winter - want_winter) < 0.01
        and abs(got_summer - want_summer) < 0.01,
        after_msg="the offset is resolved per timestamp from its own date",
        detail=f"applied: Jan {got_winter:+.0f}h, Jul {got_summer:+.0f}h · correct for "
               f"{ZONE}: Jan {want_winter:+.0f}h, Jul {want_summer:+.0f}h · "
               f"_LOCAL_TZ={timestamp_utils._LOCAL_TZ!r}",
    )


def main() -> None:
    proof = H.Proof("RP-035", "sensors keyed off the wrong collection; timezone frozen at import")
    case_new_vacuum_gets_no_sensors(proof)
    case_timezone_frozen_at_import(proof)
    proof.finish()


H.run(main)
