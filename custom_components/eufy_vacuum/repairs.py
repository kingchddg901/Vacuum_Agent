"""Repair flow for Vacuum Agent — redirects any stale repair issues to the sidebar panel."""

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict | None,
) -> RepairsFlow:
    """Return a repair flow that directs the user to the setup panel."""
    return EufyVacuumSetupRedirectFlow(issue_id=issue_id)


class EufyVacuumSetupRedirectFlow(RepairsFlow):
    """Inform the user that setup is now managed through the panel."""

    def __init__(self, *, issue_id: str) -> None:
        self._issue_id = issue_id

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Entry point — go straight to the confirmation step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show the redirect message; dismiss the issue when confirmed."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={},
        )
