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

import base64
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.eufy_vacuum import receipts
from custom_components.eufy_vacuum.listeners import stall_capture as sc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

#: A decodable 4x4 raster of room 27 -- the shape every adapter's render-data
#: block carries, used here so the geometry step SUCCEEDS where that is the
#: contrast and fails only on the property under test.
_B64 = base64.b64encode(bytes([27] * 16)).decode()


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


# ---------------------------------------------------------------------------
# [RC-C3] - [RC-C6]  THE OTHER FOUR DECLINES.
#
# The criterion above was demonstrated for TWO of this consumer's six decline
# reasons (`not_armed`, `no_render_data`). The other four -- `no_runtime`, `no_room`,
# `unusable` (twice) and `no_pillow` -- were emitted in code and reached by NOTHING,
# which is the same static-vs-runtime split this file's sibling records finding
# inside the instrument built to detect it: "a call SITE exists, not that it ever
# RUNS". A criterion that holds for a third of its own vocabulary is a criterion
# nobody has tested.
#
# ONE REASON IN THE VOCABULARY IS STILL UNEMITTABLE and is NOT closed here:
# `DECLINE_REASONS` declares `no_map`, all six emit sites live in this one module,
# and none of them emits it (the `no_map` strings in `mapping_services.py` and
# `setup/status.py` are a different vocabulary -- service refusal reasons). The
# receipts module's own docstring already names it as declared-but-never-emitted;
# it is recorded here because it is the same class of defect as the four below, not
# because this file closes it.
# ---------------------------------------------------------------------------

_PAYLOAD = {
    "vacuum_entity_id": "vacuum.ivy", "map_id": "Main floor",
    "room_id": 27, "room_name": "KITCHEN",
}


def _reasons(lines):
    """(receipt order, decline reasons) for one run -- the two things every test
    below asserts on. The ORDER is load-bearing: two of this module's six emit sites
    produce byte-identical facts, so reason alone cannot say which one fired."""
    import decode_receipts as dec

    recs = dec.parse(chr(10).join(lines))
    return (
        [r["msg"] for r in recs],
        [r["facts"][1] for r in recs if r["msg"] == "stall.capture.declined"],
        recs,
    )


async def test_rcc3_the_dump_alone_says_no_runtime(dump):
    """[RC-C3] The runtime is gone, so the listener heard the stall with nothing to
    act with -- and the decline still NAMES ITS OWN STATION.

    That naming is a deliberate reorder the code comments: the event's
    `vacuum_entity_id` is read BEFORE the runtime check so a decline can say who it
    was for. The full-list assertion below carries both halves -- the reason and the
    station -- because a separate test for the station could not fail without this
    one failing too, and a second id that cannot fail independently is a preference
    dressed as a claim.

    REACHABILITY, which is NOT the obvious one. `DATA_RUNTIME` is stored at
    `__init__.py:880` and this listener is registered 170 lines later at `:1050`, so
    there is no "event arrives before setup finishes" window. The live path is
    UNLOAD: `_on_stall` hands the capture to `hass.async_create_task` and returns,
    `remove()` only unsubscribes and cannot cancel a queued task, and unload runs
    `stall_capture.remove` (`:1281`) BEFORE popping `DATA_RUNTIME` (`:1341`). A stall
    landing moments before a reload runs `_capture` with the runtime already gone.

    TWO RED INPUTS, both measured:
    * delete the `if manager is None: ... return` block -- `is_enabled(None, ...)`
      then raises inside its own `try`, returns False, and the run declines
      `not_armed` instead;
    * move the four `event_data.get(...)` reads to below the runtime check --
      `UnboundLocalError` at the emit, which is the ordering comment's own red input.
    """
    # The domain bucket EXISTS and DATA_RUNTIME does not -- the shape an unload
    # leaves behind. The two sibling tests in this file populate
    # {DATA_RUNTIME: manager} and get past this guard, so the contrast that proves
    # the key is actually consulted lives in the file rather than in this test.
    hass = SimpleNamespace(data={sc.DOMAIN: {}})

    await sc._capture(hass, dict(_PAYLOAD))

    order, reasons, recs = _reasons(dump)
    assert order == ["stall.capture.declined"], (
        "nothing was there to hear with, so there is no `heard` before it: %s" % order
    )
    assert recs[0]["facts"] == ["vacuum.ivy", "no_runtime"], recs[0]["facts"]
    assert recs[0]["outcome"] == "D"


