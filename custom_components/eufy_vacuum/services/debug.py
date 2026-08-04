"""VA glue for the drop-in debug flight recorder.

Everything reusable lives in ``..debug_capture`` (integration-agnostic). This module is
the ONLY VA-specific part: the domain + the named area→logger scopes. Registration is a
single call — the "change one setting and register them" end of the abstraction.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..debug_capture import SERVICE_NAMES, register_debug_services

# eufy_vacuum-specific area → logger-name-substring scopes for the ``areas`` filter.
EUFY_AREAS: dict[str, tuple[str, ...]] = {
    "map": (".mapping", ".map_source", ".rooms.source_refresh"),
    "rooms": (".rooms", ".room_entities"),
    "dispatch": (
        ".services.job_control", ".jobs", ".queue", ".planning", ".dispatch",
        ".core.manager",
        # The lifecycle/dock/metrics listeners ARE the dispatch-side machinery —
        # they arm the completion gate and drive finalization — but no area's
        # substrings matched `.listeners`, so selecting "dispatch" captured the
        # code that STARTS a job and none of the code that ends it.
        ".listeners",
    ),
    "learning": (".learning", ".battery"),
    "setup": (".setup", ".onboarding", ".panels"),
    "themes": (".themes",),
    # The machine-readable record of WHY each branch was taken (decision_log.py).
    # Its own area because it cuts ACROSS all the others: a phase decision, a
    # lifecycle decision and an issue-#46 job-active observation all land in the
    # same logger. It was previously UNREACHABLE by selection — no area matched
    # `.decision_log`, so the only way to capture the decision log was to select
    # no area at all and take the entire tree.
    "decisions": (".decision_log",),
}

# Consumed by services/__init__ (async_unregister_services walks this).
SERVICES = SERVICE_NAMES


def register(hass: HomeAssistant) -> None:
    """Register the four debug services under the eufy_vacuum domain."""
    register_debug_services(hass, domain=DOMAIN, areas=EUFY_AREAS)
