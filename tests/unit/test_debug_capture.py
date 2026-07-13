"""Unit tests for the silent debug flight recorder (``debug_capture``).

The load-bearing guarantees: while active, the integration's DEBUG is captured into
the ring but does NOT reach the root handlers (no home-assistant.log flood), yet
INFO+ still passes through to the root; stop restores the logger exactly.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.eufy_vacuum.debug_capture import (
    TARGET_ALL_FLAGGED,
    TARGET_EVERYTHING,
    DebugCapture,
    build_debug_switch,
    build_debug_target_select,
    configure,
    debug_traceable,
    get_capture,
    render_text,
    traceable_services,
)

# The tests configure the recorder like a drop-in would — a package logger + areas.
PKG = "custom_components.eufy_vacuum"
TEST_AREAS = {"map": (".mapping", ".map_source"), "learning": (".learning",)}


@pytest.fixture(autouse=True)
def _configured():
    """Point the (module-global) recorder at a known logger tree for each test."""
    configure(PKG, TEST_AREAS)
    yield


class _FakeCall:
    def __init__(self, data):
        self.data = data


@debug_traceable("svc_demo")
async def _svc_demo(call):
    logging.getLogger(f"{PKG}.mapping.inner").debug("inner=%s", call.data.get("x"))
    return {"ok": True, "n": call.data.get("x")}


@pytest.fixture
def root_probe():
    """A record-collecting handler on the ROOT logger; yields the collected list."""
    seen: list[logging.LogRecord] = []

    class _Probe(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(record)

    handler = _Probe(level=logging.NOTSET)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield seen
    finally:
        root.removeHandler(handler)


@pytest.fixture
def capture():
    cap = DebugCapture()
    try:
        yield cap
    finally:
        cap.stop()  # always restore the global logger, even if a test fails


def _emit(suffix: str, level: int, msg: str, *args) -> None:
    logging.getLogger(f"{PKG}.{suffix}").log(level, msg, *args)


def test_captures_debug_with_formatted_message(capture):
    capture.start()
    _emit("mapping.x", logging.DEBUG, "segments=%d zones=%d", 3, 2)
    records = capture.records()
    assert len(records) == 1
    assert records[0]["level"] == "DEBUG"
    assert records[0]["message"] == "segments=3 zones=2"
    assert records[0]["logger"].endswith(".mapping.x")


def test_debug_does_not_reach_root_but_info_passes_through(capture, root_probe):
    capture.start()
    _emit("mapping.x", logging.DEBUG, "noisy debug line")
    _emit("mapping.x", logging.INFO, "an info line")
    _emit("mapping.x", logging.WARNING, "a warning line")

    # DEBUG is silent to the main log; INFO+ still reaches the root handlers.
    root_levels = [r.levelname for r in root_probe if r.name.startswith(PKG)]
    assert "DEBUG" not in root_levels
    assert "INFO" in root_levels
    assert "WARNING" in root_levels

    # …and all three are in the ring.
    ring_levels = [r["level"] for r in capture.records()]
    assert ring_levels == ["DEBUG", "INFO", "WARNING"]


def test_isolation_flags_while_active(capture):
    logger = logging.getLogger(PKG)
    capture.start()
    assert logger.propagate is False
    assert logger.level == logging.DEBUG
    assert capture.active is True


def test_stop_restores_logger_and_keeps_records(capture):
    logger = logging.getLogger(PKG)
    logger.setLevel(logging.WARNING)
    logger.propagate = True

    capture.start()
    _emit("dispatch.y", logging.DEBUG, "dispatch trace")
    status = capture.stop()

    assert capture.active is False
    assert logger.propagate is True
    assert logger.level == logging.WARNING
    # Records survive the stop for a final dump.
    assert status["captured"] == 1
    assert [r["message"] for r in capture.records()] == ["dispatch trace"]


def test_area_filter_scopes_capture(capture):
    capture.start(areas=["map"])
    _emit("mapping.services", logging.DEBUG, "a map line")
    _emit("learning.manager", logging.DEBUG, "a learning line")
    loggers = [r["logger"] for r in capture.records()]
    assert any(".mapping." in name for name in loggers)
    assert not any(".learning." in name for name in loggers)


def test_capacity_evicts_oldest(capture):
    capture.start(capacity=5)
    for i in range(12):
        _emit("mapping.x", logging.DEBUG, "line %d", i)
    records = capture.records()
    assert len(records) == 5  # bounded
    assert capture.status()["seen"] == 12  # but all were seen
    assert records[-1]["message"] == "line 11"  # newest kept
    assert records[0]["message"] == "line 7"  # oldest evicted


def test_restart_resets(capture):
    capture.start(capacity=100)
    _emit("mapping.x", logging.DEBUG, "first session")
    capture.start()  # restart
    assert capture.records() == []
    _emit("mapping.x", logging.DEBUG, "second session")
    assert [r["message"] for r in capture.records()] == ["second session"]


def test_stop_is_idempotent(capture):
    # Never started — stop must be a safe no-op that doesn't corrupt the logger.
    logger = logging.getLogger(PKG)
    before = (logger.level, logger.propagate)
    capture.stop()
    assert (logger.level, logger.propagate) == before


@pytest.fixture
def global_capture():
    """Reset + yield the process singleton (the decorator wraps against get_capture())."""
    import custom_components.eufy_vacuum.debug_capture as dc

    dc._CAPTURE = None
    cap = get_capture()
    try:
        yield cap
    finally:
        cap.stop()
        dc._CAPTURE = None


def test_debug_traceable_registers():
    assert "svc_demo" in traceable_services()


def test_configure_targets_the_given_logger(capture):
    """Agnostic: point it at another integration's tree — only that tree is captured,
    and everything else (incl. eufy_vacuum's own logs) is left alone."""
    configure("custom_components.some_other_integration", {})
    capture.start()
    logging.getLogger("custom_components.some_other_integration.foo").debug("theirs")
    logging.getLogger(f"{PKG}.mapping.x").debug("ours")  # outside the configured tree
    messages = [r["message"] for r in capture.records()]
    assert any("theirs" in m for m in messages)
    assert not any("ours" in m for m in messages)


def test_message_truncation(capture):
    capture.start()
    _emit("mapping.x", logging.DEBUG, "%s", "x" * 5000)
    msg = capture.records()[0]["message"]
    assert len(msg) < 5000
    assert "elided" in msg


def test_freeze_mode_keeps_first_n(capture):
    capture.start(capacity=3, freeze=True)
    for i in range(10):
        _emit("mapping.x", logging.DEBUG, "line %d", i)
    records = capture.records()
    assert [r["message"] for r in records] == ["line 0", "line 1", "line 2"]  # first N kept
    assert capture.status()["full"] is True
    assert capture.status()["seen"] == 10


@pytest.mark.asyncio
async def test_span_brackets_and_scopes_to_service(global_capture):
    global_capture.start(services=["svc_demo"])
    # A log OUTSIDE any span must NOT be captured (targeted mode).
    logging.getLogger(f"{PKG}.mapping.other").debug("outside the span")
    result = await _svc_demo(_FakeCall({"x": 7}))

    assert result == {"ok": True, "n": 7}
    messages = [r["message"] for r in global_capture.records()]
    assert any(m.startswith("▶▶ svc_demo") for m in messages)
    assert any(m.startswith("◀◀ svc_demo") for m in messages)
    assert any("inner=7" in m for m in messages)  # downstream log inside the span
    assert not any("outside the span" in m for m in messages)  # scoped out


@pytest.mark.asyncio
async def test_unarmed_service_not_bracketed(global_capture):
    global_capture.start(services=["other_service"])  # svc_demo is NOT armed
    result = await _svc_demo(_FakeCall({"x": 1}))
    assert result == {"ok": True, "n": 1}
    # Not a target -> not bracketed; targeted gate -> nothing captured at all.
    assert global_capture.records() == []


def test_target_kwargs_parsing(capture):
    capture.set_target("Service: start_zone_clean")
    assert capture.target_kwargs() == {"services": ["start_zone_clean"]}
    capture.set_target("Area: map")
    assert capture.target_kwargs() == {"areas": ["map"]}
    capture.set_target(TARGET_EVERYTHING)
    assert capture.target_kwargs() == {}
    # Default arms ALL flagged services (svc_demo is registered at import).
    capture.set_target(TARGET_ALL_FLAGGED)
    assert "svc_demo" in capture.target_kwargs()["services"]


@pytest.mark.asyncio
async def test_target_select_options_and_selection(global_capture):
    sel = build_debug_target_select(MagicMock(), domain="eufy_vacuum")
    sel.async_write_ha_state = MagicMock()
    opts = sel.options
    assert TARGET_ALL_FLAGGED in opts
    assert TARGET_EVERYTHING in opts
    assert "Service: svc_demo" in opts  # from the module-level @debug_traceable
    assert "Area: map" in opts  # from TEST_AREAS (autouse fixture)
    assert sel.current_option == TARGET_ALL_FLAGGED  # default
    await sel.async_select_option("Service: svc_demo")
    assert global_capture.get_target() == "Service: svc_demo"
    assert sel.current_option == "Service: svc_demo"


@pytest.mark.asyncio
async def test_switch_start_stop_and_autodump(global_capture):
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(return_value="/config/eufy_vacuum/debug/debug-x.log")
    sw = build_debug_switch(hass, domain="eufy_vacuum")
    sw.async_write_ha_state = MagicMock()

    assert sw.is_on is False
    global_capture.set_target(TARGET_EVERYTHING)  # unfiltered, so the plain log is caught
    await sw.async_turn_on()
    assert sw.is_on is True

    logging.getLogger(f"{PKG}.mapping.x").debug("captured line")
    await sw.async_turn_off()

    assert sw.is_on is False
    hass.async_add_executor_job.assert_awaited_once()  # auto-dump on off
    assert global_capture.last_dump_file == "/config/eufy_vacuum/debug/debug-x.log"


@pytest.mark.asyncio
async def test_concurrent_unrelated_log_not_captured(global_capture):
    """Headline fix: a concurrent unrelated log (its own context) during a traced op is
    NOT captured — only the operation's own async-context tree is."""
    global_capture.start(services=["svc_demo"])

    async def _unrelated():
        logging.getLogger(f"{PKG}.mapping.poll").debug("unrelated poll")

    await asyncio.gather(_svc_demo(_FakeCall({"x": 1})), _unrelated())

    messages = [r["message"] for r in global_capture.records()]
    assert any("inner=1" in m for m in messages)  # the traced op
    assert not any("unrelated poll" in m for m in messages)  # concurrent, other context


@pytest.mark.asyncio
async def test_span_marks_failure_outcome(global_capture):
    global_capture.start(services=["boom"])

    @debug_traceable("boom")
    async def boom(call):
        raise ValueError("kaboom")

    with pytest.raises(ValueError):
        await boom(_FakeCall({}))

    closing = [m for m in (r["message"] for r in global_capture.records()) if m.startswith("◀◀ boom")]
    assert closing and "failed: ValueError" in closing[0]


@pytest.mark.asyncio
async def test_fire_and_forget_child_inherits_trace(global_capture):
    """A task created inside the span inherits the op context, so its follow-through
    (which runs after the handler returns) is still captured."""
    global_capture.start(services=["ff_demo"])
    done = asyncio.Event()

    @debug_traceable("ff_demo")
    async def ff_demo(call):
        async def _child():
            logging.getLogger(f"{PKG}.dispatch.child").debug("child follow-through")
            done.set()

        asyncio.create_task(_child())
        return {"ok": True}

    await ff_demo(_FakeCall({}))
    await asyncio.wait_for(done.wait(), timeout=1)

    messages = [r["message"] for r in global_capture.records()]
    assert any("child follow-through" in m for m in messages)


def test_redaction_masks_secrets(capture):
    capture.start()
    _emit("mapping.x", logging.DEBUG, "connecting token=abc123secret ok")
    msg = capture.records()[0]["message"]
    assert "abc123secret" not in msg
    assert "«redacted»" in msg


def test_render_text_is_readable():
    text = render_text(
        [
            {"seq": 1, "t": 0.0, "level": "DEBUG", "logger": "custom_components.eufy_vacuum.mapping.x", "message": "hi"},
            {"seq": 2, "t": 0.0, "level": "ERROR", "logger": "custom_components.eufy_vacuum.core.manager", "message": "boom", "exc": "Traceback...\nValueError"},
        ]
    )
    assert "DEBUG" in text and "hi" in text
    assert "ERROR" in text and "boom" in text
    assert "ValueError" in text
    assert text.endswith("\n")