@pytest.mark.parametrize(
    "armed,drop",
    [
        pytest.param(True, "room_id", id="armed_no_room"),
        pytest.param(True, "vacuum_entity_id", id="no_vacuum_id"),
        pytest.param(False, "room_id", id="disarmed_no_room"),
    ],
)
async def test_rcc4_a_stall_with_no_room_declines_no_room(dump, armed, drop):
    """[RC-C4] No resolved room means nothing to render, and it outranks `not_armed`.

    THE THIRD CASE IS THE ONE THAT CARRIES THE ORDERING CLAIM, and the reason it
    exists is a measurement that contradicted the obvious reading. `is_enabled`
    returning True emits NOTHING, so with an ARMED vacuum both orderings produce one
    `no_room` decline -- armed is the single configuration in which the ordering is
    INVISIBLE. Moving this guard below the `is_enabled` check leaves `armed_no_room`
    green and reddens BOTH rows in which `is_enabled` is False -- the disarmed one
    and the empty-id one, since `is_enabled(manager, "")` is False too. (This
    docstring said "only `disarmed_no_room`" until an audit counted it; the
    ablation harness had predicted two all along, so the prose disagreed with the
    measurement that was sitting beside it.)

    The first case is still needed, for a different reason: it is the one that proves
    the guard prevents `int(None)` from raising out of the executor lambda further
    down.

    REACHABILITY, by half, measured against the three in-repo fire sites. The
    room-less payload is genuinely producible: `core/manager.py::_fire_stuck_event`
    takes `room_id` from `active_job["current_room_id"]` and NEITHER call site
    (`manager.py:5101`, `:5142`) gates on it. `detect_run_anomalies` cannot -- its
    fire sits under `if current_room_overdue and current_room_id is not None`
    (`jobs/active_job.py:1208`). The EMPTY-vacuum_entity_id half is reachable only
    from a hand-fired bus event: every in-repo producer takes the id from
    `get_known_vacuum_ids()` or from `cv.entity_id`-validated `call.data`. So 1 of 3
    producers reaches this guard, by one half only, and that is said rather than
    rounded up to "the real producers".

    RED: delete the `if not vacuum_entity_id or room_id is None: ... return` block.
    All three rows redden. ⚠ The MECHANISM for `armed_no_room` is not the one an
    earlier draft named: it dies at `AttributeError: 'types.SimpleNamespace' object
    has no attribute 'async_get_map_render_data'`, because this manager double
    carries only `data` -- execution never reaches `int(None)` at all. The other two
    decline `not_armed`, because `is_enabled` is False for an empty id and for a
    disarmed vacuum.
    """
    bucket = {"stall_capture_enabled": True} if armed else {}
    manager = SimpleNamespace(data={"vacuums": {"vacuum.ivy": bucket}})
    hass = SimpleNamespace(data={sc.DOMAIN: {sc.DATA_RUNTIME: manager}})

    # The SAME wired vacuum in every case -- the key is dropped from the PAYLOAD.
    # Naming a vacuum the install does not have would pass for the wrong reason.
    payload = {k: v for k, v in _PAYLOAD.items() if k != drop}

    await sc._capture(hass, payload)

    order, reasons, _recs = _reasons(dump)
    assert order == ["stall.capture.declined"], order
    assert reasons == ["no_room"], reasons


@pytest.mark.parametrize(
    "render",
    [
        pytest.param({"ro_width": 4, "ro_height": 4, "width": 4, "height": 4},
                     id="no_room_pixels"),
        pytest.param({"room_pixels": "!!!not base64!!!", "ro_width": 4,
                      "ro_height": 4}, id="undecodable"),
        pytest.param({"room_pixels": _B64, "ro_width": 0, "ro_height": 0},
                     id="zero_dims"),
    ],
)
async def test_rcc5_render_data_that_cannot_be_used_declines_unusable(dump, render):
    """[RC-C5] Present render data the geometry step refuses declines, not crashes.

    THREE CASES BECAUSE ONE WORD IS THREE CAUSES. The code comment is explicit that
    `unusable` stands for FOUR distinct causes across TWO emit sites; three of them
    are here (no `room_pixels`, `room_pixels` base64 will not decode, ro dimensions
    resolving to <= 0) and splitting them is C33, still open and a code change. A
    one-case test would leave two of them unexercised while reading as covered.

    REACHABILITY, stated narrowly because only one case survives the walk. Of the
    four producers `async_get_map_render_data` dispatches to, the UNDECODABLE case is
    the one reachable from real data: `render_data_from_storage` forwards the stored
    `room_pixels` as `str(rp_b64)` without ever decoding it, so a corrupt or
    truncated value in `.storage` arrives here present-and-undecodable. The other two
    are refused by every current producer (`map_source.py::render_data_from_storage`,
    `roborock_raw_map.py::roborock_render_data`) and are pinned here as this
    listener's contract
    against `_render_payload`'s documented None -- which is the seam a NEW adapter
    enters through.

    THE ORDER ASSERTION IS THE LOAD-BEARING ONE, and it must not be relaxed to a
    membership check. The other `unusable` emit site (the renderer returning None,
    pinned by [RC-C6]) produces byte-identical facts, so `facts` alone cannot say
    which site fired; its order runs on through pose and trail, and this one stops at
    two. (An earlier draft also credited it with surviving `register()`'s blanket
    `except`. That claim is empty here: this test awaits `_capture` directly, so
    `register()` is not in the path and nothing swallows anything.)

    RED: delete the `if geometry is None: ... return` block -- all three rows redden
    and no decline is emitted at all. ⚠ The MECHANISM is not the one an earlier
    draft named: it dies ~15 lines earlier at `AttributeError: ... no attribute
    'config'` on `hass.config.config_dir`, because this test's hass is the minimal
    one the decline path needs. The `**geometry` TypeError is what a FULL hass
    would give.
    """
    manager = SimpleNamespace(
        data={"vacuums": {"vacuum.ivy": {"stall_capture_enabled": True}}},
    )

    async def _render(**_kw):
        return {"present": True, **render}

    manager.async_get_map_render_data = _render
    hass = SimpleNamespace(data={sc.DOMAIN: {sc.DATA_RUNTIME: manager}})

    await sc._capture(hass, dict(_PAYLOAD))

    order, reasons, recs = _reasons(dump)
    assert order == ["stall.capture.heard", "stall.capture.declined"], order
    assert recs[-1]["facts"] == ["vacuum.ivy", "unusable"], recs[-1]["facts"]
    assert any("unusable render data" in m for m in dump), (
        "the site-unique debug line is what separates this emit from [RC-C6]'s"
    )


