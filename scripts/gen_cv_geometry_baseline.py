"""Generator -- the CV geometry baseline: what the segmentor ACTUALLY produces, per fixture.

    python scripts/gen_cv_geometry_baseline.py --check   # compare, change nothing (CI//local gate)
    python scripts/gen_cv_geometry_baseline.py           # REWRITE the baseline (read the warning)

Run inside the test image, which is the only place scipy exists:

    docker run --rm -v "<repo>:/workspace" --workdir /workspace eufy-vacuum-test \\
        python scripts/gen_cv_geometry_baseline.py --check

WHAT THIS BASELINE IS, AND WHY THE IMPERFECT POLYGONS ARE THE CORRECT ONES. The CV was
never meant to emit flawless room polygons on its own -- that is precisely why the manual
adjustment tools exist. The pipeline detects, the user corrects, and the corrections
persist. This file records only the FIRST of those three: what the algorithm accomplished
before a human finished the job, including its known geometric imperfections.

So a fresh run must reproduce the same imperfect segments, not improved ones. A change
that makes the output "better" is still a change, and it has to be understood before it
is accepted.

    ### THE RULE: NEVER REGENERATE THIS FILE TO MAKE A TEST PASS. ###

A diff here is a finding, not a chore. Investigate it, decide the new output is
intended, and only then regenerate -- in the same commit as the change that caused it,
with the commit message saying which segments moved and why. Regenerating first destroys
the only record of what the algorithm used to do, and the programme has no other copy.

WHY GEOMETRY AND NOT COUNTS. The module's existing tests assert structural properties --
that a segment carries a role, a state, an issues list. Those pass unchanged if all
fifteen segments survive but every polygon shifts, which is exactly the regression most
worth catching. The comparison is therefore over the polygon points, the bounding box and
the area, per segment.

ON THE "--cov PERTURBS CV" CONVENTION. The module's tests avoid absolute assertions on
the stated grounds that coverage instrumentation can perturb CV results. MEASURED
2026-11-10, and it does not: for all three fixtures the full geometry record is
byte-identical under `coverage.Coverage(branch=True)` and without it, stable across three
repeated calls in one process and across separate processes. Determinism is a property of
this pinned image on this architecture, which is also what CI runs; the baseline is
therefore safe HERE, and a cross-architecture runner would need re-measuring before it
could be trusted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIXTURES = os.path.join(_HERE, "tests", "adapters", "eufy", "fixtures")
_BASELINE = os.path.join(_FIXTURES, "cv_geometry_baseline.json")

#: The configurations the test-suite actually drives the pipeline with. Keep this in step
#: with the tests: a configuration that is baselined but never exercised, or exercised but
#: never baselined, is the gap this file exists to close.
CASES = {
    "adversarial_min1200": {
        "image": "adversarial_map.png",
        "kwargs": {"min_area_pixels": 1200},
    },
    "dark_with_light_assist_min1200": {
        "image": "localized_map_dark.png",
        "kwargs": {
            "min_area_pixels": 1200,
            "image_variant": "dark",
            "assist_image": "localized_map_light.png",
            "assist_variant": "light",
        },
    },
    "light_min1200": {
        "image": "localized_map_light.png",
        "kwargs": {"min_area_pixels": 1200},
    },
    # THE DOCUMENTED DEGRADED MODE. Doc 25 S3: "the assist is optional throughout;
    # without it the pipeline still runs, and the result's message says which mode it ran
    # in." The pair is the design -- light supplies the wall strokes the dark variant
    # buries (_build_light_wall_mask, cascade strategy #1), and dark supplies the stable
    # hue that separates rooms from each other. Running the primary ALONE is therefore a
    # supported-but-weaker mode, and it is worth a baseline of its own because it is the
    # configuration that reproduces the historical merge defect: measured, the largest
    # component goes from 77.7% of the frame paired to 94.2% alone -- "the full map being
    # called a room". If that number drifts, something in the merge handling moved.
    "dark_alone_min1200_degraded": {
        "image": "localized_map_dark.png",
        "kwargs": {"min_area_pixels": 1200, "image_variant": "dark"},
    },
}

#: Per-segment fields the baseline pins. `polygon_pixel` is the point of the exercise;
#: the rest localise a diff to a segment so a failure says WHICH room moved.
_FIELDS = (
    "segment_id",
    "polygon_pixel",
    "area_pixels",
    "bbox",
    "structural_role",
    "segmentation_state",
    "quality",
    "confidence",
)


def _call_kwargs(case):
    kwargs = dict(case["kwargs"])
    assist = kwargs.pop("assist_image", None)
    out = {"image_path": os.path.join(_FIXTURES, case["image"])}
    if assist:
        out["assist_image_path"] = os.path.join(_FIXTURES, assist)
    out.update(kwargs)
    return out


def _normalise(value):
    """Round every float recursively, so float noise can never read as a real change.

    Determinism was measured exact on this image, so this is belt-and-braces rather than
    load-bearing - but it costs nothing and it keeps a future runner's last-bit wobble
    from being reported as geometry moving.
    """
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    return value


def geometry_record(result):
    """A canonical, comparable record of one run: geometry, stage counters, and mode."""
    segments = []
    for seg in (result.get("segments") or []):
        row = {}
        for field in _FIELDS:
            value = seg.get(field)
            if field == "confidence" and value is not None:
                value = round(float(value), 6)
            row[field] = value
        row["issues"] = sorted(seg.get("issues") or [])
        segments.append(row)
    # Sorted by a STABLE key, so a re-ordering upstream is not read as a geometry change.
    segments.sort(key=lambda row: (str(row.get("segment_id")), json.dumps(row.get("bbox"))))

    # THE STAGE COUNTERS ARE THE LOCALISATION SURFACE, per doc 25 S5: "a bad result
    # localises to a stage before anyone touches a threshold". Polygons alone say that
    # something moved; these say WHICH of the six stages moved it, which is the
    # difference between a finding you can act on and a diff you have to bisect.
    stages = ((result.get("segmentation") or {}).get("stages")) or {}

    return {
        "available": result.get("available"),
        "reason": result.get("reason"),
        # Pinned because doc 25 S3 promises "the result's message says which mode it ran
        # in" - the paired run names the assist variants and the degraded run does not.
        # That is a user-facing promise, so a reword SHOULD redden this.
        "message": result.get("message"),
        "segment_count": len(segments),
        "stages": _normalise(stages),
        "segments": _normalise(segments),
    }


def build():
    from custom_components.eufy_vacuum.adapters.eufy.segmentor import detect_room_segments

    out = {}
    for name, case in sorted(CASES.items()):
        out[name] = geometry_record(detect_room_segments(**_call_kwargs(case)))
    return out


def _render(payload):
    return json.dumps(payload, indent=1, sort_keys=True) + "\n"


def _diff(expected, actual):
    """Human-readable, per-segment. Says WHICH room moved, not just that something did."""
    problems = []
    for name in sorted(set(expected) | set(actual)):
        if name not in expected:
            problems.append("  case %s is NEW (not in the baseline)" % name)
            continue
        if name not in actual:
            problems.append("  case %s is MISSING from this run" % name)
            continue
        want, got = expected[name], actual[name]
        for field in ("available", "reason", "segment_count", "message"):
            if want.get(field) != got.get(field):
                problems.append("  %s: %s\n      baseline: %r\n      this run: %r"
                                % (name, field, want.get(field), got.get(field)))

        # Stage counters first: they say WHICH stage moved, so reading them before the
        # per-segment diff usually means not needing the per-segment diff at all.
        want_stages = want.get("stages") or {}
        got_stages = got.get("stages") or {}
        for stage in sorted(set(want_stages) | set(got_stages)):
            if stage not in want_stages:
                problems.append("  %s: stage %s is NEW" % (name, stage))
                continue
            if stage not in got_stages:
                problems.append("  %s: stage %s is GONE" % (name, stage))
                continue
            a, b = want_stages[stage], got_stages[stage]
            if a == b:
                continue
            if isinstance(a, dict) and isinstance(b, dict):
                for counter in sorted(set(a) | set(b)):
                    if a.get(counter) != b.get(counter):
                        left = json.dumps(a.get(counter), sort_keys=True)
                        right = json.dumps(b.get(counter), sort_keys=True)
                        problems.append("  %s: stage %s.%s\n      baseline: %s\n      this run: %s"
                                        % (name, stage, counter, left[:300], right[:300]))
            else:
                problems.append("  %s: stage %s changed" % (name, stage))

        by_id_want = {s.get("segment_id"): s for s in want.get("segments") or []}
        by_id_got = {s.get("segment_id"): s for s in got.get("segments") or []}
        for seg_id in sorted(set(by_id_want) | set(by_id_got), key=str):
            if seg_id not in by_id_want:
                problems.append("  %s/%s: NEW segment" % (name, seg_id))
                continue
            if seg_id not in by_id_got:
                problems.append("  %s/%s: segment GONE" % (name, seg_id))
                continue
            for field in sorted(set(by_id_want[seg_id]) | set(by_id_got[seg_id])):
                a, b = by_id_want[seg_id].get(field), by_id_got[seg_id].get(field)
                if a != b:
                    problems.append("  %s/%s: %s\n      baseline: %s\n      this run: %s"
                                    % (name, seg_id, field, a, b))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed baseline and change nothing")
    parser.add_argument("--print-digest", action="store_true",
                        help="print a short digest per case (determinism spot-check)")
    args = parser.parse_args(argv)

    sys.path.insert(0, _HERE)
    payload = build()

    if args.print_digest:
        import hashlib
        for name in sorted(payload):
            blob = json.dumps(payload[name], sort_keys=True).encode()
            print("  %-34s n=%-3d %s"
                  % (name, payload[name]["segment_count"],
                     hashlib.sha256(blob).hexdigest()[:16]))

    if args.check:
        if not os.path.exists(_BASELINE):
            print("baseline MISSING at %s -- generate it first" % _BASELINE, file=sys.stderr)
            return 1
        with open(_BASELINE, encoding="utf-8") as handle:
            expected = json.load(handle)
        problems = _diff(expected.get("cases") or {}, payload)
        if problems:
            print("CV GEOMETRY MOVED -- %d difference(s):" % len(problems), file=sys.stderr)
            for line in problems:
                print(line, file=sys.stderr)
            print("", file=sys.stderr)
            print("This is a FINDING, not a chore. Do not regenerate to make it pass:",
                  file=sys.stderr)
            print("work out why the geometry moved, decide whether the new output is",
                  file=sys.stderr)
            print("intended, and regenerate only in the same commit as the cause.",
                  file=sys.stderr)
            return 1
        print("CV geometry matches the baseline (%d cases, %d segments)"
              % (len(payload), sum(c["segment_count"] for c in payload.values())))
        return 0

    document = {
        "_what": "What the Eufy CV segmentor ACTUALLY produces per fixture, imperfections"
                 " included. These are not ideal polygons; they are the algorithm's own"
                 " output before a human corrects it with the adjustment tools.",
        "_rule": "NEVER regenerate this file to make a test pass. A diff is a finding."
                 " Investigate, confirm the new output is intended, then regenerate in"
                 " the same commit as the change that caused it.",
        "_generator": "scripts/gen_cv_geometry_baseline.py",
        "cases": payload,
    }
    with open(_BASELINE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_render(document))
    print("wrote %s (%d bytes, %d cases, %d segments)"
          % (_BASELINE, os.path.getsize(_BASELINE), len(payload),
             sum(c["segment_count"] for c in payload.values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
