"""Tests for core/storage.py — EufyVacuumStorage HA Store wrapper.

Coverage targets
----------------
[ST-1]  async_load with empty store → full default skeleton.
[ST-2]  async_save then async_load round-trips persisted data.
[ST-3]  async_load backfills the error_tracker section on pre-existing data.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.core.storage import EufyVacuumStorage


async def test_load_empty_defaults(hass):
    """[ST-1]"""
    store = EufyVacuumStorage(hass)
    data = await store.async_load()
    for key in (
        "vacuums", "maps", "theme", "analytics", "maintenance",
        "dock_events", "onboarding", "error_tracker",
    ):
        assert key in data
    assert data["theme"]["default_theme_id"] is None


async def test_save_load_roundtrip(hass):
    """[ST-2]"""
    store = EufyVacuumStorage(hass)
    await store.async_save({"vacuums": {"vacuum.alfred": {"x": 1}}})
    data = await store.async_load()
    assert data["vacuums"]["vacuum.alfred"]["x"] == 1


async def test_load_backfills_error_tracker(hass):
    """[ST-3] data written before the error_tracker section gets it backfilled."""
    store = EufyVacuumStorage(hass)
    # Persist a payload that lacks error_tracker (pre-migration shape).
    await store.async_save({"vacuums": {}, "maps": {}})
    data = await store.async_load()
    assert data["error_tracker"] == {}
