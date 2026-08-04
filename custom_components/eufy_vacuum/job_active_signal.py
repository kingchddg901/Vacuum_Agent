"""Job-active signal: presence probe + a passive OBSERVATION trace (issue #46).

WHY THIS EXISTS
---------------
HA 2026.7 (``home-assistant/core#173282``) stopped creating
``binary_sensor.<vac>_cleaning`` on some Roborock devices. The Roborock adapter
declares that entity as ``entities.job_active`` and sets
``completion.require_job_active_clear``, so on an affected device the completion
gate can never arm — and the 10-minute stranded reaper then force-closes the run
as ``interrupted`` roughly 15 minutes after dispatch, possibly mid-clean. A real
user (Roborock Q5, `vacuum.vlad`) is sitting in exactly that state.

Replacing the binary needs a rule for "is this dock a recharge or the finish?".
We do not have one we can justify yet, and a wrong rule is worse than the bug:
finalizing early writes a truncated learning sample, which is silent and
permanent, whereas the current failure is at least visible.

SO THIS MODULE DECIDES NOTHING. It reads state and writes a decision-log record.
Nothing here is consulted by any completion gate, any reaper, or any dispatch
path. Adding a caller that gates on this is a design change, not a refactor.

WHY OBSERVATIONS AND NOT A VERDICT
----------------------------------
The obvious shape is "compute what the candidate rule would say, log whether it
agreed with the binary". That bakes one rule into the evidence: it answers "is
rule R right?" and nothing else, and every later candidate needs another live run
to evaluate. Recording the raw INPUTS instead makes the trace rule-agnostic —
any number of candidate classifiers can be scored against it offline, long after
the run, including ones nobody has thought of yet.

The trace is self-labelling on hardware whose binary works (Ivy): ``native`` IS
the ground truth for that tick. Score a candidate by replaying the trace and
comparing its output against ``native``. See
``.claude/notes/_score_job_active_rules.py``.

WHAT IS DELIBERATELY ABSENT
---------------------------
- No stored state. Dock dwell comes from the vacuum state object's own
  ``last_changed``, so there is nothing to persist, invalidate, or leak across
  runs, and no new failure mode on restart.
- No forced-absence override. A switch that makes the code "pretend the binary is
  missing" changes nothing while nothing consumes the fallback — the trace would
  be byte-identical. It earns its keep the day a classifier gates on this, and
  should land with that classifier.
- No i18n. These are maintainer-facing DEBUG records, never rendered to a user
  (same rationale as ``decision_log``).

Public surface:
    probe_presence(hass, vacuum_entity_id) -> SignalPresence
    observation(hass, vacuum_entity_id, active_job=None) -> dict
    observe(hass, vacuum_entity_id, active_job=None) -> None
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .adapters.registry import get_adapter_config
from .decision_log import emit

_LOGGER = logging.getLogger(__name__)

#: States of the vacuum entity that mean "not on the floor". Kept local and
#: small: this module only needs to know whether the robot is sitting on the
#: dock, not to reason about the lifecycle.
_DOCKED_STATES = frozenset({"docked", "returning", "returning_to_dock"})

_BLANK = frozenset({"", "unknown", "unavailable", "none", "null"})


@dataclass(frozen=True)
class SignalPresence:
    """Why a job-active read returned what it did.

    ``is_job_active`` collapses three different situations into ``False``: the
    entity exists and reads ``off``, the entity is registered but momentarily
    stateless, and the entity was never created at all. Only the third is issue
    #46, and telling them apart is the whole point of this dataclass.

    Non-lossy on purpose — ``has_state`` and ``in_registry`` are reported
    separately rather than collapsed into one "present" boolean, because the two
    existing callers of that distinction elsewhere in the tree
    (``rooms/room_discovery.py``, ``diagnostics.py``) use different predicates and
    must keep doing so.
    """

    entity_id: str | None
    has_state: bool
    in_registry: bool
    state: str | None

    @property
    def declared(self) -> bool:
        """The adapter NAMES the entity. Says nothing about it existing."""
        return bool(self.entity_id)

    @property
    def never_created(self) -> bool:
        """Declared, but absent from both the state machine and the registry.

        This is the #46 shape. A registered-but-stateless entity is excluded
        because that is the ordinary boot/restart window, not a missing entity.
        """
        return self.declared and not self.has_state and not self.in_registry

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "declared": self.declared,
            "has_state": self.has_state,
            "in_registry": self.in_registry,
            "never_created": self.never_created,
            "state": self.state,
        }


def _entity_registered(hass: HomeAssistant, entity_id: str) -> bool:
    """True if entity_id exists in the HA entity registry. Never raises."""
    try:
        return er.async_get(hass).async_get(entity_id) is not None
    except Exception:  # pragma: no cover - defensive
        return False


def probe_presence(hass: HomeAssistant, vacuum_entity_id: str) -> SignalPresence:
    """Resolve whether the declared job-active binary actually exists."""
    entity_id = None
    try:
        config = get_adapter_config(vacuum_entity_id) or {}
        entity_id = (config.get("entities") or {}).get("job_active")
    except Exception:  # pragma: no cover - defensive
        pass

    if not entity_id:
        return SignalPresence(None, False, False, None)

    state_obj = hass.states.get(entity_id)
    return SignalPresence(
        entity_id=entity_id,
        has_state=state_obj is not None,
        in_registry=_entity_registered(hass, entity_id),
        state=str(state_obj.state).strip().lower() if state_obj is not None else None,
    )


def _read(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Raw lowered state, or None for absent/blank. Never raises."""
    if not entity_id:
        return None
    try:
        state_obj = hass.states.get(entity_id)
    except Exception:  # pragma: no cover - defensive
        return None
    if state_obj is None:
        return None
    value = str(state_obj.state).strip()
    return None if value.lower() in _BLANK else value


