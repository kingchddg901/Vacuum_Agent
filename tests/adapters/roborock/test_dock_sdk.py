"""Dock decoding against the actual optional python-roborock SDK."""

import builtins
import threading
from enum import IntEnum
from types import SimpleNamespace

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eufy_vacuum.adapters import brands
from custom_components.eufy_vacuum.adapters.registry import (
    clear_registry,
    get_adapter_config,
)
from custom_components.eufy_vacuum.adapters.roborock import adapter, dock

# Import the real SDK during collection. Its module-level rate limiters start
# daemon threads; they belong to the SDK's process lifetime, not an HA test case.
codes = pytest.importorskip("roborock.data.v1.v1_code_mappings")
features = pytest.importorskip("roborock.device_features")

VACUUM = "vacuum.test_roborock"


@pytest.fixture(autouse=True)
def prepared_types(monkeypatch):
    """Supply real SDK types while isolating the module's preparation cache."""
    monkeypatch.setattr(
        dock, "_DOCK_TYPES", (codes.RoborockDockTypeCode, features.RoborockDockFeatures)
    )


@pytest.fixture
def provider(hass):
    """Register a vacuum owned by the real entity registry's Roborock platform."""
    entry = MockConfigEntry(domain="roborock")
    entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        "vacuum",
        "roborock",
        "test-roborock",
        config_entry=entry,
        suggested_object_id="test_roborock",
    )
    return entity.entity_id


@pytest.mark.parametrize("value", [999998, 999999])
def test_unknown_sdk_enum_keeps_code_without_enabling_controls(
    monkeypatch, hass, value
):
    """The real enum's _missing_ fallback must not masquerade as a known dock."""
    monkeypatch.setattr(
        dock, "find_dock_device", lambda h, v: SimpleNamespace(model_id=str(value))
    )
    profile = dock.dock_profile(hass, VACUUM)
    assert profile["has_dock"] is True
    assert profile["dock_type"] == value
    assert profile["dock_type_name"] is None
    assert profile["reason"] == "dock_type_newer_than_library"
    for flag in ("is_washable", "is_dryable", "is_collectable"):
        assert profile[flag] is False

    monkeypatch.setattr(
        adapter,
        "_device_for_vacuum",
        lambda h, v: SimpleNamespace(
            manufacturer="Roborock", model="roborock.vacuum.test_model"
        ),
    )
    clear_registry()
    try:
        hass.states.async_set(VACUUM, "docked", {"supported_features": 0})
        adapter.register_roborock_adapter_for_vacuum(hass, VACUUM)
        config = get_adapter_config(VACUUM)
        for key in ("supports_mop_wash", "supports_mop_dry", "supports_empty_dust"):
            assert config["capabilities"][key] is False
        assert not config.get("dock_events", {}).get("action_controls")
    finally:
        clear_registry()


def test_unknown_enum_that_raises_is_also_conservative(monkeypatch):
    """Support enum implementations that reject a new code with ValueError."""

    class StrictDockType(IntEnum):
        """The standard IntEnum rejection contract, without a vendor fallback."""

        NO_DOCK = 0

    monkeypatch.setattr(
        dock, "_DOCK_TYPES", (StrictDockType, features.RoborockDockFeatures)
    )
    monkeypatch.setattr(
        dock, "find_dock_device", lambda h, v: SimpleNamespace(model_id="999999")
    )
    profile = dock.dock_profile(None, VACUUM)
    assert profile["dock_type"] == 999999
    assert profile["reason"] == "dock_type_newer_than_library"
    assert profile["is_washable"] is False
    assert profile["is_dryable"] is False
    assert profile["is_collectable"] is False


@pytest.mark.parametrize("value", [-9999, 0, 1, 7])
def test_known_codes_preserve_vendor_features(monkeypatch, value):
    """Pass through actual SDK features rather than copying a vendor truth table."""
    monkeypatch.setattr(
        dock, "find_dock_device", lambda h, v: SimpleNamespace(model_id=str(value))
    )
    expected = features.RoborockDockFeatures.from_dock_type(
        codes.RoborockDockTypeCode(value)
    )
    profile = dock.dock_profile(None, VACUUM)
    assert profile["has_dock"] == expected.has_dock
    assert profile["dock_type_name"] == codes.RoborockDockTypeCode(value).name
    for flag in ("is_washable", "is_dryable", "is_collectable"):
        assert profile[flag] == getattr(expected, flag)


def test_profile_does_not_import_unprepared_sdk(monkeypatch):
    """A synchronous capability read must never trigger optional package I/O."""
    monkeypatch.setattr(dock, "_DOCK_TYPES", None)
    original = builtins.__import__

    def forbid_roborock_import(name, *args, **kwargs):
        if name.startswith("roborock"):
            raise AssertionError("synchronous optional SDK import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_roborock_import)
    monkeypatch.setattr(
        dock, "find_dock_device", lambda h, v: SimpleNamespace(model_id="7")
    )
    assert dock.dock_profile(None, VACUUM) is None


async def test_prepare_imports_in_executor(hass, provider, monkeypatch):
    """The real registry-selected provider loads its SDK outside the event loop."""
    loop_thread = threading.get_ident()
    called = []
    original = builtins.__import__

    def import_in_worker(name, *args, **kwargs):
        if name in (codes.__name__, features.__name__):
            assert threading.get_ident() != loop_thread
            called.append(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_in_worker)
    await brands.async_prepare_brand_adapter(hass, provider)
    assert called == [codes.__name__, features.__name__]


async def test_missing_sdk_is_retried(hass, provider, monkeypatch):
    """An unavailable provider package must not be cached as a permanent failure."""
    calls = []
    original = builtins.__import__
    monkeypatch.setattr(dock, "_DOCK_TYPES", None)

    def import_after_provider_ready(name, *args, **kwargs):
        if name in (codes.__name__, features.__name__):
            calls.append(name)
            if len(calls) == 1:
                raise ModuleNotFoundError("provider not ready")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_after_provider_ready)
    await brands.async_prepare_brand_adapter(hass, provider)
    assert dock._DOCK_TYPES is None
    await brands.async_prepare_brand_adapter(hass, provider)
    assert dock._DOCK_TYPES is not None
    assert calls == [codes.__name__, codes.__name__, features.__name__]


@pytest.mark.parametrize("platform", ["robovac_mqtt", "unsupported"])
async def test_other_provider_does_not_load_roborock(hass, monkeypatch, platform):
    """A different provider must not initialize the Roborock SDK."""

    original = builtins.__import__

    def unexpected_import(name, *args, **kwargs):
        if name.startswith("roborock"):
            raise AssertionError(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unexpected_import)
    entry = MockConfigEntry(domain=platform)
    entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        "vacuum",
        platform,
        "test-other-provider",
        config_entry=entry,
        suggested_object_id="test_other_provider",
    )
    await brands.async_prepare_brand_adapter(hass, entity.entity_id)
