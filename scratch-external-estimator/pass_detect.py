"""Read pass-count from an EXTERNAL job with NO device cooperation.

Unique-m2 cleaning_area RISES during pass 1 (new floor) then HOLDS while later passes
re-cover. So the cleaning_time value where area LAST increased ~= one pass's duration,
and  passes ~= total_cleaning_time / (cleaning_time at last area increase).
Also: room true area = the area plateau value (not inflated by extra passes).
"""
import csv, datetime as dt

FILES={
 "run1 (ext Kitchen)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",
 "run2 (ext Kitchen)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv",
 "run3 (ext Hallway)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv",
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
    reset=max(t for t,v in ct if v==0)
    ctp=[(t,v) for t,v in ct if v>0 and t>=reset]
    ca=[(t,float(s)) for t,s in ser("sensor.alfred_cleaning_area") if s not in("unknown","unavailable","")]
    cap=[(t,v) for t,v in ca if t>=reset]
    total=ctp[-1][1]; room_area=max(v for _,v in cap) if cap else 0
    # timestamp of last area increase
    last_inc_t=None; prev=None
    for t,v in cap:
        if prev is None or v>prev: last_inc_t=t
        prev=v
    # cleaning_time value at that moment
    ct_at=max([v for tt,v in ctp if tt<=last_inc_t], default=0)
    passes=total/ct_at if ct_at>0 else float('nan')
    print(f"{name:<20} total={total:.0f}s  area-plateau={room_area:.0f} m2 (true size)  "
          f"last area-rise at clean_time={ct_at:.0f}s  -> passes ~= {total:.0f}/{ct_at:.0f} = {passes:.1f}")
