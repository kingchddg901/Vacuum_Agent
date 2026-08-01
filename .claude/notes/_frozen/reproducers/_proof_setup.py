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


# --- RP-009 extension: the closed set vs the prefix scan ---------------------
# Post-repair, setup/delete sweeps by unique_ids_for_map (forward-reconstructed
# from the deleted map's stored rooms) and sweeps classify by ownership
# attributes. The victim set above must have ZERO overlap with the closed set.
try:
    from custom_components.eufy_vacuum.entity_helpers import (
        entity_belongs_to, unique_ids_for_map,
    )
except ImportError:
    print()
    print("closed-set helpers ABSENT (pre-RP-009 source): the prefix sweep above")
    print(f"removed vacuum_alfred_2_-prefixed ids: {len(swept)} sibling entities")
else:
    closed = unique_ids_for_map(vacuum_entity_id="vacuum.alfred", map_id="2",
                                room_ids=[1, 3])
    overlap = [u for u in victim if u in closed]
    print()
    print(f"closed set for (vacuum.alfred, map 2, rooms 1+3): {len(closed)} ids")
    print(f"sibling (vacuum.alfred_2) ids inside the closed set: {len(overlap)}")

    class _FakeRoomEnt:
        def __init__(self, vac, map_id):
            self.vacuum_entity_id, self.map_id = vac, map_id

    class _FakeMaintenanceNumber:            # EP-2: plain entity, no ownership attrs
        pass

    sib = _FakeRoomEnt("vacuum.alfred_2", "5")
    own = _FakeRoomEnt("vacuum.alfred", "2")
    mnt = _FakeMaintenanceNumber()
    assert not entity_belongs_to(sib, vacuum_entity_id="vacuum.alfred", map_id="2")
    assert entity_belongs_to(own, vacuum_entity_id="vacuum.alfred", map_id="2")
    assert not entity_belongs_to(mnt, vacuum_entity_id="vacuum.alfred", map_id="2")
    if not overlap:
        print("sibling removals == 0 — ownership is attribute-checked; the "
              "maintenance number (no ownership attrs) can never be swept (EP-2)")
