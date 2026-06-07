"""Merged timeline of the multi-room run: show cleaning_time, cleaning_area, vacuum
state, task_status side by side in time order so the RESETS (job boundaries) and
PLATEAUS (counters hold while the robot leaves to wash / transit between rooms) are
visible. Mark reset (->0) and plateau-start (counter stops incrementing) events.
"""
import csv, datetime as dt

PATH=r"C:\Users\CKing\Downloads\multi room run.csv"
WANT=["sensor.alfred_cleaning_time","sensor.alfred_cleaning_area","vacuum.alfred","sensor.alfred_task_status"]

def parse_ts(s):
    s=s.strip()
    if s.endswith("Z"): s=s[:-1]
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s)

rows=[]
with open(PATH,newline="",encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["entity_id"] in WANT:
            rows.append((parse_ts(r["last_changed"]),r["entity_id"],r["state"]))
rows.sort(key=lambda x:x[0])

cur={k:"" for k in WANT}
SHORT={"sensor.alfred_cleaning_time":"time","sensor.alfred_cleaning_area":"area","vacuum.alfred":"vacuum","sensor.alfred_task_status":"task"}
print(f"{'clock':>12} | {'time':>5} {'area':>4} | {'vacuum':<10} | task")
prev_time=None
for t,e,s in rows:
    cur[e]=s
    ct=cur["sensor.alfred_cleaning_time"]; ca=cur["sensor.alfred_cleaning_area"]
    note=""
    if e=="sensor.alfred_cleaning_time":
        if s=="0": note=" <<< RESET (job boundary)"
        elif prev_time is not None and float(s)<float(prev_time): note=" <<< reset"
        prev_time=s
    if e=="vacuum.alfred" and s in ("returning",): note+="  (leaving room)"
    if e=="sensor.alfred_task_status" and s in ("Returning to Wash","Completed","Washing Mop"): note+=f"  <- {s}"
    print(f"{t.time().isoformat('seconds')!s:>12} | {ct:>5} {ca:>4} | {cur['vacuum.alfred']:<10} | {cur['sensor.alfred_task_status']:<18}{note}")
