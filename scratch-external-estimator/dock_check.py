"""The dock is physically fixed. Extract the robot's reported position while
docked/charging in every run. If it moves run-to-run, the raw coordinate frame
is drifting and cross-run geometry is dead."""
import csv, datetime as dt

RUNS = [
    ("Run1 17:00", r"C:\Users\CKing\Downloads\history.csv"),
    ("Run2 19:30", r"C:\Users\CKing\Downloads\same room 2nd run.csv"),
    ("Multi 19:45", r"C:\Users\CKing\Downloads\multi room run.csv"),
    ("Hallway 20:25", r"C:\Users\CKing\Downloads\hallway.csv"),
]

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    return dt.datetime.fromisoformat(s)

def series(rows, ent):
    return sorted([(t, v) for e, v, t in rows if e == ent], key=lambda p: p[0])

def numseries(rows, ent):
    return sorted([(t, float(v)) for e, v, t in rows if e == ent and v not in ("unknown", "unavailable", "")], key=lambda p: p[0])

print(f"{'run':<16}{'dock x':>9}{'dock y':>9}  (robot position while docked/charging)")
docks = []
for label, path in RUNS:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [(r["entity_id"], r["state"], parse_ts(r["last_changed"])) for r in csv.DictReader(f)]
    xs, ys = numseries(rows, "sensor.alfred_robot_position_x_raw"), numseries(rows, "sensor.alfred_robot_position_y_raw")
    charging = series(rows, "binary_sensor.alfred_charging")
    vac = series(rows, "vacuum.alfred")
    # pick a time the robot is on the dock: charging 'on', else vacuum 'docked'
    dock_t = None
    on = [t for t, s in charging if s == "on"]
    dk = [t for t, s in vac if s == "docked"]
    cand = sorted(on + dk)
    if cand:
        dock_t = cand[0]
    if dock_t is None:
        dock_t = xs[0][0]
    # nearest position samples to dock_t
    dx = min(xs, key=lambda p: abs((p[0] - dock_t).total_seconds()))[1]
    dy = min(ys, key=lambda p: abs((p[0] - dock_t).total_seconds()))[1]
    docks.append((dx, dy))
    print(f"{label:<16}{dx:>9.0f}{dy:>9.0f}")

xs_ = [d[0] for d in docks]; ys_ = [d[1] for d in docks]
print(f"\ndock x spread: {max(xs_)-min(xs_):.0f}   dock y spread: {max(ys_)-min(ys_):.0f}")
print("(the dock is fixed in the real world; this spread is pure coordinate-frame drift)")
