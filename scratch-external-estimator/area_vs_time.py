"""cleaning_area corroborates cleaning_time: both reset at room boundaries and
plateau during wash/transit. cleaning_area is coarser (1 m2/step) so it's a worse
fine-gate but it (a) cross-checks the segment boundaries and (b) gives each
segment's ROOM AREA directly."""
import csv, datetime as dt

PATH = r"C:\Users\CKing\Downloads\multi room run.csv"

def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"): s = s[:-1]
    return dt.datetime.fromisoformat(s)

rows = []
with open(PATH, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append((r["entity_id"], r["state"], parse_ts(r["last_changed"])))

def series(ent):
    return sorted([(t, float(s)) for e, s, t in rows if e == ent], key=lambda p: p[0])

def segs(s):
    out, cur, prev = [], [], None
    for t, v in s:
        if prev is not None and v < prev:   # reset
            out.append(cur); cur = []
        cur.append((t, v)); prev = v
    if cur:
        out.append(cur)
    return out

for name, ent in (("cleaning_time", "sensor.alfred_cleaning_time"),
                  ("cleaning_area", "sensor.alfred_cleaning_area")):
    print(f"=== {name} segments (split on reset) ===")
    for i, seg in enumerate(segs(series(ent))):
        peak = max(v for _, v in seg)
        # largest internal gap (plateau) in seconds
        gaps = [(seg[j+1][0] - seg[j][0]).total_seconds() for j in range(len(seg)-1) if seg[j+1][1] > seg[j][1]]
        biggest = max(gaps) if gaps else 0
        print(f"  seg{i}: {seg[0][0].strftime('%H:%M')}-{seg[-1][0].strftime('%H:%M')}  "
              f"peak={peak:.0f}  events={len(seg):<3} biggest plateau={biggest:.0f}s")

# reset timestamps alignment
def resets(s):
    return [t.strftime('%H:%M:%S') for (t0, v0), (t, v) in zip(s, s[1:]) if v < v0]
print("\nreset timestamps:")
print("  cleaning_time:", resets(series("sensor.alfred_cleaning_time")))
print("  cleaning_area:", resets(series("sensor.alfred_cleaning_area")))
