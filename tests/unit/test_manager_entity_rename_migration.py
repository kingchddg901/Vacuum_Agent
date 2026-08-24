"""D4 repair — moving a renamed vacuum's data to its new entity id.

A vacuum's entity id is a storage ADDRESS: seventeen store sections are keyed by it
and the learning tree's directory is derived from its object id. This applies the
pair that ``listeners/entity_rename.py`` recorded.

Coverage targets
----------------
[RN-1] every per-vacuum section moves, and the old key is gone afterwards.
[RN-2] sections are DISCOVERED, not listed — a section this code has never heard of
       moves too. A hardcoded list of seventeen would miss the eighteenth, which is
       exactly how this bug class spreads.
[RN-3] a collision refuses ENTIRELY: nothing moves and the record stays unapplied.
       Two vacuums are involved and merging them is not this layer's decision.
[RN-4] an applied record is not applied twice.
[RN-5] the learning tree moves with the store.
[RN-6] a tree-move failure leaves NOTHING moved and the record unapplied. The
       filesystem half runs first precisely so a failure cannot half-migrate.
[RN-7] a vacuum with no learning tree still migrates its store sections.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from custom_components.eufy_vacuum.core.manager import (
    EufyVacuumManager,
    _move_learning_tree,
)


class _Hass:
    """Only what the migration asks for."""

    def __init__(self, config_dir: Path) -> None:
        self.config = type("C", (), {"config_dir": str(config_dir)})()
        self.data: dict = {}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _manager(tmp_path: Path, data: dict) -> EufyVacuumManager:
    mgr = EufyVacuumManager(_Hass(tmp_path))
    mgr.data = data
    mgr._loaded = True
    return mgr


def _rename(old="vacuum.alfred", new="vacuum.butler", applied=False) -> dict:
    return {"old_entity_id": old, "new_entity_id": new, "applied": applied}


def _tree(tmp_path: Path, slug: str) -> Path:
    d = tmp_path / "eufy_vacuum" / "learning" / slug / "jobs"
    d.mkdir(parents=True)
    (d / "job_1.json").write_text("{}", encoding="utf-8")
    return d.parent


async def test_rn1_every_per_vacuum_section_moves(tmp_path):
    data = {
        "vacuums": {"vacuum.alfred": {"x": 1}},
        "maps": {"vacuum.alfred": {"12": {}}},
        "run_profiles": {"vacuum.alfred": []},
        "pending_entity_renames": [_rename()],
    }
    mgr = _manager(tmp_path, data)
    assert await mgr._apply_pending_entity_renames() == 1

    for section in ("vacuums", "maps", "run_profiles"):
        assert "vacuum.butler" in data[section], section
        assert "vacuum.alfred" not in data[section], section
    assert data["pending_entity_renames"][0]["applied"] is True


async def test_rn2_a_section_this_code_never_heard_of_moves_too(tmp_path):
    """[RN-2] The whole point of discovering sections rather than listing them: a
    subsystem added tomorrow is covered without anyone remembering this function."""
    data = {
        "vacuums": {"vacuum.alfred": {}},
        "a_section_invented_after_this_was_written": {"vacuum.alfred": {"kept": True}},
        "pending_entity_renames": [_rename()],
    }
    mgr = _manager(tmp_path, data)
    await mgr._apply_pending_entity_renames()

    moved = data["a_section_invented_after_this_was_written"]
    assert moved == {"vacuum.butler": {"kept": True}}


async def test_rn3_a_collision_refuses_entirely(tmp_path):
    """[RN-3] Partial is the worst outcome: some sections under the new id and some
    under the old is a vacuum that is half two vacuums."""
    data = {
        "vacuums": {"vacuum.alfred": {"a": 1}, "vacuum.butler": {"b": 2}},
        "maps": {"vacuum.alfred": {"12": {}}},
        "pending_entity_renames": [_rename()],
    }
    mgr = _manager(tmp_path, data)
    assert await mgr._apply_pending_entity_renames() == 0

    assert data["vacuums"] == {"vacuum.alfred": {"a": 1}, "vacuum.butler": {"b": 2}}
    assert "vacuum.alfred" in data["maps"] and "vacuum.butler" not in data["maps"]
    assert data["pending_entity_renames"][0]["applied"] is False


async def test_rn4_an_applied_record_is_not_applied_twice(tmp_path):
    data = {
        "vacuums": {"vacuum.butler": {}},
        "pending_entity_renames": [_rename(applied=True)],
    }
    mgr = _manager(tmp_path, data)
    assert await mgr._apply_pending_entity_renames() == 0
    assert data["vacuums"] == {"vacuum.butler": {}}


async def test_rn5_the_learning_tree_moves_with_the_store(tmp_path):
    _tree(tmp_path, "alfred")
    data = {"vacuums": {"vacuum.alfred": {}}, "pending_entity_renames": [_rename()]}
    mgr = _manager(tmp_path, data)
    await mgr._apply_pending_entity_renames()

    root = tmp_path / "eufy_vacuum" / "learning"
    assert (root / "butler" / "jobs" / "job_1.json").is_file()
    assert not (root / "alfred").exists()
    assert data["pending_entity_renames"][0]["tree_moved"] is True


async def test_rn6_a_tree_failure_leaves_nothing_moved(tmp_path):
    """[RN-6] RED IF THE ORDER FLIPS. The store moves are infallible dict ops; the
    filesystem move is the half that can fail. Doing the fallible half FIRST is what
    makes a failure a clean no-op instead of a store pointing at a tree still under
    the old name."""
    _tree(tmp_path, "alfred")
    _tree(tmp_path, "butler")          # destination already exists -> the move raises
    data = {
        "vacuums": {"vacuum.alfred": {"a": 1}},
        "maps": {"vacuum.alfred": {}},
        "pending_entity_renames": [_rename()],
    }
    mgr = _manager(tmp_path, data)
    assert await mgr._apply_pending_entity_renames() == 0

    assert "vacuum.alfred" in data["vacuums"] and "vacuum.butler" not in data["vacuums"]
    assert "vacuum.alfred" in data["maps"]
    assert data["pending_entity_renames"][0]["applied"] is False


async def test_rn7_no_tree_is_not_a_failure(tmp_path):
    """[RN-7] A vacuum added but never run has no learning tree. Its rooms and
    profiles must still follow the rename."""
    data = {"maps": {"vacuum.alfred": {"12": {}}}, "pending_entity_renames": [_rename()]}
    mgr = _manager(tmp_path, data)
    assert await mgr._apply_pending_entity_renames() == 1
    assert "vacuum.butler" in data["maps"]
    assert data["pending_entity_renames"][0]["tree_moved"] is False


def test_move_learning_tree_refuses_to_merge(tmp_path):
    _tree(tmp_path, "alfred")
    _tree(tmp_path, "butler")
    with pytest.raises(FileExistsError):
        _move_learning_tree(str(tmp_path), "vacuum.alfred", "vacuum.butler")


def test_move_learning_tree_is_a_noop_without_a_source(tmp_path):
    assert _move_learning_tree(str(tmp_path), "vacuum.alfred", "vacuum.butler") is False
