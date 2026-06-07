"""v2: area-GATE first, then nearest settings-bucket time distance. Centroid shown, not scored."""
import json, glob, statistics as st, math
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
SLUGNAME = {v.lower().replace(" ","_").replace("'",""): v for v in NAMES.values()}

EXT_AREA, EXT_TIME = 4.0, 540.0
EXT_CX, EXT_CY = 15578.0, 4925.0

area = defaultdict(list); tsec_by_pass = defaultdict(lambda: defaultdict(list))
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception: continue
    if d.get("outcome", {}).get("used_for_learning") is not True: continue
    j = d.get("job", {}); rooms = (d.get("job_profile", {}) or {}).get("rooms", []) or []
    if len(rooms) != 1: continue
    r = rooms[0]; slug = str(r.get("slug", "")).strip().lower()
    if not slug: continue
    if j.get("cleaning_area_m2") is not None: area[slug].append(float(j["cleaning_area_m2"]))
    if j.get("cleaning_time_seconds") is not None:
        tsec_by_pass[slug][str(r.get("clean_passes", r.get("clean_times", 1)))].append(float(j["cleaning_time_seconds"]))

bounds = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]
cent = {NAMES[int(rid)].lower().replace(" ","_").replace("'",""): (rb["bounds"]["cx"], rb["bounds"]["cy"])
        for rid, rb in bounds.items() if int(rid) in NAMES and rb.get("bounds", {}).get("cx") is not None}

def nearest_bucket(slug):
    bk = tsec_by_pass.get(slug, {})
    if not bk: return None, None
    means = {k: st.mean(v) for k, v in bk.items()}
    best = min(means, key=lambda k: abs(EXT_TIME-means[k]))
    return best, means[best]

AREA_GATE = 1.5
rows = []
for slug, a in area.items():
    avg_a = st.mean(a); ad = abs(avg_a-EXT_AREA)
    bpass, bmean = nearest_bucket(slug)
    bd = abs(EXT_TIME-bmean) if bmean is not None else None
    c = cent.get(slug); cd = math.hypot(EXT_CX-c[0], EXT_CY-c[1]) if c else None
    rows.append((slug, avg_a, ad, bpass, bmean, bd, cd))

print(f"EXTERNAL JOB  area={EXT_AREA:.0f} m2  time={EXT_TIME:.0f}s\n")
surv = sorted([r for r in rows if r[2] <= AREA_GATE], key=lambda x: (x[2], x[5] if x[5] is not None else 9e9))
print(f"=== area-gated shortlist  |area-4| <= {AREA_GATE} ===")
h = f"{'room':<16}{'avg_a':>6}{'aD':>5}{'nearest bucket':>16}{'tD(s)':>7}{'cdist':>7}"
print(h); print("-"*len(h))
for slug, avg_a, ad, bpass, bmean, bd, cd in surv:
    nb = f"{bpass}p:{bmean:.0f}s" if bmean is not None else "-"
    print(f"{SLUGNAME.get(slug,slug):<16}{avg_a:>6.1f}{ad:>5.1f}{nb:>16}{(f'{bd:.0f}' if bd is not None else '-'):>7}{(f'{cd:.0f}' if cd is not None else '-'):>7}")
elim = sorted([r for r in rows if r[2] > AREA_GATE], key=lambda x: x[2])
print("\neliminated by area gate: " + ", ".join(f"{SLUGNAME.get(r[0],r[0])}({r[1]:.0f})" for r in elim))
