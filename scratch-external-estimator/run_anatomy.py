"""Anatomy of each single-room run's cleaning_time: where is the 'long' time?
  approach = reset(0) -> first tick   (dock->room transit + any pre-job idle)
  rise     = first tick -> last tick  (the actual cleaning; should be ~peak seconds)
  tail     = last tick -> 'returning'  (how long after the last tick it leaves)
"""
import csv, datetime as dt

FILES={
 "run1 (Kitchen)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",
 "run2 (Kitchen)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv",
 "run3 (Hallway)": r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv",
}
def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)

for name,path in FILES.items():
    ct=[]; ret=None; resets=[]
    with open(path,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_id"]=="sensor.alfred_cleaning_time" and r["state"] not in("unknown","unavailable",""):
                ct.append((parse_ts(r["last_changed"]),float(r["state"])))
            if r["entity_id"]=="vacuum.alfred" and r["state"]=="returning":
                t=parse_ts(r["last_changed"]); ret=t if ret is None else ret
    ct.sort()
    last_reset_t=max((t for t,v in ct if v==0), default=ct[0][0])
    pos=[(t,v) for t,v in ct if v>0 and t>=last_reset_t]
    first_t,first_v=pos[0]; last_t,last_v=pos[-1]
    approach=(first_t-last_reset_t).total_seconds()
    rise=(last_t-first_t).total_seconds()
    tail=(ret-last_t).total_seconds() if ret and ret>last_t else None
    print(f"{name}:")
    print(f"   reset {last_reset_t.time().isoformat('seconds')} --approach {approach:.0f}s--> first tick {first_t.time().isoformat('seconds')} (v={first_v:.0f})")
    print(f"   --RISE {rise:.0f}s ({first_v:.0f}->{last_v:.0f}, continuous)--> last tick {last_t.time().isoformat('seconds')} (peak={last_v:.0f})")
    print(f"   --tail {tail:.0f}s--> returning {ret.time().isoformat('seconds') if ret else '?'}   (cleaning_time then holds at {last_v:.0f})\n")
