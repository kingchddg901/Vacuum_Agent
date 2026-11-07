"""Integration tests for the non-segment mapping service handlers.

These call the surviving map-image / rotation / overlay / render service
handlers through the service registry, covering the handler closures
registered by async_register_mapping_services.

Coverage targets
----------------
[MSV-14] delete_map_image when the PNG is already gone → record still dropped.
[MSV-15] set_live_map_rotation stores the display rotation on the map bucket.
[MSV-16] set_map_overlay_visibility persists only the user's deltas (not the resolved map), merges them over the defaults at read time, merges successive partial calls, rejects unknown layers, and resets cleanly back to defaults.
[MSV-17] get_map_render_data is registered and degrades gracefully with present=False / reason=not_configured when the adapter declares no map_render block.
[MSV-18] delete_map_image clears dangling custom_layouts references (backdrop, home art, room art) to the deleted variant (RP-016).
[MSV-16b] set_map_overlay_visibility REFUSES an unknown map_id instead of minting a phantom durable bucket for it (RP-028/SERVIC-1).
[MSV-19] rename_saved_zone refuses an unknown map_id the same way its create_saved_zone sibling already did.
[MSV-20] the RP-028 sweep: all 14 remaining write handlers refuse an unknown map_id, each via its OWN refusal key (saved / deleted / available / cleaned), and mint nothing. Plus the managed-case control, without which a blanket refusal would pass.
"""

from __future__ import annotations

import os

import pytest

from custom_components.eufy_vacuum.const import DOMAIN
from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket
from custom_components.eufy_vacuum.mapping import mapping_services as ms
from custom_components.eufy_vacuum.mapping.mapping_services import (
    async_register_mapping_services,
    async_unregister_mapping_services,
)


_VAC = "vacuum.alfred"
_MAP = "6"


@pytest.fixture
async def mapping_services(hass, manager):
    await async_register_mapping_services(hass)
    yield manager
    await async_unregister_mapping_services(hass)


async def _call(hass, service, data):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True)


async def test_set_live_map_rotation(hass, mapping_services):
    """[MSV-15] set_live_map_rotation persists the live-map DISPLAY rotation on the
    map bucket (display only; schema validates 0/90/180/270). RP-032: map_id is now
    Optional and resolved against an EXISTING bucket (require_map_bucket, never a
    phantom create), so the bucket is seeded here first."""
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    result = await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "rotation": 90})
    assert result["saved"] is True
    assert result["live_map_rotation"] == 90
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 90
    # overwrite with another valid value
    await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "rotation": 270})
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 270
    # an out-of-set value is rejected by the schema (stored value unchanged)
    with pytest.raises(Exception):
        await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "rotation": 45})
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 270


async def test_set_live_map_rotation_unknown_map_refuses(hass, mapping_services):
    """[MSV-15b] RP-032: an address that was never discovered/created refuses
    map_not_found instead of minting a phantom bucket for it."""
    result = await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                         {"vacuum_entity_id": _VAC, "map_id": "never_seeded", "rotation": 90})
    assert result["saved"] is False
    assert result["reason"] == "map_not_found"


async def test_set_map_overlay_visibility(hass, mapping_services):
    """[MSV-16] set_map_overlay_visibility stores only the user's deltas, merges them
    over the defaults at read time, rejects unknown layers, and resets cleanly.

    RE-POINTED: this used to pass WITHOUT seeding the bucket, because the handler called
    `ensure_map_bucket` and minted the address on the way through. That was the defect
    (RP-028/SERVIC-1), so the bucket is seeded here first -- the same change [MSV-15]
    already carries for set_live_map_rotation, and for the same reason."""
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    result = await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP,
                          "visibility": {"no_go": True, "dock": False}})
    assert result["saved"] is True
    vis = result["overlay_visibility"]
    assert vis["no_go"] is True and vis["dock"] is False
    assert vis["robot"] is True                       # default preserved
    # only the deltas are persisted, not the full resolved map
    assert manager.data["maps"][_VAC][_MAP]["overlay_visibility"] == {
        "no_go": True, "dock": False}
    # a second partial call MERGES (doesn't wipe the prior deltas)
    await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                {"vacuum_entity_id": _VAC, "map_id": _MAP, "visibility": {"path": True}})
    assert manager.data["maps"][_VAC][_MAP]["overlay_visibility"] == {
        "no_go": True, "dock": False, "path": True}
    # an unknown layer is rejected by the schema
    with pytest.raises(Exception):
        await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP,
                     "visibility": {"bogus": True}})
    # reset clears the deltas -> back to defaults
    result = await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "reset": True})
    assert "overlay_visibility" not in manager.data["maps"][_VAC][_MAP]
    assert result["overlay_visibility"]["robot"] is True


