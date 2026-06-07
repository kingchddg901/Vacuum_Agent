"""Last geometry attempt: FIXED de-pollution cutoff + envelope containment, both runs.

My area-SCALED filter (box<=2x trail) was unstable: a small ctime trail discards the
true room's representative box. Use a FIXED cutoff instead (drop whole-map boxes),
and attribute by the blind session's envelope idea: % of trail points inside the
UNION of a room's honest (de-polluted) boxes. Swept over cutoffs, ctime window, both
runs. Question: is there ONE rule that puts Kitchen #1 on BOTH runs with a margin?
"""
import csv, datetime as dt, statistics as st, json

NAMES={2:"Bathroom",5:"Kitchen",9:"Office",11:"Cat Room"}; CANDS=[5,11,2,9]; TRUTH=5
RUNS=[("Run1",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv"),
      ("Run2",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv")]
rooms=json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load_rows(path):
    with open(path,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]
def fseries(rows,ent):
    return sorted([(t,float(s)) for e,s,t in rows if e==ent and s not in ("unknown","unavailable","")],key=lambda p:p[0])
def ctime_window(rows):
    ct=fseries(rows,"sensor.alfred_cleaning_time"); zeros=[t for t,v in ct if v==0]
    reset=max(zeros) if zeros else ct[0][0]; pos=[t for t,v in ct if v>0 and t>reset]
    return min(pos),max(pos)
def trail(rows,ws,we):
    xs,ys=fseries(rows,"sensor.alfred_robot_position_x_raw"),fseries(rows,"sensor.alfred_robot_position_y_raw")
    ev=sorted([(t,"x",v) for t,v in xs]+[(t,"y",v) for t,v in ys],key=lambda e:e[0])
    cx=cy=None; pts=[]
    for t,k,v in ev:
        if k=="x": cx=v
        else: cy=v
        if cx is not None and cy is not None and ws<=t<=we: pts.append((cx,cy))
    return pts
def barea(h): return max(0.0,h["max_x"]-h["min_x"])*max(0.0,h["max_y"]-h["min_y"])
def contains(h,x,y): return h["min_x"]<=x<=h["max_x"] and h["min_y"]<=y<=h["max_y"]

# map full extent (for context on what "whole-map" means)
allx=[h["min_x"] for r in rooms.values() for h in r.get("job_bounds_history",[])]+[h["max_x"] for r in rooms.values() for h in r.get("job_bounds_history",[])]
ally=[h["min_y"] for r in rooms.values() for h in r.get("job_bounds_history",[])]+[h["max_y"] for r in rooms.values() for h in r.get("job_bounds_history",[])]
print(f"map extent x[{min(allx):.0f}..{max(allx):.0f}] y[{min(ally):.0f}..{max(ally):.0f}]  full-area={ (max(allx)-min(allx))*(max(ally)-min(ally)):.0f}")

trails={}
for label,path in RUNS:
    rows=load_rows(path); ws,we=ctime_window(rows); trails[label]=trail(rows,ws,we)

for CUT in (3_000_000, 4_000_000, 5_000_000):
    print(f"\n===================== FIXED cutoff: drop boxes with area > {CUT:,} =====================")
    for label in ("Run1","Run2"):
        pts=trails[label]; txs=[p[0] for p in pts]; tys=[p[1] for p in pts]
        TCX,TCY=st.mean(txs),st.mean(tys)
        def envcont(rid):
            hs=[h for h in rooms[str(rid)].get("job_bounds_history",[]) if not h.get("excluded") and barea(h)<=CUT]
            if not hs: return (None,0,False)
            pc=100.0*sum(1 for x,y in pts if any(contains(h,x,y) for h in hs))/len(pts)
            cen=any(contains(h,TCX,TCY) for h in hs)
            return (pc,len(hs),cen)
        res=[(rid,)+envcont(rid) for rid in CANDS]
        ok=sorted([r for r in res if r[1] is not None],key=lambda r:-r[1])
        win="NONE" if not ok else ("KITCHEN" if ok[0][0]==TRUTH else NAMES[ok[0][0]].upper())
        margin = (ok[0][1]-ok[1][1]) if len(ok)>=2 else float('nan')
        print(f"  {label}: winner={win}  margin={margin:.0f}pts")
        for rid,pc,nh,cen in sorted(res,key=lambda r:-(r[1] if r[1] is not None else -1)):
            tag=" <==TRUTH" if rid==TRUTH else ""
            s="no honest boxes" if pc is None else f"envelopeContainment={pc:5.0f}%  centroidIn={'Y' if cen else 'n'}  honestBoxes={nh}"
            print(f"     {NAMES[rid]:<12} {s}{tag}")
