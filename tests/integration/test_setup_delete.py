"""Phase 7 integration tests — setup/delete.py (delete_map workflow).

Coverage targets
----------------
[SD-1]  No manager → error + code=manager_unavailable.
[SD-2]  Map not found / no rooms → already_done + code=map_not_found.
[SD-3]  Elevated-protection map without token → requires_confirmation.
[SD-4]  Elevated-protection map with any truthy token → success.
[SD-5]  NAMED high-protection map (2+ reasons) without token → requires_confirmation
        with code=typed_confirmation_required.
[SD-5b] UNNAMED high-protection map without token → one-click confirmation_required
        (no locale-invariant name to type; typed_confirmation_value is None).
[SD-6]  NAMED high-protection map with wrong token → blocked + code=confirmation_mismatch.
[SD-6b] UNNAMED high-protection map with any truthy token → success (one-click).
[SD-7]  NAMED high-protection map with correct token (stored name) → success.
[SD-8]  Success removes the map bucket from manager.data.
[SD-9]  Success with no remaining maps → warning present and next_actions includes
        import_active_map.
[SD-10] Delete sweeps leftover registry entities (platform=DOMAIN, unique_id
        prefixed by vacuum+map) that platform teardown may have missed.
[SD-11] An EMPTY bucket exists and is deletable — absent and empty are different
        answers, and conflating them made a phantom map permanently unremovable
        through the only route the UI offers.
[SD-11c] THE PUBLISHED RECIPE: the exact call the release notes tell a user to make,
        on the install shape the notes describe (ONE real map + the leftover).
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.const import DATA_RUNTIME, DOMAIN
from custom_components.eufy_vacuum.setup.delete import delete_map

from .conftest import setup_map


_VAC = "vacuum.alfred"
_MAP = "1"
_MAP2 = "2"


def _add_history(manager, vacuum_entity_id: str, map_id: str) -> None:
    """Seed learning history so evaluate_map_protection adds 'has_learning_data' reason."""
    manager.data.setdefault("room_history", {})
    manager.data["room_history"].setdefault(vacuum_entity_id, {})
    manager.data["room_history"][vacuum_entity_id][str(map_id)] = {"1": {"visits": 1}}


def _name_map(manager, vacuum_entity_id: str, map_id: str, name: str) -> None:
    """Give a map a stored display name.

    A high-protection map only enforces TYPED confirmation when it has a real,
    locale-invariant stored name to match against; an unnamed high map drops to a
    one-click confirm (the backend never fabricates an English "Map N" token).
    """
    bucket = manager.data["maps"][vacuum_entity_id][str(map_id)]
    bucket.setdefault("metadata", {})["display_name"] = name


# ---------------------------------------------------------------------------
# [SD-1] No manager
# ---------------------------------------------------------------------------

async def test_delete_map_no_manager_returns_error(hass):
    """[SD-1] delete_map returns error when manager is absent."""
    hass.data.setdefault(DOMAIN, {})
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "error"
    assert result["code"] == "manager_unavailable"


# ---------------------------------------------------------------------------
# [SD-2] Map not found
# ---------------------------------------------------------------------------

async def test_delete_map_not_found_returns_already_done(hass, manager):
    """[SD-2] delete_map returns already_done when the map has no imported data."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "already_done"
    assert result["code"] == "map_not_found"


# ---------------------------------------------------------------------------
# [SD-3] Elevated protection — no token
# ---------------------------------------------------------------------------

async def test_delete_map_elevated_no_token_returns_requires_confirmation(hass, manager):
    """[SD-3] Single imported map (only_map reason) without a token → requires_confirmation."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "requires_confirmation"
    assert result["code"] == "confirmation_required"
    assert "protection" in result["data"]


# ---------------------------------------------------------------------------
# [SD-4] Elevated protection — truthy token → success
# ---------------------------------------------------------------------------

async def test_delete_map_elevated_with_token_returns_success(hass, manager):
    """[SD-4] Elevated-protection map with any truthy confirmation_token → success."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="confirm"
    )
    assert result["status"] == "success"
    assert result["code"] == "map_deleted"


# ---------------------------------------------------------------------------
# [SD-5] High protection — no token
# ---------------------------------------------------------------------------

