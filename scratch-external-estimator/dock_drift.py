"""Dock = the one physically fixed point. Its reported raw coords per run reveal the
inter-session SLAM frame drift. If the drift is a consistent translation/rotation we
could transform sessions into a common frame; if it's inconsistent, we cannot.

For each run, report robot positions during docked/charging intervals (start + end),
plus first/last sample. Then compare the dock fix across runs.
"""
import csv, datetime as dt, statistics as st

RUNS=[("Run1",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv"),
      ("Run2",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv"),
      ("Run3",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv")]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load(path):
    with open(path,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]

def merged_positions(rows):
    xs=sorted([(t,float(s)) for e,s,t in rows if e=="sensor.alfred_robot_position_x_raw" and s not in("unknown","unavailable","")],key=lambda p:p[0])
    ys=sorted([(t,float(s)) for e,s,t in rows if e=="sensor.alfred_robot_position_y_raw" and s not in("unknown","unavailable","")],key=lambda p:p[0])
    ev=sorted([(t,"x",v) for t,v in xs]+[(t,"y",v) for t,v in ys],key=lambda e:e[0])
    cx=cy=None;out=[]
    for t,k,v in ev:
        if k=="x":cx=v
        else:cy=v
        if cx is not None and cy is not None: out.append((t,cx,cy))
    return out

def intervals(rows,ent,val):
    seq=sorted([(t,s) for e,s,t in rows if e==ent],key=lambda p:p[0])
    out=[];start=None
    for t,s in seq:
        if s==val and start is None: start=t
        elif s!=val and start is not None: out.append((start,t)); start=None
    if start is not None: out.append((start,seq[-1][0]+dt.timedelta(seconds=1)))
    return out

dock_fix={}
for label,path in RUNS:
    rows=load(path); pos=merged_positions(rows)
    docked=intervals(rows,"vacuum.alfred","docked")
    print(f"\n===== {label} =====")
    print(f"  vacuum 'docked' intervals: {[(a.time().isoformat('seconds'),b.time().isoformat('seconds')) for a,b in docked]}")
    # positions while docked
    dpos=[(t,x,y) for (t,x,y) in pos if any(a<=t<=b for a,b in docked)]
    for t,x,y in dpos:
        print(f"     docked-pos {t.time().isoformat('seconds')}  ({x:.0f},{y:.0f})")
    print(f"  first sample {pos[0][0].time().isoformat('seconds')} ({pos[0][1]:.0f},{pos[0][2]:.0f})   last sample {pos[-1][0].time().isoformat('seconds')} ({pos[-1][1]:.0f},{pos[-1][2]:.0f})")
    # best dock estimate: median of docked positions (fallback: last sample)
    if dpos:
        fix=(st.median([x for _,x,_ in dpos]),st.median([y for _,_,y in dpos]))
    else:
        fix=(pos[-1][1],pos[-1][2])
    dock_fix[label]=fix
    print(f"  -> dock fix (median docked / last): ({fix[0]:.0f},{fix[1]:.0f})")

print("\n===== inter-run dock drift (should be ~0 if frame were stable) =====")
ls=list(dock_fix)
for i in range(len(ls)):
    for j in range(i+1,len(ls)):
        a,b=dock_fix[ls[i]],dock_fix[ls[j]]
        d=((a[0]-b[0])**2+(a[1]-b[1])**2)**0.5
        print(f"  {ls[i]} {tuple(round(v) for v in a)}  vs  {ls[j]} {tuple(round(v) for v in b)}   drift = {d:.0f} raw  (dx={a[0]-b[0]:.0f}, dy={a[1]-b[1]:.0f})")
