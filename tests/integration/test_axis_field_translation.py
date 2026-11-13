"""The two hops that carry a brand's own field name across the service boundary.

Issue #71 §B: Eufy and Dreame call the pass-density axis `clean_intensity`; Roborock
calls the same physical property `path_type`. The card speaks the CANONICAL name
everywhere and the backend translates at both boundaries — in on write, out on read.

THESE TESTS EXIST BECAUSE ABLATION FOUND NOTHING COVERING EITHER HOP. Reverting the
write to the canonical key, or the read to the canonical key, left the entire suite
green — 5102 tests — while a Roborock picker would save and silently lose the value and
its chips would never show as selected. That is the #70 failure shape exactly: each
piece verified, the user's path broken.

Why translation rather than letting the card send the brand's field: the service schema
`_UPDATE_ROOM_FIELDS_SCHEMA` is a bare `vol.Schema` with no `extra=`, so PREVENT_EXTRA
is in force and a `path_type` key raises *extra keys not allowed* — killing the WHOLE
call, including `clean_mode`, `fan_speed` and colour in the same payload.

Coverage targets
----------------
[AXT-1] WRITE on a brand whose word differs: the stored field is the brand's own, and
        the canonical key is NOT written beside it.
[AXT-2] WRITE on a brand using the canonical word is unchanged.
[AXT-3] the written value survives a round trip through the save path, rather than
        being stripped by `_finalize_room_update` as an undeclared field.
[AXT-4] READ: the room switch exposes the stored brand field under the canonical name.
[AXT-5] READ on a canonical-word brand is unchanged.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    register_adapter_config,
)
from custom_components.eufy_vacuum.room_entities import EufyVacuumRoomEntity

from tests._factories import VAC as _VAC, MAP as _MAP
from .conftest import setup_map

from tests.brand_catalogs import EUFY_BLOCK, ROBOROCK_BLOCK


def _register(vacuum, *, block, vocabulary):
    """Register a minimal adapter whose vocabulary names the axis one way or the other."""
    register_adapter_config(
        vacuum,
        {
            "adapter_id": "probe",
            "source": "config",
            "room_profiles": block,
            "vocabulary": vocabulary,
        },
    )


_ROBOROCK_VOCAB = {
    "path_type_options": [
        {"value": "standard", "label": "Standard"},
        {"value": "deep", "label": "Deep"},
    ]
}
_EUFY_VOCAB = {
    "clean_intensity_options": [
        {"value": "Quick", "label": "Quick"},
        {"value": "Deep", "label": "Deep"},
    ]
}


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------

async def test_axt_1_a_brand_word_is_stored_under_that_brands_field(manager):
    """[AXT-1] THE LIVE CASE. The card sends `clean_intensity`; a Roborock room must
    end up with `path_type`.

    The second assertion is the load-bearing one. Writing the canonical key as well
    would look harmless and be the start of a silent replica pair — two fields for one
    axis, drifting apart on every later edit.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=ROBOROCK_BLOCK, vocabulary=_ROBOROCK_VOCAB)

    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, clean_intensity="deep"
    )

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room.get("path_type") == "deep", "the brand's own field was not written"
    assert "clean_intensity" not in room, (
        "wrote the canonical key too — two fields for one axis is a silent replica pair"
    )


async def test_axt_2_a_canonical_brand_is_unchanged(manager):
    """[AXT-2] The no-regression guard. Eufy names the axis canonically, so nothing
    about its storage moves — this change must be invisible to two of three brands."""
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=EUFY_BLOCK, vocabulary=_EUFY_VOCAB)

    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, clean_intensity="Deep"
    )

    room = manager.data["maps"][_VAC][_MAP]["rooms"]["1"]
    assert room.get("clean_intensity") == "Deep"
    assert "path_type" not in room


async def test_axt_3_the_written_value_is_not_stripped_on_the_way_out(manager):
    """[AXT-3] THE SHOULDER. `_finalize_room_update` runs on every save and silently
    DELETES any `VOCABULARY_FIELD` the brand's profiles do not declare — no log, no
    return signal.

    So writing the canonical key on a Roborock would be removed by the very same save
    that wrote it, and the picker would appear to work exactly once. This asserts the
    value is still there AFTER the round trip, not merely that the update function put
    it in a dict.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=ROBOROCK_BLOCK, vocabulary=_ROBOROCK_VOCAB)

    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, clean_intensity="deep"
    )
    stored = manager.get_managed_rooms(vacuum_entity_id=_VAC, map_id=_MAP)

    assert stored["rooms"]["1"].get("path_type") == "deep", (
        "the value was stripped after being written — the axis is not declared by this "
        "brand's profiles, or the wrong field was used"
    )


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "block,vocabulary,stored_field,word",
    [
        (ROBOROCK_BLOCK, _ROBOROCK_VOCAB, "path_type", "deep"),
        (EUFY_BLOCK, _EUFY_VOCAB, "clean_intensity", "Deep"),
    ],
    ids=["brand-word", "canonical-word"],
)
async def test_axt_4_5_the_switch_exposes_the_value_under_the_canonical_name(
    hass, manager, block, vocabulary, stored_field, word
):
    """[AXT-4][AXT-5] THE READ HOP, asserted on the ENTITY'S OWN ATTRIBUTES.

    The card compares its chips against `attrs.clean_intensity`, so a room storing the
    brand's word must still surface under the canonical one. Reading only the canonical
    key left every Roborock chip unselected — and the rooms-view path chip hidden by
    its FALSY branch rather than the "is this the default" branch anyone debugging it
    would have looked at.

    ⚠ A FIRST VERSION OF THIS TEST ASSERTED `resolve_axis` AND THE STORED DICT INSTEAD,
    AND ABLATION CAUGHT IT: reverting `room_entities` to read the canonical key left it
    green, because it never touched the entity. Testing the two pieces either side of a
    hop is not testing the hop.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=block, vocabulary=vocabulary)
    manager.update_room_fields(
        vacuum_entity_id=_VAC, map_id=_MAP, room_id=1, clean_intensity=word
    )
    assert manager.data["maps"][_VAC][_MAP]["rooms"]["1"].get(stored_field) == word

    entity = EufyVacuumRoomEntity(
        coordinator_key="eufy_vacuum",
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=1,
        room_data={"name": "Kitchen"},
        unique_suffix="probe",
    )
    entity.hass = hass

    attrs = entity.extra_state_attributes

    assert attrs["clean_intensity"] == word, (
        "the card reads the canonical key; a brand-word room surfaced nothing, so "
        "every chip rendered unselected"
    )
    assert [o["value"] for o in attrs["clean_intensity_options"]] == [
        o["value"] for o in vocabulary[f"{stored_field}_options"]
    ], "the picker's options must resolve to the brand's declared list"


