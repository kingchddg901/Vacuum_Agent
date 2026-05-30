"""Maintenance subsystem for the Eufy Vacuum integration.

Exposes:
- MaintenanceManager — owns maintenance state, reset snapshots, and
  remaining-hours calculations.  Constructed inside EufyVacuumManager
  after storage is loaded.
- maintenance_status / replacement_status — pure-function status
  bucket helpers also used by the upkeep snapshot composer in
  core/manager.py.
"""

from __future__ import annotations

from .manager import MaintenanceManager, maintenance_status, replacement_status

__all__ = [
    "MaintenanceManager",
    "maintenance_status",
    "replacement_status",
]
