"""Unit tests for learning/brand_facts.py — the BrandFacts contract + Eufy default.

[BF-1] EufyBrandFacts surfaces each adapter fact faithfully (drop-in for the reads it
       replaces): entity ids, alias maps, mid-run + cancel vocab, engine specs.
[BF-2] cancel_service_exclusion_states is normalized (stripped/lowered) — matches the
       caller that used to do it inline.
[BF-3] Empty / absent config degrades to safe defaults (None / {} / empty set).
[BF-4] brand_facts_for() resolves an adapter-registry-backed EufyBrandFacts.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.learning.brand_facts import (
    BrandFacts,
    EufyBrandFacts,
    brand_facts_for,
)

_CFG = {
    "brand": "eufy",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "cleaning_time": "sensor.alfred_time",
        "cleaning_area": "sensor.alfred_area",
    },
    "vocabulary": {
        "clean_mode_aliases": {"vacuum": "Vacuum", "mop": "Mop"},
        "cancel_service_exclusion_states": ["Charging", " Washing Mop "],
        "cancel_detection_states": {
            "active": ["cleaning", "segment_cleaning"],
            "returning": "returning_home",
            "paused": "paused",
        },
    },
    "external_mid_run_statuses": ["Washing Mop", "Recharge"],
    "job_segmenter": {"engine": "eufy_counter_v1", "tuning": {"foo": 1}},
    "room_attribution": {"engine": "eufy_attr_v1", "tuning": None},
}


def test_eufy_brand_facts_surfaces_each_fact():
    """[BF-1]"""
    bf = EufyBrandFacts(_CFG)
    assert isinstance(bf, BrandFacts)  # runtime_checkable Protocol
    assert bf.brand == "eufy"
    assert bf.entity_id("task_status") == "sensor.alfred_task_status"
    assert bf.entity_id("cleaning_area") == "sensor.alfred_area"
    assert bf.entity_id("nope") is None
    assert bf.alias_map("clean_mode") == {"vacuum": "Vacuum", "mop": "Mop"}
    assert bf.alias_map("fan_speed") == {}  # absent -> empty
    assert bf.mid_run_statuses == frozenset({"Washing Mop", "Recharge"})
    assert bf.cancel_detection_states == {
        "active": ["cleaning", "segment_cleaning"],
        "returning": "returning_home",
        "paused": "paused",
    }
    assert bf.job_segmenter == ("eufy_counter_v1", {"foo": 1})
    assert bf.room_attribution == ("eufy_attr_v1", None)


def test_exclusion_states_normalized():
    """[BF-2] stripped + lowercased, matching the finalizer's old inline normalization."""
    bf = EufyBrandFacts(_CFG)
    assert bf.cancel_service_exclusion_states == frozenset({"charging", "washing mop"})


@pytest.mark.parametrize("cfg", [None, {}, {"entities": None, "vocabulary": None}])
def test_empty_config_safe_defaults(cfg):
    """[BF-3]"""
    bf = EufyBrandFacts(cfg)
    assert bf.brand is None
    assert bf.entity_id("task_status") is None
    assert bf.alias_map("clean_mode") == {}
    assert bf.mid_run_statuses == frozenset()
    assert bf.cancel_service_exclusion_states == frozenset()
    assert bf.cancel_detection_states == {}
    assert bf.job_segmenter == (None, None)
    assert bf.room_attribution == (None, None)


def test_brand_facts_for_reads_registry():
    """[BF-4]"""
    vac = "vacuum.bf_test"
    register_adapter_config(vac, _CFG)
    try:
        bf = brand_facts_for(vac)
        assert isinstance(bf, BrandFacts)
        assert bf.brand == "eufy"
        assert bf.entity_id("task_status") == "sensor.alfred_task_status"
    finally:
        clear_registry()
