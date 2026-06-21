"""Formalized external-run room-attribution classifier (PROTOTYPE — pre-integration).

Recovers WHICH rooms an external (app-started) clean actually cleaned, from the live
`current_room` signal logged by the throwaway probe (debug_log_live_room). Validated against
3 adversarial runs on vacuum.alfred (see docs/dev/eufy-native-transition.md).

This is a STANDALONE prototype: no Home Assistant imports, not wired into the integration
(approval pause on runtime code still holds). Its job is to PIN the rule to data so we can
formalize thresholds and regression-test them before any integration code.

Pipeline
--------
1. Segment the run by `current_room` into contiguous RUNS (run-length encode the samples).
2. Per run, compute: dwell_s, anchor spread (RMS about centroid), path_len (sum of step
   distances), net displacement, winding (path_len / net_disp), bbox area.
3. Aggregate per room by its BEST run (max evidence). A room is cleaned if ANY of its runs
   qualifies (NOT total-dwell — a wash/park run must never dilute or fake a clean).
4. Classify each room:
   - TRANSIT: winding ~1 (a straight pass-through), regardless of dwell/spread.
   - CLEANED vs PARKED-DOCK:
       * ROBUST mode (swept-area available): swept m^2 during the room's windows >= AREA_MIN.
         A wash/park sweeps ~0 m^2; a clean sweeps real area. This is the ONLY signal that
         robustly separates a long *jittering* parked dock from a cleaned room.
       * ANCHOR-ONLY fallback (no area): dwell >= DWELL_MIN AND winding >= WIND_MIN.
         LIMITATION (proven by run #1, room 8): a parked dock can jitter into the cleaned
         cluster (high dwell, high winding, mid spread) and be indistinguishable from a small
         clean. Anchor-only therefore FALSE-POSITIVES the dock in that case. Use area when you
         can; treat anchor-only as a best-effort proxy.

THE KEY FINDING the formalization surfaced: dwell+spread+winding alone are NOT sufficient to
separate a parked dock from a clean (run #1 room 8 ≈ run #1 room 6 on every anchor axis). The
device swept-area signal (sensor.<vac>_cleaning_area, aligned to the current_room windows) is
required for a robust rule. The probe should log cleaning_area alongside current_room.
"""

import math

# --- Thresholds (formalized from the 3 adversarial validation runs) ----------------------
WIND_TRANSIT = 1.5        # winding < this  => straight pass => TRANSIT (transit rooms: ~1.0-1.22;
                          #                    cleaned rooms: >=4.9). Robust across all 3 runs.
DWELL_MIN_S = 25.0        # anchor-only fallback floor (transit single-run dwell ceiling ~18s;
                          #                    cleaned floor ~34-46s).
SWEPT_AREA_MIN_M2 = 0.5   # robust: a clean sweeps >= this; a wash/park sweeps ~0 m^2.


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def run_metrics(room, sample_times, anchors, interval_s=2.0):
    """Metrics for one contiguous current_room run. `anchors` = [(x,y), ...] (may be empty)."""
    n = len(sample_times)
    dwell_s = (n * interval_s) if n else 0.0
    m = {"room": room, "n": n, "dwell_s": dwell_s,
         "spread": 0.0, "path_len": 0.0, "net_disp": 0.0, "winding": 0.0, "bbox_area": 0.0}
    pts = [p for p in anchors if p is not None]
    if not pts:
        return m
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    m["bbox_area"] = (max(xs) - min(xs)) * (max(ys) - min(ys))
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    m["spread"] = math.sqrt(sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in pts) / len(pts))
    path = sum(_dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))
    disp = _dist(pts[0], pts[-1])
    m["path_len"], m["net_disp"] = path, disp
    m["winding"] = (path / disp) if disp > 1e-4 else (999.0 if path > 1e-3 else 0.0)
    return m


def best_run_by_room(run_metric_list):
    """Aggregate runs to per-room BEST run (max spread — the strongest clean-evidence run)."""
    by_room = {}
    for m in run_metric_list:
        cur = by_room.get(m["room"])
        if cur is None or m["spread"] > cur["spread"]:
            by_room[m["room"]] = m
    return by_room


def classify(per_room_best, swept_area_by_room=None):
    """per_room_best: {room_id: <best run metrics>}. swept_area_by_room: {room_id: m^2} or None.
    Returns {"cleaned": set, "verdicts": {room_id: (label, reason)}}."""
    cleaned, verdicts = set(), {}
    for rid, m in per_room_best.items():
        if rid is None:
            verdicts[rid] = ("transit", "no room (transit cell)")
            continue
        if m["winding"] < WIND_TRANSIT:
            verdicts[rid] = ("transit", f"straight pass (winding {m['winding']:.2f} < {WIND_TRANSIT})")
            continue
        if swept_area_by_room is not None:                       # ROBUST mode
            a = float(swept_area_by_room.get(rid, 0.0))
            if a >= SWEPT_AREA_MIN_M2:
                cleaned.add(rid); verdicts[rid] = ("cleaned", f"swept {a:.1f} m^2")
            else:
                verdicts[rid] = ("parked/dock", f"swept ~{a:.1f} m^2 (< {SWEPT_AREA_MIN_M2})")
        else:                                                    # ANCHOR-ONLY fallback
            if m["dwell_s"] >= DWELL_MIN_S:
                cleaned.add(rid)
                verdicts[rid] = ("cleaned?", f"dwell {m['dwell_s']:.0f}s + winding {m['winding']:.1f} "
                                             f"(anchor-only — cannot exclude a jittering parked dock)")
            else:
                verdicts[rid] = ("transit", f"short dwell {m['dwell_s']:.0f}s")
    return {"cleaned": cleaned, "verdicts": verdicts}