async def test_get_map_render_data_absent(hass, mapping_services):
    """[MSV-17] get_map_render_data is registered + degrades gracefully when the adapter
    declares no map_render block (no crash, present:false)."""
    result = await _call(hass, ms.SERVICE_GET_MAP_RENDER_DATA, {"vacuum_entity_id": _VAC})
    assert result["present"] is False
    assert result.get("reason") == "not_configured"


async def test_delete_map_image_file_already_gone(hass, mapping_services):
    """[MSV-14] delete_map_image when the PNG is already missing on disk:
    _remove_file hits FileNotFoundError and returns False, but the service
    still drops the stale variant record. Guards the "PNG gone, still drop
    the record" contract (mapping_services.py:691-692)."""
    manager = mapping_services
    object_id = _VAC.split(".", 1)[1]
    missing_path = os.path.join(
        hass.config.config_dir, "eufy_vacuum", "maps", object_id, "does_not_exist.png"
    )
    # Sanity: the file must be absent so os.remove raises FileNotFoundError.
    assert not os.path.exists(missing_path)

    map_bucket = ensure_map_bucket(
        data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP
    )
    map_bucket["image_variants"] = {
        "default": {
            "variant": "default",
            "path": missing_path,
            "browser_url": "/local/eufy_vacuum/missing.png",
            "width": 100,
            "height": 100,
        }
    }

    result = await _call(hass, ms.SERVICE_DELETE_MAP_IMAGE,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "default"})

    # Record dropped even though the file was already gone.
    assert result["deleted"] is True
    # FileNotFoundError branch: nothing was actually removed from disk.
    assert result["file_removed"] is False
    assert result["remaining_variants"] == []
    # Persisted side effect: the stale variant is gone from the bucket.
    assert map_bucket["image_variants"] == {}


async def test_delete_map_image_clears_layout_references(hass, mapping_services):
    """RP-016/RF-20 (delegation-checked against upload's layout-awareness):
    deleting an image variant still referenced by a layout's backdrop, home
    art, or a room's art must clear those references too -- otherwise the
    layout is left pointing at a file that no longer exists, unlike upload
    which keeps the two in sync (mapping_services.py's own
    _handle_upload_map_image)."""
    manager = mapping_services
    map_bucket = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    missing_path = os.path.join(
        hass.config.config_dir, "eufy_vacuum", "maps",
        _VAC.split(".", 1)[1], "does_not_exist.png",
    )
    map_bucket["image_variants"] = {
        "custom_L1": {"variant": "custom_L1", "path": missing_path},
    }
    map_bucket["custom_layouts"] = {
        "L1": {
            "backdrop_variant": "custom_L1",
            "home_art": {"art_variant": "custom_L1"},
            "rooms": {"3": {"art_variant": "custom_L1"}},
        },
        "L2": {"backdrop_variant": "custom_L2"},  # untouched -- different variant
    }

    result = await _call(hass, ms.SERVICE_DELETE_MAP_IMAGE,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP, "variant": "custom_L1"})

    assert result["deleted"] is True
    assert result["cleared_layout_references"] == {"backdrops": 1, "home_art": 1, "room_art": 1}
    layouts = map_bucket["custom_layouts"]
    assert layouts["L1"]["backdrop_variant"] is None
    assert layouts["L1"]["home_art"]["art_variant"] is None
    assert layouts["L1"]["rooms"]["3"]["art_variant"] is None
    assert layouts["L2"]["backdrop_variant"] == "custom_L2"  # untouched