@pytest.mark.parametrize(
    "image,reason",
    [
        pytest.param(None, "no_pillow", id="pillow_absent"),
        pytest.param(object(), "unusable", id="pillow_present_no_cells"),
    ],
)
async def test_rcc6_nothing_to_render_names_which_absence(
    dump, tmp_path, monkeypatch, image, reason
):
    """[RC-C6] A missing picture says WHICH absence -- Pillow, or an empty room.

    Both produce no image, and the old comment called them "both ABSENCE" -- which is
    why `no image` was a four-way guess. They have DIFFERENT fixes (install the
    optional CV stack / look at the segmentation), so collapsing them destroys the
    only thing the receipt is for.

    BOTH ARMS ARE LIVE, checked rather than assumed: `manifest.json` requires only
    fonttools and brotli, so numpy/Pillow/scipy are OPTIONAL and UNDECLARED and
    `_scr.Image` is None on a plain install, while `roborock_raw_map.py:252` builds
    `room_pixels` with base64 alone -- so a no-Pillow Roborock install reaches this
    guard with geometry in hand. The other arm is the ordinary `if not cells` return.

    THE PAIR IS THE POINT, not the coverage: the discriminator is a TERNARY on one
    line, so covering that line once closes the units either way and only a CONTRAST
    between the two reasons shows the ternary is consulted at all. Collapsing it to
    either constant reddens exactly one of these two rows.

    AND THE DEBUG ASSERTION IS NOT DECORATION. `_render_payload`'s decline ([RC-C5])
    emits byte-identical facts for the `unusable` arm, so without the site-unique
    "nothing to render" string this test passes against a run that stopped 70 lines
    earlier -- measured. It is also the only red input for the `_LOGGER.debug` on
    this path.

    RED, three of them: collapse the ternary to `"unusable"` (reddens
    `pillow_absent`); collapse it to `"no_pillow"` (reddens the other); delete the
    `return` below it -- execution falls into `receipts.emit(... len(png))` with
    `png` None and raises TypeError. The STOP half is subsumed by that crash here,
    unlike [RC-H3] where a valid png flows on and the negative assertions bite
    independently.
    """
    from custom_components.eufy_vacuum.mapping import stall_capture_render as _scr

    manager = SimpleNamespace(
        data={"vacuums": {"vacuum.ivy": {"stall_capture_enabled": True}},
              "maps": {"vacuum.ivy": {"Main floor": {"live_map_rotation": 0}}}},
    )

    async def _render(**_kw):
        return {"present": True, "room_pixels": _B64, "ro_width": 4, "ro_height": 4,
                "width": 4, "height": 4}

    async def _pose(**_kw):
        return {"present": True, "robot_anchor": [0.5, 0.5]}

    manager.async_get_map_render_data = _render
    manager.async_get_map_live_pose = _pose

    monkeypatch.setattr(sc, "pose_refresh_seconds", lambda _v: 30.0)
    monkeypatch.setattr(sc, "_trail_from_ring", lambda *_a: [[0.4, 0.4]])
    # The renderer answering None is the whole premise; which ABSENCE it was is read
    # off the module attribute the failure path imports, so that is what varies.
    monkeypatch.setattr(sc, "render_room_capture", lambda **_k: None)
    monkeypatch.setattr(_scr, "Image", image, raising=False)

    async def _exec(func, *args):
        return func(*args)

    fired: list = []
    hass = SimpleNamespace(
        data={sc.DOMAIN: {sc.DATA_RUNTIME: manager}},
        bus=SimpleNamespace(async_fire=lambda ev, data: fired.append((ev, data)),
                            async_listeners=lambda: {}),
        config=SimpleNamespace(config_dir=str(tmp_path)),
        async_add_executor_job=_exec,
    )

    await sc._capture(hass, dict(_PAYLOAD))

    order, reasons, recs = _reasons(dump)
    assert recs[-1]["msg"] == "stall.capture.declined", order
    assert recs[-1]["facts"] == ["vacuum.ivy", reason], recs[-1]["facts"]
    assert any("nothing to render" in m for m in dump), (
        "without the site-unique line this passes against [RC-C5]'s emit: %s" % dump
    )
    assert not [r for r in recs
                if r["msg"].endswith((".rendered", ".written", ".announced"))], order
