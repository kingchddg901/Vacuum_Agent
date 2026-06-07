import json, glob, statistics as st
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}

jobs=[]
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p, encoding="utf-8"))
    except Exception as e:
        continue
    j=d.get("job",{}); q=d.get("queue",{})
    rids=q.get("queue_room_ids") or [r.get("room_id") for r in d.get("resolved_rooms",[])]
    jobs.append(dict(id=d.get("job_id"), rids=rids,
        rc=j.get("room_count", len(rids) if rids else 0),
        area=j.get("cleaning_area_m2"), csec=j.get("cleaning_time_seconds"),
        dur=j.get("duration_minutes")))

area=defaultdict(list); tsec=defaultdict(list)
for jb in jobs:
    if jb["rc"]==1 and jb["rids"]:
        rid=jb["rids"][0]
        if jb["area"] is not None: area[rid].append(jb["area"])
        if jb["csec"] is not None: tsec[rid].append(jb["csec"])

single=sum(1 for j in jobs if j["rc"]==1)
print(f"total jobs: {len(jobs)}; single-room jobs: {single}; multi-room: {len(jobs)-single}")

rows=[]
for rid in area:
    a=area[rid]; ts=tsec[rid]
    rows.append((rid,len(a),st.mean(a),min(a),max(a),
                 (st.mean(ts) if ts else None)))

print("\n=== PER-ROOM PROFILE (single-room jobs only) ===")
print(f"{'room':<18}{'n':>4}{'area_m2 mean':>13}{'[min..max]':>12}{'clean_s mean':>14}")
for rid,n,am,amn,amx,tm in sorted(rows,key=lambda r:-r[2]):
    print(f"{NAMES.get(rid,rid):<18}{n:>4}{am:>13.1f}{('['+format(amn,'.0f')+'..'+format(amx,'.0f')+']'):>12}{(f'{tm:.0f}' if tm else '-'):>14}")

EXT_AREA=4.0; EXT_SEC=540.0
print(f"\n=== EXTERNAL JOB: area={EXT_AREA:.0f} m2, clean_time={EXT_SEC:.0f}s ===")
print("\n=== AREA-MATCH (primary) + time (secondary), ranked by |area delta| ===")
print(f"{'room':<18}{'mean_area':>10}{'area|d|':>8}{'mean_s':>8}{'time|d|s':>9}")
for rid,n,am,amn,amx,tm in sorted(rows,key=lambda r:abs(r[2]-EXT_AREA)):
    td = abs(tm-EXT_SEC) if tm else None
    print(f"{NAMES.get(rid,rid):<18}{am:>10.1f}{abs(am-EXT_AREA):>8.1f}{(f'{tm:.0f}' if tm else '-'):>8}{(f'{td:.0f}' if td is not None else '-'):>9}")
print("\n(area is recorded in coarse integer m2; rooms within ~1 m2 are size-ambiguous and need the time / centroid axes to separate)")
