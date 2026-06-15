"""Shared fixtures for the adapter test suite.

The contract tests are **brand-agnostic**: they validate any adapter config
against the framework's documented schema and runtime expectations. Each brand
contributes one entry to ``ADAPTER_BUILDERS`` — a callable that builds and
returns that brand's registered config. Add a new brand there (e.g. Roborock)
and the entire contract suite in ``test_adapter_contract.py`` runs against it
automatically, no new test code required.

Brand-*specific* deep tests (the Eufy CV segmentor, the Eufy model catalog) live
in their own files under ``tests/adapters/<brand>/`` and are not driven by this.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)


_VAC = "vacuum.alfred"


def _build_eufy(hass) -> dict[str, Any]:
    """Build + register the real Eufy adapter config for one vacuum.

    Mirrors what `async_setup_entry` does per managed vacuum: a model is read
    from the vacuum entity, capabilities are detected from the entity surface,
    and the assembled config is registered. Returns the registered config.
    """
    from custom_components.eufy_vacuum.adapters.eufy.adapter import (
        register_eufy_adapter_for_vacuum,
    )

    # A detected_model the Eufy catalog recognises (X10 family) so the build
    # exercises the real model-family + capability-hint path.
    hass.states.async_set(_VAC, "docked", {"detected_model": "T2351"})
    register_eufy_adapter_for_vacuum(hass, _VAC)
    return get_adapter_config(_VAC)


def _build_roborock(hass) -> dict[str, Any]:
    """Build + register the real Roborock adapter config for one vacuum.

    No device-registry entry is set up here, so the model resolves to the
    catalog DEFAULT_PROFILE (the conservative no-dock baseline) — enough to
    exercise the real capability-detection + config-assembly path for the
    brand-agnostic contract. Model-specific behaviour (the S6 profile,
    is_roborock_vacuum brand detection) is covered in tests/adapters/roborock/.
    """
    from custom_components.eufy_vacuum.adapters.roborock.adapter import (
        register_roborock_adapter_for_vacuum,
    )

    # supported_features 30524 matches the real vacuum.ivy (incl. CLEAN_AREA).
    hass.states.async_set(
        "vacuum.ivy", "cleaning", {"supported_features": 30524, "fan_speed": "max"}
    )
    register_roborock_adapter_for_vacuum(hass, "vacuum.ivy")
    return get_adapter_config("vacuum.ivy")


# Registry of every known adapter. KEY = brand name, VALUE = builder(hass)->config.
# Adding a brand here wires it into every contract test in this suite.
ADAPTER_BUILDERS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "eufy": _build_eufy,
    "roborock": _build_roborock,
}


@pytest.fixture(params=sorted(ADAPTER_BUILDERS))
async def adapter(request, hass):
    """Yield (brand_name, registered_config) for each known adapter.

    Parametrized over ADAPTER_BUILDERS so every contract test runs once per
    brand. Registry is cleared first for isolation.
    """
    clear_registry()
    name = request.param
    config = ADAPTER_BUILDERS[name](hass)
    assert isinstance(config, dict), f"{name} adapter produced no config dict"
    return name, config
