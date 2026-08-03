"""Probe: what does the segmenter actually return for a two-room phase slice?

Confirms the rebase is load-bearing — the raw segment fields carry the RUN's
cumulative totals, and only the rebase in _segment_group_room_timing turns them
into the phase's own numbers.

Run: docker run --rm -v <repo>:/workspace -w /workspace eufy-vacuum-test \
     python .claude/notes/_probe_phase_slice_seg.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from custom_components.eufy_vacuum.counter_segmentation import segment_counters  # noqa: E402


def _cs(t: str, ct: int, ca: float) -> dict:
    return {"t": t, "cleaning_time": ct, "cleaning_area": ca, "battery": 90}


def slice_(base_ct: int, base_area: float) -> list[dict]:
    return [
        _cs("2026-01-01T00:00:30Z", base_ct, base_area),
        _cs("2026-01-01T00:01:00Z", base_ct + 30, base_area + 1.5),
        _cs("2026-01-01T00:01:30Z", base_ct + 60, base_area + 3.0),
        # >90 s plateau — the inter-room boundary
        _cs("2026-01-01T00:03:30Z", base_ct + 90, base_area + 4.5),
        _cs("2026-01-01T00:04:00Z", base_ct + 120, base_area + 6.0),
        _cs("2026-01-01T00:04:30Z", base_ct + 150, base_area + 7.5),
    ]


KEYS = ("index", "t_start", "t_end", "ct_end", "area_end_m2",
        "area_delta_m2", "time_active_s", "time_wall_s", "boundary")


def main() -> int:
    """ASSERTS, does not merely print.

    This started as a print-only probe and was promoted when it went into
    _gate_phased_runs.py: a gate member that exits 0 whatever it observes is not a
    gate. What it pins is the PREMISE beneath SOPT-12, which no test can see —
    SOPT-12 asserts our REBASED output, so if build_segments ever became
    slice-relative upstream, SOPT-12 would keep passing while our rebase silently
    double-corrected. This fails first, and loudly, in that case.
    """
    failures: list[str] = []

    def check(name: str, got, want) -> None:
        ok = got == want
        print(f"   {'PASS' if ok else 'FAIL'}  {name}: {got!r}" +
              ("" if ok else f"  (expected {want!r})"))
        if not ok:
            failures.append(name)

    for base_ct, base_area in ((30, 1.5), (600, 42.0)):
        samples = slice_(base_ct, base_area)
        segs = segment_counters(samples, expected_rooms=2)
        print(f"\nslice opens at cleaning_time={base_ct} area={base_area} "
              f"-> {len(segs)} segments")
        for s in segs:
            print("   RAW ", {k: s[k] for k in KEYS})

        check(f"base={base_ct}: two segments found", len(segs), 2)
        if len(segs) != 2:
            continue
        check(f"base={base_ct}: the plateau is the boundary",
              segs[1]["boundary"], "wash_plateau")
        # THE PREMISE: the segmenter counts from ZERO, so segment 0 carries the
        # run's cumulative totals, not the phase's. This is exactly the trap the
        # rebase exists for — if these stop being cumulative, the rebase is wrong.
        check(f"base={base_ct}: segment 0 is CUMULATIVE, not slice-relative",
              segs[0]["time_active_s"], float(base_ct + 60))

        # The rebase _segment_group_room_timing applies.
        prev_ct, prev_area = float(base_ct), float(base_area)
        rebased = []
        for s in segs:
            secs = int(max(float(s["ct_end"]) - prev_ct, 0.0))
            area = round(max(float(s["area_end_m2"]) - prev_area, 0.0), 3)
            rebased.append((secs, area, int(s["time_wall_s"])))
            print(f"   REBASED secs={secs} area={area} wall={int(s['time_wall_s'])}")
            prev_ct, prev_area = float(s["ct_end"]), float(s["area_end_m2"])

        # Identical for both baselines — that IS the rebase working.
        check(f"base={base_ct}: rebased parts", rebased,
              [(60, 4.5, 30), (90, 3.0, 60)])

    print("\n" + "=" * 66)
    if failures:
        print(f"BROKE: {len(failures)} -> {failures}")
        return 1
    print("segmenter premise holds: counts from zero, rebase yields the phase's own")
    return 0


if __name__ == "__main__":
    sys.exit(main())
