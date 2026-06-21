"""Job subsystem for the Eufy Vacuum integration.

Exposes:
- ActiveJobTracker — active-job state tracking, timing rollover, and
  transition-room detection.  Constructed inside EufyVacuumManager after
  storage is loaded.
- PhaseRunner — strict-order (sequenced) phase execution: the per-phase
  watchdog (settle/dispatch/verify/retry) + per-phase timing capture.

The existing job_monitor.py module (lifecycle detection, start-blocker
helpers) is unchanged and continues to be importable directly.
"""

from __future__ import annotations

from .active_job import ActiveJobTracker
from .phase_runner import PhaseRunner

__all__ = ["ActiveJobTracker", "PhaseRunner"]
