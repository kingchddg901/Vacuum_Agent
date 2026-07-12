"""Unit tests for W5c pose-attribution in learning.external_ingest — pure, HA-free.

Covers the two ways the room-attribution classifier feeds the external-review wizard:
  - ENRICH (`_apply_pose_identity`): label each counter segment with its dominant room and
    promote it to shortlist[0] (robust mode only; the card pre-selects shortlist[0]). Prefers a
    swept-area-confirmed room, but falls back to the dominant room of ANY identity when stale
    `cleaning_area` left a real counter segment with no confirmed room (the first-room-dropped bug).
  - STAND ALONE (`build_attributed_job` / `build_pending_record` with no counter signal):
    build a pending record straight from pose when the counter segmenter found nothing —
    this morning's live scenario (clean a room, park at the dock; dock excluded).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from custom_components.eufy_vacuum.learning.external_ingest import (
    _apply_pose_identity,
    _dominant_room,
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


# --- _dominant_room (window identity) ---------------------------------------


def test_dominant_room_majority_in_window():
    pose = (
        [{"t": _pose_t(s), "current_room": 5} for s in range(60, 101, 2)]
        + [{"t": _pose_t(s), "current_room": 8} for s in range(102, 121, 2)]
    )
    # room 5 has the most ticks in [60,120]; when a cleaned set is given only it is eligible.
    assert _dominant_room(pose, _seg_t(60), _seg_t(120), {5, 8}) == 5
    assert _dominant_room(pose, _seg_t(60), _seg_t(120), {8}) == 8  # 5 not cleaned -> 8
    assert _dominant_room(pose, _seg_t(60), _seg_t(120), set()) is None  # nothing cleaned
    assert _dominant_room(pose, _seg_t(60), _seg_t(120)) == 5  # cleaned=None -> any room, 5 wins
    assert _dominant_room(pose, _seg_t(300), _seg_t(360), {5, 8}) is None  # none in window


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
    assert segs[0]["pose_confidence"] == "cleaned"  # both rooms were swept-confirmed


def test_apply_pose_identity_rescues_stale_masked_first_room():
    """The stale-`cleaning_area` bug: the run's FIRST room is cleaned but its swept area is
    masked (the sensor was stuck/flat), so the engine never credits it — `cleaned` holds only
    the LATER room. The counter still split BOTH windows (cleaning_time tracked), so the first
    segment must be named by its dominant room (presence) instead of keeping its wrong
    settings-ranked shortlist[0]. This is attempt #4: Kitchen=5 dropped, Dining=8 confirmed."""
    segs = [
        # First room's window: shortlist[0] is a WRONG settings guess (hallway=4, not shown in
        # _ROOMS on purpose — the bug pre-fills a room that was never cleaned).
        {"order": 0, "t_start": _seg_t(60), "t_end": _seg_t(120),
         "shortlist": [{"room_id": 4, "slug": "hallway"}, {"room_id": 5, "slug": "kitchen"}]},
        {"order": 1, "t_start": _seg_t(540), "t_end": _seg_t(600),
         "shortlist": [{"room_id": 8, "slug": "dining_room"}]},
    ]
    pose = (
        [{"t": _pose_t(s), "current_room": 5} for s in range(60, 121, 2)]   # Kitchen, area-masked
        + [{"t": _pose_t(s), "current_room": 8} for s in range(540, 601, 2)]  # Dining, swept-confirmed
    )
    attribution = {"cleaned": {8}, "mode": "robust", "per_room": {}, "verdicts": {}}
    _apply_pose_identity(segs, pose, attribution, _ROOMS)
    # Kitchen rescued by presence (no cleaned room dominates its window) ...
    assert segs[0]["shortlist"][0]["room_id"] == 5 and segs[0]["pose_room_id"] == 5
    assert segs[0]["pose_confidence"] == "presence"
    # ... while the swept-confirmed Dining room stays a high-confidence label.
    assert segs[1]["shortlist"][0]["room_id"] == 8 and segs[1]["pose_confidence"] == "cleaned"