async def test_msv16b_overlay_visibility_unknown_map_refuses(hass, mapping_services):
    """[MSV-16b] RP-028/SERVIC-1: a caller-addressed write must refuse an unknown map.

    THE DEFECT THIS CLOSES: the handler held its own copy of the map-resolution ladder
    and finished it with `ensure_map_bucket`, whose `setdefault` CREATES the address. A
    typo'd map_id therefore wrote a durable bucket into .storage, persisted it, and
    returned `saved: true`. `require_map_bucket`'s docstring forbids exactly that for
    "every mapping SERVICE handler that WRITES against a caller-supplied map_id".

    ABLATION: restore `ensure_map_bucket` in the handler and this goes red twice over --
    `saved` comes back True, and the phantom bucket assertion below finds a bucket.
    """
    manager = mapping_services
    result = await _call(hass, ms.SERVICE_SET_MAP_OVERLAY_VISIBILITY,
                         {"vacuum_entity_id": _VAC, "map_id": "never_seeded",
                          "visibility": {"no_go": True}})
    assert result["saved"] is False
    assert result["reason"] == "map_not_found", (
        "the key is `reason`, matching the other RP-032 handlers -- it used to be `error`"
    )
    assert "never_seeded" not in manager.data.get("maps", {}).get(_VAC, {}), (
        "a refused write must leave NOTHING behind; this is the phantom bucket itself"
    )


async def test_msv19_rename_saved_zone_unknown_map_refuses(hass, mapping_services):
    """[MSV-19] the same defect, ten lines from the handler that already did it right.

    `_handle_create_saved_zone` used `require_map_bucket` and refused `map_not_found`.
    `_handle_rename_saved_zone` used `ensure_map_bucket` -- so a typo'd map_id minted a
    durable bucket AND then answered `zone_not_found`, a refusal naming the wrong cause
    with a bucket left behind that no map will ever reconcile.

    ABLATION: restore `ensure_map_bucket` and this goes red on the reason (zone_not_found
    instead of map_not_found) and on the phantom bucket.
    """
    manager = mapping_services
    result = await _call(hass, ms.SERVICE_RENAME_SAVED_ZONE,
                         {"vacuum_entity_id": _VAC, "map_id": "never_seeded",
                          "zone_id": "z1", "name": "Hallway"})
    assert result["saved"] is False
    assert result["reason"] == "map_not_found", (
        "an unknown MAP must not be reported as an unknown ZONE"
    )
    assert "known_maps" in result, "name what the caller could have meant"
    assert "never_seeded" not in manager.data.get("maps", {}).get(_VAC, {})


# ---------------------------------------------------------------------------
# [MSV-20] The RP-028 sweep: every mapping handler that WRITES against a
# caller-supplied map_id refuses an unknown address instead of minting one.
#
# RP-028 (2026-08-02) applied this rule to a NAMED LIST of findings and registered
# nothing durable, so sixteen handlers in this file kept calling `ensure_map_bucket`
# -- whose `setdefault` creates the address -- on a required, unvalidated map_id.
# Two were fixed first (MSV-16b, MSV-19); these are the rest.
#
# ONE PARAMETRISED TEST, not fourteen, because the rule is one rule. What varies and
# is therefore asserted per handler is the REFUSAL KEY: these do not all answer
# `saved`. Getting that wrong is a silent failure at the card, which is why each key
# below was read off the handler's own existing refusals rather than assumed.
# ---------------------------------------------------------------------------

