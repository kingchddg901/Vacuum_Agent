# -*- coding: utf-8 -*-
"""[MER] The entity-registry half of a maintenance component rename.

WHY THESE LIVE IN tests/integration AND NOT BESIDE THEIR SIBLING. The interval migration's
suite (``tests/core/test_maintenance_component_rename_migration.py``, MCR-1..9) imports nothing
from ``homeassistant`` — it builds a ``{"maintenance": ...}`` dict and asserts on a dict. That
purity is why it is fast, and it is also exactly why nine green tests could not see that the
ENTITY REGISTRY was never migrated: there was no registry in the room to be wrong. The subject
here IS the registry, so these drive a real one. No mocking.

Coverage targets
----------------
[MER-1]  a legacy row whose canonical id is free is RENAMED IN PLACE — same entity_id, same
         history, old unique_id gone. This is the normal upgrade path.
[MER-2]  a legacy row whose canonical id is TAKEN does not raise, is pruned, and leaves the
         canonical row untouched. This is every box that already booted the new code.
[MER-3]  two legacy ids naming one canonical id: exactly one wins, the other is pruned, and
         nothing raises. Eufy's wheel really did go swivel_wheel -> caster_wheel -> canonical.
[MER-4]  all three platforms move together — button, number and sensor.
[MER-5]  idempotent: a second run is a no-op via its own latch.
[MER-6]  the registry latch is INDEPENDENT of the interval migration's latch — a box with
         ``maintenance_component_renames_v1`` already True still runs this pass.
[MER-7]  a component that was never renamed is left completely alone.
[MER-8]  the planner describes the moves and writes nothing.
[MER-9]  a RETIRED component (absorbed, no destination) has its rows pruned — the wash-dock
         Roborock case, which no machine in this house can show.
[MER-10] THE SAFETY GUARD: no retired id is still declared by a brand, and no id is both
         renamed and retired. This is the only way the pass could delete a live entity.
"""

from __future__ import annotations

from homeassistant.helpers import entity_registry as er

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.core.maintenance_entity_registry_migration import (
    REGISTRY_MIGRATION_KEY,
    migrate_maintenance_entity_registry,
    plan_entity_registry_renames,
)

VAC = "vacuum.alfred"


def _data(**migrations):
    """Minimal manager data: one vacuum with maintenance state."""
    return {"maintenance": {VAC: {"filter": {"interval_hours": 20.0}}},
            "migrations": dict(migrations)}


def _seed(hass, component, suffix="maintenance_interval", domain="number", slug=None):
    """Put a real registry row at the unique_id the platforms would have built."""
    return er.async_get(hass).async_get_or_create(
        domain,
        DOMAIN,
        f"vacuum_alfred_{component}_{suffix}",
        suggested_object_id=slug or f"alfred_{component}_{suffix}",
    ).entity_id


def test_plain_rename_keeps_the_entity_id(hass):
    """[MER-1] THE INPUT THAT MAKES THIS RED: leave the registry untouched by the rename.

    Then the canonical unique_id resolves to nothing, the platform mints a fresh entity, and
    the user's automations keep pointing at a row that will never update again. The assertion
    that matters is not merely that the canonical id exists — it is that it is THE SAME
    entity_id, because that is what carries the history and every reference to it.
    """
    original = _seed(hass, "swivel_wheel")
    reg = er.async_get(hass)
    assert reg.async_get_entity_id("number", DOMAIN, "vacuum_alfred_swivel_wheel_maintenance_interval")

    result = migrate_maintenance_entity_registry(hass, data=_data())

    assert result["ran"] is True
    assert [m["from"] for m in result["renamed"]] == ["swivel_wheel"]
    assert result["pruned"] == []
    moved = reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_omnidirectional_wheel_maintenance_interval"
    )
    assert moved == original, "the entity_id must survive, or history and automations break"
    assert reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_swivel_wheel_maintenance_interval"
    ) is None, "the legacy unique_id must be gone, not merely shadowed"


