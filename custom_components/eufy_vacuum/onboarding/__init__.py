"""Onboarding subsystem for the Eufy Vacuum integration.

Exposes:
- OnboardingManager — owns per-map room-discovery and floor-type
  confirmation state.  Constructed inside EufyVacuumManager after
  storage is loaded.
"""

from __future__ import annotations

from .manager import OnboardingManager

__all__ = ["OnboardingManager"]