def test_apply_pose_identity_presence_fallback_when_nothing_cleaned():
    """All rooms area-masked (cleaned empty) but the counter split real segments: every segment
    is still named by presence rather than left with its settings guess."""
    segs = [{"order": 0, "t_start": _seg_t(60), "t_end": _seg_t(120),
             "shortlist": [{"room_id": 4, "slug": "hallway"}]}]
    pose = [{"t": _pose_t(s), "current_room": 5} for s in range(60, 121, 2)]
    attribution = {"cleaned": set(), "mode": "robust", "per_room": {}, "verdicts": {}}
    _apply_pose_identity(segs, pose, attribution, _ROOMS)
    assert segs[0]["shortlist"][0]["room_id"] == 5 and segs[0]["pose_confidence"] == "presence"


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
    assert len(rec["pose_samples"]) == len(pose)  # raw pose embedded for re-attribution


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


def test_records_embed_pose_and_strip_removes_it():
    """Pose is embedded in BOTH record shapes (for server-side re-attribution) and stripped
    before the card ever sees it (mirrors counter_samples)."""
    from custom_components.eufy_vacuum.learning.external_ingest import strip_samples

    pose = _clean(5, 0, 14, 0.0, 0.2) + _park(8, 28, 30, 2.6)

    # stand-alone (pose-only) record embeds pose
    standalone = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=[], settings_samples=[], rooms=_ROOMS, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert standalone["source"] == "pose_attribution"
    assert len(standalone["pose_samples"]) == len(pose)
    assert "pose_samples" not in strip_samples(dict(standalone))  # stripped for the card

    # counter record (enrich) embeds pose alongside counter_samples
    counter = [_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3)]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=[_ss(30, {"clean_mode": "vacuum"})],
        rooms=_ROOMS, baselines=[], vacuum_entity_id=None, pose_samples=pose,
    )
    assert len(rec["pose_samples"]) == len(pose) and rec["counter_samples"]
    stripped = strip_samples(dict(rec))
    assert "pose_samples" not in stripped and "counter_samples" not in stripped


def test_no_pose_means_empty_pose_samples_list():
    """No pose stream → pose_samples is an empty list (stable key), not a missing key."""
    counter = [_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3)]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=[_ss(30, {"clean_mode": "vacuum"})],
        rooms=_ROOMS, baselines=[], vacuum_entity_id=None, pose_samples=None,
    )
    assert rec["pose_samples"] == []


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
    assert rec["attribution_confidence"] is None  # no pose stream → no claim
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
    assert rec["attribution_confidence"] == "available"  # pose named both segments


def test_attribution_confidence_unavailable_when_pose_names_nothing():
    """A pose stream existed but named NO segment (here: current_room never reported) →
    attribution_confidence 'unavailable', so the wizard prompts a MANUAL room pick instead of
    silently defaulting every segment to its settings-ranked shortlist[0]."""
    counter = [_c(0, 0, 0), _c(30, 30, 1), _c(60, 60, 2), _c(90, 90, 3)]
    pose = [
        {"t": _pose_t(s), "current_room": None, "anchor": [0.1 * s, 0.1 * s],
         "cleaning_area": float(s)}
        for s in range(0, 90, 2)
    ]
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=counter, settings_samples=[_ss(30, {"clean_mode": "vacuum"})],
        rooms=_ROOMS, baselines=[], vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None
    assert all(s.get("pose_room_id") is None for s in rec["segments"])
    assert rec["attribution_confidence"] == "unavailable"


# --- REAL-DATA regression: stale cleaning_area drops the first room ----------

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "external_run"


