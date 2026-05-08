"""Battery health subsystem for the Eufy Vacuum integration.

Exposes:
- BatteryHealthManager — accumulates samples, sessions, and cumulative cycles.
- Sensor classes — surface the manager's metrics as HA sensors.
"""

from __future__ import annotations

from .manager import BatteryHealthManager

__all__ = ["BatteryHealthManager"]
