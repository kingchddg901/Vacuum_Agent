"""The one-shot repair that lifts a stored pause timeout of 0 to 15.

Context: ``pause_timeout_minutes_default`` defaulted to 0 (the timeout OFF), no
adapter declared otherwise, and the GETTER persisted its own fallback on read — so
every install ended up with a hard 0 stamped in, and a paused run had nothing that
would ever close it. Observed live on 2026-08-09.

Coverage targets
----------------
[PTM-1] an explicit stored 0 is raised to 15.
[PTM-2] a non-zero stored value is left alone — this repairs the OFF case only.
[PTM-3] an ABSENT value stays absent, so the computed default still reaches it.
[PTM-4] the migration latches and is idempotent.
[PTM-5] ``force`` re-runs a latched migration.
[PTM-6] the planner is pure — planning alone changes nothing.
[PTM-7] a malformed vacuums bucket does not raise.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.core.pause_timeout_migration import (
    MIGRATION_KEY,
    REPAIRED_MINUTES,
    migrate_pause_timeout_defaults,
    plan_pause_timeout_migration,
)


def _data(vacuums: dict) -> dict:
    return {"vacuums": vacuums}


def test_explicit_zero_is_raised():
    """[PTM-1] The case this exists for: the timeout was off, so nothing closed a
    paused run."""
    data = _data({"vacuum.ivy": {"pause_timeout_minutes_default": 0}})
    result = migrate_pause_timeout_defaults(data=data)
    assert result["ran"] is True
    assert data["vacuums"]["vacuum.ivy"]["pause_timeout_minutes_default"] == REPAIRED_MINUTES
    assert [c["vacuum_entity_id"] for c in result["changes"]] == ["vacuum.ivy"]


def test_a_configured_value_is_left_alone():
    """[PTM-2] Only 0 is repaired.

    The guard against a repair that flattens the setting: someone who chose 30 must
    keep 30. A migration that rewrote every vacuum to 15 would satisfy [PTM-1] and
    silently discard every real preference on the install.
    """
    data = _data({"vacuum.alfred": {"pause_timeout_minutes_default": 30}})
    result = migrate_pause_timeout_defaults(data=data)
    assert data["vacuums"]["vacuum.alfred"]["pause_timeout_minutes_default"] == 30
    assert result["changes"] == []


def test_absent_stays_absent():
    """[PTM-3] An unset vacuum is NOT stamped with a value.

    Absence is how a vacuum inherits the computed default and any future change to
    it. Writing 15 here would recreate exactly the read-side stamping this repair
    exists to undo — the bug, reintroduced by its own fix.
    """
    data = _data({"vacuum.new": {"some_other_key": 1}})
    migrate_pause_timeout_defaults(data=data)
    assert "pause_timeout_minutes_default" not in data["vacuums"]["vacuum.new"]


def test_latches_and_is_idempotent():
    """[PTM-4] It runs once. A second pass must not re-repair a value the user has
    since deliberately set back to 0."""
    data = _data({"vacuum.ivy": {"pause_timeout_minutes_default": 0}})
    migrate_pause_timeout_defaults(data=data)
    assert data["migrations"][MIGRATION_KEY] is True

    data["vacuums"]["vacuum.ivy"]["pause_timeout_minutes_default"] = 0   # user turns it off
    second = migrate_pause_timeout_defaults(data=data)
    assert second["ran"] is False
    assert data["vacuums"]["vacuum.ivy"]["pause_timeout_minutes_default"] == 0


def test_force_reruns_a_latched_migration():
    """[PTM-5] force is the maintainer escape hatch, and must actually bypass the latch."""
    data = _data({"vacuum.ivy": {"pause_timeout_minutes_default": 0}})
    migrate_pause_timeout_defaults(data=data)
    data["vacuums"]["vacuum.ivy"]["pause_timeout_minutes_default"] = 0
    assert migrate_pause_timeout_defaults(data=data, force=True)["ran"] is True
    assert data["vacuums"]["vacuum.ivy"]["pause_timeout_minutes_default"] == REPAIRED_MINUTES


def test_planner_is_pure():
    """[PTM-6] Planning must not mutate — the plan is inspectable before it is applied."""
    data = _data({"vacuum.ivy": {"pause_timeout_minutes_default": 0}})
    changes = plan_pause_timeout_migration(data=data)
    assert len(changes) == 1
    assert data["vacuums"]["vacuum.ivy"]["pause_timeout_minutes_default"] == 0
    assert "migrations" not in data


def test_malformed_buckets_do_not_raise():
    """[PTM-7] Store contents are not guaranteed well-shaped, and a migration that
    throws on start takes the whole integration down with it."""
    data = {"vacuums": {"vacuum.a": None, "vacuum.b": "nonsense", "vacuum.c": []}}
    result = migrate_pause_timeout_defaults(data=data)
    assert result["ran"] is True
    assert result["changes"] == []
