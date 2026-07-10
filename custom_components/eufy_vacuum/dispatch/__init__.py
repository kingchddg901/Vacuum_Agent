"""Send-side dispatch subsystem for the Eufy Vacuum integration.

Exposes:
- DispatchManager — send-side wire dispatch: turning a resolved clean payload into
  the adapter's on-wire service envelope and pushing it to the vacuum (room clean,
  ad-hoc zone clean, live-id re-resolution, and global fan/mop pre-calls).
  Constructed inside EufyVacuumManager alongside the other subsystems.
"""

from __future__ import annotations

from .manager import DispatchManager

__all__ = ["DispatchManager"]
