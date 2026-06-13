"""Unit tests for mapping/trace_segmentation.py — pure trace-splitting pipeline.

Coverage targets
----------------
[TS-1]  _parse_ts: ISO string → timestamp float; None/garbage → None.
[TS-2]  _dist: Euclidean distance.
[TS-3]  _rolling_mean: trailing-window mean per index.
[TS-4]  _local_density: per-sample neighbor count within radius.
[TS-5]  _extract_samples: drops non-dict and x/y-missing entries.
[TS-6]  _compute_per_sample_signals: parallel lists, speeds/time_gaps from ts.
[TS-7]  _compute_per_sample_signals: inside_polygon filled when polygon supplied.
[TS-8]  _find_split_points: n < 2 → [].
[TS-9]  _find_split_points: a pause gap produces a hard split at that index.
[TS-10] _build_segments: empty samples → [].
[TS-11] _build_segments: split point yields two contiguous segments.
[TS-12] _merge_short_segments: a sub-threshold segment is absorbed.
[TS-13] _merge_similar_segments: behaviourally identical neighbors merge.
[TS-14] _reindex: rewrites segment_index to list position.
[TS-15] segment_trace_run: < 2 samples → insufficient_samples error.
[TS-16] segment_trace_run: pause gap counted as a hard boundary in diagnostics.
[TS-17] segment_trace_run: well-formed result keys on a valid run.
[TS-18] _find_split_points: speed_drop + boundary_crossing fire a soft split.
[TS-19] _find_split_points: density_drop + boundary_crossing fire a soft split.
[TS-20] _merge_short_segments: a short FINAL segment merges into its left neighbor.
[TS-21] _merge_short_segments: a short MIDDLE segment merges into the smaller (left) neighbor.
[TS-22] _merge_short_segments: a short MIDDLE segment merges into the smaller (right) neighbor.
[TS-23] _merge_short_segments: equal-size neighbors — the tie goes to the left neighbor.
[TS-24] _merge_similar_segments: two adjacent zero-density segments are density-similar and merge.
[TS-25] _merge_similar_segments: one zero-density + one non-zero neighbor are NOT similar (no merge, no ZeroDivisionError).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.eufy_vacuum.mapping import trace_segmentation as tseg
from custom_components.eufy_vacuum.mapping.trace_segmentation import (
    _build_segments,
    _compute_per_sample_signals,
    _dist,
    _extract_samples,
    _find_split_points,
    _local_density,
    _merge_short_segments,
    _merge_similar_segments,
    _parse_ts,
    _reindex,
    _rolling_mean,
    segment_trace_run,
)


_T0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


def _mk_samples(deltas: list[float], x_step: float = 5.0) -> list[dict]:
    """Build samples spaced by `deltas` seconds, moving x by x_step each step."""
    t = _T0
    x = 0.0
    samples = [{"x": x, "y": 0.0, "ts": t.isoformat()}]
    for d in deltas:
        t = t + timedelta(seconds=d)
        x += x_step
        samples.append({"x": x, "y": 0.0, "ts": t.isoformat()})
    return samples


def _seg(idx, start, end, *, speed=10.0, density=5.0, br=0.5):
    count = end - start + 1
    return {
        "segment_index": idx,
        "start_index": start,
        "end_index": end,
        "sample_count": count,
        "started_at": _T0.isoformat(),
        "ended_at": (_T0 + timedelta(seconds=count)).isoformat(),
        "duration_seconds": float(count),
        "split_reason": None,
        "diagnostics": {
            "mean_speed": speed, "mean_density": density,
            "boundary_state": "mixed", "boundary_ratio": br,
        },
    }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_parse_ts():
    """[TS-1]"""
    assert _parse_ts("2026-01-01T10:00:00+00:00") == pytest.approx(_T0.timestamp())
    assert _parse_ts(None) is None
    assert _parse_ts("garbage") is None


def test_dist():
    """[TS-2]"""
    assert _dist(0, 0, 3, 4) == pytest.approx(5.0)


def test_rolling_mean():
    """[TS-3]"""
    assert _rolling_mean([1.0, 2.0, 3.0, 4.0], 2) == [1.0, 1.5, 2.5, 3.5]


def test_local_density():
    """[TS-4] x at 0,5,10; radius 7 → ends see 1 neighbor, middle sees 2."""
    samples = [{"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 10, "y": 0}]
    assert _local_density(samples, 7.0) == [1.0, 2.0, 1.0]


def test_extract_samples_filters():
    """[TS-5]"""
    run = {"samples": [{"x": 1, "y": 2}, "str", {"x": "a", "y": 1}, {"y": 5}]}
    out = _extract_samples(run)
    assert len(out) == 1 and out[0] == {"x": 1, "y": 2}


def test_extract_samples_non_list():
    """[TS-5]"""
    assert _extract_samples({"samples": "nope"}) == []


def test_compute_signals_shapes():
    """[TS-6]"""
    samples = _mk_samples([2, 2, 2])
    sig = _compute_per_sample_signals(samples, None)
    assert len(sig["speeds"]) == len(samples)
    assert sig["speeds"][0] is None              # first has no previous
    assert sig["time_gaps"][1] == pytest.approx(2.0)
    assert sig["speeds"][1] == pytest.approx(2.5)  # 5 units / 2 s
    assert all(v is None for v in sig["inside_polygon"])


def test_compute_signals_polygon():
    """[TS-7] a polygon covering all points → inside_polygon all True."""
    samples = _mk_samples([2, 2])
    poly = [[-100.0, -100.0], [100.0, -100.0], [100.0, 100.0], [-100.0, 100.0]]
    sig = _compute_per_sample_signals(samples, poly)
    assert all(v is True for v in sig["inside_polygon"])


def test_find_split_points_too_short():
    """[TS-8]"""
    assert _find_split_points([{"x": 0, "y": 0}], {"speeds": [None], "time_gaps": [None],
                                                   "density": [0.0], "inside_polygon": [None]}) == []


def test_find_split_points_pause():
    """[TS-9] a 10s gap between sample 2 and 3 → hard split at index 3."""
    samples = _mk_samples([2, 2, 10, 2, 2])
    sig = _compute_per_sample_signals(samples, None)
    splits = _find_split_points(samples, sig)
    pause_indices = [p["index"] for p in splits if p["reason"].startswith("pause:")]
    assert 3 in pause_indices


# ---------------------------------------------------------------------------
# Segment construction + merges
# ---------------------------------------------------------------------------

def test_build_segments_empty():
    """[TS-10]"""
    assert _build_segments([], [], {"speeds": [], "time_gaps": [], "density": [],
                                    "inside_polygon": []}, None) == []


def test_build_segments_split():
    """[TS-11] one split → two contiguous segments covering all samples."""
    samples = _mk_samples([2, 2, 2, 2, 2])  # 6 samples, indices 0..5
    sig = _compute_per_sample_signals(samples, None)
    segs = _build_segments(samples, [{"index": 3, "reason": "pause:10s"}], sig, None)
    assert len(segs) == 2
    assert segs[0]["start_index"] == 0 and segs[0]["end_index"] == 2
    assert segs[1]["start_index"] == 3 and segs[1]["end_index"] == 5


def test_merge_short_segments():
    """[TS-12] a 3-sample segment beside a 30-sample one is absorbed."""
    segs = [_seg(0, 0, 2), _seg(1, 3, 32)]  # 3 samples + 30 samples
    merged, count = _merge_short_segments(segs)
    assert count >= 1
    assert len(merged) == 1
    assert merged[0]["sample_count"] == 33


def test_merge_similar_segments():
    """[TS-13] two adjacent segments with identical speed/density merge."""
    segs = [_seg(0, 0, 19, speed=10.0, density=5.0),
            _seg(1, 20, 39, speed=10.0, density=5.0)]
    merged, count = _merge_similar_segments(segs)
    assert count == 1
    assert len(merged) == 1
    assert merged[0]["end_index"] == 39


def test_reindex():
    """[TS-14]"""
    segs = [_seg(7, 0, 5), _seg(9, 6, 11)]
    out = _reindex(segs)
    assert [s["segment_index"] for s in out] == [0, 1]


# ---------------------------------------------------------------------------
# segment_trace_run
# ---------------------------------------------------------------------------

def test_segment_run_insufficient():
    """[TS-15]"""
    result = segment_trace_run({"run_id": "r1", "samples": [{"x": 0, "y": 0}]})
    assert result["error"] == "insufficient_samples:1"
    assert result["segment_count"] == 0


def test_segment_run_counts_pause():
    """[TS-16] a pause gap is recorded as a hard boundary even if segments merge back."""
    samples = _mk_samples([2, 2, 10, 2, 2])
    result = segment_trace_run({"run_id": "r1", "samples": samples})
    assert result["error"] is None
    assert result["diagnostics"]["hard_boundaries"] == 1
    assert result["diagnostics"]["total_samples"] == 6


def test_segment_run_result_keys():
    """[TS-17]"""
    samples = _mk_samples([2] * 10)
    result = segment_trace_run({"run_id": "r1", "vacuum_entity_id": "vacuum.alfred",
                                "map_id": "6", "samples": samples})
    for key in ("run_id", "vacuum_entity_id", "map_id", "room_id", "error",
                "segment_count", "segments", "diagnostics"):
        assert key in result
    assert result["run_id"] == "r1"
    assert isinstance(result["segments"], list)


# ---------------------------------------------------------------------------
# Soft multi-signal splits (need 2+ signals agreeing over the sustain window)
# ---------------------------------------------------------------------------

_SQUARE = [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]]


def _xy_samples(coords: list[tuple[float, float]], dt: float = 2.0) -> list[dict]:
    """Build samples from explicit (x, y) coords spaced dt seconds apart."""
    t = _T0
    out = []
    for x, y in coords:
        out.append({"x": float(x), "y": float(y), "ts": t.isoformat()})
        t = t + timedelta(seconds=dt)
    return out


def _soft_reasons(samples, poly):
    sig = _compute_per_sample_signals(samples, poly)
    splits = _find_split_points(samples, sig)
    return [p["reason"] for p in splits if not p["reason"].startswith("pause:")]


def test_find_split_speed_and_boundary():
    """[TS-18] fast inside (x=95) then a slow exit past the right edge."""
    coords = [(95.0, 10.0 if k % 2 == 0 else 90.0) for k in range(14)]   # fast, inside
    coords += [(101.0, 90.0), (102.0, 90.0), (103.0, 90.0),
               (104.0, 90.0), (105.0, 90.0)]                              # slow, outside
    reasons = _soft_reasons(_xy_samples(coords), _SQUARE)
    assert any("speed_drop" in r and "boundary_crossing" in r for r in reasons)


def test_find_split_density_and_boundary():
    """[TS-19] dense cluster inside then a fast, spread-out exit (low density)."""
    coords = [(50.0 + (k % 2) * 10.0, 45.0 + (k % 4) * 3.0) for k in range(14)]  # dense, inside
    coords += [(110.0, 50.0), (170.0, 50.0), (230.0, 50.0),
               (290.0, 50.0), (350.0, 50.0)]                                     # sparse, outside
    reasons = _soft_reasons(_xy_samples(coords), _SQUARE)
    assert any("density_drop" in r and "boundary_crossing" in r for r in reasons)


def test_merge_short_segments_merges_last_into_left():
    """[TS-20] a short FINAL segment merges into its left neighbor (the
    i == len(segments) - 1 branch); a <=0.1 boundary_ratio recomputes as 'outside'."""
    def _seg(si, ei, n, br):
        return {"start_index": si, "end_index": ei, "sample_count": n,
                "started_at": "2026-01-01T00:00:00+00:00",
                "ended_at": "2026-01-01T00:01:00+00:00", "split_reason": "x",
                "diagnostics": {"mean_speed": 1.0, "mean_density": 1.0,
                                "boundary_ratio": br, "boundary_state": "outside"}}
    segs = [_seg(0, 19, 20, 0.05), _seg(20, 22, 3, 0.05)]  # last is short (<15)
    out, count = tseg._merge_short_segments(segs)
    assert count == 1 and len(out) == 1
    assert out[0]["sample_count"] == 23
    assert out[0]["diagnostics"]["boundary_state"] == "outside"


def test_merge_short_segments_middle_into_smaller_left():
    """[TS-21] a short MIDDLE segment merges into its SMALLER (left) neighbor
    (the `segments[i-1].sample_count <= segments[i+1].sample_count -> target=i-1`
    branch). left=14, middle=3(<15), right=30 -> middle absorbed left; right intact."""
    segs = [_seg(0, 0, 13), _seg(1, 14, 16), _seg(2, 17, 46)]  # 14, 3, 30 samples
    merged, count = _merge_short_segments(segs)
    assert count == 1
    assert len(merged) == 2
    # Middle (3) absorbed into the LEFT neighbor (14 < 30).
    assert merged[0]["start_index"] == 0
    assert merged[0]["end_index"] == 16
    assert merged[0]["sample_count"] == 17
    # The larger right neighbor survives unmerged.
    assert merged[1]["start_index"] == 17
    assert merged[1]["end_index"] == 46
    assert merged[1]["sample_count"] == 30


def test_merge_short_segments_middle_into_smaller_right():
    """[TS-22] a short MIDDLE segment merges into its SMALLER (right) neighbor
    (the `else -> target=i+1` branch). left=30, middle=3(<15), right=14 ->
    middle absorbed right; left intact."""
    segs = [_seg(0, 0, 29), _seg(1, 30, 32), _seg(2, 33, 46)]  # 30, 3, 14 samples
    merged, count = _merge_short_segments(segs)
    assert count == 1
    assert len(merged) == 2
    # The larger left neighbor survives unmerged.
    assert merged[0]["start_index"] == 0
    assert merged[0]["end_index"] == 29
    assert merged[0]["sample_count"] == 30
    # Middle (3) absorbed into the RIGHT neighbor (14 < 30).
    assert merged[1]["start_index"] == 30
    assert merged[1]["end_index"] == 46
    assert merged[1]["sample_count"] == 17


def test_merge_short_segments_middle_tie_prefers_left():
    """[TS-23] equal-size neighbors -> the `<=` tie goes to the LEFT neighbor
    (target=i-1). left=20, middle=3(<15), right=20 -> middle absorbed left."""
    segs = [_seg(0, 0, 19), _seg(1, 20, 22), _seg(2, 23, 42)]  # 20, 3, 20 samples
    merged, count = _merge_short_segments(segs)
    assert count == 1
    assert len(merged) == 2
    # Tie resolves to the LEFT neighbor.
    assert merged[0]["start_index"] == 0
    assert merged[0]["end_index"] == 22
    assert merged[0]["sample_count"] == 23
    # Right neighbor survives unmerged.
    assert merged[1]["start_index"] == 23
    assert merged[1]["end_index"] == 42
    assert merged[1]["sample_count"] == 20


def test_merge_similar_segments_both_zero_density():
    """[TS-24] two adjacent zero-density segments are density-similar and merge
    (the `density_a == 0 and density_b == 0` elif branch)."""
    segs = [_seg(0, 0, 19, speed=10.0, density=0.0),
            _seg(1, 20, 39, speed=10.0, density=0.0)]
    merged, count = _merge_similar_segments(segs)
    assert count == 1
    assert len(merged) == 1
    assert merged[0]["end_index"] == 39
    assert merged[0]["diagnostics"]["mean_density"] == 0.0


def test_merge_similar_segments_mismatched_density_no_merge():
    """[TS-25] one zero-density and one non-zero-density neighbor are NOT
    density-similar — they stay split and no ZeroDivisionError is raised."""
    segs = [_seg(0, 0, 19, speed=10.0, density=0.0),
            _seg(1, 20, 39, speed=10.0, density=5.0)]
    merged, count = _merge_similar_segments(segs)
    assert count == 0
    assert len(merged) == 2

