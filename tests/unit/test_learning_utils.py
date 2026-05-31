"""Unit tests for learning/utils — pure Python, no HA dependency."""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.learning.utils import (
    _room_profile_key,
    _safe_bool,
    _safe_float,
    _safe_int,
)


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------

def test_safe_int_integer():
    assert _safe_int(42) == 42


def test_safe_int_float_string():
    assert _safe_int("3.7") == 3


def test_safe_int_none_returns_default():
    assert _safe_int(None) == 0
    assert _safe_int(None, 5) == 5


def test_safe_int_sentinel_strings():
    assert _safe_int("") == 0
    assert _safe_int("unknown") == 0
    assert _safe_int("unavailable") == 0


def test_safe_int_non_numeric_string():
    assert _safe_int("abc") == 0


def test_safe_int_zero():
    assert _safe_int(0) == 0


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

def test_safe_float_float():
    assert _safe_float(3.14) == pytest.approx(3.14)


def test_safe_float_int():
    assert _safe_float(5) == pytest.approx(5.0)


def test_safe_float_none_returns_default():
    assert _safe_float(None) == pytest.approx(0.0)
    assert _safe_float(None, 1.5) == pytest.approx(1.5)


def test_safe_float_sentinel_strings():
    assert _safe_float("") == pytest.approx(0.0)
    assert _safe_float("unknown") == pytest.approx(0.0)
    assert _safe_float("unavailable") == pytest.approx(0.0)


def test_safe_float_string_value():
    assert _safe_float("2.5") == pytest.approx(2.5)


def test_safe_float_non_numeric_string():
    assert _safe_float("abc") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _safe_bool
# ---------------------------------------------------------------------------

def test_safe_bool_true():
    assert _safe_bool(True) is True


def test_safe_bool_false():
    assert _safe_bool(False) is False


def test_safe_bool_truthy_strings():
    for s in ("true", "True", "on", "yes", "1"):
        assert _safe_bool(s) is True, f"Expected True for {s!r}"


def test_safe_bool_falsy_strings():
    for s in ("false", "False", "off", "no", "0"):
        assert _safe_bool(s) is False, f"Expected False for {s!r}"


def test_safe_bool_none_returns_default():
    assert _safe_bool(None) is False
    assert _safe_bool(None, True) is True


def test_safe_bool_sentinel_strings():
    assert _safe_bool("") is False
    assert _safe_bool("unknown") is False
    assert _safe_bool("unavailable") is False


def test_safe_bool_numeric_int():
    assert _safe_bool(1) is True
    assert _safe_bool(0) is False


# ---------------------------------------------------------------------------
# _room_profile_key
# ---------------------------------------------------------------------------

def test_room_profile_key_returns_nine_parts():
    key = _room_profile_key({
        "slug": "kitchen",
        "selected_profile_name": "default",
        "clean_mode": "vacuum",
        "clean_intensity": "standard",
        "fan_speed": "boost",
        "water_level": "off",
        "clean_passes": 1,
        "is_carpet": False,
        "edge_mopping": False,
    })
    assert len(key.split("::")) == 9


def test_room_profile_key_lowercases_slug():
    key = _room_profile_key({"slug": "Master Bedroom"})
    assert key.split("::")[0] == "master bedroom"


def test_room_profile_key_carpet_flag():
    no_carpet = _room_profile_key({"is_carpet": False})
    with_carpet = _room_profile_key({"is_carpet": True})
    assert no_carpet.split("::")[7] == "0"
    assert with_carpet.split("::")[7] == "1"


def test_room_profile_key_edge_mopping_flag():
    no_edge = _room_profile_key({"edge_mopping": False})
    with_edge = _room_profile_key({"edge_mopping": True})
    assert no_edge.split("::")[8] == "0"
    assert with_edge.split("::")[8] == "1"


def test_room_profile_key_resolved_profile_fallback():
    """resolved_profile_name is used when selected_profile_name is absent."""
    room = {"slug": "hall", "resolved_profile_name": "quiet"}
    key = _room_profile_key(room)
    assert key.split("::")[1] == "quiet"


def test_room_profile_key_selected_overrides_resolved():
    room = {"slug": "hall", "selected_profile_name": "deep", "resolved_profile_name": "quiet"}
    key = _room_profile_key(room)
    assert key.split("::")[1] == "deep"


def test_room_profile_key_missing_fields_does_not_raise():
    key = _room_profile_key({})
    assert len(key.split("::")) == 9


def test_room_profile_key_stable():
    room = {"slug": "lounge", "selected_profile_name": "deep", "clean_mode": "vacuum_mop",
            "clean_intensity": "deep", "fan_speed": "max", "water_level": "high",
            "clean_passes": 2, "is_carpet": False, "edge_mopping": True}
    assert _room_profile_key(room) == _room_profile_key(room)


def test_room_profile_key_differs_for_different_settings():
    base = {"slug": "room", "fan_speed": "standard"}
    alt = {**base, "fan_speed": "max"}
    assert _room_profile_key(base) != _room_profile_key(alt)
