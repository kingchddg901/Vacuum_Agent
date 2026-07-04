"""Integration tests for mapping/mapping_services.py — async service handlers.

Mapping services register through their own async_register_mapping_services
(not the domain async_register_services), and read/write the per-map bucket on
the core manager (DATA_RUNTIME). All target services support_response=True.

Coverage targets
----------------
[MSH-1]  get_map_segments returns adjusted segments + polygon_pct + summary.
[MSH-2]  adjust_map_segment: unknown segment → segment_not_found.
[MSH-3]  adjust_map_segment: a delta is stored and reflected on next read.
[MSH-4]  set_segment_room_link: set injects room_id; the link dict updates.
[MSH-5]  set_segment_room_link: null room_id clears the link.
[MSH-6]  set_segment_room_link: 1:1 enforcement drops the older segment's link.
[MSH-7]  set_companion_anchor: set then clear.
[MSH-8]  delete_map_image: returns a well-formed dict when no image exists.
[MSH-9]  get_mapping_state / save+get package / append trace evidence.
[MSH-10] set_dock_anchor + set_dock_room.
[MSH-11] start → stop → cancel trace capture.
[MSH-12] start a room boundary trace, then cancel it; close with no trace.
[MSH-13] room bounds snapshot + clear + exclude/restore (no bounds → no-op).
[MSH-14] review a non-existent run → error verdict (handler runs).
[LAYOUT-1] legacy single custom_segments store migrates into ONE default layout; shared links/anchors split.
[LAYOUT-2] create / rename / list / set-active / delete lifecycle, incl. delete-active reassign + delete-last flips to CV.
[LIVE-SEG-1] set_custom_segments over a live-backed layout: card-supplied backdrop dims let it save (no upload); no dims + no backdrop → no_custom_backdrop.
[LAYOUT-3] set_active with no layouts auto-creates + activates a default and flips to custom.
[LAYOUT-6] companion_anchors (incl reserved 'dock' key) are per-layout — A's dock spot doesn't bleed onto B.
[LAYOUT-7] _image_variant validator: accepts fixed variants + custom_<id>, rejects unknown (vol.Invalid).
[LAYOUT-8] rename_custom_layout error contracts: empty name → missing_name; unknown id → layout_not_found.
[LAYOUT-9] delete_custom_layout: unknown id → layout_not_found; deleting a NON-active layout leaves the active pointer.
[LAYOUT-10] set_segmentation_mode → custom with layouts present but no active pointer auto-selects the first id.
[LAYOUT-11] create_custom_layout with backdrop_source="live" pins the layout (surfaced in
        the get_map_segments summary); a normal create leaves backdrop_source None.
[ZONE-1]  saved-zone create/rename/delete lifecycle: distinct ids even same-second, bucket
        persistence, W1 filing fields (room_number/area_m2) default None + kind "clean",
        get_map_segments lists them, unknown id → zone_not_found on rename/delete.
[ZONE-2]  _migrate_saved_zones seeds saved_zones={} once and never clobbers existing zones.
[ZONE-3]  CREATE_SAVED_ZONE_SCHEMA geometry coord validation: non-finite/non-numeric (NaN,
        inf, "nan", "abc", bool) rejected with vol.Invalid; finite out-of-range coords clamped to 0-1.
[ZONE-4]  zone_membership: ≥90% floor dominance → that room, split/background-only → None; area is the
        bbox world footprint (Δnx·Δny·width·height·res²), not a cell count; <3 points / empty map → both None.
[ZONE-5]  create_saved_zone wires zone_membership output (room_number + area_m2) into the zone
        when map_data is available and the zone's map is the active map.
[ZONE-6]  set_saved_zone_room files then clears a zone's room_number; unknown id → zone_not_found.
[ZONE-7]  create_saved_zone skips filing/area compute when the zone's map_id ≠ the active map,
        so no wrong-map data is filed (room_number/area_m2 stay None).
[ZONE-8]  clean_saved_zone resolves a zone → its bbox rect → dispatch_zone_clean (active-map guarded);
        unknown id → zone_not_found and map-mismatch → map_not_active both refuse WITHOUT dispatching.
[ZONE-9]  clean_saved_zones resolves each id → its bbox → ONE dispatch carrying all rects (active-map
        guarded); a single missing id refuses the WHOLE batch atomically without dispatch.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import (
    DOMAIN,
    SERVICE_ADJUST_MAP_SEGMENT,
    SERVICE_DELETE_MAP_IMAGE,
    SERVICE_GET_MAP_SEGMENTS,
    SERVICE_SET_COMPANION_ANCHOR,
    SERVICE_SET_HIDDEN_REGIONS,
    SERVICE_SET_AREA_LABEL_ANCHOR,
    SERVICE_SET_SEGMENT_ROOM_LINK,
    SERVICE_CREATE_CUSTOM_LAYOUT,
    SERVICE_RENAME_CUSTOM_LAYOUT,
    SERVICE_DELETE_CUSTOM_LAYOUT,
    SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
    SERVICE_SET_CUSTOM_SEGMENTS,
    SERVICE_SET_SEGMENTATION_MODE,
)
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
from custom_components.eufy_vacuum.mapping.mapping_services import (
    SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
    SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
    SERVICE_CANCEL_TRACE_CAPTURE,
    SERVICE_CLEAR_ROOM_BOUNDS,
    SERVICE_CLOSE_ROOM_BOUNDARY,
    SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
    SERVICE_GET_MAPPING_PACKAGE,
    SERVICE_GET_MAPPING_STATE,
    SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
    SERVICE_REVIEW_TRACE_RUN,
    SERVICE_SAVE_MAPPING_PACKAGE,
    SERVICE_SET_DOCK_ANCHOR,
    SERVICE_SET_DOCK_ROOM,
    SERVICE_START_ROOM_BOUNDARY_TRACE,
    SERVICE_START_TRACE_CAPTURE,
    SERVICE_STOP_TRACE_CAPTURE,
    async_register_mapping_services,
    async_unregister_mapping_services,
)

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def mapping_services(hass, manager):
    from custom_components.eufy_vacuum.mapping.manager import MappingManager
    # the mapping-specific handlers resolve a dedicated MappingManager from
    # hass.data; async_setup_entry wires this in production.
    hass.data[DOMAIN]["mapping_manager"] = MappingManager(hass)
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)
    hass.data[DOMAIN].pop("mapping_manager", None)


def _seed_segments(manager, *, segment_ids=("s1", "s2")) -> None:
    bucket = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket["image_segments"] = {
        "available": True,
        "analyzed_at": "2026-01-01T00:00:00+00:00",
        "image": {"width": 100, "height": 100},
        "segments": [
            {"segment_id": sid,
             "polygon_pixel": [[0, 0], [10, 0], [10, 10], [0, 10]],
             "issues": []}
            for sid in segment_ids
        ],
        "summary": {"segment_count": len(segment_ids)},
    }
    bucket["image_variants"] = {"default": {"width": 100, "height": 100}}


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


# ---------------------------------------------------------------------------
# get_map_segments
# ---------------------------------------------------------------------------

async def test_get_map_segments(hass, mapping_services):
    """[MSH-1]"""
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert result["available"] is True
    assert result["summary"]["segment_count"] == 2
    seg = result["segments"][0]
    assert "polygon_pct" in seg


# ---------------------------------------------------------------------------
# adjust_map_segment
# ---------------------------------------------------------------------------

async def test_adjust_segment_not_found(hass, mapping_services):
    """[MSH-2]"""
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "ghost"})
    assert result["saved"] is False
    assert result["reason"] == "segment_not_found"


async def test_adjust_segment_stores_delta(hass, mapping_services):
    """[MSH-3]"""
    _seed_segments(mapping_services)
    saved = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "segment_id": "s1", "delta_x": 5})
    assert saved["saved"] is True
    # reflected on the next read: the segment polygon is translated +5 in x
    segments = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP})
    s1 = next(s for s in segments["segments"] if s["segment_id"] == "s1")
    assert s1["polygon_pixel"][0][0] == 5
    assert "translated_manual" in s1["issues"]


async def test_adjust_segment_zeroes_out_drops_stored_adjustment(hass, mapping_services):
    """[MSH-3b] netting an accumulated offset back to 0 removes the stored adjustment.

    Exercises the ``else: adjustments.pop(segment_id, None)`` cleanup branch:
    once every offset/edge nets to zero with no vertex moves, the prior entry
    is dropped and the segment reverts to its seeded (un-translated) geometry.
    """
    _seed_segments(mapping_services)
    # store a delta first, so there's an entry to remove
    stored = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "segment_id": "s1", "delta_x": 5})
    assert stored["saved"] is True
    assert stored["adjustment"] is not None

    # net it back to zero → handler pops the entry, so adjustment is None
    reset = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "segment_id": "s1", "delta_x": -5})
    assert reset["saved"] is True
    assert reset["adjustment"] is None

    # observable on the next read: geometry back to seeded origin, no manual
    # flag, summary count cleared, and no leftover adjustments entry
    segments = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP})
    s1 = next(s for s in segments["segments"] if s["segment_id"] == "s1")
    assert s1["polygon_pixel"][0][0] == 0
    assert "translated_manual" not in s1.get("issues", [])
    assert segments["summary"]["adjusted_count"] == 0
    assert "s1" not in segments["adjustments"]


# ---------------------------------------------------------------------------
# set_segment_room_link
# ---------------------------------------------------------------------------

async def test_link_set_injects_room(hass, mapping_services):
    """[MSH-4]"""
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "segment_id": "s1", "room_id": "3"})
    assert result["saved"] is True and result["action"] == "set"
    assert result["segment_room_links"]["s1"] == "3"
    segments = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP})
    s1 = next(s for s in segments["segments"] if s["segment_id"] == "s1")
    assert s1["room_id"] == "3"


async def test_link_clear(hass, mapping_services):
    """[MSH-5]"""
    _seed_segments(mapping_services)
    await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s1", "room_id": "3"})
    cleared = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP,
                           "segment_id": "s1", "room_id": None})
    assert cleared["action"] == "cleared"
    assert "s1" not in cleared["segment_room_links"]


async def test_link_one_to_one(hass, mapping_services):
    """[MSH-6] linking room 3 to s2 drops the existing s1→3 link."""
    _seed_segments(mapping_services)
    await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s1", "room_id": "3"})
    result = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s2", "room_id": "3"})
    links = result["segment_room_links"]
    assert links.get("s2") == "3"
    assert "s1" not in links


async def test_link_blank_segment_id(hass, mapping_services):
    """[MSH-6b] whitespace-only segment_id strips empty → missing_segment_id.

    Guards the strip-then-guard ordering at mapping_services.py:1033-1037 in
    _handle_set_segment_room_link: a blanked segment_id must short-circuit to
    the ``{"saved": False, "reason": "missing_segment_id"}`` failure contract
    the card reads, *before* touching the map bucket or persisting anything.
    """
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "segment_id": "   ", "room_id": "3"})
    assert result["saved"] is False
    assert result["reason"] == "missing_segment_id"


async def test_link_inert_when_segment_resegmented_away(hass, mapping_services):
    """[MSH-6c] segment_room_links DRIFT: when the segment id set changes underneath
    the links (a re-analysis, or a set_custom_segments replace-all), links keyed by
    the OLD ids go inert. The read attaches room_id by iterating the CURRENT segments
    (mapping_services.py:954-959), so a link to a vanished segment can never surface
    as a ghost room, while a preserved id keeps its link. Pins the inert-by-design
    safety net that re-analysis (which leaves segment_room_links untouched) and the
    custom-segment replace-all both rely on — neither prunes the link dict."""
    _seed_segments(mapping_services, segment_ids=("s1", "s2"))
    await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s1", "room_id": "3"})
    await _call(hass, SERVICE_SET_SEGMENT_ROOM_LINK,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "s2", "room_id": "4"})

    # Re-analysis replaces image_segments with a NEW id set (s1 gone, s2 kept, s9
    # new); segment_room_links is deliberately left untouched.
    _seed_segments(mapping_services, segment_ids=("s2", "s9"))

    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got["available"] is True                         # stale link doesn't break the read
    by_id = {s["segment_id"]: s for s in got["segments"]}
    assert set(by_id) == {"s2", "s9"}
    assert all(s.get("room_id") != "3" for s in got["segments"])  # gone s1 → no ghost room 3
    assert by_id["s2"]["room_id"] == "4"                    # preserved id keeps its link
    assert by_id["s9"].get("room_id") is None               # brand-new segment has no link

    # The orphaned s1→3 link lingers inertly in the bucket (no pruning today).
    links = mapping_services.data["maps"][_VAC][_MAP]["segment_room_links"]
    assert links.get("s1") == "3"


# ---------------------------------------------------------------------------
# set_companion_anchor
# ---------------------------------------------------------------------------

async def test_companion_anchor_set_and_clear(hass, mapping_services):
    """[MSH-7]"""
    _seed_segments(mapping_services)
    setres = await _call(hass, SERVICE_SET_COMPANION_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "room_id": "3", "pct_x": 25.0, "pct_y": 75.0})
    assert setres["action"] == "set"
    assert setres["companion_anchors"]["3"] == {"pct_x": 25.0, "pct_y": 75.0}
    clearres = await _call(hass, SERVICE_SET_COMPANION_ANCHOR,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "3"})
    assert clearres["action"] == "cleared"
    assert "3" not in clearres["companion_anchors"]


async def test_hidden_regions_set_and_clear(hass, mapping_services):
    """[MSH-7c] set_hidden_regions: sanitize (clamp, order min<max, drop degenerate/malformed),
    persist, surface in get_map_segments; an empty list clears."""
    _seed_segments(mapping_services)
    res = await _call(hass, SERVICE_SET_HIDDEN_REGIONS,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP,
                       "regions": [[0.8, 0.1, 0.5, 0.4],      # unordered -> reordered min<max
                                   [2, -1, 0.5, 0.5],         # out of range -> clamped 0-1
                                   [0.1, 0.1, 0.1001, 0.5],   # degenerate width -> dropped
                                   "junk", [0.1, 0.2]]})       # malformed -> dropped
    assert res["saved"] is True
    regions = res["hidden_regions"]
    assert regions == [[0.5, 0.1, 0.8, 0.4], [0.5, 0.0, 1.0, 0.5]]
    # rides back on get_map_segments
    seg = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert seg["hidden_regions"] == regions
    # NaN/inf coords are REJECTED (not clamped to an edge — a NaN would otherwise pin to 0/1)
    nanres = await _call(hass, SERVICE_SET_HIDDEN_REGIONS,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "regions": [[float("nan"), 0.1, 0.5, 0.5],
                                      [0.1, 0.1, float("inf"), 0.5]]})
    assert nanres["hidden_regions"] == []
    # empty list clears
    cleared = await _call(hass, SERVICE_SET_HIDDEN_REGIONS,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "regions": []})
    assert cleared["hidden_regions"] == []


async def test_hidden_regions_persist_map_level_in_custom_mode(hass, mapping_services):
    """[MSH-7d] hidden regions are MAP-LEVEL (not scope-resolved): they persist even in custom
    mode with NO active layout — the per-scope version silently dropped them (data loss)."""
    _seed_segments(mapping_services)
    bucket = ensure_map_bucket(data=mapping_services.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket["segmentation_mode"] = "custom"          # custom mode, no active layout
    res = await _call(hass, SERVICE_SET_HIDDEN_REGIONS,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "regions": [[0.2, 0.2, 0.4, 0.4]]})
    assert res["hidden_regions"] == [[0.2, 0.2, 0.4, 0.4]]
    assert bucket.get("hidden_regions") == [[0.2, 0.2, 0.4, 0.4]]   # actually persisted on the bucket
    seg = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert seg["hidden_regions"] == [[0.2, 0.2, 0.4, 0.4]]


async def test_area_label_anchor_set_and_clear(hass, mapping_services):
    """[MSH-7e] set_area_label_anchor: per-room m² chip position, MAP-LEVEL, set then reset;
    rides back on get_map_segments."""
    _seed_segments(mapping_services)
    setres = await _call(hass, SERVICE_SET_AREA_LABEL_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "room_id": 5, "pct_x": 30.0, "pct_y": 80.0})
    assert setres["action"] == "set"
    assert setres["area_label_anchors"]["5"] == {"pct_x": 30.0, "pct_y": 80.0}
    seg = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert seg["area_label_anchors"]["5"] == {"pct_x": 30.0, "pct_y": 80.0}
    # null pct resets to the default (room centre)
    clr = await _call(hass, SERVICE_SET_AREA_LABEL_ANCHOR,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "5"})
    assert clr["action"] == "cleared" and "5" not in clr["area_label_anchors"]


async def test_companion_anchor_blank_room_id(hass, mapping_services):
    """[MSH-7b] whitespace-only room_id strips empty → missing_room_id.

    Guards the strip-then-guard ordering at mapping_services.py:1087-1092 in
    _handle_set_companion_anchor: a blanked room_id must short-circuit to the
    ``{"saved": False, "reason": "missing_room_id"}`` failure contract the card
    reads, *before* touching the map bucket or persisting any anchor.
    """
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_SET_COMPANION_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "room_id": "   ", "pct_x": 25.0, "pct_y": 75.0})
    assert result["saved"] is False
    assert result["reason"] == "missing_room_id"


# ---------------------------------------------------------------------------
# delete_map_image
# ---------------------------------------------------------------------------

async def test_delete_map_image_no_image(hass, mapping_services):
    """[MSH-8]"""
    result = await _call(hass, SERVICE_DELETE_MAP_IMAGE,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "default"})
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Custom layouts (named collection per map)
# ---------------------------------------------------------------------------

async def test_custom_layout_migration_splits_shared_links(hass, mapping_services):
    """[LAYOUT-1] a legacy single custom_segments store migrates into ONE default
    layout; today's SHARED segment_room_links/companion_anchors are split — only the
    custom-resolved entries copy into the layout, CV's stay on the map bucket."""
    bucket = ensure_map_bucket(data=mapping_services.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket["image_segments"] = {"available": True, "segments": [{"segment_id": "s1"}]}
    bucket["custom_segments"] = {
        "available": True, "image": {"width": 100, "height": 100},
        "segments": [{"segment_id": "c1", "polygon_pixel": [[0, 0], [10, 0], [10, 10]]}],
        "summary": {"segment_count": 1},
    }
    bucket["image_variants"] = {"custom": {"width": 100, "height": 100}}
    bucket["segment_room_links"] = {"s1": "3", "c1": "5"}   # cv link + custom link
    bucket["companion_anchors"] = {
        "3": {"pct_x": 1, "pct_y": 1},      # cv room
        "5": {"pct_x": 2, "pct_y": 2},      # custom room
        "dock": {"pct_x": 9, "pct_y": 9},
    }
    bucket["segmentation_mode"] = "custom"

    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})

    layouts = bucket["custom_layouts"]
    assert len(layouts) == 1
    layout = next(iter(layouts.values()))
    assert bucket["active_custom_layout_id"] == layout["id"]
    # the layout carries only the custom-resolved overlays
    assert layout["segment_room_links"] == {"c1": "5"}
    assert set(layout["companion_anchors"]) == {"5", "dock"}      # not "3" (a CV room)
    # CV's map-bucket dicts are left intact
    assert bucket["segment_room_links"] == {"s1": "3", "c1": "5"}
    # the response (custom mode) serves the layout: c1 linked to room 5
    c1 = next(s for s in got["segments"] if s["segment_id"] == "c1")
    assert c1["room_id"] == "5"
    assert got["active_custom_layout_id"] == layout["id"]
    assert len(got["custom_layouts"]) == 1

    # idempotent: re-reading doesn't spawn a second layout
    await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert len(bucket["custom_layouts"]) == 1


