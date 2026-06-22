"""Integration tests for the furnished custom render backend (Wave 0).

These cover the per-layout furnished-art data model + the three new services
(set_furnished_art_placement / set_furnished_render_mode / set_room_viewport),
the room-scoped art upload convention, the resolve_furnished_render projection,
the delete_custom_layout art sweep, and per-layout isolation — all through the
real service registry + get_map_segments, never by hand-reading files.

Re-run safety (docs/testing/05-gotchas-and-pitfalls.md #2/#11): the HA test
config_dir is shared/persistent, so each test uses a UNIQUE map_id — the
custom_layouts bucket persists between tests otherwise and assertions on the
active layout / its rooms would drift on a re-run.

Coverage targets
----------------
[FURN-1]  create layout mints an empty rooms:{} + no home_art/render_mode.
[FURN-2]  set_furnished_art_placement scope=home round-trips via get_map_segments.
[FURN-3]  set_furnished_art_placement scope=room round-trips + per-room override.
[FURN-4]  set_furnished_art_placement scope=room without room_id → missing_room_id.
[FURN-5]  set_furnished_art_placement all-null clears the placement.
[FURN-6]  set_furnished_render_mode at the layout level + per-room level.
[FURN-7]  set_room_viewport round-trips; all-null clears it.
[FURN-8]  any furnished service with no active layout → no_active_layout.
[FURN-9]  upload art_scope=home writes the custom_<id>_home_art variant onto
          home_art, NOT backdrop_variant.
[FURN-10] upload art_scope=room writes custom_<id>_room_<rid> onto rooms[rid].
[FURN-11] upload art_scope without layout_id → layout_id_required;
          scope=room without room_id → missing_room_id.
[FURN-12] resolve_furnished_render: None in cv mode / no art; populated when art set,
          art_url resolved from image_variants.
[FURN-13] delete_custom_layout sweeps the furnished-art variants from image_variants.
[FURN-14] per-layout isolation: two layouts' furnished art don't leak.
[FURN-15] set_furnished_render_mode with a blank/whitespace room_id → layout level, no
          junk rooms[""] entry (regression for the `if room_id is None` gap).
[FURN-16] set_furnished_art_placement clamps scale to the card's [0.05, 20] range so a
          degenerate 0 (renderer coerces it back to 1x) can't round-trip verbatim.
"""

from __future__ import annotations

import base64
import io

import pytest

from custom_components.eufy_vacuum.const import (
    DOMAIN,
    SERVICE_CREATE_CUSTOM_LAYOUT,
    SERVICE_DELETE_CUSTOM_LAYOUT,
    SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
    SERVICE_SET_FURNISHED_ART_PLACEMENT,
    SERVICE_SET_FURNISHED_RENDER_MODE,
    SERVICE_SET_ROOM_VIEWPORT,
    SERVICE_SET_SEGMENTATION_MODE,
)
from custom_components.eufy_vacuum.mapping.manager import MappingManager
from custom_components.eufy_vacuum.mapping.map_source import resolve_furnished_render
from custom_components.eufy_vacuum.mapping.mapping_services import (
    SERVICE_GET_MAP_SEGMENTS,
    SERVICE_UPLOAD_MAP_IMAGE,
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"


@pytest.fixture
def pil():
    return pytest.importorskip("PIL")


def _tiny_png_b64() -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 40, 40)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture
async def mapping_services(hass, manager):
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


async def _svc(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


async def _create_layout(hass, map_id, *, name="Furnished"):
    """Create + activate a custom layout (flips the map into custom mode) and return
    its layout_id."""
    res = await _svc(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                     {"vacuum_entity_id": _VAC, "map_id": map_id, "name": name})
    return res["layout_id"]


async def _segments(hass, map_id):
    return await _svc(hass, SERVICE_GET_MAP_SEGMENTS,
                      {"vacuum_entity_id": _VAC, "map_id": map_id})


def _layout_summary(segments, layout_id):
    for lay in segments["custom_layouts"]:
        if lay["id"] == layout_id:
            return lay
    raise AssertionError(f"layout {layout_id} not in summary")


# ---------------------------------------------------------------------------
# Data model + service round-trips
# ---------------------------------------------------------------------------

async def test_create_layout_mints_empty_rooms(hass, mapping_services):
    """[FURN-1] a fresh layout has an empty rooms:{} and no home_art/render_mode yet."""
    map_id = "furn_create"
    lid = await _create_layout(hass, map_id)
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["rooms"] == {}
    assert lay["home_art"] is None
    assert lay["render_mode"] is None


async def test_set_home_art_placement_roundtrip(hass, mapping_services):
    """[FURN-2] set_furnished_art_placement scope=home persists the transform onto the
    layout's home_art (rounded 4dp), surfaced back through get_map_segments."""
    map_id = "furn_home_place"
    lid = await _create_layout(hass, map_id)
    res = await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home",
        "tx": 1.23456, "ty": 2.5, "scale": 1.5, "rotation": 90})
    assert res["saved"] is True
    assert res["action"] == "set"

    lay = _layout_summary(await _segments(hass, map_id), lid)
    transform = lay["home_art"]["art_placement_transform"]
    assert transform == {"tx": 1.2346, "ty": 2.5, "scale": 1.5, "rotation": 90.0}


