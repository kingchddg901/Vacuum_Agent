"""Pluggable room-attribution engines — recover which rooms an UNDISPATCHED run cleaned.

Mirrors the job-segmenter / dispatch-engine pattern
(``learning/job_segmenter_engines.py``, ``queue/dispatch_engines.py``): each brand
registers an attributor under a string name in ``_ROOM_ATTRIBUTION_ENGINES`` and the
adapter selects one via ``room_attribution.engine`` in its config.

WHAT THIS IS FOR. An EXTERNAL (app-started) clean carries no dispatched queue, so the
integration cannot anchor to known targets — today it leans on the counter-plateau
segmenter + a manual room-set step in the external-review wizard. This engine recovers
the cleaned-room SET from a per-tick pose time-series, so the wizard can open
already-answered. It is a DIFFERENT axis from the job segmenter: the segmenter owns
*time/area* boundaries; this owns *which managed room* each segment is.

EUFY ENGINE (``eufy_anchor_winding_v1``). Validated on 3 deliberately-adversarial
external runs (9/9 cleaned-room calls; see ``docs/dev/eufy-native-transition.md`` and
``scratch-external-estimator/room_attribution.py`` — the pure prototype this ports
verbatim). The rule, per contiguous ``current_room`` run:
  1. Segment the run by ``current_room`` into contiguous runs.
  2. Drop TRANSIT by path-winding — a straight pass-through (winding < ~1.5).
  3. Cleaned-vs-parked-dock by SWEPT AREA — the ``cleaning_area`` delta over the
     room's windows. A wash/park sweeps ~0 m²; a clean sweeps real area. This is the
     ONLY robust clean-vs-dock separator: the anchor-only signals (dwell + spread +
     winding) cannot tell a jittering parked dock from a clean (a long parked dock
     sits inside the cleaned cluster). When ``cleaning_area`` is absent the engine
     degrades to an anchor-only fallback (``mode="anchor_only"``) that is best-effort
     and may false-positive a parked dock — callers gate on ``mode``.

POLICIES copied from the sibling seams on purpose:
  - **Eufy fallback, not noop.** ``get_room_attribution_engine`` falls back to the
    Eufy engine for an absent/unknown name (the historical default is Eufy).
    ``NoopRoomAttributor`` stays registered for a future brand that emits no usable
    pose stream, but it is **not** the fallback.
  - **DEFAULT_TUNING by reference.** The three thresholds live as module constants;
    ``DEFAULT_TUNING`` references them so the engine and the documented rule can never
    drift.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Protocol

_LOGGER = logging.getLogger(__name__)

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover - py<3.8 shim, unused on HA's runtime
    from typing_extensions import TypedDict  # type: ignore[assignment]


# =============================================================================
# Canonical cross-engine contracts.
# =============================================================================


class PoseSample(TypedDict, total=False):
    """One per-tick pose row the run-active sampler records (W5b) and an engine reads.

    ``current_room`` is the MANAGED room id (``map_source.current_room_for_pixel``). The
    SAMPLER records ``None`` for both ``current_room`` and ``anchor`` while the robot is
    DOCKED — the fork otherwise anchors a docked robot to the dock, yielding the dock's
    room id, which would false-positive a parked dock in anchor-only mode. ``current_room``
    is also ``None`` genuinely while off-raster in transit. Those ``None`` ticks MUST be
    recorded, not dropped: the parked-dock exclusion relies on them in anchor-only mode
    (robust mode also excludes a parked dock via its ~0 swept area). ``cleaning_area`` is
    cumulative swept m² (``None`` when unavailable → anchor-only mode).
    """

    t: str
    current_room: int | None
    anchor: list[float] | None
    cleaning_area: float | None
    heading: float | None


class RoomAttributionResult(TypedDict):
    """Output of ``attribute`` — the cleaned-room SET plus per-room evidence + mode."""

    cleaned: set[int]
    verdicts: dict[Any, tuple[str, str]]
    per_room: dict[int, dict[str, float]]
    mode: str  # "robust" (swept-area) | "anchor_only"


# =============================================================================
# Protocol.
# =============================================================================


class RoomAttributionEngine(Protocol):
    """One pluggable room attributor. Stateless from the framework's perspective.

    ``tuning`` is the engine's tuning dict (the adapter ``room_attribution.tuning``
    block merged over the engine's ``DEFAULT_TUNING``); ``None`` means defaults.
    """

    engine_name: str

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        """Return a list of issue strings; empty list = tuning is valid."""
        ...

    def attribute(
        self, pose_samples: list[dict[str, Any]], *, tuning: dict[str, Any] | None = None
    ) -> RoomAttributionResult:
        """Recover which managed rooms the run cleaned from its pose time-series."""
        ...


# =============================================================================
# Eufy engine — anchor + winding + swept-area; ports the validated prototype.
# =============================================================================

# The single in-code source of these three numbers for the Eufy engine; DEFAULT_TUNING
# references them so they can never drift from the documented + tested rule.
WIND_TRANSIT = 1.5        # winding < this => straight pass => TRANSIT (transit ~1.0-1.22;
                          #                                            cleaned >= ~4.9).
DWELL_MIN_TICKS = 12      # anchor-only fallback floor, measured in TICKS (sample count), so it
                          # is cadence-INDEPENDENT — a brand tunes it to ITS own sampler via the
                          # adapter (a straight transit runs < ~9 ticks; 12 ≈ 24 s at a 2 s cadence).
SWEPT_AREA_MIN_M2 = 0.5   # robust: a clean sweeps >= this; a wash/park sweeps ~0 m².


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _segment_by_room(pose_samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run-length-encode the stream into contiguous ``current_room`` runs."""
    runs: list[dict[str, Any]] = []
    for s in pose_samples:
        room = s.get("current_room")
        if runs and runs[-1]["room"] == room:
            runs[-1]["samples"].append(s)
        else:
            runs.append({"room": room, "samples": [s]})
    return runs


