"""v4: weight by the CSV-undetectable settings using each room's STORED config
(which the device applies even to app jobs), gated by the detectable mop mode.
 - passes & edge come from the room's map-stored config
 - mop confirmed (mode=vacuum+mop, water consumed) => carpet/vacuum-only excluded,
   edge-mop is in play for edge-configured rooms
 - edge-on rooms may run ABOVE their no-edge history (edge adds perimeter time);
   edge-off rooms are pinned near their no-edge base."""
import json, glob, statistics as st
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
SLUGNAME = {v.lower().replace(" ","_").replace("'",""): v for v in NAMES.values()}
EXT_AREA, EXT_TIME, AREA_GATE = 4.0, 540.0, 1.5

# --- area + no-edge time bases per (room, passes) from single-room learning jobs ---
area = defaultdict(list)
noedge = defaultdict(lambda: defaultdict(list))   # slug -> passes -> [tsec] (edge off only)
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception: continue
    if d.get("outcome", {}).get("used_for_learning") is not True: continue
    rooms = (d.get("job_profile", {}) or {}).get("rooms", []) or []
    if len(rooms) != 1: continue
    r = rooms[0]; slug = str(r.get("slug", "")).strip().lower()
    if not slug: continue
    j = d.get("job", {})
    if j.get("cleaning_area_m2") is not None: area[slug].append(float(j["cleaning_area_m2"]))
    if j.get("cleaning_time_seconds") is not None and not bool(r.get("edge_mopping", False)):
        noedge[slug][int(r.get("clean_passes", r.get("clean_times", 1)) or 1)].append(float(j["cleaning_time_seconds"]))

# --- stored per-room config ---
sj = json.load(open(r"Z:\.storage\eufy_vacuum.storage", encoding="utf-8"))
cfg_rooms = sj["data"]["maps"]["vacuum.alfred"]["6"]["rooms"]
cfg = {}
for rid, rm in cfg_rooms.items():
    slug = str(rm.get("name","")).lower().replace(" ","_").replace("'","")
    cfg[slug] = (int(rm.get("clean_passes",1) or 1), bool(rm.get("edge_mopping", False)),
                 str(rm.get("floor_type","")), str(rm.get("clean_mode","")))

def area_fit(ad): return 1.0/(1.0+ad)
def time_fit(base, edge):
    if base is None: return 0.0
    if edge:   # edge adds time, so observed >= base is consistent; below base is the penalty
        return 1.0 if EXT_TIME >= base*0.9 else 1.0/(1.0+(base-EXT_TIME)/120.0)
    return 1.0/(1.0+abs(EXT_TIME-base)/120.0)

print(f"EXTERNAL JOB  area={EXT_AREA:.0f} m2  time={EXT_TIME:.0f}s  (mop confirmed)\n")
rows = []
for slug, a in area.items():
    avg_a = st.mean(a); ad = abs(avg_a-EXT_AREA)
    passes, edge, floor, mode = cfg.get(slug, (1, False, "?", "?"))
    mops = "mop" in mode.lower()
    if "carpet" in floor or not mops:       # excluded: mop happened, so non-mopping rooms are out
        continue
    if ad > AREA_GATE:
        continue
    base = st.mean(noedge[slug][passes]) if noedge[slug].get(passes) else (
        st.mean(noedge[slug][2]) if noedge[slug].get(2) else None)
    score = round(area_fit(ad) * time_fit(base, edge), 3)
    rows.append((slug, avg_a, ad, passes, edge, base, score))

hdr = f"{'room':<14}{'area':>6}{'aD':>5}{'cfg passes/edge':>17}{'noedge base':>12}{'score':>7}"
print(hdr); print("-"*len(hdr))
for slug, avg_a, ad, passes, edge, base, score in sorted(rows, key=lambda x: -x[6]):
    ce = f"{passes}p / {'edge' if edge else 'no-edge'}"
    bs = f"{base:.0f}s" if base is not None else "-"
    note = ""
    if edge and base is not None and EXT_TIME >= base:
        note = f"  (edge can add {EXT_TIME-base:.0f}s -> 540)"
    elif not edge and base is not None:
        note = f"  (pinned ~{base:.0f}s, no edge to add)"
    print(f"{SLUGNAME.get(slug,slug):<14}{avg_a:>6.1f}{ad:>5.1f}{ce:>17}{bs:>12}{score:>7.3f}{note}")