_RP028_SWEEP = [
    # (service, extra required payload, the key THIS handler refuses with)
    (ms.SERVICE_UPLOAD_MAP_IMAGE, {"image_base64": "aGVsbG8="}, "saved"),
    (ms.SERVICE_DELETE_MAP_IMAGE, {}, "deleted"),
    (ms.SERVICE_ANALYZE_MAP_IMAGE, {}, "available"),
    (ms.SERVICE_SET_SEGMENTATION_MODE, {"mode": "cv"}, "saved"),
    (ms.SERVICE_SET_CUSTOM_SEGMENTS,
     {"layout_id": "L1",
      "segments": [{"id": "s1", "primitives": [{"type": "rect", "x": 1, "y": 1,
                                                "w": 2, "h": 2}]}]}, "saved"),
    # `index` is required only INSIDE vertex_moves, not at the top level.
    (ms.SERVICE_ADJUST_MAP_SEGMENT, {"segment_id": "s1"}, "saved"),
    (ms.SERVICE_CREATE_CUSTOM_LAYOUT, {"name": "L"}, "saved"),
    (ms.SERVICE_RENAME_CUSTOM_LAYOUT, {"layout_id": "L1", "name": "L2"}, "saved"),
    (ms.SERVICE_DELETE_CUSTOM_LAYOUT, {"layout_id": "L1"}, "saved"),
    (ms.SERVICE_SET_ACTIVE_CUSTOM_LAYOUT, {}, "saved"),
    (ms.SERVICE_DELETE_SAVED_ZONE, {"zone_id": "z1"}, "saved"),
    (ms.SERVICE_SET_SAVED_ZONE_ROOM, {"zone_id": "z1", "room_number": 1}, "saved"),
    (ms.SERVICE_CLEAN_SAVED_ZONE, {"zone_id": "z1"}, "cleaned"),
    (ms.SERVICE_CLEAN_SAVED_ZONES, {"zone_ids": ["z1"]}, "cleaned"),
]


@pytest.mark.parametrize("service,extra,key", _RP028_SWEEP,
                         ids=[s for s, _e, _k in _RP028_SWEEP])
async def test_msv20_write_handlers_refuse_an_unknown_map(
    hass, mapping_services, service, extra, key
):
    """[MSV-20] refuse the address, and leave NOTHING behind.

    The second assertion is the defect itself: `ensure_map_bucket` would have written
    `maps[vacuum]["never_seeded"]` into live storage, and from that moment "never
    configured" and "configured and empty" are byte-identical forever -- the same
    irreversible-as-evidence loss INKV8ZQD describes one level up.

    ABLATION: restore `ensure_map_bucket` in any one handler and that handler's case
    goes red on both counts -- the refusal key and the phantom bucket.
    """
    manager = mapping_services
    assert "never_seeded" not in manager.data.get("maps", {}).get(_VAC, {}), (
        "the premise: nothing exists at that address before the call"
    )

    result = await _call(hass, service,
                         {"vacuum_entity_id": _VAC, "map_id": "never_seeded", **extra})

    assert result[key] is False, (
        f"{service} must refuse via its own key {key!r} -- these handlers do not all "
        f"answer `saved`, and a refusal under the wrong key reads as success"
    )
    assert result["reason"] == "map_not_found"
    assert "known_maps" in result, "name what the caller could have meant"
    assert "never_seeded" not in manager.data.get("maps", {}).get(_VAC, {}), (
        "THE PHANTOM BUCKET: a refused write must not mint the address it refused"
    )


async def test_msv20b_a_known_map_is_still_served(hass, mapping_services):
    """[MSV-20] the control, and it is the one that matters.

    A guard that refused everything would pass all fourteen cases above. This asserts
    the MANAGED case still works -- the same role [UV-5] plays for INKV8ZQD, whose
    entry records that without it a blanket refusal looks identical to a correct fix.
    """
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)

    result = await _call(hass, ms.SERVICE_SET_ACTIVE_CUSTOM_LAYOUT,
                         {"vacuum_entity_id": _VAC, "map_id": _MAP})
    assert result["saved"] is True, "a real map must still be writable"
    assert result.get("reason") != "map_not_found"