async def test_custom_layout_crud(hass, mapping_services):
    """[LAYOUT-2] create / rename / list / set-active / delete lifecycle, incl.
    delete-active reassigns and delete-last flips back to CV."""
    a = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Tree"})
    assert a["saved"] and a["layout_id"]
    lid_a = a["layout_id"]
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got["segmentation_mode"] == "custom"          # create flips to custom + activates
    assert got["active_custom_layout_id"] == lid_a

    b = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Solar"})
    lid_b = b["layout_id"]
    assert lid_b != lid_a

    ren = await _call(hass, SERVICE_RENAME_CUSTOM_LAYOUT,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid_a, "name": "Oak"})
    assert ren["layout"]["name"] == "Oak"

    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    names = {lay["id"]: lay["name"] for lay in got["custom_layouts"]}
    assert names == {lid_a: "Oak", lid_b: "Solar"}
    assert got["active_custom_layout_id"] == lid_b       # the 2nd create is active

    await _call(hass, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid_a})
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got["active_custom_layout_id"] == lid_a

    d = await _call(hass, SERVICE_DELETE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid_a})
    assert d["deleted"] and d["active_custom_layout_id"] == lid_b   # reassigned

    d2 = await _call(hass, SERVICE_DELETE_CUSTOM_LAYOUT,
                     {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid_b})
    assert d2["active_custom_layout_id"] is None
    assert d2["segmentation_mode"] == "cv"               # last delete flips to CV


