"""v3: weight by the CSV-undetectable settings (passes, edge-mop), using the
detectable cleaning mode to constrain them. Mode=vacuum+mop + water consumed
=> mopping happened => edge-mop POSSIBLE, and carpet rooms excluded."""
import json, glob, statistics as st
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
SLUGNAME = {v.lower().replace(" ","_").replace("'",""): v for v in NAMES.values()}

EXT_AREA, EXT_TIME = 4.0, 540.0
AREA_GATE = 1.5

area = defaultdict(list)
carpet = defaultdict(list)
joint = defaultdict(lambda: defaultdict(list))   # slug -> (passes, edge) -> [tsec]
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception: continue
    if d.get("outcome", {}).get("used_for_learning") is not True: continue
    j = d.get("job", {}); rooms = (d.get("job_profile", {}) or {}).get("rooms", []) or []
    if len(rooms) != 1: continue
    r = rooms[0]; slug = str(r.get("slug", "")).strip().lower()
    if not slug: continue
    passes = int(r.get("clean_passes", r.get("clean_times", 1)) or 1)
    edge = bool(r.get("edge_mopping", False))
    carpet[slug].append(bool(r.get("is_carpet", r.get("carpet", False))))
    if j.get("cleaning_area_m2") is not None: area[slug].append(float(j["cleaning_area_m2"]))
    if j.get("cleaning_time_seconds") is not None:
        joint[slug][(passes, edge)].append(float(j["cleaning_time_seconds"]))

print("KNOWN from CSV: mode=Vacuum+mop, water 64->52 => MOPPING happened")
print("  => carpet rooms excluded (can't wet-mop carpet); edge-mop was POSSIBLE")
print(f"  => passes & edge unknown: weight each room by its BEST plausible (pass,edge) bucket vs {EXT_TIME:.0f}s\n")

cand = []
for slug, a in area.items():
    avg_a = st.mean(a); ad = abs(avg_a - EXT_AREA)
    is_carpet = sum(carpet[slug]) / len(carpet[slug]) > 0.5
    if ad > AREA_GATE or is_carpet:
        continue
    cand.append((slug, avg_a, ad, is_carpet))

for slug, avg_a, ad, is_carpet in sorted(cand, key=lambda x: x[2]):
    print(f"{SLUGNAME.get(slug,slug)}  area={avg_a:.1f} (aD {ad:.1f})")
    best = None
    for (passes, edge), ts in sorted(joint[slug].items()):
        m = st.mean(ts); dist = abs(EXT_TIME - m)
        tag = f"{passes}p {'edge' if edge else 'no-edge'}"
        print(f"    {tag:<12} {m:6.0f}s (n{len(ts):<2})  |540-{m:.0f}| = {dist:.0f}")
        if best is None or dist < best[1]:
            best = (tag, dist, m)
    if best:
        print(f"    -> best plausible bucket: {best[0]}  ({best[2]:.0f}s, off by {best[1]:.0f}s)\n")
