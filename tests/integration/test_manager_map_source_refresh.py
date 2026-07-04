"""Tests for the map_state_source REFRESH dispatcher + render / object readers.

Closes the MapSourceCoordinator coverage gap left by the manager re-bundle: the
existing CMP-*/LP-* tests cover ``async_compare_map_sources`` + the live-pose
seam, but the central pre-warm dispatcher (``async_refresh_map_state_source``) and
its storage / memory-primary backends, ``get_live_mapdata_obj`` (zone dispatch),
and ``async_get_map_render_data`` (the card's own-render fetch) were untested.

The ``map_source_runtime`` (`_msr`) helpers, the two ``map_source`` converters, and
the module-level ``_stat_mtime`` are monkeypatched to inject canned provider data,
so the assertions exercise the coordinator's REAL dispatch / cache / fallback
branching — not the parsers (those are unit-tested separately).

Coverage targets
----------------
[MSD-1]  refresh: no map_state_source block -> not_configured, cached.
[MSD-2]  refresh: backend=storage (no memory) -> storage branch + cache mtime/gate.
[MSD-3]  refresh: storage, no device path -> no_device, cached.
[MSD-4]  refresh: storage mtime+gate unchanged -> cached result reused (no re-parse).
[MSD-5]  refresh: store version mismatch -> warned, result passed through.
[MSD-6]  refresh: backend=storage + memory block -> memory-primary (eufy) branch.
[MSD-7]  refresh: memory-primary miss -> falls back to the .storage read.
[MSD-8]  refresh: memory-primary version-cache hit -> reuses scan, no re-convert.
[MSD-9]  refresh: memory-primary convert returns None -> falls back to .storage.
[MSD-10] refresh: present=False (no live image) -> memory branch sees live_map_absent
         and falls back to storage.
[MSD-11] refresh: backend=memory (Roborock introspect) -> result + cache.
[MSD-12] refresh: unknown backend -> unknown_backend marker, cached.
[MSD-13] refresh: a backend raising -> caught, refresh_error marker, cached.
[GLM-1]  get_live_mapdata_obj: not configured -> None.
[GLM-2]  get_live_mapdata_obj: backend=memory -> first found MapData object.
[GLM-3]  get_live_mapdata_obj: backend=storage+memory -> object from candidates.
[GLM-4]  get_live_mapdata_obj: an introspector raising -> None (caller refuses).
[RND-1]  render_data: no map_render block -> not_configured.
[RND-2]  render_data: unknown format / non-storage backend -> unknown_format.
[RND-3]  render_data: memory-primary present -> render data from the in-memory map.
[RND-4]  render_data: memory absent -> .storage fallback.
[RND-5]  render_data: storage, no device path -> no_device.
[RND-6]  render_data: roborock map_render format -> the raw-map render bridge + room names.
[RIP-1]  _read_inmem_pose: locates candidates + returns the parsed live pose.
[LPG-1]  _load_live_pose_geom: full read -> map_data extracted + cached by mtime.
[LPG-2]  _load_live_pose_geom: unchanged mtime -> cached map_data reused, no re-read.
[LPG-3]  _load_live_pose_geom: store JSON without a map_data dict -> None.
[LKG-1]  _commit_result: present then transient-absent (same map) -> holds last-good, stamped stale.
[LKG-2]  _commit_result: held then a new present result -> replaced, stale flags cleared.
[LKG-3]  _commit_result: transient-absent with a DIFFERENT map_id -> not held (absent written).
[LKG-4]  _commit_result: absent with a hard-clear reason (live_map_absent) -> not held.
[LKG-5]  _commit_result: a held map aged past the TTL -> not held (absent written).
[LKG-6]  _commit_result: stale_since is set ONCE across repeated holds.
[LKG-7]  _commit_result: transient-absent with no prior present cache -> written as-is.
[LKG-8]  refresh (Roborock memory): a present read then no_parsed_map -> the held map is served.
"""

