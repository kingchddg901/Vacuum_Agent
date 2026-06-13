"""Phase 3 integration tests — room lifecycle (save, get, update_fields).

Coverage targets
----------------
[MR-1]  save_managed_rooms creates a map bucket and returns room_count.
[MR-2]  save_managed_rooms stores all discovered rooms by default.
[MR-3]  save_managed_rooms respects enabled_room_ids filter.
[MR-4]  save_managed_rooms returns summary with enabled/disabled counts.
[MR-5]  get_managed_rooms returns rooms for a saved map.
[MR-6]  get_managed_rooms returns empty for an unknown map.
[MR-7]  update_room_fields changes fan_speed.
[MR-8]  update_room_fields toggles enabled flag.
[MR-9]  update_room_fields returns error payload for unknown room.
[MR-10] update_room_fields changes clean_passes.
[MR-11] set_rooms_enabled_subset enables only the specified rooms.
[MR-12] set_rooms_enabled_subset disables all others.
[MR-13] _load_room_history_cache_sync migrates an old-format jobs index (no
        'status') via index-ingest; a new-format index uses completed jobs.
[MR-14] get_known_map_ids folds in the runtime's selected/active map ids.
[MR-15] set_rooms_enabled_subset tolerates a non-dict rooms bucket and reaches
        the non-dict-room-entry guard.
[RRS-1] _update_room_rule_status_snapshot records 'blocked_and_modified' for a
        selected+blocked+modified room and skips non-dict / room_id<=0 entries.
[RRS-2] _update_room_rule_status_snapshot records 'not_selected' for a room not
        in selected_room_ids.
[RRS-3] get_room_rule_status coerces a non-dict stored entry to {} before the
        defensive default response is built.
[RHI-1] _ingest_completed_job_into_room_history short-circuits to False on each
        malformed completed-job shape; a non-dict job sub-block falls back to {}.
[RHI-2] _ingest_completed_job_into_room_history folds a valid completed job into
        history, setting vacuum/mop mode timestamps and skipping bad rooms.
[RHI-3] _ingest_jobs_index_entry_into_room_history copies a room's last_mopped_at
        into the history entry.
[RCH-1] get_room_cleaning_history echoes stored timestamps and derives hours-since
        (positive float for parseable values, None for None timestamps).
[RCH-2] get_room_cleaning_history coerces a corrupt (non-dict) entry to {}, so
        every history field defaults to None.
"""

from __future__ import annotations

import pytest

from tests._factories import VAC as _VAC, MAP as _MAP, set_room_field
from .conftest import make_rooms, seed_discovery, setup_map


# ---------------------------------------------------------------------------
# [MR-1] — [MR-4] save_managed_rooms
# ---------------------------------------------------------------------------

async def test_save_managed_rooms_creates_map_bucket(manager):
    """[MR-1] A map bucket exists in data after save."""
    setup_map(manager, _VAC, _MAP, count=2)
    assert _VAC in manager.data.get("maps", {})
    assert _MAP in manager.data["maps"][_VAC]


async def test_save_managed_rooms_room_count(manager):
    """[MR-1] Returned room_count matches the number of seeded rooms."""
    result = setup_map(manager, _VAC, _MAP, count=3)
    assert result["room_count"] == 3


async def test_save_managed_rooms_stores_all_rooms(manager):
    """[MR-2] All seeded rooms land in the map bucket by default."""
    setup_map(manager, _VAC, _MAP, count=3)
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert set(rooms.keys()) == {"1", "2", "3"}


async def test_save_managed_rooms_filter_by_enabled_ids(manager):
    """[MR-3] Only rooms in enabled_room_ids are stored."""
    result = setup_map(manager, _VAC, _MAP, count=4, enabled_room_ids=[1, 3])
    assert result["room_count"] == 2
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert set(rooms.keys()) == {"1", "3"}


async def test_save_managed_rooms_summary_counts(manager):
    """[MR-4] Summary counts all rooms as enabled (enabled=True by default)."""
    result = setup_map(manager, _VAC, _MAP, count=3)
    assert result["summary"]["enabled_count"] == 3
    assert result["summary"]["disabled_count"] == 0


async def test_save_managed_rooms_sets_is_configured(manager):
    """[MR-2] All saved rooms have is_configured=True."""
    setup_map(manager, _VAC, _MAP, count=2)
    for room in manager.data["maps"][_VAC][_MAP]["rooms"].values():
        assert room["is_configured"] is True


