"""Find the real source of bounds pollution: are the whole-map per-room entries
the SAME job credited to MANY rooms (multi-room jobs crediting their full
house-spanning trail to each constituent room)?"""
import json
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}

rooms = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]

job_rooms = defaultdict(list)   # job_id -> [(room_id, span_y, excluded)]
room_polluted = defaultdict(int)
for rid, rb in rooms.items():
    for h in rb.get("job_bounds_history", []):
        jid = h.get("job_id", "?")
        yspan = h["max_y"] - h["min_y"]
        xspan = h["max_x"] - h["min_x"]
        job_rooms[jid].append((int(rid), yspan, xspan, h.get("excluded", False)))
        if yspan > 6000:   # ~whole-map vertically (map y-extent ~8700)
            room_polluted[int(rid)] += 1

print("=== jobs credited to MORE THAN ONE room (multi-room jobs) ===")
print(f"{'job_id':<22}{'#rooms':>7}  rooms (y-span of the shared trail)")
multi = {j: e for j, e in job_rooms.items() if len(e) > 1}
for jid, entries in sorted(multi.items(), key=lambda kv: -len(kv[1])):
    rs = ", ".join(NAMES.get(r, str(r)) for r, *_ in entries)
    yspan = entries[0][1]
    print(f"{jid:<22}{len(entries):>7}  y~{yspan:.0f}  [{rs}]")

print("\n=== single-room job entries (credited to exactly one room) ===")
singles = {j: e for j, e in job_rooms.items() if len(e) == 1}
for jid, entries in sorted(singles.items()):
    r, ys, xs, exc = entries[0]
    print(f"  {jid:<22} {NAMES.get(r,r):<16} y~{ys:.0f} x~{xs:.0f}{'  (excluded)' if exc else ''}")

print("\n=== whole-map (y-span > 6000) entries per room ===")
for rid in sorted(room_polluted, key=lambda r: -room_polluted[r]):
    total = len(rooms[str(rid)].get("job_bounds_history", []))
    print(f"  {NAMES.get(rid,rid):<16} {room_polluted[rid]} of {total} runs are whole-map")