from __future__ import annotations

import time
from typing import Any

from custom_components.eufy_vacuum.adapters.registry import register_adapter_config
from custom_components.eufy_vacuum.mapping import map_source
from custom_components.eufy_vacuum.mapping import map_source_coordinator as msc
from custom_components.eufy_vacuum.mapping import map_source_runtime as msr

_VAC = "vacuum.alfred"


def _register(*, source: dict | None = None, render: dict | None = None) -> None:
    cfg: dict[str, Any] = {"adapter_id": "eufy", "source": "code", "entities": {}}
    if source is not None:
        cfg["map_state_source"] = source
    if render is not None:
        cfg["map_render"] = render
    register_adapter_config(_VAC, cfg)


def _present(manager, monkeypatch, image: str | None = "camera.alfred_map") -> None:
    """Force the live-map presence gate to a known value."""
    monkeypatch.setattr(
        manager, "_resolve_live_map_image_entity", lambda **k: image
    )


# ---------------------------------------------------------------------------
# async_refresh_map_state_source — dispatch
# ---------------------------------------------------------------------------

async def test_refresh_not_configured(manager):
    """[MSD-1] no map_state_source -> not_configured, written to the cache."""
    _register(source=None)
    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out == {"present": False, "reason": "not_configured"}
    cached = manager._map_state_source_cache[_VAC]
    assert cached["result"] == out and cached["map_id"] == "6"


async def test_refresh_storage_plain(manager, monkeypatch):
    """[MSD-2] backend=storage (no memory) -> storage branch, cache carries mtime+gate."""
    _register(source={"backend": "storage"})
    _present(manager, monkeypatch)
    result = {"present": True, "backend": "storage", "rooms": [{"number": 1}]}
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 111.0)
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {"map_data": {}}})
    monkeypatch.setattr(
        msr, "eufy_result_from_store", lambda *a, **k: dict(result)
    )

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out == result
    cached = manager._map_state_source_cache[_VAC]
    assert cached["mtime"] == 111.0 and cached["present_gate"] is True


async def test_refresh_storage_no_device(manager, monkeypatch):
    """[MSD-3] storage with no resolvable device path -> no_device, cached."""
    _register(source={"backend": "storage"})
    _present(manager, monkeypatch)
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "")

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out == {"present": False, "backend": "storage", "reason": "no_device"}
    assert manager._map_state_source_cache[_VAC]["result"] == out


async def test_refresh_storage_cache_hit(manager, monkeypatch):
    """[MSD-4] unchanged mtime + same present gate -> the cached result is reused."""
    _register(source={"backend": "storage"})
    _present(manager, monkeypatch)
    cached_result = {"present": True, "rooms": [{"number": 9}], "from": "cache"}
    manager._map_state_source_cache[_VAC] = {
        "mtime": 222.0, "present_gate": True, "map_id": "6", "result": cached_result,
    }
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 222.0)  # unchanged

    def _boom(*a, **k):  # pragma: no cover - asserts no re-parse
        raise AssertionError("load_store_json called on a cache hit")

    monkeypatch.setattr(msr, "load_store_json", _boom)

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out is cached_result


async def test_refresh_storage_version_mismatch_warns(manager, monkeypatch):
    """[MSD-5] a store_version_mismatch result is logged and passed through."""
    _register(source={"backend": "storage", "store_version": 3})
    _present(manager, monkeypatch)
    mismatch = {"present": False, "reason": "store_version_mismatch"}
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 1.0)
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {}})
    monkeypatch.setattr(
        msr, "eufy_result_from_store", lambda *a, **k: dict(mismatch)
    )

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out["reason"] == "store_version_mismatch"


