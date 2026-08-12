"""[RC-H] THE HAPPY PATH — success must actually speak, and be tested doing it.

WHY THIS FILE EXISTS, recorded because the omission is the more useful lesson than the fix.
The pilot's first two tests both ended in a DECLINE (`not_armed`, `no_render_data`). Six of
the nine catalog keys — every receipt on the success side — were emitted in code and reached
by NOTHING. A system whose founding rule is "success is not allowed to be silent" had no test
that success speaks.

And the gate could not have caught it. `check_receipts.py` is a static AST scan: it proves a
call SITE exists, not that it ever RUNS. That is `feedback_audit_callsite_reachability`
reproduced inside the instrument built to detect it — "a correct service with ZERO callers
passes every audit". Static reachability and runtime reachability are different questions,
and only one of them was being asked.

So this test asserts the CHAIN, not just its endpoints: heard -> pose called -> pose observed
-> trail read -> rendered -> written -> announced, in order, with provenance intact.

AND IT CLAIMS ONLY WHAT THIS PILOT DEMONSTRATES. An earlier draft asserted a "two-party
edge" — the call addressed to `map.source` and a reply coming back FROM it. Both halves were
written by THIS listener, because map.source has no instrumentation: one station holding both
ends of a conversation, which is the pass-through problem wearing the protocol's clothes. A
real two-party edge needs the other station to speak for itself, and that is chain-pilot work.
This pilot is honestly ONE-PARTY, and the assertion below pins that rather than hiding it.
"""
from __future__ import annotations

import base64
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum import receipts
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


def _hass(tmp_path, fired: list, listeners: int):
    async def _exec(func, *args):
        return func(*args)

    bus = SimpleNamespace(
        async_fire=lambda ev, data: fired.append((ev, data)),
        async_listeners=lambda: {sc.EVENT_STALL_CAPTURED: listeners},
    )
    return SimpleNamespace(
        data={}, bus=bus,
        config=SimpleNamespace(config_dir=str(tmp_path)),
        async_add_executor_job=_exec,
    )


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """An armed vacuum with a decodable map, a live pose, and a renderer that returns bytes."""
    manager = SimpleNamespace(
        data={"vacuums": {"vacuum.ivy": {"stall_capture_enabled": True}},
              "maps": {"vacuum.ivy": {"Main floor": {"live_map_rotation": 0}}}},
    )

    async def _render(**_kw):
        return {"present": True, "room_pixels": base64.b64encode(bytes([27] * 16)).decode(),
                "ro_width": 4, "ro_height": 4, "width": 4, "height": 4}

    async def _pose(**_kw):
        return {"present": True, "robot_anchor": [0.5, 0.5]}

    manager.async_get_map_render_data = _render
    manager.async_get_map_live_pose = _pose

    monkeypatch.setattr(sc, "pose_refresh_seconds", lambda _v: 30.0)
    monkeypatch.setattr(sc, "_trail_from_ring", lambda *_a: [[0.4, 0.4], [0.5, 0.5]])
    monkeypatch.setattr(sc, "render_room_capture", lambda **_k: b"\x89PNG" + b"x" * 96)
    monkeypatch.setattr(sc, "_write_atomic", lambda *_a: None)
    return manager