def test_stale_area_first_room_rescued_real_capture():
    """REAL run captured live 2026-06-20 (vacuum.alfred): Kitchen(5) cleaned first while
    cleaning_area was stuck stale, so the engine credited swept area only to Dining(8)
    (cleaned={8}) and the first room was dropped. The counter split both windows, so the
    presence fallback must name segment 0 Kitchen. Pins the [8] -> [5,8] fix against the raw
    562-tick pose stream — a consecutive-delta or anchor-only fix would NOT recover it (the
    sensor was flat-stuck through the whole Kitchen clean; see scratch stale_area_timeline)."""
    fx = json.loads(
        (_FIXTURES / "alfred_stale_area_first_room_2026-06-20.json").read_text(encoding="utf-8")
    )
    rec = build_pending_record(
        detection_ts=fx["started_at"], map_id=fx["map_id"],
        counter_samples=fx["counter_samples"], settings_samples=fx["settings_samples"],
        rooms=fx["rooms"], baselines=[], vacuum_entity_id=fx["vacuum_entity_id"],
        pose_samples=fx["pose_samples"],
    )
    assert rec is not None and rec["attribution_mode"] == "robust"
    segs = rec["segments"]
    captured = {s["shortlist"][0]["room_id"] for s in segs}
    assert {5, 8} <= captured, f"expected Kitchen+Dining, got {sorted(captured)}"
    # segment 0 = Kitchen, rescued by presence (swept-area masked) ...
    assert segs[0]["pose_room_id"] == 5 and segs[0]["pose_confidence"] == "presence"
    # ... segment 1 = Dining, swept-area confirmed.
    assert segs[1]["pose_room_id"] == 8 and segs[1]["pose_confidence"] == "cleaned"


# =============================================================================
# W1 follow-through: the NATIVE current_room sample shape (Roborock — anchor=None).
#
# W1 generalized the pose sampler so a brand that publishes its live room as a NAME entity
# (Roborock) buffers samples with NO pixel anchor and a CUMULATIVE cleaning_area. These lock
# that the shape flows END-TO-END through the SAME stand-alone path Roborock always takes: its
# job-segmenter is `noop_job_fallback`, so counter segmentation finds nothing and every external
# run lands in build_attributed_job. The clean decision is the engine's ROBUST (swept-area) mode
# — pose-free — so anchors are never needed. vacuum_entity_id=None resolves the Eufy fallback
# engine = eufy_anchor_winding_v1, the exact engine Roborock declares (only the robust-mode-
# irrelevant dwell/interval tuning differs), so this is a faithful shape test. Models the
# recorder-verified Ivy runs (reference_roborock_ivy_signals).
# =============================================================================

