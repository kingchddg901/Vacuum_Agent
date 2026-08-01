"""RP-009 (RF-04) — entity ownership without prefix matching.

DR-SETUP-1 proved the prefix scan deleted a sibling vacuum's registry entries
(vacuum.alfred deleting map "2" swept vacuum.alfred_2). Ownership is now
answered by forward-reconstruction (unique_ids_for_map) and live attributes
(entity_belongs_to) — never by dissecting the non-injective unique_id join.
"""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.eufy_vacuum.entity_helpers import (
    ROOM_ENTITY_SUFFIXES,
    entity_belongs_to,
    make_room_unique_id,
    unique_ids_for_map,
)


def _victim_ids():
    """vacuum.alfred_2's entities — HA's auto-suffix sibling of vacuum.alfred."""
    return [
        make_room_unique_id(vacuum_entity_id="vacuum.alfred_2", map_id=m,
                            room_id=r, suffix=s)
        for m in ("5", "9") for r in (1, 3) for s in ("enabled", "order")
    ]


def test_closed_set_excludes_sibling_vacuum():
    """[EO-1] the DR-SETUP-1 collision: the closed set for (vacuum.alfred, map 2)
    contains ZERO of vacuum.alfred_2's ids, even though every one of them starts
    with the old scan's prefix 'vacuum_alfred_2_'."""
    closed = unique_ids_for_map(vacuum_entity_id="vacuum.alfred", map_id="2",
                                room_ids=[1, 3])
    victims = _victim_ids()
    assert all(v.startswith("vacuum_alfred_2_") for v in victims)  # the old trap
    assert not closed.intersection(victims)


def test_closed_set_is_exact():
    """[EO-2] exactly rooms x suffixes ids, all owned by the requested map."""
    closed = unique_ids_for_map(vacuum_entity_id="vacuum.alfred", map_id="2",
                                room_ids=[1, 3, "junk"])   # junk id skipped
    assert len(closed) == 2 * len(ROOM_ENTITY_SUFFIXES)
    assert closed == unique_ids_for_map(
        vacuum_entity_id="vacuum.alfred", map_id="2", room_ids=["1", "3"])


def test_entity_belongs_to_by_attributes():
    """[EO-3] ownership by live attributes: sibling vacuum and other-map entities
    never belong; an entity WITHOUT the ownership attributes (EP-2's maintenance
    number) never belongs — so no sweep can classify it stale."""
    own = SimpleNamespace(vacuum_entity_id="vacuum.alfred", map_id="2")
    other_map = SimpleNamespace(vacuum_entity_id="vacuum.alfred", map_id="20")
    sibling = SimpleNamespace(vacuum_entity_id="vacuum.alfred_2", map_id="5")
    maintenance = SimpleNamespace()   # no ownership attributes at all

    assert entity_belongs_to(own, vacuum_entity_id="vacuum.alfred", map_id="2")
    assert not entity_belongs_to(other_map, vacuum_entity_id="vacuum.alfred", map_id="2")
    assert not entity_belongs_to(sibling, vacuum_entity_id="vacuum.alfred", map_id="2")
    assert not entity_belongs_to(maintenance, vacuum_entity_id="vacuum.alfred", map_id="2")


def test_room_entity_base_exposes_ownership_properties():
    """[EO-4] (REVIEW D2) the shared base entity exposes read-only
    vacuum_entity_id / map_id properties and entity_belongs_to consumes them."""
    from custom_components.eufy_vacuum.room_entities import EufyVacuumRoomEntity

    ent = EufyVacuumRoomEntity(
        coordinator_key="k", vacuum_entity_id="vacuum.alfred", map_id="2",
        room_id=1, room_data={"name": "Kitchen"}, unique_suffix="enabled",
    )
    assert ent.vacuum_entity_id == "vacuum.alfred"
    assert ent.map_id == "2"
    assert entity_belongs_to(ent, vacuum_entity_id="vacuum.alfred", map_id="2")
    assert not entity_belongs_to(ent, vacuum_entity_id="vacuum.alfred_2", map_id="2")


def test_suffix_registry_matches_room_entity_classes():
    """[EO-5] parity: every room-entity class's suffix is in ROOM_ENTITY_SUFFIXES —
    a NEW room platform must register its suffix or the closed-set delete would
    leave its registry entries behind."""
    from custom_components.eufy_vacuum.room_entities import EufyVacuumRoomEntity

    def _suffix_of(cls, **extra):
        ent = cls(coordinator_key="k", vacuum_entity_id="vacuum.a", map_id="1",
                  room_id=1, room_data={"name": "R"}, **extra)
        return ent.unique_id.rsplit("_", 1)[-1]

    from custom_components.eufy_vacuum.switch import EufyVacuumRoomEnabledSwitch
    from custom_components.eufy_vacuum.number import EufyVacuumRoomOrderNumber
    from custom_components.eufy_vacuum.sensor.room_history import (
        EufyVacuumRoomCleaningHistorySensor,
    )
    from custom_components.eufy_vacuum.sensor.room_rule_status import (
        EufyVacuumRoomRuleStatusSensor,
    )

    assert _suffix_of(EufyVacuumRoomEnabledSwitch) == "enabled"
    assert _suffix_of(EufyVacuumRoomOrderNumber) == "order"
    # multi-word suffixes: check membership on the full ids instead
    hist = EufyVacuumRoomCleaningHistorySensor(
        coordinator_key="k", vacuum_entity_id="vacuum.a", map_id="1",
        room_id=1, room_data={"name": "R"})
    rule = EufyVacuumRoomRuleStatusSensor(
        coordinator_key="k", vacuum_entity_id="vacuum.a", map_id="1",
        room_id=1, room_data={"name": "R"})
    closed = unique_ids_for_map(vacuum_entity_id="vacuum.a", map_id="1", room_ids=[1])
    for ent in (hist, rule):
        assert ent.unique_id in closed, ent.unique_id
    assert len(closed) == len(ROOM_ENTITY_SUFFIXES)
