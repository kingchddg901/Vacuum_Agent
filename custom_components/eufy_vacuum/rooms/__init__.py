"""Room discovery and managed room configuration for the Eufy Vacuum integration.

Exposes:
- AccessGraphManager — room access graph validation and automation rule evaluation.
  Constructed inside EufyVacuumManager after storage is loaded.
- RoomMapManager — discover, save, read, remove, and rebuild room/map CRUD.
  Constructed inside EufyVacuumManager after storage is loaded.

The existing room_discovery.py, room_manager.py, and utils.py modules are
unchanged and continue to be importable directly.
"""

from __future__ import annotations

from .access_graph import AccessGraphManager
from .room_crud import RoomMapManager

__all__ = ["AccessGraphManager", "RoomMapManager"]