async def test_save_managed_rooms_preserves_existing_settings(manager):
    """[MR-2] Existing room settings survive a re-save."""
    setup_map(manager, _VAC, _MAP, count=2)
    set_room_field(manager, 1, fan_speed="quiet")

    # Re-seed and re-save with the same rooms
    seed_discovery(manager, _VAC, _MAP, make_rooms(_MAP, 2))
    manager.save_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["fan_speed"] == "quiet"


# ---------------------------------------------------------------------------
# [MR-5] — [MR-6] get_managed_rooms
# ---------------------------------------------------------------------------

async def test_get_managed_rooms_returns_rooms(manager):
    """[MR-5] get_managed_rooms returns the saved rooms."""
    setup_map(manager, _VAC, _MAP, count=3)
    result = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["room_count"] == 3
    assert "1" in result["rooms"]
    assert "2" in result["rooms"]
    assert "3" in result["rooms"]


async def test_get_managed_rooms_empty_for_unknown_map(manager):
    """[MR-6] Returns zero rooms for a map that hasn't been saved."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id="99")
    assert result["room_count"] == 0
    assert result["rooms"] == {}


async def test_get_managed_rooms_room_names(manager):
    """[MR-5] Room names from the discovery payload appear in the result."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["rooms"]["1"]["name"] == "Room 1"
    assert result["rooms"]["2"]["name"] == "Room 2"


# ---------------------------------------------------------------------------
# [MR-7] — [MR-10] update_room_fields
# ---------------------------------------------------------------------------

async def test_update_room_fields_fan_speed(manager):
    """[MR-7] fan_speed is updated in the stored room config."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, fan_speed="quiet"
    )
    assert result.get("ok") is not False
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["fan_speed"] == "quiet"


async def test_update_room_fields_toggle_enabled(manager):
    """[MR-8] enabled can be toggled to False."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, enabled=False
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["enabled"] is False


async def test_update_room_fields_unknown_room_returns_error(manager):
    """[MR-9] Returns error payload when the room_id does not exist."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=99, fan_speed="max"
    )
    assert result["ok"] is False
    assert result["error"] == "room_not_found"


async def test_update_room_fields_clean_passes(manager):
    """[MR-10] clean_passes is updated in the stored room config."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=2, clean_passes=2
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["2"]["clean_passes"] == 2


async def test_update_room_fields_clean_mode(manager):
    """[MR-7] clean_mode is updated in the stored room config."""
    setup_map(manager, _VAC, _MAP, count=2)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, clean_mode="mop"
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["clean_mode"] == "mop"


async def test_update_room_fields_invalid_access_graph_rejected(manager):
    """[MR-10b] a structurally-illegal access-graph change (a second dock room)
    is rejected with an error payload AND the room is rolled back, not saved."""
    setup_map(manager, _VAC, _MAP, count=2)
    # Room 1 becomes the dock room — a single dock room is valid.
    ok = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, is_dock_room=True
    )
    assert ok.get("ok") is not False

    # Making room 2 a second dock room is structurally illegal.
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=2, is_dock_room=True
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_access_graph"
    assert result["updated"] is False
    assert isinstance(result["issues"], list) and result["issues"]
    # rollback: room 2 was NOT persisted as a dock room
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["2"].get("is_dock_room") is not True
    # room 1 (the legitimate dock room) is untouched
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"]["is_dock_room"] is True


async def test_update_room_fields_grants_and_rules(manager):
    """[MR-10c] grants_access_to + rules field updates are normalized and persisted
    (a structurally-valid single grant is accepted, not rejected)."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1,
        grants_access_to=[2],
        rules=[{"kind": "blocker", "id": "r1", "entity_id": "binary_sensor.win",
                "operator": "is_on", "effect": {"reason": "window_open"}}],
    )
    assert result.get("ok") is not False
    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room["grants_access_to"] == [2]
    assert isinstance(room["rules"], list) and room["rules"]


@pytest.mark.parametrize("field,value,expected", [
    ("water_level", "High", "High"),
    ("clean_intensity", "Deep", "Deep"),
    ("edge_mopping", True, True),
    ("is_transition", True, True),
])
async def test_update_room_fields_individual_field_branches(manager, field, value, expected):
    """[MR-10d] the remaining update_room_fields field branches each write their
    value (water_level / clean_intensity / edge_mopping / is_transition). clean_mode
    is set to a mop mode so the carpet/mop protection doesn't force water/edge off."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1,
        clean_mode="vacuum_mop", **{field: value})
    assert result.get("ok") is not False
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"][field] == expected