def _run_metrics(run: dict[str, Any], interval_s: float) -> dict[str, Any]:
    """Per-run metrics (dwell, anchor spread, path-winding, bbox area). Ports the
    prototype's ``run_metrics`` — anchors that are ``None`` are skipped."""
    samples = run["samples"]
    n = len(samples)
    m: dict[str, Any] = {
        "room": run["room"], "n": n, "dwell_s": n * interval_s,
        "spread": 0.0, "path_len": 0.0, "net_disp": 0.0, "winding": 0.0, "bbox_area": 0.0,
    }
    pts = [tuple(s["anchor"]) for s in samples if s.get("anchor")]
    if not pts:
        return m
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m["bbox_area"] = (max(xs) - min(xs)) * (max(ys) - min(ys))
    cx, cy = sum(xs) / len(pts), sum(ys) / len(pts)
    m["spread"] = math.sqrt(sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in pts) / len(pts))
    path = sum(_dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))
    disp = _dist(pts[0], pts[-1])
    m["path_len"], m["net_disp"] = path, disp
    m["winding"] = (path / disp) if disp > 1e-4 else (999.0 if path > 1e-3 else 0.0)
    return m


def _best_run_by_room(run_metric_list: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    """Aggregate to per-room BEST run (max spread = strongest clean-evidence run).
    A wash/park run never dilutes or fakes a clean — we take the best, not the total."""
    by_room: dict[Any, dict[str, Any]] = {}
    for m in run_metric_list:
        cur = by_room.get(m["room"])
        if cur is None or m["spread"] > cur["spread"]:
            by_room[m["room"]] = m
    return by_room


def _swept_area_by_room(runs: list[dict[str, Any]]) -> dict[Any, float] | None:
    """Per-room swept m² from the ``cleaning_area`` timeline — the robust clean-vs-park
    separator. A clean run's cleaning_area RISES; a wash/park/transit run is flat (~0).

    Sum the POSITIVE per-tick increments within each room run (NOT last-minus-first), so a
    NON-MONOTONIC counter is handled. Some brands' cleaning_area resets/drops mid-run — observed
    live on Eufy (Alfred), where it fell 21.5→10.8 as the sensor re-baselined at the real clean
    start, then climbed. A drop is a RESET, not negative cleaning: clamping each tick's delta at 0
    treats the drop as a new baseline and still credits the true rises both before AND after it
    (last-minus-first would silently undercount by the drop). For a clean monotonic counter (e.g.
    Roborock's, 0→4.4) this is identical to last-minus-first. Returns ``None`` when no sample
    carries ``cleaning_area`` → caller runs anchor-only mode."""
    if not any(s.get("cleaning_area") is not None for run in runs for s in run["samples"]):
        return None
    by_room: dict[Any, float] = {}
    for run in runs:
        vals = [s["cleaning_area"] for s in run["samples"] if s.get("cleaning_area") is not None]
        swept = sum(max(0.0, vals[i] - vals[i - 1]) for i in range(1, len(vals)))
        by_room[run["room"]] = by_room.get(run["room"], 0.0) + swept
    return by_room


def _classify(
    per_room_best: dict[Any, dict[str, Any]],
    swept_area_by_room: dict[Any, float] | None,
    *,
    wind_transit: float,
    dwell_min_ticks: float,
    swept_area_min_m2: float,
) -> RoomAttributionResult:
    """Ports the prototype's ``classify``, thresholds parameterized for tuning."""
    cleaned: set[int] = set()
    verdicts: dict[Any, tuple[str, str]] = {}
    per_room: dict[int, dict[str, float]] = {}
    for rid, m in per_room_best.items():
        if rid is not None:
            per_room[rid] = {
                "dwell_s": m["dwell_s"], "spread": m["spread"],
                "winding": m["winding"], "bbox_area": m["bbox_area"],
                "swept_area_m2": (swept_area_by_room or {}).get(rid, 0.0),
            }
        if rid is None:
            verdicts[rid] = ("transit", "no room (transit cell)")
            continue
        if swept_area_by_room is not None:
            # ROBUST: swept area is THIS module's authoritative clean signal — gate
            # "cleaned" on it directly. The winding short-circuit must NOT pre-empt it:
            # a room can have a high-spread transit pass AND a real clean, and the
            # best (max-spread) run may be the transit, so winding-dropping first would
            # silently drop a genuinely-cleaned room. winding is used only to LABEL the
            # not-cleaned remainder (transit vs parked dock).
            a = float(swept_area_by_room.get(rid, 0.0))
            if a >= swept_area_min_m2:
                cleaned.add(rid)
                verdicts[rid] = ("cleaned", f"swept {a:.1f} m^2")
            elif m["winding"] < wind_transit:
                verdicts[rid] = ("transit", f"straight pass (winding {m['winding']:.2f}), ~{a:.1f} m^2")
            else:
                verdicts[rid] = ("parked/dock", f"swept ~{a:.1f} m^2 (< {swept_area_min_m2})")
        else:
            # ANCHOR-ONLY fallback (no swept area): winding drops a straight transit, then
            # dwell (in TICKS) gates. This path can false-positive a long jittering parked dock
            # — it's best-effort; prefer robust mode (callers gate on `mode`).
            if m["winding"] < wind_transit:
                verdicts[rid] = ("transit", f"straight pass (winding {m['winding']:.2f} < {wind_transit})")
            elif m["n"] >= dwell_min_ticks:
                cleaned.add(rid)
                verdicts[rid] = ("cleaned?", f"dwell {m['n']} ticks + winding {m['winding']:.1f} "
                                             f"(anchor-only — cannot exclude a jittering parked dock)")
            else:
                verdicts[rid] = ("transit", f"short dwell {m['n']} ticks")
    return {
        "cleaned": cleaned, "verdicts": verdicts, "per_room": per_room,
        "mode": "robust" if swept_area_by_room is not None else "anchor_only",
    }


class EufyAnchorWindingAttributor:
    """Anchor + winding + swept-area room attribution for an external run.

    Ports ``scratch-external-estimator/room_attribution.py`` verbatim (thresholds
    parameterized for tuning) and adds the per-room swept-area derivation from the
    live ``cleaning_area`` timeline (the prototype received it pre-aligned)."""

    engine_name = "eufy_anchor_winding_v1"

    # BY REFERENCE to the module constants above — do NOT retype the literals.
    DEFAULT_TUNING: dict[str, float] = {
        "wind_transit": WIND_TRANSIT,
        "dwell_min_ticks": DWELL_MIN_TICKS,
        "swept_area_min_m2": SWEPT_AREA_MIN_M2,
        # Sampler cadence — the SINGLE source the run-active pose sampler also reads
        # (listeners/pose_sampler.py), and what converts ticks→seconds for the dwell_s
        # display + the pose-only stand-alone timing. The dwell DECISION is now in ticks,
        # so it no longer silently depends on this matching the sampler.
        "interval_s": 2.0,
    }

    _KNOWN_TUNING_KEYS: frozenset[str] = frozenset(DEFAULT_TUNING)

    @classmethod
    def _resolve(cls, tuning: dict[str, Any] | None) -> dict[str, float]:
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
            return ["room_attribution.tuning must be a dict"]
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

    def attribute(
        self, pose_samples: list[dict[str, Any]], *, tuning: dict[str, Any] | None = None
    ) -> RoomAttributionResult:
        t = self._resolve(tuning)
        runs = _segment_by_room(pose_samples or [])
        metrics = [_run_metrics(r, t["interval_s"]) for r in runs]
        per_room_best = _best_run_by_room(metrics)
        swept = _swept_area_by_room(runs)
        return _classify(
            per_room_best, swept,
            wind_transit=t["wind_transit"],
            dwell_min_ticks=t["dwell_min_ticks"],
            swept_area_min_m2=t["swept_area_min_m2"],
        )


# =============================================================================
# Noop fallback — for a future brand with no usable pose stream.
# =============================================================================


class NoopRoomAttributor:
    """Empty result. For an adapter that emits no per-tick pose/current_room stream;
    attribution returns nothing, so the wizard stays fully manual. Registered for
    completeness; it is **not** the fallback (an absent adapter falls back to Eufy)."""

    engine_name = "noop_room_attribution"

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        if not isinstance(tuning, dict):
            return ["room_attribution.tuning must be a dict"]
        if tuning:
            return [f"{self.engine_name}: tuning is ignored; unexpected keys: {sorted(tuning)}"]
        return []

    def attribute(
        self, pose_samples: list[dict[str, Any]], *, tuning: dict[str, Any] | None = None
    ) -> RoomAttributionResult:
        # "anchor_only" matches the Eufy engine's no-usable-input labeling (it ran no
        # swept-area analysis), so callers gating on `mode` treat both the same.
        return {"cleaned": set(), "verdicts": {}, "per_room": {}, "mode": "anchor_only"}


# =============================================================================
# Registry.
# =============================================================================

_ROOM_ATTRIBUTION_ENGINES: dict[str, RoomAttributionEngine] = {
    "eufy_anchor_winding_v1": EufyAnchorWindingAttributor(),
    "noop_room_attribution": NoopRoomAttributor(),
}

_FALLBACK_ROOM_ENGINE = "eufy_anchor_winding_v1"  # Eufy fallback, NOT noop


def get_room_attribution_engine(name: str | None) -> RoomAttributionEngine:
    """Return the engine registered under ``name``; fall back to the Eufy engine for an
    absent (legacy default) or unknown name. An unknown non-empty name is warned."""
    if not name:
        return _ROOM_ATTRIBUTION_ENGINES[_FALLBACK_ROOM_ENGINE]
    engine = _ROOM_ATTRIBUTION_ENGINES.get(name)
    if engine is None:
        _LOGGER.warning(
            "Unknown room_attribution engine %r; falling back to %r. "
            "Check adapter_config.room_attribution.engine.",
            name, _FALLBACK_ROOM_ENGINE,
        )
        return _ROOM_ATTRIBUTION_ENGINES[_FALLBACK_ROOM_ENGINE]
    return engine


def known_room_attribution_names() -> list[str]:
    """Return the set of engine names ``_validate_adapter`` should accept."""
    return list(_ROOM_ATTRIBUTION_ENGINES)
