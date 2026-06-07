"""Per kitchen job: is the whole-map extent a few OUTLIER samples wrecking the raw
min/max AABB, or genuine spread? Compare raw bbox vs a robust (P10-P90 / IQR)
bbox, and surface the outlier samples."""
import json

F = r"Z:\eufy_vacuum\mapping\vacuum_alfred\raw_samples_room_5_kitchen.jsonl"

def pctl(v, p):
    v = sorted(v); k = (len(v) - 1) * p; f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)

jobs = []
with open(F, encoding="utf-8") as fh:
    for line in fh:
        d = json.loads(line)
        if "samples" in d and d["samples"]:
            jobs.append((d["job_id"], d["samples"]))

print(f"{'job_id':<22}{'n':>4}{'raw y-span':>12}{'robust y-span':>14}{'IQR y-outliers':>16}  extreme y (raw min/max)")
print("-" * 100)
for jid, s in jobs:
    ys = [p[1] for p in s]; xs = [p[0] for p in s]
    raw_span = max(ys) - min(ys)
    r_lo, r_hi = pctl(ys, .10), pctl(ys, .90)
    rob_span = r_hi - r_lo
    q1, q3 = pctl(ys, .25), pctl(ys, .75); iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outl = [y for y in ys if y < lo or y > hi]
    flag = "  <-- WHOLE-MAP" if raw_span > 6000 else ""
    print(f"{jid:<22}{len(s):>4}{raw_span:>12.0f}{rob_span:>14.0f}{len(outl):>16}  "
          f"[{min(ys):.0f} .. {max(ys):.0f}]{flag}")

# Drill into the worst whole-map job: show the outlier samples explicitly
worst = max(jobs, key=lambda kv: max(p[1] for p in kv[1]) - min(p[1] for p in kv[1]))
jid, s = worst
ys = [p[1] for p in s]
q1, q3 = pctl(ys, .25), pctl(ys, .75); iqr = q3 - q1
lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
print(f"\n=== worst job {jid}: {len(s)} samples ===")
print(f"IQR core y[{q1:.0f}..{q3:.0f}], fences [{lo:.0f}..{hi:.0f}]")
outl = sorted([p for p in s if p[1] < lo or p[1] > hi], key=lambda p: -p[1])
print(f"outlier samples ({len(outl)} of {len(s)} = {100*len(outl)/len(s):.0f}%):")
for x, y in outl:
    print(f"   ({x:.0f}, {y:.0f})")