async def test_delete_map_high_protection_no_token_typed_confirmation_required(hass, manager):
    """[SD-5] NAMED high-protection map (2+ reasons) without token → typed_confirmation_required."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)  # adds has_learning_data → 2nd reason → high
    _name_map(manager, _VAC, _MAP, "Upstairs")
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "requires_confirmation"
    assert result["code"] == "typed_confirmation_required"


async def test_delete_map_unnamed_high_no_token_returns_one_click_confirmation(hass, manager):
    """[SD-5b] UNNAMED high-protection map without token → one-click confirmation_required.

    No locale-invariant name to type, so typed-confirm is dropped; the protection
    payload exposes requires_typed_confirmation=False and a null typed value.
    """
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "requires_confirmation"
    assert result["code"] == "confirmation_required"
    protection = result["data"]["protection"]
    assert protection["protection_level"] == "high"
    assert protection["requires_typed_confirmation"] is False
    assert protection["requires_confirmation"] is True
    assert protection["typed_confirmation_value"] is None


# ---------------------------------------------------------------------------
# [SD-6] High protection — wrong token
# ---------------------------------------------------------------------------

async def test_delete_map_high_protection_wrong_token_returns_blocked(hass, manager):
    """[SD-6] NAMED high-protection map with wrong confirmation token → blocked."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)
    _name_map(manager, _VAC, _MAP, "Upstairs")
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="wrong name"
    )
    assert result["status"] == "blocked"
    assert result["code"] == "confirmation_mismatch"


async def test_delete_map_unnamed_high_with_token_returns_success(hass, manager):
    """[SD-6b] UNNAMED high-protection map with any truthy token → success (one-click)."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="confirmed"
    )
    assert result["status"] == "success"
    assert result["code"] == "map_deleted"


# ---------------------------------------------------------------------------
# [SD-7] High protection — correct token
# ---------------------------------------------------------------------------

async def test_delete_map_high_protection_correct_token_returns_success(hass, manager):
    """[SD-7] NAMED high-protection map with correct token (the stored name) → success."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)
    _name_map(manager, _VAC, _MAP, "Upstairs")
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="Upstairs"
    )
    assert result["status"] == "success"
    assert result["code"] == "map_deleted"


# ---------------------------------------------------------------------------
# [SD-8] Success removes map from manager.data
# ---------------------------------------------------------------------------

async def test_delete_map_success_removes_map_data(hass, manager):
    """[SD-8] Successful delete removes the map bucket from manager.data."""
    setup_map(manager, _VAC, _MAP, count=2)
    await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="confirm"
    )
    vac_maps = manager.data.get("maps", {}).get(_VAC, {})
    assert _MAP not in vac_maps or not vac_maps.get(_MAP, {}).get("rooms")


# ---------------------------------------------------------------------------
# [SD-9] No remaining maps → warning + import_active_map in next_actions
# ---------------------------------------------------------------------------

async def test_delete_map_no_remaining_maps_adds_warning(hass, manager):
    """[SD-9] Deleting the last map adds a warning and suggests import_active_map."""
    setup_map(manager, _VAC, _MAP, count=2)
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="confirm"
    )
    assert result["status"] == "success"
    assert len(result["warnings"]) > 0
    assert "import_active_map" in result["next_actions"]


async def test_delete_map_sweeps_stale_registry_entities(hass, manager):
    """[SD-10] (RP-009 / REVIEW D3, GATE4 Q15) delete sweeps by the CLOSED SET of
    ids reconstructed from the deleted map's stored rooms.

    Superseded contract: the old prefix sweep deleted ANY prefix-matching entry —
    including, provably, a sibling vacuum's entities (DR-SETUP-1). Now: an entry
    whose unique_id is reconstructible from the map's rooms is swept; an entry
    the old scan would have matched but the closed set cannot re-derive is
    REPORTED as an orphan_candidate and left untouched — never delete what
    cannot be re-derived.
    """
    from homeassistant.helpers import entity_registry as er
    setup_map(manager, _VAC, _MAP, count=2)
    reg = er.async_get(hass)
    prefix = f"{_VAC.replace('.', '_')}_{_MAP}_"
    # a GENUINE straggler: room 2's enabled switch, reconstructible
    genuine = reg.async_get_or_create(
        "switch", DOMAIN, f"{prefix}2_enabled",
        suggested_object_id="alfred_room2_enabled_stale")
    # a NON-reconstructible stray (old id scheme / unknown provenance)
    stray = reg.async_get_or_create(
        "sensor", DOMAIN, f"{prefix}roomhist_stale",
        suggested_object_id="alfred_stale_roomhist")
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="confirm")
    assert result["status"] == "success"
    assert reg.async_get(genuine.entity_id) is None      # reconstructible: swept
    assert reg.async_get(stray.entity_id) is not None    # unknown: preserved
    orphans = result["data"]["orphan_candidates"]
    assert [o["unique_id"] for o in orphans] == [f"{prefix}roomhist_stale"]


# ---------------------------------------------------------------------------
# [SD-11] An empty bucket EXISTS — "already_done" was a lie about it
# ---------------------------------------------------------------------------

