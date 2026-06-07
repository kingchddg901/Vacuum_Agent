"""Watch the cleaning_time cadence on the no-mop Bathroom+Hallway job: does the
inter-room boundary produce a plateau, or does the counter tick straight through?
"""
import csv, datetime as dt

PATH=r"C:\Users\CKing\Downloads\no mop job.csv"
def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
rows=[]
with open(PATH,newline="",encoding="utf-8") as f:
    for r in csv.DictReader(f): rows.append((r["entity_id"],r["state"],parse_ts(r["last_changed"])))
def ser(e): return sorted([(t,s) for ee,s,t in rows if ee==e],key=lambda p:p[0])

ct=[(t,float(s)) for t,s in ser("sensor.alfred_cleaning_time") if s not in("unknown","unavailable","")]
ca=sorted([(t,float(s)) for t,s in ser("sensor.alfred_cleaning_area") if s not in("unknown","unavailable","")])
def area_at(t): return max([a for tt,a in ca if tt<=t], default=0)

print("clean_time cadence (gap = seconds since previous tick; ~30s = actively cleaning):\n")
print(f"{'clock':>12}{'time':>6}{'gap':>7}{'area':>6}")
prev=None; maxgap=0
for t,v in ct:
    if v==0:
        print(f"{t.time().isoformat('seconds'):>12}{v:>6.0f}{'--':>7}{area_at(t):>6.0f}   reset/start"); prev=t; continue
    gap=(t-prev).total_seconds() if prev else 0
    maxgap=max(maxgap,gap)
    flag = "  <-- PLATEAU" if gap>45 else ("  <- long" if gap>35 else "")
    print(f"{t.time().isoformat('seconds'):>12}{v:>6.0f}{gap:>7.0f}{area_at(t):>6.0f}{flag}")
    prev=t

act=[s for t,s in ser("sensor.alfred_active_cleaning_target") if s not in("unavailable","unknown","")]
vac=[(t,s) for t,s in ser("vacuum.alfred")]
print(f"\nmax gap between ticks: {maxgap:.0f}s   (a real inter-room plateau would be 60-120s)")
print(f"active_cleaning_target: {act[0]!r}  -> {len(act[0].split(','))} rooms")
print("vacuum states:", [(t.time().isoformat('seconds'),s) for t,s in vac])