_ROOMS_IVY = {
    "1": {"slug": "living_room", "name": "Living Room", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "2": {"slug": "cat_room", "name": "Cat Room", "floor_type": "carpet", "clean_mode": "vacuum"},
    "3": {"slug": "hallway", "name": "Hallway", "floor_type": "hardwood", "clean_mode": "vacuum"},
    "4": {"slug": "dining_room", "name": "Dining Room", "floor_type": "hardwood", "clean_mode": "vacuum"},
}


def _native(rid, start_sec: int, n: int, ca0: float, ca_step: float, interval: int = 5) -> list[dict]:
    """A Roborock-shape sample run: NO anchor (native current_room source, not a pixel pose) +
    cumulative cleaning_area (rises by ca_step/tick when cleaning, ca_step=0 when transit/parked).
    A parked/docked tick carries current_room=None (the sampler nulls it off task_status)."""
    return [
        {"t": _pose_t(start_sec + interval * i), "current_room": rid, "anchor": None,
         "cleaning_area": round(ca0 + i * ca_step, 3)}
        for i in range(n)
    ]


def test_native_multiroom_stand_alone_ivy_shape():
    """Ivy multi-room external run in native shape: dock(None) + Living-Room transit excluded;
    Cat (swept 3.1) + Hallway (swept 5.8) cleaned; areas from swept-area, identity pre-filled as
    shortlist[0]. Proves W1's native_current_room samples produce a correct pose-only record with
    NO anchors anywhere in the stream."""
    pose = (
        _native(None, 0, 3, 0.0, 0.0)     # parked at dock: current_room nulled, ca flat
        + _native(1, 15, 3, 0.0, 0.0)     # Living Room transit: ca flat -> swept 0 -> excluded
        + _native(2, 30, 5, 0.0, 0.775)   # Cat cleaned: ca 0.0 -> 3.1
        + _native(3, 55, 6, 3.1, 1.16)    # Hallway cleaned: ca 3.1 -> 8.9 (delta 5.8)
        + _native(None, 85, 3, 8.9, 0.0)  # returned/docked: None, ca flat
    )
    assert all(s["anchor"] is None for s in pose)  # sanity: this IS the anchor-free shape
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=[], settings_samples=[], rooms=_ROOMS_IVY, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None
    assert rec["source"] == "pose_attribution" and rec["attribution_mode"] == "robust"
    by_room = {s["pose_room_id"]: s for s in rec["segments"]}
    assert set(by_room) == {2, 3}  # Cat + Hallway; Living-Room transit + dock(None) excluded
    assert by_room[2]["area_m2"] == 3.1
    assert by_room[3]["area_m2"] == 5.8
    assert all(s["shortlist"][0]["room_id"] == s["pose_room_id"] for s in rec["segments"])


def test_native_revisited_room_area_sums():
    """A room transited (flat area) THEN cleaned (rising) in two separate current_room runs: the
    swept area SUMS across both runs to the real cleaned area, and the room appears ONCE — not
    double-counted, not dropped. Locks the per-room delta-SUM for Roborock's order-agnostic
    revisits (the Hallway pattern in the Ivy capture)."""
    pose = (
        _native(3, 0, 2, 0.0, 0.0)      # Hallway pass-through (transit): ca flat 0 -> swept 0
        + _native(2, 10, 4, 0.0, 1.0)   # Cat cleaned elsewhere: ca 0 -> 3.0
        + _native(3, 30, 5, 3.0, 1.2)   # Hallway cleaned (revisit): ca 3.0 -> 7.8 (delta 4.8)
    )
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=[], settings_samples=[], rooms=_ROOMS_IVY, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None
    hall = [s for s in rec["segments"] if s["pose_room_id"] == 3]
    assert len(hall) == 1            # one Hallway segment, not two
    assert hall[0]["area_m2"] == 4.8  # 0 (transit run) + 4.8 (clean run), summed


def test_native_coarse_area_short_room_undercounted():
    """KNOWN LIMITATION (characterized, not aspirational): Roborock samples current_room every
    ~5s but cleaning_area only refreshes ~15s, so a room cleaned in a SHORT visit can carry <2
    distinct cleaning_area values -> its per-run delta reads 0 -> the swept-area-gated stand-alone
    builder DROPS it. Recoverable (the raw pose is embedded -> human Exclude/Restore + re-attribute
    after a finer-area mitigation), but pinned here so that mitigation has a target. Cat is
    genuinely cleaned yet dropped because its cleaning_area hadn't ticked during the short visit."""
    pose = (
        _native(2, 0, 3, 5.0, 0.0)      # Cat: real clean but cleaning_area flat (hadn't refreshed)
        + _native(3, 15, 6, 5.0, 1.0)   # Hallway: long enough to accrue area 5.0 -> 10.0
    )
    rec = build_pending_record(
        detection_ts=_BASE.isoformat(), map_id="6",
        counter_samples=[], settings_samples=[], rooms=_ROOMS_IVY, baselines=[],
        vacuum_entity_id=None, pose_samples=pose,
    )
    assert rec is not None
    captured = {s["pose_room_id"] for s in rec["segments"]}
    assert captured == {3}  # Hallway kept; Cat under-resolved by coarse area -> dropped (the break)
