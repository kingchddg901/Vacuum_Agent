"""Tests for the adapters/ infra — registry, config_loader, config_schema.

Covers the adapter contract surface (high-priority: adapter-degraded paths,
storage contracts): the AdapterCoordinator, the legacy bare-function fallback
shims (no-coordinator path), adapter validation, and the stored-config loader.

Coverage targets
----------------
[RG-1]  AdapterCoordinator register/get/get_all/unregister/clear/get_adapter_value.
[RG-2]  AdapterCoordinator construct sets active pointer; shutdown clears it.
[RG-3]  register with invalid mapping logs but still stores; non-dict raises.
[RG-4]  _validate_adapter: valid, mapping-not-dict, missing/unknown engine, noop ok.
[RG-5]  bare-function fallback shims operate on _REGISTRY when no coordinator.
[CL-1]  load_stored_adapter_configs: non-dict store → 0; malformed skipped; counts.
[CL-2]  load_stored_adapter_configs: register exception is swallowed.
[CL-3]  save / delete / get_stored_adapter_config round-trip.
[CS-1]  ADAPTER_CONFIG_SCHEMA is importable and has the required top-level keys.
"""

from __future__ import annotations

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.eufy_vacuum.adapters.registry as reg
from custom_components.eufy_vacuum.adapters import config_loader as cl
from custom_components.eufy_vacuum.adapters.config_schema import ADAPTER_CONFIG_SCHEMA
from custom_components.eufy_vacuum.adapters.registry import (
    AdapterCoordinator,
    _validate_adapter,
    clear_registry,
    get_active_coordinator,
    register_adapter_config,
)
from custom_components.eufy_vacuum.const import DOMAIN


_VAC = "vacuum.alfred"


@pytest.fixture(autouse=True)
def _preserve_registry():
    """Snapshot + reset the module-level registry globals around each test."""
    prev = reg._active_coordinator
    snap = dict(reg._REGISTRY)
    reg._set_active_coordinator(None)
    reg._REGISTRY.clear()
    yield
    reg._set_active_coordinator(prev)
    reg._REGISTRY.clear()
    reg._REGISTRY.update(snap)


def _coord(hass):
    return AdapterCoordinator(hass, MockConfigEntry(domain=DOMAIN))


# ---------------------------------------------------------------------------
# AdapterCoordinator
# ---------------------------------------------------------------------------

def test_coordinator_crud(hass):
    """[RG-1]"""
    c = _coord(hass)
    c.register_adapter_config(_VAC, {"adapter_id": "a", "source": "code"})
    assert c.get_adapter_config(_VAC)["adapter_id"] == "a"
    assert _VAC in c.get_all_adapter_configs()
    assert c.get_adapter_value(_VAC, "adapter_id") == "a"
    assert c.get_adapter_value(_VAC, "nope", fallback="d") == "d"
    assert c.get_adapter_value(_VAC, "adapter_id", "deeper", fallback="d") == "d"
    c.unregister_adapter_config(_VAC)
    assert c.get_adapter_config(_VAC) is None
    c.register_adapter_config(_VAC, {"adapter_id": "a"})
    c.clear_registry()
    assert c.get_all_adapter_configs() == {}
    c.shutdown()


def test_coordinator_active_pointer(hass):
    """[RG-2]"""
    assert get_active_coordinator() is None
    c = _coord(hass)
    assert get_active_coordinator() is c
    c.shutdown()
    assert get_active_coordinator() is None
    c.shutdown()  # idempotent


def test_coordinator_invalid_and_nondict(hass):
    """[RG-3] unknown segmenter engine logs but still stores; non-dict raises."""
    c = _coord(hass)
    c.register_adapter_config(_VAC, {
        "adapter_id": "a", "mapping": {"segmenter_engine": "does_not_exist"}})
    # invalid mapping is a warning, not fatal — config is still stored
    assert c.get_adapter_config(_VAC) is not None
    with pytest.raises(TypeError):
        c.register_adapter_config(_VAC, "not-a-dict")
    c.shutdown()


# ---------------------------------------------------------------------------
# _validate_adapter
# ---------------------------------------------------------------------------

