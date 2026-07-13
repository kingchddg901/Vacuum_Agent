"""Unit tests for the silent debug flight recorder (``debug_capture``).

The load-bearing guarantees: while active, the integration's DEBUG is captured into
the ring but does NOT reach the root handlers (no home-assistant.log flood), yet
INFO+ still passes through to the root; stop restores the logger exactly.
"""

from __future__ import annotations

import logging

import pytest

from custom_components.eufy_vacuum.debug_capture import (
    PACKAGE_LOGGER,
    DebugCapture,
    render_text,
)


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
    logging.getLogger(f"{PACKAGE_LOGGER}.{suffix}").log(level, msg, *args)


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
    root_levels = [r.levelname for r in root_probe if r.name.startswith(PACKAGE_LOGGER)]
    assert "DEBUG" not in root_levels
    assert "INFO" in root_levels
    assert "WARNING" in root_levels

    # …and all three are in the ring.
    ring_levels = [r["level"] for r in capture.records()]
    assert ring_levels == ["DEBUG", "INFO", "WARNING"]


def test_isolation_flags_while_active(capture):
    logger = logging.getLogger(PACKAGE_LOGGER)
    capture.start()
    assert logger.propagate is False
    assert logger.level == logging.DEBUG
    assert capture.active is True


def test_stop_restores_logger_and_keeps_records(capture):
    logger = logging.getLogger(PACKAGE_LOGGER)
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
    logger = logging.getLogger(PACKAGE_LOGGER)
    before = (logger.level, logger.propagate)
    capture.stop()
    assert (logger.level, logger.propagate) == before


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
