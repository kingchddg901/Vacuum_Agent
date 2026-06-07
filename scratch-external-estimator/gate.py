"""Validate the 'actual area vs expected room size' learning gate.

Per-room counter-derived area should converge to the room's true size. A clean that
comes in well UNDER expected = a partial/interrupted clean whose TIME would poison the
room's timing baseline if learned. The gate: learn timing only when area is in-band.

Here: per-room area stability from the archive, and a leave-one-out flag of jobs whose
area falls outside the room's learned band (= would be gated out of learning).
"""
import json, glob, statistics as st
from collections import defaultdict

NAMES={1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}

areas=defaultdict(list); times=defaultdict(list)
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    j=d.get("job",{})
    if j.get("room_count")!=1: continue
    q=d.get("queue",{}); rids=q.get("queue_room_ids") or [r.get("room_id") for r in d.get("resolved_rooms",[])]
    if not rids or j.get("cleaning_area_m2") is None: continue
    rid=rids[0]; areas[rid].append(float(j["cleaning_area_m2"]))
    if j.get("cleaning_time_seconds"): times[rid].append(float(j["cleaning_time_seconds"]))

TOL=1.5
print(f"{'room':<16}{'n':>3}{'area mean':>10}{'[min..max]':>12}{'stddev':>8}{'flagged(partial?)':>18}")
total=flagged_total=0
for rid in sorted(areas,key=lambda r:-st.mean(areas[r])):
    a=areas[rid]; med=st.median(a); sd=st.pstdev(a) if len(a)>1 else 0.0
    flagged=[x for x in a if abs(x-med)>TOL]
    total+=len(a); flagged_total+=len(flagged)
    print(f"{NAMES.get(rid,rid):<16}{len(a):>3}{st.mean(a):>10.1f}{('['+format(min(a),'.0f')+'..'+format(max(a),'.0f')+']'):>12}{sd:>8.1f}{f'{len(flagged)}/{len(a)}':>18}")

print(f"\noverall: {flagged_total}/{total} single-room cleans would be flagged as out-of-area-band ({100*flagged_total/total:.0f}%)")
print("-> those are exactly the cleans whose TIME should NOT feed the room's timing baseline.")

# Does area-gating tighten the timing band? (well-sampled rooms only)
print("\ntiming-band tightening from the area gate (rooms with n>=6):")
for rid in sorted(areas):
    a=areas[rid]; t=times.get(rid,[])
    if len(t)<6: continue
    med=st.median(a)
    keep=[t[i] for i in range(len(t)) if i<len(a) and abs(a[i]-med)<=TOL]
    if len(keep)<2: continue
    print(f"   {NAMES.get(rid,rid):<14} time stddev: all={st.pstdev(t):.0f}s (n{len(t)})  ->  area-gated={st.pstdev(keep):.0f}s (n{len(keep)})")
