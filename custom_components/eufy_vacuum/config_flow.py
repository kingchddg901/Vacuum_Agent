"""Config flow for Eufy Vacuum Manager — creates the config entry and directs users to the panel for full setup."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_NOTES,
    CONF_TESTED_MODEL,
    DEFAULT_TITLE,
    DOMAIN,
    SUPPORTED_TESTED_MODEL,
)


class EufyVacuumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Minimal config flow — creates the entry and directs user to the panel."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step: collect model identifier + optional notes, then finish."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
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
        return EufyVacuumOptionsFlow(config_entry)


class EufyVacuumOptionsFlow(OptionsFlow):
    """Options flow allowing the user to edit the notes field after initial setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the notes edit form and persist changes on submit."""
        if user_input is not None:
            return self.async_create_entry(title="", data={
                CONF_NOTES: user_input.get(CONF_NOTES, ""),
            })

        current_notes = self.config_entry.options.get(
            CONF_NOTES, self.config_entry.data.get(CONF_NOTES, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_NOTES, default=current_notes): str,
            }),
        )
