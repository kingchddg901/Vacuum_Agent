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


# ---------------------------------------------------------------------------
# [MSV-21] _resolve_write_map_bucket -- the ladder eight handlers share
#
# services.yaml promises "Leave blank to use the current active map." That
# promise is kept HERE, once, for all eight. Each rung is tried in order and
# the test drives them one at a time by removing what the rung above needs.
# ---------------------------------------------------------------------------

async def test_msv21_an_omitted_map_id_resolves_to_the_ACTIVE_map(
    hass, mapping_services, monkeypatch
):
    """[MSV-21] Rung 2: no map_id given, so the vacuum's active map is used.

    This is the documented default and the common case -- a user calling the
    service from the UI never types a map id. The assertion is that the write
    landed on the ACTIVE map specifically, with a second bucket present that it
    must not have chosen: resolving to "some map" would satisfy a test that only
    checked for success.
    """
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id="other")
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)

    from custom_components.eufy_vacuum.rooms import room_discovery
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: _MAP)

    result = await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                         {"vacuum_entity_id": _VAC, "rotation": 90})

    assert result["saved"] is True
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 90
    assert "live_map_rotation" not in manager.data["maps"][_VAC]["other"], (
        "the write landed on a map that is not the active one"
    )


async def test_msv21b_an_active_map_lookup_that_RAISES_falls_through(
    hass, mapping_services, monkeypatch
):
    """[MSV-21b] Rung 3: the active-map lookup can fail, and the ladder continues.

    `get_active_map_id` reaches into room discovery, which reads live state. A
    vacuum mid-setup, or an adapter that has not registered, makes it raise --
    and a service the user just invoked must not fail because of it. The next
    rung is the first stored map, which is the right answer for the single-map
    install that is the overwhelming majority.

    RED IF THE except GOES: the exception escapes the handler and the user sees a
    traceback from a service that had a perfectly good map to write to.
    """
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)

    from custom_components.eufy_vacuum.rooms import room_discovery

    def _boom(h, v):
        raise RuntimeError("room discovery is not ready")

    monkeypatch.setattr(room_discovery, "get_active_map_id", _boom)

    result = await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                         {"vacuum_entity_id": _VAC, "rotation": 180})

    assert result["saved"] is True, (
        "a raising active-map lookup took down a service call that had a stored "
        "map to fall back on: %r" % (result,)
    )
    assert manager.data["maps"][_VAC][_MAP]["live_map_rotation"] == 180


async def test_msv21c_a_vacuum_with_no_maps_at_all_refuses_with_no_map(
    hass, mapping_services, monkeypatch
):
    """[MSV-21c] Rung 4: nothing exists yet, and the refusal says which nothing.

    `no_map` and `map_not_found` are different facts and the ladder keeps them
    apart: `no_map` means this vacuum has no maps AT ALL (so "pass map_id
    explicitly" is useless advice on its own, and the message says so), while
    `map_not_found` means the id you gave is not among the ones that exist.
    Collapsing them would send a user hunting for a typo in an id they never
    typed.
    """
    manager = mapping_services
    manager.data.setdefault("maps", {})[_VAC] = {}

    from custom_components.eufy_vacuum.rooms import room_discovery
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: None)

    result = await _call(hass, ms.SERVICE_SET_LIVE_MAP_ROTATION,
                         {"vacuum_entity_id": _VAC, "rotation": 90})

    assert result["saved"] is False
    assert result["reason"] == "no_map", (
        "expected no_map for a vacuum with no maps at all; got %r -- "
        "map_not_found would send the user looking for a typo in an id they "
        "never typed" % (result.get("reason"),)
    )
    assert _VAC in str(result.get("message") or ""), (
        "the refusal message does not name the vacuum it is about"
    )
    assert not manager.data["maps"][_VAC], (
        "a phantom bucket was minted for a vacuum that has no maps"
    )


# ---------------------------------------------------------------------------
# [MSV-22] upload_map_image -- the refusals between "bytes arrived" and
# "variant recorded". This handler writes a FILE, so a refusal that happens
# after the write has to take the file with it.
# ---------------------------------------------------------------------------

_PNG_1x1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="
)


