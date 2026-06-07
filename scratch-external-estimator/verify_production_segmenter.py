"""Cross-check the PRODUCTION segmenter (custom_components/.../counter_segmentation.py)
against the real run CSVs — catches any porting error vs the prototypes.

Builds a counter-sample stream the way live capture will (one sample per ct/ca
change, carrying last-seen of both + battery), then runs segment_counters and
prints the per-room split. Run via the eufy-vacuum-test image from /workspace.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from custom_components.eufy_vacuum.counter_segmentation import segment_counters  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = [
    # (label, csv, expected_rooms) — expected_rooms = dispatched queue length, the
    # value the internal finalizer passes; run1 is one room (2-pass), runs 5-7 are two.
    ("run5 internal Hallway+Kitchen (ByRoom)", "run5-internal-hallway-kitchen.csv", 2),
    ("run6 no-mop Bath+Hall", "run6-nomop-bathhall.csv", 2),
    ("run7 no-mop Bath+Hall #2", "run7-nomop2-bathhall.csv", 2),
    ("run1 single-room 2-pass Kitchen", "run1-history.csv", 1),
]


def build_samples(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((r["entity_id"], r["state"], r["last_changed"]))
    events = []
    for ent, state, t in rows:
        if ent == "sensor.alfred_cleaning_time":
            events.append((t, "ct", state))
        elif ent == "sensor.alfred_cleaning_area":
            events.append((t, "ca", state))
        elif ent == "sensor.alfred_battery":
            events.append((t, "batt", state))
    events.sort(key=lambda e: e[0])
    last = {"ct": None, "ca": None, "batt": None}
    samples = []
    for t, key, val in events:
        if val in ("unknown", "unavailable", ""):
            continue
        try:
            last[key] = float(val)
        except ValueError:
            continue
        if key in ("ct", "ca") and last["ct"] is not None and last["ca"] is not None:
            samples.append({
                "t": t,
                "cleaning_time": last["ct"],
                "cleaning_area": last["ca"],
                "battery": last["batt"],
            })
    return samples


for label, fname, expected in RUNS:
    path = os.path.join(HERE, fname)
    if not os.path.exists(path):
        print(f"\n=== {label} === (missing {fname})")
        continue
    segs = segment_counters(build_samples(path), expected_rooms=expected)
    print(f"\n=== {label} === -> {len(segs)} segment(s)")
    for s in segs:
        print(f"   seg{s['index']} [{s['boundary']:>13}] area={s['area_delta_m2']:>4} m2  "
              f"active={s['time_active_s']:>5}s  wall={s['time_wall_s']:>5}s  "
              f"gap_before={s['gap_before_s']:>5}s  batt={s['battery_delta']}")
    print(f"   totals: area={sum(s['area_delta_m2'] for s in segs):.0f} m2  "
          f"active={sum(s['time_active_s'] for s in segs):.0f}s")
