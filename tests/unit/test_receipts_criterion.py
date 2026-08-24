"""[RC-C] THE PILOT'S SUCCESS CRITERION — the dump alone must explain a missing artifact.

This is the whole reason the stall chain was chosen as the vocabulary pilot
(`PROTOCOL-semantic-flight-recorder.md` item 6), and it is falsifiable rather than
aspirational because it replays a DATED incident.

On 2026-08-09 a real `dev_inject_stall` produced no image. Answering "why" took four
separate queries and a read of `.storage` — and that read returns PRESENT state, so if the
switch had been flipped afterwards it would have confidently reported the wrong cause. The
answer was `not_armed`: one of THIRTEEN return points in this consumer, TEN of which were
silent, and the three that spoke used `_LOGGER.debug` — visible only if a SEPARATE capture
was already armed before a failure nobody knew was coming.

The criterion: with receipts capturing, the dump ALONE answers it. No `.storage` read, no
present-state inference, no second arming switch.
"""
from __future__ import annotations

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
    """Capture the package logger the way debug_capture does when armed."""
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


async def test_rcc_the_dump_alone_says_not_armed(dump, monkeypatch):
    """[RC-C] Replay of the 2026-08-09 incident: disarmed vacuum, injected stall, no image."""
    manager = SimpleNamespace(data={"vacuums": {"vacuum.ivy": {}}})  # absent arming = OFF
    hass = SimpleNamespace(data={sc.DOMAIN: {sc.DATA_RUNTIME: manager}})

    # `dev_inject_stall` puts `"injected": True` in the event payload; nothing here reads it,
    # and no consumer branches on provenance either way (`receipts.PROVENANCE`: "Record it;
    # do not read it" — gating on the caller would build an injector that exercises a path
    # the real event never takes). Provenance marks the INJECTION POINT only and is never
    # inherited forward: every `receipts.emit` in this consumer omits `prov=`, so the receipt
    # carries `receipts.DEFAULT_PROVENANCE` ("live") — pinned by `d["prov"] == ["live"]` below.
    # ⚠ was: "everything it causes inherits the marker without any consumer knowing `synth`
    # exists" — false since the ContextVar build was dropped (receipts/__init__.py,
    # "PROVENANCE IS A PROPERTY OF THE RECEIPT, NOT OF A CONTEXT"). It contradicted the
    # assertion further down this same test, and was copied verbatim from item 8 of
    # PROTOCOL-semantic-flight-recorder.md, which still states the reversed rule.
    await sc._capture(hass, {
            "vacuum_entity_id": "vacuum.ivy",
            "map_id": "Main floor",
            "room_id": 27,
            "room_name": "KITCHEN",
            "injected": True,
        })

    import decode_receipts as dec

    recs = dec.parse("\n".join(dump))
    assert recs, "the consumer produced no receipts at all"

    declines = [r for r in recs if r["msg"] == "stall.capture.declined"]
    assert len(declines) == 1, f"expected exactly one decline, got {[r['msg'] for r in recs]}"

    d = declines[0]
    assert d["from"] == "listeners.stall_capture"
    assert d["outcome"] == "D", "a deliberate decline is not a failure and must not read as one"
    assert d["facts"] == ["vacuum.ivy", "not_armed"]
    # The consumer is LIVE even though the stimulus was synthetic — it really ran. What was
    # synthetic is the injection point, and provenance is not inherited forward.
    assert d["prov"] == ["live"]

    # THE CRITERION, stated as the sentence a human reads:
    prose = dec.render_prose(d, None)
    assert "not_armed" in prose
    assert "told not to answer" in prose, prose

    # And the negative half, which is what makes it evidence rather than a log line: the
    # consumer must NOT claim to have done anything. A decline that also reported work is
    # the confident liar §20 warns about.
    assert not [r for r in recs if r["msg"].endswith((".written", ".rendered", ".announced"))]


async def test_rcc_an_armed_run_does_not_decline(dump, monkeypatch):
    """[RC-C2] The mirror. If the decline fires when it should NOT, the criterion above
    passes for the wrong reason — a consumer that always declines would satisfy it."""
    manager = SimpleNamespace(data={"vacuums": {"vacuum.ivy": {"stall_capture_enabled": True}}})

    async def _no_render(**_kw):
        return {"present": False}

    manager.async_get_map_render_data = _no_render
    hass = SimpleNamespace(data={sc.DOMAIN: {sc.DATA_RUNTIME: manager}})

    await sc._capture(hass, {
        "vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
        "room_id": 27, "room_name": "KITCHEN",
    })

    import decode_receipts as dec

    recs = dec.parse("\n".join(dump))
    reasons = [r["facts"][1] for r in recs if r["msg"] == "stall.capture.declined"]
    assert reasons == ["no_render_data"], f"armed run declined for the wrong reason: {reasons}"
    assert any(r["msg"] == "stall.capture.heard" for r in recs), \
        "an armed consumer must report hearing the call before it declines downstream"
