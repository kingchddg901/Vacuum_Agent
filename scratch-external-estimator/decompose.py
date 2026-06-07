"""Check the user's decomposition:  transit = floor_time - cleaning_time - dock_time.

floor_time = first dock-departure -> final re-dock (whole active period)
cleaning_time = device in-room counter (transit-free)
dock_time = time spent DOCKED within the floor window (mop-prep toggles / mid-job)
=> transit = floor - cleaning - dock   (all non-cleaning, non-docked time = movement)

Also split transit into out-leg / return-leg / prep-wander so we can see how much of
it is productive dock<->room travel vs mop-prep wandering.
"""
import csv, datetime as dt

RUNS=[("Run1 Kitchen d1",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run1-history.csv"),
      ("Run2 Kitchen d1",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run2-history.csv"),
      ("Run3 Hallway d2",r"C:\Users\CKing\Documents\GITHUB\eufy-vacuum-manager\scratch-external-estimator\run3-hallway.csv")]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)
def load(p):
    with open(p,newline="",encoding="utf-8") as f:
        return [(r["entity_id"],r["state"],parse_ts(r["last_changed"])) for r in csv.DictReader(f)]

def vstates(rows):
    return sorted([(t,s) for e,s,t in rows if e=="vacuum.alfred"],key=lambda p:p[0])
def docked_intervals(rows):
    seq=vstates(rows);out=[];start=None
    for t,s in seq:
        if s=="docked" and start is None: start=t
        elif s!="docked" and start is not None: out.append((start,t));start=None
    if start is not None: out.append((start,seq[-1][0]))
    return out

for label,path in RUNS:
    rows=load(path); seq=vstates(rows)
    clean_tx=[t for t,s in seq if s=="cleaning"]
    ret=[t for t,s in seq if s=="returning"]; ret_t=min(ret) if ret else None
    docked=[t for t,s in seq if s=="docked"]
    first_leave=min(clean_tx)
    final_dock=min([t for t in docked if ret_t and t>=ret_t]) if ret_t else max(docked)
    # in-room counter
    ct=sorted([(t,float(s)) for e,s,t in rows if e=="sensor.alfred_cleaning_time" and s not in("unknown","unavailable","")],key=lambda p:p[0])
    zeros=[t for t,v in ct if v==0]; reset=max(zeros) if zeros else ct[0][0]
    pos=[(t,v) for t,v in ct if v>0 and t>reset]
    first_tick_t,first_tick_v=pos[0]; last_tick_t,last_tick_v=pos[-1]
    in_clean_start=first_tick_t-dt.timedelta(seconds=first_tick_v)
    cleaning_counter=last_tick_v
    cleaning_measured=(ret_t-in_clean_start).total_seconds() if ret_t else None

    floor=(final_dock-first_leave).total_seconds()
    dock_time=sum((min(b,final_dock)-max(a,first_leave)).total_seconds()
                  for a,b in docked_intervals(rows) if b>first_leave and a<final_dock)
    transit=floor-cleaning_counter-dock_time

    last_exit_before_clean=max(t for t in clean_tx if t<=in_clean_start)
    out_leg=(in_clean_start-last_exit_before_clean).total_seconds()
    return_leg=(final_dock-ret_t).total_seconds() if ret_t else None
    prep_wander=transit-out_leg-(return_leg or 0)

    print(f"== {label} ==")
    print(f"   floor={floor:.0f}s  cleaning(counter)={cleaning_counter:.0f}s (measured {cleaning_measured:.0f}s)  dock={dock_time:.0f}s")
    print(f"   => TRANSIT = floor - cleaning - dock = {transit:.0f}s")
    print(f"      breakdown: out-leg={out_leg:.0f}s + return-leg={return_leg:.0f}s + prep-wander={prep_wander:.0f}s")
    print()
