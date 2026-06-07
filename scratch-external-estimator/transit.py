"""Frame-invariant signal test: does transit time (dock -> first in-room cleaning_time
tick) track a room's DEPTH in the access tree? Depth from access_graph_6.json, rooted
at the dock (Dining Room). cleaning_time is sampled every ~30s and equals elapsed
in-room seconds, so inferred in-room start = first_tick_time - first_tick_value.
"""
import csv, datetime as dt

RUNS=[("Run1 (Kitchen, depth1)",5,1,r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv"),
      ("Run2 (Kitchen, depth1)",5,1,r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv"),
      ("Run3 (Hallway, depth2)",4,2,r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv")]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load(path):
    with open(path,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]

for label,rid,depth,path in RUNS:
    rows=load(path)
    # first in-room tick (after reset to 0) -> infer in-room cleaning start
    ct=sorted([(t,float(s)) for e,s,t in rows if e=="sensor.alfred_cleaning_time" and s not in("unknown","unavailable","")],key=lambda p:p[0])
    zeros=[t for t,v in ct if v==0]; reset=max(zeros) if zeros else (ct[0][0] if ct else None)
    pos=[(t,v) for t,v in ct if v>0 and t>reset]
    first_t,first_v=pos[0]; inroom_start=first_t-dt.timedelta(seconds=first_v)
    # returning marks end of the run
    ret=[t for e,s,t in rows if e=="vacuum.alfred" and s=="returning"]
    ret_t=min(ret) if ret else None
    # robust departure = the LAST 'cleaning' transition before returning (ignores
    # the docked<->cleaning mop-prep toggles at the start)
    clean_tx=[t for e,s,t in rows if e=="vacuum.alfred" and s=="cleaning" and (ret_t is None or t<ret_t)]
    naive_leave=min(clean_tx); real_leave=max(t for t in clean_tx if t<=inroom_start) if any(t<=inroom_start for t in clean_tx) else min(clean_tx)
    transit=(inroom_start-real_leave).total_seconds()
    last_v=pos[-1][1]
    print(f"{label}")
    print(f"   dock toggles before run: {len(clean_tx)}   naive leave={naive_leave.time().isoformat('seconds')}  REAL leave={real_leave.time().isoformat('seconds')}")
    print(f"   in-room start={inroom_start.time().isoformat('seconds')}  ->  TRANSIT = {transit:.0f}s     (in-room time={last_v:.0f}s, returning {ret_t.time().isoformat('seconds') if ret_t else '?'})")
    print()