async def test_set_room_art_placement_roundtrip(hass, mapping_services):
    """[FURN-3] scope=room writes a per-room override under rooms[room_id]; a missing
    coord defaults (tx=0,ty=0,scale=1,rotation=0) once at least one is set."""
    map_id = "furn_room_place"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "room",
        "room_id": 4, "tx": 5.0})  # only tx set → others default
    lay = _layout_summary(await _segments(hass, map_id), lid)
    transform = lay["rooms"]["4"]["art_placement_transform"]
    assert transform == {"tx": 5.0, "ty": 0.0, "scale": 1.0, "rotation": 0.0}
    # home_art untouched by a room-scoped write
    assert lay["home_art"] is None


async def test_set_room_art_placement_requires_room_id(hass, mapping_services):
    """[FURN-4] scope=room with no room_id → missing_room_id."""
    map_id = "furn_room_noid"
    await _create_layout(hass, map_id)
    res = await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "room", "tx": 1.0})
    assert res["saved"] is False
    assert res["reason"] == "missing_room_id"


async def test_clear_home_art_placement(hass, mapping_services):
    """[FURN-5] all-null tx/ty/scale/rotation clears the placement."""
    map_id = "furn_clear"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home", "tx": 3.0})
    # now clear (omit all coords)
    res = await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home"})
    assert res["action"] == "cleared"
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert "art_placement_transform" not in (lay["home_art"] or {})


async def test_set_render_mode_layout_and_room(hass, mapping_services):
    """[FURN-6] render mode at the layout level (room_id omitted) and per-room."""
    map_id = "furn_mode"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_SET_FURNISHED_RENDER_MODE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "mode": "blend"})
    await _svc(hass, SERVICE_SET_FURNISHED_RENDER_MODE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "mode": "art", "room_id": "2"})
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["render_mode"] == "blend"
    assert lay["rooms"]["2"]["render_mode"] == "art"


async def test_set_render_mode_blank_room_id_is_layout_level(hass, mapping_services):
    """[FURN-15] a blank/whitespace room_id is treated as the LAYOUT level (like None) and
    must NOT mint a junk rooms[""] entry. Regression: the handler used `if room_id is None`
    so an empty string fell into the per-room branch (the sibling services guard it)."""
    map_id = "furn_mode_blank"
    lid = await _create_layout(hass, map_id)
    res = await _svc(hass, SERVICE_SET_FURNISHED_RENDER_MODE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "mode": "art", "room_id": "  "})
    assert res["saved"] is True
    assert res["room_id"] is None              # reported as layout-level, not ""
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["render_mode"] == "art"
    assert lay["rooms"] == {}                   # no phantom empty-key room


async def test_set_home_art_placement_scale_clamped(hass, mapping_services):
    """[FURN-16] scale is clamped to the card's [0.05, 20] range, so a degenerate 0 (which
    the renderer coerces back to 1x via `Number(scale) || 1`) or an absurd value can't be
    persisted verbatim and leave state/render disagreeing."""
    map_id = "furn_scale_clamp"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home", "scale": 0})
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["home_art"]["art_placement_transform"]["scale"] == 0.05
    await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home", "scale": 100})
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["home_art"]["art_placement_transform"]["scale"] == 20.0


async def test_set_room_viewport_roundtrip_and_clear(hass, mapping_services):
    """[FURN-7] set_room_viewport persists {cx,cy,zoom} (4dp) then clears on all-null."""
    map_id = "furn_vp"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_SET_ROOM_VIEWPORT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "room_id": "7",
        "cx": 10.12345, "cy": 20.0, "zoom": 2.0})
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["rooms"]["7"]["viewport"] == {"cx": 10.1235, "cy": 20.0, "zoom": 2.0}

    res = await _svc(hass, SERVICE_SET_ROOM_VIEWPORT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "room_id": "7"})
    assert res["action"] == "cleared"
    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert "viewport" not in lay["rooms"]["7"]


