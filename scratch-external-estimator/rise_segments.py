"""Does cleaning_time keep rising after a single-room run, or does it stop (plateau)?
And how many distinct RISE stretches does each job have (= rooms, IF every boundary
plateaus)? A rise stretch = consecutive +30 ticks <=45s apart; a >45s gap = plateau.
"""
import csv, datetime as dt

FILES={
 "run1 (Kitchen, 1rm)" : r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv",
 "run2 (Kitchen, 1rm)" : r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv",
 "run3 (Hallway, 1rm)" : r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv",
 "internal Hall+Kitch (2rm mop)": r"C:\Users\CKing\Downloads\history (1).csv",
 "no-mop Bath+Hall (2rm)": r"C:\Users\CKing\Downloads\no mop job.csv",
}
def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)

for name,path in FILES.items():
    ticks=[]
    with open(path,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_id"]=="sensor.alfred_cleaning_time" and r["state"] not in("unknown","unavailable",""):
                ticks.append((parse_ts(r["last_changed"]),float(r["state"])))
    ticks.sort()
    # take the LAST job in the file (after the final reset to 0)
    last_reset=max((i for i,(t,v) in enumerate(ticks) if v==0), default=0)
    job=[(t,v) for t,v in ticks[last_reset:] if v>0]
    # group into rise stretches
    segs=[]; cur=[job[0]]
    for (t0,v0),(t1,v1) in zip(job,job[1:]):
        if (t1-t0).total_seconds()>45 or v1<v0:
            segs.append(cur); cur=[(t1,v1)]
        else: cur.append((t1,v1))
    segs.append(cur)
    desc=" , ".join(f"{s[0][1]:.0f}->{s[-1][1]:.0f}" for s in segs)
    plats=[]
    for a,b in zip(segs,segs[1:]):
        plats.append((b[0][0]-a[-1][0]).total_seconds())
    peak=job[-1][1]
    print(f"{name:<32} rises={len(segs)}  [{desc}]  peak={peak:.0f}" + (f"  inner-plateaus={[f'{p:.0f}s' for p in plats]}" if plats else "  (no inner plateau -> ends, then holds at peak until next reset)"))
