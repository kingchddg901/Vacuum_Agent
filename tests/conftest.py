"""Shared fixtures for eufy_vacuum tests.

Provides:
  - mock_config_entry   A ConfigEntry pre-loaded with typical setup data.
  - mock_options_entry  A ConfigEntry with vacuum_entity_id in options
                        (simulates a user who set it via the options flow).
  - init_integration    Helper: load the config entry into hass and return
                        it.  Kept as a fixture factory so individual tests
                        can still set up their own hass state before calling.

All fixtures that require hass use pytest-homeassistant-custom-component's
built-in `hass` fixture — no extra work needed here.
"""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eufy_vacuum.adapters.eufy.const import SUPPORTED_TESTED_MODEL
from custom_components.eufy_vacuum.const import (
    CONF_NOTES,
    CONF_TESTED_MODEL,
    CONF_VACUUM_ENTITY_ID,
    DOMAIN,
)


# ---------------------------------------------------------------------------
# Tell HA's loader to look in the local custom_components/ directory.
# Without this fixture phac blocks custom integrations for test isolation;
# every test file in this suite needs access to eufy_vacuum, so we enable
# it globally here rather than repeating it per-test.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations from the repo's custom_components/."""
    yield


# ---------------------------------------------------------------------------
# Core config-entry fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A typical first-time setup entry: vacuum entity + model set, no options."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Vacuum Agent",
        data={
            CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "Test install",
        },
        options={},
        version=1,
    )


@pytest.fixture
def mock_entry_no_vacuum() -> MockConfigEntry:
    """Entry created when the user skipped the vacuum entity during setup."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Vacuum Agent",
        data={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
            CONF_NOTES: "",
        },
        options={},
        version=1,
    )


@pytest.fixture
def mock_options_entry() -> MockConfigEntry:
    """Entry where vacuum_entity_id was set (or updated) via the options flow."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        title="Vacuum Agent",
        data={
            CONF_TESTED_MODEL: SUPPORTED_TESTED_MODEL,
        },
        options={
            CONF_VACUUM_ENTITY_ID: "vacuum.alfred",
            CONF_NOTES: "Set via options",
        },
        version=1,
    )