async def test_no_active_layout_guard(hass, mapping_services):
    """[FURN-8] the furnished services refuse when there's no active custom layout."""
    map_id = "furn_nolayout"
    # No create_custom_layout call → no active layout for this fresh map.
    for service, data in (
        (SERVICE_SET_FURNISHED_ART_PLACEMENT,
         {"scope": "home", "tx": 1.0}),
        (SERVICE_SET_FURNISHED_RENDER_MODE, {"mode": "art"}),
        (SERVICE_SET_ROOM_VIEWPORT, {"room_id": "1", "cx": 1.0}),
    ):
        res = await _svc(hass, service,
                         {"vacuum_entity_id": _VAC, "map_id": map_id, **data})
        assert res["saved"] is False
        assert res["reason"] == "no_active_layout"


# ---------------------------------------------------------------------------
# Art-scoped upload convention
# ---------------------------------------------------------------------------

async def test_upload_art_scope_home(hass, mapping_services, pil):
    """[FURN-9] art_scope=home derives custom_<id>_home_art + writes it onto home_art,
    NEVER backdrop_variant."""
    map_id = "furn_up_home"
    lid = await _create_layout(hass, map_id)
    up = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid,
        "art_scope": "home",
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})
    assert up["saved"] is True
    assert up["variant"] == f"custom_{lid}_home_art"

    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["home_art"]["art_variant"] == f"custom_{lid}_home_art"
    # backdrop_variant stays the per-layout default, NOT the art variant
    assert lay["backdrop_variant"] == f"custom_{lid}"


async def test_upload_art_scope_room(hass, mapping_services, pil):
    """[FURN-10] art_scope=room derives custom_<id>_room_<rid> + writes onto rooms[rid]."""
    map_id = "furn_up_room"
    lid = await _create_layout(hass, map_id)
    up = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid,
        "art_scope": "room", "room_id": 3,
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})
    assert up["saved"] is True
    assert up["variant"] == f"custom_{lid}_room_3"

    lay = _layout_summary(await _segments(hass, map_id), lid)
    assert lay["rooms"]["3"]["art_variant"] == f"custom_{lid}_room_3"
    assert lay["backdrop_variant"] == f"custom_{lid}"


async def test_upload_art_scope_guards(hass, mapping_services, pil):
    """[FURN-11] art_scope without layout_id → layout_id_required; scope=room without
    room_id → missing_room_id."""
    map_id = "furn_up_guard"
    lid = await _create_layout(hass, map_id)
    no_layout = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "art_scope": "home",
        "image_base64": _tiny_png_b64()})
    assert no_layout["saved"] is False
    assert no_layout["reason"] == "layout_id_required"

    no_room = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid,
        "art_scope": "room", "image_base64": _tiny_png_b64()})
    assert no_room["saved"] is False
    assert no_room["reason"] == "missing_room_id"


# ---------------------------------------------------------------------------
# resolve_furnished_render projection
# ---------------------------------------------------------------------------

def test_resolve_none_in_cv_mode():
    """[FURN-12a] cv mode (or no active layout / no art) → None."""
    assert resolve_furnished_render({"segmentation_mode": "cv"}) is None
    assert resolve_furnished_render(None) is None
    # custom mode, active layout, but the layout has no furnished data → None
    assert resolve_furnished_render({
        "segmentation_mode": "custom",
        "active_custom_layout_id": "l1",
        "custom_layouts": {"l1": {"id": "l1", "rooms": {}}},
    }) is None


async def test_resolve_populated_with_art_url(hass, mapping_services, pil):
    """[FURN-12b] once home art is uploaded + placed, the snapshot composer's projection
    resolves the art_variant to the uploaded variant's browser_url."""
    map_id = "furn_resolve"
    lid = await _create_layout(hass, map_id)
    up = await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid,
        "art_scope": "home",
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})
    placed = await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home",
        "tx": 1.0, "ty": 2.0, "scale": 1.0, "rotation": 0.0})

    rendered = placed["furnished_render"]
    assert rendered is not None
    assert rendered["active_layout_id"] == lid
    assert rendered["render_mode"] == "live"  # default, absent on the layout
    assert rendered["home_art"]["art_url"] == up["browser_url"]
    assert rendered["home_art"]["transform"] == {
        "tx": 1.0, "ty": 2.0, "scale": 1.0, "rotation": 0.0}

    # Verify directly against the bucket too (the snapshot composer reads it this way).
    bucket = mapping_services.data["maps"][_VAC][map_id]
    direct = resolve_furnished_render(bucket)
    assert direct["home_art"]["art_url"] == up["browser_url"]