def _seconds_in_state(hass: HomeAssistant, entity_id: str) -> float | None:
    """How long the entity has held its current state, from HA's own clock.

    Uses the state object's ``last_changed`` rather than anything we store. That
    keeps this module stateless, and it is also MORE correct across a restart:
    HA restores ``last_changed`` from the state machine, whereas a value we
    stamped ourselves would be lost or stale.
    """
    try:
        state_obj = hass.states.get(entity_id)
        if state_obj is None or state_obj.last_changed is None:
            return None
        return round(
            (datetime.now(timezone.utc) - state_obj.last_changed).total_seconds(), 1
        )
    except Exception:  # pragma: no cover - defensive
        return None


def observation(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    active_job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One tick's worth of raw inputs for scoring completion rules offline.

    Every field is an OBSERVATION, never a conclusion. ``native`` is the real
    binary's state where one exists — on such hardware it is the ground-truth
    label for this tick, and the reason a trace from a HEALTHY vacuum is what
    validates a rule for a BROKEN one.
    """
    config: dict[str, Any] = {}
    try:
        config = get_adapter_config(vacuum_entity_id) or {}
    except Exception:  # pragma: no cover - defensive
        pass
    entities = config.get("entities") or {}

    presence = probe_presence(hass, vacuum_entity_id)
    vacuum_state = _read(hass, vacuum_entity_id)
    docked = (vacuum_state or "").lower() in _DOCKED_STATES

    out: dict[str, Any] = {
        # ground truth (where the binary exists at all)
        "native": presence.state if presence.has_state else "absent",
        "never_created": presence.never_created,
        # candidate discriminators
        "vac": vacuum_state,
        "task": _read(hass, entities.get("task_status")),
        "batt": _read(hass, entities.get("battery")),
        "area": _read(hass, entities.get("cleaning_area")),
        "ctime": _read(hass, entities.get("cleaning_time")),
        "lce": _read(hass, entities.get("last_clean_end")),
        "count": _read(hass, entities.get("total_cleaning_count")),
        # dwell: only meaningful while docked, but recorded either way so a rule
        # can use "seconds since the last vacuum-state change" generally
        "state_s": _seconds_in_state(hass, vacuum_entity_id),
        "docked": docked,
    }
    if isinstance(active_job, dict):
        out["job"] = active_job.get("status")
        out["armed"] = bool(active_job.get("has_observed_active_lifecycle"))
    return out


def observe(
    hass: HomeAssistant,
    vacuum_entity_id: str,
    active_job: dict[str, Any] | None = None,
) -> None:
    """Emit one observation record. Best effort — must never disturb a run."""
    try:
        emit("job_active.observe", **observation(hass, vacuum_entity_id, active_job))
    except Exception:  # pragma: no cover - defensive
        pass
