"""Pin down windows, then run my discriminator on BOTH runs in matched representations.

Three windows per run:
  wide  = [cleaning_time reset, last cleaning_time tick]  -> includes dock->room transit (matches my original n=75)
  ctime = [first positive tick, last tick]                -> in-room only (blind session's clean signal)
Report trail fingerprint for each, then run the discriminator (de-pollute 2x +
mass-centroid gate + width gate, rank by containment) for BOTH windows on BOTH runs.
"""
import csv, datetime as dt, statistics as st, json

NAMES={2:"Bathroom",5:"Kitchen",9:"Office",11:"Cat Room"}; CANDS=[5,11,2,9]; TRUTH=5
RUNS=[("Run1",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv"),
      ("Run2",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv")]
rooms=json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))["rooms"]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load_rows(path):
    with open(path,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]
def fseries(rows,ent):
    return sorted([(t,float(s)) for e,s,t in rows if e==ent and s not in ("unknown","unavailable","")],key=lambda p:p[0])
def trail(rows,ws,we):
    xs,ys=fseries(rows,"sensor.alfred_robot_position_x_raw"),fseries(rows,"sensor.alfred_robot_position_y_raw")
    ev=sorted([(t,"x",v) for t,v in xs]+[(t,"y",v) for t,v in ys],key=lambda e:e[0])
    cx=cy=None; pts=[]
    for t,k,v in ev:
        if k=="x": cx=v
        else: cy=v
        if cx is not None and cy is not None and ws<=t<=we: pts.append((cx,cy))
    return pts
def barea(h): return max(0.0,h["max_x"]-h["min_x"])*max(0.0,h["max_y"]-h["min_y"])
def contains(h,x,y): return h["min_x"]<=x<=h["max_x"] and h["min_y"]<=y<=h["max_y"]

def discriminate(pts,Kvals=(2.0,)):
    txs=[p[0] for p in pts]; tys=[p[1] for p in pts]
    TCX,TCY=st.mean(txs),st.mean(tys); WT=max(txs)-min(txs); HT=max(tys)-min(tys); AT=WT*HT
    def pin(h): return 100.0*sum(1 for x,y in pts if contains(h,x,y))/len(pts)
    out=[]
    for K in Kvals:
        res=[]
        for rid in CANDS:
            hist=[h for h in rooms[str(rid)].get("job_bounds_history",[]) if not h.get("excluded")]
            honest=[h for h in hist if barea(h)<=K*AT]
            gated=[h for h in honest if contains(h,TCX,TCY) and (WT==0 or 0.6*WT<=(h["max_x"]-h["min_x"])<=1.6*WT)]
            if not gated: res.append((rid,None)); continue
            best=max(gated,key=lambda h:pin(h)); res.append((rid,(pin(best),(best["max_x"]-best["min_x"])/WT if WT else 0)))
        ok=sorted([r for r in res if r[1]],key=lambda r:-r[1][0])
        win="NONE" if not ok else ("KITCHEN" if ok[0][0]==TRUTH else NAMES[ok[0][0]].upper())
        out.append((K,win,res))
    return out

for label,path in RUNS:
    rows=load_rows(path)
    ct=fseries(rows,"sensor.alfred_cleaning_time")
    zeros=[t for t,v in ct if v==0]; reset=max(zeros) if zeros else ct[0][0]
    pos=[t for t,v in ct if v>0 and t>reset]
    first_tick,last_tick=min(pos),max(pos)
    print(f"\n############ {label} ############")
    print(f"  ctime reset={reset.time()}  first_tick={first_tick.time()}  last_tick={last_tick.time()}  span(reset->last)={(last_tick-reset).total_seconds():.0f}s")
    for wname,(ws,we) in (("wide ",(reset,last_tick)),("ctime",(first_tick,last_tick))):
        pts=trail(rows,ws,we)
        if not pts: print(f"  [{wname}] no points"); continue
        txs=[p[0] for p in pts]; tys=[p[1] for p in pts]
        print(f"  [{wname}] n={len(pts)} bbox x[{min(txs):.0f}..{max(txs):.0f}] y[{min(tys):.0f}..{max(tys):.0f}] w={max(txs)-min(txs):.0f} h={max(tys)-min(tys):.0f} centroid=({st.mean(txs):.0f},{st.mean(tys):.0f})")
        for K,win,res in discriminate(pts):
            print(f"        discriminator(K={K}) -> {win}")
            for rid,v in sorted(res,key=lambda r:-((r[1][0]) if r[1] else -1)):
                tag=" <==TRUTH" if rid==TRUTH else ""
                print(f"           {NAMES[rid]:<12} "+("ELIM" if not v else f"cont={v[0]:4.0f}% wR={v[1]:.2f}")+tag)