def test_load_room_history_migrates_old_index(manager, monkeypatch):
    """[MR-13] an old-format jobs index (entries with 'rooms' but no 'status') is
    migrated via the index-ingest path; the completed-jobs scan is skipped. Guards
    the deployed-upgrade path that backfills job history without silent loss."""
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
    old = {"map_id": "6", "rooms": [{"room_id": 1}], "ended_at": "2026-01-01T00:00:00+00:00"}
    monkeypatch.setattr(LearningHistoryStore, "load_jobs_index",
                        lambda self, *, vacuum_entity_id: {"jobs": [old]})
    completed: list = []
    monkeypatch.setattr(LearningHistoryStore, "load_all_completed_jobs",
                        lambda self, *, vacuum_entity_id: completed.append(vacuum_entity_id) or [])
    ingested: list = []
    monkeypatch.setattr(manager, "_ingest_jobs_index_entry_into_room_history",
                        lambda *, vacuum_entity_id, index_entry, _history_root=None:
                        ingested.append(index_entry) or True)
    manager._load_room_history_cache_sync(_VAC)
    assert ingested == [old]      # old-format migration branch ran
    assert completed == []        # completed-jobs scan skipped


def test_load_room_history_new_index_uses_completed_jobs(manager, monkeypatch):
    """[MR-13] a new-format index (entries carry 'status') skips the migration and
    loads from completed-job files instead."""
    from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
    new = {"map_id": "6", "status": "completed", "rooms": [{"room_id": 1}]}
    monkeypatch.setattr(LearningHistoryStore, "load_jobs_index",
                        lambda self, *, vacuum_entity_id: {"jobs": [new]})
    completed: list = []
    monkeypatch.setattr(LearningHistoryStore, "load_all_completed_jobs",
                        lambda self, *, vacuum_entity_id: completed.append(vacuum_entity_id) or [])
    ingested: list = []
    monkeypatch.setattr(manager, "_ingest_jobs_index_entry_into_room_history",
                        lambda **kw: ingested.append(kw) or True)
    manager._load_room_history_cache_sync(_VAC)
    assert ingested == []         # migration NOT taken
    assert completed == [_VAC]    # completed-jobs path taken


def test_known_map_ids_includes_runtime_maps(manager):
    """[MR-14] get_known_map_ids folds in the runtime's selected/active map ids
    (the runtime branch), on top of the maps and active_jobs buckets."""
    rt = manager.ensure_runtime(_VAC)
    rt.selected_map_id = "6"
    rt.active_map_id = "7"
    ids = manager.get_known_map_ids(_VAC)
    assert "6" in ids and "7" in ids


# ---------------------------------------------------------------------------
# [MR-11] — [MR-12] set_rooms_enabled_subset
# ---------------------------------------------------------------------------

async def test_set_rooms_enabled_subset_enables_specified(manager):
    """[MR-11] Only the specified room IDs are enabled."""
    setup_map(manager, _VAC, _MAP, count=4)
    manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[1, 3]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["1"]["enabled"] is True
    assert rooms["3"]["enabled"] is True


async def test_set_rooms_enabled_subset_disables_others(manager):
    """[MR-12] Rooms not in the subset are disabled."""
    setup_map(manager, _VAC, _MAP, count=4)
    manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[1, 3]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["2"]["enabled"] is False
    assert rooms["4"]["enabled"] is False


async def test_set_rooms_enabled_subset_returns_counts(manager):
    """[MR-11] Return value has correct enabled_count and total_count."""
    setup_map(manager, _VAC, _MAP, count=4)
    result = manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[2, 4]
    )
    assert result["enabled_count"] == 2
    assert result["total_count"] == 4


async def test_set_rooms_enabled_subset_string_ids(manager):
    """[MR-11] String room IDs are accepted and normalized correctly."""
    setup_map(manager, _VAC, _MAP, count=3)
    manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=["1", "3"]
    )
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["1"]["enabled"] is True
    assert rooms["2"]["enabled"] is False


