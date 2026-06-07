"""Kitchen-attribution dig. Anchor each room by its TIGHTEST run (smallest robust
span = cleanest single-room proxy, avoids contamination dominating the center).
Then: which room is actually next to the dock, and where do the kitchen file's
samples really fall (nearest-anchor breakdown per job)?"""
import json, glob, os, statistics as st, math
from collections import Counter

DIR = r"Z:\eufy_vacuum\mapping\vacuum_alfred"
DOCK = (16461.0, 21.0)   # docked baseline (run-1 CSV)

def pctl(v, p):
    v = sorted(v); k = (len(v) - 1) * p; f = int(k); c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)

def robust_span(s):
    xs = [p[0] for p in s]; ys = [p[1] for p in s]
    return (pctl(xs, .9) - pctl(xs, .1)) + (pctl(ys, .9) - pctl(ys, .1))

rooms = {}   # name -> [(job_id, samples)]
for path in glob.glob(os.path.join(DIR, "raw_samples_room_*.jsonl")):
    jobs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("samples"):
                jobs.append((d["job_id"], d["room_name"], d["samples"]))
    if jobs:
        rooms[jobs[0][1]] = jobs

# anchor = median of the tightest run with >=20 samples
anchors = {}
for name, jobs in rooms.items():
    cand = [(robust_span(s), s) for _, _, s in jobs if len(s) >= 20] or [(robust_span(s), s) for _, _, s in jobs]
    s = min(cand)[1]
    anchors[name] = (st.median([p[0] for p in s]), st.median([p[1] for p in s]))

print("=== room anchors (tightest-run median), sorted by distance to dock ===")
for name in sorted(anchors, key=lambda n: math.hypot(anchors[n][0] - DOCK[0], anchors[n][1] - DOCK[1])):
    ax, ay = anchors[name]
    print(f"  {name:<18} anchor=({ax:6.0f},{ay:6.0f})  dock_dist={math.hypot(ax-DOCK[0], ay-DOCK[1]):.0f}")

def nearest(x, y):
    return min(anchors, key=lambda n: math.hypot(x - anchors[n][0], y - anchors[n][1]))

print("\n=== Kitchen file: where its samples actually fall (nearest anchor) ===")
for jid, name, samples in rooms["Kitchen"]:
    c = Counter(nearest(x, y) for x, y in samples)
    tot = sum(c.values())
    own = 100 * c.get("Kitchen", 0) / tot
    mix = ", ".join(f"{nm} {100*v/tot:.0f}%" for nm, v in c.most_common(4))
    flag = "  <-- mostly NOT kitchen" if own < 50 else ""
    print(f"  {jid:<22} n={tot:<4} kitchen={own:3.0f}%  | {mix}{flag}")
