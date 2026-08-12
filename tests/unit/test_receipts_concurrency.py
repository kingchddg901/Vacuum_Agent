"""[RC-X] TWO CAPTURES AT ONCE — is a dump still attributable?

§10: "Chronological order tells what happened near each other. Correlation tells what
belonged together." The pilot has NO correlation id, so this asks whether that is a latent
defect or an actual one at this scope.

Two vacuums stall simultaneously. Their receipts interleave in one ring. The question is
whether a reader can reconstruct which chain is which — and, more importantly, whether the
mechanism that lets them is DESIGNED or ACCIDENTAL. A property that holds by luck is one
that breaks the first time a chain crosses a subsystem that does not happen to carry the
same fact.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum.listeners import stall_capture as sc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


@pytest.fixture
def dump():
    logger = logging.getLogger("custom_components.eufy_vacuum")
    lines: list[str] = []

    class _H(logging.Handler):
        def emit(self, record):  # noqa: D102
            lines.append(record.getMessage())

    h = _H()
    lvl, prop = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(h)
    try:
        yield lines
    finally:
        logger.removeHandler(h)
        logger.setLevel(lvl)
        logger.propagate = prop


@pytest.fixture
def two_vacuums(tmp_path, monkeypatch):
    """Ivy and Alfred, both armed, both renderable — and INTERLEAVED on purpose.

    Each async boundary yields, so the two chains genuinely take turns rather than running
    to completion one after the other. A test that let them run sequentially would prove
    nothing about attribution.
    """
    manager = SimpleNamespace(data={
        "vacuums": {"vacuum.ivy": {"stall_capture_enabled": True},
                    "vacuum.alfred": {"stall_capture_enabled": True}},
        "maps": {"vacuum.ivy": {"Main floor": {}}, "vacuum.alfred": {"12": {}}},
    })

    async def _render(**_kw):
        await asyncio.sleep(0)
        return {"present": True, "room_pixels": base64.b64encode(bytes([27] * 16)).decode(),
                "ro_width": 4, "ro_height": 4, "width": 4, "height": 4}

    async def _pose(**_kw):
        await asyncio.sleep(0)
        return {"present": True, "robot_anchor": [0.5, 0.5]}

    manager.async_get_map_render_data = _render
    manager.async_get_map_live_pose = _pose

    monkeypatch.setattr(sc, "pose_refresh_seconds", lambda _v: 30.0)
    monkeypatch.setattr(sc, "_trail_from_ring", lambda *_a: [[0.4, 0.4], [0.5, 0.5]])
    monkeypatch.setattr(sc, "render_room_capture", lambda **_k: b"\x89PNG" + b"y" * 64)
    monkeypatch.setattr(sc, "_write_atomic", lambda *_a: None)

    async def _exec(func, *args):
        await asyncio.sleep(0)
        return func(*args)

    bus = SimpleNamespace(async_fire=lambda *_a: None,
                          async_listeners=lambda: {sc.EVENT_STALL_CAPTURED: 1})
    hass = SimpleNamespace(
        data={sc.DOMAIN: {sc.DATA_RUNTIME: manager}}, bus=bus,
        config=SimpleNamespace(config_dir=str(tmp_path)), async_add_executor_job=_exec,
    )
    return hass


async def test_rcx_two_chains_interleave_and_stay_attributable(dump, two_vacuums):
    """[RC-X] Both chains complete, their receipts interleave, and each is separable."""
    await asyncio.gather(
        sc._capture(two_vacuums, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                                  "room_id": 27, "room_name": "KITCHEN"}),
        sc._capture(two_vacuums, {"vacuum_entity_id": "vacuum.alfred", "map_id": "12",
                                  "room_id": 7, "room_name": "Dining Room"}),
    )

    import decode_receipts as dec

    recs = dec.parse("\n".join(dump))
    assert len(recs) == 14, [r["msg"] for r in recs]

    # THE PRECONDITION. If the two ran to completion one after the other, this test would
    # prove nothing about attribution — it would just be two sequential dumps concatenated.
    order = [r["facts"][0] for r in recs]
    assert order != sorted(order, key=lambda v: v != "vacuum.ivy"), \
        "the chains did not actually interleave; this test is not testing what it claims"

    # Separable — but note HOW. Every receipt in this chain happens to carry the vacuum as
    # its FIRST fact, so the reader groups by a domain value, not by a correlation id.
    ivy = [r for r in recs if r["facts"][0] == "vacuum.ivy"]
    alfred = [r for r in recs if r["facts"][0] == "vacuum.alfred"]
    assert len(ivy) == len(alfred) == 7
    assert [r["msg"] for r in ivy] == [r["msg"] for r in alfred]


async def test_rcx_attribution_here_is_accidental_not_designed(dump, two_vacuums):
    """[RC-X2] The finding, pinned so it is not mistaken for a solved problem.

    Grouping works ONLY because every receipt in this chain carries `vacuum` as a fact. That
    is a property of this catalog, not of the protocol: the moment a chain reaches a station
    whose facts do not include the vacuum — a shared renderer, a store keyed by path, a
    queue — the grouping key vanishes and chronology is all that is left. §10 says exactly
    that: "chronological order tells what happened NEAR each other."

    So this asserts the DEPENDENCY rather than the capability, and it will fail the first
    time a receipt is added without the vacuum — which is the moment to add a correlation id
    rather than the moment to discover it is missing.
    """
    await asyncio.gather(
        sc._capture(two_vacuums, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                                  "room_id": 27, "room_name": "KITCHEN"}),
        sc._capture(two_vacuums, {"vacuum_entity_id": "vacuum.alfred", "map_id": "12",
                                  "room_id": 7, "room_name": "Dining Room"}),
    )

    import decode_receipts as dec

    recs = dec.parse("\n".join(dump))

    # There is NO correlation field on the wire — attribution rests entirely on a fact.
    assert all("corr" not in r for r in recs)
    assert all(r["facts"] and r["facts"][0].startswith("vacuum.") for r in recs), (
        "every receipt must carry the vacuum first, because that is the ONLY thing making "
        "this dump attributable. If this fails, the pilot needs a correlation id."
    )
