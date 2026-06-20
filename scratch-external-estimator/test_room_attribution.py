"""Regression harness for room_attribution.classify, pinned to the 3 adversarial validation runs.

Each fixture is the per-room EVIDENCE (max over that room's runs: spread / dwell / winding) that
the analyzer produced, plus the per-room SWEPT AREA (m^2) and the GROUND-TRUTH cleaned set from the
finalized external job records. Run:  python test_room_attribution.py

swept_m2 here stands in for the device `sensor.<vac>_cleaning_area` aligned to each current_room
window. For run #3 (vicious) this was verified non-circularly against the device-history CSV
(cleaning_area FLAT during washes, accrues during cleans). For runs #1/#2 we use the capture
record's per-room area (the same quantity the production pipeline would derive).
"""

from room_attribution import classify

# room_id -> (spread, dwell_s, winding, swept_m2)
RUNS = {
    "ext#1 (hallway/bath/entry)": {
        "truth": {2, 4, 6},
        "rooms": {
            4: (0.0688, 118, 126.48, 6.0),   # Hallway  CLEANED
            2: (0.0544, 110,  31.25, 2.0),   # Bathroom CLEANED
            6: (0.0264,  46,   5.22, 1.0),   # Entryway CLEANED (tiny floor)
            8: (0.0282, 271,  43.47, 0.0),   # Dining (DOCK) — PARKED, not cleaned  <-- the trap
            7: (0.0700,  18,   1.21, 0.0),   # transit hub
            9: (0.0297,   8,   1.00, 0.0),   # transit
        },
    },
    "dock-first (dining first)": {
        "truth": {2, 6, 8},
        "rooms": {
            8: (0.0728, 657,  39.84, 12.0),  # Dining (DOCK) — CLEANED first
            2: (0.0451,  92, 117.29,  2.0),  # Bathroom CLEANED
            6: (0.0270,  38,  13.60,  1.0),  # Entryway CLEANED (tiny)
            7: (0.0657,  16,   1.18,  0.0),  # transit
            9: (0.0323,   8,   1.00,  0.0),  # transit
            4: (0.0461,   8,   1.00,  0.0),  # Hallway — transit this run
        },
    },
    "vicious (interleaved mop-wash)": {
        "truth": {4, 5, 8},
        "rooms": {
            8: (0.0714, 789,  38.17, 12.0),  # Dining (DOCK) — CLEANED, + folded mid-run wash
            4: (0.0730,  86,   4.93,  2.0),  # Hallway CLEANED
            5: (0.0518, 106,  30.08,  2.0),  # Kitchen CLEANED
            7: (0.0751,  18,   1.22,  0.0),  # transit
            None: (0.0028, 6,  1.00,  0.0),  # transit cells
            1: (0.0000,   2,   0.00,  0.0),  # 1-tick flicker
        },
    },
}


def _per_room(rooms):
    return {rid: {"spread": s, "dwell_s": d, "winding": w} for rid, (s, d, w, _a) in rooms.items()}


def _areas(rooms):
    return {rid: a for rid, (_s, _d, _w, a) in rooms.items()}


def run(mode, use_area):
    print(f"\n===== {mode} =====")
    tp = fp = fn = 0
    for name, fx in RUNS.items():
        per_room = _per_room(fx["rooms"])
        areas = _areas(fx["rooms"]) if use_area else None
        out = classify(per_room, swept_area_by_room=areas)
        pred, truth = out["cleaned"], fx["truth"]
        ok = pred == truth
        tp += len(pred & truth); fp += len(pred - truth); fn += len(truth - pred)
        flag = "OK " if ok else "MISMATCH"
        print(f"  [{flag}] {name}: predicted {sorted(pred)}  truth {sorted(truth)}"
              + ("" if ok else f"   FP={sorted(pred-truth)} FN={sorted(truth-pred)}"))
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    print(f"  --> TP={tp} FP={fp} FN={fn}   precision={prec:.2f}  recall={rec:.2f}")
    return tp, fp, fn


print("Formalized room-attribution classifier — regression over 3 adversarial runs")
a_tp, a_fp, a_fn = run("ANCHOR-ONLY (dwell + winding, no swept-area)", use_area=False)
r_tp, r_fp, r_fn = run("AREA-AUGMENTED (winding-transit-drop + swept-area)", use_area=True)

print("\n===== verdict =====")
print(f"  anchor-only:    recall {a_tp}/{a_tp+a_fn}, {a_fp} false positive(s)  "
      f"<- the parked dock (ext#1 room 8) leaks through")
print(f"  area-augmented: recall {r_tp}/{r_tp+r_fn}, {r_fp} false positive(s)  "
      f"<- swept-area excludes the parked dock => 9/9, 0 FP")
assert (r_fp, r_fn) == (0, 0), "area-augmented rule must be perfect on the fixtures"
assert a_fp >= 1, "anchor-only is expected to false-positive the parked dock (documents the hole)"
print("\nPASS: fixtures lock the rule. Area is REQUIRED to separate parked-dock from clean.")
