"""Profiles subsystem for the Eufy Vacuum integration.

Exposes:
- ProfileManager — owns room-profile and run-profile CRUD.
  Constructed inside EufyVacuumManager after storage is loaded.

The existing room_profiles.py module (built-in presets, normalize helpers,
resolve logic) is unchanged and continues to be importable directly via
profiles.room_profiles.
"""

from __future__ import annotations

from .manager import ProfileManager

__all__ = ["ProfileManager"]