def test_collision_prunes_and_never_raises(hass):
    """[MER-2] THE INPUT THAT MAKES THIS RED: seed BOTH ids and call async_update_entity blind.

    HA raises ``ValueError: Unique id '...' is already in use``, and because the pass loops over
    every component the raise aborts the rest — leaving a box half-migrated, which is worse than
    either end state. A real box was 15-for-15 in this state, so this is the common case on any
    install that already booted the new code, not an edge case.
    """
    legacy = _seed(hass, "rolling_brush")
    canonical = _seed(hass, "main_brush")
    reg = er.async_get(hass)

    result = migrate_maintenance_entity_registry(hass, data=_data())

    assert [m["from"] for m in result["pruned"]] == ["rolling_brush"]
    assert result["renamed"] == []
    assert reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_main_brush_maintenance_interval"
    ) == canonical, "the surviving row is the one the UI has been showing"
    assert reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_rolling_brush_maintenance_interval"
    ) is None
    assert legacy != canonical


def test_two_legacy_ids_one_destination(hass):
    """[MER-3] Eufy's wheel was `swivel_wheel`, then `caster_wheel`, now canonical.

    THE INPUT THAT MAKES THIS RED: plan both moves against a free destination and apply them in
    order. The second raises on a unique_id now held by the first. Exactly one may win; the
    other has nowhere to go and is pruned.
    """
    _seed(hass, "swivel_wheel")
    _seed(hass, "caster_wheel")
    reg = er.async_get(hass)

    result = migrate_maintenance_entity_registry(hass, data=_data())

    assert len(result["renamed"]) == 1, f"exactly one may take the id, got {result['renamed']}"
    assert len(result["pruned"]) == 1
    assert result["renamed"][0]["to"] == "omnidirectional_wheel"
    assert reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_omnidirectional_wheel_maintenance_interval"
    ) is not None
    for dead in ("swivel_wheel", "caster_wheel"):
        assert reg.async_get_entity_id(
            "number", DOMAIN, f"vacuum_alfred_{dead}_maintenance_interval"
        ) is None


def test_all_three_platforms_move(hass):
    """[MER-4] THE INPUT THAT MAKES THIS RED: migrate only the number.

    The reset BUTTON and the remaining SENSOR carry the component id in their unique_ids too,
    and a partial pass leaves two thirds of the orphans behind while looking like it worked —
    the shape `f/partial_guard_blind_spot` names.
    """
    seeded = {
        ("button", "maintenance_reset"): _seed(
            hass, "mopping_cloth", "maintenance_reset", "button", "alfred_reset_mopping_cloth"),
        ("number", "maintenance_interval"): _seed(hass, "mopping_cloth"),
        ("sensor", "maintenance_remaining"): _seed(
            hass, "mopping_cloth", "maintenance_remaining", "sensor"),
    }
    reg = er.async_get(hass)

    result = migrate_maintenance_entity_registry(hass, data=_data())

    assert len(result["renamed"]) == 3, f"expected all three platforms, got {result['renamed']}"
    for (domain, suffix), original in seeded.items():
        assert reg.async_get_entity_id(
            domain, DOMAIN, f"vacuum_alfred_mop_{suffix}"
        ) == original, f"{domain} did not move"


def test_second_run_is_a_no_op(hass):
    """[MER-5] The latch. A pass that re-ran every startup would keep pruning rows a user had
    deliberately recreated."""
    _seed(hass, "swivel_wheel")
    data = _data()
    first = migrate_maintenance_entity_registry(hass, data=data)
    assert first["ran"] is True
    assert data["migrations"][REGISTRY_MIGRATION_KEY] is True

    second = migrate_maintenance_entity_registry(hass, data=data)
    assert second == {"ran": False, "renamed": [], "pruned": [], "failed": []}


def test_latch_is_independent_of_the_interval_migration(hass):
    """[MER-6] THE BUG THIS EXISTS FOR, and it is not hypothetical.

    Every box that has run this version already has ``maintenance_component_renames_v1`` set to
    True. Had the registry pass reused that key it could never have run there — including on the
    author's own machine, which is precisely where it would have been verified. Reuse the key
    and this goes red.
    """
    _seed(hass, "swivel_wheel")
    data = _data(maintenance_component_renames_v1=True,
                 maintenance_component_renames_v2=True)

    result = migrate_maintenance_entity_registry(hass, data=data)

    assert result["ran"] is True, "an already-latched interval migration must not gate this pass"
    assert len(result["renamed"]) == 1


