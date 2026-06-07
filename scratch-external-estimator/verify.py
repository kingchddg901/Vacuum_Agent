"""Verify the de-polluted-geometry discriminator on Run 1 (ground truth = Kitchen).

Fixed rule applied identically to every area-gated candidate:
  1. De-pollute: keep job_bounds_history runs with box_area <= K * trail_bbox_area
     (drop transit/whole-map runs). K swept to show robustness.
  2. Centroid hard-gate: a room must have >=1 honest run containing the trail centroid.
  3. Score = best point-containment among gated honest runs; tiebreak = shape distance
     |w-wt|+|h-ht|. (Deliberately NOT IoU — see Bathroom.)

Goal: confirm Kitchen wins with margin, and is NOT a threshold artifact.
"""
import csv, json, datetime as dt

NAMES = {2:"Bathroom",5:"Kitchen",9:"Office",11:"Cat Room"}
CANDS = [5, 11, 2, 9]
TRUTH = 5  # Kitchen (ground truth, this fork only)

rooms = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    if "+" in s: s = s.split("+")[0]
    return dt.datetime.fromisoformat(s)

rows = []
with open(r"C:\Users\CKing\Downloads\history.csv", newline="") as f:
    for row in csv.DictReader(f):
        rows.append((row["entity_id"], row["state"], parse_ts(row["last_changed"])))
def series(ent):
    return sorted([(t, float(s)) for (e, s, t) in rows if e == ent and s not in ("unknown","unavailable","")], key=lambda p: p[0])
ev = sorted([(t,'x',v) for t,v in series("sensor.alfred_robot_position_x_raw")]
          + [(t,'y',v) for t,v in series("sensor.alfred_robot_position_y_raw")], key=lambda e: e[0])
cx=cy=None; pts=[]
for t,k,v in ev:
    if k=='x': cx=v
    else: cy=v
    if cx is not None and cy is not None: pts.append((t,cx,cy))
WS=parse_ts("2026-06-06T17:41:53.688"); WE=parse_ts("2026-06-06T17:52:13.212")
clean=[(x,y) for (t,x,y) in pts if WS<=t<=WE]
txs=[x for x,_ in clean]; tys=[y for _,y in clean]
TCX,TCY=sum(txs)/len(txs),sum(tys)/len(tys)
WT,HT=max(txs)-min(txs),max(tys)-min(tys)
AT=WT*HT
print(f"TRAIL n={len(clean)} w={WT:.0f} h={HT:.0f} area={AT:.0f} centroid=({TCX:.0f},{TCY:.0f})  TRUTH=Kitchen\n")

def barea(h): return max(0.0,h["max_x"]-h["min_x"])*max(0.0,h["max_y"]-h["min_y"])
def contains(h,x,y): return h["min_x"]<=x<=h["max_x"] and h["min_y"]<=y<=h["max_y"]
def pct_in(h): return 100.0*sum(1 for x,y in clean if contains(h,x,y))/len(clean)
def shape(h): return abs((h["max_x"]-h["min_x"])-WT)+abs((h["max_y"]-h["min_y"])-HT)

def score_room(rid, K):
    hist=[h for h in rooms[str(rid)].get("job_bounds_history",[]) if not h.get("excluded")]
    honest=[h for h in hist if barea(h) <= K*AT]
    if not honest: return ("DISQUAL (no honest run)", None, None, 0)
    gated=[h for h in honest if contains(h,TCX,TCY)]
    if not gated: return ("ELIM (centroid outside)", None, None, len(honest))
    best=max(gated, key=lambda h:(pct_in(h), -shape(h)))
    return ("ok", pct_in(best), shape(best), len(honest))

def width(h): return h["max_x"]-h["min_x"]
def height(h): return h["max_y"]-h["min_y"]

def score_room_gated(rid, K, wlo=0.6, whi=1.6):
    """Add a shape gate: honest+centroid-gated run must also have width within
    [wlo,whi]x trail width (kills map-wide boxes even at a loose cutoff)."""
    hist=[h for h in rooms[str(rid)].get("job_bounds_history",[]) if not h.get("excluded")]
    honest=[h for h in hist if barea(h) <= K*AT]
    if not honest: return ("DISQUAL (no honest run)", None, None, None)
    gated=[h for h in honest if contains(h,TCX,TCY) and wlo*WT<=width(h)<=whi*WT]
    if not gated: return ("ELIM (no centroid+shape run)", None, None, None)
    best=max(gated, key=lambda h:(pct_in(h), -shape(h)))
    return ("ok", pct_in(best), shape(best), width(best)/WT)

print("############ SHAPE-GATED discriminator (centroid + width within 0.6-1.6x) ############\n")
for K in (1.5, 2.0, 3.0, 4.0):
    rkk=[]
    for rid in CANDS:
        st_,cont,sh,wr=score_room_gated(rid,K)
        rkk.append((rid,st_,cont,sh,wr))
    ok=sorted([b for b in rkk if b[1]=="ok"], key=lambda b:(-b[2], b[3]))
    other=[b for b in rkk if b[1]!="ok"]
    win="—" if not ok else ("KITCHEN" if ok[0][0]==TRUTH else NAMES[ok[0][0]].upper())
    print(f"=== K={K} === winner: {win}")
    for rank,(rid,st_,cont,sh,wr) in enumerate(ok,1):
        tag=" <== TRUTH" if rid==TRUTH else ""
        print(f"  #{rank} {NAMES[rid]:<12} containment={cont:5.0f}%  shapeDist={sh:6.0f}  widthRatio={wr:.2f}{tag}")
    for rid,st_,cont,sh,wr in other:
        tag=" <== TRUTH" if rid==TRUTH else ""
        print(f"     {NAMES[rid]:<12} {st_}{tag}")
    print()