# ---------------------------------------------------------------------------
# [MR-15] set_rooms_enabled_subset — malformed-bucket guards (lines 1279, 1285)
# ---------------------------------------------------------------------------

async def test_set_rooms_enabled_subset_non_dict_rooms_bucket_resets(manager):
    """[MR-15] When the whole ``rooms`` bucket is not a dict (corrupt store), the
    method resets it to an empty dict instead of raising (manager.py:1279).

    Observable behavior: the call returns clean zero counts and the persisted
    ``rooms`` bucket is now an empty dict — no exception, no leftover garbage.
    """
    setup_map(manager, _VAC, _MAP, count=3)
    # Corrupt the bucket: rooms is a bare string, not a mapping.
    manager.data["maps"][_VAC][_MAP]["rooms"] = "oops"

    result = manager.set_rooms_enabled_subset(
        vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[2]
    )

    assert result["enabled_count"] == 0
    assert result["total_count"] == 0
    # The non-dict bucket was reset to a clean empty dict.
    assert manager.data["maps"][_VAC][_MAP]["rooms"] == {}


async def test_set_rooms_enabled_subset_skips_non_dict_room_entry(manager):
    """[MR-15] A non-dict room *entry* mixed into the bucket exercises the
    per-entry guard's ``continue`` (manager.py:1285): the enable-flip loop steps
    over it instead of trying to spread a non-mapping.

    Real observed behavior: the ``continue`` keeps the junk entry in the bucket,
    so it survives into ``build_room_selection_summary`` downstream, which then
    raises ``AttributeError`` (``'str' object has no attribute 'get'``). We assert
    that real raise — the guard is reached on the way to it. This pins the current
    behavior: the per-entry ``continue`` does not sanitize the bucket, so a
    corrupt entry mixed with real rooms still aborts the summary rebuild.
    """
    setup_map(manager, _VAC, _MAP, count=3)
    # Inject a non-dict room entry alongside the three real rooms.
    manager.data["maps"][_VAC][_MAP]["rooms"]["junk"] = "x"

    with pytest.raises(AttributeError):
        manager.set_rooms_enabled_subset(
            vacuum_entity_id=_VAC, map_id=_MAP, room_ids=[2]
        )

    # The enable-flip loop ran (line 1285 continue reached) before the downstream
    # summary build raised: room 2 was flipped on, 1/3 flipped off, and the junk
    # entry was stepped over untouched by the loop.
    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    assert rooms["2"]["enabled"] is True
    assert rooms["1"]["enabled"] is False
    assert rooms["3"]["enabled"] is False
    assert rooms["junk"] == "x"


# ---------------------------------------------------------------------------
# [RRS-1] — [RRS-2] _update_room_rule_status_snapshot per-room result classification
# ---------------------------------------------------------------------------

async def test_room_rule_status_snapshot_blocked_modified_and_skips(manager):
    """[RRS-1] A room that is selected AND blocked AND modified records
    last_result == 'blocked_and_modified' (1531); a selected-but-skipped room is
    'not_selected' (1529). The non-dict managed-room entry (1518) and the
    room with room_id 0 (1521) are skipped without error and never get a
    rule-status entry written.

    Drives the real _update_room_rule_status_snapshot against seeded managed
    rooms and reads the result back through the public get_room_rule_status
    accessor (observable behaviour, no peeking at internal data shape)."""
    setup_map(manager, _VAC, _MAP, count=2)

    # Build managed_rooms from the seeded rooms, then inject the two entries
    # that the per-room loop must skip:
    #   - a non-dict value (exercises the isinstance guard at 1518)
    #   - a room whose room_id is 0 (exercises the room_id<=0 guard at 1521)
    managed_rooms = dict(manager.data["maps"][_VAC][_MAP]["rooms"])
    managed_rooms["junk"] = "not-a-dict"            # 1518 skip path
    managed_rooms["0"] = {"room_id": 0, "name": "Phantom"}  # 1521 skip path

    manager._update_room_rule_status_snapshot(
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        managed_rooms=managed_rooms,
        selected_room_ids=[1],
        included_room_ids=[1],
        blocked_rooms=[{
            "room_id": 1,
            "reason": "path",
            "source": "graph",
            "blocked_by_room_id": 2,
            "blocked_by_room_name": "Hall",
            "triggered_rule_id": "r1",
        }],
        modified_rooms=[{
            "room_id": 1,
            "changes": {"fan_speed": "Quiet"},
            "triggered_rule_ids": ["r2"],
        }],
        preflight={"requires_confirmation": False, "reason": "ready", "warnings": []},
    )

    # [RRS-1] Room 1 is selected + blocked + modified -> blocked_and_modified (1531).
    status_1 = manager.get_room_rule_status(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1
    )
    assert status_1["last_result"] == "blocked_and_modified"
    assert status_1["last_selected"] is True
    assert status_1["last_block_reason"] == "path"
    assert sorted(status_1["last_triggered_rule_ids"]) == ["r1", "r2"]
    assert status_1["last_modifier_changes"] == {"fan_speed": "Quiet"}

    # [RRS-2] Room 2 is not in selected_room_ids -> not_selected (1529).
    status_2 = manager.get_room_rule_status(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=2
    )
    assert status_2["last_result"] == "not_selected"
    assert status_2["last_selected"] is False

    # The two skipped entries (1518 non-dict, 1521 room_id<=0) wrote nothing:
    # no rule-status row exists for them, so the accessor returns the 'never'
    # default rather than a stored result.
    map_status = manager.data.get("room_rule_status", {}).get(_VAC, {}).get(_MAP, {})
    assert set(map_status.keys()) == {"1", "2"}
    assert manager.get_room_rule_status(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=0
    )["last_result"] == "never"


