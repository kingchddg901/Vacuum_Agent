"""Tests for EufyVacuumManager.async_compare_map_sources — the debug compare probe.

`async_compare_map_sources` (core/manager.py) is the P1 VERIFY PROBE: it reads the
fork's IN-MEMORY MapData AND the .storage map_data, and (when both are present) hands
them to ``compare_map_data`` for a field-by-field verdict before repointing the map
source. The method is ADAPTER-DRIVEN off ``map_state_source.memory`` and degrades to a
marker (never raises) on any absence.

It locates its collaborators at call time via local imports:
    from ..mapping import map_source_runtime as _msr
    from ..mapping.map_source import compare_map_data
so the runtime helpers (``eufy_inmem_candidates`` / ``eufy_mapdata_from_candidates`` /
``eufy_store_path`` / ``load_store_json``) and ``compare_map_data`` are monkeypatched on
their defining modules here — the in-memory locate + the .storage file read are exercised
elsewhere; this suite pins the manager's branching contract over their results.

Coverage targets
----------------
[CMP-1] no map_state_source in the adapter config            -> {present:False, reason:not_configured}
[CMP-2] map_state_source present but no `memory` block       -> {present:False, reason:memory_not_configured}
[CMP-3] memory present + storage absent                      -> flags only (no `compare` key)
[CMP-4] memory present + storage present                     -> compare_map_data REACHED, result embedded
[CMP-5] memory ABSENT + storage present                      -> flags only (no `compare` key)
[CMP-6] diagnostics breadcrumb is always passed through from the in-mem locate
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.mapping import map_source as _map_source
from custom_components.eufy_vacuum.mapping import map_source_runtime as _msr


_VAC = "vacuum.alfred"

# A realistic memory block (matches the shape the live adapter declares).
_MEM_CFG = {
    "hass_data_domain": "robovac_mqtt",
    "mapdata_attrs": ["_map_data"],
    "field_attrs": {"room_pixels": "room_pixels"},
}


def _register_source(hass, *, source_cfg):
    """Register a minimal adapter config carrying the given map_state_source value."""
    register_adapter_config(_VAC, {
        "adapter_id": "eufy-test",
        "source": "code",
        "entities": {},
        "map_state_source": source_cfg,
    })


def _patch_helpers(monkeypatch, *, hass, mem_result,
                   store_path="/x/.storage/robovac_mqtt.SER",
                   store_json=None, compare_sentinel=None, register=True):
    """Stub the four runtime locators + compare_map_data the method imports at call time.

    - ``eufy_inmem_candidates`` returns an opaque token (the method passes it straight
      through to ``eufy_mapdata_from_candidates`` — we just assert it was threaded).
    - ``eufy_mapdata_from_candidates`` returns ``mem_result`` (the in-memory verdict).
    - ``eufy_store_path`` returns ``store_path`` (None disables the .storage read).
    - ``load_store_json`` returns ``store_json`` (the raw Store wrapper, off-loop).
    - ``compare_map_data`` returns ``compare_sentinel`` and records its args, so the
      "both present" branch is provably reached with the right operands.

    By default it also registers an adapter config whose ``map_state_source`` carries a
    valid ``memory`` block, so the method runs PAST the config guards into the locators.
    Pass ``register=False`` to register a bespoke config in the test itself.
    """
    if register:
        _register_source(hass, source_cfg={"backend": "storage", "memory": _MEM_CFG})
    threaded: dict = {}

    def _candidates(hass, mem_cfg):
        threaded["candidates_mem_cfg"] = mem_cfg
        return ["CAND"]

    def _mapdata(candidates, *, mapdata_attrs=None, field_attrs=None):
        threaded["mapdata_candidates"] = candidates
        threaded["mapdata_attrs"] = mapdata_attrs
        threaded["field_attrs"] = field_attrs
        return mem_result

    def _store_path(hass, vacuum_entity_id, source_cfg):
        threaded["store_path_vac"] = vacuum_entity_id
        return store_path

    def _load(path):
        threaded["load_path"] = path
        return store_json

    def _compare(memory, storage):
        threaded["compare_args"] = (memory, storage)
        return compare_sentinel

    monkeypatch.setattr(_msr, "eufy_inmem_candidates", _candidates)
    monkeypatch.setattr(_msr, "eufy_mapdata_from_candidates", _mapdata)
    monkeypatch.setattr(_msr, "eufy_store_path", _store_path)
    monkeypatch.setattr(_msr, "load_store_json", _load)
    monkeypatch.setattr(_map_source, "compare_map_data", _compare)
    return threaded


# --- [CMP-1] not configured ------------------------------------------------------

async def test_no_map_state_source_returns_not_configured(hass, manager, monkeypatch):
    """[CMP-1] adapter config without a map_state_source dict -> not_configured."""
    # No map_state_source key at all.
    register_adapter_config(_VAC, {
        "adapter_id": "eufy-test", "source": "code", "entities": {},
    })
    # Helpers must not even be consulted; patch them to blow up if reached.
    monkeypatch.setattr(_msr, "eufy_inmem_candidates",
                        lambda *a, **k: pytest.fail("locator reached on not_configured"))

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "not_configured"}


async def test_map_state_source_not_a_dict_returns_not_configured(hass, manager, monkeypatch):
    """[CMP-1b] a non-dict map_state_source is rejected the same way."""
    _register_source(hass, source_cfg="storage")  # a bare string, not a dict
    monkeypatch.setattr(_msr, "eufy_inmem_candidates",
                        lambda *a, **k: pytest.fail("locator reached on not_configured"))

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "not_configured"}


async def test_unknown_vacuum_returns_not_configured(hass, manager):
    """[CMP-1c] no adapter config registered at all -> not_configured (empty cfg path)."""
    out = await manager.async_compare_map_sources(vacuum_entity_id="vacuum.ghost")
    assert out == {"present": False, "reason": "not_configured"}


# --- [CMP-2] memory not configured ----------------------------------------------

async def test_memory_block_missing_returns_memory_not_configured(hass, manager, monkeypatch):
    """[CMP-2] map_state_source present but no `memory` dict -> memory_not_configured."""
    _register_source(hass, source_cfg={"backend": "storage"})  # no "memory" key
    monkeypatch.setattr(_msr, "eufy_inmem_candidates",
                        lambda *a, **k: pytest.fail("locator reached without a memory block"))

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "memory_not_configured"}


async def test_memory_block_not_a_dict_returns_memory_not_configured(hass, manager, monkeypatch):
    """[CMP-2b] a non-dict `memory` value is rejected the same way."""
    _register_source(hass, source_cfg={"backend": "storage", "memory": True})
    monkeypatch.setattr(_msr, "eufy_inmem_candidates",
                        lambda *a, **k: pytest.fail("locator reached with non-dict memory"))

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "memory_not_configured"}


# --- [CMP-3] memory present, storage absent -> flags only -----------------------

async def test_memory_present_storage_absent_reports_flags_no_compare(hass, manager, monkeypatch):
    """[CMP-3] in-mem present but no .storage file -> presence flags, NO compare key."""
    threaded = _patch_helpers(
        monkeypatch,
        hass=hass,
        mem_result={"present": True, "map_data": {"room_pixels": b"AB"},
                    "diagnostics": {"mapdata_at": "hass_data:robovac_mqtt:._map_data"}},
        store_json=None,   # load_store_json returns None -> storage_present False
    )

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["in_memory_present"] is True
    assert out["storage_present"] is False
    assert out["diagnostics"] == {"mapdata_at": "hass_data:robovac_mqtt:._map_data"}
    assert "compare" not in out
    # compare_map_data must NOT have been called.
    assert "compare_args" not in threaded


async def test_storage_path_none_skips_executor_read(hass, manager, monkeypatch):
    """[CMP-3b] no resolvable store path -> load_store_json never called, storage absent."""
    threaded = _patch_helpers(
        monkeypatch,
        hass=hass,
        mem_result={"present": True, "map_data": {"room_pixels": b"AB"}, "diagnostics": None},
        store_path=None,   # eufy_store_path -> None short-circuits the read
        store_json={"data": {"map_data": {"room_pixels": "ZZ"}}},  # would-be store, unused
    )

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["in_memory_present"] is True
    assert out["storage_present"] is False
    assert "compare" not in out
    assert "load_path" not in threaded  # the executor read was skipped entirely


async def test_storage_json_without_map_data_is_absent(hass, manager, monkeypatch):
    """[CMP-3c] store JSON present but its data.map_data is missing -> storage absent."""
    threaded = _patch_helpers(
        monkeypatch,
        hass=hass,
        mem_result={"present": True, "map_data": {"room_pixels": b"AB"}, "diagnostics": None},
        store_json={"version": 1, "data": {}},  # no map_data under data
    )

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["storage_present"] is False
    assert "compare" not in out
    assert "compare_args" not in threaded


# --- [CMP-4] memory present + storage present -> compare reached -----------------

async def test_both_present_calls_compare_map_data(hass, manager, monkeypatch):
    """[CMP-4] in-mem + .storage both present -> compare_map_data reached, result embedded."""
    mem_md = {"room_pixels": b"MEMORY", "width": 10}
    store_md = {"room_pixels": "STORAGE", "width": 10}
    sentinel = {"normalization_safe": True, "fields": {"width": {"equal": True}}}

    threaded = _patch_helpers(
        monkeypatch,
        hass=hass,
        mem_result={"present": True, "map_data": mem_md,
                    "diagnostics": {"mapdata_at": "runtime_data:e1:._map_data"}},
        store_json={"data": {"map_data": store_md}},
        compare_sentinel=sentinel,
    )

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["in_memory_present"] is True
    assert out["storage_present"] is True
    assert out["diagnostics"] == {"mapdata_at": "runtime_data:e1:._map_data"}
    # The compare branch ran and its verdict is embedded verbatim.
    assert out["compare"] is sentinel
    # ...and it was handed the in-memory map_data and the .storage map_data, in order.
    assert threaded["compare_args"] == (mem_md, store_md)


async def test_both_present_threads_memory_cfg_into_locators(hass, manager, monkeypatch):
    """[CMP-6] the memory block (attrs) + resolved candidates are threaded into the locators."""
    threaded = _patch_helpers(
        monkeypatch,
        hass=hass,
        mem_result={"present": True, "map_data": {"room_pixels": b"X"}, "diagnostics": None},
        store_json={"data": {"map_data": {"room_pixels": "Y"}}},
        compare_sentinel={"normalization_safe": False, "fields": {}},
    )
    _register_source(hass, source_cfg={"backend": "storage", "memory": _MEM_CFG})

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["compare"]["normalization_safe"] is False
    # eufy_inmem_candidates got the memory block; the candidates + attrs flowed onward.
    assert threaded["candidates_mem_cfg"] == _MEM_CFG
    assert threaded["mapdata_candidates"] == ["CAND"]
    assert threaded["mapdata_attrs"] == _MEM_CFG["mapdata_attrs"]
    assert threaded["field_attrs"] == _MEM_CFG["field_attrs"]
    assert threaded["store_path_vac"] == _VAC


async def test_compare_runs_against_real_compare_map_data(hass, manager, monkeypatch):
    """[CMP-4b] end-to-end with the REAL compare_map_data: a clean match -> normalization_safe."""
    raster = b"\x00\x04\x08" * 4
    geom = {
        "width": 10, "height": 10, "origin_x": 0, "origin_y": 0, "resolution": 5,
        "room_outline_width": 10, "room_outline_height": 10,
        "room_outline_origin_x": 0, "room_outline_origin_y": 0,
    }
    mem_md = {"room_pixels": raster, "room_names": {1: "Kitchen"}, **geom}
    store_md = {"room_pixels": raster, "room_names": {"1": "Kitchen"}, **geom}

    # Patch only the locators/IO; leave compare_map_data REAL (compare_sentinel=None never used).
    monkeypatch.setattr(_msr, "eufy_inmem_candidates", lambda hass, cfg: ["C"])
    monkeypatch.setattr(
        _msr, "eufy_mapdata_from_candidates",
        lambda candidates, *, mapdata_attrs=None, field_attrs=None: {
            "present": True, "map_data": mem_md, "diagnostics": None},
    )
    monkeypatch.setattr(_msr, "eufy_store_path", lambda *a, **k: "/x/.storage/k")
    monkeypatch.setattr(_msr, "load_store_json", lambda p: {"data": {"map_data": store_md}})
    _register_source(hass, source_cfg={"backend": "storage", "memory": _MEM_CFG})

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["storage_present"] is True
    cmp = out["compare"]
    # Same raster + identical geometry -> the decoders' fields all match.
    assert cmp["normalization_safe"] is True
    assert cmp["fields"]["room_pixels"]["equal"] is True
    assert cmp["fields"]["width"]["equal"] is True
    # room_names differs only by key type (int vs JSON str) — reported, not a safety break.
    assert cmp["fields"]["room_names"]["equal"] is False
    assert cmp["fields"]["room_names"]["memory_key_types"] != \
        cmp["fields"]["room_names"]["storage_key_types"]


# --- [CMP-5] memory absent + storage present -> flags only ----------------------

async def test_memory_absent_storage_present_no_compare(hass, manager, monkeypatch):
    """[CMP-5] in-mem locate misses but .storage present -> flags only, no compare."""
    threaded = _patch_helpers(
        monkeypatch,
        hass=hass,
        mem_result={"present": False, "reason": "no_mapdata",
                    "diagnostics": {"candidates": []}},
        store_json={"data": {"map_data": {"room_pixels": "ZZ"}}},
    )

    out = await manager.async_compare_map_sources(vacuum_entity_id=_VAC)

    assert out["in_memory_present"] is False
    assert out["storage_present"] is True       # the store side is genuinely present
    assert out["diagnostics"] == {"candidates": []}
    assert "compare" not in out                 # but compare needs BOTH sides
    assert "compare_args" not in threaded
