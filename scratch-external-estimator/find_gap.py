"""Where in the rise do run1's 40s and run2's 41s within-cleaning gaps occur?
Print every cleaning tick with its gap to the previous; flag the long ones."""
import csv, datetime as dt

FILES={
 "run1 (Kitchen)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",
 "run2 (Kitchen)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv",
}
def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
for name,path in FILES.items():
    ct=[]
    with open(path,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_id"]=="sensor.alfred_cleaning_time" and r["state"] not in("unknown","unavailable",""):
                ct.append((parse_ts(r["last_changed"]),float(r["state"])))
    ct.sort()
    last_reset=max((t for t,v in ct if v==0), default=ct[0][0])
    pos=[(t,v) for t,v in ct if v>0 and t>=last_reset]
    print(f"\n=== {name} === ({len(pos)} ticks, peak {pos[-1][1]:.0f})")
    prev=None
    for i,(t,v) in enumerate(pos):
        gap=(t-prev).total_seconds() if prev else 0
        pct=100*i/(len(pos)-1)
        flag=f"   <== {gap:.0f}s gap  (tick {i+1}/{len(pos)}, {pct:.0f}% through rise)" if gap>35 else ""
        print(f"   {t.time().isoformat('seconds')}  v={v:>3.0f}  gap={gap:>3.0f}s{flag}")
        prev=t