async def test_rch_the_whole_chain_speaks(dump, tmp_path, wired, monkeypatch):
    """[RC-H] Every success receipt fires, in causal order, with its edges consistent."""
    fired: list = []
    hass = _hass(tmp_path, fired, listeners=2)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                             "room_id": 27, "room_name": "KITCHEN"})

    import decode_receipts as dec

    recs = dec.parse("\n".join(dump))
    order = [r["msg"] for r in recs]

    assert order == [
        "stall.capture.heard",
        "stall.capture.pose.called",
        "stall.capture.pose.observed",
        "stall.capture.trail.read",
        "stall.capture.rendered",
        "stall.capture.written",
        "stall.capture.announced",
    ], order

    # NOTHING declined on a run that succeeded — a chain that both works and declines is
    # the confident liar, and it would still satisfy an order-only assertion.
    assert not [r for r in recs if r["outcome"] == "D"]

    by = {r["msg"]: r for r in recs}

    # THE CALL is addressed to the station being called — that half is real.
    assert by["stall.capture.pose.called"]["to"] == "mapping.map_source"

    # A STATION MAY ONLY SPEAK AS ITSELF, and every receipt here comes from one module.
    # An earlier draft emitted `from=map.source` out of this listener and the test asserted
    # a "two-party edge" — but BOTH halves were written by the same station, which is the
    # pass-through problem wearing the protocol's clothes. A genuine two-party edge needs
    # map.source instrumented to speak for itself; that is chain-pilot work, and this pilot
    # is HONESTLY ONE-PARTY until then.
    assert {r["from"] for r in recs} == {"listeners.stall_capture"}

    # A pose that carried a position reads loud and clear — the readability report exists
    # to DISCRIMINATE, which [RC-H2] pins from the other side.
    assert by["stall.capture.pose.observed"]["facts"][1] == "lc"

    # The broadcast reports how many stations were on the net. Zero would mean silence is
    # CORRECT; two means an unanswered call would be a real fault.
    assert by["stall.capture.announced"]["facts"][2] == "2"
    assert by["stall.capture.announced"]["to"] == "ANY"

    # The map id survived the wire intact — this is the encoding bug the pilot found on its
    # first run, pinned here on the real path rather than only in a unit round-trip.
    assert by["stall.capture.heard"]["facts"][1] == "Main floor"

    assert all(r["prov"] == ["live"] for r in recs)
    assert fired and fired[0][0] == sc.EVENT_STALL_CAPTURED


async def test_rch_a_poseless_brand_reads_weak_not_clear(dump, tmp_path, wired, monkeypatch):
    """[RC-H2] The readability report has to DISCRIMINATE, or it is decoration.

    A brand whose map source answers but carries no position must read `weak`, not `lc`.
    That distinction is not hypothetical: it is exactly the state Roborock shipped in until
    2026-08-09 — an answer with no anchor, indistinguishable from a clean read, which is how
    a whole brand had no dot and nobody noticed.
    """
    async def _poseless(**_kw):
        return {"present": True}  # answered, no anchor

    wired.async_get_map_live_pose = _poseless
    hass = _hass(tmp_path, [], listeners=0)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                             "room_id": 27, "room_name": "KITCHEN"})

    import decode_receipts as dec

    by = {r["msg"]: r for r in dec.parse("\n".join(dump))}
    assert by["stall.capture.pose.observed"]["facts"][1] == "weak"
    # and the run still completes — a weak pose costs the dot, never the capture
    assert "stall.capture.written" in by
    # zero listeners is recorded, so a silent net is distinguishable from a lost broadcast
    assert by["stall.capture.announced"]["facts"][2] == "0"


async def test_rch3_a_write_failure_speaks_then_stops(dump, tmp_path, wired, monkeypatch):
    """[RC-H3] A FAILURE MAY NOT BE SILENT EITHER — §4's rule has a sibling.

    Before this, a write that raised aborted the capture and emitted NOTHING: the chain
    simply stopped after `rendered`, and an unexplained absence is the four-way guess this
    pilot exists to end. It now reports F and stops — with no artifact on disk there is
    nothing to notify about and nothing to announce, so continuing would be the confident
    liar in the other direction.

    Written because the GATE could not have caught this. It sees the F call site statically
    and is satisfied; only running the path proves it fires — the same static-vs-runtime
    split that hid six unreached success receipts.
    """
    def _boom(*_a):
        raise OSError("no space left on device")

    monkeypatch.setattr(sc, "_write_atomic", _boom)
    fired: list = []
    hass = _hass(tmp_path, fired, listeners=1)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                             "room_id": 27, "room_name": "KITCHEN"})

    import decode_receipts as dec

    recs = dec.parse(chr(10).join(dump))
    by = {r["msg"]: r for r in recs}

    assert by["stall.capture.written"]["outcome"] == "F"
    assert "stall.capture.announced" not in by, "nothing to announce without an artifact"
    assert not fired, "no event may claim a capture that does not exist"
    # and the failure is the LAST thing said — the chain stops rather than trailing off
    assert recs[-1]["msg"] == "stall.capture.written"
