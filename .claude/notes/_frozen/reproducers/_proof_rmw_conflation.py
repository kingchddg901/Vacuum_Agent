"""Proof (RP-006 / RF-06): read_json returns None for BOTH 'file absent' and 'file
unreadable', and RMW callers conflate the two — an UNREADABLE store is read as EMPTY,
then the read-modify-write replaces the whole file with just the current delta.

Demonstrated on the trouble-rooms log: a 9-room store is corrupted (unreadable, but
its bytes still recoverable), one job is finalized, and the RMW at
learning/job_finalizer._update_trouble_rooms_log writes back a 1-room store. Nine
rooms of chronic-miss history are gone, and the write reported nothing.

Run: docker eufy-vacuum-test -> python .claude/notes/_proof_rmw_conflation.py
"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from custom_components.eufy_vacuum.learning.job_finalizer import LearningJobFinalizer

VAC = "vacuum.alfred"


def make_hass(config_dir: str):
    return SimpleNamespace(
        config=SimpleNamespace(config_dir=config_dir,
                               path=lambda *p: config_dir + "/" + "/".join(p)),
        data={},
    )


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="_proof_rmw_")
    fin = LearningJobFinalizer(make_hass(tmp))

    # --- a healthy 9-room chronic-miss store ---------------------------------
    rooms = {str(i): {"room_id": i, "name": f"Room {i}", "run_count": 4,
                      "miss_count": 2, "last_missed_at": "2026-07-30T00:00:00Z"}
             for i in range(1, 10)}
    fin.store.save_trouble_rooms(vacuum_entity_id=VAC,
                                 payload={"schema_version": 1,
                                          "record_type": "trouble_rooms_log",
                                          "vacuum_entity_id": VAC,
                                          "rooms": rooms})
    path = fin.store.get_trouble_rooms_path(vacuum_entity_id=VAC)
    healthy = path.read_text(encoding="utf-8")
    assert len((json.loads(healthy)).get("rooms", {})) == 9

    # --- corrupt it: unreadable to json.loads, bytes still recoverable -------
    path.write_text(healthy + "\n<<TRUNCATED-BY-POWER-LOSS>>", encoding="utf-8")

    # --- one job finalizes; the RMW runs -------------------------------------
    fin._update_trouble_rooms_log(
        vacuum_entity_id=VAC,
        completed_job={
            "outcome": {"status": "completed"},
            "resolved_rooms": [{"room_id": 27, "name": "KITCHEN"}],
            "queue": {"queue_room_ids": [27]},
        },
        active_job_state={},
        ended_at="2026-08-01T03:16:13Z",
    )

    # --- what survived? -------------------------------------------------------
    raw = path.read_text(encoding="utf-8")
    try:
        after = json.loads(raw)
        replaced = True
    except json.JSONDecodeError:
        # file untouched (still carries the corruption marker) -> recover the
        # original payload from the bytes before the marker
        after = json.loads(raw.split("\n<<TRUNCATED-BY-POWER-LOSS>>")[0])
        replaced = False

    n = len(after.get("rooms", {}))
    print(f"store file replaced by the RMW: {replaced}")
    print(f"trouble_rooms rooms after RMW: {n}")

    if replaced and n == 1:
        print("nine rooms of chronic-miss history destroyed: the unreadable store "
              "was read as EMPTY (read_json None-conflation) and the RMW rewrote "
              "the file with only the current job's room")
        return 0
    if not replaced and n == 9:
        print("update skipped: store unreadable")
        print(f"rooms after RMW: {n}")
        return 0
    print(f"UNEXPECTED SHAPE: replaced={replaced} rooms={n}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