async def test_sd11_an_empty_bucket_is_deletable(hass, manager):
    """[SD-11] THE RED INPUT: a phantom map, measured on a live install.

    `ensure_map_bucket` mints a durable nine-key bucket from any caller-supplied
    map_id, and `delete_map` refused to remove one that held no rooms -- it answered
    `already_done / map_not_found` while the key was still sitting in `maps`,
    `run_profiles` and `room_rule_status`. Easy to create, impossible to delete, with
    no supported route out: the maintainer had to edit .storage by hand.

    `already_done` must mean nothing remains. It did not.

    ABLATION: restore `or not bucket.get("rooms")` to the guard and this goes red.
    """
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket

    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    phantom = "Home (ID: 12)"

    # TWO real maps, so `only_map` protection cannot fire and this test measures the
    # empty-bucket guard rather than the confirmation ladder. `imported_map_ids` counts
    # buckets WITH rooms, so one real map would still trip `len <= 1`.
    setup_map(manager, _VAC, _MAP)
    setup_map(manager, _VAC, _MAP2)

    # Create the phantom exactly the way the defect did.
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=phantom)
    # ...and the siblings that rode along with it on the real install.
    manager.data.setdefault("run_profiles", {}).setdefault(_VAC, {})[phantom] = {}
    manager.data.setdefault("room_rule_status", {}).setdefault(_VAC, {})[phantom] = {}

    assert phantom in manager.data["maps"][_VAC], "fixture did not create the phantom"
    assert not manager.data["maps"][_VAC][phantom].get("rooms"), "must be EMPTY to bite"

    from custom_components.eufy_vacuum.setup.protection import evaluate_map_protection
    _prot = evaluate_map_protection(manager, vacuum_entity_id=_VAC, map_id=phantom)
    assert _prot["protection_level"] == "normal", (
        f"an empty phantom beside two real maps should need no confirmation; "
        f"reasons={_prot['reasons']}"
    )

    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=phantom)

    assert result["status"] == "success", (
        f"an empty bucket that EXISTS must be deletable, got {result['status']!r} "
        f"/ {result.get('code')!r}"
    )
    assert phantom not in manager.data["maps"].get(_VAC, {}), "bucket survived the delete"
    for store in ("run_profiles", "room_rule_status"):
        assert phantom not in manager.data.get(store, {}).get(_VAC, {}), (
            f"{store} still carries the phantom; remove_map must clear every "
            "PER_MAP_STORE, not just the bucket"
        )


async def test_sd11b_a_genuinely_absent_map_still_answers_already_done(hass, manager):
    """[SD-11b] The other half of the split, so [SD-11] cannot be satisfied by making
    delete_map claim success for anything. A map with NO bucket is genuinely nothing to
    do, and must keep saying so."""
    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id="never-existed")
    assert result["status"] == "already_done"
    assert result["code"] == "map_not_found"


async def test_sd11c_the_published_recipe_actually_deletes_it(hass, manager):
    """[SD-11c] The release notes hand the user a literal call. This is that call, on
    the install shape the notes are addressed to.

    [SD-11] deliberately stages TWO real maps so it measures the empty-bucket guard
    instead of the confirmation ladder. That makes it the WRONG witness for the
    documented recipe, because the shape this bug actually produces is ONE real map
    plus the leftover -- and there `only_map` fires, the delete returns
    `requires_confirmation`, and nothing is removed. A user following notes written
    without the token would conclude the fix did not ship.

    So this asserts the failure first, then the documented remedy, in the same test:
    without `confirmation_token` nothing is deleted; with it the leftover goes.

    ABLATION: drop `confirmation_token` from the second call and this goes red.
    """
    from custom_components.eufy_vacuum.maps.map_manager import ensure_map_bucket

    manager.ensure_vacuum_record(vacuum_entity_id=_VAC)
    phantom = "Home (ID: 12)"
    setup_map(manager, _VAC, _MAP)          # ONE real map -- the documented shape
    ensure_map_bucket(data=manager.data, vacuum_entity_id=_VAC, map_id=phantom)

    # Without the token: refused, and the map survives. This is what the first draft
    # of the notes would have produced for almost every affected user.
    first = await delete_map(hass, vacuum_entity_id=_VAC, map_id=phantom)
    assert first["status"] == "requires_confirmation", first
    assert phantom in manager.data["maps"][_VAC], "refused but deleted anyway"

    # With it -- exactly what the notes print, a quoted string (the schema is cv.string).
    second = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=phantom, confirmation_token="yes",
    )
    assert second["status"] == "success", (
        f"the recipe published in the release notes did not work: {second}"
    )
    assert phantom not in manager.data["maps"].get(_VAC, {})
    assert _MAP in manager.data["maps"][_VAC], "the REAL map was taken with it"
