"""Phase 7 integration tests — setup/delete.py (delete_map workflow).

Coverage targets
----------------
[SD-1]  No manager → error + code=manager_unavailable.
[SD-2]  Map not found / no rooms → already_done + code=map_not_found.
[SD-3]  Elevated-protection map without token → requires_confirmation.
[SD-4]  Elevated-protection map with any truthy token → success.
[SD-5]  High-protection map (2+ reasons) without token → requires_confirmation
        with code=typed_confirmation_required.
[SD-6]  High-protection map with wrong token → blocked + code=confirmation_mismatch.
[SD-7]  High-protection map with correct token → success.
[SD-8]  Success removes the map bucket from manager.data.
[SD-9]  Success with no remaining maps → warning present and next_actions includes
        import_active_map.
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
    """[SD-5] High-protection map (2+ reasons) without token → typed_confirmation_required."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)  # adds has_learning_data → 2nd reason → high
    result = await delete_map(hass, vacuum_entity_id=_VAC, map_id=_MAP)
    assert result["status"] == "requires_confirmation"
    assert result["code"] == "typed_confirmation_required"


# ---------------------------------------------------------------------------
# [SD-6] High protection — wrong token
# ---------------------------------------------------------------------------

async def test_delete_map_high_protection_wrong_token_returns_blocked(hass, manager):
    """[SD-6] High-protection map with wrong confirmation token → blocked."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token="wrong name"
    )
    assert result["status"] == "blocked"
    assert result["code"] == "confirmation_mismatch"


# ---------------------------------------------------------------------------
# [SD-7] High protection — correct token
# ---------------------------------------------------------------------------

async def test_delete_map_high_protection_correct_token_returns_success(hass, manager):
    """[SD-7] High-protection map with correct token (map display name) → success."""
    setup_map(manager, _VAC, _MAP, count=2)
    _add_history(manager, _VAC, _MAP)
    # Default display name is "Map {map_id}" when no metadata is set.
    result = await delete_map(
        hass, vacuum_entity_id=_VAC, map_id=_MAP, confirmation_token=f"Map {_MAP}"
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
