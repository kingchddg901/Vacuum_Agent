"""Where did the 'massive maxes' come from? Separate:
  - approach/idle gap = 0 -> first positive tick (export-start idle + dock->room transit)
  - within-cleaning gaps = positive tick -> next positive tick (the only place a real
    inter-room plateau can live)
A reset (value drops to 0) breaks the chain so cross-job idle is never counted.
"""
import csv, datetime as dt

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

print(f"{'job':<22}{'approach(0->1st)':>18}{'within-clean gaps':>32}")
for name,path in FILES.items():
    rows=[]
    with open(path,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_id"]=="sensor.alfred_cleaning_time" and r["state"] not in("unknown","unavailable",""):
                rows.append((parse_ts(r["last_changed"]),float(r["state"])))
    rows.sort()
    approaches=[]; within=[]; prev=None
    for t,v in rows:
        if v==0: prev=("reset",t); continue
        if prev is None: prev=(v,t); continue
        pv,pt=prev
        if pv=="reset": approaches.append((t-pt).total_seconds())
        elif v>pv:      within.append((t-pt).total_seconds())
        prev=(v,t)
    appr=f"{max(approaches):.0f}s" if approaches else "-"
    wstr=(f"med {sorted(within)[len(within)//2]:.0f}s  max {max(within):.0f}s  (n={len(within)})") if within else "-"
    note=""
    if within and max(within)>120: note="  <- REAL plateau (wash)"
    elif within and max(within)<=45: note="  <- no plateau (continuous)"
    print(f"{name:<22}{appr:>18}{wstr:>32}{note}")