async def test_refresh_memory_primary(manager, monkeypatch):
    """[MSD-6] backend=storage + memory block -> memory-primary scan (no .storage read)."""
    _register(source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}})
    _present(manager, monkeypatch)
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(
        msr, "eufy_mapdata_obj_from_candidates",
        lambda *a, **k: {"present": True, "version": "v1", "obj": object()},
    )
    monkeypatch.setattr(map_source, "mapdata_dict_from_obj", lambda *a, **k: {"width": 100})
    monkeypatch.setattr(
        msr, "eufy_result_from_mapdata",
        lambda *a, **k: {"present": True, "rooms": [{"number": 2}], "src": "memory"},
    )

    def _no_storage(*a, **k):  # pragma: no cover - asserts memory path, not storage
        raise AssertionError("fell through to the .storage read")

    monkeypatch.setattr(msr, "eufy_store_path", _no_storage)

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out["src"] == "memory" and out["rooms"] == [{"number": 2}]
    # The static scan was cached by content version for re-use.
    assert manager.map_source._mem_rooms_cache[_VAC]["version"] == "v1"


async def test_refresh_memory_miss_falls_back_to_storage(manager, monkeypatch):
    """[MSD-7] in-memory map absent -> falls back to the .storage read."""
    _register(source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}})
    _present(manager, monkeypatch)
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: [])
    monkeypatch.setattr(
        msr, "eufy_mapdata_obj_from_candidates",
        lambda *a, **k: {"present": False, "reason": "no_inmem"},
    )
    # Storage fallback is reached:
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 5.0)
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {}})
    monkeypatch.setattr(
        msr, "eufy_result_from_store",
        lambda *a, **k: {"present": True, "src": "storage_fallback"},
    )

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out["src"] == "storage_fallback"


async def test_refresh_memory_version_cache_hit(manager, monkeypatch):
    """[MSD-8] same content version -> reuse the cached scan, never re-convert."""
    _register(source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}})
    _present(manager, monkeypatch)
    static = {"present": True, "rooms": [{"number": 7}], "src": "cached_scan"}
    manager.map_source._mem_rooms_cache[_VAC] = {
        "version": "v9", "result": static, "map_data": {"width": 1},
    }
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(
        msr, "eufy_mapdata_obj_from_candidates",
        lambda *a, **k: {"present": True, "version": "v9", "obj": object()},
    )

    def _boom(*a, **k):  # pragma: no cover - asserts the scan is reused
        raise AssertionError("re-converted on a version cache hit")

    monkeypatch.setattr(map_source, "mapdata_dict_from_obj", _boom)

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out["src"] == "cached_scan" and out["rooms"] == [{"number": 7}]


async def test_refresh_memory_convert_none_falls_back(manager, monkeypatch):
    """[MSD-9] convert returns None -> falls back to the .storage read."""
    _register(source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}})
    _present(manager, monkeypatch)
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(
        msr, "eufy_mapdata_obj_from_candidates",
        lambda *a, **k: {"present": True, "version": "v1", "obj": object()},
    )
    monkeypatch.setattr(map_source, "mapdata_dict_from_obj", lambda *a, **k: None)
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 5.0)
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {}})
    monkeypatch.setattr(
        msr, "eufy_result_from_store", lambda *a, **k: {"present": True, "src": "fallback"},
    )

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out["src"] == "fallback"


async def test_refresh_memory_present_false_falls_back(manager, monkeypatch):
    """[MSD-10] no live image -> present=False -> memory sees live_map_absent -> storage."""
    _register(source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}})
    _present(manager, monkeypatch, image=None)  # gate fails -> present False
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 5.0)
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {}})
    monkeypatch.setattr(
        msr, "eufy_result_from_store",
        lambda *a, present, **k: {"present": present, "src": "storage"},
    )

    def _boom(*a, **k):  # pragma: no cover - in-memory must not be consulted when absent
        raise AssertionError("read in-memory map despite an absent live image")

    monkeypatch.setattr(msr, "eufy_inmem_candidates", _boom)

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out["src"] == "storage" and out["present"] is False


