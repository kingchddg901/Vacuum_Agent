"""Compare two external-run CSVs. Trail windows:
  - state : vacuum.alfred == 'cleaning' (starts at dock -> includes transit)
  - ctime : sensor.alfred_cleaning_time ticking (robot in room -> transit excluded)
Plus a dock-normalized variant: subtract each run's docked-baseline position to
cancel per-session SLAM frame drift (the dock is physically fixed, so its raw
coords moving run-to-run = drift). Tests whether geometry agrees once normalized.
"""
import csv, datetime as dt, statistics as st

RUNS = [
    ("Run1", r"C:\Users\CKing\Downloads\history.csv"),
    ("Run2", r"C:\Users\CKing\Downloads\same room 2nd run.csv"),
]

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    if "+" in s: s = s.split("+")[0]
    return dt.datetime.fromisoformat(s)

def pctl(vals, p):
    v = sorted(vals); k = (len(v) - 1) * p; f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)

def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [(r["entity_id"], r["state"], parse_ts(r["last_changed"])) for r in csv.DictReader(f)]

def series(rows, ent):
    return sorted([(t, float(s)) for e, s, t in rows if e == ent and s not in ("unknown", "unavailable", "")], key=lambda p: p[0])

def window_ctime(rows):
    ct = series(rows, "sensor.alfred_cleaning_time")
    zeros = [t for t, v in ct if v == 0]
    reset = max(zeros) if zeros else ct[0][0]
    pos = [t for t, v in ct if v > 0 and t > reset]
    return min(pos), max(t for t, _ in ct)

def trail(rows, ws, we, dock=(0.0, 0.0)):
    xs, ys = series(rows, "sensor.alfred_robot_position_x_raw"), series(rows, "sensor.alfred_robot_position_y_raw")
    ev = sorted([(t, "x", v) for t, v in xs] + [(t, "y", v) for t, v in ys], key=lambda e: e[0])
    cx = cy = None; pts = []
    for t, k, v in ev:
        if k == "x": cx = v
        else: cy = v
        if cx is not None and cy is not None and ws <= t <= we:
            pts.append((cx - dock[0], cy - dock[1]))
    return pts

def fp(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return dict(n=len(pts), cx=st.mean(xs), cy=st.mean(ys),
                box=(pctl(xs, .10), pctl(xs, .90), pctl(ys, .10), pctl(ys, .90)))

def iou(a, b):
    ax0, ax1, ay0, ay1 = a; bx0, bx1, by0, by1 = b
    ix = max(0, min(ax1, bx1) - max(ax0, bx0)); iy = max(0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy; ua = (ax1 - ax0) * (ay1 - ay0); ub = (bx1 - bx0) * (by1 - by0)
    return inter / (ua + ub - inter) if (ua + ub - inter) > 0 else 0.0

raw, norm = {}, {}
for label, path in RUNS:
    rows = load_rows(path)
    ws, we = window_ctime(rows)
    dock = (series(rows, "sensor.alfred_robot_position_x_raw")[0][1],
            series(rows, "sensor.alfred_robot_position_y_raw")[0][1])
    raw[label] = fp(trail(rows, ws, we))
    norm[label] = fp(trail(rows, ws, we, dock))
    print(f"{label}: dock=({dock[0]:.0f},{dock[1]:.0f})  ctime n={raw[label]['n']}  "
          f"centroid=({raw[label]['cx']:.0f},{raw[label]['cy']:.0f})")

print("\n=== cross-run agreement (ctime window) ===")
for name, d in (("raw coords     ", raw), ("dock-normalized", norm)):
    a, b = d["Run1"], d["Run2"]
    cd = ((a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2) ** 0.5
    print(f"  {name}: centroid dist {cd:5.0f}   trimmed-bbox IoU {iou(a['box'], b['box']):.2f}")
