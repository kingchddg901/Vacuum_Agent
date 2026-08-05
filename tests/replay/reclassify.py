"""Run the SHIPPED segmenter over a harvested recorder tape.

The half `reverdict.py` cannot reach. Job records carry the integration's
CONCLUSIONS, not its inputs — no counter_samples, no battery_samples, no pose —
so nothing upstream of a job record can be re-judged from one. A tape is the
device's own stream, so the classifier can be run against exactly what it saw.

That distinction is the whole reason both files exist: a job record cannot
testify about the classifier that produced it.

WHAT IT IS GOOD FOR, and what it is not. This reproduces the CLASSIFICATION of a
gap — was this pause a room boundary, a wash, or a recharge? It does NOT
reproduce the run's room split. The live segmenter also reads task_status, the
per-room selected-for-cleaning switches and pose, and `select_active` filters
candidates the live path kept; measured 2026-08-05, this harness implied 1 and 2
rooms on runs that really had 4. Do not report a room count from it.

Usage:
    python tests/replay/reclassify.py --bundles C:/Users/CKing/Documents/durable/replays
    python tests/replay/reclassify.py --bundles <dir> --vacuum ivy
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from custom_components.eufy_vacuum.counter_segmentation import (  # noqa: E402
    _NEVER_BOUNDARY_KINDS,
    _RECHARGE_MIN_RISE_PCT,
    find_candidates,
    select_active,
)


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_samples(bundle: dict[str, Any], vacuum: str) -> list[dict[str, Any]]:
    """One sample per cleaning_time observation, carrying area/battery in force.

    The tape is a flat event log, so area and battery are carried FORWARD from
    their last observation rather than joined on timestamp — they tick on their
    own cadence and almost never share an instant with a counter increment.
    """
    counter = f"sensor.{vacuum}_cleaning_time"
    area_id = f"sensor.{vacuum}_cleaning_area"
    batt_id = f"sensor.{vacuum}_battery"

    area = batt = None
    samples: list[dict[str, Any]] = []
    for ts, entity_id, state in sorted(bundle.get("events") or [], key=lambda e: e[0]):
        if entity_id == area_id:
            value = _num(state)
            if value is not None:
                area = value
        elif entity_id == batt_id:
            value = _num(state)
            if value is not None:
                batt = value
        elif entity_id == counter:
            value = _num(state)
            if value is None:
                continue          # "unavailable"/"unknown" is not a counter reading
            samples.append({
                "t": ts,
                "cleaning_time": value,
                "cleaning_area": area if area is not None else -1.0,
                "battery": batt,
            })
    return samples


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundles", required=True, help="directory of window_*.json tapes")
    ap.add_argument("--vacuum", default="alfred", help="entity object_id, e.g. alfred")
    args = ap.parse_args()

    root = pathlib.Path(args.bundles)
    tapes = sorted(root.glob("window_*.json"))
    if not tapes:
        raise SystemExit(f"no window_*.json under {root}")

    print(f"_RECHARGE_MIN_RISE_PCT = {_RECHARGE_MIN_RISE_PCT}")
    print(f"_NEVER_BOUNDARY_KINDS  = {sorted(_NEVER_BOUNDARY_KINDS)}\n")

    for tape in tapes:
        bundle = json.loads(tape.read_text(encoding="utf-8"))
        window = (bundle.get("meta") or {}).get("window", ["?", "?"])
        samples = build_samples(bundle, args.vacuum)
        print("=" * 74)
        print(tape.name)
        print(f"  window {window[0]} -> {window[1]}   counter samples: {len(samples)}")
        if not samples:
            print("  no counter signal for this vacuum in this window")
            continue

        candidates = find_candidates(samples)
        print(f"  candidate boundaries: {len(candidates)}")
        for c in candidates:
            rise = c.get("batt_rise_pct")
            rise_s = f"{rise:+.1f}%" if isinstance(rise, (int, float)) else "n/a"
            never = "  <-- NEVER a boundary" if c.get("kind") in _NEVER_BOUNDARY_KINDS else ""
            print(f"    gap={_num(c.get('gap_s')) or 0:8.0f}s  kind={str(c.get('kind')):15}"
                  f" batt_rise={rise_s:>7}  area_after={c.get('area_after_m2')}{never}")

        active = select_active(candidates)
        print(f"  active after filtering: {len(active)}   kinds: {[a.get('kind') for a in active]}")
        print("  (classification only — this harness does not reproduce the room split)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
