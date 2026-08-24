"""The manual rename repair (D4) — for a rename that happened before detection existed.

The automatic path is driven by `listeners/entity_rename.py`, which only records what it
was running to see. A rename from before that shipped left no record, and Home Assistant
does not keep the old entity id anywhere — so only the user can supply it.

Coverage targets
----------------
[RS-1] a straightforward repair moves every per-vacuum section.
[RS-2] an unknown old id changes nothing and says so.
[RS-3] old == new is refused rather than treated as a no-op success.
[RS-4] a collision changes NOTHING by default and names what is in the way. This is the
       EXPECTED case here — the new id normally holds the shell `ensure_vacuum_record`
       created on the first restart after the rename.
[RS-5] `overwrite_destination` proceeds and REPORTS what it discarded.
[RS-6] the service goes through the SAME applier as the automatic path. It returns the
       applier's own bookkeeping, so a second divergent migration cannot hide behind it.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.core.manager import EufyVacuumManager
from custom_components.eufy_vacuum.services.setup import _handle_repair_renamed_vacuum


class _Hass:
    def __init__(self, config_dir: Path) -> None:
        self.config = type("C", (), {"config_dir": str(config_dir)})()
        self.data: dict = {}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


def _wire(tmp_path: Path, data: dict) -> _Hass:
    hass = _Hass(tmp_path)
    mgr = EufyVacuumManager(hass)
    mgr.data = data
    mgr._loaded = True
    hass.data = {DOMAIN: {DATA_RUNTIME: mgr}}
    return hass


def _call(old="vacuum.alfred", new="vacuum.butler", overwrite=False):
    return SimpleNamespace(data={
        "old_entity_id": old, "new_entity_id": new, "overwrite_destination": overwrite,
    })


async def test_rs1_a_straightforward_repair_moves_every_section(tmp_path):
    data = {
        "vacuums": {"vacuum.alfred": {"a": 1}},
        "maps": {"vacuum.alfred": {"12": {}}},
        "run_profiles": {"vacuum.alfred": ["p"]},
    }
    hass = _wire(tmp_path, data)
    out = await _handle_repair_renamed_vacuum(hass, _call())

    assert out["repaired"] is True
    assert set(out["sections_moved"]) == {"vacuums", "maps", "run_profiles"}
    for section in ("vacuums", "maps", "run_profiles"):
        assert "vacuum.butler" in data[section] and "vacuum.alfred" not in data[section]


async def test_rs2_an_unknown_old_id_changes_nothing(tmp_path):
    """[RS-2] A typo and an already-repaired vacuum look identical from here, so the
    reason says what is TRUE (nothing is stored under it) rather than guessing which."""
    data = {"vacuums": {"vacuum.butler": {}}}
    hass = _wire(tmp_path, data)
    out = await _handle_repair_renamed_vacuum(hass, _call(old="vacuum.nope"))

    assert out["repaired"] is False
    assert out["reason"] == "nothing_stored_under_old_id"
    assert data == {"vacuums": {"vacuum.butler": {}}}


async def test_rs3_same_id_is_refused(tmp_path):
    hass = _wire(tmp_path, {"vacuums": {"vacuum.alfred": {}}})
    out = await _handle_repair_renamed_vacuum(
        hass, _call(old="vacuum.alfred", new="vacuum.alfred"))
    assert out["repaired"] is False and out["reason"] == "same_entity_id"


async def test_rs4_a_collision_changes_nothing_and_names_the_obstacle(tmp_path):
    """[RS-4] The EXPECTED first call. Reporting must precede any destruction: the user
    cannot consent to discarding something they have not been told about."""
    data = {
        "vacuums": {"vacuum.alfred": {"real": True}, "vacuum.butler": {"shell": True}},
        "maps": {"vacuum.alfred": {"12": {}}},
    }
    hass = _wire(tmp_path, data)
    out = await _handle_repair_renamed_vacuum(hass, _call())

    assert out["repaired"] is False
    assert out["reason"] == "destination_not_empty"
    assert out["blocked_on"] == ["vacuums"]
    assert "overwrite_destination" in out["message"]
    # nothing moved
    assert data["vacuums"]["vacuum.alfred"] == {"real": True}
    assert data["vacuums"]["vacuum.butler"] == {"shell": True}
    assert "vacuum.alfred" in data["maps"]


async def test_rs5_overwrite_proceeds_and_reports_what_it_discarded(tmp_path):
    """[RS-5] Silently overwriting would be the same class of bug as the one being
    repaired — data going away with nobody told."""
    data = {
        "vacuums": {"vacuum.alfred": {"real": True}, "vacuum.butler": {"shell": True}},
        "maps": {"vacuum.alfred": {"12": {}}},
    }
    hass = _wire(tmp_path, data)
    out = await _handle_repair_renamed_vacuum(hass, _call(overwrite=True))

    assert out["repaired"] is True
    assert out["overwrote"] == ["vacuums"]
    assert data["vacuums"] == {"vacuum.butler": {"real": True}}
    assert data["maps"] == {"vacuum.butler": {"12": {}}}


async def test_rs6_it_reports_the_appliers_own_bookkeeping(tmp_path):
    """[RS-6] `sections_moved` and `tree_moved` are written by
    `_apply_pending_entity_renames`, not by the service. Their presence is evidence the
    service delegated rather than growing a second, divergent migration."""
    tree = tmp_path / "eufy_vacuum" / "learning" / "alfred" / "jobs"
    tree.mkdir(parents=True)
    (tree / "j.json").write_text("{}", encoding="utf-8")

    data = {"vacuums": {"vacuum.alfred": {}}}
    hass = _wire(tmp_path, data)
    out = await _handle_repair_renamed_vacuum(hass, _call())

    assert out["tree_moved"] is True
    assert out["sections_moved"] == ["vacuums"]
    assert (tmp_path / "eufy_vacuum" / "learning" / "butler" / "jobs" / "j.json").is_file()
    # and the record it appended is marked applied, so a restart does not redo it
    assert data["pending_entity_renames"][0]["applied"] is True
    assert data["pending_entity_renames"][0]["manual"] is True
