"""MaintenanceManager — owns upkeep model metadata, replacement entity
discovery, maintenance reset snapshots, remaining-hours calculations,
and the upkeep snapshot compositor for each managed vacuum.

Also defines two pure-function status helpers (maintenance_status,
replacement_status) used to label components in the upkeep snapshot.

Design
------
Constructed inside EufyVacuumManager after storage is loaded.
Receives a back-reference to the owning manager via ``manager=self``,
following the same pattern as DockManager, ProfileManager, etc.

EufyVacuumManager keeps thin delegation shims on all public methods
for backward compat with the services/ layer and sensors.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er

from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..timestamp_utils import utc_now_iso

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level pure helpers
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    """Return current UTC timestamp in stable format."""
    return utc_now_iso()


def _safe_int(value: Any, default: int = 0) -> int:
    """Return int value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return float value safely."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _display_label(value: Any) -> str | None:
    """Return a friendly title-cased label for enum-like values."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = " ".join(text.replace("_", " ").replace("-", " ").split())
    if not normalized:
        return None
    explicit = {
        "vacuum mop": "Vacuum + Mop",
        "vacuum and mop": "Vacuum + Mop",
        "by room": "By Room",
        "by time": "By Time",
        "replace soon": "Replace Soon",
        "replace now": "Replace Now",
    }
    lowered = normalized.lower()
    if lowered in explicit:
        return explicit[lowered]
    return " ".join(part.capitalize() for part in normalized.split())


def _hours_text(value: Any) -> str | None:
    """Return a simple human-readable hours label."""
    try:
        if value in (None, "", "unknown", "unavailable"):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    rounded = round(number, 1)
    if abs(rounded - round(rounded)) < 0.05:
        integer = int(round(rounded))
        return f"{integer} hour" if integer == 1 else f"{integer} hours"
    return f"{rounded:g} hours"


# ---------------------------------------------------------------------------
# Pure-function status helpers
# ---------------------------------------------------------------------------


def maintenance_status(*, remaining_hours: float, interval_hours: float) -> str:
    """Return maintenance status bucket for one component."""
    if interval_hours <= 0:
        return "unknown"
    ratio = remaining_hours / interval_hours
    if remaining_hours <= 0:
        return "replace_now"
    if ratio <= 0.1:
        return "replace_soon"
    if ratio <= 0.25:
        return "warning"
    return "good"


def replacement_status(*, remaining_percent: float | None) -> str:
    """Return replacement status bucket from remaining % of total service life.

    Percentage-based, NOT absolute hours: a component is judged on the same
    scale whether its full life is 30 h or 360 h, so a freshly-reset part at
    100% always reads "good". The old absolute thresholds (≤30 h = warning)
    pinned any part whose entire service life sat under the warning line — the
    30 h cleaning tray could never leave "warning" even at 100% (issue #38).

    ``remaining_percent`` is None (no total_life to divide by) -> "unknown".
    """
    if remaining_percent is None:
        return "unknown"
    try:
        pct = float(remaining_percent)
    except (TypeError, ValueError):
        return "unknown"
    if pct <= 5:
        return "replace_now"
    if pct <= 10:
        return "replace_soon"
    if pct <= 15:
        return "warning"
    return "good"


# ---------------------------------------------------------------------------
# MaintenanceManager
# ---------------------------------------------------------------------------


class MaintenanceManager:
    """Owns upkeep metadata, replacement entity discovery, maintenance
    reset snapshots, remaining-hours logic, and the upkeep snapshot."""

    def __init__(self, manager: EufyVacuumManager) -> None:
        """Initialise with a back-reference to the owning manager."""
        self._manager = manager
        self._manager.data.setdefault("maintenance", {})

    # ------------------------------------------------------------------
    # Upkeep model metadata + guide helpers
    # ------------------------------------------------------------------

    def _get_upkeep_model_meta(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return upkeep model metadata derived from the upstream device registry."""
        _catalog = (_get_adapter_config(vacuum_entity_id) or {}).get("upkeep_catalog", {})
        model_names = _catalog.get("model_names", {})
        model_guide_families = _catalog.get("model_guide_families", {})
        guide_family_names = _catalog.get("guide_family_names", {})
        guide_library = _catalog.get("guide_library", {})

        model_code = self._manager._get_registry_model_code(vacuum_entity_id=vacuum_entity_id)
        guide_family = model_guide_families.get(model_code or "")
        guide_map = guide_library.get(guide_family or "", {})
        return {
            "code": model_code,
            "name": model_names.get(model_code or "", model_code),
            "source": "device_registry" if model_code else None,
            "guide_family": guide_family,
            "guide_family_name": guide_family_names.get(guide_family or "", guide_family),
            "guide_available": bool(guide_map),
            "supported_guide_components": sorted(guide_map.keys()),
        }

    def _guide_language(self) -> str:
        """Base HA instance language (e.g. 'de' from 'de-DE') for localized upkeep
        guides, or '' when unavailable. NOTE: guides follow the HA INSTANCE language
        (hass.config.language) — not a per-user frontend locale or the card's
        per-dashboard i18n override (the backend can't see those)."""
        hass = getattr(self._manager, "hass", None)
        lang = getattr(getattr(hass, "config", None), "language", None) or ""
        return str(lang).split("-")[0].lower()

    def _get_upkeep_item_guide(
        self,
        *,
        vacuum_entity_id: str,
        model_code: str | None,
        component: str,
        item_kind: str,
    ) -> dict[str, Any] | None:
        """Return model-specific upkeep guide metadata for one component."""
        _catalog = (_get_adapter_config(vacuum_entity_id) or {}).get("upkeep_catalog", {})
        model_names = _catalog.get("model_names", {})
        model_guide_families = _catalog.get("model_guide_families", {})
        guide_family_names = _catalog.get("guide_family_names", {})
        guide_library = _catalog.get("guide_library", {})
        guide_translations = _catalog.get("guide_translations", {})

        guide_family = model_guide_families.get(model_code or "")
        guide = dict(guide_library.get(guide_family or "", {}).get(component, {}))
        if not guide:
            return None

        # Overlay official localized steps/notes/frequencies on the English base
        # PER FIELD, selected by the HA instance language. Anything the localized
        # entry lacks (an unharvested component/language, or a frequency the manual
        # didn't state) falls back to English. See adapters/eufy/upkeep_guides_i18n.
        lang = self._guide_language()
        translated = (
            guide_translations.get(lang, {}).get(guide_family or "", {}).get(component)
            if lang else None
        )
        if translated:
            if translated.get("steps"):
                guide["steps"] = list(translated["steps"])
            if translated.get("notes"):
                guide["notes"] = list(translated["notes"])
            if translated.get("clean_frequency"):
                guide["clean_frequency"] = translated["clean_frequency"]
            if translated.get("replace_frequency"):
                guide["replace_frequency"] = translated["replace_frequency"]

        guide["source_model_code"] = model_code
        guide["source_model_name"] = model_names.get(model_code or "", model_code)
        guide["source_guide_family"] = guide_family
        guide["source_guide_family_name"] = guide_family_names.get(guide_family or "", guide_family)
        guide["available"] = True
        guide["maintenance"] = {
            "frequency": guide.get("clean_frequency"),
            "steps": list(guide.get("steps", [])),
            "notes": list(guide.get("notes", [])),
            "available": bool(guide.get("clean_frequency") or guide.get("steps") or guide.get("notes")),
        }
        guide["replacement"] = {
            "frequency": guide.get("replace_frequency"),
            "steps": list(guide.get("steps", [])),
            "notes": list(guide.get("notes", [])),
            "available": bool(guide.get("replace_frequency")),
        }
        guide["display_kind"] = item_kind
        guide["display"] = dict(
            guide["replacement"] if item_kind == "replacement" else guide["maintenance"]
        )
        return guide

    def _get_replacement_reset_entity(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
    ) -> str | None:
        """Return upstream replacement reset button entity for one component.

        Resolution is adapter-driven from maintenance_components[component]
        ['reset_button']: entity_suffixes (appended to 'button.{object_id}_')
        first, then token_sets as registry fallbacks. Absent config = None.
        """
        from ..adapters.registry import get_adapter_config as _get_adapter_config

        object_id = vacuum_entity_id.split(".", 1)[1]
        reset_cfg = (
            (_get_adapter_config(vacuum_entity_id) or {})
            .get("maintenance_components", {})
            .get(component, {})
            .get("reset_button")
            or {}
        )

        registry = er.async_get(self._manager.hass)
        for suffix in reset_cfg.get("entity_suffixes", []):
            entity_id = f"button.{object_id}_{suffix}"
            if self._manager.hass.states.get(entity_id) is not None:
                return entity_id
            if registry.async_get(entity_id) is not None:
                return entity_id

        for tokens in reset_cfg.get("token_sets", []):
            entity_id = self._manager._find_button_entity_by_tokens(
                object_id=object_id,
                required_tokens=tokens,
            )
            if entity_id is not None and "maintenance" not in entity_id.lower():
                return entity_id

        return None

    # ------------------------------------------------------------------
    # Upkeep snapshot
    # ------------------------------------------------------------------

    def get_upkeep_snapshot(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return replacement, maintenance, and dock upkeep state for one vacuum."""
        capabilities = self._manager.get_vacuum_capabilities(vacuum_entity_id=vacuum_entity_id, refresh=False)
        model_meta = self._get_upkeep_model_meta(vacuum_entity_id=vacuum_entity_id)
        model_code = model_meta.get("code")
        sources = capabilities.get("maintenance_sources", {})
        replacement_items: list[dict[str, Any]] = []
        maintenance_items: list[dict[str, Any]] = []
        attention_count = 0
        highest_priority_status = "good"
        priority_rank = {"unknown": 0, "good": 1, "warning": 2, "replace_soon": 3, "replace_now": 4}

        _maintenance_components = (_get_adapter_config(vacuum_entity_id) or {}).get("maintenance_components", {})
        for component, meta in _maintenance_components.items():
            label = meta.get("label", component.replace("_", " ").title())
            # A "maintenance_only" component (e.g. the cleaning tray — a cleanable,
            # not a service-life wear part) is not surfaced as a Replacement row;
            # only its integration-tracked Maintenance row shows (issue #38).
            maintenance_only = bool(meta.get("maintenance_only"))
            source_entity = sources.get(component)
            replacement_state = self._manager.hass.states.get(source_entity) if source_entity else None
            replacement_reset_entity = self._get_replacement_reset_entity(
                vacuum_entity_id=vacuum_entity_id,
                component=component,
            )
            replacement_status_val = "unknown"
            replacement_value: float | str | None = None
            replacement_unit = None
            replacement_hours = None
            usage_hours = None
            total_life_hours = None
            remaining_percent = None

            if replacement_state is not None:
                replacement_value = replacement_state.state
                replacement_unit = replacement_state.attributes.get("unit_of_measurement")
                try:
                    usage_hours = float(replacement_state.attributes.get("usage_hours"))
                except (TypeError, ValueError):
                    usage_hours = None
                try:
                    total_life_hours = float(replacement_state.attributes.get("total_life_hours"))
                except (TypeError, ValueError):
                    total_life_hours = None
                try:
                    remaining_hours = float(replacement_state.state)
                except (TypeError, ValueError):
                    remaining_hours = None
                replacement_hours = remaining_hours
                if total_life_hours and total_life_hours > 0 and remaining_hours is not None:
                    remaining_percent = round(
                        max(min((remaining_hours / total_life_hours) * 100.0, 100.0), 0.0),
                        2,
                    )
                # Status is bucketed on % of total service life (see
                # replacement_status): computed AFTER remaining_percent so a
                # short-life part isn't stuck at "warning" (issue #38).
                replacement_status_val = replacement_status(remaining_percent=remaining_percent)

            replacement_item = {
                "component": component,
                "label": label,
                "component_label": _display_label(component) or label,
                "kind": "replacement",
                "kind_label": "Replacement",
                "source": "upstream",
                "entity_id": source_entity,
                "remaining_value": replacement_value,
                "remaining_unit": replacement_unit,
                "remaining_hours": replacement_hours,
                "usage_hours": round(usage_hours, 2) if usage_hours is not None else None,
                "total_life_hours": round(total_life_hours, 2) if total_life_hours is not None else None,
                "max_life_hours": round(total_life_hours, 2) if total_life_hours is not None else None,
                "remaining_percent": remaining_percent,
                "status": replacement_status_val,
                "status_label": _display_label(replacement_status_val),
                "available": replacement_state is not None,
                "can_reset": replacement_reset_entity is not None,
                "reset_kind": "upstream" if replacement_reset_entity is not None else None,
                "reset_kind_label": "Upstream" if replacement_reset_entity is not None else None,
                "reset_service": "button.press" if replacement_reset_entity is not None else None,
                "reset_service_data": (
                    {"entity_id": replacement_reset_entity}
                    if replacement_reset_entity is not None
                    else None
                ),
                "remaining_summary": (
                    f"{round(remaining_percent)}% remaining"
                    if remaining_percent is not None
                    else (_hours_text(replacement_hours) + " remaining" if replacement_hours is not None else None)
                ),
                "usage_summary": (
                    _hours_text(usage_hours) + " used"
                    if usage_hours is not None
                    else None
                ),
                "guide": self._get_upkeep_item_guide(
                    vacuum_entity_id=vacuum_entity_id,
                    model_code=model_code,
                    component=component,
                    item_kind="replacement",
                ),
            }
            if not maintenance_only:
                replacement_items.append(replacement_item)

            # Honor a user-saved interval override stored at
            # data["maintenance"][vacuum][component]["interval_hours"]
            # (written by set_maintenance_interval and by the
            # EufyVacuumMaintenanceIntervalNumber entity). Fall back to
            # the adapter-declared default when no override exists or
            # the stored value can't be coerced. Same precedence the
            # sensor entity uses — keeps card + entity + dashboard
            # snapshot all reporting the same value.
            default_interval = float(meta.get("default_interval_hours", 0.0) or 0.0)
            override_raw = (
                self._manager.data.get("maintenance", {})
                .get(vacuum_entity_id, {})
                .get(component, {})
                .get("interval_hours")
            )
            try:
                interval_hours = float(override_raw) if override_raw is not None else default_interval
            except (TypeError, ValueError):
                interval_hours = default_interval
            maint = self.get_maintenance_remaining(
                vacuum_entity_id=vacuum_entity_id,
                component=component,
                interval_hours=interval_hours,
            )
            maintenance_status_val = maintenance_status(
                remaining_hours=float(maint.get("remaining_hours", 0.0) or 0.0),
                interval_hours=float(maint.get("interval_hours", interval_hours) or interval_hours),
            )
            remaining_percent = None
            if interval_hours > 0:
                remaining_percent = round(
                    max(min((float(maint.get("remaining_hours", 0.0) or 0.0) / interval_hours) * 100.0, 100.0), 0.0),
                    2,
                )

            from ..const import DOMAIN
            maintenance_item = {
                "component": component,
                "label": label,
                "component_label": _display_label(component) or label,
                "kind": "maintenance",
                "kind_label": "Maintenance",
                "source": "integration",
                "entity_id": maint.get("source_entity"),
                "remaining_hours": maint.get("remaining_hours"),
                "used_since_reset_hours": maint.get("used_since_reset_hours"),
                "interval_hours": maint.get("interval_hours"),
                # Surface the adapter-declared bounds so the card's maintenance
                # modal can render an interval editor with the right defaults
                # and validation cap. Per maintenance_components.py: default is
                # the manufacturer recommendation; max is the absolute ceiling
                # for a user override (set generously, e.g. 720h for filter).
                "default_interval_hours": float(meta.get("default_interval_hours", 0.0) or 0.0),
                "max_interval_hours": float(meta.get("max_interval_hours", 0.0) or 0.0),
                "current_usage_hours": maint.get("current_usage_hours"),
                "reset_at": maint.get("reset_at"),
                "remaining_percent": remaining_percent,
                "status": maintenance_status_val,
                "status_label": _display_label(maintenance_status_val),
                "available": bool(maint.get("source_available")),
                "can_reset": True,
                "reset_kind": "integration",
                "reset_kind_label": "Integration",
                "reset_service": f"{DOMAIN}.reset_maintenance",
                "reset_service_data": {
                    "vacuum_entity_id": vacuum_entity_id,
                    "component": component,
                },
                "remaining_summary": (
                    f"{round(remaining_percent)}% remaining"
                    if remaining_percent is not None
                    else (_hours_text(maint.get("remaining_hours")) + " left" if maint.get("remaining_hours") is not None else None)
                ),
                "usage_summary": (
                    _hours_text(maint.get("used_since_reset_hours")) + " used since reset"
                    if maint.get("used_since_reset_hours") is not None
                    else None
                ),
                "guide": self._get_upkeep_item_guide(
                    vacuum_entity_id=vacuum_entity_id,
                    model_code=model_code,
                    component=component,
                    item_kind="maintenance",
                ),
            }
            maintenance_items.append(maintenance_item)

            # A maintenance_only component contributes no Replacement status to
            # the attention roll-up (its replacement row was suppressed above).
            _statuses = [maintenance_status_val]
            if not maintenance_only:
                _statuses.append(replacement_status_val)
            for status_value in _statuses:
                if status_value in {"warning", "replace_soon", "replace_now"}:
                    attention_count += 1
                if priority_rank.get(status_value, 0) > priority_rank.get(highest_priority_status, 0):
                    highest_priority_status = status_value

        dock_entity = capabilities.get("entities", {}).get("dock_status")
        station_water_entity = capabilities.get("entities", {}).get("water_level") or capabilities.get("entities", {}).get("station_water")
        dock_state = self._manager.hass.states.get(dock_entity) if dock_entity else None
        station_water_state = self._manager.hass.states.get(station_water_entity) if station_water_entity else None
        dock_events = dict(self._manager.get_dock_events(vacuum_entity_id=vacuum_entity_id))
        dock_counts = {
            "mop_wash_count": _safe_int(dock_events.get("mop_wash_count"), 0),
            "dust_empty_count": _safe_int(dock_events.get("dust_empty_count"), 0),
            "dry_start_count": _safe_int(dock_events.get("dry_start_count"), 0),
        }

        # Lifetime device totals + dock firmware (robovac_mqtt v1.11.0+). Brand-
        # neutral: any adapter that declares these entities gets them surfaced. Each
        # is omitted (None) when its entity is absent or reports a placeholder
        # state, so older integrations / brands without them simply show nothing.
        _device_entities = capabilities.get("entities", {})

        def _device_total(key, cast):
            eid = _device_entities.get(key)
            st = self._manager.hass.states.get(eid) if eid else None
            if st is None or st.state in {None, "", "unknown", "unavailable"}:
                return None
            try:
                return cast(float(st.state))
            except (TypeError, ValueError):
                return None

        _area_m2 = _device_total("total_cleaning_area", float)
        _time_s = _device_total("total_cleaning_time", float)
        _count = _device_total("total_cleaning_count", int)
        device_totals = (
            {"area_m2": _area_m2, "time_s": _time_s, "count": _count}
            if any(v is not None for v in (_area_m2, _time_s, _count))
            else None
        )
        _fw_entity = _device_entities.get("dock_firmware_version")
        _fw_state = self._manager.hass.states.get(_fw_entity) if _fw_entity else None
        dock_firmware = (
            _fw_state.state
            if _fw_state is not None
            and _fw_state.state not in {None, "", "unknown", "unavailable"}
            else None
        )

        attention_summary = (
            f"{attention_count} upkeep item(s) need attention."
            if attention_count > 0
            else "No upkeep items need attention."
        )

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "dock_status": dock_state.state if dock_state is not None else capabilities.get("sources", {}).get("dock_status_value"),
            "dock_status_label": _display_label(dock_state.state if dock_state is not None else capabilities.get("sources", {}).get("dock_status_value")),
            "dock_status_entity": dock_entity,
            "station_water": station_water_state.state if station_water_state is not None else None,
            "station_water_label": (
                f"{round(_safe_float(station_water_state.state, 0.0))}%"
                if station_water_state is not None and station_water_state.state not in {None, "", "unknown", "unavailable"}
                else _display_label(station_water_state.state if station_water_state is not None else None)
            ),
            "station_water_entity": station_water_entity,
            "dock_events": {
                "last_mop_wash": dock_events.get("last_mop_wash"),
                "last_dust_empty": dock_events.get("last_dust_empty"),
                "last_dry_start": dock_events.get("last_dry_start"),
                "last_dry_duration": dock_events.get("last_dry_duration"),
                **dock_counts,
            },
            "model_meta": model_meta,
            "device_totals": device_totals,
            "dock_firmware": dock_firmware,
            "replacement_items": replacement_items,
            "maintenance_items": maintenance_items,
            "attention_count": attention_count,
            "highest_priority_status": highest_priority_status,
            "highest_priority_status_label": _display_label(highest_priority_status),
            "attention_summary": attention_summary,
            "updated_at": _iso_now(),
        }

    # ------------------------------------------------------------------
    # Maintenance state / reset / remaining
    # ------------------------------------------------------------------

    def get_maintenance_state(self, *, vacuum_entity_id: str) -> dict[str, Any]:
        """Return current maintenance reset snapshots for one vacuum."""
        self._manager.data.setdefault("maintenance", {})
        return self._manager.data["maintenance"].setdefault(vacuum_entity_id, {})

    def reset_maintenance(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
    ) -> dict[str, Any]:
        """Snapshot current usage_hours for a component as the new reset point."""
        capabilities = self._manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        source_entity = sources.get(component)

        if source_entity is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "no_source_entity",
            }

        state = self._manager.hass.states.get(source_entity)
        if state is None:
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "source_unavailable",
                "source_entity": source_entity,
            }

        try:
            usage_hours = float(state.attributes.get("usage_hours", 0))
        except (TypeError, ValueError):
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "invalid_usage_hours",
                "source_entity": source_entity,
            }

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        maintenance[component] = {
            "reset_at_usage_hours": usage_hours,
            "reset_at": _iso_now(),
        }

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "component": component,
            "reset": True,
            "reset_at_usage_hours": usage_hours,
            "reset_at": maintenance[component]["reset_at"],
            "source_entity": source_entity,
        }

    def get_maintenance_remaining(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
        interval_hours: float,
    ) -> dict[str, Any]:
        """Return remaining maintenance hours for one component."""
        capabilities = self._manager.get_vacuum_capabilities(
            vacuum_entity_id=vacuum_entity_id,
            refresh=False,
        )
        sources = capabilities.get("maintenance_sources", {})
        source_entity = sources.get(component)

        current_usage: float = 0.0
        source_available = False

        if source_entity:
            state = self._manager.hass.states.get(source_entity)
            if state is not None:
                try:
                    current_usage = float(state.attributes.get("usage_hours", 0))
                    source_available = True
                except (TypeError, ValueError):
                    pass

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        component_data = maintenance.get(component, {})
        reset_snapshot = float(component_data.get("reset_at_usage_hours", 0.0))
        reset_at = component_data.get("reset_at")

        used_since_reset = max(current_usage - reset_snapshot, 0.0)
        remaining = max(interval_hours - used_since_reset, 0.0)

        return {
            "vacuum_entity_id": vacuum_entity_id,
            "component": component,
            "remaining_hours": round(remaining, 2),
            "used_since_reset_hours": round(used_since_reset, 2),
            "interval_hours": interval_hours,
            "current_usage_hours": round(current_usage, 2),
            "reset_at_usage_hours": reset_snapshot,
            "reset_at": reset_at,
            "source_entity": source_entity,
            "source_available": source_available,
        }
