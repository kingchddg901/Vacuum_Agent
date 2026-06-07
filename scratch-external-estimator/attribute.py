"""Generalized external-job attributor (validated rule), ready for the Hallway run.

Pipeline: read CSV -> area + mop from sensors -> area/carpet gate over all rooms ->
envelope containment (ctime window, FIXED cutoff, point-in-any-box, centroid gate)
over the shortlist AND over all rooms -> abstain if weak.

Set CSV_PATH + TRUTH_RID below. Dry-run default = Run 1 (truth Kitchen=5).
"""
import csv, datetime as dt, statistics as st, json
from collections import defaultdict

CSV_PATH = r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv"
TRUTH_RID = 4

NAMES={1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
CARPET={1,3}                # Heidi and Chris, Bryan (handoff §6)
CUT=4_000_000; AREA_GATE=1.5; CONT_FLOOR=60.0   # abstain below this containment
rooms=json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]

# per-room avg area from the learning archive (single-room jobs)
import glob
area_samples=defaultdict(list)
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    j=d.get("job",{}); q=d.get("queue",{})
    rids=q.get("queue_room_ids") or [r.get("room_id") for r in d.get("resolved_rooms",[])]
    if j.get("room_count",len(rids) if rids else 0)==1 and rids and j.get("cleaning_area_m2") is not None:
        area_samples[rids[0]].append(float(j["cleaning_area_m2"]))
avg_area={rid:st.mean(v) for rid,v in area_samples.items()}

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load_rows(path):
    with open(path,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]
def fser(rows,ent):
    return sorted([(t,float(s)) for e,s,t in rows if e==ent and s not in ("unknown","unavailable","")],key=lambda p:p[0])
def sser(rows,ent):
    return [s for e,s,t in rows if e==ent]
def barea(h): return max(0.0,h["max_x"]-h["min_x"])*max(0.0,h["max_y"]-h["min_y"])
def contains(h,x,y): return h["min_x"]<=x<=h["max_x"] and h["min_y"]<=y<=h["max_y"]

rows=load_rows(CSV_PATH)
ct=fser(rows,"sensor.alfred_cleaning_time"); zeros=[t for t,v in ct if v==0]
reset=max(zeros) if zeros else (ct[0][0] if ct else None)
pos=[t for t,v in ct if v>0 and t>reset]
ws,we=min(pos),max(pos)
xs,ys=fser(rows,"sensor.alfred_robot_position_x_raw"),fser(rows,"sensor.alfred_robot_position_y_raw")
ev=sorted([(t,"x",v) for t,v in xs]+[(t,"y",v) for t,v in ys],key=lambda e:e[0])
cx=cy=None; pts=[]
for t,k,v in ev:
    if k=="x": cx=v
    else: cy=v
    if cx is not None and cy is not None and ws<=t<=we: pts.append((cx,cy))
txs=[p[0] for p in pts]; tys=[p[1] for p in pts]; TCX,TCY=st.mean(txs),st.mean(tys)

carea=fser(rows,"sensor.alfred_cleaning_area")
# guard the stale pre-reset value: take the max only AFTER cleaning_area resets to 0
_az=[t for t,v in carea if v==0]; _ar=max(_az) if _az else (carea[0][0] if carea else None)
_post=[v for t,v in carea if _ar is not None and t>=_ar]
job_area=max(_post) if _post else (max(v for _,v in carea) if carea else None)
modes=sser(rows,"select.alfred_cleaning_mode"); mopped=any("mop" in m.lower() for m in modes)

print(f"CSV={CSV_PATH.split(chr(92))[-1]}  truth={NAMES[TRUTH_RID]}")
print(f"trail: n={len(pts)} bbox x[{min(txs):.0f}..{max(txs):.0f}] y[{min(tys):.0f}..{max(tys):.0f}] centroid=({TCX:.0f},{TCY:.0f})")
print(f"job_area={job_area} m2  mopped={mopped}  modes={set(modes)}")

def envelope(rid):
    r=rooms.get(str(rid))
    if not r: return None
    hs=[h for h in r.get("job_bounds_history",[]) if not h.get("excluded") and barea(h)<=CUT]
    if not hs: return None
    pc=100.0*sum(1 for x,y in pts if any(contains(h,x,y) for h in hs))/len(pts)
    cen=any(contains(h,TCX,TCY) for h in hs)
    return (pc,cen,len(hs))

# area + carpet gate
shortlist=[rid for rid,a in avg_area.items() if abs(a-job_area)<=AREA_GATE and not (mopped and rid in CARPET)]
print(f"\nAREA+MOP SHORTLIST (|area-{job_area}|<= {AREA_GATE}): "+", ".join(f"{NAMES[r]}({avg_area[r]:.1f})" for r in sorted(shortlist,key=lambda r:abs(avg_area[r]-job_area))))
truth_repr = rooms.get(str(TRUTH_RID)) is not None and envelope(TRUTH_RID) is not None
print(f"TRUTH room representable by an envelope? {truth_repr}  (in shortlist? {TRUTH_RID in shortlist})")

def rank(ids,label):
    res=[(rid,envelope(rid)) for rid in ids]
    res=[(rid,e) for rid,e in res if e is not None]
    res.sort(key=lambda r:-r[1][0])
    print(f"\n-- {label} --")
    if not res: print("   (no candidate has an envelope)"); return
    for rid,(pc,cen,nh) in res:
        tag=" <==TRUTH" if rid==TRUTH_RID else ""
        print(f"   {NAMES[rid]:<16} containment={pc:5.0f}%  centroidIn={'Y' if cen else 'n'}  honestBoxes={nh}{tag}")
    top=res[0]
    decision = (f"ATTRIBUTE -> {NAMES[top[0]]}" if (top[1][0]>=CONT_FLOOR and top[1][1]) else "ABSTAIN (flag for review)")
    print(f"   => {decision}  [floor={CONT_FLOOR}%, centroid gate]")

rank(shortlist,"ranking within area+mop shortlist")
rank(list(avg_area.keys()),"ranking over ALL rooms (false-positive check)")
