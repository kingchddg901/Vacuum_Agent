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

from pathlib import Path

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


@pytest.fixture
def hass_config_dir(tmp_path) -> str:
    """Isolate on-disk history as well as in-memory Home Assistant state."""
    return str(tmp_path)


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


# ---------------------------------------------------------------------------
# THE --cov SOURCE GUARD
#
# anchor: CNP337CY  the --cov source guard
#
# This note is WHY tests/ is a doc_anchor declaration root. It used to read "no
# `anchor:` declaration here on purpose", because tests/ could CITE an anchor but not
# DECLARE one -- so a token minted for this reasoning was inert, and the checker called
# it "defined nowhere" as soon as a document cited it. Fixed 2026-11-07 by adding tests/
# to SOURCE_ROOTS; this is the first declaration to use it.
#
# A DOTTED `--cov` source silently corrupts NumPy, and the damage shows up as
# ordinary-looking test failures a long way from the cause. Measured 2026-11-07:
#
#   pytest tests --no-cov                                       -> 5338 passed, 0 failed
#   pytest tests                        (pytest.ini addopts)     -> 5338 passed, 0 failed
#   pytest tests --cov=custom_components/eufy_vacuum/learning    -> clean (directory)
#   pytest tests --cov=.../learning/external_run.py              -> clean (file)
#   pytest tests --cov=custom_components.eufy_vacuum.learning.external_run
#                                                                -> 46 FAILED
#
# so coverage itself is innocent and the DOTTED form is the whole trigger. The
# chain: coverage resolves a non-path source by calling
# `importlib.util.find_spec()` on it (coverage/inorout.py::file_and_path_for_module),
# which imports the parent package tree mid-session. NumPy is then imported a
# SECOND time -- numpy says so itself, "The NumPy module was reloaded (imported a
# second time)" -- and its compiled reduce still compares `initial` against the
# sentinel object it cached on the FIRST import. The reload replaced that object,
# so `np._NoValue` is no longer recognised and numpy tries to coerce it:
#
#   TypeError: float() argument must be a string or a real number, not '_NoValueType'
#
# Every `ndarray.sum()` raises, which is why the casualties are the numpy-backed
# mapping/segmentor tests and not anything to do with the module being measured.
# The Python-level sentinel stays SELF-CONSISTENT across the reload
# (`numpy._NoValue is numpy._globals._NoValue` is True either way), so the
# obvious probe for a duplicate module reports nothing wrong -- which is why this
# note records the mechanism instead of leaving it to be re-derived.
#
# WHAT THE GUARD DELIBERATELY DOES NOT FLAG. Only a source with NO path separator
# can reach `find_spec`, so that is the whole rule: a slash-bearing source is left
# alone however wrong it is. Two such wrong-but-harmless forms exist in the repo's
# own history, and an earlier draft of this guard rejected both -- which would have
# broken the documented recipes rather than the trap:
#   --cov=custom_components/eufy_vacuum/learning/manager   (no .py; path does not
#       exist, so it collects nothing -- a silent no-op, not a numpy reload)
#   --cov=.../external_run.py                              (a FILE is accepted as a
#       source but collects nothing: "No data to report")
# Neither is worth refusing at the gate; both are a docs problem, and
# docs/testing/02-running-tests.md now carries the recipe that actually narrows.
#
# AND NOTE WHY NARROWING NEEDS MORE THAN `--cov`: the flag is `action="append"`, so a
# command-line source ADDS to the addopts one instead of replacing it -- measured, the
# table still listed 205 files. Narrowing takes `-o addopts=""` to drop the package
# source AND `--cov-config=/dev/null` to drop .coveragerc's `source =`, which is the
# recipe the docs now give. Otherwise just read the per-file row out of the
# whole-package term-missing table, which is already per-file.
# ---------------------------------------------------------------------------

_COV_GUARD_MESSAGE = """--cov source(s) look like module names, not paths: {bad}

Coverage resolves a source with no path separator by importing it, which reloads
NumPy. Every ndarray.sum() then raises
    TypeError: float() argument must be a string or a real number, not '_NoValueType'
and 46 tests go red -- none of them related to the module you were measuring.

A command-line --cov cannot narrow the report anyway: the flag APPENDS to the one
pytest.ini already sets, so the table still covers the whole package. Either read
the per-file row out of that table (it is already per-file), or narrow properly:

    pytest <tests> -o addopts="" --cov-config=/dev/null --cov-branch         --cov=custom_components/eufy_vacuum/learning --cov-report=term-missing

See tests/conftest.py::offending_cov_sources for the measured mechanism."""


def offending_cov_sources(sources, *, path_exists):
    """Return the `--cov` sources that are module names rather than paths.

    `path_exists` is injected so this is testable without touching the disk; the
    hook below supplies one that tries the source both as given and relative to
    the rootdir, because the addopts source is rootdir-relative and pytest may be
    invoked from anywhere.

    A bare `--cov` (no value) arrives as True and is not a source at all.

    The rule is the separator, not existence: only a separator-free source reaches
    `find_spec`, so a slash-bearing one is never flagged however wrong it is. See
    the note above for the two wrong-but-harmless path forms this protects.
    """
    bad = []
    for source in sources or ():
        if source is True:
            continue
        text = str(source)
        if "/" in text or "\\" in text:
            continue
        if path_exists(text):
            continue
        bad.append(text)
    return bad


def pytest_configure(config):
    """Refuse a dotted `--cov` source before any test runs.

    See the note above offending_cov_sources for the measured mechanism.
    """
    sources = getattr(config.option, "cov_source", None)
    root = Path(getattr(config, "rootpath", "."))

    def _exists(text):
        return Path(text).exists() or (root / text).exists()

    bad = offending_cov_sources(sources, path_exists=_exists)
    if bad:
        raise pytest.UsageError(_COV_GUARD_MESSAGE.format(bad=", ".join(bad)))
