"""External-job attribution prototype: combine area + time-range + centroid, blind."""
import json, glob, statistics as st, math
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
SLUGNAME = {v.lower().replace(" ","_").replace("'",""): v for v in NAMES.values()}

# --- the external job under test (from history.csv) ---
EXT_AREA = 4.0        # sensor.alfred_cleaning_area (max)
EXT_TIME = 540.0      # sensor.alfred_cleaning_time (max), seconds
EXT_CX, EXT_CY = 15578.0, 4925.0   # trail centroid, clean window (prior trail analysis)

# --- per-room profiles from single-room learning jobs ---
area = defaultdict(list); tsec = defaultdict(list)
tsec_by_pass = defaultdict(lambda: defaultdict(list))
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d = json.load(open(p, encoding="utf-8"))
    except Exception: continue
    if d.get("outcome", {}).get("used_for_learning") is not True: continue
    j = d.get("job", {}); rooms = (d.get("job_profile", {}) or {}).get("rooms", []) or []
    if len(rooms) != 1: continue
    r = rooms[0]; slug = str(r.get("slug", "")).strip().lower()
    if not slug: continue
    a = j.get("cleaning_area_m2"); ts = j.get("cleaning_time_seconds")
    passes = str(r.get("clean_passes", r.get("clean_times", 1)))
    if a is not None: area[slug].append(float(a))
    if ts is not None:
        tsec[slug].append(float(ts)); tsec_by_pass[slug][passes].append(float(ts))

# --- per-room bounds centroid (raw space) ---
bounds = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]
cent = {}
for rid, rb in bounds.items():
    b = rb.get("bounds", {})
    nm = NAMES.get(int(rid))
    if nm and b.get("cx") is not None:
        cent[nm.lower().replace(" ","_").replace("'","")] = (b["cx"], b["cy"])

# --- signal -> [0,1] match scores ---
def m_area(a): return 1.0/(1.0+abs(a-EXT_AREA)) if a is not None else 0.0
def m_time(tmin, tmax):
    if tmin is None: return 0.0
    if tmin <= EXT_TIME <= tmax: return 1.0
    d = (tmin-EXT_TIME) if EXT_TIME < tmin else (EXT_TIME-tmax)
    return 1.0/(1.0+d/60.0)
def m_cent(cd): return 1.0/(1.0+cd/300.0) if cd is not None else 0.0

W_A, W_T, W_C = 0.50, 0.35, 0.15   # centroid weak: bounds are transit-polluted
rows = []
for slug in set(list(area)+list(tsec)):
    a = area.get(slug, []); ts = tsec.get(slug, [])
    avg_a = st.mean(a) if a else None
    tmin = min(ts) if ts else None; tmax = max(ts) if ts else None
    c = cent.get(slug); cd = math.hypot(EXT_CX-c[0], EXT_CY-c[1]) if c else None
    score = W_A*m_area(avg_a) + W_T*m_time(tmin, tmax) + W_C*m_cent(cd)
    rows.append((slug, avg_a, tmin, tmax, cd, score))

print(f"EXTERNAL JOB  area={EXT_AREA:.0f} m2  time={EXT_TIME:.0f}s  trail_centroid=({EXT_CX:.0f},{EXT_CY:.0f})")
print(f"weights: area {W_A} | time-in-range {W_T} | centroid {W_C}  (centroid weak: transit-polluted bounds)\n")
h = f"{'room':<16}{'avg_a':>6}{'aD':>5}{'time_s range':>14}{'fit':>5}{'cdist':>7}{'score':>7}"
print(h); print("-"*len(h))
for slug, avg_a, tmin, tmax, cd, score in sorted(rows, key=lambda x: -x[5]):
    nm = SLUGNAME.get(slug, slug)
    av = f"{avg_a:.1f}" if avg_a is not None else "-"
    ad = f"{abs(avg_a-EXT_AREA):.1f}" if avg_a is not None else "-"
    tr = f"{tmin:.0f}..{tmax:.0f}" if tmin is not None else "-"
    fit = "in" if (tmin is not None and tmin <= EXT_TIME <= tmax) else "out"
    cds = f"{cd:.0f}" if cd is not None else "-"
    print(f"{nm:<16}{av:>6}{ad:>5}{tr:>14}{fit:>5}{cds:>7}{score:>7.2f}")

# show the per-pass time buckets for the top-3 (the new room_baselines.by_clean_times)
print("\nper-pass time buckets (s) for context:")
for slug, avg_a, tmin, tmax, cd, score in sorted(rows, key=lambda x: -x[5])[:4]:
    bp = {k: f"{round(st.mean(v))}(n{len(v)})" for k, v in sorted(tsec_by_pass[slug].items())}
    print(f"  {SLUGNAME.get(slug,slug):<16} {bp}")
