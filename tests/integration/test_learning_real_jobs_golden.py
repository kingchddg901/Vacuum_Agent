"""Golden regression — REAL Alfred job records drive the learning-inclusion gate.

These fixtures are actual completed-job records captured on vacuum.alfred (curated +
PII-scrubbed by scratch: 2 learning-eligible runs, 1 cancelled, 1 manually un-learned),
frozen so the "audited by work" classification is now also audited by code. They pin:

[LRG-1]  is_learning_job on real records: completed+used_for_learning => True; a
         cancelled run OR a manually un-learned completed run => False (both unhappy paths).
[LRG-2]  happy path — a full rebuild over the real included runs learns their rooms.
[LRG-3]  unhappy path — seeding the excluded runs (incl. a room-bearing one) alongside the
         included runs adds NOTHING: the excluded room never enters the learned baselines.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.eufy_vacuum.learning.history_store import LearningHistoryStore
from custom_components.eufy_vacuum.learning.stats_rebuilder import LearningStatsRebuilder

_VAC = "vacuum.alfred"
_FIX_DIR = Path(__file__).parent.parent / "fixtures" / "learning" / "alfred_jobs"


def _fix(name: str) -> dict:
    return json.loads((_FIX_DIR / f"{name}.json").read_text(encoding="utf-8"))


# Expected gate outcome per real fixture (the "work" verdict we now pin in code).
_EXPECTED = {
    "included_kitchen_1room": True,
    "included_multiroom": True,
    "excluded_cancelled": False,
    "excluded_manual": False,
}


@pytest.mark.parametrize("name,expected", sorted(_EXPECTED.items()))
def test_is_learning_job_matches_real_outcomes(name, expected):
    """[LRG-1] the real completed/used_for_learning gate, frozen on real records."""
    store = LearningHistoryStore(MagicMock())
    assert store.is_learning_job(_fix(name)) is expected


def _seed_and_rebuild(tmp_path: Path, records: list[dict]) -> dict:
    """Write the records into a throwaway learning store, rebuild, return room_stats."""
    hass = MagicMock()
    hass.config.config_dir = str(tmp_path)
    store = LearningHistoryStore(hass)
    for i, rec in enumerate(records):
        store.save_completed_job(
            vacuum_entity_id=_VAC,
            job_id=str(rec.get("job_id") or f"job-{i}"),
            payload=rec,
        )
    LearningStatsRebuilder(hass).rebuild_all(vacuum_entity_id=_VAC, rebuild_csv=False)
    return json.loads(store.get_room_stats_path(vacuum_entity_id=_VAC).read_text(encoding="utf-8"))


def _learned_slugs(room_stats: dict) -> set[str]:
    return {
        str(e.get("room_slug", "")).strip().lower()
        for e in (room_stats.get("room_baselines") or [])
        if str(e.get("room_slug", "")).strip()
    }


def test_rebuild_all_learns_the_real_included_runs(tmp_path):
    """[LRG-2] the two real learning-eligible runs (kitchen; bathroom+kitchen) fold into
    the learned room baselines — the whole rebuild runs clean on the real record shapes."""
    room_stats = _seed_and_rebuild(
        tmp_path, [_fix("included_kitchen_1room"), _fix("included_multiroom")]
    )
    assert {"kitchen", "bathroom"} <= _learned_slugs(room_stats)


def test_rebuild_all_skips_the_real_excluded_runs(tmp_path):
    """[LRG-3] Seed the real included runs + the real excluded runs, plus a room-bearing
    excluded copy (a completed run marked used_for_learning=False that DID clean a room):
    the excluded room must never enter the learned baselines, and the excluded runs must
    not perturb what the included runs learned."""
    # A room-bearing excluded run: real included record, un-learned, cleaning a unique room.
    garage = copy.deepcopy(_fix("included_kitchen_1room"))
    garage["job_id"] = "excluded-garage"
    garage["outcome"]["used_for_learning"] = False
    for coll in (
        garage.get("job", {}).get("room_timings", []),
        garage.get("resolved_rooms", []),
        (garage.get("job_profile") or {}).get("rooms", []),
    ):
        for r in coll:
            if isinstance(r, dict) and r.get("slug"):
                r["slug"] = "garage"
                if r.get("name"):
                    r["name"] = "Garage"

    included_only = _seed_and_rebuild(
        tmp_path / "a", [_fix("included_kitchen_1room"), _fix("included_multiroom")]
    )
    with_excluded = _seed_and_rebuild(
        tmp_path / "b",
        [
            _fix("included_kitchen_1room"),
            _fix("included_multiroom"),
            _fix("excluded_cancelled"),
            _fix("excluded_manual"),
            garage,
        ],
    )

    # The room-bearing excluded run's room is never learned...
    assert "garage" not in _learned_slugs(with_excluded)
    # ...and the excluded runs changed nothing the included runs taught.
    assert _learned_slugs(included_only) == _learned_slugs(with_excluded)