async def test_saved_zone_crud(hass, mapping_services):
    """[ZONE-1] create / rename / delete saved-zone lifecycle: distinct ids, persistence
    on the map bucket, W1 filing fields default None, unknown-id -> zone_not_found."""
    from custom_components.eufy_vacuum.const import (
        SERVICE_CREATE_SAVED_ZONE,
        SERVICE_DELETE_SAVED_ZONE,
        SERVICE_RENAME_SAVED_ZONE,
    )
    quad = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]]
    a = await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "The couch", "geometry": quad})
    assert a["saved"] and a["zone_id"]
    zid = a["zone_id"]
    assert a["zone"]["name"] == "The couch"
    assert a["zone"]["geometry"] == quad
    assert a["zone"]["room_number"] is None   # W1: filing lands in W2
    assert a["zone"]["area_m2"] is None        # W1: computed in W2
    assert a["zone"]["kind"] == "clean"

    bucket = ensure_map_bucket(data=mapping_services.data, vacuum_entity_id=_VAC, map_id=_MAP)
    assert zid in bucket["saved_zones"]

    b = await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "The stove", "geometry": quad})
    assert b["zone_id"] != zid                 # distinct id even same-second

    ren = await _call(hass, SERVICE_RENAME_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid, "name": "Under the table"})
    assert ren["saved"] and ren["zone"]["name"] == "Under the table"

    # the read surface (get_map_segments) lists all saved zones for the card
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    listed = {z["id"]: z["name"] for z in got["saved_zones"]}
    assert listed == {zid: "Under the table", b["zone_id"]: "The stove"}

    bad = await _call(hass, SERVICE_RENAME_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": "nope", "name": "x"})
    assert bad["saved"] is False and bad["reason"] == "zone_not_found"

    d = await _call(hass, SERVICE_DELETE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid})
    assert d["saved"] and d["deleted"]
    assert zid not in bucket["saved_zones"]

    d2 = await _call(hass, SERVICE_DELETE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid})
    assert d2["saved"] is False and d2["reason"] == "zone_not_found"


