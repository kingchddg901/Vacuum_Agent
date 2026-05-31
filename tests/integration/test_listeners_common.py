"""Phase 5 integration tests — listeners/_common.py pure helpers.

Coverage targets
----------------
[LC-1]  get_adapter_vocab returns fallback when no adapter is registered.
[LC-2]  get_adapter_vocab returns frozenset from registered adapter.
[LC-3]  get_adapter_vocab handles missing section gracefully.
[LC-4]  get_adapter_value returns fallback when no adapter is registered.
[LC-5]  get_adapter_value returns nested value from registered adapter.
[LC-6]  get_adapter_value returns fallback for missing intermediate key.
[LC-7]  get_lifecycle_watch_entities returns only vacuum when no adapter.
[LC-8]  get_lifecycle_watch_entities includes adapter-declared entities.
[LC-9]  completed_finalize_signals returns empty strings for absent states.
[LC-10] completed_finalize_signals reads live hass entity states.
[LC-11] job_finished_event_data returns correct vacuum/map fields.
[LC-12] job_finished_event_data defaults status to "completed".
[LC-13] job_finished_event_data reads outcome from nested structure.
[LC-14] job_finished_event_data tolerates None finalize_result.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.listeners._common import (
    completed_finalize_signals,
    get_adapter_value,
    get_adapter_vocab,
    get_lifecycle_watch_entities,
    job_finished_event_data,
)


_VAC = "vacuum.alfred"
_FALLBACK: frozenset[str] = frozenset({"fallback"})

_MINIMAL_ADAPTER = {
    "adapter_id": "test",
    "source": "test",
    "entities": {
        "task_status": "sensor.alfred_task_status",
        "dock_status": "sensor.alfred_dock_status",
        "active_cleaning_target": "sensor.alfred_target",
        "active_map": "sensor.alfred_active_map",
    },
    "completion": {
        "task_status_value": "completed",
        "secondary_clear_sentinels": ["", "unknown", "unavailable"],
    },
}


# ---------------------------------------------------------------------------
# [LC-1] — [LC-3] get_adapter_vocab
# ---------------------------------------------------------------------------

def test_get_adapter_vocab_no_adapter_returns_fallback(manager):
    """[LC-1] Returns fallback frozenset when no adapter is registered."""
    result = get_adapter_vocab(_VAC, "completion", "secondary_clear_sentinels", _FALLBACK)
    assert result == _FALLBACK


def test_get_adapter_vocab_returns_frozenset(manager):
    """[LC-2] Returns frozenset of lowercased, stripped strings from adapter."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "completion": {"secondary_clear_sentinels": ["Unknown", "Unavailable", ""]},
    })
    result = get_adapter_vocab(_VAC, "completion", "secondary_clear_sentinels", _FALLBACK)
    assert isinstance(result, frozenset)
    assert "unknown" in result
    assert "unavailable" in result


def test_get_adapter_vocab_missing_section_returns_fallback(manager):
    """[LC-3] Returns fallback when the requested section does not exist."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_vocab(_VAC, "nonexistent_section", "key", _FALLBACK)
    assert result == _FALLBACK


def test_get_adapter_vocab_missing_key_returns_fallback(manager):
    """[LC-3] Returns fallback when the key is absent inside a known section."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_vocab(_VAC, "completion", "nonexistent_key", _FALLBACK)
    assert result == _FALLBACK


# ---------------------------------------------------------------------------
# [LC-4] — [LC-6] get_adapter_value
# ---------------------------------------------------------------------------

def test_get_adapter_value_no_adapter_returns_fallback(manager):
    """[LC-4] Returns fallback when no adapter is registered."""
    result = get_adapter_value(_VAC, "completion", "task_status_value", fallback="default")
    assert result == "default"


def test_get_adapter_value_finds_nested_value(manager):
    """[LC-5] Returns the value at the requested nested path."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_value(_VAC, "completion", "task_status_value", fallback="fallback")
    assert result == "completed"


def test_get_adapter_value_missing_intermediate_key_returns_fallback(manager):
    """[LC-6] Returns fallback when an intermediate key in the path is missing."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_adapter_value(_VAC, "nonexistent", "task_status_value", fallback="fb")
    assert result == "fb"