def test_an_unrenamed_component_is_untouched(hass):
    """[MER-7] THE INPUT THAT MAKES THIS RED: match on a prefix or a substring instead of the
    exact legacy unique_id. `filter` and `sensor` were never renamed and must not move."""
    keep = {c: _seed(hass, c) for c in ("filter", "sensor", "side_brush", "cleaning_tray")}
    reg = er.async_get(hass)

    result = migrate_maintenance_entity_registry(hass, data=_data())

    assert result["renamed"] == [] and result["pruned"] == []
    for component, entity_id in keep.items():
        assert reg.async_get_entity_id(
            "number", DOMAIN, f"vacuum_alfred_{component}_maintenance_interval"
        ) == entity_id, f"{component} was never renamed and must not be touched"


def test_retired_components_are_pruned(hass):
    """[MER-9] THE INPUT THAT MAKES THIS RED: handle only COMPONENT_RENAMES.

    `cleaning_brush` and `strainer` are the two of the eight retired Roborock components that
    ever minted entities — both declared a `sensor_suffix` the integration publishes on a
    WASH-DOCK machine, so an owner of one carries six real rows for parts this integration no
    longer has any opinion about. They are absorptions, so there is no destination and the
    rename table excludes them by design; without a prune they stay `unavailable` forever.

    Not observable on the author's hardware — ivy is a charge-only S6 and publishes neither.
    """
    dead = {c: _seed(hass, c) for c in ("cleaning_brush", "strainer")}
    live = _seed(hass, "filter")
    reg = er.async_get(hass)

    result = migrate_maintenance_entity_registry(hass, data=_data())

    assert sorted(m["from"] for m in result["pruned"]) == ["cleaning_brush", "strainer"]
    assert all(m["reason"] == "component_retired" for m in result["pruned"])
    for component in dead:
        assert reg.async_get_entity_id(
            "number", DOMAIN, f"vacuum_alfred_{component}_maintenance_interval"
        ) is None, f"{component} is retired and must not linger as an unavailable row"
    assert reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_filter_maintenance_interval"
    ) == live, "a live component must survive the prune untouched"


def test_no_retired_id_is_still_declared_by_a_brand():
    """[MER-10] THE SAFETY GUARD, and the only way this migration could destroy a live entity.

    RETIRED_COMPONENTS drives an unconditional registry DELETE. If an id on that list ever
    reappears in a brand's catalog — a component un-retired, or a name reused for a different
    part — the migration would delete entities that the platforms are actively creating, every
    single startup, and the user would watch a working panel vanish on a loop.

    THE INPUT THAT MAKES THIS RED: add any RETIRED_COMPONENTS id back to any brand's
    MAINTENANCE_COMPONENTS. Deliberately a pure test with no registry: it guards the TABLE, and
    a table mistake must be caught before anything touches a user's registry at all.
    """
    from custom_components.eufy_vacuum.core.maintenance_component_rename_migration import (
        COMPONENT_RENAMES,
        RETIRED_COMPONENTS,
    )

    declared: set[str] = set()
    for brand in ("dreame", "eufy", "roborock"):
        module = __import__(
            f"custom_components.eufy_vacuum.adapters.{brand}.maintenance_components",
            fromlist=["MAINTENANCE_COMPONENTS"],
        )
        declared |= set(module.MAINTENANCE_COMPONENTS)

    clash = RETIRED_COMPONENTS & declared
    assert not clash, (
        f"{sorted(clash)} is listed as RETIRED but a brand still declares it. This migration "
        "would delete those entities on every startup while the platforms recreate them. "
        "Remove it from RETIRED_COMPONENTS, or stop declaring it."
    )
    # The same id must not be in both tables either: one says rename it, the other says delete
    # it, and which wins would be decided by nothing more than loop order.
    overlap = RETIRED_COMPONENTS & set(COMPONENT_RENAMES)
    assert not overlap, f"{sorted(overlap)} is both renamed and retired — pick one"


def test_plan_reports_without_writing(hass):
    """[MER-8] The planner is the reviewable half: it must describe the moves and change
    nothing, so a maintainer can see what a release will do to real users before it does it."""
    _seed(hass, "swivel_wheel")
    reg = er.async_get(hass)

    moves = plan_entity_registry_renames(hass, data=_data())

    assert [(m["from"], m["to"], m["action"]) for m in moves] == [
        ("swivel_wheel", "omnidirectional_wheel", "rename")
    ]
    assert reg.async_get_entity_id(
        "number", DOMAIN, "vacuum_alfred_swivel_wheel_maintenance_interval"
    ) is not None, "planning must not mutate the registry"