async def test_saved_zones_migration_idempotent(hass, mapping_services):
    """[ZONE-2] _migrate_saved_zones seeds {} once and never clobbers existing zones."""
    from custom_components.eufy_vacuum.mapping.mapping_services import _migrate_saved_zones
    bucket = ensure_map_bucket(data=mapping_services.data, vacuum_entity_id=_VAC, map_id=_MAP)
    _migrate_saved_zones(bucket)
    assert bucket["saved_zones"] == {}
    bucket["saved_zones"]["sz_x"] = {"id": "sz_x", "name": "keep"}
    _migrate_saved_zones(bucket)               # idempotent — must not wipe
    assert bucket["saved_zones"] == {"sz_x": {"id": "sz_x", "name": "keep"}}


def test_saved_zone_geometry_coord_validation():
    """[ZONE-3] geometry coords: non-finite / non-numeric rejected (fail loud, so
    NaN/inf never persist and get orjson-nulled on save); out-of-range clamped to 0-1."""
    import math

    import voluptuous as vol

    from custom_components.eufy_vacuum.mapping.mapping_services import (
        CREATE_SAVED_ZONE_SCHEMA,
    )
    base = {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "z"}
    for bad in (float("nan"), float("inf"), float("-inf"), "nan", "inf", "abc", True):
        with pytest.raises(vol.Invalid):
            CREATE_SAVED_ZONE_SCHEMA(
                {**base, "geometry": [[bad, 0.0], [0.0, 0.0], [1.0, 1.0]]})
    # finite but out of the normalized 0-1 range -> clamped, not rejected
    out = CREATE_SAVED_ZONE_SCHEMA(
        {**base, "geometry": [[5.0, -3.0], [100.0, 0.5], [1.0, 1.0]]})
    assert out["geometry"] == [[1.0, 0.0], [1.0, 0.5], [1.0, 1.0]]
    assert all(math.isfinite(c) for pt in out["geometry"] for c in pt)