# ---------------------------------------------------------------------------
# [RRS-3] get_room_rule_status — corrupt (non-dict) stored entry coercion
# ---------------------------------------------------------------------------

async def test_get_room_rule_status_coerces_non_dict_entry(manager):
    """[RRS-3] When the stored room_rule_status entry is not a dict, it is coerced
    to {} before the defensive default response is built (manager.py line 1613).

    Seeds a corrupt scalar entry (a plain string, not a dict) for room "1" and
    asserts get_room_rule_status falls through to the entry={} default path: a
    'never' result with the empty/false defaults, rather than raising on the
    .get() calls a string does not support."""
    setup_map(manager, _VAC, _MAP, count=2)

    # Corrupt the stored status: the entry for room "1" is a bare string, not the
    # expected dict. This exercises the `if not isinstance(entry, dict)` guard.
    manager.data["room_rule_status"] = {_VAC: {_MAP: {"1": "corrupt-not-a-dict"}}}

    result = manager.get_room_rule_status(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1
    )

    # The non-dict entry is coerced to {}, so every field reflects its default.
    assert result["last_result"] == "never"
    assert result["last_selected"] is False
    assert result["last_triggered_rule_ids"] == []
    # Sanity: the room is still identified correctly despite the corrupt status.
    assert result["room_id"] == "1"
    assert result["last_modifier_changes"] == {}


# ---------------------------------------------------------------------------
# [RHI-1] — [RHI-3] room-history ingest guards + mode branches
#
# Direct unit-style exercise of the room-history ingest helpers. Every call
# passes an explicit `_history_root={}` so nothing touches manager.data, the
# LearningHistoryStore, real time, or the network — the helpers are pure dict
# folds. We assert the boolean returns (the guard contract) AND the observable
# shape written into the supplied root.
# ---------------------------------------------------------------------------

# Each entry: (label, synthetic completed_job) that must short-circuit to False
# without writing anything into the history root.
_REJECTED_COMPLETED_JOBS = [
    # 1824 — not a dict at all
    ("non_dict_job", "not-a-dict"),
    # 1824 — None is also not a dict
    ("none_job", None),
    # 1825-1826 — wrong record_type
    ("wrong_record_type", {"record_type": "live"}),
    # 1827-1831 — outcome present but status != 'completed'
    ("outcome_cancelled", {
        "record_type": "completed_job",
        "outcome": {"status": "cancelled"},
    }),
    # 1828-1829 — outcome is not a dict
    ("outcome_not_dict", {
        "record_type": "completed_job",
        "outcome": "done",
    }),
    # 1840 — completed, but ended_at is unparseable -> ended_dt None
    ("unparseable_ended_at", {
        "record_type": "completed_job",
        "outcome": {"status": "completed"},
        "job": {"ended_at": "not-a-date"},
    }),
    # 1847-1848 — completed + parseable, but resolved_rooms is not a list
    ("resolved_rooms_not_list", {
        "record_type": "completed_job",
        "outcome": {"status": "completed"},
        "job": {"ended_at": "2026-01-01T00:00:00+00:00"},
        "resolved_rooms": "oops",
    }),
]


