"""Optional learning system for the Eufy Vacuum integration."""

from __future__ import annotations

from .manager import LearningManager

__all__ = ["LearningManager"]


def __getattr__(name: str):
    # Lazily expose ExternalRunManager without importing external_run at package-load
    # time. external_run.py imports two constants from ..core.manager at module top;
    # deferring this import keeps the learning package importable during core.manager's
    # own module load (no import cycle), while callers still use `from ..learning import
    # ExternalRunManager` (resolved on first access, e.g. in EufyVacuumManager.__init__).
    if name == "ExternalRunManager":
        from .external_run import ExternalRunManager

        return ExternalRunManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")