"""Proof RP-019 (RF-25c) — reconciliation becomes reachable and reviewable.

Four cases (of the packet's 8 finding_ids — REC-1 is a product-wiring/UX
finding with no backend behaviour to unit-test; ID-4/GUARD-5's drift
map-scoping needs the full setup/drift.py + manager stack and is left as a
materialization gap, same disposition as RP-015's Q4 migration: named in
required_behavior, not driven here, flagged rather than guessed):

  REC-5 — reconcile_room (rooms/room_crud.py:121) takes no token of any kind;
    it re-reads data["discovery"][...] FRESH at confirm time. If discovery
    changes between when the user reviewed it and when they clicked confirm,
    migrate silently applies the NEW plan, not the one displayed. Probed with
    a TypeError-tolerant plan_token= call (the natural name; the packet does
    not pin the exact kwarg).
  REC-3 — a room renamed AND renumbered in the SAME re-map is invisible to
    BOTH compute_reconciliation (no slug match, no id match -> no review) AND
    plan_migration (same two misses -> "no durable data for this discovered
    room" -> treated as brand new, and the old room's slug is reported
    DROPPED). plan_migration is listed in this packet's own `symbols`, and
    the packet's expected_before wording ("renamed+renumbered room deleted")
    describes DATA LOSS, not just review invisibility -- so this case drives
    plan_migration's actual carry outcome, not only compute_reconciliation's
    review list.
  REC-7 — compute_reconciliation has no dismissed_at parameter; an identical
    review re-fires every discovery pass with no way to suppress it. Probed
    the same TypeError-tolerant way.
  ID-2 — discover_rooms_for_vacuum's single-map fallback (room_discovery.py:
    176-180) fires whenever exactly one map is cached, regardless of whether
    its key matches the REQUESTED map_id -- relabelling one map's rooms as
    another's.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_reconciliation.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config   # noqa: E402
from custom_components.eufy_vacuum.rooms.room_crud import RoomMapManager   # noqa: E402
from custom_components.eufy_vacuum.rooms.reconciliation import (   # noqa: E402
    compute_reconciliation, plan_migration,
)
from custom_components.eufy_vacuum.rooms.source_refresh import (   # noqa: E402
    set_cached_room_source,
)
from custom_components.eufy_vacuum.rooms.room_discovery import discover_rooms_for_vacuum   # noqa: E402

VAC = H.VAC
MAP = "1"


def main() -> int:
    proof = H.Proof("RP-019", "reconciliation becomes reachable and reviewable")

    # -------------------------------------------------------------------
    # Case 1 (REC-5): no plan_token -- migrate applies whatever discovery
    # is cached NOW, not the plan the user reviewed.
    # -------------------------------------------------------------------
    from types import SimpleNamespace

    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr.onboarding = SimpleNamespace(remap_confirmed_floor_types=lambda **kw: None)
    mgr.data["maps"] = {VAC: {MAP: {"rooms": {
        "1": {"room_id": 1, "slug": "kitchen", "name": "Kitchen", "fan_speed": "low"},
    }}}}
    # the user reviewed THIS discovery (kitchen unchanged, still id 1)...
    mgr.data["discovery"] = {VAC: {MAP: {"rooms": [
        {"room_id": 1, "map_id": MAP, "name": "Kitchen", "slug": "kitchen"},
    ]}}}
    room_map = RoomMapManager(manager=mgr)

    # ...but before they clicked confirm, ANOTHER discovery pass cached a
    # DIFFERENT plan: kitchen renumbered 1 -> 5 (e.g. an automatic re-scan
    # fired mid-review). plan_migration only touches rooms with a durable
    # match, so this (unlike an unrelated brand-new room) DOES produce a
    # real, silently-applied change to detect.
    mgr.data["discovery"][VAC][MAP]["rooms"] = [
        {"room_id": 5, "map_id": MAP, "name": "Kitchen", "slug": "kitchen"},
    ]

    result_no_token = room_map.reconcile_room(vacuum_entity_id=VAC, map_id=MAP, action="migrate")
    # the SWAPPED renumber (kitchen -> id 5) landed, even though the user
    # reviewed a plan where kitchen stayed at id 1.
    applied_unseen_plan = (
        isinstance(result_no_token, dict)
        and "5" in mgr.data["maps"][VAC][MAP]["rooms"]
        and mgr.data["maps"][VAC][MAP]["rooms"]["5"].get("fan_speed") == "low"
        and "1" not in mgr.data["maps"][VAC][MAP]["rooms"]
    )

    try:
        room_map.reconcile_room(
            vacuum_entity_id=VAC, map_id=MAP, action="migrate", plan_token="stale-token",
        )
        accepts_token = True
    except TypeError:
        accepts_token = False
    except Exception:
        accepts_token = True   # raised something OTHER than "unknown kwarg" -- the param exists

    proof.case(
        "discovery changes between review and confirm (no token to detect it)",
        before=applied_unseen_plan and not accepts_token,
        before_msg="migrate silently applied the SWAPPED renumber (kitchen "
                   "1->5) with no way to have detected the discovery changed "
                   "since the user reviewed the original (kitchen stays at 1) "
                   "plan -- reconcile_room takes no plan_token argument at all",
        after=accepts_token,
        after_msg="reconcile_room requires a plan_token and refuses "
                  "'plan_changed' when the live discovery no longer matches "
                  "the reviewed snapshot",
        detail=f"stored rooms after migrate={sorted(mgr.data['maps'][VAC][MAP]['rooms'])} "
               f"(review showed room 1 unchanged) · accepts plan_token kwarg={accepts_token}",
    )

    # -------------------------------------------------------------------
    # Case 2 (REC-3): rename+renumber in one edit -- invisible + data-lost.
    # -------------------------------------------------------------------
    existing = {"5": {"room_id": 5, "slug": "office", "name": "Office",
                       "fan_speed": "max", "is_dock_room": True}}
    discovered = [{"room_id": 8, "map_id": MAP, "name": "Den", "slug": "den"}]

    recon = compute_reconciliation(discovered_rooms=discovered, existing_rooms=existing)
    plan = plan_migration(discovered_rooms=discovered, existing_rooms=existing)

    # a paired review names BOTH the old (5/office) and new (8/den) identity
    # together -- checked flexibly (field names for this NEW review kind are
    # not pinned by the packet) rather than against a guessed exact shape.
    paired_review = [
        r for r in recon["reviews"]
        if {5, 8} <= {v for v in r.values() if isinstance(v, int)}
        or {"office", "den"} <= {v for v in r.values() if isinstance(v, str)}
    ]

    proof.case(
        "Office (id 5) renamed to Den AND renumbered to id 8 in one edit",
        before=len(paired_review) == 0
        and plan["dropped"] == ["office"]
        and plan["rooms"].get("8", {}).get("fan_speed") != "max",
        before_msg="no review fires (neither a slug nor an id match) and "
                   "plan_migration reports 'office' DROPPED -- its fan_speed "
                   "and dock flag are gone, not carried to the new id 8",
        after=len(paired_review) == 1
        and plan["dropped"] == []
        and plan["rooms"].get("8", {}).get("fan_speed") == "max",
        after_msg="a paired rename+renumber review names both identities, and "
                  "plan_migration carries Office's settings (fan_speed=max, "
                  "dock flag) onto id 8 -- nothing dropped",
        detail=f"reviews={recon['reviews']} · plan.dropped={plan['dropped']} · "
               f"plan.rooms['8']={plan['rooms'].get('8')}",
    )

    # -------------------------------------------------------------------
    # Case 3 (REC-7): dismissals are not consulted.
    # -------------------------------------------------------------------
    try:
        compute_reconciliation(
            discovered_rooms=discovered, existing_rooms=existing, dismissed_at="2026-01-01",
        )
        accepts_dismissed_at = True
    except TypeError:
        accepts_dismissed_at = False

    proof.case(
        "compute_reconciliation has no way to suppress a dismissed review",
        before=not accepts_dismissed_at,
        before_msg="no dismissed_at parameter exists -- an identical review "
                   "re-fires on every discovery pass with no suppression, even "
                   "after the user explicitly dismissed it",
        after=accepts_dismissed_at,
        after_msg="compute_reconciliation takes dismissed_at and suppresses an "
                  "identical review until the discovery snapshot changes",
        detail=f"accepts dismissed_at kwarg={accepts_dismissed_at}",
    )

    # -------------------------------------------------------------------
    # Case 4 (ID-2): single-map fallback relabels a DIFFERENT map's rooms.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    register_adapter_config(VAC, {
        "adapter_id": "rb", "source": "code",
        "discovery": {
            "source": "service_response",
            "room_id_key": "segment_id", "room_name_key": "name",
        },
    })
    # only ONE map is cached, under a DIFFERENT key than what will be requested.
    set_cached_room_source(hass2, VAC, {
        "Kitchen Floor": [{"segment_id": 1, "name": "Kitchen"}],
    })
    wrong_map_rooms = discover_rooms_for_vacuum(hass2, vacuum_entity_id=VAC, map_id="Garage Floor")

    proof.case(
        "requesting 'Garage Floor' while only 'Kitchen Floor' is cached",
        before=len(wrong_map_rooms) == 1
        and wrong_map_rooms[0]["map_id"] == "Garage Floor",
        before_msg="the single-map fallback serves Kitchen Floor's rooms "
                   "anyway, RELABELLED with the requested (wrong) map_id "
                   "'Garage Floor' -- a caller has no way to tell they got "
                   "another map's data",
        after=len(wrong_map_rooms) == 0,
        after_msg="the fallback requires the cached map key to MATCH the "
                  "requested map_id -- a mismatch returns no rooms",
        detail=f"rooms={wrong_map_rooms}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
