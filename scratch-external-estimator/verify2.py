"""Run-2 stress test: does the discriminator generalize, and which method is robust?

Blind session's Run-2 finding: Run1 cleaned the LEFT sub-band, Run2 the RIGHT;
single-run footprints don't overlap (IoU 0.19). My Run-1 discriminator leaned on
shape+centroid match to a room's best single honest run. This tests, on BOTH runs:

  M1  best single honest run   : centroid-gate + width-gate, rank by containment   (mine)
  M3  union of honest runs     : % trail pts inside ANY honest (de-polluted) run    (theirs: envelope+containment)

against the same 4 area-gated candidates. Honest = job_bounds_history box with
area <= 2x the run's own bbox area. cleaning_time-gated window (device transit filter).
"""
import csv, datetime as dt, statistics as st

NAMES = {2:"Bathroom",5:"Kitchen",9:"Office",11:"Cat Room"}
CANDS = [5, 11, 2, 9]; TRUTH = 5
RUNS = [("Run1", r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv"),
        ("Run2", r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv")]
import json
rooms = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load_rows(path):
    with open(path,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]
def series(rows,ent):
    return sorted([(t,float(s)) for e,s,t in rows if e==ent and s not in ("unknown","unavailable","")],key=lambda p:p[0])
def window_ctime(rows):
    ct=series(rows,"sensor.alfred_cleaning_time")
    zeros=[t for t,v in ct if v==0]; reset=max(zeros) if zeros else ct[0][0]
    pos=[t for t,v in ct if v>0 and t>reset]
    return min(pos),max(t for t,_ in ct)
def trail(rows,ws,we):
    xs,ys=series(rows,"sensor.alfred_robot_position_x_raw"),series(rows,"sensor.alfred_robot_position_y_raw")
    ev=sorted([(t,"x",v) for t,v in xs]+[(t,"y",v) for t,v in ys],key=lambda e:e[0])
    cx=cy=None; pts=[]
    for t,k,v in ev:
        if k=="x": cx=v
        else: cy=v
        if cx is not None and cy is not None and ws<=t<=we: pts.append((cx,cy))
    return pts

def barea(h): return max(0.0,h["max_x"]-h["min_x"])*max(0.0,h["max_y"]-h["min_y"])
def contains(h,x,y): return h["min_x"]<=x<=h["max_x"] and h["min_y"]<=y<=h["max_y"]

for label,path in RUNS:
    rows=load_rows(path); ws,we=window_ctime(rows); pts=trail(rows,ws,we)
    txs=[p[0] for p in pts]; tys=[p[1] for p in pts]
    TCX,TCY=st.mean(txs),st.mean(tys); WT=max(txs)-min(txs); HT=max(tys)-min(tys); AT=WT*HT
    print(f"\n################# {label}  n={len(pts)}  bbox x[{min(txs):.0f}..{max(txs):.0f}] y[{min(tys):.0f}..{max(tys):.0f}]  w={WT:.0f} h={HT:.0f}  centroid=({TCX:.0f},{TCY:.0f}) #################")

    def honest(rid):
        hist=[h for h in rooms[str(rid)].get("job_bounds_history",[]) if not h.get("excluded")]
        return [h for h in hist if barea(h)<=2.0*AT]
    def pct_in_box(h): return 100.0*sum(1 for x,y in pts if contains(h,x,y))/len(pts)
    def pct_in_any(hs): return 100.0*sum(1 for x,y in pts if any(contains(h,x,y) for h in hs))/len(pts)

    # M1: best single honest run, centroid-gate + width-gate
    print("  -- M1 (mine: best single honest run; centroid+width gate) --")
    m1=[]
    for rid in CANDS:
        hs=honest(rid)
        gated=[h for h in hs if contains(h,TCX,TCY) and 0.6*WT<=(h["max_x"]-h["min_x"])<=1.6*WT]
        if not gated: m1.append((rid,None)); continue
        best=max(gated,key=lambda h:pct_in_box(h)); m1.append((rid,(pct_in_box(best),(best["max_x"]-best["min_x"])/WT)))
    for rid,v in sorted(m1,key=lambda r:(-(r[1][0] if r[1] else -1))):
        tag=" <==TRUTH" if rid==TRUTH else ""
        print(f"     {NAMES[rid]:<12} "+("ELIM" if not v else f"containment={v[0]:5.0f}%  widthRatio={v[1]:.2f}")+tag)

    # M3: union of honest runs, % points inside any honest box
    print("  -- M3 (theirs: % trail points inside ANY honest run = de-polluted envelope) --")
    m3=[]
    for rid in CANDS:
        hs=honest(rid)
        m3.append((rid, pct_in_any(hs) if hs else None, len(hs)))
    for rid,v,nh in sorted(m3,key=lambda r:-(r[1] if r[1] is not None else -1)):
        tag=" <==TRUTH" if rid==TRUTH else ""
        print(f"     {NAMES[rid]:<12} "+("no honest runs" if v is None else f"envelope-containment={v:5.0f}%  (honestRuns={nh})")+tag)