def _synthetic_map_data(byte_list):
    """A tiny 4x4 room_pixels raster (each byte >> 2 = room id) with identity geometry."""
    import base64
    return {
        "room_pixels": base64.b64encode(bytes(byte_list)).decode(),
        "width": 4, "height": 4, "resolution": 10,
        "room_outline_width": 4, "room_outline_height": 4,
        "origin_x": 0, "origin_y": 0,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
    }


def test_zone_membership_computes_room_and_area():
    """[ZONE-4] zone_membership: >=90% floor dominance -> that room; split -> None;
    over background only -> None. area is the bbox's world FOOTPRINT (fork de-normalization:
    Δnx*Δny*width*height*res^2), NOT a raster cell count; malformed -> both None."""
    from custom_components.eufy_vacuum.mapping.map_source import zone_membership
    whole = [[-0.5, -0.5], [1.5, -0.5], [1.5, 1.5], [-0.5, 1.5]]   # strictly contains every cell
    # width=4 height=4 res=10 -> full-bbox footprint = Δnx*Δny*4*4*(10/100)^2, Δ=2 each
    whole_area = round(2.0 * 2.0 * 4 * 4 * (10 / 100.0) ** 2, 1)   # 0.64

    dom = zone_membership(_synthetic_map_data([5 << 2] * 15 + [9 << 2]), whole)
    assert dom["room_number"] == 5 and dom["area_m2"] == whole_area  # 15/16 = 93.75%

    split = zone_membership(_synthetic_map_data([5 << 2] * 8 + [9 << 2] * 8), whole)
    assert split["room_number"] is None and split["area_m2"] == whole_area

    bg = zone_membership(_synthetic_map_data([0] * 16), whole)     # no floor cells
    assert bg["room_number"] is None and bg["area_m2"] == whole_area

    # area tracks the bbox, not the raster: half the image in each axis -> a quarter the area
    half = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]
    half_area = round(0.5 * 0.5 * 4 * 4 * (10 / 100.0) ** 2, 1)    # 0.16
    assert zone_membership(_synthetic_map_data([5 << 2] * 16), half)["area_m2"] == half_area

    assert zone_membership(_synthetic_map_data([5 << 2] * 16), [[0.0, 0.0]]) == {
        "area_m2": None, "room_number": None}                      # < 3 points
    assert zone_membership({}, whole) == {"area_m2": None, "room_number": None}


def test_zone_membership_area_is_offset_independent():
    """[ZONE-4b] the area = bbox world footprint (fork de-normalization), so it depends ONLY
    on width/height/resolution — NOT on the room_outline offset. This is what keeps the size
    correct even on maps whose segmentation raster is offset from the render grid."""
    from custom_components.eufy_vacuum.mapping.map_source import zone_membership
    box = [[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]
    expect = round(0.5 * 0.5 * 4 * 4 * (10 / 100.0) ** 2, 1)       # 0.04
    md0 = _synthetic_map_data([5 << 2] * 16)
    md_off = {**md0, "room_outline_origin_x": 40, "room_outline_origin_y": 40}  # big offset
    assert zone_membership(md0, box)["area_m2"] == expect
    assert zone_membership(md_off, box)["area_m2"] == expect       # offset changes nothing


async def test_create_saved_zone_computes_filing_when_map_present(hass, mapping_services, monkeypatch):
    """[ZONE-5] create wires zone_membership output into the zone when map_data is
    available (accessor monkeypatched); the existing crud test covers the None fallback."""
    from custom_components.eufy_vacuum.const import SERVICE_CREATE_SAVED_ZONE

    async def _fake_map_data(**_kwargs):
        return _synthetic_map_data([7 << 2] * 16)                  # all room 7
    monkeypatch.setattr(mapping_services, "async_get_map_data_dict", _fake_map_data)
    monkeypatch.setattr(                                            # zone's map IS active
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda hass, vid: _MAP)

    a = await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "couch",
        "geometry": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]})
    assert a["zone"]["room_number"] == 7
    assert a["zone"]["area_m2"] is not None and a["zone"]["area_m2"] > 0


async def test_create_saved_zone_skips_compute_on_map_mismatch(hass, mapping_services, monkeypatch):
    """[ZONE-7] filing/area compute is skipped when the zone's map_id != the active map
    (the fork exposes only the current map's raster), so no wrong-map data is filed."""
    from custom_components.eufy_vacuum.const import SERVICE_CREATE_SAVED_ZONE

    async def _fake_map_data(**_kwargs):
        return _synthetic_map_data([7 << 2] * 16)
    monkeypatch.setattr(mapping_services, "async_get_map_data_dict", _fake_map_data)
    monkeypatch.setattr(                                            # active map != _MAP ("6")
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda hass, vid: "999")

    a = await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "z",
        "geometry": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]})
    assert a["zone"]["room_number"] is None   # mismatch -> not computed (no wrong-map data)
    assert a["zone"]["area_m2"] is None