def test_validate_adapter():
    """[RG-4]"""
    assert _validate_adapter({"adapter_id": "a"}) == []
    assert _validate_adapter("nope") == ["adapter config must be a dict"]
    assert "'mapping' must be a dict if present" in _validate_adapter(
        {"mapping": "x"})
    # mapping present but no engine declared
    assert any("segmenter_engine is required" in i
               for i in _validate_adapter({"mapping": {}}))
    # unknown engine name
    assert any("is unknown" in i for i in _validate_adapter(
        {"mapping": {"segmenter_engine": "bogus_engine"}}))
    # a real engine passes validation
    assert _validate_adapter(
        {"mapping": {"segmenter_engine": "noop_fallback"}}) == []


def test_validate_adapter_job_segmenter_block():
    """[RG-4] job_segmenter block is the 2nd-brand JobSegmenter seam contract.

    A declared block that is not-a-dict / omits the engine / names an unknown
    engine must surface a checked issue (so registration rejects a brand that
    would otherwise silently fall back to the Eufy counter engine), mirroring
    the mapping.segmenter_engine contract. The declared 'noop_job_fallback'
    sentinel must pass clean.
    """
    # block present but not a dict
    assert "'job_segmenter' must be a dict if present" in _validate_adapter(
        {"job_segmenter": "x"})
    # block present but no engine declared
    assert any("job_segmenter.engine is required" in i
               for i in _validate_adapter({"job_segmenter": {}}))
    # unknown engine name
    assert any("is unknown" in i for i in _validate_adapter(
        {"job_segmenter": {"engine": "bogus_job_engine"}}))
    # the documented disable sentinel passes validation
    assert _validate_adapter(
        {"job_segmenter": {"engine": "noop_job_fallback"}}) == []


# ---------------------------------------------------------------------------
# bare-function fallback shims (no active coordinator)
# ---------------------------------------------------------------------------

def test_fallback_shims():
    """[RG-5] with no coordinator active, shims operate on _REGISTRY."""
    assert get_active_coordinator() is None  # _preserve set it None
    reg.register_adapter_config(_VAC, {"adapter_id": "a", "source": "code"})
    assert reg.get_adapter_config(_VAC)["adapter_id"] == "a"
    assert _VAC in reg.get_all_adapter_configs()
    assert reg.get_adapter_value(_VAC, "adapter_id") == "a"
    assert reg.get_adapter_value(_VAC, "missing", fallback="d") == "d"
    reg.unregister_adapter_config(_VAC)
    assert reg.get_adapter_config(_VAC) is None
    reg.register_adapter_config(_VAC, {"adapter_id": "a"})
    reg.clear_registry()
    assert reg.get_all_adapter_configs() == {}


def test_fallback_register_nondict_raises():
    """[RG-5] fallback path also rejects non-dict configs."""
    with pytest.raises(TypeError):
        reg.register_adapter_config(_VAC, "not-a-dict")


# ---------------------------------------------------------------------------
# config_loader
# ---------------------------------------------------------------------------

def test_load_stored_configs(hass):
    """[CL-1]"""
    assert cl.load_stored_adapter_configs(hass, {"adapters": "not-a-dict"}) == 0
    data = {"adapters": {
        _VAC: {"adapter_id": "a", "source": "config"},
        "vacuum.bad": "malformed",   # non-dict → skipped
    }}
    assert cl.load_stored_adapter_configs(hass, data) == 1
    assert reg.get_adapter_config(_VAC)["adapter_id"] == "a"


def test_load_stored_configs_register_raises(hass, monkeypatch):
    """[CL-2] a register failure is logged and skipped, not propagated."""
    def _boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(cl, "register_adapter_config", _boom)
    data = {"adapters": {_VAC: {"adapter_id": "a"}}}
    assert cl.load_stored_adapter_configs(hass, data) == 0


def test_save_delete_get_stored():
    """[CL-3]"""
    data: dict = {}
    cl.save_adapter_config(data, _VAC, {"adapter_id": "a"})
    assert cl.get_stored_adapter_config(data, _VAC)["adapter_id"] == "a"
    assert cl.delete_adapter_config(data, _VAC) is True
    assert cl.get_stored_adapter_config(data, _VAC) is None
    assert cl.delete_adapter_config(data, _VAC) is False


# ---------------------------------------------------------------------------
# config_schema
# ---------------------------------------------------------------------------

def test_schema_shape():
    """[CS-1]"""
    for key in ("adapter_id", "source", "entities", "dispatch"):
        assert key in ADAPTER_CONFIG_SCHEMA
    assert ADAPTER_CONFIG_SCHEMA["adapter_id"]["required"] is True


# --- RC-4: an omitted engine block resolves to EUFY, and must say so ----------

