"""Tuned attributor: joint (area, travel) nearest-neighbor instead of a hard area gate
(the hard gate missed 18% on coarse/variable area). Travel = PHYSICAL distance signal
(straight-shot geometry, not access-graph depth), calibrated per room from the archive.

Compares feature sets and reports top-1/2/3 recall (top-k = "shortlist of k contains
the true room", which is what a flag-for-review feature actually needs). carpet rooms
excluded when the job mopped (hard, reliable constraint).
"""
import json, glob, statistics as st
from collections import defaultdict

NAMES={1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
CARPET={1,3}

jobs=[]
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    j=d.get("job",{})
    if j.get("room_count")!=1: continue
    q=d.get("queue",{}); rids=q.get("queue_room_ids") or [r.get("room_id") for r in d.get("resolved_rooms",[])]
    if not rids: continue
    area=j.get("cleaning_area_m2"); dur=j.get("duration_minutes") or j.get("wall_clock_duration_minutes")
    rcm=j.get("room_cleaning_minutes"); ret=j.get("return_to_dock_minutes")
    if area is None or dur is None or rcm is None: continue
    mopped=any("mop" in str(r.get("clean_mode","")).lower() for r in d.get("resolved_rooms",[]))
    jobs.append(dict(rid=rids[0],area=float(area),travel=float(dur-rcm),ret=(float(ret) if ret is not None else None),mopped=mopped))

# global feature scales (std) for normalization
A_SD=st.pstdev([j["area"] for j in jobs]) or 1.0
T_SD=st.pstdev([j["travel"] for j in jobs]) or 1.0
R_SD=st.pstdev([j["ret"] for j in jobs if j["ret"] is not None]) or 1.0

def centroids(exclude_idx):
    by=defaultdict(list)
    for i,jb in enumerate(jobs):
        if i!=exclude_idx: by[jb["rid"]].append(jb)
    out={}
    for rid,js in by.items():
        out[rid]=dict(area=st.mean(j["area"] for j in js),travel=st.mean(j["travel"] for j in js),
                      ret=st.mean([j["ret"] for j in js if j["ret"] is not None]) if any(j["ret"] is not None for j in js) else None)
    return out

def rank(jb,cent,feats):
    cand=[]
    for rid,c in cent.items():
        if jb["mopped"] and rid in CARPET: continue
        d=0.0
        if "area" in feats: d+=((c["area"]-jb["area"])/A_SD)**2
        if "travel" in feats: d+=((c["travel"]-jb["travel"])/T_SD)**2
        if "ret" in feats:
            if c["ret"] is None or jb["ret"] is None: continue
            d+=((c["ret"]-jb["ret"])/R_SD)**2
        cand.append((d**0.5,rid))
    cand.sort()
    return [rid for _,rid in cand]

METHODS={"area only":("area",),"area+travel":("area","travel"),"area+return":("area","ret")}
print(f"jobs={len(jobs)}  (feature SDs: area={A_SD:.2f} travel={T_SD:.2f} return={R_SD:.2f})\n")
print(f"{'method':<14}{'top-1':>8}{'top-2':>8}{'top-3':>8}")
res={}
for mname,feats in METHODS.items():
    t1=t2=t3=n=0
    confus=defaultdict(int)
    for i,jb in enumerate(jobs):
        R=jb["rid"]; order=rank(jb,centroids(i),feats)
        if not order: continue
        n+=1
        if order[0]==R: t1+=1
        else: confus[(NAMES.get(R,R),NAMES.get(order[0],order[0]))]+=1
        if R in order[:2]: t2+=1
        if R in order[:3]: t3+=1
    res[mname]=(t1,t2,t3,n,confus)
    print(f"{mname:<14}{f'{t1}/{n}':>8}{f'{t2}/{n}':>8}{f'{t3}/{n}':>8}   ({100*t1/n:.0f}% / {100*t2/n:.0f}% / {100*t3/n:.0f}%)")

print("\ntop confusions for area+travel (true -> predicted):")
for (tr,pr),c in sorted(res["area+travel"][4].items(),key=lambda kv:-kv[1])[:6]:
    print(f"   {tr:<16} -> {pr:<16} x{c}")
