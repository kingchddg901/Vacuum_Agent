"""The live-pose backend seam — ``async_get_map_live_pose``'s brand dispatch.

WHAT THIS FILE EXISTS TO PREVENT. This accessor was the eufy-clean fork reader wearing a
generic name. It required a ``map_state_source.live_pose`` block whose every key described
the fork's in-memory pixel coordinator, so a brand that could not describe itself in those
terms got ``not_configured`` — an answer no consumer can distinguish from "this brand has
no robot position". Roborock hit exactly that: its position was live on the parsed MapData
the card rendered every refresh, while the stall capture drew rooms with no dot in them and
the pose ring banked rows with no anchors (verified end-to-end on the maintainer's box,
2026-08-09).

So the tests here are all about the DECLARATION, not the geometry (the projection itself is
covered in ``test_map_source_runtime.py``):

[LP-1] a brand's declared backend selects the reader — nothing sniffs which keys are present.
[LP-2] no backend is a default; an undeclared or unknown one says so rather than falling
       through to some brand's reader.
[LP-3] the pixel-pose override path is gated on the pixel backend, so a parsed-map brand
       can never drive the fork's attr walk over an unrelated provider's internals.
"""

from __future__ import annotations

import pytest

from custom_components.eufy_vacuum.mapping import map_source_coordinator as msc
from custom_components.eufy_vacuum.mapping.map_source_coordinator import (
    POSE_BACKEND_INMEM_PIXELS,
    POSE_BACKEND_PARSED_MAPDATA,
    MapSourceCoordinator,
)


class _Manager:
    """Just enough manager for the coordinator's constructor and hass reads."""

    def __init__(self):
        self.hass = object()


def _coordinator():
    return MapSourceCoordinator(manager=_Manager())


def _with_config(monkeypatch, config):
    monkeypatch.setattr(msc, "_get_adapter_config", lambda _vid: config)


# ---------------------------------------------------------------------------
# [LP-1] the declaration selects the reader
# ---------------------------------------------------------------------------

async def test_a_parsed_mapdata_brand_gets_its_pose(monkeypatch):
    """[LP-1] THE BUG, AS A PASSING TEST.

    A brand whose position rides its in-memory parsed map declares that, and the accessor
    reads it. Before the dispatch existed this returned ``not_configured`` and every
    consumer — the stall capture's dot, the pose sampler's anchor — read it as "no
    position".
    """
    _with_config(monkeypatch, {
        "map_state_source": {
            "backend": "memory",
            "hass_data_domain": "roborock",
            "live_pose": {"backend": POSE_BACKEND_PARSED_MAPDATA, "pose_refresh_s": 30.0},
        }
    })

    from custom_components.eufy_vacuum.mapping import map_source_runtime as _msr

    monkeypatch.setattr(_msr, "roborock_candidates", lambda *a, **kw: [("rt", "e1", object())])
    monkeypatch.setattr(
        _msr, "mapdata_live_pose_from_candidates",
        lambda _c: {"present": True, "robot_anchor": [0.694, 0.509], "robot_heading": 67},
    )

    pose = await _coordinator().async_get_map_live_pose(vacuum_entity_id="vacuum.ivy")

    assert pose["present"] is True
    assert pose["robot_anchor"] == [0.694, 0.509]


async def test_the_parsed_mapdata_reader_never_touches_the_pixel_walk(monkeypatch):
    """[LP-1] The two readers are exclusive.

    Running the fork's attr walk against another provider's internals finds nothing and
    then pays for a full structure dump to say so — on every refresh.
    """
    _with_config(monkeypatch, {
        "map_state_source": {
            "backend": "memory",
            "live_pose": {"backend": POSE_BACKEND_PARSED_MAPDATA, "pose_refresh_s": 30.0},
        }
    })

    def _must_not_run(*_a, **_kw):
        raise AssertionError("the pixel-pose reader ran for a parsed-mapdata brand")

    monkeypatch.setattr(MapSourceCoordinator, "_read_inmem_pose", _must_not_run)

    from custom_components.eufy_vacuum.mapping import map_source_runtime as _msr

    monkeypatch.setattr(_msr, "roborock_candidates", lambda *a, **kw: [])
    monkeypatch.setattr(
        _msr, "mapdata_live_pose_from_candidates",
        lambda _c: {"present": False, "reason": "no_parsed_map"},
    )

    pose = await _coordinator().async_get_map_live_pose(vacuum_entity_id="vacuum.ivy")

    assert pose["present"] is False and pose["reason"] == "no_parsed_map"


