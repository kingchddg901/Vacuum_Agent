"""Pluggable map segmenter engines.

Each engine implements the MapSegmenter Protocol and is registered in
``_SEGMENTER_ENGINES`` under a string name. The adapter selects an engine via
``adapter_config["mapping"]["segmenter_engine"]``.

This module defines:

- The canonical ``SegmentationResult`` shape every engine returns.
- The ``MapSegmenter`` Protocol every engine satisfies.
- ``EufyCVSegmenter`` — wraps the existing Pillow/NumPy/SciPy pipeline.
- ``NoopSegmenter`` — empty result; for adapters that yield no map image.
- ``get_segmenter_engine(name)`` — registry lookup with safe fallback.
- ``known_engine_names()`` — for validator use.

A new vendor adds support by writing a new ``MapSegmenter`` subclass and
registering it under a new string name. The framework's two call sites in
``manager.py`` and ``mapping_services.py`` consume the canonical
``SegmentationResult`` regardless of which engine produced it.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, NotRequired, Protocol, TypedDict

from ..adapters.eufy.segmentor import detect_room_segments, image_runtime_capabilities

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# Type definitions — the canonical SegmentationResult contract.
# =============================================================================
#
# Every engine produces this shape regardless of how it derived the segments.
# Consumers (manager.py, card snapshots) read only CanonicalSegment fields for
# production UI. EnrichedSegment fields are advisory / diagnostic and any
# subset may be absent depending on the engine.


class Bbox(TypedDict):
    """Pixel-space axis-aligned bounding box."""
    x: int
    y: int
    width: int
    height: int


SegmentQuality = Literal["strong", "good", "usable", "poor"]
SegmentationState = Literal["clean", "needs_review", "ambiguous"]
EditReadiness = Literal["ready", "needs_edit", "blocked"]


class CanonicalSegment(TypedDict):
    """Required fields every engine produces for every segment.

    Renderers, room-link UIs, and overlay code must restrict themselves to
    these fields. They are the cross-engine contract.
    """
    segment_id:         str
    polygon_pixel:      list[list[float]]   # [[x, y], ...] in canvas pixel space
    bbox:               Bbox
    area_pixels:        int
    area_percent:       float                # area_pixels / image_area
    center_pixel:       list[float]          # [cx, cy]
    confidence:         float                # 0.0–1.0
    quality:            SegmentQuality
    structural_role:    str                  # "room" | "hallway" | "closet" | "hub" | ...
    segmentation_state: SegmentationState
    edit_readiness:     EditReadiness
    matched_room_id:    str | None           # vendor-supplied room id if available
    matched_room_label: str | None           # vendor-supplied room label if available


class EnrichedSegment(CanonicalSegment, total=False):
    """Engine-specific extras. Consumers must tolerate any subset being absent.

    The CV engine populates most of these; deterministic engines populate
    fewer; the noop engine populates none of them. Use them for diagnostics
    and debug overlays, never for production rendering.
    """
    cluster_index:         int
    point_count_raw:       int
    point_count_simplified: int
    fill_ratio:            float
    compactness:           float
    aspect_ratio:          float
    issues:                list[str]
    suggested_color_bgr:   list[int]
    mean_saturation:       float
    mean_value:            float
    variant_agreement:     float
    variant_support:       str
    local_split_suspicion: bool
    polygon_pct:           list[list[float]]   # bbox-relative %


class ImageDimensions(TypedDict):
    width:  int
    height: int


class SegmentationSummary(TypedDict):
    segment_count:        int
    quality_counts:       dict[str, int]       # {"strong": 8, "good": 2, ...}
    good_or_better_count: int


class SegmentationResult(TypedDict):
    """The contract every MapSegmenter engine returns.

    Lifecycle fields (``available``, ``reason``, ``message``) describe
    whether the engine could run. ``segments`` and ``summary`` describe what
    it produced. ``engine_diagnostics`` is a free-form blob for engine-
    specific data — consumers must never *require* any key in it.
    """
    # Lifecycle
    available:          bool                    # False = engine couldn't run (degraded)
    reason:             str                     # "ready" | "pipeline_unavailable" | "noop" | ...
    message:            str

    # Identity / provenance
    engine:             str                     # the segmenter_engine name that produced this

    # Spatial frame (None if the engine doesn't render to a canvas)
    image:              ImageDimensions | None

    # Output
    segments:           list[EnrichedSegment]
    summary:            SegmentationSummary

    # Engine-specific diagnostic blob — consumers may surface in debug UI
    # but must never *require* any key here.
    engine_diagnostics: NotRequired[dict[str, Any]]


# =============================================================================
# Protocol — what the framework registers in _SEGMENTER_ENGINES.
# =============================================================================


class MapSegmenter(Protocol):
    """One pluggable mapping engine.

    Stateless from the framework's perspective. Engines may cache internally
    but must produce deterministic output for the same (image, tuning, context)
    input.
    """

    engine_name: str   # matches the key in _SEGMENTER_ENGINES

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        """Return a list of issue strings; empty list = tuning is valid."""
        ...

    def segment_map_image(
        self,
        *,
        image_path: str | None,
        tuning: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SegmentationResult:
        """Produce segments.

        ``image_path`` is None for engines that don't read images
        (e.g. ``roborock_deterministic``, which reads the wire payload via
        ``context``). The framework passes both unconditionally; the engine
        uses what it knows.
        """
        ...


# =============================================================================
# Eufy CV engine — wraps the existing detect_room_segments pipeline.
# =============================================================================


class EufyCVSegmenter:
    """Pillow + NumPy + SciPy pipeline.

    Wraps the existing ``detect_room_segments`` function and reshapes its
    output to conform to ``SegmentationResult``. Engine-specific diagnostics
    (pipeline stages, runtime capability flags) are relocated under
    ``engine_diagnostics`` so consumers that don't care about CV internals
    don't have to know they exist.
    """

    engine_name = "eufy_cv_v1"

    # Keys we accept in adapter_config.mapping.segmenter_tuning.
    _KNOWN_TUNING_KEYS: frozenset[str] = frozenset({
        "min_area_pixels",
        "simplify_epsilon",
        "expected_room_count",
        "max_segments",
        "assist_image_path",
        "image_variant",
        "assist_variant",
    })

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        issues: list[str] = []

        if not isinstance(tuning, dict):
            return ["mapping.segmenter_tuning must be a dict"]

        unknown = set(tuning) - self._KNOWN_TUNING_KEYS
        for key in sorted(unknown):
            issues.append(f"{self.engine_name}: unknown tuning key {key!r}")

        if "min_area_pixels" in tuning:
            value = tuning["min_area_pixels"]
            if not isinstance(value, int) or value <= 0:
                issues.append(
                    f"{self.engine_name}: min_area_pixels must be a positive "
                    f"int (got {value!r})"
                )

        if "simplify_epsilon" in tuning:
            value = tuning["simplify_epsilon"]
            if value is not None and not isinstance(value, (int, float)):
                issues.append(
                    f"{self.engine_name}: simplify_epsilon must be a number "
                    f"or None (got {value!r})"
                )
            elif isinstance(value, (int, float)) and value < 0:
                issues.append(
                    f"{self.engine_name}: simplify_epsilon must be non-"
                    f"negative (got {value!r})"
                )

        if "expected_room_count" in tuning:
            value = tuning["expected_room_count"]
            if value is not None and (not isinstance(value, int) or value < 0):
                issues.append(
                    f"{self.engine_name}: expected_room_count must be a non-"
                    f"negative int or None (got {value!r})"
                )

        return issues

    def segment_map_image(
        self,
        *,
        image_path: str | None,
        tuning: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SegmentationResult:
        if not image_path:
            return _engine_unavailable(
                engine=self.engine_name,
                reason="no_image_path",
                message=(
                    f"{self.engine_name} requires an image_path; "
                    "none was supplied."
                ),
            )

        # Pull only known kwargs from tuning. validate_tuning already warned
        # about unknown keys; we read defensively so a stale adapter config
        # can't crash the pipeline.
        kwargs = {
            "image_path":          image_path,
            "expected_room_count": tuning.get("expected_room_count"),
            "max_segments":        tuning.get("max_segments"),
            "min_area_pixels":     int(tuning.get("min_area_pixels", 1200)),
            "simplify_epsilon":    tuning.get("simplify_epsilon"),
            "assist_image_path":   tuning.get("assist_image_path"),
            "image_variant":       tuning.get("image_variant"),
            "assist_variant":      tuning.get("assist_variant"),
        }

        try:
            raw = detect_room_segments(**kwargs)
        except Exception:
            _LOGGER.exception("%s: detect_room_segments raised", self.engine_name)
            return _engine_unavailable(
                engine=self.engine_name,
                reason="engine_exception",
                message=(
                    f"{self.engine_name} raised an exception; "
                    "see logs for traceback."
                ),
            )

        return self._reshape(raw)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reshape(self, raw: dict[str, Any]) -> SegmentationResult:
        """Translate detect_room_segments output -> SegmentationResult."""

        segments = list(raw.get("segments", []))
        summary  = dict(raw.get("summary", {}))

        # Hoist engine-specific blocks under engine_diagnostics so the
        # universal contract isn't polluted with CV-only fields.
        diagnostics: dict[str, Any] = {}
        if "segmentation" in raw:
            diagnostics["segmentation"] = raw["segmentation"]
        if "runtime" in raw:
            diagnostics["runtime"] = raw["runtime"]

        return {
            "available": bool(raw.get("available", False)),
            "reason":    str(raw.get("reason", "unknown")),
            "message":   str(raw.get("message", "")),
            "engine":    self.engine_name,
            "image":     raw.get("image"),
            "segments":  segments,
            "summary": {
                "segment_count":        int(summary.get("segment_count", len(segments))),
                "quality_counts":       dict(summary.get("quality_counts", {})),
                "good_or_better_count": int(summary.get("good_or_better_count", 0)),
            },
            "engine_diagnostics": diagnostics,
        }


# =============================================================================
# Noop fallback — for adapters that yield no segmentation at all.
# =============================================================================


class NoopSegmenter:
    """Empty result.

    Used by adapters that don't supply map images or vector map data. The
    backend trace tracker still operates (it's coordinate-space, not pixel-
    space), so room presence detection keeps going; the card simply does not
    render polygonal room overlays.
    """

    engine_name = "noop_fallback"

    def validate_tuning(self, tuning: dict[str, Any]) -> list[str]:
        if not isinstance(tuning, dict):
            return ["mapping.segmenter_tuning must be a dict"]
        if tuning:
            return [
                f"{self.engine_name}: tuning is ignored; "
                f"unexpected keys: {sorted(tuning)}"
            ]
        return []

    def segment_map_image(
        self,
        *,
        image_path: str | None,
        tuning: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SegmentationResult:
        return _engine_unavailable(
            engine=self.engine_name,
            reason="noop",
            message=(
                "This adapter declares no map segmentation. Backend trace "
                "tracking remains active; the card will not render polygonal "
                "room overlays."
            ),
        )


# =============================================================================
# Registry
# =============================================================================


_SEGMENTER_ENGINES: dict[str, MapSegmenter] = {
    "eufy_cv_v1":    EufyCVSegmenter(),
    "noop_fallback": NoopSegmenter(),
    # "roborock_deterministic": RoborockDeterministicSegmenter(),  # when ready
}


def get_segmenter_engine(name: str | None) -> MapSegmenter:
    """Return the engine registered under ``name``.

    Falls back to ``noop_fallback`` when ``name`` is None or unknown and logs
    a warning so misconfigured adapters don't silently degrade.
    """
    if not name:
        return _SEGMENTER_ENGINES["noop_fallback"]

    engine = _SEGMENTER_ENGINES.get(name)
    if engine is None:
        _LOGGER.warning(
            "Unknown segmenter_engine %r; falling back to noop_fallback. "
            "Check adapter_config.mapping.segmenter_engine.",
            name,
        )
        return _SEGMENTER_ENGINES["noop_fallback"]

    return engine


def known_engine_names() -> list[str]:
    """Return the set of engine names ``_validate_adapter`` should accept."""
    return list(_SEGMENTER_ENGINES)


# =============================================================================
# Internal helpers
# =============================================================================


def _engine_unavailable(
    *, engine: str, reason: str, message: str,
) -> SegmentationResult:
    """Canonical empty SegmentationResult for engines that can't run.

    Only ``eufy_cv_v1`` surfaces a runtime-capabilities block on failure — it
    is the diagnostic that tells the user "you're missing scipy" or similar.
    Deterministic and noop engines have no library dependency to report.
    """
    diagnostics: dict[str, Any] = {}
    if engine == EufyCVSegmenter.engine_name:
        diagnostics["runtime"] = image_runtime_capabilities()

    return {
        "available": False,
        "reason":    reason,
        "message":   message,
        "engine":    engine,
        "image":     None,
        "segments":  [],
        "summary": {
            "segment_count":        0,
            "quality_counts":       {},
            "good_or_better_count": 0,
        },
        "engine_diagnostics": diagnostics,
    }
