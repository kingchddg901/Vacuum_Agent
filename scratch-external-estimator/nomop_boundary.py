"""Both no-mop Bath+Hall runs: is the room transition a DELAYED (not skipped) time step,
co-occurring with an area jump? And does position shift there too?
"""
import csv, datetime as dt, statistics as st

FILES={
 "no-mop #1 (2 rooms)": r"C:\Users\CKing\Downloads\no mop job.csv",
 "no-mop #2 (2 rooms)": r"C:\Users\CKing\Downloads\Second test bathroom hallway.csv",
 "run1 (1 room, 2-pass)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",
 "run2 (1 room, 2-pass)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv",
}
def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)

for name,path in FILES.items():
    rows=[]
    with open(path,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append((r["entity_id"],r["state"],parse_ts(r["last_changed"])))
    def ser(e): return sorted([(t,s) for ee,s,t in rows if ee==e],key=lambda p:p[0])
    ct=[(t,float(s)) for t,s in ser("sensor.alfred_cleaning_time") if s not in("unknown","unavailable","")]
    ca=sorted([(t,float(s)) for t,s in ser("sensor.alfred_cleaning_area") if s not in("unknown","unavailable","")])
    reset=max(t for t,v in ct if v==0)
    def area_at(t):
        cand=[a for tt,a in ca if reset<=tt<=t]   # post-reset only (ignore stale pre-reset value)
        return cand[-1] if cand else 0
    pos=[(t,v) for t,v in ct if v>0 and t>=reset]
    peak=pos[-1][1]
    print(f"\n=== {name}  (total {peak:.0f}s) ===")
    prev=None; prevA=0; boundary=None
    for t,v in pos:
        gap=(t-prev).total_seconds() if prev else 0
        A=area_at(t); dA=A-prevA
        flag=""
        if gap>35 and dA>=2: flag=f"  <== DELAYED {gap:.0f}s + area jump +{dA:.0f}  (transition @ {100*v/peak:.0f}% of clean)"; boundary=t
        elif gap>35: flag=f"  (delayed {gap:.0f}s)"
        elif dA>=2: flag=f"  (area +{dA:.0f})"
        print(f"   {t.time().isoformat('seconds')}  t={v:>3.0f}  gap={gap:>3.0f}s  area={A:.0f}{flag}")
        prev=t; prevA=A
    # position centroid before vs after the boundary (within-job frame is stable)
    if boundary:
        xs=sorted([(t,float(s)) for ee,s,t in rows if ee=="sensor.alfred_robot_position_x_raw" and s not in("unknown","unavailable","")])
        ys=sorted([(t,float(s)) for ee,s,t in rows if ee=="sensor.alfred_robot_position_y_raw" and s not in("unknown","unavailable","")])
        def cen(seq,a,b):
            v=[x for t,x in seq if a<=t<=b]; return st.mean(v) if v else float('nan')
        c0=reset; c1=boundary; c2=pos[-1][0]
        print(f"   position centroid  before-boundary ({cen(xs,c0,c1):.0f},{cen(ys,c0,c1):.0f})  vs  after ({cen(xs,c1,c2):.0f},{cen(ys,c1,c2):.0f})")
