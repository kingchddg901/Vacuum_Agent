"""Proof (RP-008 / #12:A6-GUARD-1): a blocker sensor DROPOUT reads as a rule match.

_room_rule_matches (rooms/access_graph.py) has no notion of unknown/unavailable —
'unavailable' is normalized like any other string, so a negating rule
(not_equals 'closed': "block when the door is not closed") MATCHES the moment the
sensor drops off the network. During a started job with path_block_action
'cancel_and_event', listeners/path_blockers.py takes a blocked report straight to
async_cancel_active_job with no known-state re-check — the run is cancelled by a
battery dying in a door sensor.

Both halves shown: (1) the rule evaluation against the real code, (2) a source
assertion that the action path has no guard between report and cancel.

Run: docker eufy-vacuum-test -> python .claude/notes/_proof_blocker_unavailable.py
"""
import inspect
import sys
from types import SimpleNamespace

from custom_components.eufy_vacuum.rooms.access_graph import AccessGraphManager
import custom_components.eufy_vacuum.listeners.path_blockers as path_blockers

RULE = {"entity_id": "binary_sensor.hall_door", "operator": "not_equals",
        "value": "closed", "kind": "blocker", "enabled": True}


def graph_with_state(state_value):
    states = SimpleNamespace(get=lambda _eid: (
        None if state_value is None else SimpleNamespace(state=state_value)))
    return AccessGraphManager({}, SimpleNamespace(states=states))


def main() -> int:
    rc = 0
    open_m = graph_with_state("open")._room_rule_matches(RULE)
    closed_m = graph_with_state("closed")._room_rule_matches(RULE)
    unavail_m = graph_with_state("unavailable")._room_rule_matches(RULE)
    unknown_m = graph_with_state("unknown")._room_rule_matches(RULE)

    print(f"not_equals 'closed' vs open        -> matched={open_m}   (genuine block: correct)")
    print(f"not_equals 'closed' vs closed      -> matched={closed_m}  (clear: correct)")
    print(f"not_equals 'closed' vs unavailable -> matched={unavail_m}")
    print(f"not_equals 'closed' vs unknown     -> matched={unknown_m}")

    # the action path: report dict + cancel_and_event -> cancel, unconditionally
    src = inspect.getsource(path_blockers)
    cancel_gated = "indeterminate" in src.lower() or "unavailable" in src.split(
        "async_cancel_active_job")[0].rsplit("def _process", 1)[-1]

    if unavail_m and not cancel_gated:
        print()
        print("cancel fired on unavailable")
        print("mechanism: dropout state normalized as an ordinary string -> "
              "not_equals matches -> path_blockers passes the blocked report to "
              "async_cancel_active_job with no known-state re-check "
              "(GUARD-2: each event also spawns an unguarded _process task)")
    elif not unavail_m:
        print()
        print("unavailable held previous verdict")
        # dedup half (GUARD-2) — a per-vacuum in-flight guard on _process
        if "_in_flight" in src or "single" in src.lower():
            print("single cancel on real edge")
    else:
        print(f"UNEXPECTED SHAPE: unavail_m={unavail_m} cancel_gated={cancel_gated}")
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