def _upload(hass, **extra):
    data = {"vacuum_entity_id": _VAC, "map_id": _MAP, "image_base64": _PNG_1x1}
    data.update(extra)
    return _call(hass, ms.SERVICE_UPLOAD_MAP_IMAGE, data)


async def test_msv22_a_layout_scoped_upload_needs_the_layout_to_exist(
    hass, mapping_services
):
    """[MSV-22] Layout-scoped uploads are validated BEFORE any file is written.

    The variant key and the layout field are both DERIVED from `layout_id`, so a
    layout that does not exist has nowhere to put the result. Three shapes:

      art_scope with no layout_id      -> layout_id_required
      art_scope="room" with no room_id -> missing_room_id
      a layout_id naming nothing       -> layout_not_found

    The comment on the early map guard explains the ordering: this handler has
    three ensure_map_bucket sites and writes a PNG before the last of them, so
    validating late would leave an orphan file named for something that does not
    exist.
    """
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)

    out = await _upload(hass, art_scope="home")
    assert out["saved"] is False and out["reason"] == "layout_id_required"

    out = await _upload(hass, art_scope="room", layout_id="L1")
    assert out["saved"] is False and out["reason"] == "missing_room_id"

    out = await _upload(hass, art_scope="room", layout_id="L1", room_id="3")
    assert out["saved"] is False and out["reason"] == "layout_not_found", (
        "a room-art upload for a layout that does not exist was accepted: %r" % out
    )

    # the BACKDROP path has its own copy of the same check
    out = await _upload(hass, layout_id="L1")
    assert out["saved"] is False and out["reason"] == "layout_not_found", (
        "the per-layout backdrop path accepted a layout that does not exist: %r" % out
    )

    # ⚠ THE FILE IS WHAT THESE CHECKS ARE FOR, and the reason alone does not pin
    # them: ablating either copy leaves the REASON unchanged, because a later
    # check refuses too. What the early ones buy is in their own comment --
    # "validate before writing any file" -- so the observable is the absence of
    # an orphan PNG named for a layout that does not exist. Measured: without
    # that assertion both copies came back DEAD.
    import os as _os
    object_id = _VAC.split(".", 1)[1]
    art_dir = _os.path.join(
        hass.config.config_dir, "eufy_vacuum", "maps", object_id
    )
    strays = [
        f for f in (_os.listdir(art_dir) if _os.path.isdir(art_dir) else [])
        if "custom_L1" in f
    ]
    assert not strays, (
        "a PNG was written for a layout that does not exist: %r -- the record "
        "never lands, so the file is an orphan nothing will ever delete" % strays
    )


async def test_msv22b_bytes_that_are_not_an_image_are_refused_by_kind(
    hass, mapping_services
):
    """[MSV-22b] Two different failures, two different reasons.

    `invalid_base64` means the payload never decoded at all -- a truncated
    websocket frame, a card bug. `unsupported_format` means it decoded to bytes
    that are not a PNG and that Pillow could not convert either.

    KEEPING THEM APART IS THE CLAIM. They point at different culprits: the first
    is the transport, the second is the file the user chose. A single "bad image"
    reason sends them looking in the wrong place.
    """
    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)

    out = await _upload(hass, image_base64="!!!! not base64 !!!!")
    assert out["saved"] is False and out["reason"] == "invalid_base64"

    # decodes cleanly, but is not an image in any format
    import base64 as _b64
    not_an_image = _b64.b64encode(b"\x00\x01\x02 definitely not an image").decode()
    out = await _upload(hass, image_base64=not_an_image)
    assert out["saved"] is False and out["reason"] == "unsupported_format", (
        "bytes that decoded but are not an image were not refused as a FORMAT "
        "problem: %r" % out
    )


