"""Maintenance subsystem for the Eufy Vacuum integration.

Exposes:
- MaintenanceManager — owns upkeep model metadata, replacement entity
  discovery, maintenance reset snapshots, remaining-hours calculations,
  and the upkeep snapshot compositor.  Constructed inside
  EufyVacuumManager after storage is loaded.
- maintenance_status / replacement_status — pure-function status
  bucket helpers also used by sensors and the services layer.
"""

from __future__ import annotations

from .manager import MaintenanceManager, maintenance_status, replacement_status

__all__ = [
    "MaintenanceManager",
    "maintenance_status",
    "replacement_status",
]
