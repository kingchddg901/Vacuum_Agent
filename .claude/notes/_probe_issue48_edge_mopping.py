"""Issue #48 (ptruman, X10 Pro Omni): does Edge Mopping survive a read-back?

Reported: enable Edge Mopping, save, reopen the room settings -> it is off again.

His diagnostics show the value IS persisted (rooms 1/2/5 all carry
edge_mopping: true), so the loss is on the READ path. This drives the resolver
with his exact stored room dicts and prints what the card would be handed.
"""
from custom_components.eufy_vacuum.profiles.room_profiles import (
    resolve_room_profile_for_room,
)

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

print("HIS ROOMS, as stored -> as resolved for the card")
print("-" * 64)
for room in ROOMS:
    out = resolve_room_profile_for_room(room_config=room, stored_profiles={})
    print(f"  room {room['room_id']} {room['name']:<9} stored={room['edge_mopping']!s:<5} "
          f"resolved={out.get('edge_mopping')!s:<5} clean_mode={out.get('clean_mode')!r}")

print()
print("THE PREDICATE, across clean_mode spellings")
print("-" * 64)
base = dict(ROOMS[0])
for mode in ("Vacuum and mop", "vacuum_mop", "mop", "Mop", "VACUUM_MOP",
             "Vacuum", "vacuum"):
    out = resolve_room_profile_for_room(
        room_config={**base, "clean_mode": mode}, stored_profiles={}
    )
    keeps = out.get("edge_mopping")
    print(f"  clean_mode={mode!r:<18} -> edge_mopping={keeps!s:<5}"
          f"{'  <-- LOST' if base['edge_mopping'] and not keeps else ''}")

print()
print("SIBLING PREDICATE (_protected_room_config, the SAVE path) for contrast")
print("-" * 64)
for mode in ("Vacuum and mop", "vacuum_mop", "mop", "Vacuum"):
    lowered = mode.lower()
    substring_form = ("mop" in lowered) or ("wash" in lowered)
    exact_form = lowered in {"mop", "vacuum_mop"}
    print(f"  clean_mode={mode!r:<18} substring={substring_form!s:<5} "
          f"exact_set={exact_form!s:<5}"
          f"{'  <-- DISAGREE' if substring_form != exact_form else ''}")
