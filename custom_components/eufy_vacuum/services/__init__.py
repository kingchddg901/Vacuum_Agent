"""Service registration package.

Each submodule owns the handlers, schemas, and registration logic for
one functional domain. Public surface per submodule is:

    register(hass: HomeAssistant) -> None
    SERVICES: tuple[str, ...]    # names registered by this module

This package's ``async_register_services`` calls every submodule's
``register``; ``async_unregister_services`` walks every submodule's
``SERVICES`` tuple and removes each.

The integration's ``__init__.py`` imports the same two names from
``.services`` as before — refactor is invisible from outside the
package.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import (
    access_graph,
    adapter_config,
    dock,
    errors,
    job_control,
    maintenance,
    queue,
    room_profiles,
    rooms,
    run_profiles,
    setup,
    snapshots,
)


# Order matters only in that the user-facing service list in Developer
# Tools displays in registration order. Group rooms/queue/job_control
# first since those are the "main" services users invoke directly;
# leave the panel/setup/adapter services for last.
_DOMAINS = (
    rooms,
    queue,
    job_control,
    snapshots,
    dock,
    maintenance,
    errors,
    room_profiles,
    run_profiles,
    access_graph,
    adapter_config,
    setup,
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register every service from every domain."""
    for domain in _DOMAINS:
        domain.register(hass)


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister every service from every domain."""
    from ..const import DOMAIN
    for domain in _DOMAINS:
        for service_name in domain.SERVICES:
            hass.services.async_remove(DOMAIN, service_name)