@pytest.mark.parametrize(
    "label,job",
    _REJECTED_COMPLETED_JOBS,
    ids=[case[0] for case in _REJECTED_COMPLETED_JOBS],
)
def test_ingest_completed_job_guard_rejects(manager, label, job):
    """[RHI-1] each malformed completed-job shape short-circuits to False and
    leaves the supplied history root untouched (guards 1824-1848)."""
    root: dict = {}
    result = manager._ingest_completed_job_into_room_history(
        vacuum_entity_id=_VAC, completed_job=job, _history_root=root,
    )
    assert result is False
    # A guard that returns before the room loop must not have created the
    # vacuum bucket; guards after bucket creation (resolved_rooms-not-a-list)
    # may set up the empty bucket but must write no room entries.
    map_history = root.get(_VAC, {})
    assert all(rooms == {} for rooms in map_history.values())


def test_ingest_completed_job_non_dict_sub_blocks_default(manager):
    """[RHI-1] a non-dict `job` sub-block (1832-1834) falls back to {} so ended_at
    resolves from finalized_at instead of crashing; the job is still ingested."""
    root: dict = {}
    job = {
        "record_type": "completed_job",
        "outcome": {"status": "completed"},
        # job is not a dict -> coerced to {}, ended_at falls through to finalized_at
        "job": ["unexpected", "list"],
        "finalized_at": "2026-01-01T00:00:00+00:00",
        "job_profile": {"map_id": "6"},
        "resolved_rooms": [{"room_id": 1, "name": "Kitchen", "clean_mode": "vacuum"}],
    }
    result = manager._ingest_completed_job_into_room_history(
        vacuum_entity_id=_VAC, completed_job=job, _history_root=root,
    )
    assert result is True
    entry = root[_VAC]["6"]["1"]
    assert entry["last_cleaned_at"] == "2026-01-01T00:00:00+00:00"


def test_ingest_completed_job_valid_writes_history_and_mode_branches(manager):
    """[RHI-2] a valid completed job folds resolved rooms into history: the
    vacuum_mop room gets last_cleaned_at + BOTH last_vacuumed_at (1881) and
    last_mopped_at (1884); room_id<=0 (1861) and a non-dict room (1858) are
    silently skipped."""
    root: dict = {}
    ended = "2026-01-01T00:00:00+00:00"
    job = {
        "record_type": "completed_job",
        "outcome": {"status": "completed"},
        "job": {"ended_at": ended},
        "job_profile": {"map_id": "6"},
        "resolved_rooms": [
            {"room_id": 1, "name": "Kitchen", "clean_mode": "vacuum_mop"},
            {"room_id": 0},          # 1861 — room_id <= 0 skipped
            "not-a-dict",            # 1858 — non-dict room skipped
        ],
    }
    result = manager._ingest_completed_job_into_room_history(
        vacuum_entity_id=_VAC, completed_job=job, _history_root=root,
    )
    assert result is True

    map_history = root[_VAC]["6"]
    # Only the one valid room landed; the skipped ones produced no keys.
    assert set(map_history.keys()) == {"1"}

    entry = map_history["1"]
    assert entry["room_id"] == 1
    assert entry["map_id"] == "6"
    assert entry["room_name"] == "Kitchen"
    assert entry["last_cleaned_at"] == ended
    assert entry["last_job_mode"] == "vacuum_mop"
    # vacuum_mop drives BOTH mode branches
    assert entry["last_vacuumed_at"] == ended   # 1881 vacuum branch
    assert entry["last_mopped_at"] == ended      # 1884 mop branch


def test_ingest_completed_job_mop_only_sets_mopped_not_vacuumed(manager):
    """[RHI-2b] a mop-only room sets last_mopped_at (1884) but NOT last_vacuumed_at,
    isolating the mop branch from the vacuum branch."""
    root: dict = {}
    ended = "2026-02-02T12:00:00+00:00"
    job = {
        "record_type": "completed_job",
        "outcome": {"status": "completed"},
        "job": {"ended_at": ended},
        "job_profile": {"map_id": "6"},
        "resolved_rooms": [{"room_id": 1, "name": "Bath", "clean_mode": "mop"}],
    }
    assert manager._ingest_completed_job_into_room_history(
        vacuum_entity_id=_VAC, completed_job=job, _history_root=root,
    ) is True
    entry = root[_VAC]["6"]["1"]
    assert entry["last_mopped_at"] == ended       # 1884 mop branch
    assert "last_vacuumed_at" not in entry         # vacuum branch NOT taken


