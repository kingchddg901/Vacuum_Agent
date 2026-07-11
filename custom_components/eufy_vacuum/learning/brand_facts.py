"""BrandFacts — the brand-fact surface the learning engine reads.

Learning reaches a brand adapter for only a handful of scalar facts: entity ids, a
few alias maps, status vocabularies, and engine selection. It **never** branches on
capability — no pass-count caps, no mop/water-settable flags; ``clean_times`` /
``clean_passes`` ride through as *observed data*, used only as estimate lookup keys.

This module defines the contract (``BrandFacts`` Protocol), the default adapter-backed
implementation (``EufyBrandFacts``), and the provider (``brand_facts_for``) that
learning calls instead of reading the adapter directly. A host re-hosting the engine
swaps ``brand_facts_for`` (or supplies its own ``BrandFacts``); nothing else about the
brand is needed. See docs/dev/10-learning-system.md §9.3.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..adapters.registry import get_adapter_config

# (engine_name, tuning_overrides) — resolved against learning's own engine registry.
EngineSpec = tuple[str | None, dict[str, Any] | None]


@runtime_checkable
class BrandFacts(Protocol):
    """Everything learning needs to know about a brand — replaces direct adapter reads."""

    brand: str | None                                   # cosmetic label only

    def entity_id(self, key: str) -> str | None: ...    # "task_status", "cleaning_time",
                                                        # "cleaning_area", "wash_frequency_mode", …
    def alias_map(self, key: str) -> dict[str, str]: ...  # "clean_mode", "clean_intensity",
                                                        # "fan_speed", "water_level", "wash_frequency_mode"

    mid_run_statuses: frozenset[str]                    # docked-but-will-resume task_status values
    cancel_service_exclusion_states: frozenset[str]     # early-return explained by a service call
    cancel_detection_states: dict[str, Any]             # {"active": str|list, "returning": …, "paused": …}

    job_segmenter: EngineSpec
    room_attribution: EngineSpec


class EufyBrandFacts:
    """Default ``BrandFacts`` backed by the adapter registry.

    Reads a config snapshot at construction — brand facts are static per vacuum, so a
    per-resolution snapshot is fine and avoids repeated registry lookups. Faithfully
    mirrors the reads it replaces (see §9.3): raw values except where the callers were
    already normalizing (``cancel_service_exclusion_states`` → stripped/lowered set).
    """

    def __init__(self, config: dict[str, Any] | None) -> None:
        self._cfg: dict[str, Any] = config or {}
        self._entities: dict[str, Any] = self._cfg.get("entities") or {}
        self._vocab: dict[str, Any] = self._cfg.get("vocabulary") or {}

    @property
    def brand(self) -> str | None:
        return self._cfg.get("brand")

    def entity_id(self, key: str) -> str | None:
        return self._entities.get(key)

    def alias_map(self, key: str) -> dict[str, str]:
        return dict(self._vocab.get(f"{key}_aliases") or {})

    @property
    def mid_run_statuses(self) -> frozenset[str]:
        return frozenset(self._cfg.get("external_mid_run_statuses") or [])

    @property
    def cancel_service_exclusion_states(self) -> frozenset[str]:
        return frozenset(
            str(s).strip().lower()
            for s in (self._vocab.get("cancel_service_exclusion_states") or [])
            if s
        )

    @property
    def cancel_detection_states(self) -> dict[str, Any]:
        return dict(self._vocab.get("cancel_detection_states") or {})

    @property
    def job_segmenter(self) -> EngineSpec:
        js = self._cfg.get("job_segmenter")
        return (js.get("engine"), js.get("tuning")) if isinstance(js, dict) else (None, None)

    @property
    def room_attribution(self) -> EngineSpec:
        ra = self._cfg.get("room_attribution")
        return (ra.get("engine"), ra.get("tuning")) if isinstance(ra, dict) else (None, None)


def brand_facts_for(vacuum_entity_id: str) -> BrandFacts:
    """Resolve the ``BrandFacts`` for a vacuum.

    Default: adapter-registry-backed ``EufyBrandFacts``. This is the single seam a host
    swaps to re-host the learning engine on a different brand source — learning calls
    ``brand_facts_for(...)`` rather than reading the adapter directly.
    """
    return EufyBrandFacts(get_adapter_config(vacuum_entity_id))
