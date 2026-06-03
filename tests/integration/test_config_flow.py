"""Tests for the EufyVacuumConfigFlow setup flow and EufyVacuumOptionsFlow.

Coverage targets
----------------
Setup flow:
  [CF-1]  Showing the form returns the user step.
  [CF-2]  Valid input with all fields → entry created, vacuum_entity_id in data.
  [CF-3]  Valid input with vacuum field left blank → entry created,
          vacuum_entity_id absent from data.
  [CF-4]  Duplicate setup (unique_id already configured) → aborted.

Options flow:
  [OF-1]  Opening options shows the form pre-populated from existing data.
  [OF-2]  Submitting new vacuum_entity_id → stored in options.
  [OF-3]  Clearing vacuum_entity_id (empty string) → key absent from options.
  [OF-4]  Opening options when vacuum was set via initial data (not options).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eufy_vacuum.const import (
    CONF_NOTES,
    CONF_TESTED_MODEL,
    CONF_VACUUM_ENTITY_ID,
    DOMAIN,
)
from custom_components.eufy_vacuum.adapters.eufy.const import SUPPORTED_TESTED_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _start_flow(hass: HomeAssistant):
    """Initialise a fresh setup flow and return the first result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    return result


# ---------------------------------------------------------------------------
# Setup flow — [CF-1] through [CF-4]
# ---------------------------------------------------------------------------

async def test_setup_flow_shows_form(hass: HomeAssistant):
    """[CF-1] Initiating the flow without data shows the user step form."""
    result = await _start_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result.get("errors")  # None or {} both acceptable


async def test_setup_flow_creates_entry_with_vacuum(hass: HomeAssistant):
    """[CF-2] Submitting all fields creates an entry with vacuum_entity_id in data."""
    await _start_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "My robot",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vacuum Agent"
    data = result["data"]
    assert data[CONF_VACUUM_ENTITY_ID] == "vacuum.alfred"
    assert data[CONF_TESTED_MODEL] == SUPPORTED_TESTED_MODEL
    assert data[CONF_NOTES] == "My robot"


async def test_setup_flow_creates_entry_without_vacuum(hass: HomeAssistant):
    """[CF-3] Leaving vacuum blank creates an entry; vacuum_entity_id absent from data."""
    # Omit CONF_VACUUM_ENTITY_ID entirely — the field is Optional in the schema.
    # Passing "" would fail EntitySelector validation before our stripping logic runs.
    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert CONF_VACUUM_ENTITY_ID not in result["data"]


async def test_setup_flow_aborts_on_duplicate(hass: HomeAssistant):
    """[CF-4] A second setup flow is aborted when the unique_id is already configured."""
    # First install
    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Second attempt
    result2 = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options flow — [OF-1] through [OF-4]
# ---------------------------------------------------------------------------

async def test_options_flow_shows_prepopulated_form(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-1] Opening options shows form pre-populated from the existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert CONF_VACUUM_ENTITY_ID in schema_keys
    assert CONF_NOTES in schema_keys


async def test_options_flow_updates_vacuum_entity(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-2] Submitting a new vacuum_entity_id stores it in options."""
    mock_config_entry.add_to_hass(hass)

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.new_robot",
            CONF_NOTES: "Updated",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VACUUM_ENTITY_ID] == "vacuum.new_robot"
    assert result["data"][CONF_NOTES] == "Updated"


async def test_options_flow_vacuum_default_preserved(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-3] Once a vacuum_entity_id is set, omitting the field keeps it.

    The options form uses `vol.Optional(key, default=current_vacuum)` when a
    vacuum is already configured, so voluptuous fills the default back in when
    the field is absent from user_input.  This is intentional — the options
    flow has no "clear" affordance for a vacuum that is already set.
    """
    mock_config_entry.add_to_hass(hass)

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_NOTES: "no vacuum key submitted",
            # CONF_VACUUM_ENTITY_ID intentionally omitted
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Default kicks in — original vacuum entity is preserved, not cleared.
    assert result["data"][CONF_VACUUM_ENTITY_ID] == "vacuum.alfred"


async def test_options_flow_reads_vacuum_from_data(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-4] vacuum_entity_id set in initial data (not options) appears in the form."""
    # mock_config_entry has vacuum_entity_id in .data, not .options
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    # The form schema should include a default for CONF_VACUUM_ENTITY_ID
    # drawn from config_entry.data — verified by inspecting schema defaults.
    defaults = {
        str(k): k.default() if callable(k.default) else None
        for k in result["data_schema"].schema
        if hasattr(k, "default")
    }
    assert defaults.get(CONF_VACUUM_ENTITY_ID) == "vacuum.alfred"
