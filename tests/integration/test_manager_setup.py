"""Phase 3 integration tests — EufyVacuumManager initialization and vacuum records.

Coverage targets
----------------
[MS-1]  After async_initialize, data contains expected top-level keys.
[MS-2]  ensure_vacuum_record creates a new record when none exists.
[MS-3]  ensure_vacuum_record is idempotent on repeated calls.
[MS-4]  ensure_vacuum_record stores a detected_model when supplied.
[MS-5]  get_managed_vacuums returns empty when no vacuums are recorded.
[MS-6]  get_managed_vacuums returns an entry for each ensure'd vacuum.
[MS-7]  get_known_vacuum_ids is empty on a fresh manager.
[MS-8]  get_known_vacuum_ids includes vacuums added via ensure_vacuum_record.
[MS-9]  ensure_runtime creates a VacuumRuntimeState on first call.
[MS-10] ensure_runtime returns the same object on subsequent calls.
[MS-11] runtime state is independent per vacuum entity_id.
[MS-12] remove_vacuum_record deletes the managed-vacuum record from data["vacuums"].
[MS-13] remove_vacuum_record clears every per-vacuum bucket (incl. nested theme.vacuums and battery.vacuums) for the removed vacuum only, reports them in removed_buckets, and leaves the other vacuum untouched.
[MS-14] remove_vacuum_record on a never-added vacuum is a safe no-op (removed_buckets empty).
[MS-15] After remove_vacuum_record the vacuum drops out of get_known_vacuum_ids and get_managed_vacuums.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant


# ---------------------------------------------------------------------------
# [MS-1] Initialization
# ---------------------------------------------------------------------------

async def test_manager_data_keys_after_init(manager):
    """[MS-1] Top-level data keys are seeded after async_initialize."""
    for key in ("vacuums", "capabilities", "maps", "room_history", "room_rule_status"):
        assert key in manager.data, f"Expected key {key!r} in manager.data"


# ---------------------------------------------------------------------------
# [MS-2] — [MS-4] ensure_vacuum_record
# ---------------------------------------------------------------------------

async def test_ensure_vacuum_record_creates_entry(manager):
    """[MS-2] A vacuum record is created on first call."""
    record = manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    assert record["vacuum_entity_id"] == "vacuum.alfred"
    assert "vacuum.alfred" in manager.data["vacuums"]


async def test_ensure_vacuum_record_idempotent(manager):
    """[MS-3] Calling ensure_vacuum_record twice returns the same record."""
    first = manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    second = manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    assert first is second


async def test_ensure_vacuum_record_stores_detected_model(manager):
    """[MS-4] Passing detected_model stores it in the record."""
    manager.ensure_vacuum_record(
        vacuum_entity_id="vacuum.alfred", detected_model="T2351"
    )
    record = manager.data["vacuums"]["vacuum.alfred"]
    assert record["detected_model"] == "T2351"


async def test_ensure_vacuum_record_updates_detected_model(manager):
    """[MS-4] detected_model is overwritten when a new one is supplied."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred", detected_model="T2351")
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred", detected_model="T2261")
    assert manager.data["vacuums"]["vacuum.alfred"]["detected_model"] == "T2261"


async def test_ensure_vacuum_record_is_managed_true(manager):
    """[MS-2] New records have is_managed=True by default."""
    record = manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    assert record["is_managed"] is True


# ---------------------------------------------------------------------------
# [MS-5] — [MS-6] get_managed_vacuums
# ---------------------------------------------------------------------------

async def test_get_managed_vacuums_empty(manager):
    """[MS-5] Returns zero vacuums on a fresh manager."""
    result = manager.get_managed_vacuums()
    assert result["vacuum_count"] == 0
    assert result["vacuums"] == []


async def test_get_managed_vacuums_returns_entry(manager):
    """[MS-6] Returns one entry per ensure'd vacuum."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    result = manager.get_managed_vacuums()
    assert result["vacuum_count"] == 1
    assert result["vacuums"][0]["vacuum_entity_id"] == "vacuum.alfred"


async def test_get_managed_vacuums_two_vacuums(manager):
    """[MS-6] Returns one entry per vacuum when multiple are registered."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.bertie")
    result = manager.get_managed_vacuums()
    assert result["vacuum_count"] == 2
    ids = {v["vacuum_entity_id"] for v in result["vacuums"]}
    assert ids == {"vacuum.alfred", "vacuum.bertie"}


# ---------------------------------------------------------------------------
# [MS-7] — [MS-8] get_known_vacuum_ids
# ---------------------------------------------------------------------------

async def test_get_known_vacuum_ids_empty(manager):
    """[MS-7] Empty list on a fresh manager."""
    assert manager.get_known_vacuum_ids() == []


