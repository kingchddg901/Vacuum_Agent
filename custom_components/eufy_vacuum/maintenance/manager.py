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

from ..adapters.entity_resolve import resolve_action_entity, sweep_siblings
from ..const import ENTITY_OVERRIDES_KEY
from ..core import usage_accumulator
from ..core.capabilities import MAINTENANCE_CLOCK_ROLE
from ..adapters.registry import get_adapter_config as _get_adapter_config
from ..adapters.upkeep_keys import components_for_model, model_has_component
from ..timestamp_utils import utc_now_iso

if TYPE_CHECKING:
    from ..core.manager import EufyVacuumManager

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# anchor: BNBFVSBR
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


# REPLICA RNJ9YQF7 -- _display_label is byte-identical here, in planning/run_plan.py
# (the primary, which carries the reasoning) and in core/manager.py. Found by
# _relation_hunt.py AFTER the set was recorded by hand as two copies.
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


def _hours_summary(value: Any, suffix: str) -> str | None:
    """``"<hours label> <suffix>"``, or None when the value has no hours label.

    GUARD THE RESULT, NOT THE INPUT. The four call sites below used to read
    ``_hours_text(value) + " suffix" if value is not None else None`` — but
    ``value is not None`` is NOT the condition under which _hours_text returns a
    string. It also returns None for a NEGATIVE number (line above) and for
    anything non-numeric. An overdue consumable reports negative remaining hours,
    passes the ``is not None`` guard, and lands on ``None + str`` → TypeError.

    Found in a user's diagnostics rather than by audit (Roborock Q5, issue #46
    thread): ``upkeep_snapshot_error: TypeError("unsupported operand type(s) for
    +: 'NoneType' and 'str'")``. It surfaced there only because diagnostics.py
    wraps this call in try/except — ``get_upkeep_snapshot`` is ALSO on
    ``get_dashboard_snapshot``'s path (core/manager.py) with no guard of its own,
    so the same overdue consumable takes out the card's whole data source.

    Both copies of _hours_text have tests asserting None-for-negative ([MNT-3],
    [CMH-2]); nothing exercised a CALL SITE with one.
    """
    text = _hours_text(value)
    return f"{text} {suffix}" if text else None


