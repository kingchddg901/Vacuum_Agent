"""Across EVERY CSV handed over: does cleaning_time ever step by anything but +30?
Report the set of positive step sizes and the wall-clock gap distribution per file.
"""
import csv, datetime as dt
from collections import Counter

FILES={
 "run1 (Kitchen)"      : r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",
 "run2 (Kitchen)"      : r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv",
 "run3 (Hallway ext)"  : r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv",
 "multi-room (ext)"    : r"C:\Users\CKing\Downloads\multi room run.csv",
 "internal Hall+Kitch" : r"C:\Users\CKing\Downloads\history (1).csv",
 "no-mop Bath+Hall"    : r"C:\Users\CKing\Downloads\no mop job.csv",
}
def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)

for name,path in FILES.items():
    try:
        rows=[]
        with open(path,newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["entity_id"]=="sensor.alfred_cleaning_time" and r["state"] not in ("unknown","unavailable",""):
                    rows.append((parse_ts(r["last_changed"]),float(r["state"])))
    except FileNotFoundError:
        print(f"{name:<22} (file not found)"); continue
    rows.sort()
    steps=Counter(); gaps=[]
    for (t0,v0),(t1,v1) in zip(rows,rows[1:]):
        d=v1-v0
        if d>0:                       # ignore resets to 0
            steps[int(d)]+=1
            gaps.append((t1-t0).total_seconds())
    gapstr=f"gaps min/med/max = {min(gaps):.0f}/{sorted(gaps)[len(gaps)//2]:.0f}/{max(gaps):.0f}s" if gaps else "no ticks"
    odd = [k for k in steps if k!=30]
    print(f"{name:<22} steps={dict(sorted(steps.items()))}   {gapstr}" + (f"   <-- NON-30 STEP: {odd}" if odd else ""))