async def test_set_saved_zone_room(hass, mapping_services):
    """[ZONE-6] set_saved_zone_room files / clears a zone's room_number (filing only)."""
    from custom_components.eufy_vacuum.const import (
        SERVICE_CREATE_SAVED_ZONE,
        SERVICE_SET_SAVED_ZONE_ROOM,
    )
    quad = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.5], [0.1, 0.5]]
    a = await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "z", "geometry": quad})
    zid = a["zone_id"]

    r = await _call(hass, SERVICE_SET_SAVED_ZONE_ROOM, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid, "room_number": 7})
    assert r["saved"] and r["zone"]["room_number"] == 7

    c = await _call(hass, SERVICE_SET_SAVED_ZONE_ROOM, {   # omit -> clear to Unassigned
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid})
    assert c["saved"] and c["zone"]["room_number"] is None

    bad = await _call(hass, SERVICE_SET_SAVED_ZONE_ROOM, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": "nope", "room_number": 1})
    assert bad["saved"] is False and bad["reason"] == "zone_not_found"


async def test_clean_saved_zone_dispatches_bbox(hass, mapping_services, monkeypatch):
    """[ZONE-8] clean_saved_zone resolves the zone -> its bbox rect -> dispatch_zone_clean;
    guards to the active map; not-found + map-mismatch refuse WITHOUT dispatching."""
    from custom_components.eufy_vacuum.const import (
        SERVICE_CLEAN_SAVED_ZONE,
        SERVICE_CREATE_SAVED_ZONE,
    )
    captured = {}

    async def _fake_dispatch(*, vacuum_entity_id, zones, clean_times=1, map_id=None):
        captured["zones"] = zones
        captured["clean_times"] = clean_times
        return {"dispatched": True}
    monkeypatch.setattr(mapping_services, "dispatch_zone_clean", _fake_dispatch)
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda hass, vid: _MAP)

    geom = [[0.2, 0.3], [0.6, 0.25], [0.55, 0.7], [0.15, 0.65]]   # non-rect -> bbox
    a = await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "z", "geometry": geom})
    zid = a["zone_id"]
    xs = [p[0] for p in a["zone"]["geometry"]]
    ys = [p[1] for p in a["zone"]["geometry"]]

    r = await _call(hass, SERVICE_CLEAN_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid, "clean_times": 2})
    assert r["cleaned"] is True and r["zone_id"] == zid
    assert captured["zones"] == [[min(xs), min(ys), max(xs), max(ys)]]
    assert captured["clean_times"] == 2

    captured.clear()
    nf = await _call(hass, SERVICE_CLEAN_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": "nope"})
    assert nf["cleaned"] is False and nf["reason"] == "zone_not_found"
    assert captured == {}                                          # never dispatched

    monkeypatch.setattr(   # zone's map != active map -> refuse, no dispatch
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda hass, vid: "999")
    mm = await _call(hass, SERVICE_CLEAN_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zid})
    assert mm["cleaned"] is False and mm["reason"] == "map_not_active"


async def test_clean_saved_zones_dispatches_combined_bboxes(hass, mapping_services, monkeypatch):
    """[ZONE-9] clean_saved_zones resolves EACH id -> its bbox -> ONE dispatch carrying all
    rects; active-map guard; a missing id refuses the WHOLE batch (atomic) without dispatch."""
    from custom_components.eufy_vacuum.const import (
        SERVICE_CLEAN_SAVED_ZONES,
        SERVICE_CREATE_SAVED_ZONE,
    )
    captured = {}

    async def _fake_dispatch(*, vacuum_entity_id, zones, clean_times=1, map_id=None):
        captured["zones"] = zones
        captured["clean_times"] = clean_times
        return {"dispatched": True}
    monkeypatch.setattr(mapping_services, "dispatch_zone_clean", _fake_dispatch)
    monkeypatch.setattr(
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda hass, vid: _MAP)

    g1 = [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]
    g2 = [[0.5, 0.5], [0.8, 0.5], [0.8, 0.75], [0.5, 0.75]]
    id1 = (await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "a", "geometry": g1}))["zone_id"]
    id2 = (await _call(hass, SERVICE_CREATE_SAVED_ZONE, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "name": "b", "geometry": g2}))["zone_id"]

    r = await _call(hass, SERVICE_CLEAN_SAVED_ZONES, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": [id1, id2], "clean_times": 2})
    assert r["cleaned"] is True and r["zone_count"] == 2
    assert captured["zones"] == [[0.1, 0.1, 0.3, 0.3], [0.5, 0.5, 0.8, 0.75]]  # both bboxes, one call
    assert captured["clean_times"] == 2

    captured.clear()
    nf = await _call(hass, SERVICE_CLEAN_SAVED_ZONES, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": [id1, "nope"]})
    assert nf["cleaned"] is False and nf["reason"] == "zone_not_found"
    assert captured == {}                                          # atomic: nothing dispatched

    monkeypatch.setattr(
        "custom_components.eufy_vacuum.rooms.room_discovery.get_active_map_id",
        lambda hass, vid: "999")
    mm = await _call(hass, SERVICE_CLEAN_SAVED_ZONES, {
        "vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": [id1]})
    assert mm["cleaned"] is False and mm["reason"] == "map_not_active"
    assert captured == {}


async def test_create_custom_layout_live_backdrop_source(hass, mapping_services):
    """[LAYOUT-11] create_custom_layout with backdrop_source='live' pins the layout to
    the live map (surfaced in the get_map_segments summary so the card's "Live map" chip
    can find + reselect it); a normal create leaves backdrop_source None."""
    live = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP,
                        "name": "Live map", "backdrop_source": "live"})
    assert live["saved"]
    plain = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Blueprint"})

    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    by_id = {lay["id"]: lay for lay in got["custom_layouts"]}
    assert by_id[live["layout_id"]]["backdrop_source"] == "live"
    assert by_id[plain["layout_id"]]["backdrop_source"] is None


def test_image_variant_validator_rejects_unknown():
    """[LAYOUT-7] the _image_variant schema validator accepts the fixed variants and any
    'custom_<id>' but rejects anything else (vol.Invalid) — stops an unknown key reaching
    image_variants where downstream readers (suggest/delete/segmentor) would mis-serve."""
    import voluptuous as vol
    from custom_components.eufy_vacuum.mapping.mapping_services import _image_variant
    assert _image_variant("default") == "default"
    assert _image_variant("custom_ab12") == "custom_ab12"
    with pytest.raises(vol.Invalid):
        _image_variant("bogus")


