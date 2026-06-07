"""Cross-check the 2026-06-06 INTERNAL run (queue: Hallway, Kitchen) against its
finalized job JSON, and test the core Phase-1 assumption:

  does sensor.alfred_cleaning_time RESET per room, or is it job-cumulative and
  only PLATEAU between rooms?

The shipped Phase-1 segmenter splits on RESET (value drops). If this run is
cumulative-with-plateau, that segmenter yields ONE segment (transit_capture_valid
would be False) and the user's "plateau" hypothesis is the correct signal.
"""
import csv
import datetime as dt

CSV = r"C:\Users\CKing\Downloads\history (1).csv"
GAP_THRESH = 75  # s; active cleaning increments land ~30s apart, >> that = not cleaning


def parse_ts(s: str) -> dt.datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1]
    return dt.datetime.fromisoformat(s)


rows = []
with open(CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append((r["entity_id"], r["state"], parse_ts(r["last_changed"])))


def num_series(ent: str):
    out = []
    for e, s, t in rows:
        if e == ent and s not in ("unknown", "unavailable", ""):
            try:
                out.append((t, float(s)))
            except ValueError:
                pass
    return sorted(out, key=lambda p: p[0])


def from_job_start(series):
    """Drop the stale pre-job sample; start at the job-start reset to 0."""
    for i in range(1, len(series)):
        if series[i][1] == 0 and series[i - 1][1] > 0:
            return series[i:]
    return series


for ent in ("sensor.alfred_cleaning_time", "sensor.alfred_cleaning_area"):
    s = from_job_start(num_series(ent))
    print(f"\n=== {ent}  (from job-start reset) ===")
    resets = big_gaps = 0
    prev = None
    seg_bounds = []
    for t, v in s:
        gap = (t - prev[0]).total_seconds() if prev else 0.0
        flag = ""
        if prev and v < prev[1]:
            flag = "  <-- RESET (value drop)"
            resets += 1
        elif prev and gap > GAP_THRESH:
            flag = f"  <-- PLATEAU GAP {gap:.0f}s"
            big_gaps += 1
            seg_bounds.append(prev[0])
        print(f"   {t.strftime('%H:%M:%S')}  {v:6.0f}   +{gap:6.0f}s{flag}")
        prev = (t, v)
    print(f"  RESETS (value drops) after job start: {resets}")
    print(f"  PLATEAU gaps (>{GAP_THRESH}s):           {big_gaps}")

    # Gap-segmentation: split where the increment gap exceeds the cadence.
    segs, cur = [], []
    prev = None
    for t, v in s:
        if prev and (t - prev[0]).total_seconds() > GAP_THRESH:
            segs.append(cur)
            cur = []
        cur.append((t, v))
        prev = (t, v)
    if cur:
        segs.append(cur)
    print(f"  -> gap-segmentation yields {len(segs)} segment(s):")
    for i, seg in enumerate(segs):
        v0, v1 = seg[0][1], seg[-1][1]
        print(f"     seg{i}: {seg[0][0].strftime('%H:%M:%S')}-{seg[-1][0].strftime('%H:%M:%S')}"
              f"  value {v0:.0f}->{v1:.0f}  (delta {v1 - v0:.0f})")


# Where was the robot during the gap? (within-session frame is stable; drift is cross-session)
print("\n=== task_status + dock during the inter-segment gap (22:01-22:07) ===")
for e, s, t in rows:
    if e in ("sensor.alfred_task_status", "vacuum.alfred", "sensor.alfred_dock_status"):
        if dt.datetime(2026, 6, 6, 22, 1, 30) <= t <= dt.datetime(2026, 6, 6, 22, 7, 0):
            print(f"   {t.strftime('%H:%M:%S')}  {e.split('.')[-1]:24} {s}")

print("\n=== within-session position by phase (y_raw) ===")
ys = num_series("sensor.alfred_robot_position_y_raw")
for label, a, b in (("Hallway clean 21:58-22:01", (21, 58), (22, 2)),
                    ("Kitchen clean 22:05-22:08", (22, 5), (22, 8))):
    pts = [v for t, v in ys if dt.datetime(2026, 6, 6, *a) <= t <= dt.datetime(2026, 6, 6, *b)]
    if pts:
        print(f"   {label}: y range [{min(pts):.0f}..{max(pts):.0f}]  (n={len(pts)})")