async def test_resolve_room_only_art(hass, mapping_services, pil):
    """[FURN-12c] a layout with ONLY a per-room viewport (no art, no home_art) still
    resolves (rooms entry present) — any furnished field counts."""
    map_id = "furn_resolve_room"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_SET_ROOM_VIEWPORT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "room_id": "9",
        "cx": 5.0, "cy": 5.0, "zoom": 1.5})
    bucket = mapping_services.data["maps"][_VAC][map_id]
    rendered = resolve_furnished_render(bucket)
    assert rendered is not None
    assert rendered["home_art"] is None
    assert rendered["rooms"]["9"]["viewport"] == {"cx": 5.0, "cy": 5.0, "zoom": 1.5}
    assert rendered["rooms"]["9"]["art_url"] is None


# ---------------------------------------------------------------------------
# delete sweep + isolation
# ---------------------------------------------------------------------------

async def test_delete_layout_sweeps_furnished_art(hass, mapping_services, pil):
    """[FURN-13] delete_custom_layout drops the furnished-art variants (home + room)
    from image_variants alongside the backdrop variant."""
    map_id = "furn_delete"
    lid = await _create_layout(hass, map_id)
    await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid,
        "art_scope": "home",
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})
    await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid,
        "art_scope": "room", "room_id": "6",
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})

    bucket = mapping_services.data["maps"][_VAC][map_id]
    assert f"custom_{lid}_home_art" in bucket["image_variants"]
    assert f"custom_{lid}_room_6" in bucket["image_variants"]

    res = await _svc(hass, SERVICE_DELETE_CUSTOM_LAYOUT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid})
    assert res["saved"] is True
    # all three (backdrop + home art + room art) variants are gone
    assert f"custom_{lid}_home_art" not in bucket["image_variants"]
    assert f"custom_{lid}_room_6" not in bucket["image_variants"]
    assert f"custom_{lid}" not in bucket["image_variants"]


async def test_per_layout_furnished_isolation(hass, mapping_services, pil):
    """[FURN-14] HEADLINE: two layouts' furnished art doesn't leak. Each holds its own
    home_art variant + placement; switching active layout swaps cleanly."""
    map_id = "furn_iso"
    lid_a = await _create_layout(hass, map_id, name="Living")
    await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid_a,
        "art_scope": "home",
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})
    # A is active right after create → place A's home art.
    await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home", "tx": 11.0})

    lid_b = await _create_layout(hass, map_id, name="Bedroom")  # now B active
    await _svc(hass, SERVICE_UPLOAD_MAP_IMAGE, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid_b,
        "art_scope": "home",
        "image_base64": _tiny_png_b64(), "image_width": 8, "image_height": 8})
    await _svc(hass, SERVICE_SET_FURNISHED_ART_PLACEMENT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "scope": "home", "tx": 22.0})

    segs = await _segments(hass, map_id)
    lay_a = _layout_summary(segs, lid_a)
    lay_b = _layout_summary(segs, lid_b)
    # distinct art variants + distinct placements, no bleed
    assert lay_a["home_art"]["art_variant"] == f"custom_{lid_a}_home_art"
    assert lay_b["home_art"]["art_variant"] == f"custom_{lid_b}_home_art"
    assert lay_a["home_art"]["art_placement_transform"]["tx"] == 11.0
    assert lay_b["home_art"]["art_placement_transform"]["tx"] == 22.0

    # active is B → resolve_furnished_render reflects B only
    bucket = mapping_services.data["maps"][_VAC][map_id]
    assert resolve_furnished_render(bucket)["active_layout_id"] == lid_b
    assert resolve_furnished_render(bucket)["home_art"]["transform"]["tx"] == 22.0

    # switch to A → resolve reflects A only, B untouched
    await _svc(hass, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT, {
        "vacuum_entity_id": _VAC, "map_id": map_id, "layout_id": lid_a})
    rendered_a = resolve_furnished_render(bucket)
    assert rendered_a["active_layout_id"] == lid_a
    assert rendered_a["home_art"]["transform"]["tx"] == 11.0