async def test_axt_6_the_switch_exposes_floor_material(hass, manager):
    """[AXT-6] THE SAME HOP, for the appearance field — and it was broken on a live box.

    floor_material was stored correctly by build_managed_rooms and read correctly by
    the card's resolveFloorType, and selecting a material did NOTHING, because the
    value never travelled between them: the room entity's attribute dict is built
    from an explicit field list and the new field was not in it. The card reads a
    room's settings from THESE ATTRIBUTES, so a field absent here cannot reach the
    renderer however correctly it is stored.

    Both ends had tests. Both passed. That is this file's whole thesis: testing the
    two pieces either side of a hop is not testing the hop.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=EUFY_BLOCK, vocabulary=_EUFY_VOCAB)

    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    rooms["1"]["floor_material"] = "slate"

    entity = EufyVacuumRoomEntity(
        coordinator_key="eufy_vacuum",
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=1,
        room_data={"name": "Kitchen"},
        unique_suffix="probe",
    )
    entity.hass = hass
    attrs = entity.extra_state_attributes

    assert attrs["floor_material"] == "slate", (
        "the card reads room settings off these attributes; without this the chip "
        "renders but selecting a material changes nothing"
    )


async def test_axt_7_floor_material_defaults_to_empty_not_missing(hass, manager):
    """[AXT-7] A room that never set one surfaces "", not an absent key.

    Absent would work by luck downstream (falsy either way) but leaves every consumer
    relying on a missing key rather than a value, and makes “never set” and “cleared”
    different shapes on the wire for no reason.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=EUFY_BLOCK, vocabulary=_EUFY_VOCAB)

    entity = EufyVacuumRoomEntity(
        coordinator_key="eufy_vacuum",
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=1,
        room_data={"name": "Kitchen"},
        unique_suffix="probe",
    )
    entity.hass = hass
    attrs = entity.extra_state_attributes

    assert "floor_material" in attrs
    assert attrs["floor_material"] == ""
    assert attrs["floor_type"], "the appearance field must not disturb floor_type"


async def test_axt_8_the_switch_exposes_floor_rotation(hass, manager):
    """[AXT-8] THE SAME HOP AGAIN, for the per-room map-texture angle.

    Third field across this dict, and the first two both shipped broken here, so it
    gets its own gate rather than trusting that the lesson stuck.

    Rotation is PER ROOM because it describes the house: the planks in a hallway and a
    living room routinely run different ways, which the per-material
    --evcc-floor-<type>-map-rotate token could never express.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=EUFY_BLOCK, vocabulary=_EUFY_VOCAB)

    rooms = manager.data["maps"][_VAC][_MAP]["rooms"]
    rooms["1"]["floor_rotation"] = 90.0

    entity = EufyVacuumRoomEntity(
        coordinator_key="eufy_vacuum",
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=1,
        room_data={"name": "Kitchen"},
        unique_suffix="probe",
    )
    entity.hass = hass
    attrs = entity.extra_state_attributes

    assert attrs["floor_rotation"] == 90.0, (
        "the card builds its map paint key from this attribute; without it every room "
        "paints at the theme-wide angle and the per-room control does nothing"
    )


async def test_axt_9_floor_rotation_defaults_to_zero_not_missing(hass, manager):
    """[AXT-9] A room that never set one surfaces 0.0, not an absent key.

    0 means "as authored", which is exactly what every room written before the field
    means. The card does `Number(attrs.floor_rotation ?? 0) || 0`, so an absent key
    would work by luck; publishing a real 0 keeps the consumer's check total and keeps
    "never set" and "set back to 0" the same shape on the wire.
    """
    clear_registry()
    setup_map(manager, _VAC, _MAP, count=2)
    _register(_VAC, block=EUFY_BLOCK, vocabulary=_EUFY_VOCAB)

    entity = EufyVacuumRoomEntity(
        coordinator_key="eufy_vacuum",
        vacuum_entity_id=_VAC,
        map_id=_MAP,
        room_id=1,
        room_data={"name": "Kitchen"},
        unique_suffix="probe",
    )
    entity.hass = hass
    attrs = entity.extra_state_attributes

    assert attrs["floor_rotation"] == 0.0
    assert isinstance(attrs["floor_rotation"], float)
