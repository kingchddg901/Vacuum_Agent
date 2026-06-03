"""Unit tests for mapping/segmenter_engines.py — engine registry, tuning
validation, and the engine-unavailable result paths (no CV pipeline needed).

Coverage targets
----------------
[SE-1]  get_segmenter_engine: known name returns that engine.
[SE-2]  get_segmenter_engine: None → noop_fallback.
[SE-3]  get_segmenter_engine: unknown name → noop_fallback.
[SE-4]  known_engine_names: includes the registered engines.
[SE-5]  EufyCVSegmenter.validate_tuning: non-dict → single error.
[SE-6]  EufyCVSegmenter.validate_tuning: unknown key flagged.
[SE-7]  EufyCVSegmenter.validate_tuning: bad min_area_pixels flagged.
[SE-8]  EufyCVSegmenter.validate_tuning: bad simplify_epsilon flagged.
[SE-9]  EufyCVSegmenter.validate_tuning: bad expected_room_count flagged.
[SE-10] EufyCVSegmenter.validate_tuning: valid tuning → [].
[SE-11] EufyCVSegmenter.segment_map_image: no image_path → unavailable (no_image_path).
[SE-12] EufyCVSegmenter unavailable result carries a runtime diagnostics block.
[SE-13] NoopSegmenter.validate_tuning: non-dict → error; non-empty → warning; empty → [].
[SE-14] NoopSegmenter.segment_map_image: unavailable with reason "noop", no runtime block.
[SE-15] _engine_unavailable: canonical empty result shape.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.mapping.segmenter_engines import (
    EufyCVSegmenter,
    NoopSegmenter,
    _engine_unavailable,
    get_segmenter_engine,
    known_engine_names,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_get_engine_known():
    """[SE-1]"""
    engine = get_segmenter_engine("eufy_cv_v1")
    assert engine.engine_name == "eufy_cv_v1"


def test_get_engine_none_falls_back():
    """[SE-2]"""
    assert get_segmenter_engine(None).engine_name == "noop_fallback"


def test_get_engine_unknown_falls_back():
    """[SE-3]"""
    assert get_segmenter_engine("does_not_exist").engine_name == "noop_fallback"


def test_eufy_engine_detect_raises_returns_unavailable(monkeypatch):
    """[SE-16] when detect_room_segments raises, the Eufy engine returns a
    canonical engine_unavailable result (engine_exception) rather than
    propagating the exception up the pipeline."""
    from custom_components.eufy_vacuum.mapping import segmenter_engines as se

    def _boom(**kwargs):
        raise RuntimeError("cv exploded")

    monkeypatch.setattr(se, "detect_room_segments", _boom)
    engine = get_segmenter_engine("eufy_cv_v1")
    result = engine.segment_map_image(image_path="/tmp/nope.png", tuning={})
    assert result["available"] is False
    assert result["reason"] == "engine_exception"
    assert result["segments"] == []


def test_known_engine_names():
    """[SE-4]"""
    names = known_engine_names()
    assert "eufy_cv_v1" in names
    assert "noop_fallback" in names


# ---------------------------------------------------------------------------
# EufyCVSegmenter.validate_tuning
# ---------------------------------------------------------------------------

def test_cv_validate_non_dict():
    """[SE-5]"""
    assert EufyCVSegmenter().validate_tuning("nope") == [
        "mapping.segmenter_tuning must be a dict"
    ]


def test_cv_validate_unknown_key():
    """[SE-6]"""
    issues = EufyCVSegmenter().validate_tuning({"bogus_key": 1})
    assert any("unknown tuning key" in i for i in issues)


@pytest.mark.parametrize("value", [0, -5, "x", 1.5])
def test_cv_validate_bad_min_area(value):
    """[SE-7]"""
    issues = EufyCVSegmenter().validate_tuning({"min_area_pixels": value})
    assert any("min_area_pixels" in i for i in issues)


@pytest.mark.parametrize("value", ["x", -1.0])
def test_cv_validate_bad_simplify_epsilon(value):
    """[SE-8]"""
    issues = EufyCVSegmenter().validate_tuning({"simplify_epsilon": value})
    assert any("simplify_epsilon" in i for i in issues)


@pytest.mark.parametrize("value", [-1, "x"])
def test_cv_validate_bad_expected_room_count(value):
    """[SE-9]"""
    issues = EufyCVSegmenter().validate_tuning({"expected_room_count": value})
    assert any("expected_room_count" in i for i in issues)


def test_cv_validate_valid():
    """[SE-10]"""
    tuning = {
        "min_area_pixels": 1200,
        "simplify_epsilon": 2.0,
        "expected_room_count": 5,
        "max_segments": 12,
    }
    assert EufyCVSegmenter().validate_tuning(tuning) == []


def test_cv_validate_simplify_epsilon_none_ok():
    """[SE-8] None is an allowed simplify_epsilon value."""
    assert EufyCVSegmenter().validate_tuning({"simplify_epsilon": None}) == []


# ---------------------------------------------------------------------------
# EufyCVSegmenter.segment_map_image
# ---------------------------------------------------------------------------

def test_cv_segment_no_image_path():
    """[SE-11]"""
    result = EufyCVSegmenter().segment_map_image(image_path=None, tuning={})
    assert result["available"] is False
    assert result["reason"] == "no_image_path"
    assert result["engine"] == "eufy_cv_v1"
    assert result["segments"] == []


def test_cv_unavailable_has_runtime_diagnostics():
    """[SE-12] the CV engine surfaces a runtime-capabilities block on failure."""
    result = EufyCVSegmenter().segment_map_image(image_path="", tuning={})
    assert "runtime" in result["engine_diagnostics"]
    assert "numpy" in result["engine_diagnostics"]["runtime"]


# ---------------------------------------------------------------------------
# NoopSegmenter
# ---------------------------------------------------------------------------

def test_noop_validate():
    """[SE-13]"""
    noop = NoopSegmenter()
    assert noop.validate_tuning("nope") == ["mapping.segmenter_tuning must be a dict"]
    assert any("ignored" in i for i in noop.validate_tuning({"k": 1}))
    assert noop.validate_tuning({}) == []


def test_noop_segment():
    """[SE-14]"""
    result = NoopSegmenter().segment_map_image(image_path="anything", tuning={})
    assert result["available"] is False
    assert result["reason"] == "noop"
    assert result["engine"] == "noop_fallback"
    # noop engines have no library dependency to report
    assert "runtime" not in result["engine_diagnostics"]


# ---------------------------------------------------------------------------
# _engine_unavailable
# ---------------------------------------------------------------------------

def test_engine_unavailable_shape():
    """[SE-15]"""
    result = _engine_unavailable(engine="custom", reason="x", message="m")
    assert result["available"] is False
    assert result["reason"] == "x"
    assert result["message"] == "m"
    assert result["engine"] == "custom"
    assert result["image"] is None
    assert result["segments"] == []
    assert result["summary"]["segment_count"] == 0
    # only the CV engine attaches a runtime block
    assert result["engine_diagnostics"] == {}
