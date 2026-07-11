"""Optional learning system for the Eufy Vacuum integration."""

from __future__ import annotations

from .external_run import ExternalRunManager
from .manager import LearningManager

__all__ = ["ExternalRunManager", "LearningManager"]