# ---------------------------------------------------------------------------
# anchor: BNXFRB65
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
# anchor: BN6QNPKK
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
    # anchor: BN6NQY5J
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

        # ONE ROUTING. Every adapter ships i18n KEYS routed by REGIME; the per-FAMILY prose
        # routing was removed 2026-09-12 with its last user. `guide_family` and
        # `guide_family_name` are no longer in this payload -- the card's badge that showed
        # them went at the same time, because a model does not resolve to a family any more.
        model_code = self._manager._get_registry_model_code(vacuum_entity_id=vacuum_entity_id)
        guide_regime = _catalog.get("model_key_regimes", {}).get(model_code or "")
        key_map = _catalog.get("key_guides", {}).get(guide_regime or "", {})
        return {
            "code": model_code,
            "name": model_names.get(model_code or "", model_code),
            "source": "device_registry" if model_code else None,
            "guide_regime": guide_regime,
            "guide_available": bool(key_map),
            "supported_guide_components": sorted(key_map),
        }

    # REMOVED 2026-09-12 — `_guide_language`. It read the HA INSTANCE language to pick which
    # translated prose to overlay, and the prose overlay is gone. The instance language was
    # always the wrong axis for this: the guide follows the CARD's globe, which is per user and
    # which the backend cannot see. That mismatch is the whole reason the key system exists —
    # the backend ships keys and holds no words, so there is no language for it to choose.

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

        # ── KEY GUIDES — the only routing there is ──────────────────────────────────
        # Every adapter ships i18n KEYS, routed by REGIME. The backend carries no words at
        # all: it emits the key lists and the CARD resolves them in the READER's language,
        # which is the one language the backend cannot see — it knows the HA instance
        # language and nothing about the per-user globe.
        #
        # THAT MISMATCH IS WHY THE PROSE ROUTING HAD TO GO, not merely why it was unused. It
        # picked translated text by INSTANCE language, so two people reading the same card in
        # different languages got the same words. No amount of translation fixed that; only
        # moving the choice to the card did.
        #
        # ADDITIVE ON THE WIRE: `steps_keys`/`notes_keys` are new fields beside the existing
        # `steps`/`notes`, which stay present and empty. A card that has not been rebuilt
        # renders an empty guide rather than raising, and nothing that reads the old fields
        # has to learn the difference between a key and a sentence.
        key_regime = _catalog.get("model_key_regimes", {}).get(model_code or "")
        key_guide = _catalog.get("key_guides", {}).get(key_regime or "", {}).get(component)
        if key_guide:
            steps_keys = list(key_guide.get("steps", []))
            notes_keys = list(key_guide.get("notes", []))
            # No frequency. A key guide has none by design: the cadence a card can state
            # honestly is the device's own countdown, which the sensor-backed rows already
            # show in hours. The card renders the frequency line only when it has one.
            body = {
                "frequency": None,
                "steps": [],
                "notes": [],
                "steps_keys": steps_keys,
                "notes_keys": notes_keys,
                "available": bool(steps_keys or notes_keys),
            }
            return {
                "source_model_code": model_code,
                "source_model_name": model_names.get(model_code or "", model_code),
                "source_guide_regime": key_regime,
                "available": True,
                "steps": [],
                "notes": [],
                "steps_keys": steps_keys,
                "notes_keys": notes_keys,
                "maintenance": dict(body),
                # A key guide draws no line between cleaning a part and replacing it: the
                # steps are what a person does with their hands either way.
                "replacement": dict(body),
                "display_kind": item_kind,
                "display": dict(body),
            }

        # NO PROSE FALLBACK. Everything below this point used to build a guide from the
        # per-family library and overlay translated fields by HA instance language. Both are
        # deleted. An adapter that declares no `key_guides` for this model has no guide, and
        # None is what every caller already handles -- the same answer the prose path gave for
        # an unknown family.
        return None

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
        all_components = (
            (_get_adapter_config(vacuum_entity_id) or {})
            .get("maintenance_components", {})
        )
        reset_cfg = (all_components.get(component, {}) or {}).get("reset_button") or {}

        registry = er.async_get(self._manager.hass)

        # THE SHARED ACT-PATH LADDER (issue #51). The third rung — upstream
        # translation_key — needs NO new vocabulary here: Roborock's declared reset
        # suffixes are byte-identical to its upstream keys
        # (`reset_main_brush_consumable` and friends). Without it a localized install
        # reported `can_reset: false` on every consumable while the buttons plainly
        # existed as `..._hauptbursten_verbrauchsmaterial_zurucksetzen`, which no
        # English token set can reach.
        _resolved, _status = resolve_action_entity(
            self._manager.hass, registry,
            vacuum_entity_id=vacuum_entity_id,
            domain="button",
            suffixes=reset_cfg.get("entity_suffixes", []),
        )
        if _resolved is not None and _status == "resolved":
            return _resolved
        if _status == "disabled":
            # DISABLED IS NOT MISSING, and it is the common case here: all four of the
            # reporter's reset buttons are disabled in the registry. Returning it would
            # put a Reset control on the card that silently does nothing when pressed.
            _LOGGER.warning(
                "%s: the %s reset button resolved to %s, which is DISABLED in the "
                "entity registry — enable it to reset this consumable from here",
                vacuum_entity_id, component, _resolved,
            )
            return None

        # The same ownership guard the dock actions use. No reset component
        # currently dominates another on either brand, so this arms nothing today —
        # it is here because the reset tokens are the SAME shape as the dock ones
        # and the next brand's vocabulary is not ours to predict.
        rival_token_sets = [
            tokens
            for other, cfg in all_components.items()
            if other != component
            for tokens in ((cfg or {}).get("reset_button") or {}).get("token_sets", [])
        ]

        for tokens in reset_cfg.get("token_sets", []):
            entity_id = self._manager._find_button_entity_by_tokens(
                object_id=object_id,
                required_tokens=tokens,
                rival_token_sets=rival_token_sets,
            )
            if entity_id is not None and "maintenance" not in entity_id.lower():
                return entity_id

        return None

    # ------------------------------------------------------------------
    # anchor: BNNYPRQB
    # Upkeep snapshot
    # ------------------------------------------------------------------

    def get_maintenance_source_candidates(
        self,
        *,
        vacuum_entity_id: str,
    ) -> list[dict[str, Any]]:
        """Entities that could back a maintenance counter for this vacuum, for the user to pick.

        WHY A PICKER AND NOT A RULE. A component with no counter of its own needs a clock, and
        there is no way to derive WHICH entity that should be. Measured across the three
        integrations:

          * a suffix rule breaks on real installs — alfred's lifetime clock is
            `sensor.dining_room_alfred_total_cleaning_time`, which is not
            `sensor.{object_id}_{suffix}` at all;
          * `state_class` would filter it, but ROBOROCK DECLARES NONE on any sensor, so its
            clock and its part countdowns are indistinguishable by metadata.

        Guessing would therefore be wrong exactly where there is least information. Chris: "can
        we read and filter to counter timers for the integration we are looking at and ask users
        to select one?" — so we list, and the person who owns the machine decides.

        THE WRITE HALF ALREADY EXISTS. A user's pick is stored through
        `services/setup.py::set_entity_override` keyed by COMPONENT, and
        `core/capabilities.py::resolve_maintenance_sources` already lets an explicit choice
        outrank derivation (live:ENT-7). Nothing new is stored and nothing new resolves it.

        THE POOL IS THE VACUUM'S OWN INTEGRATION, via the same two-scope sweep every rescue
        uses (device, then config entry — live:ENT-5). We never offer another integration's
        entities: a clock from an unrelated device would count something, plausibly, forever.

        Excluded: anything WE created. Our own `*_maintenance_remaining` sensors are outputs of
        this very calculation, so offering one would let a user point the counter at its own
        result — a genuine feedback loop, and the ONLY exclusion.

        INCLUDED WITH A CAVEAT: a sibling already bound as some component's own counter. Those
        are part counters rather than clocks, and we know it without guessing because we are
        already using them as such. They work — the accumulator survives their resets — but they
        SATURATE: upstream clamps them at zero, so an overdue part that has not been reset
        freezes the clock for every component at once. Each candidate therefore carries
        `bound_components` and a `caveat_key`; the decision to list them anyway is Chris's.

        ⚠ WHAT CANNOT BE DONE, measured rather than assumed: rank them. A lifetime clock is not
        reliably the largest duration a device publishes — on a Roborock S6,
        `main_brush_time_left` reads 293 h against a 206 h `total_cleaning_time`. Magnitude,
        `device_class` and `state_class` all fail to separate the two, which is why this returns
        a LIST and a caveat instead of a default.
        """
        from ..const import DOMAIN

        hass = getattr(self._manager, "hass", None)
        if hass is None:
            return []
        try:
            registry = er.async_get(hass)
            entry = registry.async_get(vacuum_entity_id)
        except Exception:  # pragma: no cover - defensive
            return []
        if entry is None:
            return []

        siblings, _device_count = sweep_siblings(registry, entry)
        # WHICH SIBLINGS ARE ALREADY A COMPONENT'S OWN COUNTER. This is the one thing we KNOW
        # rather than guess: an entity already bound as a component's source is a PART counter,
        # not a lifetime clock. They stay on the list — Chris ruled to include them, and the
        # accumulator handles their resets correctly since `observe` re-baselines on a move
        # against expectation — but they carry a caveat, because they SATURATE.
        _bound: dict[str, list[str]] = {}
        _current_clock: str | None = None
        try:
            _caps = self._manager.get_vacuum_capabilities_snapshot(
                vacuum_entity_id=vacuum_entity_id
            )
            # ⚠ THE CURRENT CLOCK IS ALSO "SOME COMPONENT'S SOURCE" — that is literally its job,
            # so a naive is-this-bound test labels the lifetime clock a part counter and hangs
            # the saturation caveat on the one candidate that cannot saturate. Caught by listing
            # real candidates across three machines, not by reasoning. The user's own stored pick
            # is the fact that separates them, so it is read FIRST and excluded from the caveat.
            _overrides = (
                (self._manager.data.get(ENTITY_OVERRIDES_KEY) or {}).get(vacuum_entity_id) or {}
            )
            _clock_raw = _overrides.get(MAINTENANCE_CLOCK_ROLE)
            if isinstance(_clock_raw, str) and "." in _clock_raw:
                _current_clock = _clock_raw
            for _component, _src in (_caps.get("maintenance_sources") or {}).items():
                if isinstance(_src, str) and _src != _current_clock:
                    _bound.setdefault(_src, []).append(_component)
        except Exception:  # pragma: no cover - a missing snapshot must not hide the list
            _bound, _current_clock = {}, None
        out: list[dict[str, Any]] = []
        for entity_id in siblings:
            if not entity_id.startswith("sensor."):
                continue
            sibling = registry.async_get(entity_id)
            if sibling is not None and getattr(sibling, "platform", None) == DOMAIN:
                continue  # ours — offering it would point the counter at its own output
            state = hass.states.get(entity_id)
            if state is None:
                continue
            attributes = getattr(state, "attributes", None) or {}
            if attributes.get("device_class") != "duration":
                continue
            if usage_accumulator._number(getattr(state, "state", None)) is None:
                continue
            out.append({
                "entity_id": entity_id,
                "name": attributes.get("friendly_name") or entity_id,
                "state": state.state,
                "unit": attributes.get("unit_of_measurement"),
                # A HINT FOR THE LIST, never a requirement: where HA declares a state_class we
                # can say which way it counts before it has moved. Roborock declares none, and
                # the counter learns from the source itself in that case.
                "direction_hint": usage_accumulator.declared_direction(
                    attributes.get("state_class"), attributes, self.USAGE_ATTRIBUTE
                ),
                # The components this entity already counts for, if any. Empty for a genuine
                # lifetime clock.
                "bound_components": sorted(_bound.get(entity_id, [])),
                # Whether this is the pick currently in force. The UI marks it; more importantly
                # it is what keeps the clock out of the part-counter branch above.
                "is_current": entity_id == _current_clock,
                # ⚠ A PART COUNTER SATURATES AND A LIFETIME CLOCK DOES NOT. Upstream clamps
                # these at zero (`max(0, max_life - usage)` in robovac_mqtt), so a part that is
                # overdue and not yet reset reads 0 FOREVER — and a clock pointed at it stops
                # accruing hours for EVERY component on the machine until that one part is
                # reset. The accumulator cannot detect it: a frozen counter and a docked vacuum
                # are the same reading. Chris ruled these stay selectable ("if you dont do the
                # replace reset maybe you deserve to have your other counter freeze") with the
                # caveat SHOWN, so the choice is informed rather than discovered later.
                # A KEY, NEVER PROSE — the card resolves it in the reader's language
                # (`f/no_string_without_i18n`).
                "caveat_key": (
                    "maintenance.clock_candidate.saturates_at_zero"
                    if _bound.get(entity_id)
                    else None
                ),
            })
        out.sort(key=lambda c: c["name"])
        return out

    def get_upkeep_snapshot(
        self,
        *,
        vacuum_entity_id: str,
    ) -> dict[str, Any]:
        """Return replacement, maintenance, and dock upkeep state for one vacuum."""
        # RF-33 (INTCWVFM) cont'd: read-only, unlike get_vacuum_capabilities(refresh=False) —
        # this is the collector diagnostics.py's own upkeep_snapshot call reaches,
        # and it's also on get_dashboard_snapshot's path. Detection is primed
        # elsewhere (setup-time priming loop, every sensor/button/number poll for
        # this vacuum) well before this runs, so reading whatever's stored is safe;
        # `capabilities` below is threaded into get_maintenance_remaining so the
        # per-component loop doesn't re-open the non-inert path.
        capabilities = self._manager.get_vacuum_capabilities_snapshot(vacuum_entity_id=vacuum_entity_id)
        model_meta = self._get_upkeep_model_meta(vacuum_entity_id=vacuum_entity_id)
        model_code = model_meta.get("code")
        sources = capabilities.get("maintenance_sources", {})
        replacement_items: list[dict[str, Any]] = []
        maintenance_items: list[dict[str, Any]] = []
        attention_count = 0
        highest_priority_status = "good"
        priority_rank = {"unknown": 0, "good": 1, "warning": 2, "replace_soon": 3, "replace_now": 4}

        _adapter_cfg = _get_adapter_config(vacuum_entity_id) or {}
        _maintenance_components = _adapter_cfg.get("maintenance_components", {})
        # THE MODEL GATE, now SHARED with the three entity platforms rather than living only
        # here. The rule and the reasoning are in `adapters/upkeep_keys.model_has_component`;
        # this call site keys on the same `model_code` the platforms do, which is what makes
        # "the card shows X" and "X has entities" the same statement instead of two.
        _emitted = components_for_model(_adapter_cfg, model_code)
        # The per-vacuum clock, so each row can say whether IT depends on one. A component with
        # its own counter never does; a guide-only one always does, whether or not a clock has
        # been picked yet. The card needs both facts to choose its treatment: prompt loudly when
        # a row needs a clock and has none, quietly when it needs one and has it.
        _clock_pick = (
            (self._manager.data.get(ENTITY_OVERRIDES_KEY) or {}).get(vacuum_entity_id) or {}
        ).get(MAINTENANCE_CLOCK_ROLE)
        if not (isinstance(_clock_pick, str) and "." in _clock_pick):
            _clock_pick = None
        # The NAME, resolved here rather than in the card: the card would otherwise have to
        # reach into the HA state machine for a friendly_name, which no other maintenance field
        # makes it do. A faded link that says "Counter: Total cleaning time" is what lets someone
        # notice they picked the per-JOB timer by mistake -- the two are one word apart.
        _clock_label = None
        if _clock_pick:
            _clock_state = self._manager.hass.states.get(_clock_pick)
            _clock_label = (
                (getattr(_clock_state, "attributes", None) or {}).get("friendly_name")
                if _clock_state is not None else None
            ) or _clock_pick
        for component, meta in _maintenance_components.items():
            label = meta.get("label", component.replace("_", " ").title())
            # Per-brand DISPLAY key: the component key is canonical (`main_brush`),
            # but a brand may keep its own display word (Eufy shows "Rolling Brush")
            # via label_key -> its own translated vocab entry. Absent => the card
            # uses `component`. Core owns the key; the brand keeps the word.
            label_key = meta.get("label_key")
            # A "maintenance_only" component (e.g. the cleaning tray — a cleanable,
            # not a service-life wear part) is not surfaced as a Replacement row;
            # only its integration-tracked Maintenance row shows (issue #38).
            maintenance_only = bool(meta.get("maintenance_only"))
            # ⚠ THIS REPLACES A FOUR-CLAUSE GATE WHOSE LAST TWO CLAUSES COULD NOT BOTH HOLD
            # FOR EUFY. It read `maintenance_only and not meta.get("sensor_suffix") and
            # component not in <regime set>`, and its own comment asserted "sensor-backed
            # components are never gated (so Eufy ... is unaffected)" as a virtue. Eufy's
            # `cleaning_tray` declares a `sensor_suffix`, so the gate could never reach it —
            # the exemption was structural, not an oversight, and 11 Eufy (model, component)
            # pairs rendered a panel their regime omits. Worse, that exemption assumed a
            # sensor's existence implies the hardware: MEASURED FALSE, because `robovac_mqtt`
            # gates its consumables on `supported_api_types`, a PROTOCOL family, so a
            # novel-protocol Eufy publishes a tray counter whether or not it owns a tray.
            # Chris: *"for eufy Gate them."* One question now, asked of the regime.
            if not model_has_component(
                _emitted, component, has_own_counter=bool(meta.get("sensor_suffix"))
            ):
                continue
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
                # Shape-aware: the attribute on eufy, life-minus-remaining on the
                # countdown brands. Reading only the attribute is why roborock and
                # dreame both showed "0 hours used of N hours" beside a correct
                # percentage — the sibling half of the total_life_hours fix below.
                # THE DEVICE'S OWN VIEW, deliberately not our accumulator. A REPLACEMENT row
                # answers "how much life is left in this part", which the device knows and we
                # do not: it ships the life and the remaining figure together. Our counter
                # answers a different question -- "how long since YOU last serviced it" -- and
                # starts at zero on a countdown brand, which would read as 0 h used beside a
                # perfectly correct 77%. Doc 41: the interval is ours and the usage is theirs.
                usage_hours = self._device_consumed_hours(replacement_state, meta)
                try:
                    total_life_hours = float(replacement_state.attributes.get("total_life_hours"))
                except (TypeError, ValueError):
                    total_life_hours = None

                # THE ATTRIBUTE IS AN EUFY-ISM. robovac_mqtt publishes
                # `total_life_hours` on its consumable sensors; Roborock's carry the
                # remaining hours and nothing else. Reading only the attribute meant
                # `remaining_percent` stayed None on every Roborock part, so
                # `replacement_status` returned "unknown" for all of them — issue #51
                # showed 6 items, 6 "attention", 0 healthy, with perfectly good values
                # like "232.3 hours remaining" sitting right next to the word Unknown.
                #
                # The adapter already declares the service life we need, and the
                # MAINTENANCE half of this very loop has been reading it all along
                # (that is why the same screen showed "300 hours left of 300 hours"
                # while the replacement row said Unknown). Verified against the
                # reporter's own vendor dump: mainBrushWorkTime 243607 s = 67.67 h used,
                # and 300 - 67.67 = 232.33, exactly the figure on his card. Same for
                # side brush (200), filter (150), sensor (30) and strainer (150).
                #
                # Attribute wins when present, so Eufy is untouched.
                if total_life_hours is None:
                    _declared_life = float(meta.get("default_interval_hours", 0.0) or 0.0)
                    if _declared_life > 0:
                        total_life_hours = _declared_life
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
                "label_key": label_key,
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
                    else _hours_summary(replacement_hours, "remaining")
                ),
                "usage_summary": _hours_summary(usage_hours, "used"),
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
                capabilities=capabilities,
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
                "label_key": label_key,
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
                # ⚠ NOT THE SAME QUESTION AS `available`. That says "is anything counting this
                # right now"; this says "would picking a clock be the fix". A component with its
                # own resolved counter is never clock-dependent, so prompting on it would send
                # the user to a setting that cannot help. Since the interval ruling gave every
                # guide-only component a real default, an unclocked row now renders a PLAUSIBLE
                # static bar ("20 hours left of 20 hours, Good") where it used to render an
                # obviously-broken "0 of 0" — so the prompt is what keeps the state visible.
                "needs_clock": source_entity is None or source_entity == _clock_pick,
                "clock_entity": _clock_pick,
                "clock_label": _clock_label,
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
                    else _hours_summary(maint.get("remaining_hours"), "left")
                ),
                "usage_summary": _hours_summary(
                    maint.get("used_since_reset_hours"), "used since reset"
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
        # Tank presence/level as an ENUM, for devices that report tank STATE rather than a
        # numeric fill percent. Brand-neutral and declaration-driven, exactly like the totals
        # above: an adapter that declares the entity gets it surfaced, one that does not
        # simply omits it (None) and the card shows nothing. This exists because the numeric
        # `station_water` role above cannot be satisfied by an enum-only device — rendering
        # a missing percent as "Empty / ~0 ml" states a reading we do not have.
        def _tank_status(key):
            eid = _device_entities.get(key)
            st = self._manager.hass.states.get(eid) if eid else None
            if st is None or st.state in {None, "", "unknown", "unavailable"}:
                return None
            return {"state": st.state, "label": _display_label(st.state), "entity_id": eid}

        _clean_tank = _tank_status("clean_water_tank_status")
        _dirty_tank = _tank_status("dirty_water_tank_status")
        tank_status = (
            {"clean": _clean_tank, "dirty": _dirty_tank}
            if (_clean_tank or _dirty_tank)
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
            # Enum tank state (clean/dirty), None when the device reports no such entity.
            "tank_status": tank_status,
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
    # anchor: BNF7YZZ4
    # Maintenance state / reset / remaining
    # ------------------------------------------------------------------

    def get_maintenance_state(self, *, vacuum_entity_id: str) -> dict[str, Any]:
        """Return current maintenance reset snapshots for one vacuum."""
        self._manager.data.setdefault("maintenance", {})
        return self._manager.data["maintenance"].setdefault(vacuum_entity_id, {})

    @staticmethod
    def _device_consumed_hours(state: Any, meta: dict[str, Any] | None) -> float | None:
        """The DEVICE's view of how much of this part is gone. Used by the REPLACEMENT row.

        Two counter shapes, and only one publishes a usage attribute:

        * ACCUMULATOR — ``usage_hours`` rises on the attributes (eufy, via robovac_mqtt).
        * COUNTDOWN — the STATE is the hours remaining and there is no usage attribute
          (roborock, dreame). Consumed is the declared service life minus what is left.

        Returns None when neither form is readable — callers must treat that as UNKNOWN, never
        as zero. Defaulting to 0 is what made a countdown brand report "0 hours used" beside a
        permanently full maintenance row.

        ⚠ NOT THE MAINTENANCE FIGURE. `_consumed_hours` below is our own accumulated total and
        answers a different question. This one is a POINT reading and is correct for replacement
        precisely because it is: it asks the device what it knows about its own part.
        """
        if state is None:
            return None
        try:
            return float(state.attributes.get("usage_hours"))
        except (TypeError, ValueError):
            pass
        # Declared service life, NOT the user's interval override: the override is the cadence
        # they want prompting at, while this derivation needs the life the device counts from.
        try:
            life = float((meta or {}).get("default_interval_hours", 0.0) or 0.0)
        except (TypeError, ValueError):
            return None
        if life <= 0:
            return None
        try:
            remaining = float(state.state)
        except (TypeError, ValueError):
            return None
        return max(life - remaining, 0.0)

    #: Attribute a count-up integration publishes its accumulated hours on.
    USAGE_ATTRIBUTE = "usage_hours"

    def _consumed_hours(
        self,
        state: Any,
        meta: dict[str, Any] | None,
        *,
        vacuum_entity_id: str | None = None,
        component: str | None = None,
    ) -> float | None:
        """Hours a consumable has been used — OUR accumulated figure, not a point reading.

        THE DEVICE OWNS THE READING, WE OWN THE TOTAL. That is doc 41 §1's rule, and the
        countdown half of it was never actually built: this used to return
        ``default_interval_hours - state``, which is an estimate rather than a count. When a
        device reset its own consumable the countdown jumped back to full, consumed dropped
        toward zero, the stored snapshot exceeded it, and clamp 1 absorbed the difference —
        the card read BRAND NEW. Now the reset is a baseline move and our total keeps climbing.

        Folding happens HERE, on read, and that is safe because the fold is IDEMPOTENT: a second
        fold of the same value sees a zero delta, takes the against-expectation branch, and books
        nothing. So repeated renders cannot double-count and no state-change listener is needed.

        SEEDING, and it is the one place the two shapes genuinely differ:

        * COUNT-UP — the device already keeps the total, so the first fold ADOPTS it
          (``total = reading``). Eufy's numbers are unchanged by this commit.
        * COUNTDOWN — the device keeps no total and never did. We start at zero and count from
          now. The old ``life - state`` looked like history but was arithmetic on a number WE
          chose, and on Eufy that number is the cleaning cadence rather than the part's life —
          20 h against a device-declared 360 h. Inventing a past from it is worse than saying
          we began counting today.

        Returns None when THIS reading is unusable, which keeps `source_available` meaning what
        it says. The accumulated total is not lost — it is persisted and returns on the next
        good reading.
        """
        if state is None:
            return None

        attributes = getattr(state, "attributes", None) or {}
        # The usage ATTRIBUTE is its own source when present; otherwise the STATE is.
        has_usage_attr = usage_accumulator._number(
            attributes.get(self.USAGE_ATTRIBUTE)
        ) is not None
        # NORMALISE THE STATE TO HOURS; the attribute is already hours by its own name.
        # Measured live: robin's lifetime clock reads 409 with unit `min` while alfred's and
        # ivy's read hours, so folding the raw number booked 5 MINUTES of cleaning as 5 HOURS.
        # Every interval in this system is in hours, so the source has to be too.
        reading = (
            attributes.get(self.USAGE_ATTRIBUTE)
            if has_usage_attr
            else usage_accumulator.to_hours(
                getattr(state, "state", None),
                attributes.get("unit_of_measurement"),
            )
        )
        declared = usage_accumulator.declared_direction(
            attributes.get("state_class"), attributes, self.USAGE_ATTRIBUTE
        )

        # A caller with no component identity cannot persist; fold nothing and answer from the
        # reading alone. Nothing does this today — the parameter keeps the seam honest rather
        # than pretending the method is still static.
        if vacuum_entity_id is None or component is None:
            value = usage_accumulator._number(reading)
            return value if direction == usage_accumulator.UP else None

        bucket = self.get_maintenance_state(
            vacuum_entity_id=vacuum_entity_id
        ).setdefault(component, {})
        had_baseline = bucket.get("usage_baseline") is not None
        before_total = float(bucket.get("usage_total") or 0.0)
        moves_up = int(bucket.get("usage_moves_up") or 0)
        moves_down = int(bucket.get("usage_moves_down") or 0)

        # DECLARED IF HA SAYS SO, LEARNED FROM THE SOURCE OTHERWISE, and None until it has
        # moved enough to tell. Roborock publishes no `state_class` on any sensor, so its parts
        # take the learning path; alfred and robin declare one and skip it. Nothing is booked
        # while the answer is None — see `observe`.
        direction = usage_accumulator.learned_direction(declared, moves_up, moves_down)

        result = usage_accumulator.observe(
            reading,
            baseline=bucket.get("usage_baseline"),
            total=before_total,
            direction=direction,
        )
        if result["moved"] == usage_accumulator.UP:
            moves_up += 1
        elif result["moved"] == usage_accumulator.DOWN:
            moves_down += 1

        if result["rejected"] is not None:
            # REPORTED, NEVER ABSORBED. A glitch that books a whole service life and
            # re-baselines leaves a permanent overcount with nothing to show it happened.
            _LOGGER.warning(
                "maintenance: %s %s reported a %.1f h jump in one reading, which is longer "
                "than any part's service life — ignoring it as a glitch. If the figure looks "
                "wrong afterwards, reset the component.",
                vacuum_entity_id, component, result["rejected"],
            )

        if not had_baseline and result["baseline"] is not None:
            if has_usage_attr:
                # Adopt the device's own total; it has been counting all along.
                result = {**result, "total": float(result["baseline"])}

        if (result["baseline"] != bucket.get("usage_baseline")
                or result["total"] != before_total
                or moves_up != int(bucket.get("usage_moves_up") or 0)
                or moves_down != int(bucket.get("usage_moves_down") or 0)):
            bucket["usage_baseline"] = result["baseline"]
            bucket["usage_total"] = result["total"]
            bucket["usage_moves_up"] = moves_up
            bucket["usage_moves_down"] = moves_down
            self._manager.async_save_delayed()

        if usage_accumulator._number(reading) is None:
            return None
        return float(result["total"])

    def _component_meta(self, *, vacuum_entity_id: str, component: str) -> dict[str, Any]:
        """Adapter-declared metadata for one maintenance component."""
        from ..adapters.registry import get_adapter_config as _get_adapter_config

        cfg = _get_adapter_config(vacuum_entity_id) or {}
        return (cfg.get("maintenance_components", {}) or {}).get(component, {}) or {}

    def reset_maintenance(
        self,
        *,
        vacuum_entity_id: str,
        component: str,
    ) -> dict[str, Any]:
        """Snapshot current usage_hours for a component as the new reset point."""
        # Left on get_vacuum_capabilities(refresh=False) deliberately: this method
        # is itself only reachable from an explicit user action (the reset button
        # or the reset_maintenance service) and already writes a new baseline, so
        # there's no read-only contract to protect here — and self-heal detection
        # right before the reset guarantees an accurate component→entity mapping.
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

        usage_hours = self._consumed_hours(
            state,
            self._component_meta(vacuum_entity_id=vacuum_entity_id, component=component),
            vacuum_entity_id=vacuum_entity_id, component=component,
        )
        if usage_hours is None:
            # Unreadable, not zero. Snapshotting 0 here would silently baseline the
            # component at "never used" and the counter could never move.
            return {
                "vacuum_entity_id": vacuum_entity_id,
                "component": component,
                "reset": False,
                "reason": "invalid_usage_hours",
                "source_entity": source_entity,
            }

        maintenance = self.get_maintenance_state(vacuum_entity_id=vacuum_entity_id)
        # A reset only re-snapshots the usage baseline — preserve any user-set
        # interval_hours override. Replacing the entry wholesale used to silently
        # drop the override, forcing the user to re-enter their custom interval.
        existing = maintenance.get(component)
        new_entry: dict[str, Any] = {
            "reset_at_usage_hours": usage_hours,
            "reset_at": _iso_now(),
        }
        # ⚠ AND THE SAME TRAP CAUGHT THE ACCUMULATOR, 2026-09-12. The note above fixed ONE
        # field; the guard then read as complete while the wholesale replace went on eating
        # anything added later. `usage_baseline` and `usage_total` are OUR counter, not reset
        # state — wiping them makes the next reading a first reading, so the counter silently
        # restarts from zero on every reset and never books an hour again. A reset moves the
        # BOOKMARK (`reset_at_usage_hours`); it must not touch the thing being bookmarked.
        #
        # Carrying a NAMED LIST rather than another `if` per field, so the next addition is
        # a list entry instead of a fourth silent loss.
        for _carried in ("interval_hours", "usage_baseline", "usage_total",
                         "usage_moves_up", "usage_moves_down"):
            if isinstance(existing, dict) and existing.get(_carried) is not None:
                new_entry[_carried] = existing[_carried]
        maintenance[component] = new_entry

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
        capabilities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return remaining maintenance hours for one component.

        ``capabilities`` lets a caller that already fetched the capabilities
        dict (e.g. get_upkeep_snapshot, via the read-only
        get_vacuum_capabilities_snapshot) pass it straight through instead of
        this method re-fetching its own copy. Omitted (the sensor entity and
        service call sites), this falls back to get_vacuum_capabilities
        (refresh=False) — self-heal detection is wanted there, since a
        maintenance sensor's own poll may be the first thing to run for a
        freshly-added vacuum.
        """
        if capabilities is None:
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
                _consumed = self._consumed_hours(
                    state,
                    self._component_meta(
                        vacuum_entity_id=vacuum_entity_id, component=component
                    ),
                    vacuum_entity_id=vacuum_entity_id, component=component,
                )
                if _consumed is not None:
                    current_usage = _consumed
                    source_available = True

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
