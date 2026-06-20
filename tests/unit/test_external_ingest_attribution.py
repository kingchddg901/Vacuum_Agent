"""Unit tests for W5c pose-attribution in learning.external_ingest — pure, HA-free.

Covers the two ways the room-attribution classifier feeds the external-review wizard:
  - ENRICH (`_apply_pose_identity`): label each counter segment with its dominant cleaned
    room and promote it to shortlist[0] (robust mode only; the card pre-selects shortlist[0]).
  - STAND ALONE (`build_attributed_job` / `build_pending_record` with no counter signal):
    build a pending record straight from pose when the counter segmenter found nothing —
    this morning's live scenario (clean a room, park at the dock; dock excluded).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from custom_components.eufy_vacuum.learning.external_ingest import (
    _apply_pose_identity,
    _dominant_cleaned_room,
    build_attributed_job,
    build_pending_record,
)

_BASE = datetime(2026, 6, 20, 8, 13, 0)


def _seg_t(sec: int) -> str:
    """A counter segment boundary timestamp — naive UTC (no 'Z'), like segment_counters."""
    return (_BASE + timedelta(seconds=sec)).isoformat()


def _pose_t(sec: int) -> str:
    """A pose sample timestamp — '...Z', like the run-active sampler records."""
    return (_BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _c(sec: int, ct: float, ca: float) -> dict:
    return {"t": _seg_t(sec), "cleaning_time": ct, "cleaning_area": ca, "battery": 100}


def _ss(sec: int, settings: dict) -> dict:
    return {"t": _seg_t(sec), "settings": settings}


_ROOMS = {
    "5": {"slug": "kitchen", "name": "Kitchen", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "8": {"slug": "dining_room", "name": "Dining Room", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "9": {"slug": "office", "name": "Office", "floor_type": "hardwood", "clean_mode": "vacuum"},
}


def _clean(rid: int, start_sec: int, n: int, area0: float, step: float) -> list[dict]:
    """A cleaned run: zigzag anchors (high winding) + rising cleaning_area (real swept)."""
    pts = [(0.0, 0.0), (0.1, 0.1)]
    return [
        {"t": _pose_t(start_sec + 2 * i), "current_room": rid,
         "anchor": list(pts[i % 2]), "cleaning_area": area0 + i * step}
        for i in range(n)
    ]


def _park(rid: int, start_sec: int, n: int, area: float) -> list[dict]:
    """A parked dock: tiny anchor jitter + FLAT cleaning_area (~0 swept)."""
    pts = [(0.5, 0.5), (0.51, 0.51)]
    return [
        {"t": _pose_t(start_sec + 2 * i), "current_room": rid,
         "anchor": list(pts[i % 2]), "cleaning_area": area}
        for i in range(n)
    ]


# --- _dominant_cleaned_room (window identity) -------------------------------


def test_dominant_cleaned_room_majority_in_window():
    pose = (
        [{"t": _pose_t(s), "current_room": 5} for s in range(60, 101, 2)]
        + [{"t": _pose_t(s), "current_room": 8} for s in range(102, 121, 2)]
    )
    # room 5 has the most ticks in [60,120]; only cleaned rooms are eligible.
    assert _dominant_cleaned_room(pose, _seg_t(60), _seg_t(120), {5, 8}) == 5
    assert _dominant_cleaned_room(pose, _seg_t(60), _seg_t(120), {8}) == 8  # 5 not cleaned -> 8
    assert _dominant_cleaned_room(pose, _seg_t(300), _seg_t(360), {5, 8}) is None  # none in window


# --- _apply_pose_identity (enrich counter segments) -------------------------


def test_apply_pose_identity_promotes_room_robust():
    segs = [
        {"order": 0, "t_start": _seg_t(60), "t_end": _seg_t(120),
         "shortlist": [{"room_id": 8, "slug": "dining_room"}, {"room_id": 5, "slug": "kitchen"}]},
        {"order": 1, "t_start": _seg_t(540), "t_end": _seg_t(600),
         "shortlist": [{"room_id": 8, "slug": "dining_room"}]},
    ]
    pose = (
        [{"t": _pose_t(s), "current_room": 5} for s in range(60, 121, 2)]
        + [{"t": _pose_t(s), "current_room": 9} for s in range(540, 601, 2)]
    )
    attribution = {"cleaned": {5, 9}, "mode": "robust", "per_room": {}, "verdicts": {}}
    _apply_pose_identity(segs, pose, attribution, _ROOMS)
    assert segs[0]["shortlist"][0]["room_id"] == 5 and segs[0]["pose_room_id"] == 5
    assert segs[0]["shortlist"][0]["from_pose"] is True
    assert segs[1]["shortlist"][0]["room_id"] == 9 and segs[1]["pose_room_id"] == 9
    assert segs[0]["pose_mode"] == "robust"


def test_apply_pose_identity_skipped_in_anchor_only():
    """anchor-only attribution can false-positive a parked dock, so it must NOT override the
    settings-based shortlist of a counter-segmented record."""
    segs = [{"order": 0, "t_start": _seg_t(60), "t_end": _seg_t(120),
             "shortlist": [{"room_id": 8, "slug": "dining_room"}]}]
    pose = [{"t": _pose_t(s), "current_room": 5} for s in range(60, 121, 2)]
    attribution = {"cleaned": {5}, "mode": "anchor_only", "per_room": {}, "verdicts": {}}
    _apply_pose_identity(segs, pose, attribution, _ROOMS)
    assert segs[0]["shortlist"][0]["room_id"] == 8  # unchanged
    assert "pose_room_id" not in segs[0]


# --- build_attributed_job (stand-alone pose-only record) --------------------


def test_build_attributed_job_stands_up_pose_only_record():
    attribution = {
        "cleaned": {5, 9}, "mode": "robust", "interval_s": 2.0,
        "per_room": {5: {"swept_area_m2": 6.0}, 9: {"swept_area_m2": 2.0}}, "verdicts": {},
    }
    pose = (
        [{"t": _pose_t(s), "current_room": 5} for s in range(0, 24, 2)]
        + [{"t": _pose_t(s), "current_room": 9} for s in range(24, 60, 2)]
        + [{"t": _pose_t(s), "current_room": 8} for s in range(60, 80, 2)]  # 8 not cleaned
    )
    rec = build_attributed_job(
        detection_ts=_BASE.isoformat(), map_id="6", pose_samples=pose,
        attribution=attribution, settings_samples=[], rooms=_ROOMS, baselines=[],
    )
    assert rec["source"] == "pose_attribution" and rec["attribution_mode"] == "robust"
    assert rec["segment_count"] == 2  # only the two cleaned rooms; dock (8) excluded
    assert [s["shortlist"][0]["room_id"] for s in rec["segments"]] == [5, 9]  # first-seen order
    assert [s["pose_room_id"] for s in rec["segments"]] == [5, 9]
    assert rec["segments"][0]["area_m2"] == 6.0 and rec["segments"][1]["area_m2"] == 2.0
    assert all(s["boundary"] == "pose_attribution" for s in rec["segments"])
    assert "counter_samples" not in rec and rec["candidates"] == []  # not counter-resegmentable


def test_build_attributed_job_none_when_nothing_cleaned():
    assert build_attributed_job(
        detection_ts="x", map_id="6", pose_samples=[{"t": _pose_t(0), "current_room": 8}],
        attribution={"cleaned": set(), "mode": "robust", "per_room": {}, "interval_s": 2.0},
        settings_samples=[], rooms=_ROOMS, baselines=[],
    ) is None
    assert build_attributed_job(
        detection_ts="x", map_id="6", pose_samples=[], attribution=None,
        settings_samples=[], rooms=_ROOMS, baselines=[],
    ) is None


# --- build_pending_record end-to-end (real Eufy engine, vacuum_entity_id=None) ---


def test_build_pending_record_stand_alone_from_pose():
    """The live scenario: counter found no plateaus, but pose recovers the cleaned room and
    excludes the parked dock — a run that would otherwise be lost now opens a pre-answered wizard."""
    pose = _clean(5, 0, 14, 0.0, 0.2) + _park(8, 28, 30, 2.6)
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=[], settings_samples=[], rooms=_ROOMS, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None
    assert rec["source"] == "pose_attribution" and rec["attribution_mode"] == "robust"
    assert [s["pose_room_id"] for s in rec["segments"]] == [5]  # dock (8) excluded
    assert rec["segments"][0]["shortlist"][0]["room_id"] == 5
    assert rec["segments"][0]["area_m2"] > 0.5
    assert "counter_samples" not in rec


def test_build_pending_record_no_pose_is_pre_w5c():
    """No pose stream → attribution is None and the record is exactly the pre-W5c shape
    (a counter record with attribution_mode=None and no pose fields)."""
    counter = [_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3)]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=[_ss(30, {"clean_mode": "vacuum"})],
        rooms=_ROOMS, baselines=[], vacuum_entity_id=None, pose_samples=None,
    )
    assert rec["attribution_mode"] is None
    assert "source" not in rec  # a counter record, not pose-only
    assert "pose_room_id" not in rec["segments"][0]
    assert rec["counter_samples"]  # counter-resegmentable


def test_attribution_engine_error_degrades_to_counter(monkeypatch):
    """P1 (review): an attribution-engine exception must NOT lose the run — _attribute catches
    it and build_pending_record falls through to the counter-only path (attribution_mode None)."""
    import custom_components.eufy_vacuum.learning.external_ingest as ei

    class _Boom:
        DEFAULT_TUNING = {"interval_s": 2.0}

        def attribute(self, *a, **k):
            raise RuntimeError("engine boom")

    monkeypatch.setattr(ei, "get_room_attribution_engine", lambda name: _Boom())
    counter = [_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3)]
    pose = [{"t": _pose_t(s), "current_room": 5} for s in range(0, 90, 2)]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=[_ss(30, {"clean_mode": "vacuum"})],
        rooms=_ROOMS, baselines=[], vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None                  # the run is still captured (counter record)
    assert rec["attribution_mode"] is None  # degraded — no pose identity
    assert "source" not in rec and "pose_room_id" not in rec["segments"][0]


def test_attribution_engine_error_no_counter_returns_none(monkeypatch):
    """P1: engine error + no counter signal → None (the run yields no record) but NO exception
    propagates (so the finalize still clears the slot)."""
    import custom_components.eufy_vacuum.learning.external_ingest as ei

    class _Boom:
        DEFAULT_TUNING = {"interval_s": 2.0}

        def attribute(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(ei, "get_room_attribution_engine", lambda name: _Boom())
    pose = [{"t": _pose_t(s), "current_room": 5} for s in range(0, 30, 2)]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=[], settings_samples=[], rooms=_ROOMS, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is None


def test_build_pending_record_enrich_counter_with_pose():
    """Counter segments own time/area; robust pose promotes the cleaned room to shortlist[0]
    and tags the record robust. Pose places room 9 over the second (vacuum) segment whose
    settings-ranked top would otherwise be hall/kitchen."""
    counter = [
        _c(0, 0, 0),
        _c(60, 30, 1), _c(90, 60, 2), _c(120, 90, 3),       # segment A: sec 60-120
        _c(540, 120, 3), _c(570, 150, 5), _c(600, 180, 6),  # wash plateau -> segment B: 540-600
    ]
    settings = [_ss(60, {"clean_mode": "vacuum"})]
    pose = (
        _clean(5, 60, 30, 0.0, 0.2)     # room 5 across segment A's window
        + _clean(9, 540, 30, 6.0, 0.2)  # room 9 across segment B's window
    )
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=settings, rooms=_ROOMS, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None and rec["attribution_mode"] == "robust"
    assert rec["segment_count"] == 2
    assert rec["segments"][0]["pose_room_id"] == 5
    assert rec["segments"][0]["shortlist"][0]["room_id"] == 5
    assert rec["segments"][1]["pose_room_id"] == 9
    assert rec["segments"][1]["shortlist"][0]["room_id"] == 9
    assert rec["counter_samples"]  # still a counter record (resegmentable)
