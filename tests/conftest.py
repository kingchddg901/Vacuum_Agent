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
from custom_components.eufy_vacuum.profiles.room_profiles import resolve_profile_catalog

from .brand_catalogs import BRAND_BLOCKS, SYNTHETIC_ADAPTER_CONFIG, SYNTHETIC_BLOCK


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
# Brand catalogs — see tests/brand_catalogs.py for why these exist.
# ---------------------------------------------------------------------------

@pytest.fixture(params=sorted(BRAND_BLOCKS), ids=sorted(BRAND_BLOCKS))
def brand(request):
    """A declared catalog, one test run per brand.

    Any test using this must assert RELATIONSHIPS — that a resolved value equals what
    THIS catalog declares — never a literal. A literal passes for one brand and fails
    for the rest, which is exactly the leak the parameterization exists to catch.

    Returns the resolved catalog (post ``resolve_profile_catalog``), since that is what
    every consumer in core actually receives.
    """
    return resolve_profile_catalog(BRAND_BLOCKS[request.param])


@pytest.fixture
def synthetic_catalog():
    """A catalog whose words belong to no real brand.

    For tests that need *a* catalog to function but are not about vocabulary —
    dispatch, queueing, planning. If one of these fails only because a real brand's
    word is missing, that word is load-bearing somewhere it should not be.
    """
    return resolve_profile_catalog(SYNTHETIC_BLOCK)


@pytest.fixture
def synthetic_adapter():
    """Register the synthetic brand for the test vacuum, and unregister after.

    For pure-unit tests of code that resolves its own catalog from the registry
    (``queue_engine.build_room_clean_payload`` and the dispatch engines above it)
    rather than taking one as a parameter. They need an adapter to EXIST; they are not
    about whose it is, so it must not be a real brand's — a dispatch test that only
    passes against Eufy is testing Eufy.

    Registers through the module-level shim, which writes to ``registry._REGISTRY``
    when no coordinator is active. Teardown is not optional: that registry is global,
    and a leftover entry would silently satisfy a later test that should have failed.
    """
    from custom_components.eufy_vacuum.adapters.registry import (
        register_adapter_config,
        unregister_adapter_config,
    )

    vacuum_entity_id = "vacuum.alfred"
    register_adapter_config(vacuum_entity_id, dict(SYNTHETIC_ADAPTER_CONFIG))
    try:
        yield vacuum_entity_id
    finally:
        unregister_adapter_config(vacuum_entity_id)


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
