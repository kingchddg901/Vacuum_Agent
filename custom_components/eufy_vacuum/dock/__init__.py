"""Dock subsystem for the Eufy Vacuum integration.

Exposes:
- DockManager — owns dock action dispatch (wash/dry/empty/stop-dry),
  dock action status gating, dock event recording, and event counters.
"""

from __future__ import annotations

from .manager import DockManager

__all__ = ["DockManager"]
