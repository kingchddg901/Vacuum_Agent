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
        # Present so a test can DECLARE a map-name entity. Unused by the others:
        # with `get_adapter_value` left real there is no adapter config for
        # vacuum.ivy, so `map_label` returns the id without ever reaching here.
        states=SimpleNamespace(get=lambda _entity_id: None),
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

    # A DECLARED map name that differs from the map id, because that difference is
    # the only thing that can prove `map_label`'s answer is CONSUMED. Measured: with
    # the declaration absent, `map_label` falls back to `str(map_id)` and an
    # assertion on the message holds whether the call is made or not -- replacing
    # `label = map_label(...)` with `str(map_id)` left this test GREEN. [SL-11]
    # proves `map_label` HANDLES a list; only this proves `_capture` uses its answer.
    monkeypatch.setattr(
        sc, "get_adapter_value",
        lambda vid, *path, **kw: ("select.ivy_selected_map"
                                  if path[-1] == "active_map" else None),
    )
    hass.states = SimpleNamespace(
        get=lambda _e: SimpleNamespace(state="Upstairs"),
    )

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

    # THE EVENT PAYLOAD IS A DOCUMENTED PUBLIC CONTRACT (docs/advanced/02-events.md)
    # and nothing asserted a single field of it until 2026-11-08 -- only that SOME
    # event fired. Measured: making `image_path` carry `path + ".tmp"` survived the
    # whole suite, which is the one field the module docstring tells consumers to
    # USE ("not `map_id`, to reach the file"), so an automation reading it would
    # have opened a path that is deleted by the next write.
    assert len(fired) == 1, fired
    event, payload = fired[0]
    assert event == sc.EVENT_STALL_CAPTURED
    assert payload == {
        "vacuum_entity_id": "vacuum.ivy",
        "map_id": "Main floor",
        "room_id": 27,
        "room_name": "KITCHEN",
        "image_path": sc.capture_path(str(tmp_path), "vacuum.ivy", "Main floor"),
        "message": payload["message"],
    }, payload
    # The message is asserted for its CONTENT rather than pinned verbatim.
    assert "KITCHEN" in payload["message"], payload["message"]
    # THE DECLARED NAME, not the id -- this is the assertion `str(map_id)` cannot
    # satisfy, and the `not in` half is what stops a message carrying BOTH from
    # passing for the wrong reason.
    assert "on map Upstairs" in payload["message"], payload["message"]
    assert "Main floor" not in payload["message"], payload["message"]


@pytest.mark.parametrize("pose,expected", [
    pytest.param({"present": True}, "weak", id="answered_without_a_position"),
    pytest.param({"present": False}, "broken", id="answered_unusably"),
    pytest.param(None, "broken", id="did_not_answer"),
])
async def test_rch_a_poseless_brand_reads_weak_not_clear(
    dump, tmp_path, wired, monkeypatch, pose, expected
):
    """[RC-H2] The readability report has to DISCRIMINATE, or it is decoration.

    A brand whose map source answers but carries no position must read `weak`, not `lc`.
    That distinction is not hypothetical: it is exactly the state Roborock shipped in until
    2026-08-09 — an answer with no anchor, indistinguishable from a clean read, which is how
    a whole brand had no dot and nobody noticed.

    ALL THREE WORDS, because until 2026-11-08 only two of them were ever asserted and
    `broken` was dead vocabulary — collapsing it into `weak` survived the suite
    (measured). That is the same defect as the four decline reasons this campaign
    found unemitted, one layer over: a word that cannot be observed is not a
    distinction. `broken` means the source did not answer USABLY at all, which is a
    different fault from answering without a position — one is the source, the other
    is the robot.

    RED: collapse the ternary's `broken` arm into `weak`, and the two `broken` rows
    fail while `answered_without_a_position` stays green.
    """
    async def _poseless(**_kw):
        return pose

    wired.async_get_map_live_pose = _poseless
    hass = _hass(tmp_path, [], listeners=0)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                             "room_id": 27, "room_name": "KITCHEN"})

    import decode_receipts as dec

    by = {r["msg"]: r for r in dec.parse("\n".join(dump))}
    assert by["stall.capture.pose.observed"]["facts"][1] == expected
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


