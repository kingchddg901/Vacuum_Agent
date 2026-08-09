"""Issue #48 (X10 Pro Omni): does Edge Mopping survive a read-back?

Reported: enable Edge Mopping, save, reopen the room settings -> it is off again.

The reporter's diagnostics show the value IS persisted (rooms 1/2/5 all carry
edge_mopping: true), so the loss is on the READ path. This drives the real
resolver with the exact stored room dicts and prints what the card would be
handed.

RUN IT (the suite cannot run on a Windows host -- homeassistant.runner imports
fcntl -- so use the pre-baked image, and put the repo on PYTHONPATH because this
file lives outside the pytest rootdir):

    docker run --rm -v "<repo>:/workspace" -w /workspace -e PYTHONPATH=/workspace \
      eufy-vacuum-test python .claude/notes/_probe_issue48_edge_mopping.py

REPAIRED 2026-08-08. It had stopped running: it called the resolver with no
``catalog``, which was fine when core still carried Eufy's vocabulary as the
framework default, and became UndeclaredProfileCatalogError once adapters took
ownership of the words ("core holds no catalog"). A probe cited as a commit's
evidence that no longer executes is the stale-proof class the audit charter
warns about -- the citation keeps reading as proof long after the proof stopped
being one. It now sources the catalog the way the adapter declares it, so a
future catalog move breaks it loudly here instead of silently.

Section 3 was added at the same time: the same predicate defect survived on the
DISPATCH side after the read path was fixed, and that side is worse, because a
wrong answer there is a wrong payload sent to real hardware rather than a wrong
checkbox.
"""
from custom_components.eufy_vacuum.adapters.eufy.room_profiles import (
    BUILT_IN_ROOM_PROFILES,
    DEFAULT_CUSTOM_ROOM_PROFILE,
    DEFAULT_ROOM_PROFILE_NAME,
    FLOOR_TYPE_FAN_DEFAULTS,
    FLOOR_TYPE_WATER_DEFAULTS,
    LEGACY_PROFILE_ALIASES,
)
from custom_components.eufy_vacuum.profiles.room_profiles import (
    apply_capability_gate,
    resolve_profile_catalog,
    resolve_room_profile_for_room,
)

# Exactly the block adapters/eufy/adapter.py declares. Built here rather than
# instantiating an adapter so the probe needs no hass, and so it fails loudly if
# the declared key set changes.
CATALOG = resolve_profile_catalog({
    "default_profile": DEFAULT_ROOM_PROFILE_NAME,
    "builtins": BUILT_IN_ROOM_PROFILES,
    "custom_template": DEFAULT_CUSTOM_ROOM_PROFILE,
    "legacy_aliases": LEGACY_PROFILE_ALIASES,
    "floor_type_water_defaults": FLOOR_TYPE_WATER_DEFAULTS,
    "floor_type_fan_defaults": FLOOR_TYPE_FAN_DEFAULTS,
    "normalize_defaults": DEFAULT_CUSTOM_ROOM_PROFILE,
})

# Verbatim from the diagnostics attached to issue #48.
ROOMS = [
    {"room_id": 1, "name": "Utility", "profile_name": "custom",
     "clean_mode": "Vacuum and mop", "floor_type": "laminate",
     "water_level": "Medium", "clean_intensity": "Deep",
     "edge_mopping": True, "clean_passes": 1},
    {"room_id": 2, "name": "Kitchen", "profile_name": "custom",
     "clean_mode": "Vacuum and mop", "floor_type": "tile",
     "water_level": "High", "clean_intensity": "Deep",
     "edge_mopping": True, "clean_passes": 1},
    {"room_id": 5, "name": "Hallway", "profile_name": "custom",
     "clean_mode": "Vacuum and mop", "floor_type": "hardwood",
     "water_level": "High", "clean_intensity": "Deep",
     "edge_mopping": True, "clean_passes": 1},
]

failures: list[str] = []

print("1. THE REPORTED ROOMS, as stored -> as resolved for the card")
print("-" * 70)
for room in ROOMS:
    out = resolve_room_profile_for_room(
        room_config=room, stored_profiles={}, catalog=CATALOG
    )
    kept = bool(out.get("edge_mopping"))
    if room["edge_mopping"] and not kept:
        failures.append(f"room {room['room_id']} lost edge_mopping on read")
    print(f"  room {room['room_id']} {room['name']:<9} stored={room['edge_mopping']!s:<5} "
          f"resolved={kept!s:<5} clean_mode={out.get('clean_mode')!r}"
          f"{'   <-- LOST' if room['edge_mopping'] and not kept else ''}")

