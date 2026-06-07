"""v5: match within a VARIANCE BAND (learning-jobs only), not a point mean.
For each area-gated candidate, show its no-edge time band for the config pass-count,
and whether the observed 540s actually falls inside it."""
import json, glob, statistics as st
from collections import defaultdict

NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}
SLUGNAME = {v.lower().replace(" ","_").replace("'",""): v for v in NAMES.values()}
EXT_AREA, EXT_TIME, AREA_GATE = 4.0, 540.0, 1.5

def stddev(xs):
    n=len(xs)
    if n<2: return 0.0
    m=sum(xs)/n
    return (sum((x-m)**2 for x in xs)/n)**0.5

area=defaultdict(list); carpet=defaultdict(list)
buckets=defaultdict(lambda: defaultdict(list))   # slug->(passes,edge)->[tsec]
for p in glob.glob(r"Z:\eufy_vacuum\learning\alfred\jobs\*.json"):
    try: d=json.load(open(p,encoding="utf-8"))
    except Exception: continue
    if d.get("outcome",{}).get("used_for_learning") is not True: continue   # learning-only
    rooms=(d.get("job_profile",{}) or {}).get("rooms",[]) or []
    if len(rooms)!=1: continue
    r=rooms[0]; slug=str(r.get("slug","")).strip().lower()
    if not slug: continue
    j=d.get("job",{}); passes=int(r.get("clean_passes",r.get("clean_times",1)) or 1); edge=bool(r.get("edge_mopping",False))
    carpet[slug].append(bool(r.get("is_carpet",r.get("carpet",False))))
    if j.get("cleaning_area_m2") is not None: area[slug].append(float(j["cleaning_area_m2"]))
    if j.get("cleaning_time_seconds") is not None: buckets[slug][(passes,edge)].append(float(j["cleaning_time_seconds"]))

sj=json.load(open(r"Z:\.storage\eufy_vacuum.storage",encoding="utf-8"))
cfg={}
for rid,rm in sj["data"]["maps"]["vacuum.alfred"]["6"]["rooms"].items():
    slug=str(rm.get("name","")).lower().replace(" ","_").replace("'","")
    cfg[slug]=(int(rm.get("clean_passes",1) or 1), bool(rm.get("edge_mopping",False)), str(rm.get("floor_type","")), str(rm.get("clean_mode","")))

print(f"EXTERNAL JOB  area={EXT_AREA:.0f} m2  time={EXT_TIME:.0f}s  (mop confirmed; learning-jobs-only profiles)\n")
cands=[]
for slug,a in area.items():
    avg_a=st.mean(a); ad=abs(avg_a-EXT_AREA)
    passes,edge,floor,mode=cfg.get(slug,(1,False,"?","?"))
    if "carpet" in floor or "mop" not in mode.lower() or ad>AREA_GATE: continue
    cands.append((slug,avg_a,ad,passes,edge))

for slug,avg_a,ad,cpass,cedge in sorted(cands,key=lambda x:x[2]):
    print(f"{SLUGNAME.get(slug,slug)}  area={avg_a:.1f} (aD {ad:.1f})  config={cpass}p/{'edge' if cedge else 'no-edge'}")
    for (passes,edge),ts in sorted(buckets[slug].items()):
        m=sum(ts)/len(ts); mn=min(ts); mx=max(ts); sd=stddev(ts)
        in_range = mn<=EXT_TIME<=mx
        in_sd = (m-sd)<=EXT_TIME<=(m+sd)
        star = " <-config" if (passes==cpass and edge==cedge) else ""
        verdict = "540 IN range" if in_range else ("540 in mean+/-sd" if in_sd else f"540 OUT (band max {mx:.0f})")
        print(f"    {passes}p {'edge   ' if edge else 'no-edge'}  mean {m:5.0f}  [{mn:.0f}..{mx:.0f}]  +/-{sd:.0f}  n{len(ts):<2}  {verdict}{star}")
    print()
