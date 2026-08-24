"""Tests for the EufyVacuumConfigFlow setup flow and EufyVacuumOptionsFlow.

Coverage targets
----------------
Setup flow:
  [CF-1]  Showing the form returns the user step.
  [CF-2]  Valid input with all fields → entry created, vacuum_entity_id in data.
  [CF-3]  Valid input with vacuum field left blank → entry created,
          vacuum_entity_id absent from data.
  [CF-4]  Duplicate setup is refused at flow START (manifest single_config_entry),
          before any form is rendered.
  [CF-5]  The flow's own unique_id guard still refuses a duplicate on the paths
          the manifest gate does not cover.

Options flow:
  [OF-1]  Opening options shows the form pre-populated from existing data.
  [OF-2]  Submitting new vacuum_entity_id → stored in options.
  [OF-3]  Clearing vacuum_entity_id (empty string) → key absent from options.
  [OF-4]  Opening options when vacuum was set via initial data (not options).
  [OF-5]  FLOW-3: submitting a vacuum_entity_id that no longer exists in HA's
          state machine (e.g. a stale form outliving a device delete) is
          refused with a form + vacuum_not_found error, not written to options.
  [OF-6]  FLOW-2: switching to a different (existing) vacuum logs a warning
          naming the old vacuum_entity_id, and does not touch its stored data.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

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


async def test_setup_flow_aborts_before_showing_the_form(hass: HomeAssistant):
    """[CF-4] C43: a second setup attempt is refused at async_init, not after the form.

    The refusal itself was never in doubt — async_step_user has always called
    _abort_if_unique_id_configured. But that guard lives INSIDE the submit branch,
    so it can only fire once the user has picked a vacuum, typed a model and
    submitted: the whole form filled in for a flow that was doomed before it
    opened. manifest.json declaring ``single_config_entry`` is what moves the
    refusal to flow start (HA aborts in ConfigEntriesFlowManager.async_init with
    ``single_instance_allowed``).

    Asserting FlowResultType.ABORT alone would pass for either mechanism — the
    step_id assertion is the one that bites, because without the manifest key
    this call returns the ``user`` FORM.
    """
    # First install, through the real flow.
    result = await hass.config_entries.flow.async_configure(
        (await _start_flow(hass))["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Second attempt: merely STARTING the flow must already be the end of it.
    result2 = await _start_flow(hass)
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"
    assert result2.get("step_id") is None  # no form was ever rendered
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_setup_flow_unique_id_guard_still_refuses_duplicate(hass: HomeAssistant):
    """[CF-5] The in-flow unique_id guard survives as defence in depth.

    The manifest gate covers the ordinary user path only. It does not run for
    SOURCE_IGNORE/reauth/reconfigure, and it cannot see an entry that appears
    while a flow is already open — the case reproduced here: the flow is started
    while nothing is configured, the entry arrives (added directly, not via a
    flow, so HA does not cancel flows in progress), and only then is the form
    submitted. Ablated (guard removed on the grounds that the manifest now
    covers it) this goes red while CF-4 stays green — the flow runs to
    completion and is refused later, by HA's finish-flow gate, as the generic
    ``single_instance_allowed`` instead of this integration's own
    ``already_configured``. No duplicate entry either way; what the guard buys
    is the specific reason and the refusal happening in our step.
    """
    flow = await _start_flow(hass)
    assert flow["type"] == FlowResultType.FORM  # nothing configured yet

    MockConfigEntry(domain=DOMAIN, data={CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL},
                    unique_id=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
    # FLOW-3: submit now re-validates the vacuum against HA's live state.
    hass.states.async_set("vacuum.new_robot", "docked")

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
    # FLOW-3: the schema default ("vacuum.alfred") is what actually gets
    # submitted (voluptuous fills it in before async_step_init runs), so it
    # must exist in HA's state for the re-validation to accept it.
    hass.states.async_set("vacuum.alfred", "docked")

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


async def test_options_flow_refuses_deleted_vacuum(
    hass: HomeAssistant, mock_config_entry
):
    """[OF-5] FLOW-3: submitting a vacuum_entity_id that no longer exists in
    HA's state machine (e.g. a stale dialog outliving a device delete) is
    refused with a form + vacuum_not_found error, not written to options."""
    mock_config_entry.add_to_hass(hass)
    # Deliberately NOT registering vacuum.gone in hass.states.

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"],
        user_input={
            CONF_VACUUM_ENTITY_ID: "vacuum.gone",
            CONF_NOTES: "should not save",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {CONF_VACUUM_ENTITY_ID: "vacuum_not_found"}
    # The entry itself was never updated.
    assert mock_config_entry.options.get(CONF_VACUUM_ENTITY_ID) is None


async def test_options_flow_switch_logs_warning_for_old_vacuum(
    hass: HomeAssistant, mock_config_entry, caplog
):
    """[OF-6] FLOW-2: switching to a different (existing) vacuum logs a
    warning naming the OLD vacuum_entity_id — its stored data is deliberately
    KEPT, not auto-removed, since this flow never calls remove_vacuum_record."""
    mock_config_entry.add_to_hass(hass)
    hass.states.async_set("vacuum.alfred", "docked")
    hass.states.async_set("vacuum.new_robot", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with caplog.at_level("WARNING"):
        result = await hass.config_entries.options.async_configure(
            init["flow_id"],
            user_input={
                CONF_VACUUM_ENTITY_ID: "vacuum.new_robot",
                CONF_NOTES: "switched",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VACUUM_ENTITY_ID] == "vacuum.new_robot"
    assert any(
        "vacuum.alfred" in rec.message and "vacuum.new_robot" in rec.message
        for rec in caplog.records
    )


async def test_options_flow_no_warning_when_vacuum_unchanged(
    hass: HomeAssistant, mock_config_entry, caplog
):
    """[OF-6] Control: resubmitting the SAME vacuum_entity_id does not log the
    switch warning — it only fires on an actual change."""
    mock_config_entry.add_to_hass(hass)
    hass.states.async_set("vacuum.alfred", "docked")

    init = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    with caplog.at_level("WARNING"):
        result = await hass.config_entries.options.async_configure(
            init["flow_id"],
            user_input={
                CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
                CONF_NOTES: "unchanged",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert not any("stored data" in rec.message for rec in caplog.records)


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
