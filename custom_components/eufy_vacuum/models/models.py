"""Canonical dataclass and TypedDict definitions for the Eufy Vacuum integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Rule models
# ---------------------------------------------------------------------------

class RuleEffect(TypedDict, total=False):
    """Nested effect block inside a ``RuleDefinition``.

    ``action`` is ``"exclude"`` for blockers and ``"mutate"`` for modifiers.
    ``changes`` is only populated for modifier rules.
    """

    action: str            # "exclude" | "mutate"
    reason: Optional[str]
    changes: dict          # partial RoomRecord fields; empty for blockers


class RuleDefinition(TypedDict, total=False):
    """Canonical shape for one stored room automation rule.

    Stored inside ``RoomRecord["rules"]`` as a plain dict, always normalized
    by ``_normalize_room_rule()`` before storage.
    ``kind`` is ``"blocker"`` or ``"modifier"``.
    ``operator`` is the comparison applied to the HA entity state.
    ``value`` is the RHS of the comparison (``None`` for boolean operators).
    """

    id: str
    label: Optional[str]
    entity_id: str
    kind: str              # "blocker" | "modifier"
    operator: str          # "equals" | "not_equals" | "in" | "not_in" |
                           # "gt" | "gte" | "lt" | "lte" |
                           # "is_on" | "is_off" | "exists" | "missing"
    value: Any             # compared against entity state; None for boolean ops
    enabled: bool
    effect: dict           # RuleEffect


class LiveRuleState(TypedDict, total=False):
    """Per-room snapshot of the last rule evaluation result.

    Stored in ``data["room_rule_status"][vacuum][map][room_id]``.
    ``last_result`` is one of: ``"not_selected"`` | ``"blocked"`` |
    ``"modified"`` | ``"blocked_and_modified"`` | ``"allowed"``.
    """

    room_id: int
    map_id: str
    room_name: str
    last_evaluated_at: str
    last_result: str
    last_selected: bool
    last_included: bool
    last_block_reason: Optional[str]
    last_block_source: Optional[str]    # "direct_rule" | "access_graph"
    last_blocked_by_room_id: Optional[str]
    last_blocked_by_room_name: Optional[str]
    last_triggered_rule_ids: list       # list[str]
    last_modifier_changes: dict         # partial RoomRecord fields
    last_requires_confirmation: bool
    last_preflight_reason: str


class RuleActionContext(TypedDict, total=False):
    """How a rule's action is interpreted in a specific lifecycle phase (documentation-only).

    ``pre_start``: blocker prevents room inclusion; modifier mutates settings.
    ``in_run``: blocker triggers pause/warn/cancel; modifier has no effect
    because the job is already frozen.
    """

    context: str           # "pre_start" | "in_run"
    rule_id: str
    kind: str              # "blocker" | "modifier"
    action_taken: str      # "exclude" | "mutate" | "pause" | "warn" | "cancel"
    reason: Optional[str]


# ---------------------------------------------------------------------------
# Theme models
# ---------------------------------------------------------------------------

class ThemeEntry(TypedDict, total=False):
    """One entry in the theme library, stored in ``data["theme"]["library"][theme_id]``.

    ``tokens`` — named design tokens; ``colors`` — hex/CSS color values;
    ``alpha``  — named opacity values (0.0–1.0).
    """

    id: str
    name: str
    tokens: dict           # str → Any
    colors: dict           # str → str
    alpha: dict            # str → float


class ThemeDraft(TypedDict, total=False):
    """Working draft overrides for the active theme.

    Stored in ``data["theme"]["vacuums"][vacuum_entity_id]["working_draft"]``.
    Only contains keys the user has explicitly overridden; merged on top of
    the active theme entry at read time. ``draft_dirty`` lives on the parent.
    """

    tokens: dict           # str → Any  (only overridden keys)
    colors: dict           # str → str  (only overridden keys)
    alpha: dict            # str → float  (only overridden keys)


class ThemeVacuumState(TypedDict, total=False):
    """Per-vacuum theme state stored in ``data["theme"]["vacuums"][vacuum_entity_id]``.

    ``active_theme_id`` points into the library (``None`` = no theme selected).
    ``draft_dirty`` is ``True`` when ``working_draft`` differs from the saved entry.
    ``editor_mode`` is always ``"live"``.
    """

    active_theme_id: Optional[str]
    working_draft: dict    # ThemeDraft
    draft_dirty: bool
    editor_mode: str       # "live"


class RoomRecord(TypedDict, total=False):
    """Canonical shape for a stored room configuration dict (documentation-only).

    Runtime storage uses a plain dict for HA storage compatibility.
    ``floor_type`` encodes carpet pile in the value (e.g. ``"carpet_low_pile"``);
    use ``floor_type.startswith("carpet")`` rather than a separate carpet flag.
    """

    room_id: int
    map_id: str
    name: str
    slug: Optional[str]
    enabled: bool
    order: int
    profile_name: Optional[str]
    floor_type: str             # "hardwood"|"laminate"|"tile"|"marble"|"granite"|"concrete"|"carpet_low_pile"|"carpet_high_pile"
    clean_mode: str
    fan_speed: str
    water_level: str
    clean_intensity: str
    clean_passes: int
    edge_mopping: bool
    path_type: Optional[str]    # "wide" | "narrow" | None
    is_dock_room: bool
    grants_access_to: list      # list[str] — room slugs this room grants access to
    rules: list                 # list[dict] — scheduling/condition rules
    color: Optional[str]        # "#rrggbb" per-room map fill override, or None/absent for the palette


@dataclass(slots=True)
class RoomConfig:
    """Normalized room configuration."""

    room_id: int
    map_id: str
    name: str
    slug: str | None = None

    enabled: bool = True
    order: int = 0
    profile_name: str = "vacuum_quick"

    # floor_type encodes carpet pile height in the value (e.g. "carpet_low_pile");
    # use floor_type.startswith("carpet") rather than a separate flag.
    floor_type: str = "hardwood"

    clean_mode: str = "vacuum"
    fan_speed: str = "Max"
    water_level: str = "Off"
    clean_intensity: str = "Standard"
    clean_passes: int = 1
    edge_mopping: bool = False

    # Stored explicitly so callers can read path_type without re-resolving the profile.
    path_type: Optional[str] = None

    is_dock_room: bool = False
    grants_access_to: list = field(default_factory=list)
    rules: list = field(default_factory=list)

    # Setup-state flag — True iff the user has explicitly approved this
    # room via the save_rooms step. Discovered-but-not-yet-approved rooms
    # carry False and are filtered out of entity creation, drift "removed"
    # signals, and other consumer paths. See setup/drift.py.
    is_configured: bool = False
    configured_at: Optional[str] = None

    # Per-room map fill color override — a canonical "#rrggbb" (lowercased) or None to use the
    # themeable room-fill palette. Purely presentational; see docs/dev/themeable-map-palette.md.
    color: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        """Return the room config as a dictionary."""
        return asdict(self)


@dataclass(slots=True)
class MapConfig:
    """Normalized map configuration."""

    map_id: str
    name: str | None = None
    rooms: dict[int, RoomConfig] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return the map config as a dictionary."""
        return {
            "map_id": self.map_id,
            "name": self.name,
            "rooms": {str(room_id): room.as_dict() for room_id, room in self.rooms.items()},
        }


@dataclass(slots=True)
class VacuumCapabilities:
    """Detected capabilities for one vacuum."""

    supports_room_clean: bool = False
    supports_map_selection: bool = False
    supports_dock_empty: bool = False
    supports_mop_wash: bool = False
    supports_mop_dry: bool = False
    supports_live_map: bool = False
    supports_maintenance_entities: bool = False

    tested_profile: str = "generic"
    detected_model: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return capabilities as a dictionary."""
        return asdict(self)


@dataclass(slots=True)
class VacuumRuntimeState:
    """Transient runtime state for one vacuum."""

    vacuum_entity_id: str
    active_map_id: str | None = None
    selected_map_id: str | None = None
    selected_room_ids: list[int] = field(default_factory=list)
    queue_room_ids: list[int] = field(default_factory=list)
    active_job_room_ids: list[int] = field(default_factory=list)
    start_block_reason: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        """Return runtime state as a dictionary."""
        return asdict(self)