def test_get_adapter_value_none_fallback(manager):
    """[LC-4] Fallback can be None and is returned correctly."""
    result = get_adapter_value(_VAC, "completion", "task_status_value", fallback=None)
    assert result is None


# ---------------------------------------------------------------------------
# [LC-7] — [LC-8] get_lifecycle_watch_entities
# ---------------------------------------------------------------------------

def test_get_lifecycle_watch_entities_no_adapter(manager):
    """[LC-7] Returns only the vacuum entity when no adapter is registered."""
    result = get_lifecycle_watch_entities(_VAC)
    assert result == [_VAC]


def test_get_lifecycle_watch_entities_includes_adapter_entities(manager):
    """[LC-8] Includes all declared lifecycle entities from the adapter."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    result = get_lifecycle_watch_entities(_VAC)
    assert _VAC in result
    assert "sensor.alfred_task_status" in result
    assert "sensor.alfred_dock_status" in result
    assert "sensor.alfred_target" in result
    assert "sensor.alfred_active_map" in result


def test_get_lifecycle_watch_entities_partial_adapter(manager):
    """[LC-8] Only declared entities are included; missing keys are skipped."""
    register_adapter_config(_VAC, {
        **_MINIMAL_ADAPTER,
        "entities": {"task_status": "sensor.alfred_task_status"},
    })
    result = get_lifecycle_watch_entities(_VAC)
    assert _VAC in result
    assert "sensor.alfred_task_status" in result
    # dock_status not declared — must not appear
    assert "sensor.alfred_dock_status" not in result


# ---------------------------------------------------------------------------
# [LC-9] — [LC-10] completed_finalize_signals
# ---------------------------------------------------------------------------

async def test_completed_finalize_signals_no_entities_empty_strings(hass, manager):
    """[LC-9] Returns empty strings for all signals when entity states are absent."""
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["vacuum_state"] == ""
    assert signals["task_status"] == ""
    assert signals["dock_status"] == ""
    assert signals["active_target"] == ""


async def test_completed_finalize_signals_reads_live_state(hass, manager):
    """[LC-10] Returns the live HA state for the vacuum entity."""
    hass.states.async_set(_VAC, "docked")
    await hass.async_block_till_done()
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["vacuum_state"] == "docked"


async def test_completed_finalize_signals_reads_adapter_entities(hass, manager):
    """[LC-10] Reads states for adapter-declared task_status and dock_status."""
    register_adapter_config(_VAC, _MINIMAL_ADAPTER)
    hass.states.async_set("sensor.alfred_task_status", "Completed")
    hass.states.async_set("sensor.alfred_dock_status", "washing")
    await hass.async_block_till_done()
    signals = completed_finalize_signals(hass, _VAC)
    assert signals["task_status"] == "completed"
    assert signals["dock_status"] == "washing"


# ---------------------------------------------------------------------------
# [LC-11] — [LC-14] job_finished_event_data
# ---------------------------------------------------------------------------

def test_job_finished_event_data_has_vacuum_and_map(manager):
    """[LC-11] Payload always contains vacuum_entity_id and map_id."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC,
        map_id="1",
        finalize_result={},
    )
    assert payload["vacuum_entity_id"] == _VAC
    assert payload["map_id"] == "1"


def test_job_finished_event_data_default_status(manager):
    """[LC-12] Status defaults to 'completed' when absent."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id="1", finalize_result={}
    )
    assert payload["status"] == "completed"


def test_job_finished_event_data_reads_outcome_status(manager):
    """[LC-13] Reads status from nested completed_job.outcome."""
    finalize_result = {
        "completed_job": {
            "outcome": {"status": "cancelled"},
        }
    }
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id="1", finalize_result=finalize_result
    )
    assert payload["status"] == "cancelled"


def test_job_finished_event_data_none_finalize_result(manager):
    """[LC-14] Treats None finalize_result as empty — returns default values."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id="1", finalize_result=None
    )
    assert payload["vacuum_entity_id"] == _VAC
    assert payload["status"] == "completed"
    assert payload["job_id"] is None


def test_job_finished_event_data_map_id_coerced_to_string(manager):
    """[LC-11] map_id is coerced to a string in the payload."""
    payload = job_finished_event_data(
        vacuum_entity_id=_VAC, map_id=42, finalize_result={}
    )
    assert payload["map_id"] == "42"