def test_ingest_jobs_index_entry_sets_last_mopped_at(manager):
    """[RHI-3] the sibling index-ingest helper copies a room's pre-set
    last_mopped_at into the history entry (1809) when it is newer than the
    (absent) existing value."""
    root: dict = {}
    mopped = "2026-03-03T08:30:00+00:00"
    index_entry = {
        "map_id": "6",
        "ended_at": "2026-03-03T09:00:00+00:00",
        "rooms": [{"room_id": 1, "name": "Hall", "last_mopped_at": mopped}],
    }
    result = manager._ingest_jobs_index_entry_into_room_history(
        vacuum_entity_id=_VAC, index_entry=index_entry, _history_root=root,
    )
    assert result is True
    assert root[_VAC]["6"]["1"]["last_mopped_at"] == mopped  # 1809 write


# ---------------------------------------------------------------------------
# [RCH-1] — [RCH-2] get_room_cleaning_history (lines 1916-1925)
# ---------------------------------------------------------------------------

def _seed_room_history(manager, entry):
    """Seed manager.data['room_history'] for VAC/MAP/room '1' and short-circuit
    the disk-backed cache preload so get_room_cleaning_history reads our seed
    synchronously (no async task / lingering timer is spawned).

    Adding _VAC to _room_history_cache_ready makes _ensure_room_history_cache
    (manager.py:1664) return immediately at the `vacuum_key in ...ready` guard.
    """
    manager.data.setdefault("room_history", {}).setdefault(_VAC, {})[_MAP] = {"1": entry}
    manager._room_history_cache_ready.add(_VAC)


async def test_get_room_cleaning_history_value_and_none_paths(manager):
    """[RCH-1] With a valid past last_vacuumed_at and a None last_mopped_at, the
    summary echoes the stored timestamps, derives a positive float hours-since for
    the parseable value (the 1919-1925 round/max non-negative path), and yields
    None hours-since for the None timestamp (the unparseable-value None path)."""
    setup_map(manager, _VAC, _MAP, count=2)  # gives room "1" the name "Room 1"
    seeded_ts = "2020-01-01T00:00:00+00:00"
    _seed_room_history(manager, {
        "last_vacuumed_at": seeded_ts,
        "last_mopped_at": None,
        "last_cleaned_at": seeded_ts,
        "last_job_mode": "vacuum",
    })

    result = manager.get_room_cleaning_history(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1
    )

    # Identity + name come from the managed-room bucket / seeded entry.
    assert result["room_name"] == "Room 1"
    assert result["room_id"] == "1"
    assert result["last_vacuumed_at"] == seeded_ts
    assert result["last_cleaned_at"] == seeded_ts
    assert result["last_mopped_at"] is None
    assert result["last_job_mode"] == "vacuum"

    # 1919-1925 value path: a parseable past timestamp -> positive float hours.
    hv = result["hours_since_last_vacuum"]
    assert isinstance(hv, float)
    assert hv > 0.0

    # 1922-1924 None path: an unparseable (None) timestamp -> None hours.
    assert result["hours_since_last_mop"] is None


async def test_get_room_cleaning_history_corrupt_entry_defaults(manager):
    """[RCH-2] A corrupt (non-dict) stored room_history entry is coerced to {}
    (line 1916), so every history field defaults to None while the room identity
    and name are still resolved from the managed-room bucket."""
    setup_map(manager, _VAC, _MAP, count=2)
    _seed_room_history(manager, "not-a-dict")  # non-dict triggers the {} coercion

    result = manager.get_room_cleaning_history(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1
    )

    assert result["room_name"] == "Room 1"
    assert result["room_id"] == "1"
    # entry coerced to {} -> all .get() lookups return None.
    assert result["last_cleaned_at"] is None
    assert result["last_vacuumed_at"] is None
    assert result["last_mopped_at"] is None
    assert result["last_job_mode"] is None
    # Both hours-since derive from None timestamps -> None.
    assert result["hours_since_last_vacuum"] is None
    assert result["hours_since_last_mop"] is None
