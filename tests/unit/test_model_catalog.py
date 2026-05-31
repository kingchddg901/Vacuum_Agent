"""Unit tests for adapters/eufy/model_catalog — pure Python, no HA dependency."""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.eufy.model_catalog import (
    MODEL_CODE_FAMILIES,
    detect_model_family,
)


def test_known_code_x10():
    assert detect_model_family("T2351") == "x10"


def test_known_code_x8():
    assert detect_model_family("T2261") == "x8"


def test_known_code_l60():
    assert detect_model_family("T2267") == "l60"


def test_known_code_lr30():
    assert detect_model_family("T2192") == "lr30"


def test_none_returns_generic():
    assert detect_model_family(None) == "generic"


def test_empty_string_returns_generic():
    assert detect_model_family("") == "generic"


def test_whitespace_only_returns_generic():
    assert detect_model_family("   ") == "generic"


def test_unknown_code_returns_generic():
    assert detect_model_family("T9999") == "generic"


def test_hint_match_x10():
    assert detect_model_family("robovac x10 pro omni") == "x10"


def test_hint_match_x8():
    assert detect_model_family("Eufy X8 Hybrid") == "x8"


def test_hint_match_lr30():
    assert detect_model_family("RoboVac LR30 Hybrid+") == "lr30"


def test_hint_match_case_insensitive():
    assert detect_model_family("ROBOVAC L60") == "l60"


def test_exact_code_c20_not_matched_by_hint():
    """T2280 maps to 'c20'; no hint would catch that code — exact match wins."""
    assert detect_model_family("T2280") == "c20"


def test_whitespace_stripped_before_lookup():
    assert detect_model_family("  T2351  ") == "x10"


def test_all_known_codes_resolve_consistently():
    """Every code in MODEL_CODE_FAMILIES must round-trip through detect_model_family."""
    for code, expected_family in MODEL_CODE_FAMILIES.items():
        result = detect_model_family(code)
        assert result == expected_family, f"Code {code!r}: expected {expected_family!r}, got {result!r}"
