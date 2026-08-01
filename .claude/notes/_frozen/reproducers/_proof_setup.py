"""Proof: the map-scoped unique_id prefix collides across sibling vacuum entity_ids."""
from custom_components.eufy_vacuum.entity_helpers import make_room_unique_id

# HA auto-suffixes a duplicate entity_id with _2, so this is a normal two-vacuum install.
victim = [make_room_unique_id(vacuum_entity_id="vacuum.alfred_2", map_id=m, room_id=r,
                              suffix=s)
          for m in ("5", "9") for r in (1, 3) for s in ("enabled", "passes")]

# User deletes map "2" from the OTHER vacuum.
prefix = f"{'vacuum.alfred'.replace('.', '_')}_2_"        # setup/delete.py:136
swept = [u for u in victim if u.startswith(prefix)]

print(f"deleting map 2 from vacuum.alfred -> sweep prefix {prefix!r}")
print(f"entities belonging to vacuum.alfred_2 : {len(victim)}")
print(f"...matched by that prefix             : {len(swept)}")
for u in swept[:4]:
    print(f"    {u}")
print()
own = make_room_unique_id(vacuum_entity_id="vacuum.alfred", map_id="20", room_id=1, suffix="enabled")
print(f"control - map 20 of the same vacuum {own!r} matched: {own.startswith(prefix)}")
