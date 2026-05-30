"""Job subsystem for the Eufy Vacuum integration.

Exposes:
- ActiveJobTracker — active-job state tracking, timing rollover, and
  transition-room detection.  Constructed inside EufyVacuumManager after
  storage is loaded.

The existing job_monitor.py module (lifecycle detection, start-blocker
helpers) is unchanged and continues to be importable directly.
"""

from __future__ import annotations

from .active_job import ActiveJobTracker

__all__ = ["ActiveJobTracker"]