async def test_refresh_memory_backend_roborock(manager, monkeypatch):
    """[MSD-11] backend=memory -> Roborock introspect; dispatcher caches the result."""
    _register(source={"backend": "memory"})
    _present(manager, monkeypatch)
    monkeypatch.setattr(msr, "roborock_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(
        msr, "roborock_result_from_candidates",
        lambda c, present: {"present": present, "src": "roborock", "diagnostics": {"x": 1}},
    )

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="m"
    )
    assert out["src"] == "roborock" and out["present"] is True
    cached = manager._map_state_source_cache[_VAC]
    assert cached["map_id"] == "m" and cached["result"] == out


async def test_refresh_unknown_backend(manager, monkeypatch):
    """[MSD-12] an unrecognized backend -> a clear marker, cached."""
    _register(source={"backend": "wat"})
    _present(manager, monkeypatch)
    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out == {"present": False, "reason": "unknown_backend:wat"}
    assert manager._map_state_source_cache[_VAC]["result"] == out


async def test_refresh_backend_raises_degrades(manager, monkeypatch):
    """[MSD-13] a backend that raises -> caught; never propagates out of the pre-warm."""
    _register(source={"backend": "memory"})
    _present(manager, monkeypatch)

    def _raise(*a, **k):
        raise RuntimeError("introspector blew up")

    monkeypatch.setattr(msr, "roborock_candidates", _raise)

    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="6"
    )
    assert out == {"present": False, "reason": "refresh_error"}
    assert manager._map_state_source_cache[_VAC]["result"] == out


# ---------------------------------------------------------------------------
# get_live_mapdata_obj — zone-dispatch object locator
# ---------------------------------------------------------------------------

def test_get_live_mapdata_obj_not_configured(manager):
    """[GLM-1] no map_state_source -> None (caller must refuse to dispatch)."""
    _register(source=None)
    assert manager.map_source.get_live_mapdata_obj(vacuum_entity_id=_VAC, map_id="6") is None


def test_get_live_mapdata_obj_memory_backend(manager, monkeypatch):
    """[GLM-2] backend=memory -> the first non-None MapData object from candidates."""
    _register(source={"backend": "memory"})
    monkeypatch.setattr(manager, "_resolve_live_map_image_entity", lambda **k: "camera.x")
    md = object()
    monkeypatch.setattr(msr, "roborock_candidates", lambda *a, **k: [("h", "p", "root")])
    monkeypatch.setattr(msr, "find_mapdata", lambda root: (md, "path"))

    assert manager.map_source.get_live_mapdata_obj(vacuum_entity_id=_VAC, map_id="6") is md


def test_get_live_mapdata_obj_storage_memory(manager, monkeypatch):
    """[GLM-3] backend=storage + memory -> object from the in-memory candidates."""
    _register(source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}})
    obj = object()
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(
        msr, "eufy_mapdata_obj_from_candidates",
        lambda *a, **k: {"present": True, "obj": obj},
    )
    assert manager.map_source.get_live_mapdata_obj(vacuum_entity_id=_VAC, map_id="6") is obj


