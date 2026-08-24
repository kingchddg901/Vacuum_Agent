"""Clean-order services — apply and clear the DEVICE'S saved order.

Two services, both explicit user actions:

- ``apply_clean_sequence``: write the current queue order to the device
- ``clear_clean_sequence``: wipe the saved order, restoring path optimisation

⚠ THESE EDIT A PERSISTENT, MAP-LEVEL USER SETTING IN THE VENDOR APP. A saved sequence
orders EVERY start, including ones the user begins from the Roborock app, and it
renders in that app's own Sequence screen as numbered badges. This is not per-run.

Gated on the Override Order switch — a user must have deliberately enabled the override
before either service will fire. Toggling the switch off is deliberately NOT the same as
clearing the device: doing so would destroy a sequence the user set in their own app.
Clear is EXPLICIT here for that reason (FINDINGS-roborock-clean-sequence 2026-08-19).

Only registered when at least one vacuum's adapter declares the write; both handlers
report ``unsupported`` for any vacuum whose adapter does not, so the services stay safe
to call speculatively (the card can offer them without first probing capabilities).
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN
from ._common import get_manager


_LOGGER = logging.getLogger(__name__)


SERVICE_APPLY_CLEAN_SEQUENCE = "apply_clean_sequence"
SERVICE_CLEAR_CLEAN_SEQUENCE = "clear_clean_sequence"


SERVICES = (SERVICE_APPLY_CLEAN_SEQUENCE, SERVICE_CLEAR_CLEAN_SEQUENCE)


_APPLY_SCHEMA = vol.Schema(
    {
        vol.Required("vacuum_entity_id"): cv.entity_id,
    }
)
_CLEAR_SCHEMA = _APPLY_SCHEMA


def _clean_order(hass: HomeAssistant):
    """Return the CleanOrderManager, or None if the integration is unwired.

    Both handlers survive that: they report ``unsupported``, so a badly-timed call
    (during setup, or after a config-entry reload) never raises into the caller.
    """
    manager = get_manager(hass)
    return getattr(manager, "clean_order", None)


async def _handle_apply(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Write the CURRENT QUEUE ORDER to the device's saved sequence.

    "Current queue" is what a Start would dispatch right now — using it means the saved
    sequence always matches the dispatch, which sidesteps the OPEN question of whether
    a saved sequence constrains a subset dispatch. See the finding.
    """
    vacuum_entity_id = call.data["vacuum_entity_id"]
    co = _clean_order(hass)
    if co is None or not co.can_write(vacuum_entity_id):
        return {"status": "unsupported", "order": None}

    try:
        payload = await co.apply_current_queue(vacuum_entity_id)
    except Exception as err:  # pragma: no cover - defensive
        raise HomeAssistantError(f"Failed to apply clean sequence: {err}") from err
    _LOGGER.debug("apply_clean_sequence complete: %s", payload)
    return payload


async def _handle_clear(hass: HomeAssistant, call: ServiceCall) -> dict:
    """Clear the device's saved sequence so it path-optimises again.

    Explicit — the switch turning OFF does not do this. A user who set their own
    sequence in the Roborock app and never touched ours must be able to toggle our
    override off without losing what they configured there.
    """
    vacuum_entity_id = call.data["vacuum_entity_id"]
    co = _clean_order(hass)
    if co is None or not co.can_write(vacuum_entity_id):
        return {"status": "unsupported", "order": None}

    try:
        payload = await co.async_clear(vacuum_entity_id)
    except Exception as err:  # pragma: no cover - defensive
        raise HomeAssistantError(f"Failed to clear clean sequence: {err}") from err
    _LOGGER.debug("clear_clean_sequence complete: %s", payload)
    return payload


def register(hass: HomeAssistant) -> None:
    """Register clean-order services."""

    async def apply_clean_sequence(call: ServiceCall) -> dict:
        return await _handle_apply(hass, call)

    async def clear_clean_sequence(call: ServiceCall) -> dict:
        return await _handle_clear(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_CLEAN_SEQUENCE, apply_clean_sequence,
        schema=_APPLY_SCHEMA, supports_response=True,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_CLEAN_SEQUENCE, clear_clean_sequence,
        schema=_CLEAR_SCHEMA, supports_response=True,
    )
