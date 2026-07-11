"""Constants owned by the learning package.

These live here — not in ``core.manager`` — so the learning engine stays
self-contained and importable without a ``core.manager`` import cycle. Previously
``external_run.py`` imported them from ``core.manager`` at module top, which forced
``learning/__init__.py`` to defer the ``ExternalRunManager`` import via ``__getattr__``;
owning them here removes both. See docs/dev/10-learning-system.md §9.3.
"""

from __future__ import annotations

# Grace window before an app-started (external) run is finalized once the robot
# reaches the dock: it may be docking MID-run (mop prewash, recharge) and about to
# resume. If it resumes within this window the run stays one record (the dock
# becomes a cleaning_time plateau the segmenter splits into a room boundary); if it
# stays docked, the timer finalizes. Sized just above the observed vacuum->mop
# prewash dock (~3.5 min end-to-end in HA) so a mixed-mode multi-room run merges; a
# recharge longer than this still fragments. Tune as needed. See
# maybe_handle_external_run.
EXTERNAL_FINALIZE_GRACE_S = 300  # 5 minutes

# Safety cap on how many times the grace re-checks a still-docked external run that
# task_status reports as mid-run (washing / emptying / recharging). 8 x 5 min ~= 40
# min — well past any real station cycle — then we finalize regardless.
EXTERNAL_GRACE_MAX_RECHECKS = 8
