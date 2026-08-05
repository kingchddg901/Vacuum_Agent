"""Re-judge harvested runs with the CURRENT code and diff against what shipped.

WHY THIS EXISTS. Every fix this campaign produced was green in CI and unproven on
a device, and the standing gate says an unvalidated packet is an unshipped one.
Waiting for a vacuum to reproduce each defect on demand is the slow way — and for
some (a mid-job recharge) it means engineering a low battery and hoping. But the
runs are already on disk. A job record written by the OLD build *is* the old
verdict, frozen; re-judging the same inputs with the shipped functions shows
exactly what a fix changes, on real device data, with no vacuum involved.

Chris, 2026-08-05, on being told the remaining validation needed hardware runs:
"why are we working so hard ... we have the raw traces. we harvested directly for
this."

TWO SOURCES, AND THE SPLIT MATTERS:

  job records (this file)     — the integration's own conclusions: room timings,
                                battery block, outcome. Enough to re-judge
                                anything DERIVED from them.
  recorder tape (harvest.py)  — the device's raw entity stream. The only source
                                for anything upstream of a job record, because
                                job records do NOT persist counter/battery/pose
                                samples. Segmentation itself can only be replayed
                                from a tape.

Ask which source can answer a question BEFORE writing the check. A job record
cannot testify about the classifier that produced it.

IMPORT THE REAL FUNCTIONS, never restate their logic. A re-implementation agrees
with whatever the author believed while writing it, which is the one thing a
validation must not do.

Usage:
    python tests/replay/reverdict.py --learning "Z:/eufy_vacuum/learning"
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from custom_components.eufy_vacuum.learning.external_ingest import (  # noqa: E402
    monotone_shift_run,
)
from custom_components.eufy_vacuum.learning.stats_rebuilder import (  # noqa: E402
    _captured_minutes,
)


def load_records(learning_root: pathlib.Path) -> list[tuple[str, str, dict[str, Any]]]:
    """Every job record under <learning>/<vacuum>/jobs, phase children included."""
    out: list[tuple[str, str, dict[str, Any]]] = []
    if not learning_root.is_dir():
        raise SystemExit(f"no such learning dir: {learning_root}")
    for vac_dir in sorted(p for p in learning_root.iterdir() if p.is_dir()):
        jobs = vac_dir / "jobs"
        if not jobs.is_dir():
            continue
        for f in sorted(jobs.glob("*.json")):
            try:
                out.append((vac_dir.name, f.name,
                            json.loads(f.read_text(encoding="utf-8"))))
            except (ValueError, OSError) as exc:
                print(f"  unreadable {f.name}: {exc}")
    return out


def check_recharge_flag(records) -> list[tuple]:
    """live:RECHARGE-FLAG-2 — observed is DERIVED, not a live flag that gets cleared.

    A recharge that RESUMED cleared the flag before finalize, so the run recorded
    observed=False while its own count/accumulator said otherwise. The same file's
    battery_metrics.mid_job_recharge already disagreed, which is how a single
    record ends up testifying both ways.
    """
    hits = []
    for vac, name, j in records:
        b = j.get("battery") or {}
        recorded = bool(b.get("mid_job_recharge_observed"))
        count = int(b.get("mid_job_recharge_count") or 0)
        accum = float(b.get("recharge_seconds_accumulated") or 0)
        derived = count > 0 or accum > 0
        if recorded != derived:
            metrics = (j.get("job") or {}).get("battery_metrics") or {}
            hits.append((vac, name, recorded, derived, count, accum,
                         metrics.get("mid_job_recharge")))
    return hits


def check_attribution_shift(records) -> list[tuple]:
    """live:RECHARGE-ATTR-1 net — a dropped boundary slides every later label.

    Reading disagreements one at a time cannot see this; the run of consecutive
    rows each naming its SUCCESSOR is the signature.
    """
    hits = []
    for vac, name, j in records:
        timings = (j.get("job") or {}).get("room_timings") or []
        run = monotone_shift_run(timings)
        if run >= 2:
            hits.append((vac, name, run, len(timings),
                         (j.get("outcome") or {}).get("used_for_learning")))
    return hits


def check_wall_fenceposts(records) -> dict[str, list[float]]:
    """live:PHASE-ATTR-3 — cleaning_wall_seconds means two different things.

    The finding predicted the phase path runs LONGER than cleaning_seconds and the
    segmenter path SHORTER, measured on one room (Kitchen, n=37). Split every row
    by which path produced it and let the corpus re-measure it.
    """
    by_kind: dict[str, list[float]] = {"phase": [], "segmenter": []}
    for _vac, _name, j in records:
        for t in (j.get("job") or {}).get("room_timings") or []:
            clean, wall = t.get("cleaning_seconds"), t.get("cleaning_wall_seconds")
            if not isinstance(clean, (int, float)) or not isinstance(wall, (int, float)):
                continue
            if clean <= 0:
                continue
            kind = "phase" if t.get("boundary") == "phase" else "segmenter"
            by_kind[kind].append(wall - clean)
    return by_kind


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--learning", required=True,
                    help='the eufy_vacuum learning dir, e.g. "Z:/eufy_vacuum/learning"')
    args = ap.parse_args()

    records = load_records(pathlib.Path(args.learning))
    print(f"records replayed: {len(records)}\n")

    print("=" * 72)
    print("RECHARGE-FLAG-2 — mid_job_recharge_observed is derived, not a live flag")
    print("=" * 72)
    hits = check_recharge_flag(records)
    print(f"records where the OLD value disagrees with what the NEW code derives: {len(hits)}")
    for vac, name, rec, der, count, accum, metrics in hits:
        print(f"  {vac} {name}")
        print(f"     observed recorded={rec} -> derived={der}  (count={count}, accum={accum:.0f}s)")
        print(f"     same file's battery_metrics.mid_job_recharge={metrics}")

    print()
    print("=" * 72)
    print("RECHARGE-ATTR-1 net — monotone attribution shift blocks learning")
    print("=" * 72)
    shifts = check_attribution_shift(records)
    print(f"records the NEW rule blocks: {len(shifts)}")
    for vac, name, run, rooms, learned in shifts:
        print(f"  {vac} {name}  shift_run={run}/{rooms} rooms   OLD used_for_learning={learned}")

    print()
    print("=" * 72)
    print("PHASE-ATTR-3 — two fenceposts feeding one accumulator")
    print("=" * 72)
    by_kind = check_wall_fenceposts(records)
    for kind, deltas in by_kind.items():
        if not deltas:
            print(f"  {kind:10}: no rows")
            continue
        print(f"  {kind:10}: n={len(deltas):4}  mean(wall-cleaning)={statistics.mean(deltas):+8.1f}s"
              f"  median={statistics.median(deltas):+8.1f}s")
    if by_kind["phase"] and by_kind["segmenter"]:
        gap = statistics.mean(by_kind["phase"]) - statistics.mean(by_kind["segmenter"])
        print(f"  -> the two populations sit {gap:+.1f}s apart measuring the same thing")

    changed = []
    for _vac, _name, j in records:
        for t in (j.get("job") or {}).get("room_timings") or []:
            wall = t.get("cleaning_wall_seconds")
            if not isinstance(wall, (int, float)):
                continue
            new_min, old_min = _captured_minutes(t), round(wall / 60.0, 4)
            if new_min and abs(new_min - old_min) > 1e-9:
                changed.append(abs(new_min - old_min) * 60.0)
    if changed:
        print(f"\n  per-room learned minutes change on {len(changed)} rows; "
              f"mean {statistics.mean(changed):.1f}s, max {max(changed):.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
