"""Calibrate the frame-invariant attributor (area + travel) from the job archive,
then leave-one-out test it.

Per single-room job:
  area          = cleaning_area_m2
  room_cleaning = room_cleaning_minutes (wall-clock in-room; the device cleaning_time
                  counter undercounts, so we don't use it)
  total_travel  = duration_minutes - room_cleaning_minutes   (out + return, dock-actions excl.)
  return_leg    = return_to_dock_minutes                      (clean prep-free leg)
Travel is frame-invariant (pure timing) and tracks distance/depth from the dock.

LOO: for each job, rebuild per-room baselines from the OTHER jobs, area-gate (+-1.5,
drop carpet if mopped), then attribute by nearest travel. Compare area-only vs
area+travel uniqueness, and tally correct / ambiguous / wrong / cold-start.
"""
import json, glob, statistics as st
from collections import defaultdict

NAMES={1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
CARPET={1,3}; AREA_GATE=1.5

# --- access-graph depth (BFS from the dock room = the node with no incoming edge) ---
ag=json.load(open(r"Z:\eufy_vacuum\learning\mapping\alfred\access_graph_6.json"))
children=defaultdict(list); incoming=set()
for n in ag["adjacency"]:
    for c in n.get("grants_access_to",[]):
        children[n["room_id"]].append(c["room_id"]); incoming.add(c["room_id"])
root=[n["room_id"] for n in ag["adjacency"] if n["room_id"] not in incoming]
depth={}; frontier=[(root[0],0)] if root else []
while frontier:
    r,d=frontier.pop(0)
    if r in depth: continue
    depth[r]=d
    for c in children.get(r,[]): frontier.append((c,d+1))

# --- load single-room jobs ---
jobs=[]
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    j=d.get("job",{})
    if j.get("room_count")!=1: continue
    q=d.get("queue",{}); rids=q.get("queue_room_ids") or [r.get("room_id") for r in d.get("resolved_rooms",[])]
    if not rids: continue
    rid=rids[0]
    area=j.get("cleaning_area_m2")
    dur=j.get("duration_minutes") or j.get("wall_clock_duration_minutes")
    rcm=j.get("room_cleaning_minutes")
    ret=j.get("return_to_dock_minutes")
    if area is None or dur is None or rcm is None: continue   # need the decomposed timing
    travel=dur-rcm
    mopped=any("mop" in str(r.get("clean_mode","")).lower() for r in d.get("resolved_rooms",[]))
    jobs.append(dict(rid=rid,area=float(area),travel=float(travel),ret=(float(ret) if ret is not None else None),
                     mopped=mopped,room_cleaning=float(rcm),dur=float(dur)))

print(f"single-room jobs with decomposed timing: {len(jobs)}")

def baselines(exclude_idx=None):
    by=defaultdict(list)
    for i,jb in enumerate(jobs):
        if i==exclude_idx: continue
        by[jb["rid"]].append(jb)
    out={}
    for rid,js in by.items():
        out[rid]=dict(n=len(js),area=st.mean(j["area"] for j in js),
                      travel=st.mean(j["travel"] for j in js),
                      ret=st.mean([j["ret"] for j in js if j["ret"] is not None]) if any(j["ret"] is not None for j in js) else None)
    return out

# --- per-room calibration table ---
base=baselines()
print(f"\n{'room':<16}{'depth':>6}{'n':>4}{'avg_area':>9}{'avg_travel(min)':>16}{'avg_return(min)':>16}")
for rid in sorted(base,key=lambda r:depth.get(r,9)):
    b=base[rid]
    print(f"{NAMES.get(rid,rid):<16}{depth.get(rid,'?'):>6}{b['n']:>4}{b['area']:>9.1f}{b['travel']:>16.2f}{(b['ret'] if b['ret'] is not None else float('nan')):>16.2f}")

# --- leave-one-out attribution ---
TRAVEL_TOL=0.75   # minutes; rooms within this travel of the job are travel-consistent
tally=defaultdict(int)
for i,jb in enumerate(jobs):
    R=jb["rid"]; b=baselines(exclude_idx=i)
    if R not in b: tally["cold_start(no baseline)"]+=1; continue
    short=[rid for rid,bb in b.items() if abs(bb["area"]-jb["area"])<=AREA_GATE and not (jb["mopped"] and rid in CARPET)]
    if R not in short: tally["area_gate_missed_true"]+=1; continue
    area_unique = (len(short)==1)
    # travel filter within shortlist
    tcons=[rid for rid in short if abs(b[rid]["travel"]-jb["travel"])<=TRAVEL_TOL]
    nearest=min(short,key=lambda rid:abs(b[rid]["travel"]-jb["travel"]))
    if area_unique:
        tally["unique_by_area_alone"]+=1
    elif len(tcons)==1 and tcons[0]==R:
        tally["travel_broke_tie_correct"]+=1
    elif nearest==R and len(tcons)>1:
        tally["nearest_correct_but_ambiguous"]+=1
    elif nearest==R:
        tally["nearest_correct"]+=1
    else:
        tally["WRONG"]+=1
print(f"\n=== leave-one-out (area gate +-{AREA_GATE} m2, travel tol {TRAVEL_TOL} min) ===")
total=sum(tally.values())
for k,v in sorted(tally.items(),key=lambda kv:-kv[1]):
    print(f"   {k:<32} {v:>3}  ({100*v/total:.0f}%)")
correct=tally['unique_by_area_alone']+tally['travel_broke_tie_correct']+tally['nearest_correct']+tally['nearest_correct_but_ambiguous']
print(f"   ---\n   landed on true room: {correct}/{total} ({100*correct/total:.0f}%)   WRONG: {tally['WRONG']}   cold-start: {tally['cold_start(no baseline)']}")