async def test_msv22c_an_unmeasurable_image_is_refused_AND_the_file_removed(
    hass, mapping_services, monkeypatch
):
    """[MSV-22c] "A refusal that leaves half its work behind is a second bug."

    Dimensions come from three sources, most reliable first: the PNG's own IHDR
    chunk (no dependency -- the spec fixes it as the first chunk), then Pillow,
    then the caller's declared values. If all three fail the variant cannot be
    recorded, because a variant persisted with null dimensions "is the state that
    then poisons every consumer downstream".

    The handler has already WRITTEN THE PNG by then, so the refusal unlinks it:
    a saved file whose variant record never lands is a leak, and the store and
    the filesystem would disagree.

    THE FILE CHECK IS THE ASSERTION. The refusal payload alone passes against a
    handler that refuses and leaves the orphan behind -- which is exactly the
    second bug the comment names.
    """
    import os as _os

    manager = mapping_services
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)

    # every dimension source fails: IHDR unreadable, Pillow unavailable, nothing
    # declared by the caller
    monkeypatch.setattr(ms, "_png_dimensions", lambda _b: None)
    import sys
    monkeypatch.setitem(sys.modules, "PIL", None)

    out = await _upload(hass)

    assert out["saved"] is False
    assert out["reason"] == "unreadable_image_dimensions", (
        "expected the dimension refusal; got %r" % out
    )

    object_id = _VAC.split(".", 1)[1]
    orphan = _os.path.join(
        hass.config.config_dir, "eufy_vacuum", "maps", object_id, f"map_{_MAP}.png"
    )
    assert not _os.path.exists(orphan), (
        "the refusal left the PNG it had already written on disk -- the store and "
        "the filesystem now disagree, which is the leak the code comment names"
    )
    assert not (manager.data["maps"][_VAC][_MAP].get("image_variants") or {}), (
        "a variant was recorded for an image that was refused"
    )


# ---------------------------------------------------------------------------
# [MSV-23] clean_saved_zones -- five refusals, and they MOVE HARDWARE if wrong
#
# This handler dispatches a real clean. Every refusal below is the difference
# between the robot going to the right place and going somewhere else, so each
# one names its own reason rather than sharing a generic failure.
# ---------------------------------------------------------------------------

def _seed_zone(manager, zid="z1", geometry=((0, 0), (0, 10), (10, 10), (10, 0))):
    bucket = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket.setdefault("saved_zones", {})[zid] = {
        "zone_id": zid, "name": "Rug", "geometry": [list(p) for p in geometry],
    }
    return bucket


async def test_msv23_an_indeterminate_active_map_is_not_a_match(
    hass, mapping_services, monkeypatch
):
    """[MSV-23] RP-029/ZONE-C-1: "indeterminate != match".

    The zones are stored per map, so cleaning them is only safe when the robot is
    ON that map. If the active map cannot be determined, the honest answer is a
    refusal -- NOT an assumption that it matches. Treating unknown as a match
    sends the robot to coordinates from a different floor's map.

    Two ways to be indeterminate and both refuse the same way: the lookup
    returning None, and the lookup raising.
    """
    manager = mapping_services
    _seed_zone(manager)

    from custom_components.eufy_vacuum.rooms import room_discovery

    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: None)
    out = await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONES,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": ["z1"]})
    assert out["cleaned"] is False
    assert out["reason"] == "active_map_indeterminate", (
        "an unknown active map was treated as a match -- the robot would be sent "
        "to coordinates from whatever map these zones belong to: %r" % out
    )

    def _boom(h, v):
        raise RuntimeError("discovery unavailable")

    monkeypatch.setattr(room_discovery, "get_active_map_id", _boom)
    out = await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONES,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": ["z1"]})
    assert out["reason"] == "active_map_indeterminate", (
        "a RAISING active-map lookup did not degrade to the same refusal"
    )


async def test_msv23b_a_map_that_is_not_the_active_one_refuses_and_says_which_is(
    hass, mapping_services, monkeypatch
):
    """[MSV-23b] The refusal carries the ACTIVE id, because that is the fix.

    Knowing the request was for the wrong map is not actionable on its own; the
    user needs to know which map the robot is actually on. The payload names it.
    """
    manager = mapping_services
    _seed_zone(manager)
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id="upstairs")

    from custom_components.eufy_vacuum.rooms import room_discovery
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: "upstairs")

    out = await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONES,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": ["z1"]})

    assert out["cleaned"] is False and out["reason"] == "map_not_active"
    assert out.get("active_map_id") == "upstairs", (
        "the refusal did not name the map the robot is actually on, which is the "
        "only thing that tells the user what to do next: %r" % out
    )


