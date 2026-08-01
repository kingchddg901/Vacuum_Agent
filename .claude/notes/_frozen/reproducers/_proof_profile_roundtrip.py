"""Proof RP-021b (RF-35 part 2) — run-profile round trip.

Three cases (of five finding_ids -- RP-6's _build_steps_phases overlay and
RUNPROF-4's schema validation are not driven here, time-boxed; left for a
follow-up pass).

  RP-2 -- overwrite_run_profile (profiles/manager.py:1027-1100) sets
    "steps": [] UNCONDITIONALLY (line 1086), with its own comment stating
    the current design: "the {**existing} spread would otherwise carry the
    STALE steps list forward". required_behavior wants the contract
    reversed: re-snapshot via get_queue_steps (mirroring save_run_profile's
    own line 982-986), not blank.
  RP-4 -- apply_run_profile never writes any applied-profile stamp (grepped
    "applied_run_profile" across planning/run_plan.py: zero matches).
    _build_effective_start_plan's step source (run_plan.py:1330-1351) checks
    only an explicit start_run_profile stash, then falls back to the LIVE
    QUEUE's OWN breaks -- there is no third path reading a stamp, so a plain
    Start after apply either runs flat or picks up whatever UNRELATED
    queue breaks the map happened to have configured before. This case
    drives apply_run_profile itself and confirms no stamp is written; the
    downstream consequence in _build_effective_start_plan is confirmed by
    direct source reading (quoted above), not driven end-to-end -- that
    function pulls in ~6 further manager collaborators (access-graph
    validation, rule evaluation) out of scope for this proof's time budget.
  RP-1 (settings half) -- apply_run_profile sources per-room settings from
    run_profile_steps(profile)'s room_group entries (profiles/manager.py:
    1211-1214), NOT from profile["rooms"]. For a STEPPED profile those
    entries come verbatim from get_queue_steps, whose room_group rooms are
    bare {"room_id": rid} (core/manager.py:1720) -- no settings fields at
    all. Every room_snapshot.get(field, current_room.get(field, ...)) call
    therefore falls through to CURRENT room state, silently discarding the
    profile's saved settings. (Confirmed this is stepped-profile-ONLY: a
    legacy/flat profile's run_profile_steps back-fills from profile["rooms"]
    directly (profiles/manager.py:819-820), which DOES carry full settings,
    so apply already works correctly there -- the defect is specific to the
    steps path.)

Run: docker eufy-vacuum-test (PYTHONPATH=/workspace) ->
     python .claude/notes/_proof_profile_roundtrip.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".claude/notes")
import _proof_harness as H   # noqa: E402

from custom_components.eufy_vacuum.profiles.manager import ProfileManager   # noqa: E402
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket   # noqa: E402

VAC = H.VAC
MAP = "1"


def _room(room_id, **extra):
    return {
        "room_id": room_id, "name": f"Room {room_id}", "enabled": True, "order": room_id,
        "profile_name": "vacuum_quick", "clean_mode": "vacuum", "fan_speed": "Max",
        "water_level": "Off", "clean_intensity": "Quick", "clean_passes": 1,
        "edge_mopping": False, **extra,
    }


def main() -> int:
    proof = H.Proof("RP-021b", "run-profile round trip")

    # -------------------------------------------------------------------
    # Case 1 (RP-2): overwrite unconditionally wipes steps to [].
    # -------------------------------------------------------------------
    hass = H.make_hass()
    mgr = H.ManagerStub(hass=hass)
    mgr.get_queue_steps = lambda **kw: {
        "has_breaks": True,
        "steps": [{"type": "room_group", "rooms": [{"room_id": 9}]},
                  {"type": "charge_wait", "target_battery_percent": 80}],
    }
    mgr._notify_run_profiles_updated = lambda **kw: None
    bucket = ensure_map_bucket(data=mgr.data, vacuum_entity_id=VAC, map_id=MAP)
    bucket["rooms"] = {"9": _room(9)}
    profiles = ProfileManager(manager=mgr)
    library = profiles._get_saved_run_profile_store(vacuum_entity_id=VAC, map_id=MAP)
    library["rp_1"] = {
        "id": "rp_1", "name": "Weeknight", "rooms": [_room(9)],
        "steps": [{"type": "room_group", "rooms": [{"room_id": 9}]},
                  {"type": "charge_wait", "target_battery_percent": 60}],
    }

    profiles.overwrite_run_profile(vacuum_entity_id=VAC, map_id=MAP, profile_id="rp_1")
    # the STORED value, not the enriched result["profile"] -- _enrich_saved_
    # run_profile back-fills a single room_group from profile["rooms"] when
    # steps is empty (run_profile_steps' legacy fallback), which would mask
    # exactly the data loss this case exists to catch.
    steps_after = library["rp_1"]["steps"]

    proof.case(
        "overwrite a stepped profile while the current queue is ALSO stepped",
        before=steps_after == [],
        before_msg="steps is unconditionally wiped to [] -- the STORED "
                   "profile loses its charge_wait boundary entirely (the "
                   "enriched read-back papers over this with a back-filled "
                   "single room_group, which is exactly why this checks the "
                   "stored value, not the enriched one)",
        after=steps_after != [] and any(s.get("type") == "charge_wait" for s in steps_after),
        after_msg="overwrite re-snapshots steps via get_queue_steps (mirroring "
                  "save's own contract) -- the charge_wait boundary survives "
                  "in STORAGE, not just in a derived read-back",
        detail=f"stored steps after overwrite={steps_after}",
    )

    # -------------------------------------------------------------------
    # Case 2 (RP-4): apply never stamps applied_run_profile.
    # -------------------------------------------------------------------
    hass2 = H.make_hass()
    mgr2 = H.ManagerStub(hass=hass2)
    mgr2._refresh_room_derived_state = lambda **kw: None
    mgr2._notify_rooms_updated = lambda **kw: None
    bucket2 = ensure_map_bucket(data=mgr2.data, vacuum_entity_id=VAC, map_id=MAP)
    bucket2["rooms"] = {"9": _room(9, enabled=False)}
    profiles2 = ProfileManager(manager=mgr2)
    library2 = profiles2._get_saved_run_profile_store(vacuum_entity_id=VAC, map_id=MAP)
    library2["rp_1"] = {
        "id": "rp_1", "name": "Weeknight",
        "rooms": [_room(9)],
        "steps": [{"type": "room_group", "rooms": [{"room_id": 9}]},
                  {"type": "charge_wait", "target_battery_percent": 80}],
    }

    profiles2.apply_run_profile(vacuum_entity_id=VAC, map_id=MAP, profile_id="rp_1")
    stamp = bucket2.get("applied_run_profile")

    proof.case(
        "apply a STEPPED profile, then check for a stamp a plain Start could read",
        before=stamp is None,
        before_msg="no applied_run_profile stamp is written -- verified at "
                   "source, _build_effective_start_plan has no code path "
                   "that could read one even if it existed: it checks only "
                   "an explicit start_run_profile stash, else falls back to "
                   "the map's OWN (possibly unrelated) queue breaks",
        after=isinstance(stamp, dict) and stamp.get("id") == "rp_1" and stamp.get("stepped") is True,
        after_msg="apply stamps {id, stepped, applied_at} -- "
                  "_build_effective_start_plan can now prefer the applied "
                  "profile's authored steps over unrelated leftover breaks",
        detail=f"map_bucket['applied_run_profile'] after apply={stamp!r}",
    )

    # -------------------------------------------------------------------
    # Case 3 (RP-1 settings half): apply discards saved settings for a
    # STEPPED profile (bare id-only step room entries).
    # -------------------------------------------------------------------
    hass3 = H.make_hass()
    mgr3 = H.ManagerStub(hass=hass3)
    mgr3._refresh_room_derived_state = lambda **kw: None
    mgr3._notify_rooms_updated = lambda **kw: None
    bucket3 = ensure_map_bucket(data=mgr3.data, vacuum_entity_id=VAC, map_id=MAP)
    # the room's CURRENT setting -- unrelated to what the profile saved.
    bucket3["rooms"] = {"9": _room(9, enabled=False, fan_speed="Max")}
    profiles3 = ProfileManager(manager=mgr3)
    library3 = profiles3._get_saved_run_profile_store(vacuum_entity_id=VAC, map_id=MAP)
    library3["rp_1"] = {
        "id": "rp_1", "name": "Quiet Night",
        # the profile's SAVED per-room snapshot -- fan_speed="Quiet".
        "rooms": [_room(9, fan_speed="Quiet")],
        # a stepped profile: run_profile_steps returns THIS list verbatim,
        # whose room_group entries are bare id-only dicts (matching
        # get_queue_steps' real shape) -- not profile["rooms"].
        "steps": [{"type": "room_group", "rooms": [{"room_id": 9}]}],
    }

    result3 = profiles3.apply_run_profile(vacuum_entity_id=VAC, map_id=MAP, profile_id="rp_1")
    fan_speed_after = bucket3["rooms"]["9"]["fan_speed"]

    proof.case(
        "apply a stepped profile whose saved fan_speed differs from the room's CURRENT one",
        before=fan_speed_after == "Max" and 9 in result3["applied_room_ids"],
        before_msg="the room WAS enabled by apply (id matched), but its "
                   "fan_speed stayed 'Max' (current) instead of 'Quiet' "
                   "(the profile's saved value) -- the step's bare "
                   "{room_id: 9} entry has no fan_speed key to read",
        after=fan_speed_after == "Quiet",
        after_msg="apply sources per-room settings from profile['rooms'] "
                  "(keyed by room_id), independent of the steps' own "
                  "id-only room entries -- the saved fan_speed is restored",
        detail=f"fan_speed after apply={fan_speed_after!r} (profile saved "
               f"'Quiet', room was 'Max')",
    )

    return proof.finish()


if __name__ == "__main__":
    H.run(main)