def _minimal(**extra):
    """The smallest registerable config, plus whatever blocks the test declares."""
    return {
        "adapter_id": "brand3", "source": "code",
        "entities": {}, "dispatch": {},
        **extra,
    }


def test_omitting_an_engine_block_warns_which_eufy_default_takes_over(caplog):
    """[RC-4] Every permissive default in this framework resolves to a concrete EUFY
    answer rather than to a refusal.

    A brand-3 config assembled from the schema silently runs Eufy's counter-plateau
    segmenter and anchor-winding attribution against a device that emits neither signal:
    no crash, no warning, wrong learned boundaries. The engine resolvers already warn on
    an UNKNOWN name, but an ABSENT block was silent — a resolver only receives a name and
    cannot tell "no adapter at all" (legacy, fine) from "an adapter omitted this".

    At registration the whole config is in hand, so the difference is knowable there.
    """
    import logging
    caplog.set_level(logging.WARNING)
    clear_registry()

    register_adapter_config("vacuum.brand3", _minimal())

    text = caplog.text
    for block, eufy_default in (
        ("mapping", "eufy_cv_v1"),
        ("job_segmenter", "eufy_counter_v1"),
        ("room_attribution", "eufy_anchor_winding_v1"),
    ):
        assert block in text, f"no advisory for the omitted {block!r} block"
        assert eufy_default in text, (
            f"the {block!r} advisory does not name the Eufy default it falls back to"
        )
    # The advisory must tell the porter how to opt OUT, not just that it happened.
    assert "noop_job_fallback" in text and "noop_room_attribution" in text


def test_declaring_the_blocks_is_silent(caplog):
    """[RC-4] Both shipped brands declare all three, so this must be silent on every real
    install today — an advisory that fires for correct configs is noise, and noise is how
    a real warning gets ignored."""
    import logging
    caplog.set_level(logging.WARNING)
    clear_registry()

    register_adapter_config("vacuum.brand3", _minimal(
        mapping={"segmenter_engine": "noop_fallback"},
        job_segmenter={"engine": "noop_job_fallback"},
        room_attribution={"engine": "noop_room_attribution"},
    ))

    for block in ("mapping", "job_segmenter", "room_attribution"):
        assert f"declares no '{block}' block" not in caplog.text


def test_an_unknown_capability_hint_is_reported_not_ignored():
    """[RC-3] A hint key the reader does not know is a SILENT no-op.

    `_hints.get(name)` misses and the derived/default value stands, so a typo is
    indistinguishable from declaring nothing — a brand saying "I categorically cannot do
    this" gets ignored exactly as thoroughly as a brand saying nothing. That is the same
    silent-wrong-answer shape `_hint_wins` exists to prevent, one level up.
    """
    issues = _validate_adapter({
        "adapter_id": "brand3", "source": "code", "entities": {}, "dispatch": {},
        "capability_hints": {"supports_zone_cleen": False, "supports_passes": True},
    })
    # Exactly one issue, and it names the typo as its SUBJECT. Checked by count rather
    # than by substring: every message also prints the valid-key list, so `"supports_passes"
    # in issue` is true for the typo's own message too.
    assert len(issues) == 1, issues
    assert issues[0].startswith("capability_hints.'supports_zone_cleen'"), issues[0]


def test_known_capability_hints_matches_what_the_module_actually_reads():
    """[RC-3] The gate is only as good as its key set, and that set is hand-maintained.

    Derive the truth from the source instead of trusting the list: every `_hints` read in
    capabilities.py must appear in KNOWN_CAPABILITY_HINTS, and vice versa. Without this a
    newly-added hint would be rejected as a typo, which is a worse failure than the one
    the gate fixes.
    """
    import inspect
    import re

    from custom_components.eufy_vacuum.core import capabilities as caps_mod
    from custom_components.eufy_vacuum.core.capabilities import KNOWN_CAPABILITY_HINTS

    src = inspect.getsource(caps_mod)
    read = set(re.findall(r'_hints(?:\.get\(|\[)"([a-z_]+)"', src))
    read |= set(re.findall(r'_hint_wins\("([a-z_]+)"', src))

    assert read == set(KNOWN_CAPABILITY_HINTS), (
        f"KNOWN_CAPABILITY_HINTS drifted from the reads:\n"
        f"  read but undeclared: {sorted(read - set(KNOWN_CAPABILITY_HINTS))}\n"
        f"  declared but unread: {sorted(set(KNOWN_CAPABILITY_HINTS) - read)}"
    )