# ---------------------------------------------------------------------------
# [LP-2] no backend is a default
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("declared", [{}, {"backend": ""}, {"backend": "guesswork"}])
async def test_an_undeclared_backend_does_not_fall_through_to_a_brand(monkeypatch, declared):
    """[LP-2] The fallback IS the defect, so there is no fallback.

    A block that names no backend must not quietly run the fork reader: that is how the
    accessor came to mean "the Eufy path" in the first place, and it would rediscover the
    same silence from the other direction — a brand whose block is a typo would appear to
    have no position rather than a bad declaration.
    """
    _with_config(monkeypatch, {"map_state_source": {"live_pose": declared}})

    def _must_not_run(*_a, **_kw):
        raise AssertionError("an undeclared backend fell through to the pixel reader")

    monkeypatch.setattr(MapSourceCoordinator, "_read_inmem_pose", _must_not_run)

    pose = await _coordinator().async_get_map_live_pose(vacuum_entity_id="vacuum.mystery")

    assert pose["present"] is False
    assert pose["reason"].startswith("unknown_pose_backend:")


async def test_no_live_pose_block_is_still_not_configured(monkeypatch):
    """[LP-2] A brand with no pose at all keeps the honest, pre-existing answer."""
    _with_config(monkeypatch, {"map_state_source": {"backend": "memory"}})

    pose = await _coordinator().async_get_map_live_pose(vacuum_entity_id="vacuum.plain")

    assert pose == {"present": False, "reason": "not_configured"}


async def test_the_pixel_backend_still_runs_the_fork_reader(monkeypatch):
    """[LP-2] The change is additive: Eufy's path is reached exactly as before."""
    _with_config(monkeypatch, {
        "map_state_source": {
            "backend": "storage",
            "live_pose": {"backend": POSE_BACKEND_INMEM_PIXELS, "pose_refresh_s": 2.0},
        }
    })
    called: dict = {}

    def _read(_self, vid, live_cfg):
        called["vid"] = vid
        return {"present": False, "reason": "no_pose", "diagnostics": {}}

    monkeypatch.setattr(MapSourceCoordinator, "_read_inmem_pose", _read)

    pose = await _coordinator().async_get_map_live_pose(vacuum_entity_id="vacuum.alfred")

    assert called["vid"] == "vacuum.alfred"
    assert pose["present"] is False and pose["reason"] == "no_pose"


# ---------------------------------------------------------------------------
# [LP-3] the snapshot override path is gated too
# ---------------------------------------------------------------------------

def test_the_pixel_override_is_gated_on_the_pixel_backend(monkeypatch):
    """[LP-3] The OTHER door into the fork walk.

    ``_apply_inmem_pose_to_result`` runs on the event loop inside the dashboard snapshot
    and used to gate on the block merely being a dict. Once a second brand declares a
    ``live_pose``, that check would let a parsed-map brand in — walking a provider graph
    that cannot match, then dumping its structure, on every snapshot.

    RECORDED, NOT RAISED. A stub that raises proves nothing here: the method wraps its body
    in ``except Exception`` by design (a provider internal must never abort the snapshot),
    so it swallows the probe and the test passes with the gate removed. Caught by ablation
    — the first version of this test was green either way.
    """
    called: list[str] = []

    def _read(_self, vid, _live_cfg):
        called.append(vid)
        # A pose that WOULD change the result, so "unchanged" means "never read" rather
        # than "read and had nothing to say".
        return {"present": True, "robot_pixel": [1, 1], "dock_pixel": [2, 2],
                "robot_heading": 90, "trail_pixels": None}

    monkeypatch.setattr(MapSourceCoordinator, "_read_inmem_pose", _read)
    result = {"present": True}

    _coordinator()._apply_inmem_pose_to_result(
        result, {"width": 100, "height": 100}, "vacuum.ivy",
        {"backend": POSE_BACKEND_PARSED_MAPDATA, "pose_refresh_s": 30.0},
    )

    assert called == [], "the pixel walk ran for a parsed-mapdata brand"
    assert result == {"present": True}, "the base overlays must be left untouched"


def test_the_pixel_override_still_runs_for_the_pixel_backend(monkeypatch):
    """[LP-3] The gate must not disable the path it is protecting."""
    called: dict = {}

    def _read(_self, vid, live_cfg):
        called["vid"] = vid
        return {"present": False}

    monkeypatch.setattr(MapSourceCoordinator, "_read_inmem_pose", _read)

    _coordinator()._apply_inmem_pose_to_result(
        {"present": True}, {}, "vacuum.alfred",
        {"backend": POSE_BACKEND_INMEM_PIXELS},
    )

    assert called["vid"] == "vacuum.alfred"