async def test_msv23c_unknown_and_degenerate_zones_refuse_by_kind(
    hass, mapping_services, monkeypatch
):
    """[MSV-23c] `zone_not_found` and `bad_geometry` are different problems.

    An id naming no stored zone is a stale reference -- the zone was deleted, or
    the caller has an old list. A zone whose geometry has fewer than three usable
    points is stored but unusable -- a truncated write, or an author UI that saved
    mid-drag. Each names the offending ids so the user can act on the specific
    one rather than the whole call.

    THE ORDER MATTERS AND IS ASSERTED: missing is checked before bad, so a call
    carrying both reports the stale reference first -- the one the caller can fix
    without touching the map.
    """
    manager = mapping_services
    bucket = _seed_zone(manager)
    bucket["saved_zones"]["degenerate"] = {
        "zone_id": "degenerate", "name": "Sliver",
        "geometry": [[0, 0], [1, 1]],          # two points: not a polygon
    }

    from custom_components.eufy_vacuum.rooms import room_discovery
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: _MAP)

    out = await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONES,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP,
                       "zone_ids": ["z1", "degenerate"]})
    assert out["cleaned"] is False and out["reason"] == "bad_geometry"
    assert out.get("zone_ids") == ["degenerate"], (
        "the refusal did not name only the unusable zone: %r" % out
    )

    out = await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONES,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP,
                       "zone_ids": ["z1", "never_saved", "degenerate"]})
    assert out["reason"] == "zone_not_found", (
        "a call carrying BOTH a stale id and a broken zone reported the geometry "
        "problem first; the stale reference is the one the caller can fix: %r" % out
    )
    assert out.get("zone_ids") == ["never_saved"]


# ---------------------------------------------------------------------------
# [MSV-24] delete_map_image -- the unlink can fail for two different reasons
# ---------------------------------------------------------------------------

async def test_msv24_a_file_that_cannot_be_REMOVED_still_drops_the_record(
    hass, mapping_services, monkeypatch, caplog
):
    """[MSV-24] A permission error is not the same as an absent file, and neither blocks.

    [MSV-14] covers the already-gone case. This is the other arm: the file is
    there and `os.remove` fails -- a read-only mount, a file held open on
    Windows, an ACL. The record is still dropped, because leaving it would show
    the user a variant whose image they cannot delete, forever.

    The warning is asserted because it is the only trace: `file_removed` comes
    back False either way, so without the log the two failures are
    indistinguishable in a bug report.
    """
    import logging
    import os as _os

    manager = mapping_services
    bucket = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    bucket["image_variants"] = {
        "default": {"path": "/nonexistent/held_open.png", "width": 10, "height": 10}
    }

    real_remove = _os.remove

    def _denied(path, *a, **kw):
        if str(path).endswith("held_open.png"):
            raise PermissionError(13, "Permission denied")
        return real_remove(path, *a, **kw)

    monkeypatch.setattr(ms.os, "remove", _denied)

    with caplog.at_level(logging.WARNING):
        out = await _call(hass, ms.SERVICE_DELETE_MAP_IMAGE,
                          {"vacuum_entity_id": _VAC, "map_id": _MAP,
                           "variant": "default"})

    assert out.get("deleted") is True, (
        "a file that could not be removed blocked the record deletion; the user "
        "keeps a variant whose image they cannot delete: %r" % out
    )
    assert not (bucket.get("image_variants") or {}), "the variant record survived"
    assert "failed to remove" in caplog.text, (
        "the only trace of a permission failure is this warning, and it was not "
        "written -- file_removed is False for an absent file too"
    )


