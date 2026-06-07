"""Thread A prototype: de-polluted per-room geometry vs the external trail.

Read-only analysis. For each room, instead of the transit-polluted aggregate
union box, derive an HONEST footprint from job_bounds_history (the tightest
single-run boxes), then test the external trail against it three ways:
  - containment: % of trail points inside the honest box
  - centroid-in: is the trail centroid inside the honest box?
  - IoU: overlap of trail bbox vs honest box

The aggregate boxes match ~everyone (attrib.py shows 7.1/8). The question is
whether honest per-run geometry separates the candidates.
"""
import csv, json, datetime as dt, statistics as st

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
CANDS = [5, 11, 2, 9]  # Kitchen, Cat Room, Bathroom, Office (area-gated shortlist)

BOUNDS = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))
rooms = BOUNDS["rooms"]

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    if "+" in s: s = s.split("+")[0]
    return dt.datetime.fromisoformat(s)

# --- trail from Run-1 CSV ---
rows = []
with open(r"C:\Users\CKing\Downloads\history.csv", newline="") as f:
    for row in csv.DictReader(f):
        rows.append((row["entity_id"], row["state"], parse_ts(row["last_changed"])))
def series(ent):
    out = [(t, float(s)) for (e, s, t) in rows if e == ent and s not in ("unknown","unavailable","")]
    return sorted(out, key=lambda p: p[0])
xs = series("sensor.alfred_robot_position_x_raw")
ys = series("sensor.alfred_robot_position_y_raw")
events = sorted([(t,'x',v) for t,v in xs]+[(t,'y',v) for t,v in ys], key=lambda e: e[0])
curx = cury = None; pts = []
for t,k,v in events:
    if k == 'x': curx = v
    else: cury = v
    if curx is not None and cury is not None: pts.append((t, curx, cury))
WS = parse_ts("2026-06-06T17:41:53.688"); WE = parse_ts("2026-06-06T17:52:13.212")
clean = [(x, y) for (t, x, y) in pts if WS <= t <= WE]
txs = [x for x,_ in clean]; tys = [y for _,y in clean]
tcx, tcy = sum(txs)/len(txs), sum(tys)/len(tys)
tbb = (min(txs), max(txs), min(tys), max(tys))
print(f"TRAIL  n={len(clean)}  bbox x[{tbb[0]:.0f}..{tbb[1]:.0f}] y[{tbb[2]:.0f}..{tbb[3]:.0f}]  centroid ({tcx:.0f},{tcy:.0f})")
print(f"       trail box: w={tbb[1]-tbb[0]:.0f} h={tbb[3]-tbb[2]:.0f}  raw-area={(tbb[1]-tbb[0])*(tbb[3]-tbb[2]):.0f}\n")

def area(b): return max(0.0,(b[1]-b[0]))*max(0.0,(b[3]-b[2]))
def iou(a, b):
    ix = max(0.0, min(a[1],b[1])-max(a[0],b[0]))
    iy = max(0.0, min(a[3],b[3])-max(a[2],b[2]))
    inter = ix*iy
    uni = area(a)+area(b)-inter
    return inter/uni if uni > 0 else 0.0
def contains(b, x, y): return b[0] <= x <= b[1] and b[2] <= y <= b[3]
def pct_in(b):
    return 100.0*sum(1 for x,y in clean if contains(b,x,y))/len(clean)

print(f"{'room':<16}{'#runs':>6}{'honest box (tightest)':>34}{'rawA':>8}{'pts%':>6}{'cen?':>6}{'IoU':>7}")
for rid in CANDS:
    rk = str(rid)
    hist = [h for h in rooms[rk].get("job_bounds_history", []) if not h.get("excluded")]
    if not hist:
        print(f"{NAMES[rid]:<16}{'0':>6}   (no honest runs)"); continue
    boxes = [(h["min_x"],h["max_x"],h["min_y"],h["max_y"],h.get("sample_count",0),h.get("recorded_at","?")[:10]) for h in hist]
    # honest footprint = the tightest (smallest-area) run box
    boxes.sort(key=lambda b: area(b[:4]))
    bx = boxes[0]
    b4 = bx[:4]
    cx, cy = (b4[0]+b4[1])/2, (b4[2]+b4[3])/2
    print(f"{NAMES[rid]:<16}{len(hist):>6}   x[{b4[0]:.0f}..{b4[1]:.0f}] y[{b4[2]:.0f}..{b4[3]:.0f}]{area(b4):>8.0f}{pct_in(b4):>5.0f}%{('YES' if contains(b4,tcx,tcy) else 'no'):>6}{iou(tbb,b4):>7.2f}  ({bx[5]} n={bx[4]})")

print("\n--- all honest runs per candidate (sorted tightest-first) ---")
for rid in CANDS:
    rk = str(rid)
    hist = [h for h in rooms[rk].get("job_bounds_history", []) if not h.get("excluded")]
    print(f"\n{NAMES[rid]} ({len(hist)} runs):")
    boxes = [(h["min_x"],h["max_x"],h["min_y"],h["max_y"],h.get("sample_count",0),h.get("recorded_at","?")[:10]) for h in hist]
    for b in sorted(boxes, key=lambda b: area(b[:4])):
        b4 = b[:4]
        print(f"   x[{b4[0]:.0f}..{b4[1]:.0f}] y[{b4[2]:.0f}..{b4[3]:.0f}]  rawA={area(b4):>7.0f} w={b4[1]-b4[0]:.0f} h={b4[3]-b4[2]:.0f}  pts%={pct_in(b4):>3.0f} cen={'Y' if contains(b4,tcx,tcy) else 'n'} IoU={iou(tbb,b4):.2f}  ({b[5]} n={b[4]})")
