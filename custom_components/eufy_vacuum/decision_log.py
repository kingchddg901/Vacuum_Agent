"""Decision log — a machine-readable DEBUG record at every decision point.

WHY. A live run makes dozens of decisions and records almost none of them. When
`_segment_group_room_timing` fell back to apportioning on Alfred's
`pj_2026-08-03T17-22-18`, it did so through one of four silent `return None`
paths, and the only way to tell them apart was to not be able to. The flight
recorder (`debug_capture.py`) can only capture what the code emits; a branch that
returns silently is invisible to it no matter how the capture is configured.

NOT ``trace_*``. That prefix already belongs to the pose-path capture modules
(``mapping/trace_capture.py``, ``trace_store.py``, ``trace_segmentation.py``,
``trace_review.py``). This is an unrelated thing and must not be filed with them.

SHAPE — one record per decision, no prose::

    [phase.segment.reject] {"expected":2,"gate":"count","got":3}

A stable bracketed EVENT ID plus compact JSON params, and nothing else. The
event id is the contract and the test anchor; the params carry the values that
discriminate this branch from its siblings. Sentences are deliberately absent:
wording can be rewritten later without touching a single test, which is the whole
point of anchoring on the id.

Event ids are ``<area>.<operation>.<outcome>``, lowercase, dot-separated. An
outcome of ``reject`` / ``skip`` / ``fallback`` means "we did not do the thing";
``ok`` / ``commit`` means we did. Params are primitives — ids, counts, deltas,
short codes — never objects and never user-facing text.

NO i18n, DELIBERATELY. These are maintainer-facing DEBUG records that are never
rendered to a user, so the standing "no string without i18n" rule does not reach
them. Do not "fix" this by routing it through the i18n pipeline; there is no
Python ``t()`` in this codebase and these strings are not user copy.

LEARNING NEVER READS THIS. Decision records skew hard toward failed, degraded and
fallback runs — exactly the population that would poison a learner. The guarantee
is kept structurally rather than by policy: there is no store, no record_type and
no service here. It emits to the logger and stops.

BEST EFFORT. ``emit`` cannot raise. A diagnostic that aborts a live clean is
strictly worse than no diagnostic.

Public surface:
    emit(event_id: str, **params: Any) -> None
"""

from __future__ import annotations

import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: Params are a diagnostic aid, not a payload. A record that outgrows this is a
#: sign the caller is dumping a structure instead of naming a decision.
MAX_PARAMS_CHARS = 800


def _compact(params: dict[str, Any]) -> str:
    """Params as stable, sorted, parseable JSON — never raises.

    ``sort_keys`` so a captured line is diffable across runs, ``default=str`` so
    a stray datetime or Enum degrades to text instead of taking the record down,
    and a hard cap so one careless caller cannot flood the ring.
    """
    try:
        text = json.dumps(
            params, sort_keys=True, separators=(",", ":"), default=str
        )
    except Exception:  # pragma: no cover - defensive; default=str covers ~all
        try:
            text = repr(params)
        except Exception:  # pragma: no cover
            return "{}"
    if len(text) > MAX_PARAMS_CHARS:
        return text[:MAX_PARAMS_CHARS] + "...<elided>"
    return text


def emit(event_id: str, /, **params: Any) -> None:
    """Record one decision. Never raises, never aborts the caller.

    Guarded on ``isEnabledFor`` so the JSON is not built when DEBUG is off —
    these sit on hot paths (per-sample loops, per-phase finalization) and must
    cost nothing when the flight recorder is not running.
    """
    try:
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        _LOGGER.debug("[%s] %s", event_id, _compact(params))
    except Exception:  # pragma: no cover - a diagnostic must never break a run
        pass
