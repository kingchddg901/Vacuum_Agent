"""Eufy adapter job_segmenter block — the threshold-dedup byte-identical pins.

When the gap/area/cadence thresholds moved out of ``live_transition`` into the new
``job_segmenter.tuning`` (the single source), these lock that the Eufy numbers did
not drift and that the engine resolves correctly.

Coverage targets
----------------
[JSC-1] The Eufy adapter declares job_segmenter.engine = "eufy_counter_v1".
[JSC-2] job_segmenter.tuning == EufyCounterSegmenter.DEFAULT_TUNING (which equals the
        counter_segmentation module constants via [JE-6]) — no threshold drift.
[JSC-3] live_transition no longer carries the threshold keys (single source = tuning).
[JSC-4] The declared engine resolves and validates clean.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.adapters.eufy.adapter import (
    register_eufy_adapter_for_vacuum,
)
from custom_components.eufy_vacuum.adapters.registry import get_adapter_config
from custom_components.eufy_vacuum.learning.job_segmenter_engines import (
    EufyCounterSegmenter,
    get_job_segmenter_engine,
    known_job_engine_names,
)

_VAC = "vacuum.alfred"


def _eufy_config(hass) -> dict:
    register_eufy_adapter_for_vacuum(hass, _VAC)
    return get_adapter_config(_VAC) or {}


def test_job_segmenter_engine_declared(hass):
    """[JSC-1]"""
    js = _eufy_config(hass).get("job_segmenter") or {}
    assert js.get("engine") == "eufy_counter_v1"
    assert js.get("engine") in known_job_engine_names()


def test_job_segmenter_tuning_matches_engine_defaults(hass):
    """[JSC-2] the adapter tuning literals equal the engine defaults — the dedup that
    moved them out of live_transition did not change a single number."""
    js = _eufy_config(hass).get("job_segmenter") or {}
    assert js.get("tuning") == EufyCounterSegmenter.DEFAULT_TUNING


def test_live_transition_thresholds_moved_out(hass):
    """[JSC-3] live_transition keeps only the orchestration knobs."""
    lt = _eufy_config(hass).get("live_transition") or {}
    for key in ("gap_delayed_s", "gap_transit_s", "gap_plateau_s", "area_jump_m2", "cadence_s"):
        assert key not in lt
    assert lt.get("enabled") is True
    assert lt.get("rollover_kinds")


def test_declared_engine_validates_clean(hass):
    """[JSC-4] the engine resolves and accepts its own declared tuning."""
    js = _eufy_config(hass).get("job_segmenter") or {}
    engine = get_job_segmenter_engine(js.get("engine"))
    assert engine.validate_tuning(js.get("tuning") or {}) == []