def test_get_live_mapdata_obj_raises_returns_none(manager, monkeypatch):
    """[GLM-4] an introspector that raises -> None (never breaks dispatch)."""
    _register(source={"backend": "memory"})
    monkeypatch.setattr(manager, "_resolve_live_map_image_entity", lambda **k: "camera.x")

    def _raise(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(msr, "roborock_candidates", _raise)
    assert manager.map_source.get_live_mapdata_obj(vacuum_entity_id=_VAC, map_id="6") is None


# ---------------------------------------------------------------------------
# async_get_map_render_data — the card's own-render fetch
# ---------------------------------------------------------------------------

async def test_render_data_not_configured(manager):
    """[RND-1] no map_render block -> not_configured."""
    _register(source={"backend": "storage"})  # render absent
    out = await manager.map_source.async_get_map_render_data(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "not_configured"}


async def test_render_data_unknown_format(manager):
    """[RND-2] a format the core can't decode -> unknown_format."""
    _register(source={"backend": "storage"}, render={"format": "mystery_v9"})
    out = await manager.map_source.async_get_map_render_data(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "unknown_format:mystery_v9"}


async def test_render_data_memory_primary(manager, monkeypatch):
    """[RND-3] memory-primary -> render data from the fresh in-memory map (no file read)."""
    _register(
        source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}},
        render={"format": "eufy_room_pixels_v1"},
    )
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(
        msr, "eufy_mapdata_from_candidates",
        lambda *a, **k: {"present": True, "map_data": {"width": 8}},
    )
    monkeypatch.setattr(
        map_source, "render_data_from_storage",
        lambda md: {"present": True, "src": "memory", "width": md["width"]},
    )

    def _boom(*a, **k):  # pragma: no cover - asserts no .storage read
        raise AssertionError("read .storage despite a present in-memory map")

    monkeypatch.setattr(msr, "eufy_store_path", _boom)

    out = await manager.map_source.async_get_map_render_data(vacuum_entity_id=_VAC)
    assert out == {"present": True, "src": "memory", "width": 8}


async def test_render_data_storage_fallback(manager, monkeypatch):
    """[RND-4] in-memory absent -> the .storage render-data read."""
    _register(
        source={"backend": "storage", "memory": {"mapdata_attrs": ["_map_data"]}},
        render={"format": "eufy_room_pixels_v1"},
    )
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: [])
    monkeypatch.setattr(
        msr, "eufy_mapdata_from_candidates", lambda *a, **k: {"present": False},
    )
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {}})
    monkeypatch.setattr(
        msr, "eufy_render_data_from_store",
        lambda *a, **k: {"present": True, "src": "storage"},
    )

    out = await manager.map_source.async_get_map_render_data(vacuum_entity_id=_VAC)
    assert out == {"present": True, "src": "storage"}


async def test_render_data_storage_no_device(manager, monkeypatch):
    """[RND-5] storage path with no device -> no_device."""
    _register(
        source={"backend": "storage"},  # no memory block -> straight to storage
        render={"format": "eufy_room_pixels_v1"},
    )
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "")
    out = await manager.map_source.async_get_map_render_data(vacuum_entity_id=_VAC)
    assert out == {"present": False, "reason": "no_device"}


# ---------------------------------------------------------------------------
# _read_inmem_pose / _load_live_pose_geom — the live-pose read layer
# ---------------------------------------------------------------------------

def test_read_inmem_pose_returns_pose(manager, monkeypatch):
    """[RIP-1] locates candidates and returns the parser's pose verbatim."""
    pose = {"present": True, "robot_pixel": [1, 2], "diagnostics": {"pose_at": "x"}}
    monkeypatch.setattr(msr, "eufy_inmem_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(msr, "eufy_live_pose_from_candidates", lambda *a, **k: dict(pose))
    out = manager.map_source._read_inmem_pose(_VAC, {"robot_pixel_attrs": ["robot_pixel"]})
    assert out == pose


async def test_load_live_pose_geom_reads_and_caches(manager, monkeypatch):
    """[LPG-1] full read: the store's map_data is extracted and cached by mtime."""
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 7.0)
    monkeypatch.setattr(
        msr, "load_store_json", lambda p: {"data": {"map_data": {"width": 50}}}
    )
    out = await manager.map_source._load_live_pose_geom(_VAC, {"backend": "storage"})
    assert out == {"width": 50}
    assert manager.map_source._live_pose_geom_cache[_VAC] == {
        "mtime": 7.0, "map_data": {"width": 50},
    }


