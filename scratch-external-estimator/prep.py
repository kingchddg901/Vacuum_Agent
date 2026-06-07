"""Prep for the Hallway external run: room envelopes + CSV entity inventory."""
import csv, json
from collections import Counter

rooms = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]
NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
CUT = 4_000_000

def barea(h): return max(0.0,h["max_x"]-h["min_x"])*max(0.0,h["max_y"]-h["min_y"])

print("=== per-room honest envelope (boxes with area <= 4M), all rooms ===")
print(f"{'room':<16}{'#hist':>6}{'#honest':>8}   honest-envelope bbox (union)")
for rid,r in sorted(rooms.items(), key=lambda kv:int(kv[0])):
    hist=[h for h in r.get("job_bounds_history",[]) if not h.get("excluded")]
    honest=[h for h in hist if barea(h)<=CUT]
    name=NAMES.get(int(rid),rid)
    if honest:
        ex=(min(h["min_x"] for h in honest),max(h["max_x"] for h in honest),
            min(h["min_y"] for h in honest),max(h["max_y"] for h in honest))
        print(f"{name:<16}{len(hist):>6}{len(honest):>8}   x[{ex[0]:.0f}..{ex[1]:.0f}] y[{ex[2]:.0f}..{ex[3]:.0f}]")
    else:
        print(f"{name:<16}{len(hist):>6}{len(honest):>8}   (no honest boxes)")

print("\n=== room ids present in map_6.json ===")
present=sorted(int(k) for k in rooms)
print("   present:", present)
print("   MISSING:", [r for r in NAMES if r not in present], "->", [NAMES[r] for r in NAMES if r not in present])

if "4" in rooms:
    print("\n=== Hallway (room 4) every job_bounds_history box ===")
    for h in sorted(rooms["4"].get("job_bounds_history",[]), key=barea):
        print(f"   x[{h['min_x']:.0f}..{h['max_x']:.0f}] y[{h['min_y']:.0f}..{h['max_y']:.0f}]  area={barea(h):>9.0f} n={h.get('sample_count','?')} {h.get('recorded_at','?')[:10]} excl={h.get('excluded',False)}")
else:
    print("\n=== Hallway (room 4): NOT PRESENT in map_6.json (no bounds history at all) ===")

print("\n=== alfred entity inventory in run1-history.csv (id -> #rows) ===")
ids=Counter()
with open(r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",newline="",encoding="utf-8") as f:
    for row in csv.DictReader(f):
        e=row["entity_id"]
        if "alfred" in e and ("area" in e or "clean" in e or "mode" in e or "water" in e or "position" in e or "map" in e or e=="vacuum.alfred"):
            ids[e]+=1
for e,c in sorted(ids.items()):
    print(f"   {e:<45} {c}")
