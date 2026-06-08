"""Pluggable job/run segmenter engines — brand-specific room-boundary detection.

Mirrors the dispatch-engine pattern (``queue/dispatch_engines.py``): each brand
registers a job segmenter under a string name in ``_JOB_SEGMENTER_ENGINES``, and
the adapter selects one via ``job_segmenter.engine`` in its config. The engine owns
the *brand-specific* stages of turning a counter-sample stream into ordered
per-room segments:

  - Eufy → counter-plateau detection over ``cleaning_time``/``cleaning_area``
    (no geometry; coordinates drift). A future brand with native per-room
    telemetry implements ``find_candidates`` by reading native room-change events
    and returns the SAME ``JobBoundaryCandidate``/``JobSegment`` shape, so the
    three consumers (live rollover, external-run ingest, learned history) never
    change.

**What the engine owns vs. what the framework owns.** Unlike the map seam (where
the engine owns the whole production), the job pipeline is three stages —
``find_candidates → select_active → build_segments`` — because the external-review
wizard re-*selects* boundaries (by room count or per-boundary toggle) from a frozen
candidate pool *without re-detecting*. ``select_active`` is pure ranking/filtering
over the candidate *shape* (it reads only ``kind``/``confident``/``strength``/``id``)
and is therefore **brand-agnostic** — it stays a framework function
(``counter_segmentation.select_active``) so the wizard's count/toggle logic is
uniform across brands. The engine owns the two brand-specific stages
(``find_candidates``, ``build_segments``) plus the legacy convenience composition
(``segment_legacy``). The ``JobBoundaryCandidate`` TypedDict is the cross-engine
contract that makes ``select_active``'s genericity real.

Two policies copied from ``dispatch_engines`` on purpose, and one non-mirror of the
map seam:

  - **Eufy fallback, not noop.** ``get_job_segmenter_engine`` falls back to the
    Eufy engine for an absent/unknown name, because the framework's historical
    default (no adapter registered) is Eufy counter segmentation, and live
    rollover + learned history must keep working byte-for-byte in that case. The
    map seam falls back to a *noop* — that would silently stop live rollover here.
    ``NoopJobSegmenter`` stays registered for a future brand that genuinely emits
    no segmentable signal, but it is **not** the fallback.
  - **Byte-identical by delegation.** ``EufyCounterSegmenter`` delegates verbatim
    to the existing ``counter_segmentation`` primitives and its ``DEFAULT_TUNING``
    is defined *by reference* to that module's constants, so the Eufy path is
    byte-for-byte identical to the pre-engine code by construction (drift is a
    compile-time impossibility, not a vigilance task). Tests assert
    ``engine == module`` (the ``[JE-7]`` fidelity battery).

The Eufy *kind vocabulary* (``"wash_plateau"``/``"transit"``/``"area_jump"``/``"weak"``)
is produced by ``find_candidates`` and referenced by the Eufy-specific call sites
(the live ``rollover_kinds`` and the legacy ``kinds={"wash_plateau","area_jump"}``
filter). A future brand with a different kind vocabulary supplies its own engine
*and* its own kind literals at those sites — that's the documented extension point;
no kind-vocabulary indirection is built here.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from ..counter_segmentation import (
    _AREA_JUMP_M2,
    _CADENCE_S,
    _GAP_DELAYED_S,
    _GAP_PLATEAU_S,
    _GAP_TRANSIT_S,
    build_segments as _build_segments,
    find_candidates as _find_candidates,
    segment_counters as _segment_counters,
)

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Canonical cross-engine contract.
# =============================================================================
#
# These TypedDicts are the EXACT union field-lists the counter primitives already
# produce (verified against counter_segmentation.find_candidates / build_segments).
# Defining them documents the contract every engine must satisfy; it changes no
# output. Consumers (live rollover, ingest, history) read only these fields, so a
# new engine that produces the same shape needs no consumer changes.

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover - py<3.8 shim, unused on HA's runtime
    from typing_extensions import TypedDict  # type: ignore[assignment]


class JobBoundaryCandidate(TypedDict):
    """One detected room boundary in a run, before selection.

    The fields ``select_active`` ranks/filters on (``id``, ``kind``, ``strength``,
    ``confident``) are the brand-agnostic part of the contract — every engine's
    ``find_candidates`` must populate them.
    """

    id: int
    position: int
    gap_s: float
    area_after_m2: float
    kind: str
    strength: float
    confident: bool
    t: str


class JobSegment(TypedDict):
    """One ordered per-room cleaning bout produced by ``build_segments``."""

    index: int
    boundary_id: int | None
    t_start: str
    t_end: str
    ct_start: float
    ct_end: float
    area_start_m2: float
    area_end_m2: float
    area_delta_m2: float
    time_active_s: float
    time_wall_s: float
    gap_before_s: float
    battery_delta: float | None
    boundary: str
    increment_count: int


# =============================================================================
# Protocol.
# =============================================================================


class JobSegmenter(Protocol):
    """One pluggable job segmenter.

    Stateless from the framework's perspective. ``find_candidates`` and
    ``build_segments`` are the brand-specific stages; ``select_active`` is NOT on
    the engine (it is the brand-agnostic framework function
    ``counter_segmentation.select_active``). ``segment_legacy`` is the
    back-compat one-shot composition used by the live-disabled path and learned
    history — it must stay byte-identical to ``segment_counters``.

    ``tuning`` is the engine's tuning dict (the adapter ``job_segmenter.tuning``
    block merged over the engine's ``DEFAULT_TUNING``); ``None`` means defaults.
    """

    engine_name: str

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        """Return a list of issue strings; empty list = tuning is valid."""
        ...

    def find_candidates(
        self, samples: list[dict[str, Any]], *, tuning: dict[str, Any] | None = None
    ) -> list[JobBoundaryCandidate]:
        """Every detected boundary in the stream, in cleaning order — no discards."""
        ...

    def build_segments(
        self,
        samples: list[dict[str, Any]],
        active_candidates: list[dict[str, Any]],
        *,
        tuning: dict[str, Any] | None = None,
    ) -> list[JobSegment]:
        """The ordered per-room segment dicts for a chosen active boundary set."""
        ...

    def segment_legacy(
        self,
        samples: list[dict[str, Any]],
        *,
        expected_rooms: int | None = None,
        tuning: dict[str, Any] | None = None,
    ) -> list[JobSegment]:
        """Legacy one-shot segmentation (detect → select strongest → build)."""
        ...


# =============================================================================
# Eufy engine — counter-plateau, delegates verbatim.
# =============================================================================


class EufyCounterSegmenter:
    """Counter-plateau segmentation over ``cleaning_time``/``cleaning_area``.

    Wraps ``counter_segmentation``'s primitives unchanged — the original
    implementation — so the Eufy path is byte-for-byte identical to pre-engine
    output. ``DEFAULT_TUNING`` is defined *by reference* to that module's
    constants, so it can never drift from the primitives' own kwarg defaults.
    """

    engine_name = "eufy_counter_v1"

    # The single in-code source of these five numbers for the Eufy engine. BY
    # REFERENCE to counter_segmentation's module constants — do NOT retype the
    # literals here, or the byte-identical guarantee becomes a vigilance task.
    DEFAULT_TUNING: dict[str, float] = {
        "gap_delayed_s": _GAP_DELAYED_S,
        "gap_transit_s": _GAP_TRANSIT_S,
        "gap_plateau_s": _GAP_PLATEAU_S,
        "area_jump_m2": _AREA_JUMP_M2,
        "cadence_s": _CADENCE_S,
    }

    _KNOWN_TUNING_KEYS: frozenset[str] = frozenset(DEFAULT_TUNING)

    @classmethod
    def _resolve(cls, tuning: dict[str, Any] | None) -> dict[str, float]:
        """Merge a (possibly partial) tuning dict over the defaults; ignore unknown
        keys and None values (validate_tuning warns about them separately)."""
        merged = dict(cls.DEFAULT_TUNING)
        if isinstance(tuning, dict):
            for key in cls._KNOWN_TUNING_KEYS:
                value = tuning.get(key)
                if value is not None:
                    merged[key] = float(value)
        return merged

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        if not isinstance(tuning, dict):
            return ["job_segmenter.tuning must be a dict"]

        for key in sorted(set(tuning) - self._KNOWN_TUNING_KEYS):
            issues.append(f"{self.engine_name}: unknown tuning key {key!r}")

        for key in self._KNOWN_TUNING_KEYS:
            if key not in tuning:
                continue
            value = tuning[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                issues.append(
                    f"{self.engine_name}: {key} must be a positive number (got {value!r})"
                )
        return issues

    def find_candidates(
        self, samples: list[dict[str, Any]], *, tuning: dict[str, Any] | None = None
    ) -> list[JobBoundaryCandidate]:
        t = self._resolve(tuning)
        return _find_candidates(
            samples,
            gap_delayed_s=t["gap_delayed_s"],
            gap_transit_s=t["gap_transit_s"],
            gap_plateau_s=t["gap_plateau_s"],
            area_jump_m2=t["area_jump_m2"],
            cadence_s=t["cadence_s"],
        )

    def build_segments(
        self,
        samples: list[dict[str, Any]],
        active_candidates: list[dict[str, Any]],
        *,
        tuning: dict[str, Any] | None = None,
    ) -> list[JobSegment]:
        t = self._resolve(tuning)
        return _build_segments(samples, active_candidates, cadence_s=t["cadence_s"])

    def segment_legacy(
        self,
        samples: list[dict[str, Any]],
        *,
        expected_rooms: int | None = None,
        tuning: dict[str, Any] | None = None,
    ) -> list[JobSegment]:
        # Delegate verbatim to the one back-compat wrapper (it hardcodes the
        # transit collapse + the wash/area_jump kind filter internally — do NOT
        # reimplement that composition here, or learned history would drift).
        t = self._resolve(tuning)
        return _segment_counters(
            samples,
            expected_rooms=expected_rooms,
            cadence_s=t["cadence_s"],
            gap_delayed_s=t["gap_delayed_s"],
            gap_plateau_s=t["gap_plateau_s"],
            area_jump_m2=t["area_jump_m2"],
        )


# =============================================================================
# Noop fallback — for a future brand with no segmentable signal.
# =============================================================================


class NoopJobSegmenter:
    """Empty result.

    For an adapter that emits no counter (or native-transition) signal at all:
    every stage returns ``[]``, so live rollover never advances on segmentation
    and external-run ingest writes no boundaries. Registered for completeness; it
    is **not** the fallback (an absent adapter falls back to the Eufy engine).
    """

    engine_name = "noop_job_fallback"

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        if not isinstance(tuning, dict):
            return ["job_segmenter.tuning must be a dict"]
        if tuning:
            return [f"{self.engine_name}: tuning is ignored; unexpected keys: {sorted(tuning)}"]
        return []

    def find_candidates(
        self, samples: list[dict[str, Any]], *, tuning: dict[str, Any] | None = None
    ) -> list[JobBoundaryCandidate]:
        return []

    def build_segments(
        self,
        samples: list[dict[str, Any]],
        active_candidates: list[dict[str, Any]],
        *,
        tuning: dict[str, Any] | None = None,
    ) -> list[JobSegment]:
        return []

    def segment_legacy(
        self,
        samples: list[dict[str, Any]],
        *,
        expected_rooms: int | None = None,
        tuning: dict[str, Any] | None = None,
    ) -> list[JobSegment]:
        return []


# =============================================================================
# Registry.
# =============================================================================

_JOB_SEGMENTER_ENGINES: dict[str, JobSegmenter] = {
    "eufy_counter_v1": EufyCounterSegmenter(),
    "noop_job_fallback": NoopJobSegmenter(),
}

_FALLBACK_JOB_ENGINE = "eufy_counter_v1"  # Eufy fallback (dispatch-style), NOT noop


def get_job_segmenter_engine(name: str | None) -> JobSegmenter:
    """Return the engine registered under ``name``.

    Falls back to the Eufy engine when ``name`` is absent (the legacy no-adapter
    default) or unknown. An *unknown* (non-empty) name is logged as a warning since
    it signals a misconfigured adapter; an absent name is normal legacy behavior
    and is not warned.
    """
    if not name:
        return _JOB_SEGMENTER_ENGINES[_FALLBACK_JOB_ENGINE]

    engine = _JOB_SEGMENTER_ENGINES.get(name)
    if engine is None:
        _LOGGER.warning(
            "Unknown job_segmenter engine %r; falling back to %r. "
            "Check adapter_config.job_segmenter.engine.",
            name,
            _FALLBACK_JOB_ENGINE,
        )
        return _JOB_SEGMENTER_ENGINES[_FALLBACK_JOB_ENGINE]

    return engine


def known_job_engine_names() -> list[str]:
    """Return the set of engine names ``_validate_adapter`` should accept."""
    return list(_JOB_SEGMENTER_ENGINES)