# ---------------------------------------------------------------------------
# [RC-H4] - [RC-H5]  TWO THINGS THAT MUST NOT COST THE CAPTURE.
#
# Both live in this file rather than beside the declines because the claim in each
# case is that the chain still COMPLETES -- a corrupt stored rotation costs the
# orientation, and an unarmed receipts logger costs nothing at all.
# ---------------------------------------------------------------------------

_PNG = b"\x89PNG" + b"x" * 96


def _recording_renderer(monkeypatch, seen):
    """Replace the renderer with one that records the kwargs it was handed."""
    def _render(**kw):
        seen.update(kw)
        return _PNG

    monkeypatch.setattr(sc, "render_room_capture", _render)


@pytest.mark.parametrize("stored", ["sideways", [90], {"deg": 90}, "90deg"])
async def test_rch4_a_corrupt_rotation_costs_the_orientation_not_the_capture(
    dump, tmp_path, wired, monkeypatch, stored
):
    """[RC-H4] A stored rotation `int()` cannot read falls back to 0 and the run finishes.

    The user's per-map rotation is display-only state the card applies. A capture at
    the raw raster angle is correct and UNRECOGNISABLE, which for a glanced
    notification is worse than no picture -- so the value is applied, and a value
    that will not coerce costs the ORIENTATION, never the capture.

    ALL FOUR SHAPES ARE TRUTHY, so the `or 0` cannot absorb them, and they cover both
    arms of the except tuple: `sideways`/`90deg` raise ValueError, `[90]`/`{...}`
    raise TypeError.

    REACHABLE ONLY FROM STATE NO IN-PACKAGE WRITER CAN EMIT, and that is said plainly
    rather than dressed up as an incident. The sole writer is
    `mapping_services.py::_handle_set_live_map_rotation`, schema-bound to
    `vol.All(vol.Coerce(int), vol.In([0, 90, 180, 270]))`, and `git log -S` shows the
    writer and that schema arrived in the SAME commit -- there was never a
    coerce-free version. What remains is the store: `core/storage.py` wraps HA's
    Store with no load-time validation, so a legacy or hand-edited `.storage` value
    reaches this read as-is. The IDENTICAL guard at `core/manager.py:6226-6229` is
    also uncovered, so the class was untested package-wide.

    ⚠ THE GUARD IS NARROWER THAN THIS TEST'S TITLE SUGGESTS, and the except tuple is
    where the line falls. The same external store that can put `sideways` at
    `live_map_rotation` can put a string or a list at `maps[vacuum][map_id]` -- and
    `.get` on that raises AttributeError, which this handler does NOT catch and
    nothing in `_capture` catches either. A corrupt VALUE costs the orientation; a
    corrupt BUCKET does cost the capture. Widening the tuple is a code change and a
    separate decision, not this test's to make.

    RED: replace the try/except with its bare body. The ValueError/TypeError then
    propagates out of `_capture`, the `written` receipt never fires and no event is
    fired -- and the contrast test below stays GREEN under that ablation, which is
    why both are needed.
    """
    seen: dict = {}
    _recording_renderer(monkeypatch, seen)
    wired.data["maps"]["vacuum.ivy"]["Main floor"]["live_map_rotation"] = stored

    fired: list = []
    hass = _hass(tmp_path, fired, listeners=1)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                             "room_id": 27, "room_name": "KITCHEN"})

    import decode_receipts as dec

    by = {r["msg"]: r for r in dec.parse(chr(10).join(dump))}
    assert seen["rotation_deg"] == 0, seen.get("rotation_deg")
    assert by["stall.capture.written"]["outcome"] == "P", "the capture was lost"
    assert fired and fired[0][0] == sc.EVENT_STALL_CAPTURED


