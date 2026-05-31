"""Unit tests for setup/protection.py — map-delete protection level evaluation.

Coverage targets
----------------
[PROT-1] no risk factors → normal.
[PROT-2] only imported map → elevated (single reason).
[PROT-3] active job → high + typed confirmation.
[PROT-4] two reasons → high.
[PROT-5] rules / access-graph reasons are detected; typed value is the display name.
"""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.eufy_vacuum.setup.protection import evaluate_map_protection


_VAC = "vacuum.alfred"


def _mgr(data):
    return SimpleNamespace(data=data)


def _maps(*, rooms=None, extra_map=True):
    """Two imported maps by default so 'only_map' doesn't trigger."""
    maps = {"6": {"metadata": {"display_name": "Downstairs"}, "rooms": rooms or {"1": {}}}}
    if extra_map:
        maps["7"] = {"rooms": {"1": {}}}
    return {"maps": {_VAC: maps}}


def test_normal():
    """[PROT-1]"""
    result = evaluate_map_protection(_mgr(_maps()), vacuum_entity_id=_VAC, map_id="6")
    assert result["protection_level"] == "normal"
    assert result["requires_typed_confirmation"] is False


def test_only_map_elevated():
    """[PROT-2]"""
    result = evaluate_map_protection(
        _mgr(_maps(extra_map=False)), vacuum_entity_id=_VAC, map_id="6")
    assert result["protection_level"] == "elevated"
    assert any(r["code"] == "only_map" for r in result["reasons"])


def test_active_job_high():
    """[PROT-3]"""
    data = _maps()
    data["active_jobs"] = {_VAC: {"6": {"has_observed_active_lifecycle": True}}}
    result = evaluate_map_protection(_mgr(data), vacuum_entity_id=_VAC, map_id="6")
    assert result["protection_level"] == "high"
    assert result["requires_typed_confirmation"] is True
    assert result["typed_confirmation_value"] == "Downstairs"


def test_two_reasons_high():
    """[PROT-4] history + rules → 2 reasons → high."""
    data = _maps(rooms={"1": {"rules": [{"id": "r1"}]}})
    data["room_history"] = {_VAC: {"6": {"1": {}}}}
    result = evaluate_map_protection(_mgr(data), vacuum_entity_id=_VAC, map_id="6")
    assert result["protection_level"] == "high"


def test_access_graph_reason():
    """[PROT-5]"""
    data = _maps(rooms={"1": {"grants_access_to": [2]}})
    result = evaluate_map_protection(_mgr(data), vacuum_entity_id=_VAC, map_id="6")
    codes = {r["code"] for r in result["reasons"]}
    assert "has_access_graph" in codes