# The sensitivity control. These spellings all mean the same thing to a user, and
# the bug was visible only in some of them -- run against 9ce51af^ the first two
# columns disagree, which is the whole defect in one line.
print()
print("2. READ PATH, across clean_mode spellings (sensitivity control)")
print("-" * 70)
base = dict(ROOMS[0])
for mode in ("Vacuum and mop", "vacuum_mop", "mop", "Mop", "VACUUM_MOP",
             "Vacuum", "vacuum"):
    out = resolve_room_profile_for_room(
        room_config={**base, "clean_mode": mode}, stored_profiles={}, catalog=CATALOG
    )
    keeps = bool(out.get("edge_mopping"))
    # "Vacuum"/"vacuum" SHOULD drop it -- a vacuum-only room has no edge mopping.
    should_keep = "mop" in mode.lower()
    ok = keeps == should_keep
    if not ok:
        failures.append(f"read path: {mode!r} -> edge_mopping={keeps}, expected {should_keep}")
    print(f"  clean_mode={mode!r:<18} -> edge_mopping={keeps!s:<5} "
          f"expected={should_keep!s:<5}{'' if ok else '  <-- WRONG'}")

# Section 3: the same question asked on the payload side. apply_capability_gate
# reads settings["clean_mode"] WITHOUT lowercasing, and its own docstring says it
# is handed "display/storage values" -- so comparing them against canonical
# tokens is the identical mistake one layer along, on the side that talks to the
# robot. A non-mop device handed "Vacuum and mop" must still downgrade.
print()
print("3. DISPATCH PATH (apply_capability_gate) -- non-mop device must downgrade")
print("-" * 70)
NO_MOP = {
    "supports_mop_features": False,
    "supports_water_control": False,
    "supports_edge_mopping": False,
    "supports_path_control": True,
    "supports_passes": True,
}
for mode in ("Vacuum and mop", "vacuum_mop", "mop", "Mop"):
    gated = apply_capability_gate(
        settings={"clean_mode": mode, "fan_speed": "Max", "water_level": "High",
                  "edge_mopping": True, "clean_passes": 1, "clean_intensity": "Deep"},
        capabilities=NO_MOP,
        resolved_profile_name="custom",
        catalog=CATALOG,
    )
    got = str(gated.get("clean_mode"))
    ok = got == "vacuum"
    if not ok:
        failures.append(f"dispatch: {mode!r} not downgraded on a non-mop device (got {got!r})")
    print(f"  clean_mode={mode!r:<18} -> gated={got!r:<16}"
          f"{'' if ok else '  <-- NOT DOWNGRADED'}")

# The vacuum-only invariant, same shape: a room stored with the DISPLAY label
# "Vacuum" must still have water and edge cleared.
print()
print("4. DISPATCH PATH -- vacuum-only must clear water and edge")
print("-" * 70)
FULL = {
    "supports_mop_features": True,
    "supports_water_control": True,
    "supports_edge_mopping": True,
    "supports_path_control": True,
    "supports_passes": True,
}
for mode in ("Vacuum", "vacuum"):
    gated = apply_capability_gate(
        settings={"clean_mode": mode, "fan_speed": "Max", "water_level": "High",
                  "edge_mopping": True, "clean_passes": 1, "clean_intensity": "Deep"},
        capabilities=FULL,
        resolved_profile_name="custom",
        catalog=CATALOG,
    )
    edge = bool(gated.get("edge_mopping"))
    if edge:
        failures.append(f"dispatch: {mode!r} kept edge_mopping on a vacuum-only run")
    print(f"  clean_mode={mode!r:<18} -> edge_mopping={edge!s:<5} "
          f"water_level={gated.get('water_level')!r}"
          f"{'  <-- NOT CLEARED' if edge else ''}")

print()
print("=" * 70)
if failures:
    print(f"FAIL - {len(failures)} problem(s):")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("PASS - edge_mopping survives every mop spelling on read, and the dispatch")
print("       gate downgrades and clears correctly for display-label input.")
