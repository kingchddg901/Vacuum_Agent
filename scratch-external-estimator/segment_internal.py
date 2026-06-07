"""Validate counter-plateau segmentation on an INTERNAL multi-room job, against the
device's own ground truth (active_cleaning_target queue) + the area gate.

Segment blind from the counters (reset = job start; gap >90s between cleaning_time
increments = room boundary), read per-segment (area d, time d), then map to the queue
order and check each segment's area against the room's learned expected size.
"""
import csv, datetime as dt, glob, json, statistics as st
from collections import defaultdict

PATH=r"C:\Users\CKing\Downloads\history (1).csv"
GAP=90  # seconds between cleaning_time increments that counts as a plateau/boundary

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
rows=[]
with open(PATH,newline="",encoding="utf-8") as f:
    for r in csv.DictReader(f): rows.append((r["entity_id"],r["state"],parse_ts(r["last_changed"])))

def ser(ent):
    return sorted([(t,s) for e,s,t in rows if e==ent],key=lambda p:p[0])
ct=[(t,float(s)) for t,s in ser("sensor.alfred_cleaning_time") if s not in ("unknown","unavailable","")]
ca=[(t,float(s)) for t,s in ser("sensor.alfred_cleaning_area") if s not in ("unknown","unavailable","")]
act=[(t,s) for t,s in ser("sensor.alfred_active_cleaning_target") if s not in ("unavailable","unknown","")]

# job window: from the last reset (cleaning_time -> 0)
reset_t=max(t for t,v in ct if v==0)
inc=[(t,v) for t,v in ct if v>0 and t>reset_t]          # post-reset increments
def area_at(t):  # step lookup
    vals=[v for tt,v in ca if tt<=t and tt>=reset_t]
    return vals[-1] if vals else 0.0

# split increments into segments on >GAP gaps
segs=[]; cur=[inc[0]]
for prev,nxt in zip(inc,inc[1:]):
    if (nxt[0]-prev[0]).total_seconds()>GAP:
        segs.append(cur); cur=[nxt]
    else: cur.append(nxt)
segs.append(cur)

print(f"job reset at {reset_t.time().isoformat('seconds')}  ->  {len(segs)} segment(s) found (plateau gap > {GAP}s)\n")
prev_time=0.0; prev_area=0.0; seg_rows=[]
for i,sg in enumerate(segs,1):
    end_t=sg[-1][0]; end_time=sg[-1][1]; end_area=area_at(end_t)
    d_time=end_time-prev_time; d_area=end_area-prev_area
    print(f"  segment {i}: {sg[0][0].time().isoformat('seconds')}-{end_t.time().isoformat('seconds')}   "
          f"time d={d_time:.0f}s   area d={d_area:.0f} m2")
    seg_rows.append((d_area,d_time)); prev_time=end_time; prev_area=end_area

# ground truth
queue=[r.strip() for r in act[0][1].split(",")] if act else []
print(f"\nGROUND TRUTH active_cleaning_target = {act[0][1]!r}  ->  queue {queue}")
print(f"check: segments={len(segs)} vs rooms={len(queue)}   area-sum={sum(a for a,_ in seg_rows):.0f}  time-sum={sum(t for _,t in seg_rows):.0f}")

# expected room areas from the archive
areas=defaultdict(list)
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    j=d.get("job",{})
    if j.get("room_count")!=1: continue
    q=d.get("queue",{}); rids=q.get("queue_room_ids") or []
    nm=(d.get("queue",{}).get("queue_rooms") or [{}])[0].get("name")
    if rids and j.get("cleaning_area_m2") is not None and nm: areas[nm].append(float(j["cleaning_area_m2"]))
exp={k:st.mean(v) for k,v in areas.items()}

print("\nmap segment K -> queue room K, gate each on expected size:")
for i,(room) in enumerate(queue):
    if i>=len(seg_rows): break
    a,t=seg_rows[i]; e=exp.get(room)
    verdict="(no baseline)" if e is None else ("IN-NORMS OK learn" if abs(a-e)<=1.5 else f"FLAG X under/over expected ({a:.0f} vs ~{e:.1f})")
    print(f"  {room:<10} area d={a:.0f} m2 (expected ~{e if e else '?'})  time d={t:.0f}s   -> {verdict}")
