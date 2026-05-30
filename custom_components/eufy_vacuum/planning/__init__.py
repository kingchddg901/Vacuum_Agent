"""Run planning and water estimation for the Eufy Vacuum integration.

Exposes:
- RunPlanManager — water model helpers, job water estimation, and effective
  start-plan construction (blocker / modifier rule evaluation, access-graph
  fan-out, preflight snapshots).  Constructed inside EufyVacuumManager after
  storage is loaded.
"""

from __future__ import annotations

from .run_plan import RunPlanManager

__all__ = ["RunPlanManager"]
