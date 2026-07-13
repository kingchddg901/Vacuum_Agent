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
    "dispatch": (".services.job_control", ".jobs", ".queue", ".planning", ".dispatch", ".core.manager"),
    "learning": (".learning", ".battery"),
    "setup": (".setup", ".onboarding", ".panels"),
    "themes": (".themes",),
}

# Consumed by services/__init__ (async_unregister_services walks this).
SERVICES = SERVICE_NAMES


def register(hass: HomeAssistant) -> None:
    """Register the four debug services under the eufy_vacuum domain."""
    register_debug_services(hass, domain=DOMAIN, areas=EUFY_AREAS)