async def test_rename_custom_layout_error_contracts(hass, mapping_services):
    """[LAYOUT-8] rename_custom_layout's frontend error contracts: an empty/whitespace
    name returns reason 'missing_name'; an unknown layout_id returns 'layout_not_found'.
    The card branches on these exact reason strings to surface a validation error."""
    a = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Tree"})
    lid = a["layout_id"]
    blank = await _call(hass, SERVICE_RENAME_CUSTOM_LAYOUT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid, "name": "   "})
    assert blank["saved"] is False and blank["reason"] == "missing_name"
    missing = await _call(hass, SERVICE_RENAME_CUSTOM_LAYOUT,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": "ghost", "name": "X"})
    assert missing["saved"] is False and missing["reason"] == "layout_not_found"


async def test_delete_custom_layout_error_and_non_active(hass, mapping_services):
    """[LAYOUT-9] delete_custom_layout: an unknown layout_id returns 'layout_not_found';
    deleting a NON-active layout removes it and LEAVES the active pointer unchanged (the
    active-reassignment block only runs when the deleted layout WAS the active one)."""
    missing = await _call(hass, SERVICE_DELETE_CUSTOM_LAYOUT,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": "ghost"})
    assert missing["saved"] is False and missing["reason"] == "layout_not_found"
    a = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Tree"})
    lid_a = a["layout_id"]
    b = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Solar"})
    lid_b = b["layout_id"]                               # the 2nd create is active
    d = await _call(hass, SERVICE_DELETE_CUSTOM_LAYOUT,   # delete the NON-active one (A)
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid_a})
    assert d["deleted"] and d["active_custom_layout_id"] == lid_b   # active untouched
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert {lay["id"] for lay in got["custom_layouts"]} == {lid_b}


async def test_set_segmentation_mode_auto_selects_first_layout(hass, mapping_services):
    """[LAYOUT-10] flipping to custom mode with layouts present but NO active pointer
    auto-selects the alphabetically-first layout id, so custom mode never resolves to an
    empty store (which would serve no segments to the card). Soft-select guard."""
    a = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Tree"})
    b = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "Solar"})
    # force the orphaned state: layouts exist, but no active pointer and mode back to cv
    bucket = ensure_map_bucket(data=mapping_services.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket["active_custom_layout_id"] = None
    bucket["segmentation_mode"] = "cv"
    await _call(hass, SERVICE_SET_SEGMENTATION_MODE,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "mode": "custom"})
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got["active_custom_layout_id"] == sorted([a["layout_id"], b["layout_id"]])[0]


async def test_set_active_auto_creates(hass, mapping_services):
    """[LAYOUT-3] set_active with no layouts (null target) auto-creates + activates
    a default and flips to custom — closing the zero-layout trap."""
    res = await _call(hass, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert res["saved"] and res["mode"] == "custom"
    assert res["active_custom_layout_id"]
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert len(got["custom_layouts"]) == 1
    assert got["active_custom_layout_id"] == res["active_custom_layout_id"]


async def test_set_custom_segments_live_backdrop_dims(hass, mapping_services):
    """[LIVE-SEG-1] A custom layout with NO uploaded backdrop (live-image-backed):
    set_custom_segments fails 'no_custom_backdrop' without dims, but SAVES when the
    card supplies the live image's pixel size — so rooms drawn over the live map
    persist with no upload."""
    # auto-create + activate a custom layout (no uploaded backdrop in image_variants)
    await _call(hass, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
                {"vacuum_entity_id": _VAC, "map_id": _MAP})
    seg = {"id": "custom_1",
           "primitives": [{"type": "rect", "x": 10, "y": 10, "w": 30, "h": 30}]}
    # no uploaded backdrop + no card-supplied dims -> can't rasterise
    no_dims = await _call(hass, SERVICE_SET_CUSTOM_SEGMENTS,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "segments": [seg]})
    assert no_dims["saved"] is False
    assert no_dims["reason"] == "no_custom_backdrop"
    # the card supplies the live image's natural pixel size -> saves
    saved = await _call(hass, SERVICE_SET_CUSTOM_SEGMENTS,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP, "segments": [seg],
                         "backdrop_width": 1024, "backdrop_height": 768})
    assert saved["saved"] is True
    assert saved["segment_count"] == 1
    # Read back: polygon_pct must be in 0-100, scaled by the STORE's live dims. A
    # live-backed layout has no image_variant, so deriving the scale from
    # image_variants (empty -> width 1) would leave polygon_pct = pixel*100, far
    # off-screen (the "segments don't appear / aren't saving" bug).
    got = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    pct = got["segments"][0]["polygon_pct"]
    assert pct and all(0 <= x <= 100 and 0 <= y <= 100 for x, y in pct), pct


