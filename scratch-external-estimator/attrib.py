import csv, json, datetime as dt, math

BOUNDS = json.load(open(r"Z:\eufy_vacuum\mapping\alfred\map_6.json"))
NAMES = {1:"Heidi and Chris",2:"Bathroom",3:"Bryan",4:"Hallway",5:"Kitchen",
         6:"Entryway",7:"Living Room",8:"Dining Room",9:"Office",11:"Cat Room"}

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    if "+" in s: s = s.split("+")[0]
    return dt.datetime.fromisoformat(s)

rows=[]
with open(r"C:\Users\CKing\Downloads\history.csv", newline="") as f:
    for row in csv.DictReader(f):
        rows.append((row["entity_id"], row["state"], parse_ts(row["last_changed"])))

def series(ent):
    out=[(t,float(s)) for (e,s,t) in rows if e==ent and s not in ("unknown","unavailable","")]
    return sorted(out, key=lambda p:p[0])

xs=series("sensor.alfred_robot_position_x_raw")
ys=series("sensor.alfred_robot_position_y_raw")
events=sorted([(t,'x',v) for t,v in xs]+[(t,'y',v) for t,v in ys], key=lambda e:e[0])
curx=cury=None; pts=[]
for t,k,v in events:
    if k=='x': curx=v
    else: cury=v
    if curx is not None and cury is not None: pts.append((t,curx,cury))

WS=parse_ts("2026-06-06T17:41:53.688"); WE=parse_ts("2026-06-06T17:52:13.212")
clean=[(t,x,y) for (t,x,y) in pts if WS<=t<=WE]
xsv=[x for _,x,_ in clean]; ysv=[y for _,_,y in clean]
tcx=sum(xsv)/len(xsv); tcy=sum(ysv)/len(ysv)

print(f"=== EXTERNAL JOB TRAIL (clean window 17:41:53-17:52:13) ===")
print(f"points: {len(clean)}")
print(f"x: {min(xsv):.0f}..{max(xsv):.0f}   y: {min(ysv):.0f}..{max(ysv):.0f}")
print(f"centroid: ({tcx:.0f}, {tcy:.0f})")

def inside(x,y,b,m=0.0):
    return b["min_x"]-m<=x<=b["max_x"]+m and b["min_y"]-m<=y<=b["max_y"]+m

# overlap diagnostic: how many rooms' AGGREGATE bounds contain each point
rooms=BOUNDS["rooms"]
def agg(rid): return rooms[rid]["bounds"]
contain_counts=[]
for _,x,y in clean:
    c=sum(1 for rid in rooms if inside(x,y,agg(rid)))
    contain_counts.append(c)
print(f"\n=== OVERLAP DIAGNOSTIC (aggregate bounds) ===")
print(f"avg # rooms whose aggregate box contains a trail point: {sum(contain_counts)/len(contain_counts):.1f} of {len(rooms)}")
print("(high = aggregate boxes overlap too much to attribute)")

def best_run(rid):
    best=(-1,None,0)
    for h in rooms[rid].get("job_bounds_history",[]):
        if h.get("excluded"): continue
        cnt=sum(1 for _,x,y in clean if inside(x,y,h))
        pct=100*cnt/len(clean)
        if pct>best[0]: best=(pct,h.get("recorded_at","?")[:10],h.get("sample_count",0))
    return best

print(f"\n=== PER-ROOM ATTRIBUTION ===")
print(f"{'room':<18}{'agg%':>6}{'cdist':>8}{'bestrun%':>10}  best-run(date, n)")
res=[]
for rid in rooms:
    b=agg(rid); name=NAMES.get(int(rid),rid)
    cnt=sum(1 for _,x,y in clean if inside(x,y,b)); pct=100*cnt/len(clean)
    cd=math.hypot(tcx-b["cx"], tcy-b["cy"])
    bp,bdate,bn=best_run(rid)
    res.append((name,pct,cd,bp,bdate,bn,rooms[rid]["bounds"].get("run_count",0)))
# sort by best-run containment desc, then centroid dist asc
for name,pct,cd,bp,bdate,bn,rc in sorted(res,key=lambda r:(-r[3],r[2])):
    print(f"{name:<18}{pct:>5.0f}%{cd:>8.0f}{bp:>9.0f}%  {bdate} n={bn}")

print(f"\n=== aggregate bounds (showing the overlap) ===")
for rid in rooms:
    b=agg(rid)
    print(f"{NAMES.get(int(rid),rid):<18} x[{b['min_x']:.0f}..{b['max_x']:.0f}] y[{b['min_y']:.0f}..{b['max_y']:.0f}] runs={b.get('run_count',0)}")
