"""Config flow for Eufy Vacuum Manager.

Collects the user's vacuum entity (so the integration knows which device
to manage) plus an optional tested-model string and free-text notes.
The vacuum picker is OPTIONAL during initial setup — leaving it blank
still creates the config entry; the user can fill it in later via
Configure → Options.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_NOTES,
    CONF_TESTED_MODEL,
    CONF_VACUUM_ENTITY_ID,
    DEFAULT_TITLE,
    DOMAIN,
    SUPPORTED_TESTED_MODEL,
)


_VACUUM_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="vacuum"),
)


class EufyVacuumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup flow — collects vacuum entity, model identifier, and notes."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step: collect vacuum entity + model + optional notes, then finish."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            # Drop the vacuum field from data if blank — keeps the config-entry
            # data clean and the integration's setup_entry can detect "no
            # vacuum chosen yet" by checking for key absence.
            if not user_input.get(CONF_VACUUM_ENTITY_ID):
                user_input.pop(CONF_VACUUM_ENTITY_ID, None)
            return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_VACUUM_ENTITY_ID): _VACUUM_SELECTOR,
                vol.Required(CONF_TESTED_MODEL, default=SUPPORTED_TESTED_MODEL): str,
                vol.Optional(CONF_NOTES, default=(
                    "Open the Eufy Vacuum panel in the sidebar to add your vacuum "
                    "and import its current map."
                )): str,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        # HA >= 2024.12: do NOT pass config_entry to the OptionsFlow constructor.
        # The framework auto-attaches it as a read-only property; assigning it
        # in __init__ raises AttributeError on the property setter.
        return EufyVacuumOptionsFlow()


class EufyVacuumOptionsFlow(OptionsFlow):
    """Options flow for editing the vacuum entity and notes after initial setup.

    The vacuum entity field here is the recovery path for users who installed
    before the field existed in the config flow (or skipped it during initial
    setup). Saving a new value reloads the config entry, which in turn
    registers the panel for the chosen vacuum.

    No __init__: ``self.config_entry`` is set automatically by HA on the
    OptionsFlow base class as of 2024.12. Defining our own __init__ that
    assigns ``self.config_entry`` raises ``AttributeError: property
    'config_entry' of 'EufyVacuumOptionsFlow' object has no setter``.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options edit form and persist changes on submit."""
        if user_input is not None:
            data = {CONF_NOTES: user_input.get(CONF_NOTES, "")}
            vacuum_entity_id = user_input.get(CONF_VACUUM_ENTITY_ID)
            if vacuum_entity_id:
                data[CONF_VACUUM_ENTITY_ID] = vacuum_entity_id
            return self.async_create_entry(title="", data=data)

        current_vacuum = self.config_entry.options.get(
            CONF_VACUUM_ENTITY_ID,
            self.config_entry.data.get(CONF_VACUUM_ENTITY_ID, ""),
        )
        current_notes = self.config_entry.options.get(
            CONF_NOTES, self.config_entry.data.get(CONF_NOTES, ""),
        )

        schema: dict[Any, Any] = {}
        if current_vacuum:
            schema[vol.Optional(CONF_VACUUM_ENTITY_ID, default=current_vacuum)] = (
                _VACUUM_SELECTOR
            )
        else:
            schema[vol.Optional(CONF_VACUUM_ENTITY_ID)] = _VACUUM_SELECTOR
        schema[vol.Optional(CONF_NOTES, default=current_notes)] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
