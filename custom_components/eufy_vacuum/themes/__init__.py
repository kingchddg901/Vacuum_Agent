"""Theme subsystem for the Eufy Vacuum integration.

Exposes:
- ThemeManager — owns theme library CRUD, per-vacuum draft state, and
  update callbacks.  Constructed inside EufyVacuumManager after storage
  is loaded; receives a reference to the root data dict so it reads/writes
  data["theme"] directly.
- async_register_theme_services / async_unregister_theme_services — HA
  service registration, absorbed from the old theme_services.py module.
"""

from __future__ import annotations

from .manager import ThemeManager
from .services import async_register_theme_services, async_unregister_theme_services

__all__ = [
    "ThemeManager",
    "async_register_theme_services",
    "async_unregister_theme_services",
]