async def test_load_live_pose_geom_cache_hit(manager, monkeypatch):
    """[LPG-2] unchanged mtime -> the cached map_data is reused, store not re-read."""
    manager.map_source._live_pose_geom_cache[_VAC] = {
        "mtime": 9.0, "map_data": {"cached": True},
    }
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 9.0)

    def _boom(*a, **k):  # pragma: no cover - asserts no re-read on a geom cache hit
        raise AssertionError("load_store_json called on a geom cache hit")

    monkeypatch.setattr(msr, "load_store_json", _boom)
    out = await manager.map_source._load_live_pose_geom(_VAC, {"backend": "storage"})
    assert out == {"cached": True}


async def test_load_live_pose_geom_no_map_data(manager, monkeypatch):
    """[LPG-3] a store JSON without a map_data dict -> None."""
    monkeypatch.setattr(msr, "eufy_store_path", lambda *a, **k: "/x/store.json")
    monkeypatch.setattr(msc, "_stat_mtime", lambda p: 1.0)
    monkeypatch.setattr(msr, "load_store_json", lambda p: {"data": {}})
    out = await manager.map_source._load_live_pose_geom(_VAC, {"backend": "storage"})
    assert out is None


# ---------------------------------------------------------------------------
# _commit_result — last-known-good map retention (hold a present map through a
# TRANSIENT source dropout, e.g. a Roborock cloud map going unavailable on idle)
# ---------------------------------------------------------------------------

_PRESENT = {"present": True, "backend": "memory", "rooms": [{"number": 1}]}
_ABSENT = {"present": False, "reason": "no_parsed_map"}


def test_commit_result_holds_last_good(manager):
    """[LKG-1] a transient-absent result does NOT drop a present map for the same map_id;
    the last-good is kept and stamped stale."""
    co = manager.map_source
    co._commit_result(_VAC, "6", dict(_PRESENT))
    out = co._commit_result(_VAC, "6", dict(_ABSENT))

    assert out["present"] is True and out["rooms"] == [{"number": 1}]     # held, not dropped
    assert out["stale"] is True and out["stale_reason"] == "no_parsed_map"
    assert isinstance(out["stale_since"], float)
    assert manager._map_state_source_cache[_VAC]["result"]["stale"] is True


def test_commit_result_replaced_by_new_present(manager):
    """[LKG-2] a genuinely NEW present result always replaces a held map (stale cleared)."""
    co = manager.map_source
    co._commit_result(_VAC, "6", dict(_PRESENT))
    co._commit_result(_VAC, "6", dict(_ABSENT))                      # holds -> stale
    fresh = {"present": True, "backend": "memory", "rooms": [{"number": 2}]}
    out = co._commit_result(_VAC, "6", dict(fresh))

    assert out["rooms"] == [{"number": 2}] and "stale" not in out
    assert manager._map_state_source_cache[_VAC]["result"] == fresh


def test_commit_result_different_map_not_held(manager):
    """[LKG-3] the sticky rule is map-scoped: an absent read for a DIFFERENT map_id never
    serves map 6's geometry -> the absent marker is written."""
    co = manager.map_source
    co._commit_result(_VAC, "6", dict(_PRESENT))
    out = co._commit_result(_VAC, "7", dict(_ABSENT))               # different map

    assert out == _ABSENT
    cached = manager._map_state_source_cache[_VAC]
    assert cached["map_id"] == "7" and cached["result"] == _ABSENT


def test_commit_result_hard_clear_not_held(manager):
    """[LKG-4] a STRUCTURAL absent reason (the live-map entity removed) clears the held map
    rather than pinning it."""
    co = manager.map_source
    co._commit_result(_VAC, "6", dict(_PRESENT))
    out = co._commit_result(_VAC, "6", {"present": False, "reason": "live_map_absent"})

    assert out == {"present": False, "reason": "live_map_absent"}
    assert manager._map_state_source_cache[_VAC]["result"]["present"] is False


