# -*- coding: utf-8 -*-
"""[MCR] The interval carry-over across a component-key rename.

WHAT THIS GUARDS. A component id is a STORAGE KEY: ``data["maintenance"][vacuum][component]``.
Renaming one orphans whatever it held. Two of the three fields heal themselves -- the next reset
rewrites ``reset_at`` and ``reset_at_usage_hours``, and the card visibly shows the component as
never-reset until then. ``interval_hours`` does not: it is a preference, nothing prompts the user
to restore it, and the old value survives only in ``.storage``, which they are correctly told
never to open. It silently reverts to the default and there is no way for them to notice.

That is not hypothetical. The September 2026 canonicalisation shipped without this and lost a
real 65-hour interval on a real box.
"""

from __future__ import annotations

from custom_components.eufy_vacuum.core.maintenance_component_rename_migration import (
    COMPONENT_RENAMES,
    MIGRATION_KEY,
    migrate_maintenance_component_renames,
    plan_component_rename_migration,
)


def _data(maintenance):
    return {"maintenance": maintenance}


def test_a_custom_interval_moves_to_the_new_key():
    """[MCR-1] the whole point: a preference survives the rename."""
    data = _data({"vacuum.a": {"mop_cloth": {"interval_hours": 19.0}}})
    result = migrate_maintenance_component_renames(data=data)

    assert result["ran"] is True
    assert data["maintenance"]["vacuum.a"]["mop"]["interval_hours"] == 19.0
    # the legacy row is LEFT IN PLACE — it is inert (no adapter declares it) and deleting a
    # user's stored data to tidy up is the worse trade.
    assert data["maintenance"]["vacuum.a"]["mop_cloth"]["interval_hours"] == 19.0


def test_reset_timestamps_are_not_carried():
    """[MCR-2] only the interval moves — the rest self-heals and must not be faked forward.

    Carrying ``reset_at`` would tell the user a part was serviced under a name that did not
    exist then. The card showing "never reset" is the honest state, and one reset fixes it.
    """
    data = _data({"vacuum.a": {"mop_cloth": {
        "interval_hours": 19.0,
        "reset_at": "2026-05-17T10:35:09Z",
        "reset_at_usage_hours": 21.0,
    }}})
    migrate_maintenance_component_renames(data=data)

    moved = data["maintenance"]["vacuum.a"]["mop"]
    assert moved == {"interval_hours": 19.0}


def test_a_value_already_on_the_new_key_is_never_overwritten():
    """[MCR-3] the destination is the user's LATER choice — they set it after the rename."""
    data = _data({"vacuum.a": {
        "mop_cloth": {"interval_hours": 19.0},
        "mop": {"interval_hours": 7.0},
    }})
    migrate_maintenance_component_renames(data=data)

    assert data["maintenance"]["vacuum.a"]["mop"]["interval_hours"] == 7.0


def test_a_rename_chain_takes_the_most_recently_reset_row():
    """[MCR-4] THE BUG REAL DATA FOUND, pinned.

    Eufy's front wheel was renamed TWICE: swivel_wheel -> caster_wheel -> omnidirectional_wheel.
    A box that lived through both carries two dead rows aimed at one destination. Planning each
    move independently against an empty destination let BOTH be planned, and applying them in
    order let the OLDER one win: a real box had caster_wheel 30h, set an hour earlier, silently
    replaced by swivel_wheel 65h, dead since May.

    THE INPUT THAT MAKES THIS RED: remove the grouping and the 65.0 comes back.
    """
    data = _data({"vacuum.a": {
        "swivel_wheel": {"interval_hours": 65.0, "reset_at": "2026-05-17T10:36:03Z"},
        "caster_wheel": {"interval_hours": 30.0, "reset_at": "2026-09-13T01:18:57Z"},
    }})
    changes = plan_component_rename_migration(data=data)

    aimed_at_wheel = [c for c in changes if c["to"] == "omnidirectional_wheel"]
    assert len(aimed_at_wheel) == 1, "two sources, one destination — exactly one may survive"
    assert aimed_at_wheel[0]["from"] == "caster_wheel"
    assert aimed_at_wheel[0]["interval_hours"] == 30.0


def test_a_row_with_no_reset_at_loses_to_one_that_has_it():
    """[MCR-5] the tie-break, from the other side: a never-reset row is the weaker claim."""
    data = _data({"vacuum.a": {
        "swivel_wheel": {"interval_hours": 65.0, "reset_at": "2026-05-17T10:36:03Z"},
        "caster_wheel": {"interval_hours": 30.0},
    }})
    changes = plan_component_rename_migration(data=data)
    winner = [c for c in changes if c["to"] == "omnidirectional_wheel"][0]

    assert winner["from"] == "swivel_wheel"


def test_a_legacy_row_with_no_interval_is_not_a_change():
    """[MCR-6] reset-only rows carry no preference, so there is nothing to rescue."""
    data = _data({"vacuum.a": {"mop_cloth": {"reset_at": "2026-05-17T10:35:09Z"}}})
    assert plan_component_rename_migration(data=data) == []


def test_it_runs_once():
    """[MCR-7] idempotent, and the second call is a no-op rather than a re-apply."""
    data = _data({"vacuum.a": {"mop_cloth": {"interval_hours": 19.0}}})
    assert migrate_maintenance_component_renames(data=data)["ran"] is True
    assert data["migrations"][MIGRATION_KEY] is True

    data["maintenance"]["vacuum.a"]["mop"]["interval_hours"] = 7.0
    assert migrate_maintenance_component_renames(data=data)["ran"] is False
    assert data["maintenance"]["vacuum.a"]["mop"]["interval_hours"] == 7.0


def test_malformed_storage_is_survived_not_raised():
    """[MCR-8] this runs during setup on every install; one bad shape must not take it down."""
    for junk in ({}, {"maintenance": None}, {"maintenance": {"vacuum.a": None}},
                 {"maintenance": {"vacuum.a": {"mop_cloth": "not a dict"}}}):
        assert plan_component_rename_migration(data=junk) == []


def test_the_table_holds_only_one_to_one_renames():
    """[MCR-9] ABSORPTIONS MUST NEVER BE IN HERE, and this is the guard that says so.

    A rename has one destination. An absorption does not: Roborock's cleaning_brush and strainer
    both fold into one panel, dustbin and water_filter both into filter. Carrying an interval
    across one of those would have to pick between two source values or clobber a destination
    that already holds its own — so those legitimately drop to the default and are covered by
    the release note instead.

    The named ids below are the absorbed set. A future edit that adds one here is the mistake
    this test exists to catch.
    """
    absorbed = {"cleaning_brush", "strainer", "dustbin", "water_filter",
                "dust_bag", "clean_water_tank", "dirty_water_tank", "main_wheel"}
    assert not (set(COMPONENT_RENAMES) & absorbed), (
        "an ABSORBED component is in the rename table — it has no single destination"
    )