async def test_per_layout_anchors_and_dock(hass, mapping_services):
    """[LAYOUT-6] companion_anchors (incl the reserved 'dock' key) are per-layout —
    a dock spot set on layout A must not bleed onto layout B."""
    a = await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "A"})
    lid_a = a["layout_id"]
    await _call(hass, SERVICE_SET_COMPANION_ANCHOR,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": "dock",
                 "pct_x": 80, "pct_y": 20})
    got_a = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got_a["companion_anchors"].get("dock") == {"pct_x": 80.0, "pct_y": 20.0}

    await _call(hass, SERVICE_CREATE_CUSTOM_LAYOUT,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "name": "B"})   # activates B
    got_b = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert "dock" not in got_b["companion_anchors"]      # B has its own (empty) anchors

    await _call(hass, SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "layout_id": lid_a})
    got_a2 = await _call(hass, SERVICE_GET_MAP_SEGMENTS, {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert got_a2["companion_anchors"].get("dock") == {"pct_x": 80.0, "pct_y": 20.0}


# ---------------------------------------------------------------------------
# [MSH-9+] non-CV data handlers (dock / bounds / trace capture / package)
# ---------------------------------------------------------------------------

async def test_mapping_state_and_package(hass, mapping_services):
    """[MSH-9] get_mapping_state / save+get package / append trace evidence."""
    state = await _call(hass, SERVICE_GET_MAPPING_STATE,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert state["vacuum_entity_id"] == _VAC
    saved = await _call(hass, SERVICE_SAVE_MAPPING_PACKAGE,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "package": {"rooms": {}}})
    assert saved["saved"] is True
    pkg = await _call(hass, SERVICE_GET_MAPPING_PACKAGE,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert isinstance(pkg, dict)
    ev = await _call(hass, SERVICE_APPEND_MAPPING_TRACE_EVIDENCE,
                     {"vacuum_entity_id": _VAC, "map_id": _MAP,
                      "evidence": {"label": "doorway"}})
    assert ev["saved"] is True


async def test_dock_anchor_and_room(hass, mapping_services):
    """[MSH-10] set_dock_anchor + set_dock_room."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    hass.states.async_set(_VAC, "docked")  # dock anchor requires docked state
    anchor = await _call(hass, SERVICE_SET_DOCK_ANCHOR,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "pixel_x": 50, "pixel_y": 50})
    assert anchor["saved"] is True
    room = await _call(hass, SERVICE_SET_DOCK_ROOM,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert room["saved"] is True


async def test_trace_capture_cycle(hass, mapping_services):
    """[MSH-11] start → stop → cancel trace capture."""
    started = await _call(hass, SERVICE_START_TRACE_CAPTURE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert started["started"] is True
    stopped = await _call(hass, SERVICE_STOP_TRACE_CAPTURE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert isinstance(stopped, dict)
    # no active session now → cancel returns cancelled False
    cancelled = await _call(hass, SERVICE_CANCEL_TRACE_CAPTURE,
                            {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert cancelled["cancelled"] is False


async def test_room_boundary_trace(hass, mapping_services):
    """[MSH-12] start a room boundary trace, then cancel it; close with no trace."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    started = await _call(hass, SERVICE_START_ROOM_BOUNDARY_TRACE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert isinstance(started, dict)
    cancelled = await _call(hass, SERVICE_CANCEL_ROOM_BOUNDARY_TRACE,
                            {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert isinstance(cancelled, dict)
    closed = await _call(hass, SERVICE_CLOSE_ROOM_BOUNDARY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 2})
    assert closed.get("closed") is not True


async def test_bounds_snapshot_and_clear(hass, mapping_services):
    """[MSH-13] room bounds snapshot + clear + exclude/restore (no bounds → no-op)."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    snap = await _call(hass, SERVICE_GET_ROOM_BOUNDS_SNAPSHOT,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert "rooms" in snap
    cleared = await _call(hass, SERVICE_CLEAR_ROOM_BOUNDS,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP, "room_id": 1})
    assert isinstance(cleared, dict)
    excl = await _call(hass, SERVICE_EXCLUDE_ROOM_JOB_BOUNDS,
                       {"vacuum_entity_id": _VAC, "map_id": _MAP,
                        "room_id": 1, "job_index": 0})
    assert isinstance(excl, dict)


async def test_review_trace_run_missing(hass, mapping_services):
    """[MSH-14] review a non-existent run → error verdict (handler runs)."""
    setup_map(mapping_services, _VAC, _MAP, count=2)
    result = await _call(hass, SERVICE_REVIEW_TRACE_RUN,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "run_id": "ghost", "room_id": 1})
    assert isinstance(result, dict)
    assert "verdict" in result


async def test_adjust_segment_blank_id(hass, mapping_services):
    """[MSH-2b] whitespace-only segment_id strips empty → missing_segment_id.

    Guards the strip-then-guard ordering at mapping_services.py:948-951:
    the handler must reject the blanked id with ``missing_segment_id``
    *before* the segment-existence lookup, so the reason is distinct from
    the seeded-but-unknown ``segment_not_found`` case (MSH-2).
    """
    _seed_segments(mapping_services)
    result = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "segment_id": "   "})
    assert result["saved"] is False
    assert result["reason"] == "missing_segment_id"


async def test_adjust_segment_vertex_moves_accumulate(hass, mapping_services):
    """[MSH-3a] vertex_moves on the same index accumulate into one entry.

    Two adjust calls (delta_x 5 then 3) on vertex index 0 of "s1" merge into a
    single move whose delta is the sum — exercising the accumulate branch of the
    vertex-merge loop (mapping_services.py:985-989).
    """
    _seed_segments(mapping_services)
    first = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "segment_id": "s1",
                         "vertex_moves": [{"index": 0, "delta_x": 5}]})
    assert first["saved"] is True
    second = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "segment_id": "s1",
                          "vertex_moves": [{"index": 0, "delta_x": 3}]})
    # single merged entry, deltas summed (5 + 3 = 8), delta_y untouched
    assert second["adjustment"]["vertex_moves"] == [
        {"index": 0, "delta_x": 8, "delta_y": 0}
    ]


async def test_adjust_segment_vertex_move_cancels_to_zero(hass, mapping_services):
    """[MSH-3b] a vertex move that nets to zero pops the whole adjustment.

    After +8 on vertex 0, sending -8 nets the move to zero, emptying the move
    set; with no offsets/edges either, the segment's adjustment is removed
    entirely — the pop branch of the vertex-merge loop (mapping_services.py:
    990-991) mirroring the card's "Vertex reset" button. The next read shows
    s1's polygon back at its un-translated seed coords.
    """
    _seed_segments(mapping_services)
    await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                {"vacuum_entity_id": _VAC, "map_id": _MAP,
                 "segment_id": "s1",
                 "vertex_moves": [{"index": 0, "delta_x": 8}]})
    reset = await _call(hass, SERVICE_ADJUST_MAP_SEGMENT,
                        {"vacuum_entity_id": _VAC, "map_id": _MAP,
                         "segment_id": "s1",
                         "vertex_moves": [{"index": 0, "delta_x": -8}]})
    # adjustment for s1 is gone from the response and from the stored bucket
    assert reset["adjustment"] is None
    bucket = ensure_map_bucket(
        data=mapping_services.data, vacuum_entity_id=_VAC, map_id=_MAP)
    assert "s1" not in bucket.get("image_segment_adjustments", {})
    # and the polygon reads back at its un-translated seed coords
    segments = await _call(hass, SERVICE_GET_MAP_SEGMENTS,
                           {"vacuum_entity_id": _VAC, "map_id": _MAP})
    s1 = next(s for s in segments["segments"] if s["segment_id"] == "s1")
    assert s1["polygon_pixel"][0] == [0, 0]

