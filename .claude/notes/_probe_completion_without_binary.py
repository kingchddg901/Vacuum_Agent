"""Can a run's END be detected WITHOUT binary_sensor.<vac>_cleaning? (issue #46)

WHY. HA 2026.7 (home-assistant/core#173282) stops creating
`binary_sensor.<vac>_cleaning` on some Roborock devices. For this brand that
binary is the SOLE disambiguator between "docked mid-job to recharge" and
"finished": the adapter's completion block keys on it precisely because
`sensor.<vac>_current_room` reverts to the DOCK ROOM'S NAME at the end and never
reads a sentinel, so the default secondary check can never pass. Lose the binary
and a naive "treat it as undeclared" fallback just moves the failure from
"never arms" to "secondary never satisfied" -- the same wedged run, one line down.

The adapter comment names the substitute, with a trace behind it: the binary goes
"OFF only at completion when total_count incremented". `total_cleaning_count`
increments once per COMPLETED run and not on a recharge dock -- exactly the
discrimination the binary provided.

THIS PROBE TESTS THAT CLAIM AGAINST REAL DATA, and it can only be done on a
vacuum that still HAS the binary. Ivy does; the reporter's Q5 does not. So Ivy is
the oracle: hide her binary, run the proposed rule, and check it reproduces the
completions her job records already prove happened.

Ground truth comes from the run records themselves
(`eufy_vacuum/learning/<vac>/jobs/job_*.json` -> job.started_at / job.ended_at),
not from the signal under test. Two questions:

  RECALL     does a total_cleaning_count increment land at each real run end?
  PRECISION  does it stay flat across mid-run recharge docks (the case the
             binary exists to survive)?

A rule that fires on every real finish but ALSO on a recharge is useless -- it
would finalize a job that is still cleaning, which is worse than never
finalizing because it writes a truncated learning sample.

EXPORT NEEDED (HA -> History -> pick the window -> Download data), covering the
run window the records show:
    sensor.<vac>_total_cleaning_count
    binary_sensor.<vac>_cleaning        (the oracle -- not used by the rule)
    sensor.<vac>_status                 (task_status; completion trigger)
    vacuum.<vac>
    sensor.<vac>_battery                (to spot the recharge dips)

Run:
    python .claude/notes/_probe_completion_without_binary.py <csv> --vacuum ivy
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys

CONFIG = pathlib.Path("//192.168.4.104/config/eufy_vacuum/learning")


def _ts(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _series(rows: list[dict], entity: str) -> list[tuple[dt.datetime, str]]:
    out = [(_ts(r["last_changed"]), r["state"])
           for r in rows if r["entity_id"] == entity]
    return sorted(out)


def _runs(vacuum: str) -> list[tuple[dt.datetime, dt.datetime, str]]:
    """(started, ended, record) for every finalized run, from the RECORDS.

    Deliberately not from any live signal: the point is to judge a candidate
    signal against something independent of it.
    """
    out = []
    jobs = CONFIG / vacuum / "jobs"
    for p in sorted(jobs.glob("job_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        j = d.get("job") or {}
        s, e = j.get("started_at"), j.get("ended_at")
        if s and e:
            out.append((_ts(s), _ts(e), p.name))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--vacuum", default="ivy")
    ap.add_argument("--tolerance", type=float, default=180.0,
                    help="seconds either side of a run end that still counts as 'at' it")
    args = ap.parse_args()

    # utf-8-sig: HA's history download carries a BOM, which would otherwise ride
    # along on the first column name and make every entity_id lookup miss.
    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    v = args.vacuum
    count = _series(rows, f"sensor.{v}_total_cleaning_count")
    binary = _series(rows, f"binary_sensor.{v}_cleaning")
    battery = _series(rows, f"sensor.{v}_battery")

    print(f"total_cleaning_count changes : {len(count)}")
    print(f"binary_sensor cleaning changes: {len(binary)}   (ORACLE — the rule never reads it)")
    print(f"battery samples               : {len(battery)}")
    if not count:
        print(f"\nNo sensor.{v}_total_cleaning_count rows — export it and re-run.")
        return 2

    lo, hi = min(t for t, _ in count), max(t for t, _ in count)
    runs = [r for r in _runs(v) if lo <= r[0] and r[1] <= hi]
    print(f"\nruns fully inside the export window: {len(runs)}")
    if not runs:
        print("Export does not cover any complete run — widen the window.")
        return 2

    # increments only; the sensor can also reset or re-report the same value
    incs = []
    prev = None
    for t, raw in count:
        try:
            val = float(raw)
        except ValueError:
            continue
        if prev is not None and val > prev:
            incs.append((t, prev, val))
        prev = val
    print(f"total_cleaning_count INCREMENTS: {len(incs)}\n")

    tol = dt.timedelta(seconds=args.tolerance)
    print(f"{'run record':40} {'ended':>9}  increment within ±{int(args.tolerance)}s?")
    print("-" * 78)
    matched = set()
    recall = 0
    for start, end, name in runs:
        near = [i for i in incs if abs(i[0] - end) <= tol]
        if near:
            recall += 1
            matched.add(near[0][0])
        print(f"{name:40} {end.strftime('%m-%d %H:%M'):>9}  "
              f"{'YES ' + near[0][0].strftime('%H:%M:%S') if near else 'no'}")

    # PRECISION: increments that land INSIDE a run (not at its end) would fire
    # the rule mid-clean -- the recharge-dock case the binary exists to survive.
    inside = []
    for t, before, after in incs:
        if t in matched:
            continue
        for start, end, name in runs:
            if start < t < end - tol:
                inside.append((t, name, before, after))
    print("\n" + "=" * 78)
    print(f"RECALL   : {recall}/{len(runs)} run ends had an increment within tolerance")
    print(f"PRECISION: {len(inside)} increment(s) landed MID-RUN (would finalize early)")
    for t, name, b, a in inside:
        print(f"   {t:%m-%d %H:%M:%S} inside {name}  ({b} -> {a})")
    if recall == len(runs) and not inside:
        print("\nVERDICT: the counter reproduces every completion and fires on none of the"
              "\n         mid-run docks — it can stand in for the binary on this data.")
        return 0
    print("\nVERDICT: NOT a safe substitute as-is. Do not ship the fallback on this"
          "\n         evidence; read the misses above first.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