async def test_msv25_the_SINGULAR_clean_refuses_by_the_same_ladder(
    hass, mapping_services, monkeypatch
):
    """[MSV-25] `clean_saved_zone` carries its own copy of `clean_saved_zones`' ladder.

    ⚠ THESE TWO ARE A REPLICA PAIR. The singular and plural handlers implement the
    same refusals -- zone_not_found, active_map_indeterminate, map_not_active,
    bad_geometry -- with the same RP-029/ZONE-C-1 reasoning quoted in both:
    "A saved zone's geometry is only valid on ITS map, so an unknown active map
    must refuse, not assume." Neither carries a replica anchor today, so nothing
    sends a reader from one to the other; [MSV-23..23c] pin the plural and this
    pins the singular, independently, so a fix landing in one copy and not the
    other goes red here.

    All four refusals in one test because they are one ladder and the ORDER is
    part of it: an unknown zone is refused before the map is even consulted,
    since a stale id is the caller's problem and tells them nothing about where
    the robot is.
    """
    manager = mapping_services
    bucket = _seed_zone(manager)
    bucket["saved_zones"]["degenerate"] = {
        "zone_id": "degenerate", "name": "Sliver", "geometry": [[0, 0], [1, 1]],
    }

    from custom_components.eufy_vacuum.rooms import room_discovery

    def _one(zone_id):
        return _call(hass, ms.SERVICE_CLEAN_SAVED_ZONE,
                     {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": zone_id})

    # unknown zone: refused before the active map is consulted at all
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: None)
    out = await _one("never_saved")
    assert out["cleaned"] is False and out["reason"] == "zone_not_found", (
        "a stale zone id reported a map problem instead of naming itself: %r" % out
    )

    # indeterminate active map
    out = await _one("z1")
    assert out["reason"] == "active_map_indeterminate"

    # wrong active map, and it says which
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: "upstairs")
    out = await _one("z1")
    assert out["reason"] == "map_not_active" and out.get("active_map_id") == "upstairs"

    # right map, unusable geometry
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: _MAP)
    out = await _one("degenerate")
    assert out["reason"] == "bad_geometry", (
        "a two-point zone was dispatched as a rectangle: %r" % out
    )


async def test_msv26_the_zone_area_backfill_is_advisory_and_never_breaks_the_read(
    hass, mapping_services, monkeypatch
):
    """[MSV-26] "sizing is advisory; a fetch failure must not break the read".

    This self-heals a saved zone's `area_m2` on the dashboard read, so it runs
    every time the card loads. Four ways it declines, and all of them answer
    False rather than raising -- because the caller is a READ, and a zone without
    a size is a cosmetic gap while a raised exception is a blank dashboard.

      nothing pending        -> False, and no map fetch attempted
      a wrong active map     -> False (sizing off another map's raster is wrong)
      the map fetch fails    -> False
      one zone's membership raises -> that zone skipped, the others still sized

    THE LAST IS THE ONE WITH A CONTROL. A second, healthy zone is present so a
    backfill that abandoned the loop on the first bad zone would be visible --
    "no crash" alone passes against exactly that.
    """
    manager = mapping_services
    bucket = ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=_MAP)
    from custom_components.eufy_vacuum.rooms import room_discovery
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: _MAP)

    # 1. nothing pending -- every zone already sized
    bucket["saved_zones"] = {
        "z1": {"zone_id": "z1", "geometry": [[0, 0], [0, 9], [9, 9]], "area_m2": 4.0},
    }
    fetched = []
    async def _fetch(**kw):
        fetched.append(kw)
        return {"room_pixels": "x"}
    monkeypatch.setattr(manager, "async_get_map_data_dict", _fetch, raising=False)

    assert await ms._backfill_saved_zone_area(
        hass, manager, vacuum_entity_id=_VAC, map_id=_MAP, map_bucket=bucket
    ) is False
    assert fetched == [], (
        "a backfill with nothing pending still fetched the map raster -- that is "
        "an image decode on every dashboard read"
    )

    # 2. the active map is a DIFFERENT one -- sizing off its raster would be wrong.
    # ⚠ `zone_membership` is made to SUCCEED first, or this proves nothing: left
    # as the real one it declined anyway and the guard had no red of its own.
    # Measured -- that ablation came back DEAD.
    monkeypatch.setattr(
        ms, "zone_membership", lambda md, geom: {"area_m2": 9.9, "room_number": 1}
    )
    bucket["saved_zones"]["z2"] = {
        "zone_id": "z2", "geometry": [[0, 0], [0, 9], [9, 9]], "area_m2": None,
    }
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: "upstairs")
    assert await ms._backfill_saved_zone_area(
        hass, manager, vacuum_entity_id=_VAC, map_id=_MAP, map_bucket=bucket
    ) is False
    assert bucket["saved_zones"]["z2"]["area_m2"] is None

    # 3. the map fetch itself fails
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: _MAP)
    async def _boom(**kw):
        raise RuntimeError("store unreadable")
    monkeypatch.setattr(manager, "async_get_map_data_dict", _boom, raising=False)
    assert await ms._backfill_saved_zone_area(
        hass, manager, vacuum_entity_id=_VAC, map_id=_MAP, map_bucket=bucket
    ) is False

    # 4. one zone's membership raises; a healthy sibling must still be sized
    bucket["saved_zones"]["z3"] = {
        "zone_id": "z3", "geometry": [[1, 1], [1, 8], [8, 8]], "area_m2": None,
    }
    monkeypatch.setattr(manager, "async_get_map_data_dict", _fetch, raising=False)

    def _membership(map_data, geometry):
        if geometry and geometry[0] == [0, 0]:
            raise ValueError("this zone's geometry is unusable")
        return {"area_m2": 3.5, "room_number": 2}

    monkeypatch.setattr(ms, "zone_membership", _membership)

    changed = await ms._backfill_saved_zone_area(
        hass, manager, vacuum_entity_id=_VAC, map_id=_MAP, map_bucket=bucket
    )

    assert changed is True
    assert bucket["saved_zones"]["z2"]["area_m2"] is None, (
        "the zone whose membership raised was given a size anyway"
    )
    assert bucket["saved_zones"]["z3"]["area_m2"] == 3.5, (
        "the healthy zone after the raising one was never sized -- the loop "
        "abandoned the rest on the first bad zone"
    )