async def test_get_known_vacuum_ids_after_ensure(manager):
    """[MS-8] Includes vacuums added via ensure_vacuum_record."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    ids = manager.get_known_vacuum_ids()
    assert "vacuum.alfred" in ids


async def test_get_known_vacuum_ids_deduplicated(manager):
    """[MS-8] Each vacuum appears only once even if added multiple times."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    ids = manager.get_known_vacuum_ids()
    assert ids.count("vacuum.alfred") == 1


# ---------------------------------------------------------------------------
# [MS-9] — [MS-11] ensure_runtime
# ---------------------------------------------------------------------------

async def test_ensure_runtime_creates_state(manager):
    """[MS-9] Creates a VacuumRuntimeState on first call."""
    runtime = manager.ensure_runtime("vacuum.alfred")
    assert runtime.vacuum_entity_id == "vacuum.alfred"
    assert "vacuum.alfred" in manager.runtime


async def test_ensure_runtime_idempotent(manager):
    """[MS-10] Returns the same object on repeated calls."""
    first = manager.ensure_runtime("vacuum.alfred")
    second = manager.ensure_runtime("vacuum.alfred")
    assert first is second


async def test_ensure_runtime_independent_per_vacuum(manager):
    """[MS-11] Different vacuums get separate runtime state objects."""
    alfred = manager.ensure_runtime("vacuum.alfred")
    bertie = manager.ensure_runtime("vacuum.bertie")
    alfred.active_map_id = "map_1"
    assert bertie.active_map_id is None


# ---------------------------------------------------------------------------
# [MS-12] — [MS-15] remove_vacuum_record (inverse of ensure_vacuum_record)
# ---------------------------------------------------------------------------

def _seed_two_vacuums(manager):
    """Populate per-vacuum data across several buckets for two vacuums."""
    for vid in ("vacuum.alfred", "vacuum.bertie"):
        manager.ensure_vacuum_record(vacuum_entity_id=vid)
        manager.data.setdefault("maps", {})[vid] = {"6": {"rooms": {"1": {}}}}
        manager.data.setdefault("capabilities", {})[vid] = {"supports_rooms": True}
        manager.data.setdefault("room_history", {})[vid] = {"6": {}}
        manager.data.setdefault("active_jobs", {})[vid] = {"6": {}}
        # Both NESTED per-vacuum buckets (one level down, not top-level).
        manager.data.setdefault("theme", {}).setdefault("vacuums", {})[vid] = {
            "active_theme_id": "lcars"
        }
        manager.data.setdefault("battery", {}).setdefault("vacuums", {})[vid] = {
            "baseline_pct": 100, "cycles": 5
        }


async def test_remove_vacuum_record_drops_vacuum(manager):
    """[MS-12] remove_vacuum_record removes the managed-vacuum record."""
    manager.ensure_vacuum_record(vacuum_entity_id="vacuum.alfred")
    manager.remove_vacuum_record(vacuum_entity_id="vacuum.alfred")
    assert "vacuum.alfred" not in manager.data["vacuums"]


async def test_remove_vacuum_record_clears_all_buckets_leaves_other(manager):
    """[MS-13] Every per-vacuum bucket is cleared for the removed vacuum ONLY."""
    _seed_two_vacuums(manager)
    result = manager.remove_vacuum_record(vacuum_entity_id="vacuum.alfred")

    # alfred is gone from every top-level bucket + reported as removed...
    for bucket in ("vacuums", "maps", "capabilities", "room_history", "active_jobs"):
        assert "vacuum.alfred" not in manager.data.get(bucket, {})
        assert bucket in result["removed_buckets"]
    # ...including BOTH nested buckets (theme.vacuums + battery.vacuums — the
    # battery one was the orphan the scan used to miss).
    assert "theme.vacuums" in result["removed_buckets"]
    assert "battery.vacuums" in result["removed_buckets"]
    assert "vacuum.alfred" not in manager.data["theme"]["vacuums"]
    assert "vacuum.alfred" not in manager.data["battery"]["vacuums"]

    # bertie is completely untouched.
    for bucket in ("vacuums", "maps", "capabilities", "room_history", "active_jobs"):
        assert "vacuum.bertie" in manager.data[bucket]
    assert "vacuum.bertie" in manager.data["theme"]["vacuums"]
    assert "vacuum.bertie" in manager.data["battery"]["vacuums"]


async def test_remove_vacuum_record_unknown_is_noop(manager):
    """[MS-14] Removing a never-added vacuum is a safe no-op."""
    result = manager.remove_vacuum_record(vacuum_entity_id="vacuum.ghost")
    assert result["removed_buckets"] == []


async def test_remove_vacuum_record_clears_known_and_managed_views(manager):
    """[MS-15] After removal the vacuum drops out of the known/managed views."""
    _seed_two_vacuums(manager)
    manager.remove_vacuum_record(vacuum_entity_id="vacuum.alfred")
    assert "vacuum.alfred" not in manager.get_known_vacuum_ids()
    ids = {v["vacuum_entity_id"] for v in manager.get_managed_vacuums()["vacuums"]}
    assert ids == {"vacuum.bertie"}
