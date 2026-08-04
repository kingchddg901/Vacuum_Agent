"""Replay a REAL counter stream from an HA recorder export through the REAL segmenter.

WHY THIS EXISTS. On 2026-08-03 Alfred's group phase `pj_2026-08-03T17-22-18`
phase2 ([Entryway, Home Office]) recorded 195/195 — an even arithmetic split —
instead of measured per-room timings. The samples the segmenter saw were gone:
``counter_samples`` live only on the in-flight job and die at finalize. But HA's
recorder still had the two sensors they are built from, so the stream was
reconstructable and the question answerable WITHOUT another hardware run.

It returned 1 segment for 2 rooms -> gate 2 (count) rejects -> apportion. The
boundary IS in the data (00:31:11, a 47 s gap carrying +2.0 m², which the card
independently reported as the Entryway->Home Office handover at ~3.5 min); the
engine walks past it because 47 s sits below BOTH gap_transit_s (60) and
gap_plateau_s (90), leaving only the area_jump arm.

ROOT CAUSE (confirmed by bisecting the threshold with --tuning, 2026-08-03):
``area_after >= area_jump_m2`` fails by less than a THOUSANDTH of a square metre.
The jump is nominally exactly 2.0 m², but the sensor reports ft² and the device
moves in whole 1 m² steps (10.76 ft² each), so after the 0.09290304 conversion
the compared quantity lands at ~1.9995-1.9999 against a threshold of exactly 2.0.
This probe flips 2 segments -> 1 between ``area_jump_m2`` 1.9995 and 2.0, and gap
tuning does not help (45 and 40 both still give 1).

That makes it SYSTEMATIC rather than a one-off: because the counter is quantised
to 1 m², a two-room boundary essentially always lands on a near-exact 2.0, so the
most common case is a permanent coin-flip on float error. It is an exact-threshold
comparison against a unit-converted float — treat the whole class that way, not
just this constant.

USE IT FOR: any future group-phase mis-attribution. One hardware run produces one
data point; this produces unlimited hypothesis tests against it — retune, patch
the engine, re-run in seconds.

HOW TO GET THE CSV. HA -> History -> pick the window -> Download data. Needs at
least ``sensor.<vac>_cleaning_time`` and ``sensor.<vac>_cleaning_area``. Columns:
entity_id,state,last_changed.

WINDOW. Use the phase record's own room_timings cleaning_start/cleaning_end
(``learning/<vac>/jobs/job_<id>.phaseN.json`` -> job.room_timings[0]) so the
slice matches what production sliced.

UNITS — the two conversions the live path applies, applied here identically:
  * ``cleaning_time``  sensor is MINUTES (0.5 steps); the field is SECONDS.
  * ``cleaning_area``  sensor is ft² on an imperial HA; the field is m².
Get either wrong and the verdict is meaningless: at ft² every step clears
area_jump_m2=2.0 and the engine OVER-segments instead.

RECONSTRUCTION CAVEAT. ``record_counter_sample`` snapshots BOTH counters whenever
either changes, so this steps the union of change instants carrying each one's
last-seen value. Samples before the first in-window change of a counter therefore
carry a stale pre-phase value. Verified 2026-08-03 not to change the verdict
(1 segment either way) — but re-check it when a result looks marginal.

Run (docker, from the repo root):
  docker run --rm -v "%CD%:/workspace" -v "<csvdir>:/data" -w /workspace \
    -e PYTHONPATH=/workspace eufy-vacuum-test \
    python .claude/notes/_probe_replay_segmenter.py /data/recorder.csv \
      --vacuum alfred --start 2026-08-04T00:27:48Z --end 2026-08-04T00:35:11Z --rooms 2
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys

FT2_TO_M2 = 0.09290304


def _ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _load(path: str, vacuum: str) -> tuple[list, list]:
    ct_id = f"sensor.{vacuum}_cleaning_time"
    ca_id = f"sensor.{vacuum}_cleaning_area"
    ct: list[tuple[dt.datetime, float]] = []
    ca: list[tuple[dt.datetime, float]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                value = float(row["state"])
            except (ValueError, KeyError, TypeError):
                continue
            when = _ts(row["last_changed"])
            if row["entity_id"] == ct_id:
                ct.append((when, value))
            elif row["entity_id"] == ca_id:
                ca.append((when, value))
    if not ct and not ca:
        raise SystemExit(
            f"no rows for {ct_id} / {ca_id} — check --vacuum and that the export "
            f"actually covers those entities"
        )
    return sorted(ct), sorted(ca)


def build_samples(ct, ca, a, b, *, require_both=False) -> list[dict]:
    """The union of change instants, each carrying both counters' last-seen value —
    the exact shape ``record_counter_sample`` appends."""
    marks = sorted({t for t, _ in ct} | {t for t, _ in ca})
    out: list[dict] = []
    i = j = 0
    last_ct = last_ca = None
    for t in marks:
        while i < len(ct) and ct[i][0] <= t:
            last_ct = ct[i][1]
            i += 1
        while j < len(ca) and ca[j][0] <= t:
            last_ca = ca[j][1]
            j += 1
        if not (a <= t <= b):
            continue
        if last_ct is None and last_ca is None:
            continue
        if require_both and (last_ct is None or last_ca is None):
            continue
        out.append({
            "t": t.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "cleaning_time": None if last_ct is None else last_ct * 60.0,
            "cleaning_area": None if last_ca is None else last_ca * FT2_TO_M2,
            "battery": None,
        })
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv")
    p.add_argument("--vacuum", default="alfred")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--rooms", type=int, required=True)
    p.add_argument("--engine", default=None, help="engine name; default = adapter fallback")
    p.add_argument("--tuning", default=None, help='JSON, e.g. \'{"gap_transit_s":45}\'')
    p.add_argument("--require-both", action="store_true",
                   help="drop samples before BOTH counters have an in-window value")
    args = p.parse_args()

    ct, ca = _load(args.csv, args.vacuum)
    samples = build_samples(ct, ca, _ts(args.start), _ts(args.end),
                            require_both=args.require_both)
    print(f"reconstructed {len(samples)} samples  ({args.start} -> {args.end})\n")
    prev_a = None
    for s in samples:
        area = s["cleaning_area"]
        delta = "" if (area is None or prev_a is None) else f"  d_area={area - prev_a:+.2f}"
        print(f"   {s['t'][11:19]}  ct={s['cleaning_time']}  "
              f"ca={None if area is None else round(area, 3)}{delta}")
        prev_a = area if area is not None else prev_a

    from custom_components.eufy_vacuum.learning.job_segmenter_engines import (
        get_job_segmenter_engine,
    )
    engine = get_job_segmenter_engine(args.engine)
    tuning = json.loads(args.tuning) if args.tuning else None
    print(f"\nengine = {engine.engine_name}")
    print(f"tuning = {json.dumps(getattr(engine, 'DEFAULT_TUNING', {}), sort_keys=True)}")
    if tuning:
        print(f"override = {json.dumps(tuning, sort_keys=True)}")

    segments = engine.segment_legacy(samples, expected_rooms=args.rooms, tuning=tuning)
    print(f"\n=== segment_legacy(expected_rooms={args.rooms}) -> {len(segments)} SEGMENT(S) ===")
    for k, seg in enumerate(segments):
        flat = {kk: vv for kk, vv in seg.items() if not isinstance(vv, (list, dict))}
        print(f"  seg{k}: {json.dumps(flat, sort_keys=True, default=str)[:320]}")

    print("\n=== VERDICT ===")
    if len(segments) == args.rooms:
        print(f"count gate PASSES ({len(segments)} == {args.rooms}) — any rejection "
              f"was a LATER gate (baseline or reconciliation).")
        return 0
    print(f"GATE 2 (count) REJECTS: expected {args.rooms}, got {len(segments)}.")
    print("  -> " + ("OVER-segmentation: extra boundaries in the stream."
                     if len(segments) > args.rooms else
                     "UNDER-segmentation: the boundary was not detected."))
    return 1


if __name__ == "__main__":
    sys.exit(main())