async def test_msv25b_the_singular_clean_also_survives_a_RAISING_map_lookup(
    hass, mapping_services, monkeypatch
):
    """[MSV-25b] Returning None and RAISING are different code paths, same answer.

    [MSV-25] drives the lookup returning None. The handler ALSO wraps the call in
    its own try, because `get_active_map_id` reaches into room discovery and can
    raise outright on a vacuum mid-setup. Measured: testing only the None case
    left that except arm uncovered -- the right answer by the other road.

    [MSV-23] already pins the same pair on the plural handler; this is the
    singular copy of the replica.
    """
    manager = mapping_services
    _seed_zone(manager)

    from custom_components.eufy_vacuum.rooms import room_discovery

    def _boom(h, v):
        raise RuntimeError("discovery unavailable")

    monkeypatch.setattr(room_discovery, "get_active_map_id", _boom)

    out = await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONE,
                      {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": "z1"})

    assert out["cleaned"] is False
    assert out["reason"] == "active_map_indeterminate", (
        "a raising active-map lookup escaped the singular handler instead of "
        "degrading to the same refusal as a None return: %r" % out
    )


async def test_msv27_a_failed_dispatch_is_raised_as_a_HomeAssistantError(
    hass, mapping_services, monkeypatch
):
    """[MSV-27] A dispatch failure is an ERROR, not a refusal -- and both handlers agree.

    Every other failure in these handlers answers `{"cleaned": False, "reason":
    ...}`, because the request was understood and declined. A dispatch that
    raises is different: the request was ACCEPTED and the robot was told to go,
    and something went wrong mid-command. That surfaces to the caller as a
    HomeAssistantError so the service call itself fails, rather than returning a
    tidy payload that implies the zone was simply not cleaned.

    BOTH COPIES, because singular and plural carry the same wrapper
    independently -- the replica noted in [MSV-25]. The original exception is
    chained (`from err`), so the cause survives into the log.
    """
    manager = mapping_services
    _seed_zone(manager)

    from custom_components.eufy_vacuum.rooms import room_discovery
    monkeypatch.setattr(room_discovery, "get_active_map_id", lambda h, v: _MAP)

    async def _boom(**kw):
        raise RuntimeError("the robot refused the command")

    monkeypatch.setattr(manager, "dispatch_zone_clean", _boom, raising=False)

    with pytest.raises(Exception) as caught_single:
        await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONE,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_id": "z1"})
    assert "clean saved zone" in str(caught_single.value).lower(), (
        "the singular dispatch failure did not surface as its own error: %r"
        % (caught_single.value,)
    )

    with pytest.raises(Exception) as caught_plural:
        await _call(hass, ms.SERVICE_CLEAN_SAVED_ZONES,
                    {"vacuum_entity_id": _VAC, "map_id": _MAP, "zone_ids": ["z1"]})
    assert "clean saved zones" in str(caught_plural.value).lower(), (
        "the plural dispatch failure did not surface as its own error: %r"
        % (caught_plural.value,)
    )