@pytest.mark.parametrize("stored,expected", [
    pytest.param(270, 270, id="a_declared_angle"),
    pytest.param(450, 90, id="past_a_full_turn"),
])
async def test_rch4b_a_good_rotation_reaches_the_renderer(
    dump, tmp_path, wired, monkeypatch, stored, expected
):
    """[RC-H4] The contrast, and without it the test above is vacuous.

    A renderer that ignored `rotation_deg` entirely, or a bucket read that resolved to
    `{}` for the wrong reason, would satisfy `rotation_deg == 0` for all four corrupt
    shapes. Only a stored value arriving INTACT shows the read is consulted at all --
    the empty-container trap in another costume.

    450 IS THE SECOND ROW BECAUSE 270 IS ITS OWN MODULO FIXED POINT. With only 270
    declared, dropping the `% 360` entirely left this GREEN (measured) -- so the
    normalisation had no red input at all, and it is in the same reachability class
    as the `except` beside it: an unvalidated `.storage` value. A renderer handed 450
    degrees is not a wrong angle, it is an angle no canvas transform expects.

    RED: this one stays green under [RC-H4]'s ablation and goes red if the rotation
    read or its pass-through is dropped, or if `% 360` is dropped (the 450 row only).
    """
    seen: dict = {}
    _recording_renderer(monkeypatch, seen)
    wired.data["maps"]["vacuum.ivy"]["Main floor"]["live_map_rotation"] = stored

    hass = _hass(tmp_path, [], listeners=1)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
                             "room_id": 27, "room_name": "KITCHEN"})

    assert seen["rotation_deg"] == expected, seen.get("rotation_deg")


async def test_rch5_an_unarmed_run_does_not_count_the_net(tmp_path, wired):
    """[RC-H5] With nothing capturing receipts, the net is not counted at all.

    The all-stations announcement's third fact is
    `hass.bus.async_listeners().get(EVENT_STALL_CAPTURED, 0)` -- the listener COUNT is
    what makes the broadcast's silence readable. The guard exists so that counting
    the net is not paid for when nobody is listening to the receipt, and on a live box
    HA's `async_listeners` is a comprehension over EVERY registered event type, so it
    is not a token cost.

    THIS IS SUBSUMED UNLESS THE NON-CALL IS THE OBSERVABLE, and that is why the test
    is shaped the way it is. Unarmed, `receipts.emit` returns at its own first line,
    so the guard changes no outcome, no raise and no disk state. The ONE thing that
    distinguishes it is that Python evaluates the argument BEFORE calling `emit` --
    so with the guard gone, the net is counted on every capture. Assert that
    non-call, or there is nothing here.

    DELIBERATELY NOT USING THE `dump` FIXTURE: it sets the package logger to DEBUG,
    which is exactly the state this test needs absent -- which is also why every
    existing test that reaches this line takes the armed arm. `assert not
    receipts.armed()` is the precondition that fails closed if DEBUG is left on the
    receipts logger itself.

    RED: delete `if receipts.armed():` and dedent the emit -- `async_listeners()` is
    then called on every capture and `calls` is non-empty.
    """
    calls: list = []
    fired: list = []
    # `listeners=` is deliberately absent: the recorder below REPLACES
    # `bus.async_listeners` wholesale, so a value passed here would be dead and read
    # as if it mattered.
    hass = _hass(tmp_path, fired, listeners=0)
    hass.data = {sc.DOMAIN: {sc.DATA_RUNTIME: wired}}

    def _recording_listeners():
        calls.append(1)
        return {sc.EVENT_STALL_CAPTURED: 3}

    hass.bus.async_listeners = _recording_listeners

    logger = logging.getLogger("custom_components.eufy_vacuum")
    lvl = logger.level
    logger.setLevel(logging.INFO)
    try:
        assert not receipts.armed(), "the precondition for this test is not armed"
        await sc._capture(hass, {"vacuum_entity_id": "vacuum.ivy",
                                 "map_id": "Main floor", "room_id": 27,
                                 "room_name": "KITCHEN"})
    finally:
        logger.setLevel(lvl)

    # The positive control, and it comes FIRST: `async_fire` is the line immediately
    # above the guard, so a fired event PROVES the guard was reached. Without it the
    # assertion below would pass on a run that returned early.
    assert fired and fired[0][0] == sc.EVENT_STALL_CAPTURED, (
        "nothing about receipts may gate the user-visible announcement"
    )
    assert calls == [], "unarmed, async_listeners() must not be called"

    # ...and the recorder must be able to SEE a call, or the line above is a
    # tautology the day `_hass` rebuilds its bus or HA renames the method.
    assert hass.bus.async_listeners() == {sc.EVENT_STALL_CAPTURED: 3}
    assert calls == [1], "the recorder never observed a call it did see"
