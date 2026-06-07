"""Multi-room segmentation from cleaning_time alone:
  - RESET (value drops) => new room segment.
  - RISING (+~30 in <=THRESH s) => actively cleaning -> collect position samples.
  - PLATEAU (held >> 30s) or reset gap => not cleaning (transit / mop wash) -> skip.
Proves per-room sample sets fall out clean, transit + wash stripped, no dock leak.
"""
import csv, datetime as dt, statistics as st
from collections import defaultdict

PATH = r"C:\Users\CKing\Downloads\multi room run.csv"
THRESH = 75   # s; cleaning increments are 30-41s, plateaus/transit are >=130s

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    return dt.datetime.fromisoformat(s)

rows = []
with open(PATH, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append((r["entity_id"], r["state"], parse_ts(r["last_changed"])))

def series(ent):
    return sorted([(t, float(s)) for e, s, t in rows if e == ent and s not in ("unknown", "unavailable", "")], key=lambda p: p[0])

ct = series("sensor.alfred_cleaning_time")
xs, ys = series("sensor.alfred_robot_position_x_raw"), series("sensor.alfred_robot_position_y_raw")

# asof-merge positions
ev = sorted([(t, "x", v) for t, v in xs] + [(t, "y", v) for t, v in ys], key=lambda e: e[0])
cx = cy = None; pos = []
for t, k, v in ev:
    if k == "x": cx = v
    else: cy = v
    if cx is not None and cy is not None: pos.append((t, cx, cy))

# build active cleaning intervals tagged by segment id (segment increments on reset)
active = []   # (seg_id, t0, t1)
seg = 0
for (t0, v0), (t1, v1) in zip(ct, ct[1:]):
    if v1 < v0:                       # RESET -> next room
        seg += 1
        continue
    if v1 > v0 and (t1 - t0).total_seconds() <= THRESH:   # RISING & fast -> cleaning
        active.append((seg, t0, t1))
    # else: plateau -> skip (wash/transit), same segment

seg_samples = defaultdict(list)
for t, x, y in pos:
    for sid, a, b in active:
        if a <= t <= b:
            seg_samples[sid].append((x, y)); break

print(f"detected {len(set(s for s,_,_ in active))} room segment(s) from cleaning_time\n")
print(f"{'seg':>3}{'n':>5}{'centroid':>16}{'x range':>16}{'y range':>16}")
for sid in sorted(seg_samples):
    pts = seg_samples[sid]; px = [p[0] for p in pts]; py = [p[1] for p in pts]
    print(f"{sid:>3}{len(pts):>5}  ({st.mean(px):.0f},{st.mean(py):.0f})   "
          f"[{min(px):.0f}..{max(px):.0f}]  [{min(py):.0f}..{max(py):.0f}]")

# sanity: how many position samples were EXCLUDED (transit/wash/dock)?
kept = sum(len(v) for v in seg_samples.values())
print(f"\nkept {kept} of {len(pos)} position samples ({100*kept/len(pos):.0f}%); "
      f"{len(pos)-kept} excluded as transit/wash/dock")
# show the lowest-y kept sample per segment (proves no dock leak; dock is y~21-900)
for sid in sorted(seg_samples):
    miny = min(p[1] for p in seg_samples[sid])
    print(f"  seg {sid}: lowest kept y = {miny:.0f}")
