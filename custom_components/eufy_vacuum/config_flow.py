"""Config flow for Vacuum Agent.

Collects the user's vacuum entity (so the integration knows which device
to manage) plus an optional tested-model string and free-text notes.
The vacuum picker is OPTIONAL during initial setup — leaving it blank
still creates the config entry; the user can fill it in later via
Configure → Options.
"""

from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)

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
            # reload_on_update=False: the entry-update reload is handled by the
            # add_update_listener in __init__ (options changes need it). HA 2026.6
            # deprecates having BOTH a reloading config-flow method and an update
            # listener (double-reload/race) — error from 2026.12 — so this flow
            # must NOT also reload. Single-instance anyway, so this just aborts.
            self._abort_if_unique_id_configured(reload_on_update=False)
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
                    "Open the Vacuum Agent panel in the sidebar to add your vacuum "
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
        previous_vacuum = self.config_entry.options.get(
            CONF_VACUUM_ENTITY_ID,
            self.config_entry.data.get(CONF_VACUUM_ENTITY_ID, ""),
        )

        if user_input is not None:
            notes = user_input.get(CONF_NOTES, "")
            vacuum_entity_id = user_input.get(CONF_VACUUM_ENTITY_ID)
            if vacuum_entity_id:
                # FLOW-3: the form's default was baked in at RENDER time
                # (below) from self.config_entry as it stood THEN. If the
                # device behind that default was deleted while this dialog
                # sat open (__init__._teardown_vacuum /
                # _schedule_clear_configured_vacuum already stripped it from
                # entry.data/options), submitting the untouched default would
                # resurrect it. Re-validate against HA's live state now,
                # rather than trusting what the stale form remembers.
                if self.hass.states.get(vacuum_entity_id) is None:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._options_schema(
                            current_vacuum=previous_vacuum, current_notes=notes,
                        ),
                        errors={CONF_VACUUM_ENTITY_ID: "vacuum_not_found"},
                    )
                # FLOW-2: switching to a different vacuum here does NOT
                # reconcile the vacuum being replaced -- remove_vacuum_record
                # is never called from this flow (its one caller is the
                # device-delete path). Decision (pre-resolved, not
                # relitigated here): KEEP the old vacuum's stored data by
                # default; just make the change visible in the log so the
                # operator knows which vacuum_entity_id is now orphaned from
                # this entry.
                if previous_vacuum and previous_vacuum != vacuum_entity_id:
                    _LOGGER.warning(
                        "eufy_vacuum: options flow switched the configured "
                        "vacuum from %s to %s — %s's stored data (rooms, "
                        "maps, history, etc.) is KEPT, not removed; delete "
                        "its device from the device page if you want it "
                        "cleared",
                        previous_vacuum, vacuum_entity_id, previous_vacuum,
                    )
                data = {CONF_NOTES: notes, CONF_VACUUM_ENTITY_ID: vacuum_entity_id}
            else:
                data = {CONF_NOTES: notes}
            return self.async_create_entry(title="", data=data)

        current_notes = self.config_entry.options.get(
            CONF_NOTES, self.config_entry.data.get(CONF_NOTES, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self._options_schema(
                current_vacuum=previous_vacuum, current_notes=current_notes,
            ),
        )

    @staticmethod
    def _options_schema(*, current_vacuum: str, current_notes: str) -> vol.Schema:
        """Build the options form schema for a given current vacuum/notes pair."""
        schema: dict[Any, Any] = {}
        if current_vacuum:
            schema[vol.Optional(CONF_VACUUM_ENTITY_ID, default=current_vacuum)] = (
                _VACUUM_SELECTOR
            )
        else:
            schema[vol.Optional(CONF_VACUUM_ENTITY_ID)] = _VACUUM_SELECTOR
        schema[vol.Optional(CONF_NOTES, default=current_notes)] = str
        return vol.Schema(schema)