def test_commit_result_ttl_expiry(manager):
    """[LKG-5] a map held past the TTL ages out -> the next absent read clears it."""
    co = manager.map_source
    old = time.time() - msc._STALE_MAP_TTL_SECONDS - 10
    manager._map_state_source_cache[_VAC] = {
        "mtime": None, "map_id": "6",
        "result": {"present": True, "rooms": [{"number": 1}],
                   "stale": True, "stale_since": old},
    }
    out = co._commit_result(_VAC, "6", dict(_ABSENT))

    assert out == _ABSENT                                            # aged out — no longer held
    assert manager._map_state_source_cache[_VAC]["result"] == _ABSENT


def test_commit_result_stale_since_set_once(manager):
    """[LKG-6] stale_since is stamped once, so 'held for N min' + the TTL stay accurate
    across repeated holds."""
    co = manager.map_source
    co._commit_result(_VAC, "6", dict(_PRESENT))
    first = co._commit_result(_VAC, "6", dict(_ABSENT))
    since1 = first["stale_since"]
    second = co._commit_result(_VAC, "6", {"present": False, "reason": "no_room_geometry"})

    assert second["stale_since"] == since1                          # reused, not reset
    assert second["stale_reason"] == "no_room_geometry"


def test_commit_result_no_prior_present(manager):
    """[LKG-7] with no prior present map there is nothing to hold -> the absent marker is
    written as-is."""
    co = manager.map_source
    out = co._commit_result(_VAC, "6", dict(_ABSENT))
    assert out == _ABSENT
    assert manager._map_state_source_cache[_VAC]["result"] == _ABSENT


async def test_refresh_holds_roborock_map_on_idle_drop(manager, monkeypatch):
    """[LKG-8] end-to-end: a Roborock memory read that goes present -> no_parsed_map (the
    'Ivy idles and the cloud map entity drops' case) serves the HELD map, not empty."""
    _register(source={"backend": "memory"})
    _present(manager, monkeypatch)
    monkeypatch.setattr(msr, "roborock_candidates", lambda *a, **k: ["cand"])

    monkeypatch.setattr(                                             # first read: map present
        msr, "roborock_result_from_candidates",
        lambda c, present: {"present": True, "src": "roborock", "rooms": [{"number": 3}]},
    )
    await manager.map_source.async_refresh_map_state_source(vacuum_entity_id=_VAC, map_id="m")

    monkeypatch.setattr(                                             # Ivy idles: MapData gone
        msr, "roborock_result_from_candidates",
        lambda c, present: {"present": False, "reason": "no_parsed_map"},
    )
    out = await manager.map_source.async_refresh_map_state_source(
        vacuum_entity_id=_VAC, map_id="m"
    )

    assert out["present"] is True and out["rooms"] == [{"number": 3}]   # held through the drop
    assert out["stale"] is True and out["stale_reason"] == "no_parsed_map"


async def test_render_data_roborock_dispatches(manager, monkeypatch):
    """[RND-6] map_render.format roborock_raw_map_v1 dispatches to the raw-map render bridge,
    with room names sourced from the manager's stored rooms."""
    _register(
        source={"backend": "memory", "hass_data_domain": "roborock"},
        render={"format": "roborock_raw_map_v1"},
    )
    manager.data.setdefault("maps", {})[_VAC] = {
        "1": {"rooms": {"7": {"room_id": 7, "name": "Den"}}}
    }
    seen: dict = {}

    def _fake_bridge(candidates, room_names):
        seen["room_names"] = room_names
        return {"present": True, "format": "eufy_room_pixels_v1", "room_pixels": "x"}

    monkeypatch.setattr(msr, "roborock_candidates", lambda *a, **k: ["cand"])
    monkeypatch.setattr(msr, "roborock_render_data_from_candidates", _fake_bridge)

    out = await manager.map_source.async_get_map_render_data(vacuum_entity_id=_VAC)
    assert out["present"] is True and out["format"] == "eufy_room_pixels_v1"
    assert seen["room_names"] == {"7": "Den"}     # sourced from the manager's rooms
