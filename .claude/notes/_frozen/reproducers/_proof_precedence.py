"""Proof RP-024 (RF-19; Q2+Q3) — clause (1): water_level is floor-over-profile.

ONE case, out of 13 finding_ids across 5 required_behavior clauses. This
drives the packet's own named reproducer_script example verbatim: "vacuum_
mop_quick on hardwood (before: water floor-default 'Low' overrode profile
'Medium', re-labelled custom; after: 'Medium', label sticks)". The other four
clauses (Q3 granite/concrete water defaults, RES-3 path_type None-as-absent,
RES-7 dangling-profile resolved_fallback flag, CRUD-5/8 id-generator
uniqueness + save round-trip) are NOT driven here -- left for follow-up, each
independent of this one. The "re-labelled custom" visible symptom
(_match_profile_from_fields, referenced by the packet but not found in
room_profiles.py -- likely profiles/manager.py) is also not driven; this
proof targets the ROOT CAUSE clause (1) explicitly names, not its downstream
display symptom.

resolve_room_profile_for_room (profiles/room_profiles.py:372-469) resolves
every OTHER field room-value > profile-value > "" (lines 415-423, e.g.
resolved_fan_speed = room_config.get("fan_speed", resolved_profile.get(
"fan_speed", ""))) -- but water_level gets a SECOND, later pass (lines
432-436):
    if floor_type.startswith("carpet"):
        ...
    elif "water_level" not in room_config:
        resolved_water_level = water_defaults.get(floor_type, "")
This checks only whether the ROOM's own dict has an explicit water_level key
-- never whether the SELECTED PROFILE supplied one. A room relying on its
profile (the normal case -- no per-room override) always fails this check,
so the floor's water default UNCONDITIONALLY overwrites whatever the profile
ladder (line 423) just resolved, even when the profile has a real, explicit
water_level. Every sibling field's ladder is untouched by floor_type at all
(fan_speed only gets floor-clamped on carpet, line 433) -- water_level is
the one field where "floor default" outranks "explicit profile value" on
ordinary hard floors, exactly backwards from Q2's precedence contract.

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_precedence.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.profiles.room_profiles import (   # noqa: E402
    resolve_room_profile_for_room,
)


def main() -> int:
    proof = H.Proof("RP-024", "Q2 clause 1: water_level resolves floor-default-over-profile")

    # A room on hardwood (floor water default "Low"), selecting the built-in
    # vacuum_mop_quick profile (its OWN water_level is "Medium"), with NO
    # per-room water_level override -- the ordinary case; the room trusts its
    # selected profile.
    room_config = {
        "profile_name": "vacuum_mop_quick",
        "floor_type": "hardwood",
    }

    resolved = resolve_room_profile_for_room(room_config=room_config, stored_profiles={})

    proof.case(
        "a room on hardwood selecting the built-in vacuum_mop_quick profile "
        "(water_level='Medium'), with no per-room water override",
        before=(resolved.get("water_level") == "Low"),
        before_msg="the floor's water default ('Low', hardwood) silently "
                   "overrides the profile's own explicit water_level "
                   "('Medium') -- the just-selected mop profile's water "
                   "setting never reaches the resolved room at all",
        after=(resolved.get("water_level") == "Medium"),
        after_msg="floor water defaults apply only when the room AND the "
                  "resolved profile both omit water_level (matching every "
                  "sibling field's own room > profile > default ladder); "
                  "floor safety clamps (carpet) still apply afterward as an "
                  "explicit stage, unaffected by this",
        detail=f"resolved={resolved}",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
